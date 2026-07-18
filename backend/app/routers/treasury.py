from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.treasury import TreasuryTransactionIn, TreasuryTransactionOut
from app.services import treasury as treasury_service

router = APIRouter(tags=["treasury"])


def _to_out(txn) -> TreasuryTransactionOut:
    return TreasuryTransactionOut(
        id=txn.id,
        type=txn.type,
        transaction_date=txn.transaction_date,
        contact_id=txn.contact_id,
        contact_name=txn.contact.name if txn.contact else "",
        amount=txn.amount,
        method=txn.method,
        bank_account_id=txn.bank_account_id,
        description=txn.description,
        journal_entry_id=txn.journal_entry_id,
    )


@router.get("/api/treasury", response_model=list[TreasuryTransactionOut])
def list_treasury(db: Session = Depends(get_db), _=Depends(require_permission("checks_bank", "view"))):
    return [_to_out(t) for t in treasury_service.list_transactions(db)]


@router.post("/api/treasury/receipts", response_model=TreasuryTransactionOut, status_code=201)
def create_receipt(
    data: TreasuryTransactionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    return _to_out(treasury_service.create_receipt(db, data, user))


@router.post("/api/treasury/payments", response_model=TreasuryTransactionOut, status_code=201)
def create_payment(
    data: TreasuryTransactionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    return _to_out(treasury_service.create_payment(db, data, user))
