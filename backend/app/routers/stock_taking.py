from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.user import User
from app.schemas.stock_count import (
    CountDriftOut,
    SetCountsIn,
    StockCountCreateIn,
    StockCountSessionOut,
    StockCountSummaryOut,
)
from app.services import stock_taking as service
from app.services.printing import render_count_tags

router = APIRouter(prefix="/api/stock-counts", tags=["stock-counts"])


@router.get("", response_model=list[StockCountSummaryOut])
def list_stock_counts(
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    return service.list_sessions(db)


@router.post("", response_model=StockCountSessionOut, status_code=201)
def create_stock_count(
    data: StockCountCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "create")),
):
    session = service.create_session(
        db, data.warehouse_id, data.count_date, user, data.notes, data.item_ids
    )
    return service.serialize_session(session)


@router.get("/{session_id}", response_model=StockCountSessionOut)
def get_stock_count(
    session_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    return service.get_session_detail(db, session_id)


@router.put("/{session_id}/counts", response_model=StockCountSessionOut)
def set_stock_count_counts(
    session_id: UUID,
    data: SetCountsIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    """شمارشِ فیزیکی را ثبت می‌کند — و همان لحظه عکسِ سیستمیِ آن ردیف‌ها را تازه
    می‌کند، تا اختلاف با چیزی سنجیده شود که سیستم *در لحظه‌ی شمارش* باور داشت."""
    session = service.set_counts(db, session_id, data.lines, user)
    return service.serialize_session(session)


@router.post("/{session_id}/post", response_model=StockCountSessionOut)
def post_stock_count(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    session = service.post_session(db, session_id, user)
    return service.serialize_session(session)


@router.post("/{session_id}/cancel", response_model=StockCountSessionOut)
def cancel_stock_count(
    session_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    session = service.cancel_session(db, session_id)
    return service.serialize_session(session)


@router.get("/{session_id}/drift", response_model=list[CountDriftOut])
def stock_count_drift(
    session_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    """کالاهایی که **پس از** ثبتِ شمارششان حرکت کرده‌اند.

    گزارش است، نه گارد: اختلافشان درست حساب می‌شود، ولی کاربر پیش از ثبت باید
    بداند بینِ شمارش و حالا انبار بی‌کار ننشسته.
    """
    session = service._get_session(db, session_id)
    return service.moved_since_count(db, session)


@router.get("/{session_id}/tags", response_class=HTMLResponse)
def print_count_tags(
    session_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("inventory", "view")),
):
    """برگه‌های شمارش — **بدونِ موجودیِ سیستمی**.

    شمارنده نباید عددِ سیستم را ببیند، وگرنه شمارش دیگر شاهدِ مستقلی نیست. چاپِ
    دوباره هویتِ تازه نمی‌سازد: شماره‌ی تگ از ترتیبِ ثابتِ ردیف‌ها مشتق می‌شود.
    """
    session = service._get_session(db, session_id)
    html = render_count_tags(
        business_name=principal.membership.tenant.name,
        **service.count_tag_projection(db, session),
    )
    return HTMLResponse(content=html, headers={"Content-Disposition": "inline"})
