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
    extract_membership_fields,
    membership_grants_access,
    verify_webhook,
    whop_enabled,
)
from app.services.whop_access import (
    apply_pending_access,
    apply_subscription_from_webhook,
    sync_user_subscription,
    user_has_app_access,
)

router = APIRouter(prefix="/whop", tags=["whop"])


@router.get("/checkout", response_model=WhopCheckoutOut)
def checkout_url() -> WhopCheckoutOut:
    if not settings.whop_checkout_url:
        raise HTTPException(
            status_code=503,
            detail="Whop checkout URL is not configured. Set WHOP_CHECKOUT_URL.",
        )
    return WhopCheckoutOut(
        checkout_url=settings.whop_checkout_url,
        product_id=settings.whop_product_id,
        message="Complete payment on Whop, then return here and sign in with the same email.",
    )


@router.get("/subscription", response_model=SubscriptionOut)
def subscription_status(user: CurrentUser, db: DB) -> SubscriptionOut:
    user = sync_user_subscription(db, user)
    db.commit()
    db.refresh(user)
    return SubscriptionOut(
        required=whop_enabled(),
        has_access=user_has_app_access(user),
        status=user.subscription_status,
        whop_user_id=user.whop_user_id,
        checkout_url=settings.whop_checkout_url,
    )


@router.post("/sync", response_model=SubscriptionOut)
def sync_subscription(user: CurrentUser, db: DB) -> SubscriptionOut:
    user = apply_pending_access(db, user)
    user = sync_user_subscription(db, user)
    db.commit()
    db.refresh(user)
    return SubscriptionOut(
        required=whop_enabled(),
        has_access=user_has_app_access(user),
        status=user.subscription_status,
        whop_user_id=user.whop_user_id,
        checkout_url=settings.whop_checkout_url,
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

    if event_type == "membership.activated":
        apply_subscription_from_webhook(
            db,
            email=fields["email"],
            whop_user_id=fields["whop_user_id"],
            membership_id=fields["membership_id"],
            active=membership_grants_access(fields["status"]),
        )
    elif event_type in {"membership.deactivated", "membership.cancel_at_period_end_changed"}:
        active = event_type != "membership.deactivated" and fields.get("status") == "active"
        if event_type == "membership.deactivated":
            active = False
        apply_subscription_from_webhook(
            db,
            email=fields["email"],
            whop_user_id=fields["whop_user_id"],
            membership_id=fields["membership_id"],
            active=active,
        )
    elif event_type == "payment.succeeded":
        apply_subscription_from_webhook(
            db,
            email=fields["email"],
            whop_user_id=fields["whop_user_id"],
            membership_id=fields["membership_id"],
            active=True,
        )

    if webhook_id:
        db.add(WhopWebhookDelivery(webhook_id=webhook_id, event_type=event_type))

    db.commit()
    return MessageOut(message="OK")
