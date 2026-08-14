from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.period_close import FiscalPeriodClose
from app.models.user import User
from app.schemas.period_close import FiscalPeriodCloseIn, FiscalPeriodCloseOut
from app.services.period_close import close_period

router = APIRouter(tags=["period_close"])


@router.get("/api/fiscal-period-closes", response_model=list[FiscalPeriodCloseOut])
def list_period_closes(db: Session = Depends(get_db), _=Depends(require_permission("accounting", "view"))):
    return db.query(FiscalPeriodClose).order_by(FiscalPeriodClose.closing_date.desc()).all()


@router.post("/api/fiscal-period-closes", response_model=FiscalPeriodCloseOut, status_code=201)
def create_period_close(
    data: FiscalPeriodCloseIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "approve")),
):
    return close_period(db, data, user)
