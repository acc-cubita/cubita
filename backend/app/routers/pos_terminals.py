from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.schemas.pos_terminal import PosTerminalIn, PosTerminalOut, PosTerminalUpdateIn
from app.services import card_terminals as svc

router = APIRouter(tags=["pos-terminals"])


@router.get("/api/pos-terminals", response_model=list[PosTerminalOut])
def list_terminals(
    db: Session = Depends(get_db),
    search: str | None = Query(None, description="شماره پایانه یا نامِ دستگاه"),
    bank_account_id: UUID | None = Query(None),
    currency_code: str | None = Query(None),
    active_only: bool = Query(False),
    # نمای فهرست را فروشنده/صندوق‌دار هم لازم دارد تا دکمه‌ی پرداخت بداند به کدام
    # ترمینال/حسابِ بانکی وصل شود؛ پس با مجوزِ فروش (نه صرفاً checks_bank) گیت می‌شود.
    _=Depends(require_permission("invoices", "view")),
):
    """فهرست با موجودیِ تسویه‌نشده، جست‌وجو و صافی (§۲۲ §۲۳)."""
    return svc.list_terminals(
        db,
        search=search,
        bank_account_id=bank_account_id,
        currency_code=currency_code,
        active_only=active_only,
    )


@router.post("/api/pos-terminals", response_model=PosTerminalOut, status_code=201)
def create_terminal(
    data: PosTerminalIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "update")),
):
    return svc.row(db, svc.create_terminal(db, data.model_dump()))


@router.patch("/api/pos-terminals/{terminal_id}", response_model=PosTerminalOut)
def update_terminal(
    terminal_id: UUID,
    data: PosTerminalUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "update")),
):
    """ویرایشِ جزئی.

    عمداً `PosTerminalUpdateIn` است نه `PosTerminalIn`: با شِمای کامل، هر فیلدی که
    کلاینت نمی‌فرستاد **پیش‌فرضش نوشته می‌شد** — و چون پیش‌فرضِ `is_active` مقدارِ
    `True` است، ویرایشِ هر دستگاهی دستگاهِ غیرفعال را بی‌صدا فعال می‌کرد.
    """
    return svc.row(db, svc.update_terminal(db, terminal_id, data.model_dump(exclude_unset=True)))


@router.delete("/api/pos-terminals/{terminal_id}", status_code=204)
def delete_terminal(
    terminal_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "update")),
):
    """دستگاهِ بی‌سابقه حذف می‌شود؛ دستگاهِ استفاده‌شده غیرفعال (§۲۱)."""
    svc.delete_terminal(db, terminal_id)
