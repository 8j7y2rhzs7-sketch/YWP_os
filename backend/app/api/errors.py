from __future__ import annotations

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app.deps import DB, AdminUser, OptionalUser
from app.models import AuditLog, ErrorReport
from app.schemas import ErrorReportCreate, ErrorReportOut, MessageOut

router = APIRouter(prefix="/errors", tags=["errors"])


@router.post("", response_model=MessageOut, status_code=201)
def submit_error_report(
    payload: ErrorReportCreate,
    request: Request,
    db: DB,
    user: OptionalUser,
) -> MessageOut:
    """Accept crash / user bug reports so post-use issues can be fixed."""
    report = ErrorReport(
        user_id=user.id if user else None,
        category=payload.category,
        message=payload.message.strip(),
        screen=payload.screen,
        stack=payload.stack,
        app_version=payload.app_version,
        platform=payload.platform,
        analysis_id=payload.analysis_id,
        recommendation_id=payload.recommendation_id,
        ticket_id=payload.ticket_id,
        context={
            **(payload.context or {}),
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        },
        status="open",
    )
    db.add(report)
    db.flush()
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action="error_report_submitted",
            entity_type="error_report",
            entity_id=report.id,
            details={
                "category": payload.category,
                "screen": payload.screen,
                "app_version": payload.app_version,
                "platform": payload.platform,
            },
        )
    )
    db.commit()
    return MessageOut(message=f"Error report {report.id} received. Thank you.")


@router.get("", response_model=list[ErrorReportOut])
def list_error_reports(
    admin: AdminUser,
    db: DB,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ErrorReportOut]:
    del admin
    stmt = select(ErrorReport).order_by(ErrorReport.created_at.desc()).limit(limit)
    if status_filter:
        stmt = stmt.where(ErrorReport.status == status_filter)
    rows = list(db.scalars(stmt).all())
    return [ErrorReportOut.model_validate(row) for row in rows]
