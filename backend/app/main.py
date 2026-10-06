from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal
from app.middleware.process_evidence import ProcessEvidenceMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.services.whop import (
    check_user_access,
    checkout_url,
    product_id,
    verify_whop_user_token,
)
from app.services.whop_access import get_or_create_whop_user

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Move the published demo row to the owner, then lock any leftover demo login."""
    if not settings.demo_mode:
        db = SessionLocal()
        try:
            from app.services.demo_account import prepare_production_identities

            prepare_production_identities(db)
        except Exception:
            db.rollback()
            logger.exception("Could not prepare the owner account on startup")
        finally:
            db.close()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "YWP OS v3.0 decision support, ticket construction, Lock Check, "
        "Miss-by-1 review, and guarded adaptive-learning API."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "x-whop-user-token",
        "X-YWP-Provision-Secret",
        "X-YWP-Marketing-Token",
        "X-YWP-Markets-Token",
    ],
)


app.add_middleware(RateLimitMiddleware)
app.add_middleware(ProcessEvidenceMiddleware)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/experiences/"):
        response.headers["Content-Security-Policy"] = (
            "frame-ancestors https://whop.com https://*.whop.com"
        )
    else:
        response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = (
        "no-store" if request.url.path.startswith(settings.api_prefix) else "no-cache"
    )
    return response


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    """Process is listening. Does not touch the database.

    Render uses this so a sleeping database cannot keep the site from opening.
    """
    return {"status": "ok", "version": settings.app_version}


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "protocol": settings.protocol_version,
        "docs": "/docs",
    }


@app.get("/experiences/{experience_id}", include_in_schema=False)
def experience_view(experience_id: str, request: Request) -> RedirectResponse:
    """Whop experience path: /experiences/[experienceId].

    Verify the iframe user token, then users.check_access on prod_NuPQUAGoibkpW.
    No access → existing Daily Access checkout. Never creates a product or plan.
    """
    del experience_id
    pay_url = checkout_url()
    whop_user_id = verify_whop_user_token(request.headers)
    if not whop_user_id:
        return RedirectResponse(pay_url, status_code=302)
    access = check_user_access(whop_user_id, product_id())
    if not access.get("has_access"):
        return RedirectResponse(pay_url, status_code=302)
    db = SessionLocal()
    try:
        user = get_or_create_whop_user(db, whop_user_id)
        user.subscription_status = "active"
        db.commit()
    finally:
        db.close()
    return RedirectResponse("/docs", status_code=302)


app.include_router(api_router, prefix=settings.api_prefix)
