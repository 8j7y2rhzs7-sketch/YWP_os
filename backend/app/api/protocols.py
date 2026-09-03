from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.deps import DB, SubscribedUser
from app.models import ProtocolRun
from app.schemas import ProtocolRunOut
from app.services.protocols import CURRENT_PROTOCOL
from app.services.trusted_sources import trusted_sources_manifest

router = APIRouter(prefix="/protocol", tags=["protocol"])


@router.get("/current")
def current_protocol(_: SubscribedUser) -> dict:
    return CURRENT_PROTOCOL


@router.get("/trusted-sources")
def trusted_sources(_: SubscribedUser) -> dict:
    """Certified sources the research searchers are allowed to pull from."""
    return trusted_sources_manifest()


@router.get("/runs/{analysis_id}", response_model=ProtocolRunOut)
def protocol_run(analysis_id: str, user: SubscribedUser, db: DB) -> ProtocolRunOut:
    record = db.scalar(
        select(ProtocolRun)
        .where(ProtocolRun.analysis_id == analysis_id, ProtocolRun.user_id == user.id)
        .order_by(ProtocolRun.created_at.desc())
    )
    if not record:
        raise HTTPException(status_code=404, detail="Protocol run not found")
    return ProtocolRunOut.model_validate(record)
