"""Whop access checks, user-token verification, and webhooks.

Endpoints and helpers come from the official Whop docs / Python SDK
(`whop-sdk`): GET /users/{id}/access/{resource_id}, verify_user_token,
POST /experiences, POST /experiences/{id}/attach.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any

from whop_sdk import Whop
from whop_sdk.lib.verify_user_token import try_verify_user_token

from app.core.config import settings

logger = logging.getLogger(__name__)

WHOP_API_BASE = "https://api.whop.com/api/v1"
WEBHOOK_TOLERANCE_SECONDS = 300
DECISION_ENGINE_PRODUCT_ID = "prod_NuPQUAGoibkpW"
DECISION_ENGINE_CHECKOUT_URL = "https://whop.com/checkout/plan_MwJ2qcFxmvqDY"
DEFAULT_APP_DOWNLOAD_URL = (
    "https://github.com/8j7y2rhzs7-sketch/YWP_os/releases/download/"
    "android-v3.3.6/YWP-OS-3.3.6.apk"
)


class WhopWebhookError(Exception):
    pass


def product_id() -> str:
    return settings.whop_product_id or DECISION_ENGINE_PRODUCT_ID


def checkout_url() -> str:
    return settings.checkout_url or DECISION_ENGINE_CHECKOUT_URL


def app_download_url() -> str:
    return settings.app_download_url or DEFAULT_APP_DOWNLOAD_URL


def whop_enabled() -> bool:
    if not settings.whop_subscription_required:
        return False
    return bool(product_id())


def whop_client() -> Whop:
    if not settings.whop_api_key:
        raise RuntimeError("WHOP_API_KEY is not set")
    return Whop(token=settings.whop_api_key, api_version_date=settings.whop_api_version_date)


def verify_whop_user_token(headers: Any) -> str | None:
    """Return the Whop user id from `x-whop-user-token`, or None.

    Official helper: `whop_sdk.lib.verify_user_token.try_verify_user_token`.
    `app_id` is required and is checked against the token audience.
    """
    if not settings.whop_app_id:
        return None
    payload = try_verify_user_token(headers, app_id=settings.whop_app_id)
    if payload is None:
        return None
    return payload.user_id


def check_user_access(whop_user_id: str, resource_id: str | None = None) -> dict[str, Any]:
    """Official: users.check_access → GET /users/{id}/access/{resource_id}."""
    resource = resource_id or product_id()
    if not settings.whop_api_key:
        return {"has_access": False, "access_level": "unknown"}
    result = whop_client().users.check_access(id=whop_user_id, resource_id=resource)
    return {"has_access": bool(result.has_access), "access_level": result.access_level}


def find_whop_user_id_by_email(email: str) -> str | None:
    """Resolve a Whop user id from exact membership email (member:email:read)."""
    cleaned = (email or "").strip().lower()
    if not cleaned or not settings.whop_api_key:
        return None
    try:
        pager = whop_client().members.list(
            account_id=settings.whop_company_id,
            query=cleaned,
            first=5,
        )
        for member in pager:
            user = getattr(member, "user", None)
            member_email = (
                (getattr(user, "email", None) if user is not None else None)
                or getattr(member, "email", None)
                or ""
            ).lower()
            user_id = (
                (getattr(user, "id", None) if user is not None else None)
                or getattr(member, "user_id", None)
            )
            if user_id and (not member_email or member_email == cleaned):
                return str(user_id)
    except Exception:
        logger.exception("Whop member email lookup failed for %s", cleaned)
    return None


def verify_webhook(payload: bytes, headers: dict[str, str], secret: str) -> dict[str, Any]:
    """Verify Standard Webhooks signature and return parsed event."""
    msg_id = headers.get("webhook-id") or headers.get("Webhook-Id")
    timestamp = headers.get("webhook-timestamp") or headers.get("Webhook-Timestamp")
    signature = headers.get("webhook-signature") or headers.get("Webhook-Signature")

    if not msg_id or not timestamp or not signature:
        raise WhopWebhookError("Missing webhook signature headers")

    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise WhopWebhookError("Invalid webhook timestamp") from exc

    if abs(time.time() - ts) > WEBHOOK_TOLERANCE_SECONDS:
        raise WhopWebhookError("Webhook timestamp too old")

    signed_content = f"{msg_id}.{timestamp}.{payload.decode('utf-8')}"
    key_bytes = secret.encode("utf-8")
    expected = base64.b64encode(
        hmac.new(key_bytes, signed_content.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")

    received = signature.split(",")[-1].strip() if "," in signature else signature.strip()
    if not hmac.compare_digest(received, expected):
        raise WhopWebhookError("Invalid webhook signature")

    return json.loads(payload)


def extract_membership_fields(data: dict[str, Any]) -> dict[str, str | None]:
    """Pull user id, email, membership id from webhook payload."""
    user = data.get("user") or {}
    member = data.get("member") or {}
    if isinstance(user, dict):
        whop_user_id = user.get("id") or member.get("user_id")
        email = user.get("email") or member.get("email")
    else:
        whop_user_id = data.get("user_id")
        email = data.get("email")

    return {
        "whop_user_id": whop_user_id,
        "email": (email or "").lower() or None,
        "membership_id": data.get("id"),
        "product_id": data.get("product_id") or data.get("product", {}).get("id")
        if isinstance(data.get("product"), dict)
        else data.get("product_id"),
        "status": data.get("status") or "active",
    }


def membership_grants_access(status: str | None) -> bool:
    return status in {"active", "trialing", "completed"}
