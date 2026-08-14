"""مرکز هشدارها — تجمیعِ چک، مطالبات معوق، سقف اعتبار، سند تکرارشونده، تقویم، موجودی منفی."""
from datetime import date, timedelta
from decimal import Decimal

from app.models.banking import Check
from app.models.calendar import CalendarEvent
from app.models.inventory import StockLedger
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.schemas.recurring import RecurringEntryIn, RecurringLineIn
from app.services import chart_codes as cc
from app.services.alerts import get_alerts
from app.services.common import get_account
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.recurring import create_template
from tests.factories import main_warehouse, make_contact, make_item

AS_OF = date(2026, 6, 15)


def _cats(result, category):
    return [i for i in result["items"] if i["category"] == category]


def _add_check(db, user, *, due, status="in_hand", type_="receivable", number="123", amount=5_000_000):
    db.add(
        Check(
            type=type_,
            number=number,
            bank_name="ملی",
            amount=Decimal(amount),
            issue_date=AS_OF - timedelta(days=30),
            due_date=due,
            status=status,
            created_by_id=user.id,
        )
    )
    db.flush()


def test_check_due_and_overdue_only_active(db, user):
    _add_check(db, user, due=AS_OF + timedelta(days=3), number="soon")       # نزدیک → warning
    _add_check(db, user, due=AS_OF - timedelta(days=5), number="late", status="issued", type_="payable")  # گذشته → danger
    _add_check(db, user, due=AS_OF + timedelta(days=30), number="far")        # دور → نه
    _add_check(db, user, due=AS_OF, number="done", status="cleared")          # تعیین‌تکلیف‌شده → نه

    checks = _cats(get_alerts(db, AS_OF), "check")
    numbers = {c["title"] for c in checks}
    assert any("soon" in n for n in numbers)
    assert any("late" in n for n in numbers)
    assert not any("far" in n for n in numbers)
    assert not any("done" in n for n in numbers)
    late = next(c for c in checks if "late" in c["title"])
    soon = next(c for c in checks if "soon" in c["title"])
    assert late["severity"] == "danger"
    assert soon["severity"] == "warning"


def _stock_and_sell(db, user, *, contact, amount, on):
    wh = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=AS_OF - timedelta(days=200),
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(100_000))],
        ),
        user,
    )
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=on,
            warehouse_id=wh.id,
            contact_id=contact.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(amount))],
        ),
        user,
    )


def test_overdue_receivable_and_credit_over_limit(db, user):
    contact = make_contact(db, name="بدهکار", credit_limit=1_000_000)
    _stock_and_sell(db, user, contact=contact, amount=5_000_000, on=AS_OF - timedelta(days=100))

    result = get_alerts(db, AS_OF)
    receivables = _cats(result, "receivable")
    credit = _cats(result, "credit")
    assert any(r["ref_id"] == contact.id and r["severity"] == "danger" for r in receivables)  # >۹۰ روز
    assert any(c["ref_id"] == contact.id for c in credit)  # ۵م > سقف ۱م
    over = next(c for c in credit if c["ref_id"] == contact.id)
    assert over["amount"] == Decimal(4_000_000)  # ۵م − سقف ۱م


def test_recurring_due_alert(db, user):
    exp = get_account(db, cc.INVENTORY_ADJUSTMENT)
    cash = get_account(db, cc.CASH)
    tpl = create_template(
        db,
        RecurringEntryIn(
            title="اجاره",
            frequency="monthly",
            start_date=AS_OF - timedelta(days=1),  # سررسیدشده
            lines=[
                RecurringLineIn(account_id=exp.id, debit=Decimal(2_000_000), credit=Decimal(0)),
                RecurringLineIn(account_id=cash.id, debit=Decimal(0), credit=Decimal(2_000_000)),
            ],
        ),
        user,
    )
    recurring = _cats(get_alerts(db, AS_OF), "recurring")
    assert any(r["ref_id"] == tpl.id for r in recurring)
    assert next(r for r in recurring if r["ref_id"] == tpl.id)["amount"] == Decimal(2_000_000)


def test_calendar_reminders(db, user):
    db.add(CalendarEvent(title="گذشته", event_date=AS_OF - timedelta(days=2), created_by_id=user.id))
    db.add(CalendarEvent(title="پیش‌رو", event_date=AS_OF + timedelta(days=2), created_by_id=user.id))
    db.add(CalendarEvent(title="انجام‌شده", event_date=AS_OF - timedelta(days=1), is_done=True, created_by_id=user.id))
    db.add(CalendarEvent(title="دور", event_date=AS_OF + timedelta(days=30), created_by_id=user.id))
    db.flush()

    cal = _cats(get_alerts(db, AS_OF), "calendar")
    titles = {c["title"] for c in cal}
    assert "گذشته" in titles and "پیش‌رو" in titles
    assert "انجام‌شده" not in titles and "دور" not in titles
    assert next(c for c in cal if c["title"] == "گذشته")["severity"] == "danger"
    assert next(c for c in cal if c["title"] == "پیش‌رو")["severity"] == "info"


def test_negative_stock_alert(db, user):
    wh = main_warehouse(db)
    item = make_item(db, name="کالای منفی")
    db.add(
        StockLedger(
            item_id=item.id,
            warehouse_id=wh.id,
            qty=Decimal(-3),
            unit_cost=Decimal(100_000),
            source_type="adjustment",
        )
    )
    db.flush()

    stock = _cats(get_alerts(db, AS_OF), "stock")
    assert any(s["ref_id"] == item.id and s["severity"] == "danger" for s in stock)


def test_counts_match_items_and_total(db, user):
    _add_check(db, user, due=AS_OF, number="c1")
    _add_check(db, user, due=AS_OF, number="c2")
    db.add(CalendarEvent(title="یادآور", event_date=AS_OF, created_by_id=user.id))
    db.flush()

    result = get_alerts(db, AS_OF)
    assert result["total"] == len(result["items"])
    assert sum(result["counts"].values()) == result["total"]
    assert result["counts"]["check"] == 2


def test_empty_when_nothing_actionable(db, user):
    result = get_alerts(db, AS_OF)
    assert result["total"] == 0
    assert result["items"] == []
