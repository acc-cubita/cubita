from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.inventory_valuation import InventoryValuationRun
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.inventory_valuation import (
    ValuationPreviewOut,
    ValuationRunDetailOut,
    ValuationRunIn,
    ValuationRunOut,
)
from app.schemas.voiding import VoidIn
from app.services import valuation_runs
from app.services.idempotency import idempotent

router = APIRouter(tags=["inventory-valuation"])

#: **هر چه این مسیر نشان می‌دهد بهاست** — بهای قبل و بعد، اثرِ ریالی، سندِ اصلاحی. پس دیدنش
#: همان مجوزِ بهای گزارش‌های انبار را می‌خواهد (`routers/reports.MONEY_MODULE`: حسابداری/دیدن)،
#: نه مجوزِ انبار؛ وگرنه انبارداری که کاردکسش بی‌مبلغ است، بها را از این‌جا می‌دید.
#: ثبت و ابطالِ سندِ اصلاحی فقط حسابداری.
_view = require_permission("accounting", "view")


@router.get("/api/inventory-valuation/preview", response_model=ValuationPreviewOut)
def preview_valuation(
    date_to: date = Query(...),
    date_from: date | None = Query(None),
    warehouse_id: UUID | None = Query(None),
    item_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(_view),
):
    """محاسبه بدونِ نوشتن — حرکاتِ منقضی، سندِ اصلاحی، موجودیِ منفی و توکنِ دفتر."""
    return valuation_runs.calculate(
        db, date_from=date_from, date_to=date_to, warehouse_id=warehouse_id, item_id=item_id
    )


@router.post("/api/inventory-valuation/runs", response_model=ValuationRunOut, status_code=201)
def create_valuation_run(
    data: ValuationRunIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    """**idempotent.** تکرارِ شبکه‌ای نباید دو سندِ اصلاحی بزند."""
    run = idempotent(
        db, request, user, operation="create_inventory_valuation_run", payload=data,
        run=lambda: valuation_runs.commit_run(db, data, user),
        replay=lambda rid: db.get(InventoryValuationRun, rid),
    )
    return valuation_runs.run_outs(db, [run])[0]


@router.get("/api/inventory-valuation/runs", response_model=Page[ValuationRunOut])
def list_valuation_runs(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(_view),
):
    items, next_cursor = paginate(
        db.query(InventoryValuationRun),
        [InventoryValuationRun.date_to, InventoryValuationRun.number],
        params,
    )
    return Page(items=valuation_runs.run_outs(db, items), next_cursor=next_cursor)


@router.get("/api/inventory-valuation/runs/{run_id}", response_model=ValuationRunDetailOut)
def get_valuation_run(run_id: UUID, db: Session = Depends(get_db), _=Depends(_view)):
    return valuation_runs.run_detail(db, run_id)


@router.post("/api/inventory-valuation/runs/{run_id}/void", response_model=ValuationRunOut)
def void_valuation_run(
    run_id: UUID,
    data: VoidIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "delete")),
):
    run = valuation_runs.void_run(db, run_id, reason=data.reason, user=user, void_date=data.void_date)
    return valuation_runs.run_outs(db, [run])[0]
