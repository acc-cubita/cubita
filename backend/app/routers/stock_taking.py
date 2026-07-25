from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.stock_count import (
    SetCountsIn,
    StockCountCreateIn,
    StockCountSessionOut,
    StockCountSummaryOut,
)
from app.services import stock_taking as service

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
    session = service.create_session(db, data.warehouse_id, data.count_date, user, data.notes)
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
    _=Depends(require_permission("inventory", "update")),
):
    session = service.set_counts(db, session_id, data.lines)
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
