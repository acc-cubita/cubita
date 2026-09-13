"""راه‌اندازی: ورودِ گروهیِ کالا/اشخاص و مانده‌های اول دوره (سند افتتاحیه).

هدف: مهاجرتِ یک کسب‌وکارِ واقعی به کوبیتا. به‌جای ثبتِ تک‌تک، فهرستِ کالا/اشخاص یک‌جا
وارد می‌شود و مانده‌های اول دوره در یک سندِ افتتاحیه‌ی متوازن ثبت می‌شوند.
"""
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalLine
from app.models.inventory import Contact, Item, StockLedger
from app.models.user import User
from app.schemas.inventory import ENTITY_TYPES
from app.schemas.onboarding import (
    ContactImportRow,
    ImportContactsIn,
    ImportItemsIn,
    OpeningBalancesIn,
)
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.inventory import get_total_stock_qty
from app.services.period_close import assert_period_open

CONTACT_TYPES = ("customer", "supplier", "both")


# ── ورودِ گروهی ────────────────────────────────────────
def import_items(db: Session, data: ImportItemsIn, user: User) -> dict:
    """کالاها را یک‌جا وارد می‌کند. SKUِ تکراری (موجود یا داخلِ همین دسته) رد می‌شود."""
    existing = {sku for (sku,) in db.query(Item.sku).all()}
    created = skipped = 0
    errors: list[dict] = []
    seen: set[str] = set()

    for i, row in enumerate(data.rows, start=1):
        sku = (row.sku or "").strip()
        name = (row.name or "").strip()
        if not sku or not name:
            errors.append({"row": i, "message": "کد کالا (SKU) و نام الزامی‌اند"})
            continue
        if sku in existing or sku in seen:
            skipped += 1
            continue
        if row.sales_price < 0:
            errors.append({"row": i, "message": "قیمت فروش نمی‌تواند منفی باشد"})
            continue
        seen.add(sku)
        barcode = (row.barcode or "").strip() or None
        db.add(Item(
            sku=sku, name=name, category=row.category or "", unit=row.unit or "عدد",
            is_service=row.is_service, sales_price=row.sales_price, barcode=barcode,
        ))
        created += 1

    db.flush()
    return {"created": created, "skipped": skipped, "errors": errors}


def import_contacts(db: Session, data: ImportContactsIn, user: User) -> dict:
    """اشخاص را یک‌جا وارد می‌کند. نامِ تکراری (موجود یا داخلِ همین دسته) رد می‌شود."""
    existing = {name for (name,) in db.query(Contact.name).all()}
    created = skipped = 0
    errors: list[dict] = []
    seen: set[str] = set()

    for i, row in enumerate(data.rows, start=1):
        name = (row.name or "").strip()
        if not name:
            errors.append({"row": i, "message": "نام الزامی است"})
            continue
        if row.type not in CONTACT_TYPES:
            errors.append({"row": i, "message": "نوع باید مشتری/تأمین‌کننده/هردو باشد"})
            continue
        if row.entity_type not in ENTITY_TYPES:
            errors.append({"row": i, "message": "نوعِ شخص باید حقیقی یا حقوقی باشد"})
            continue
        if name in existing or name in seen:
            skipped += 1
            continue
        seen.add(name)
        db.add(Contact(
            name=name, type=row.type, phone=(row.phone or None), email=(row.email or None),
            address=row.address or "", entity_type=row.entity_type,
            national_id=(row.national_id or "").strip() or None,
            economic_code=(row.economic_code or "").strip() or None,
            postal_code=(row.postal_code or "").strip() or None,
        ))
        created += 1

    db.flush()
    return {"created": created, "skipped": skipped, "errors": errors}


# ── مانده‌های اول دوره / سند افتتاحیه ──────────────────
def _existing_opening(db: Session) -> JournalEntry | None:
    return (
        db.query(JournalEntry)
        .filter(JournalEntry.source_type == "opening", JournalEntry.voided_at.is_(None))
        .first()
    )


def get_opening_status(db: Session) -> dict:
    entry = _existing_opening(db)
    if entry is None:
        return {"exists": False, "entry_id": None, "entry_number": None, "entry_date": None}
    return {
        "exists": True,
        "entry_id": entry.id,
        "entry_number": entry.number,
        "entry_date": entry.entry_date,
    }


