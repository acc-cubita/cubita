"""ورودِ گروهیِ کالا/اشخاص و مانده‌های اول دوره.

نامِ فایل تاریخی است: این اندپوینت‌ها زمانی پشتِ صفحه‌ی «فرآیند راه‌اندازی» بودند. آن
ماژول بازنشسته شد و هر سه کار به ماژولِ خودش رفت — ورودِ کالا به «انبار»، ورودِ اشخاص
به «اشخاص» و مانده‌ی اول دوره به «حسابداری». مجوزها از همان اول هم همین را می‌گفتند و
دست‌نخورده مانده‌اند؛ فقط جایِ صفحه‌ها در پنل عوض شده.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.accounting import JournalEntryOut
from app.schemas.onboarding import (
    ImportContactsIn,
    ImportItemsIn,
    ImportResult,
    OpeningBalancesIn,
    OpeningStatusOut,
)
from app.services import onboarding as svc

router = APIRouter(prefix="/api", tags=["onboarding"])


# ── ورودِ گروهی ────────────────────────────────────────
@router.post("/import/items", response_model=ImportResult)
def import_items(
    data: ImportItemsIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "create")),
):
    return svc.import_items(db, data, user)


@router.post("/import/contacts", response_model=ImportResult)
def import_contacts(
    data: ImportContactsIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return svc.import_contacts(db, data, user)


# ── مانده‌های اول دوره / سند افتتاحیه ──────────────────
@router.get("/opening-balances/status", response_model=OpeningStatusOut)
def opening_status(
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return svc.get_opening_status(db)


@router.post("/opening-balances", response_model=JournalEntryOut, status_code=201)
def create_opening(
    data: OpeningBalancesIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    return svc.create_opening_entry(db, data, user)
