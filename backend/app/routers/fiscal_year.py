"""روترِ سالِ مالی — تعریف، فعال‌سازی، افتتاحیه و اختتامیه.

مجوزها عمداً همانِ «بستنِ دوره» است: دیدن با `accounting:view` و هر تغییرِ رسمی با
`accounting:approve`، چون بستن/افتتاحیه سندِ حسابداری می‌سازد.
"""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.fiscal_year import (
    FiscalYearIn,
    FiscalYearOut,
    FiscalYearSuggestion,
    FiscalYearUpdate,
)
from app.services import fiscal_year as svc

router = APIRouter(prefix="/api/fiscal-years", tags=["fiscal_year"])


def _out(db: Session, year) -> FiscalYearOut:
    data = FiscalYearOut.model_validate(year)
    data.entry_count = svc.entry_count(db, year)
    return data


@router.get("", response_model=list[FiscalYearOut])
def list_years(db: Session = Depends(get_db), _=Depends(require_permission("accounting", "view"))):
    return [_out(db, y) for y in svc.list_years(db)]


@router.get("/suggest", response_model=FiscalYearSuggestion)
def suggest(db: Session = Depends(get_db), _=Depends(require_permission("accounting", "view"))):
    """بازه‌ی پیشنهادیِ سالِ مالیِ بعدی (۱ فروردین تا آخرِ اسفند، با محاسبه‌ی کبیسه)."""
    return svc.suggest_next(db)


@router.post("", response_model=FiscalYearOut, status_code=201)
def create_year(
    data: FiscalYearIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("accounting", "approve")),
):
    return _out(db, svc.create_year(db, data))


@router.patch("/{year_id}", response_model=FiscalYearOut)
def update_year(
    year_id: UUID,
    data: FiscalYearUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("accounting", "approve")),
):
    return _out(db, svc.update_year(db, year_id, data))


@router.post("/{year_id}/activate", response_model=FiscalYearOut)
def activate_year(
    year_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("accounting", "approve")),
):
    return _out(db, svc.activate_year(db, year_id))


@router.post("/{year_id}/carry-forward")
def carry_forward(
    year_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "approve")),
):
    return svc.carry_forward(db, year_id, user)


@router.post("/{year_id}/close", response_model=FiscalYearOut)
def close_year(
    year_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "approve")),
):
    return _out(db, svc.close_year(db, year_id, user))


@router.delete("/{year_id}", status_code=204)
def delete_year(
    year_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("accounting", "approve")),
):
    svc.delete_year(db, year_id)
