"""تسویه‌ی کارت‌خوان — روترِ مستقل.

پیش از این دو اندپوینتِ تسویه داخلِ `routers/banking.py` بودند، کنارِ چک و
صورت‌حسابِ بانک. حالا که تسویه خودش سند و فهرست و ابطال دارد، روترِ خودش را
می‌گیرد — قرینه‌ی `routers/pos_terminals.py`.
"""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.pos_settlement import PosSettlement
from app.models.user import User
from app.schemas.pos_settlement import (
    PosPendingGroupOut,
    PosSettlementDetailOut,
    PosSettlementIn,
    PosSettlementOut,
    PosSettlementPreviewOut,
    PosSettlementVoidIn,
)
from app.services import pos_settlements as svc
from app.services.idempotency import idempotent

router = APIRouter(tags=["pos-settlements"])


@router.get("/api/pos-settlements", response_model=list[PosSettlementOut])
def list_settlements(
    pos_terminal_id: UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    include_voided: bool = Query(True),
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    """فهرستِ تسویه‌ها (§۲۸)."""
    return svc.list_settlements(
        db,
        pos_terminal_id=pos_terminal_id,
        date_from=date_from,
        date_to=date_to,
        include_voided=include_voided,
    )


@router.get("/api/pos-settlements/pending", response_model=list[PosPendingGroupOut])
def pending(
    terminal_no: str | None = Query(None),
    pos_terminal_id: UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    """نمای کلیِ «کدام دستگاه چقدر پولِ نرسیده دارد» — گروه‌بندی‌شده بر روز."""
    return svc.pending_groups(
        db,
        terminal_no=terminal_no,
        pos_terminal_id=pos_terminal_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/api/pos-settlements/preview", response_model=PosSettlementPreviewOut)
def preview(
    pos_terminal_id: UUID = Query(...),
    settle_through: date = Query(...),
    date_from: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    """رسیدهایی که با این برش تسویه می‌شوند — پیش از ثبت (§۱۲).

    **مسیرش باید پیش از `/{settlement_id}` بیاید**، وگرنه FastAPI رشته‌ی
    «preview» را شناسه می‌گیرد و ۴۲۲ می‌دهد.
    """
    return svc.preview(
        db,
        pos_terminal_id=pos_terminal_id,
        settle_through=settle_through,
        date_from=date_from,
    )


@router.get("/api/pos-settlements/{settlement_id}", response_model=PosSettlementDetailOut)
def get_settlement(
    settlement_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    settlement = svc.get(db, settlement_id)
    return {**svc.row(db, settlement), "receipts": svc.related_receipts(db, settlement)}


@router.post("/api/pos-settlements", response_model=PosSettlementOut, status_code=201)
def create_settlement(
    data: PosSettlementIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    """ثبتِ یک واریزِ شرکتِ پرداخت.

    idempotent است: اگر پاسخ در راه گم شود و کلاینت دوباره بفرستد، **نباید** دو
    تسویه و دو سند و دو ردیفِ بانکی ساخته شود. بدونِ این، ارسالِ دوباره تسویه‌ی
    دوم نمی‌ساخت — چون رسیدها دیگر تسویه‌نشده نبودند — ولی پاسخش خطای گمراه‌کننده‌ی
    «رسیدِ تسویه‌نشده‌ای نیست» بود، و کارمزد در حالتِ رقابتی می‌توانست دوبار بخورد.
    """
    settlement = idempotent(
        db,
        request,
        user,
        operation="create_pos_settlement",
        payload=data,
        run=lambda: svc.create(
            db,
            user,
            pos_terminal_id=data.pos_terminal_id,
            settlement_date=data.settlement_date,
            settle_through=data.settle_through,
            date_from=data.date_from,
            fee_amount=data.fee_amount,
            note=data.note,
        ),
        replay=lambda rid: db.get(PosSettlement, rid),
    )
    result = svc.row(db, settlement)
    db.commit()
    return result


@router.post("/api/pos-settlements/{settlement_id}/void", response_model=PosSettlementOut)
def void_settlement(
    settlement_id: UUID,
    data: PosSettlementVoidIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "delete")),
):
    """ابطال با سندِ معکوس (§۳۳) — رسیدها دوباره تسویه‌نشده می‌شوند."""
    settlement = svc.void(db, settlement_id, user, data.reason)
    result = svc.row(db, settlement)
    db.commit()
    return result
