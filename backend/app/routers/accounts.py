from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.accounting import Account
from app.schemas.accounting import AccountOut

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
def list_accounts(
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return db.query(Account).order_by(Account.code).all()
