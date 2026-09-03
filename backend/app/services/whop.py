"""Whop subscription verification, webhooks, and access checks."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

WHOP_API_BASE = "https://api.whop.com/api/v1"
WEBHOOK_TOLERANCE_SECONDS = 300


class WhopWebhookError(Exception):
    pass


def whop_enabled() -> bool:
    if not settings.whop_subscription_required:
        return False
    return bool(settings.whop_api_key and settings.whop_product_id)


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


def check_user_access(whop_user_id: str, resource_id: str | None = None) -> dict[str, Any]:
    """Call Whop API: GET /users/{id}/access/{resource_id}."""
    if not settings.whop_api_key:
        return {"has_access": True, "access_level": "customer"}
    resource = resource_id or settings.whop_product_id
    if not resource:
        return {"has_access": False, "access_level": "no_access"}

    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            f"{WHOP_API_BASE}/users/{whop_user_id}/access/{resource}",
            headers={"Authorization": f"Bearer {settings.whop_api_key}"},
        )
        resp.raise_for_status()
        return resp.json()


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
