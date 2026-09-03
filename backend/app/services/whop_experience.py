"""Create/install a Whop experience on the existing company and attach it to DECISION ENGINE.

Official endpoints (whop-sdk):
  GET  /experiences?account_id=&app_id=
  POST /experiences          {account_id, app_id, name}   — is_public omitted
  POST /experiences/{id}/attach  {product_id}

Does not create a product or plan.
"""
from __future__ import annotations

from app.core.config import settings
from app.services.whop import product_id, whop_client


def link_decision_engine_experience() -> dict[str, str]:
    if not settings.whop_api_key:
        raise RuntimeError(
            "WHOP_API_KEY is missing. Generate it in Whop Dashboard → Developer."
        )
    if not settings.whop_app_id:
        raise RuntimeError(
            "NEXT_PUBLIC_WHOP_APP_ID / WHOP_APP_ID is missing. "
            "Generate it in Whop Dashboard → Developer."
        )
    company_id = settings.whop_company_id
    if not company_id:
        raise RuntimeError("WHOP_COMPANY_ID is missing.")

    client = whop_client()
    prod = product_id()

    existing_id = None
    for item in client.experiences.list(
        account_id=company_id,
        app_id=settings.whop_app_id,
        first=20,
    ):
        existing_id = item.id
        break

    if existing_id:
        attached = client.experiences.attach(existing_id, product_id=prod)
        return {
            "status": "attached_existing",
            "experience_id": attached.id,
            "product_id": prod,
            "company_id": company_id,
        }

    created = client.experiences.create(
        account_id=company_id,
        app_id=settings.whop_app_id,
        name="DECISION ENGINE",
    )
    attached = client.experiences.attach(created.id, product_id=prod)
    return {
        "status": "created_and_attached",
        "experience_id": attached.id,
        "product_id": prod,
        "company_id": company_id,
    }
