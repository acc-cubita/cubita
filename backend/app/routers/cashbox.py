from uuid import UUID

from fastapi import APIRouter, Depends

from app.database import get_db
from app.deps import require_permission
from app.schemas.cashbox import CashboxIn, CashboxOut, CashboxUpdateIn
from app.services import cashboxes as svc
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/cashboxes", tags=["cashboxes"])


@router.get("", response_model=list[CashboxOut])
def list_cashboxes(
    include_inactive: bool = True,
    db: Session = Depends(get_db),
    _=Depends(require_permission("banking", "view")),
):
    """فهرستِ صندوق‌ها با موجودیِ اولیه و مانده — هر دو مشتق از دفتر.

    جمعِ کلِ صندوق‌ها عمداً برنمی‌گردد: ریالی و ارزی بدونِ نرخ و تاریخ جمع‌شدنی
    نیستند.
    """
    return svc.list_cashboxes(db, include_inactive=include_inactive)


@router.post("", response_model=CashboxOut, status_code=201)
def create_cashbox(
    data: CashboxIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("banking", "create")),
):
    box = svc.create_cashbox(db, data.model_dump())
    return _row(db, box)


@router.patch("/{cashbox_id}", response_model=CashboxOut)
def update_cashbox(
    cashbox_id: UUID,
    data: CashboxUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("banking", "update")),
):
    box = svc.update_cashbox(db, cashbox_id, data.model_dump(exclude_unset=True))
    return _row(db, box)


@router.delete("/{cashbox_id}", status_code=204)
def delete_cashbox(
    cashbox_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("banking", "delete")),
):
    """حذف فقط برای صندوقِ استفاده‌نشده؛ بقیه غیرفعال می‌شوند."""
    svc.delete_cashbox(db, cashbox_id)


def _row(db: Session, box) -> dict:
    """یک صندوق به شکلِ خروجی — از همان تابعی که فهرست را می‌سازد، تا دو شکل نشود."""
    return next(r for r in svc.list_cashboxes(db) if r["id"] == box.id)
