from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import require_permission
from app.models.counters import DOC_JOURNAL_ENTRY
from app.services.numbering import next_document_number
from app.models.accounting import JournalEntry, JournalLine
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.accounting import JournalEntryIn, JournalEntryOut
from app.services.cost_centers import resolve_cost_center_id
from app.services.period_close import assert_period_open

router = APIRouter(prefix="/api/journal-entries", tags=["journal"])


@router.get("", response_model=Page[JournalEntryOut])
def list_entries(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("accounting", "view")),
):
    # (entry_date, number) یکتاست چون number از sequence می‌آید — کلید امن برای keyset
    items, next_cursor = paginate(
        db.query(JournalEntry).options(selectinload(JournalEntry.lines)),
        [JournalEntry.entry_date, JournalEntry.number],
        params,
    )
    return Page(items=items, next_cursor=next_cursor)


@router.post("", response_model=JournalEntryOut, status_code=201)
def create_entry(
    data: JournalEntryIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    assert_period_open(db, data.entry_date)
    cost_center_id = resolve_cost_center_id(db, data.cost_center_id)

    # شماره‌ی سند از یک sequence اتمیک پایگاه‌داده گرفته می‌شود تا زیر بار همزمان چند کاربر تصادم نکند
    number = next_document_number(db, DOC_JOURNAL_ENTRY)

    entry = JournalEntry(
        number=number,
        entry_date=data.entry_date,
        description=data.description,
        source_type="manual",
        created_by_id=user.id,
        lines=[
            JournalLine(
                account_id=line.account_id,
                cost_center_id=cost_center_id,
                debit=line.debit,
                credit=line.credit,
                description=line.description,
            )
            for line in data.lines
        ],
    )
    db.add(entry)
    db.flush()
    db.refresh(entry)
    return entry
