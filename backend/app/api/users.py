from fastapi import APIRouter

from app.deps import DB, CurrentUser
from app.models import AuditLog
from app.schemas import UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
def update_me(payload: UserUpdate, user: CurrentUser, db: DB) -> UserOut:
    changes = payload.model_dump(exclude_none=True)
    for key, value in changes.items():
        setattr(user, key, value.value if hasattr(value, "value") else value)
    db.add(
        AuditLog(
            user_id=user.id,
            action="USER_PROFILE_UPDATED",
            entity_type="user",
            entity_id=user.id,
            details={"fields": sorted(changes)},
        )
    )
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
