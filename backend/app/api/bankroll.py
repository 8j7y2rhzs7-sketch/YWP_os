from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import DB, CurrentUser
from app.models import AuditLog, BankrollAccount, BankrollTransaction
from app.schemas import (
    BankrollOut,
    BankrollTransactionCreate,
    BankrollTransactionOut,
    BankrollUpdate,
)

router = APIRouter(prefix="/bankroll", tags=["bankroll"])


def _account(db: DB, user_id: str) -> BankrollAccount:
    account = db.scalar(select(BankrollAccount).where(BankrollAccount.user_id == user_id))
    if not account:
        account = BankrollAccount(user_id=user_id)
        db.add(account)
        db.commit()
        db.refresh(account)
    return account


@router.get("", response_model=BankrollOut)
def get_bankroll(user: CurrentUser, db: DB) -> BankrollOut:
    return BankrollOut.model_validate(_account(db, user.id))


@router.patch("", response_model=BankrollOut)
def update_bankroll(payload: BankrollUpdate, user: CurrentUser, db: DB) -> BankrollOut:
    account = _account(db, user.id)
    changes = payload.model_dump(exclude_none=True)
    for key, value in changes.items():
        setattr(account, key, value)
    db.add(
        AuditLog(
            user_id=user.id,
            action="BANKROLL_RULES_UPDATED",
            entity_type="bankroll",
            entity_id=account.id,
            details={"fields": sorted(changes)},
        )
    )
    db.commit()
    db.refresh(account)
    return BankrollOut.model_validate(account)


@router.get("/transactions", response_model=list[BankrollTransactionOut])
def transactions(user: CurrentUser, db: DB, limit: int = 100) -> list[BankrollTransaction]:
    account = _account(db, user.id)
    return list(
        db.scalars(
            select(BankrollTransaction)
            .where(BankrollTransaction.bankroll_id == account.id)
            .order_by(BankrollTransaction.created_at.desc())
            .limit(min(max(limit, 1), 500))
        ).all()
    )


@router.post(
    "/transactions", response_model=BankrollTransactionOut, status_code=status.HTTP_201_CREATED
)
def add_transaction(
    payload: BankrollTransactionCreate, user: CurrentUser, db: DB
) -> BankrollTransactionOut:
    account = _account(db, user.id)
    amount = Decimal(payload.amount)
    signed = -amount if payload.transaction_type == "withdrawal" else amount
    new_balance = account.balance + signed
    if new_balance < 0:
        raise HTTPException(status_code=422, detail="Withdrawal exceeds bankroll balance")
    account.balance = new_balance
    transaction = BankrollTransaction(
        bankroll_id=account.id,
        transaction_type=payload.transaction_type,
        amount=signed,
        balance_after=new_balance,
        note=payload.note,
    )
    db.add(transaction)
    db.add(
        AuditLog(
            user_id=user.id,
            action="BANKROLL_TRANSACTION",
            entity_type="bankroll_transaction",
            entity_id=transaction.id,
            details={"type": payload.transaction_type, "amount": str(signed)},
        )
    )
    db.commit()
    db.refresh(transaction)
    return BankrollTransactionOut.model_validate(transaction)