def _contact_opening_lines(db: Session) -> list[JournalLine]:
    """مانده‌ی اول دوره‌ی طرف‌حساب‌ها را به ردیفِ سند تبدیل می‌کند.

    همان الگویِ موجودیِ اول دوره: عدد روی خودِ طرف‌حساب می‌نشیند و سندِ افتتاحیه از
    رویش ساخته می‌شود — نه اینکه کاربر مجبور باشد همان رقم را یک‌بار در فرمِ
    طرف‌حساب و یک‌بار در ردیف‌های سند وارد کند.

    تفصیلیِ طرف‌حساب (اگر داشته باشد) روی ردیف می‌نشیند، پس مانده‌ی افتتاحیه هم در
    گزارشِ تفصیلی تفکیک می‌شود، نه اینکه یک رقمِ درهم روی حسابِ دریافتنی بماند.
    """
    lines: list[JournalLine] = []
    rows = (
        db.query(Contact)
        .filter((Contact.opening_ar_amount > 0) | (Contact.opening_ap_amount > 0))
        .order_by(Contact.name)
        .all()
    )
    if not rows:
        return lines

    for contact in rows:
        for amount, side, role, label in (
            (contact.opening_ar_amount, contact.opening_ar_side, cc.ACCOUNTS_RECEIVABLE, "دریافتنی"),
            (contact.opening_ap_amount, contact.opening_ap_side, cc.ACCOUNTS_PAYABLE, "پرداختنی"),
        ):
            amount = Decimal(amount or 0)
            if amount <= 0:
                continue
            lines.append(JournalLine(
                account_id=get_account(db, role).id,
                debit=amount if side == "debit" else Decimal(0),
                credit=amount if side == "credit" else Decimal(0),
                analytic_id=contact.analytic_id,
                description=f"{label} — {contact.name} (اول دوره)",
            ))
    return lines


def create_opening_entry(db: Session, data: OpeningBalancesIn, user: User) -> JournalEntry:
    """یک سندِ افتتاحیه‌ی متوازن می‌سازد و در صورتِ وجودِ موجودیِ اول دوره، حرکاتِ
    انبار و میانگینِ بها را هم ثبت می‌کند.

    - موجودیِ اول دوره (stock) حرکتِ ورودِ `opening` می‌سازد، میانگینِ موزون را ست
      می‌کند و ارزشش خودکار به‌عنوان بدهکارِ حسابِ «موجودی کالا» به سند می‌رود (پس
      حسابِ موجودی را دستی وارد نکنید).
    - اگر سند متوازن نباشد و `balancing_account_id` داده شده باشد، اختلاف به آن حساب
      (معمولاً «سرمایه») بسته می‌شود؛ وگرنه رد می‌شود.
    """
    if _existing_opening(db) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "سند افتتاحیه از قبل ثبت شده است")
    assert_period_open(db, data.entry_date)
    # مانده‌ی طرف‌حساب‌ها منبعِ سومِ این سند است (کنارِ ردیف‌های دستی و موجودیِ کالا)،
    # پس در این گارد هم باید شمرده شود — وگرنه سندی که *فقط* از مانده‌ی طرف‌حساب‌ها
    # می‌آید رد می‌شد.
    contact_lines = _contact_opening_lines(db)
    if not data.lines and not data.stock and not contact_lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "حداقل یک مانده یا موجودیِ اول دوره لازم است")

    journal_lines: list[JournalLine] = [
        JournalLine(account_id=ln.account_id, debit=ln.debit, credit=ln.credit, description=ln.description or "مانده اول دوره")
        for ln in data.lines
    ]

    # موجودیِ اول دوره → حرکتِ انبار + میانگینِ بها + ارزشِ ریالی
    inventory_value = Decimal(0)
    opening_moves: list[StockLedger] = []
    for s in data.stock:
        item = db.get(Item, s.item_id)
        if item is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "کالای موجودیِ اول دوره یافت نشد")
        if item.is_service:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کالای «{item.name}» خدماتی است و موجودی ندارد")
        line_value = s.qty * s.unit_cost
        inventory_value += line_value
        existing_qty = get_total_stock_qty(db, item.id)
        new_qty = existing_qty + s.qty
        if new_qty > 0:
            item.average_cost = ((existing_qty * Decimal(item.average_cost)) + line_value) / new_qty
        opening_moves.append(StockLedger(
            item_id=s.item_id, warehouse_id=s.warehouse_id, qty=s.qty,
            unit_cost=s.unit_cost, entry_date=data.entry_date, source_type="opening",
        ))
        db.add(opening_moves[-1])

    from app.services import valuation

    #: موجودیِ اول دوره معمولاً قدیمی‌ترین تاریخ را دارد، پس «پیش‌تاریخ» است اگر
    #: پیش از آن حرکتی ثبت شده باشد — و آن‌وقت میانگین باید از بازپخش بیاید.
    valuation.settle_posting(db, opening_moves)

    if inventory_value > 0:
        journal_lines.append(JournalLine(
            account_id=get_account(db, cc.INVENTORY).id,
            debit=inventory_value, credit=0, description="موجودیِ کالا — اول دوره",
        ))

    journal_lines.extend(contact_lines)

    total_debit = sum((Decimal(ln.debit) for ln in journal_lines), Decimal(0))
    total_credit = sum((Decimal(ln.credit) for ln in journal_lines), Decimal(0))
    diff = total_debit - total_credit

    if diff != 0:
        if data.balancing_account_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"سند متوازن نیست (اختلاف {abs(diff)}). حسابِ تراز (سرمایه) را انتخاب کنید.",
            )
        journal_lines.append(JournalLine(
            account_id=data.balancing_account_id,
            debit=Decimal(0) if diff > 0 else -diff,
            credit=diff if diff > 0 else Decimal(0),
            description="تراز افتتاحیه (سرمایه)",
        ))

    if len(journal_lines) < 2:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سند افتتاحیه باید حداقل دو ردیف داشته باشد")

    entry = make_journal_entry(
        db, data.entry_date, "سند افتتاحیه — مانده‌های اول دوره", "opening", user, journal_lines,
    )
    return entry
