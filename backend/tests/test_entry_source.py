"""«این سند از کدام عملیات آمد؟» — نیمه‌ی دومِ ردیابی.

جهتِ عملیات ← سند از قبل محکم بود (`journal_entry_id` روی شانزده مدل، و
`voiding._apply_void` رویش زندگی می‌کند). جهتِ معکوس نبود: `JournalEntry.source_id`
تعریف شده بود، کامنت داشت، و **هیچ‌جا نوشته نمی‌شد**.

جواب به‌جای ذخیره‌شدن **مشتق** می‌شود: `source_type` می‌گوید سراغِ کدام جدول
برویم و `journal_entry_id` آن‌جا جواب را دارد. مهم‌ترین تستِ این فایل
`test_every_model_with_a_journal_link_is_registered` است — تنها چیزی که جلوی
پوسیدنِ دوباره را می‌گیرد.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event, inspect as sa_inspect

from app.database import Base
from app.models.accounting import JournalEntry, JournalLine
from app.models.invoices import SalesInvoice
from app.models.tenant import Tenant
from app.services import chart_codes as cc
from app.services import entry_source
from app.services.common import get_account, make_journal_entry
from app.tenant_context import session_tenant
from tests.factories import main_warehouse, make_item


def _hybrid(db) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = "hybrid"
    db.flush()


def _stock_up(db, user, item, warehouse, qty=100) -> None:
    from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
    from app.services.inventory import post_purchase_invoice

    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 1, 1),
            warehouse_id=warehouse.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(1000))],
        ),
        user,
    )


def _sell(db, user) -> SalesInvoice:
    from app.schemas.invoices import SalesInvoiceIn, SalesInvoiceLineIn
    from app.services.inventory import post_sales_invoice

    item = make_item(db, sales_price=Decimal(5000))
    warehouse = main_warehouse(db)
    _stock_up(db, user, item, warehouse)
    return post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=date(2026, 6, 1),
            warehouse_id=warehouse.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(5000))],
        ),
        user,
    )


def _manual(db, user) -> JournalEntry:
    cash = get_account(db, cc.CASH).id
    inventory = get_account(db, cc.INVENTORY).id
    return make_journal_entry(
        db,
        date(2026, 6, 1),
        "سندِ دستی",
        "manual",
        user,
        [
            JournalLine(account_id=inventory, debit=100, credit=0),
            JournalLine(account_id=cash, debit=0, credit=100),
        ],
    )


# ── جهتِ معکوس کار می‌کند ────────────────────────────────────────────────────


def test_a_sales_invoice_entry_names_its_invoice(db, user):
    """**قیدِ اصلی.** تا امروز فقط «فاکتور فروش» معلوم بود، نه کدام فاکتور."""
    _hybrid(db)
    invoice = _sell(db, user)
    entry = db.get(JournalEntry, invoice.journal_entry_id)

    found = entry_source.resolve_source(db, entry)
    assert found is not None
    assert found["source_type"] == "sales_invoice"
    assert found["model"] == "SalesInvoice"
    assert found["id"] == invoice.id
    assert found["number"] == str(invoice.number)
    assert found["count"] == 1


def test_the_label_carries_the_number(db, user):
    """چیزی که روی برگه‌ی چاپی و در فهرست دیده می‌شود."""
    _hybrid(db)
    invoice = _sell(db, user)
    entry = db.get(JournalEntry, invoice.journal_entry_id)

    text = entry_source.describe(entry_source.resolve_source(db, entry))
    assert text.startswith("فاکتور فروش")
    assert text != "فاکتور فروش"  # شماره هم باید باشد


def test_an_accounting_native_entry_has_no_source(db, user):
    """سندِ دستی عملیاتِ منبع ندارد — `None` درست است، نه شکاف."""
    entry = _manual(db, user)
    db.flush()

    assert entry_source.resolve_source(db, entry) is None
    assert entry_source.describe(None) == ""


def test_an_unknown_source_type_does_not_explode(db, user):
    """`source_type`ی که در رجیستری نیست باید تمیز `None` بدهد، نه خطا."""
    entry = _manual(db, user)
    entry.source_type = "something_nobody_registered"
    db.flush()

    assert entry_source.resolve_source(db, entry) is None


# ── رجیستری نباید بپوسد ─────────────────────────────────────────────────────


def test_every_model_with_a_journal_link_is_registered(db):
    """**مهم‌ترین تستِ این فایل.**

    هر مدلی که `journal_entry_id` دارد باید یا در `SOURCE_MODELS` باشد یا صریحاً
    در `MODELS_WITHOUT_ENTRIES`. بدونِ این، مدلِ تازه بی‌سروصدا از ردیابی جا
    می‌ماند — دقیقاً بلایی که سرِ `source_id` آمد.
    """
    registered = {m.__name__ for m in entry_source.SOURCE_MODELS.values()}
    linked = {
        mapper.class_.__name__
        for mapper in Base.registry.mappers
        if "journal_entry_id" in sa_inspect(mapper.class_).columns
    }
    missing = linked - registered - entry_source.MODELS_WITHOUT_ENTRIES
    assert not missing, f"این مدل‌ها به سند وصل‌اند ولی در رجیستری نیستند: {sorted(missing)}"


def test_the_exemption_list_stays_honest(db):
    """مدلی که در فهرستِ معافیت است باید واقعاً ستونِ پیوند داشته باشد.

    وگرنه معافیت به یک نامِ مرده تبدیل می‌شود و کسی متوجه نمی‌شود.
    """
    linked = {
        mapper.class_.__name__
        for mapper in Base.registry.mappers
        if "journal_entry_id" in sa_inspect(mapper.class_).columns
    }
    assert entry_source.MODELS_WITHOUT_ENTRIES <= linked


# ── کارایی ──────────────────────────────────────────────────────────────────


def test_lookup_cost_grows_with_source_types_not_with_entries(db, user):
    """**قیدِ کارایی.** فهرستِ اسناد نباید N+1 بزند.

    سه فاکتور فروش = یک نوعِ منبع = یک کوئری. اگر روزی کسی حلقه‌ی per-entry
    بگذارد، این عدد بالا می‌رود و تست قرمز می‌شود.
    """
    _hybrid(db)
    invoices = [_sell(db, user) for _ in range(3)]
    entries = [db.get(JournalEntry, inv.journal_entry_id) for inv in invoices]

    seen: list[str] = []

    def _count(conn, cursor, statement, params, context, executemany):
        seen.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", _count)
    try:
        found = entry_source.resolve_sources(db, entries)
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", _count)

    assert len(found) == 3
    assert len(seen) == 1, f"انتظار یک کوئری بود، {len(seen)} تا اجرا شد"


# ── مسیرِ HTTP ──────────────────────────────────────────────────────────────


def test_the_entry_list_carries_the_source(db, user, client):
    """تنها جایی که کاربر سند را می‌بیند همین فهرست است — روتر `GET /{id}` ندارد."""
    _hybrid(db)
    invoice = _sell(db, user)
    db.flush()

    res = client.get("/api/journal-entries")
    assert res.status_code == 200, res.text
    rows = res.json()["items"]
    row = next(r for r in rows if r["id"] == str(invoice.journal_entry_id))
    assert row["source"]["source_type"] == "sales_invoice"
    assert row["source"]["id"] == str(invoice.id)

    manual = next((r for r in rows if r["source_type"] == "manual"), None)
    if manual is not None:
        assert manual["source"] is None
