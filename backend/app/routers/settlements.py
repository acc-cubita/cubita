"""تسویه‌ی حسابِ طرف مقابل — روترِ مستقل.

جدا از `routers/treasury.py` می‌ماند و عمداً: آن‌جا *جابه‌جاییِ پول* ثبت می‌شود،
این‌جا *رابطه*. یکی‌کردنشان همان اشتباهی است که §۲ درباره‌اش هشدار می‌دهد.
"""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.settlement import Settlement
from app.models.user import User
from app.schemas.settlement import (
    AllocationHistoryOut,
    CounterpartyAccountOut,
    OpenItemSummaryOut,
    SettlementDetailOut,
    SettlementIn,
    SettlementOut,
    SettlementVoidIn,
)
from app.services import open_items as oi
from app.services import settlements as svc
from app.services.idempotency import idempotent

router = APIRouter(tags=["settlements"])


@router.get("/api/settlements/accounts", response_model=list[CounterpartyAccountOut])
def counterparty_accounts(
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    """معین‌هایی که تسویه رویشان ممکن است (§۵).

    **پیش از `/{settlement_id}` می‌آید**، وگرنه FastAPI «accounts» را شناسه
    می‌گیرد و ۴۲۲ می‌دهد.
    """
    return [{"id": a.id, "code": a.code, "name": a.name} for a in oi.counterparty_accounts(db)]


@router.get("/api/settlements/open-items", response_model=OpenItemSummaryOut)
def open_items(
    account_id: UUID = Query(...),
    contact_id: UUID | None = Query(None),
    as_of: date | None = Query(None),
    only_open: bool = Query(True),
    exclude_settlement_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    """اقلامِ باز — هم پنجره‌ی انتخابِ قلم (§۹) و هم صورتِ اقلامِ باز (§۴۵)."""
    return svc.open_items_summary(
        db,
        account_id=account_id,
        contact_id=contact_id,
        as_of=as_of,
        only_open=only_open,
        exclude_settlement_id=exclude_settlement_id,
    )


@router.get("/api/settlements/history", response_model=list[AllocationHistoryOut])
def allocation_history(
    source_type: str = Query(...),
    source_id: UUID = Query(...),
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    """از سند به تسویه‌هایش (§۳۵ §۳۶) — نیمه‌ی دومِ ردیابی."""
    return oi.allocation_history(db, source_type, source_id)


@router.get("/api/settlements", response_model=list[SettlementOut])
def list_settlements(
    contact_id: UUID | None = Query(None),
    account_id: UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    include_voided: bool = Query(True),
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    query = svc.settlements_query(db)
    if contact_id is not None:
        query = query.filter(Settlement.contact_id == contact_id)
    if account_id is not None:
        query = query.filter(Settlement.account_id == account_id)
    if date_from is not None:
        query = query.filter(Settlement.settlement_date >= date_from)
    if date_to is not None:
        query = query.filter(Settlement.settlement_date <= date_to)
    if not include_voided:
        query = query.filter(Settlement.voided_at.is_(None))
    return [svc.row(db, settlement) for settlement in query.all()]


@router.get("/api/settlements/{settlement_id}", response_model=SettlementDetailOut)
def get_settlement(
    settlement_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    settlement = svc.get(db, settlement_id)
    return {**svc.row(db, settlement), "allocations": svc.describe_allocations(db, settlement)}


@router.post("/api/settlements", response_model=SettlementDetailOut, status_code=201)
def create_settlement(
    data: SettlementIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    """ثبتِ تسویه (§۵۰).

    idempotent است و این‌جا اهمیتش از تسویه‌ی کارت‌خوان هم بیشتر: ارسالِ دوباره
    بدونِ محافظ، تخصیص‌ها را **دو برابر** می‌کرد و فاکتوری که ۱۰۰ بدهکار بود
    ناگهان ۲۰۰ تسویه‌شده نشان می‌داد. چون تسویه سندِ حسابداری نمی‌زند، هیچ ترازی
    هم به‌هم نمی‌خورد تا خطا را لو بدهد.
    """
    settlement = idempotent(
        db,
        request,
        user,
        operation="create_settlement",
        payload=data,
        run=lambda: svc.create_settlement(db, data, user),
        replay=lambda rid: svc.get(db, rid),
    )
    result = {**svc.row(db, settlement), "allocations": svc.describe_allocations(db, settlement)}
    db.commit()
    return result


@router.post("/api/settlements/{settlement_id}/void", response_model=SettlementOut)
def void_settlement(
    settlement_id: UUID,
    data: SettlementVoidIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "update")),
):
    """برگشتِ تسویه — رابطه آزاد می‌شود، اسنادِ منبع دست‌نخورده می‌مانند (§۳۸)."""
    settlement = svc.void_settlement(db, settlement_id, reason=data.reason, user=user)
    result = svc.row(db, settlement)
    db.commit()
    return result
