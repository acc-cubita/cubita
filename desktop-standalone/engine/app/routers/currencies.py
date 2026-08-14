from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.currency import (
    CurrencyIn,
    CurrencyOut,
    ExchangeRateIn,
    ExchangeRateOut,
    LatestRateOut,
)
from app.services import currencies as service

router = APIRouter(prefix="/api/currencies", tags=["currencies"])


@router.get("", response_model=list[CurrencyOut])
def list_currencies(
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    return service.list_currencies(db)


@router.post("", response_model=CurrencyOut, status_code=201)
def create_currency(
    data: CurrencyIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    return service.create_currency(db, data, user)


@router.delete("/{currency_id}", status_code=204)
def delete_currency(
    currency_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "delete")),
):
    service.delete_currency(db, currency_id)


@router.get("/rates", response_model=list[ExchangeRateOut])
def list_rates(
    currency_code: str | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    return service.list_rates(db, currency_code)


@router.post("/rates", response_model=ExchangeRateOut, status_code=201)
def upsert_rate(
    data: ExchangeRateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    return service.upsert_rate(db, data, user)


@router.get("/rates/latest", response_model=LatestRateOut)
def latest_rate(
    currency_code: str = Query(...),
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    return service.get_latest(db, currency_code)
