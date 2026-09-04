"""Whop subscription: webhooks, checkout link, access sync."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.core.config import settings
from app.deps import CurrentUser, DB
from app.models import WhopWebhookDelivery
from app.schemas import MessageOut, SubscriptionOut, WhopCheckoutOut
from app.services.whop import (
    WhopWebhookError,
    app_download_url,
    checkout_url,
    extract_membership_fields,
    membership_grants_access,
    product_id,
    verify_webhook,
    verify_whop_user_token,
    check_user_access,
    whop_enabled,
)
from app.services.whop_access import (
    apply_subscription_from_webhook,
    ensure_fresh_subscription,
    get_or_create_whop_user,
    user_has_app_access,
)

router = APIRouter(prefix="/whop", tags=["whop"])


@router.get("/checkout", response_model=WhopCheckoutOut)
def get_checkout_url() -> WhopCheckoutOut:
    return WhopCheckoutOut(
        checkout_url=checkout_url(),
        product_id=product_id(),
        app_download_url=app_download_url(),
        message=(
            "Pay on Whop with the same email as your YWP OS account, download the "
            "Android APK from Whop (or the backup link), install it, then Sync my access."
        ),
    )


@router.get("/gate")
def access_gate(request: Request, db: DB) -> dict[str, object]:
    """Verify the iframe user token, then checkAccess on DECISION ENGINE."""
    url = checkout_url()
    whop_user_id = verify_whop_user_token(request.headers)
    if not whop_user_id:
        return {
            "has_access": False,
            "checkout_url": url,
            "product_id": product_id(),
            "required": whop_enabled(),
        }
    access = check_user_access(whop_user_id, product_id())
    if access.get("has_access"):
        user = get_or_create_whop_user(db, whop_user_id)
        apply_subscription_from_webhook(
            db,
            email=user.email if not user.email.endswith("@members.whop.invalid") else None,
            whop_user_id=whop_user_id,
            membership_id=user.whop_membership_id,
            active=True,
        )
        db.commit()
    return {
        "has_access": bool(access.get("has_access")),
        "access_level": access.get("access_level"),
        "checkout_url": url,
        "product_id": product_id(),
        "required": True,
    }


@router.get("/subscription", response_model=SubscriptionOut)
def subscription_status(user: CurrentUser, db: DB) -> SubscriptionOut:
    user = ensure_fresh_subscription(db, user, force=False)
    db.commit()
    db.refresh(user)
    return SubscriptionOut(
        required=whop_enabled(),
        has_access=user_has_app_access(user),
        status=user.subscription_status,
        whop_user_id=user.whop_user_id,
        checkout_url=checkout_url(),
        app_download_url=app_download_url(),
    )


@router.post("/sync", response_model=SubscriptionOut)
def sync_subscription(user: CurrentUser, db: DB) -> SubscriptionOut:
    user = ensure_fresh_subscription(db, user, force=True)
    db.commit()
    db.refresh(user)
    return SubscriptionOut(
        required=whop_enabled(),
        has_access=user_has_app_access(user),
        status=user.subscription_status,
        whop_user_id=user.whop_user_id,
        checkout_url=checkout_url(),
        app_download_url=app_download_url(),
    )


@router.post("/webhook", response_model=MessageOut, include_in_schema=False)
async def whop_webhook(request: Request, db: DB) -> MessageOut:
    if not settings.whop_webhook_secret:
        raise HTTPException(status_code=503, detail="Whop webhooks not configured")

    payload = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    try:
        event = verify_webhook(payload, headers, settings.whop_webhook_secret)
    except WhopWebhookError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    webhook_id = event.get("id") or headers.get("webhook-id")
    if webhook_id:
        seen = db.scalar(
            select(WhopWebhookDelivery).where(WhopWebhookDelivery.webhook_id == webhook_id)
        )
        if seen:
            return MessageOut(message="Already processed")

    event_type = event.get("type", "")
    data = event.get("data") or {}
    fields = extract_membership_fields(data)
    status = (fields.get("status") or "").lower()

    active: bool | None = None
    if event_type in {"membership.activated", "payment.succeeded"}:
        active = True
    elif event_type in {"membership.deactivated", "membership.expired"}:
        active = False
    elif event_type == "membership.cancel_at_period_end_changed":
        active = status == "active"
    elif event_type.startswith("membership."):
        if membership_grants_access(status):
            active = True
        elif status in {"expired", "canceled", "cancelled", "inactive"}:
            active = False

    if active is not None:
        apply_subscription_from_webhook(
            db,
            email=fields["email"],
            whop_user_id=fields["whop_user_id"],
            membership_id=fields["membership_id"],
            active=active,
        )

    if webhook_id:
        db.add(WhopWebhookDelivery(webhook_id=webhook_id, event_type=event_type))

    db.commit()
    return MessageOut(message="OK")
