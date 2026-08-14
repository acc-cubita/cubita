"""ابطال سند.

بزرگ‌ترین شکاف کارکردی سیستم بود: فاکتور اشتباه هیچ راه تصحیحی نداشت.

مهم‌ترین تست این پرونده `test_trial_balance_returns_to_where_it_was` است. ابطال،
سند *می‌نویسد* و نه اینکه چیزی پاک کند، پس هر اشتباهی در آن به‌شکل دفتری نامتوازن
یا مانده‌ی نادرست ظاهر می‌شود — نه به‌شکل خطا. تنها چیزی که این را می‌گیرد سنجیدن
مانده‌ها قبل و بعد است.

`test_average_cost_returns_to_its_previous_value` هم بی‌سروصداترین حالت شکست را
می‌سنجد: اگر بهای تمام‌شده بعد از ابطال درست برنگردد، هیچ خطایی رخ نمی‌دهد و فقط
سودِ همه‌ی فروش‌های بعدی کمی غلط می‌شود.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import JournalEntry, JournalLine
from app.models.inventory import Item, StockLedger, Warehouse
from app.models.invoices import PurchaseInvoice, SalesInvoice
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.schemas.returns import SalesReturnIn, SalesReturnLineIn
from app.services.inventory import get_stock_qty, post_purchase_invoice, post_sales_invoice
from app.services.returns import post_sales_return
from app.services.voiding import (
    void_journal_entry,
    void_purchase_invoice,
    void_sales_invoice,
)

TODAY = date.today()


@pytest.fixture
def warehouse(db):
    return db.query(Warehouse).filter(Warehouse.code == "MAIN").one()


@pytest.fixture
def widget(db):
    item = Item(sku=f"VOID-{id(db)}", name="کالای آزمون ابطال", unit="عدد", sales_price=5000)
    db.add(item)
    db.flush()
    return item


def buy(db, user, warehouse, item, qty, unit_cost):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=warehouse.id,
            contact_id=None,
            description="خرید",
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=qty, unit_cost=unit_cost, description="")],
        ),
        user,
    )


def sell(db, user, warehouse, item, qty, unit_price):
    return post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=warehouse.id,
            contact_id=None,
            description="فروش",
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=qty, unit_price=unit_price, description="")],
        ),
        user,
    )


def trial_balance(db) -> dict:
    """مانده‌ی هر حساب — فقط از روی ردیف‌های سند، مثل خودِ گزارش."""
    rows = (
        db.query(JournalLine.account_id, JournalLine.debit, JournalLine.credit)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .all()
    )
    balances: dict = {}
    for account_id, debit, credit in rows:
        balances[account_id] = balances.get(account_id, Decimal(0)) + Decimal(debit) - Decimal(credit)
    return {k: v for k, v in balances.items() if v != 0}


def _return(db, user, inv, item, qty):
    return post_sales_return(
        db,
        SalesReturnIn(
            return_date=TODAY,
            sales_invoice_id=inv.id,
            lines=[SalesReturnLineIn(item_id=item.id, qty=Decimal(qty))],
        ),
        user,
    )


# --- محافظِ تعارضِ برگشت/ابطال: نباید یک فروش دوبار معکوس شود -------------------------


def test_return_on_voided_invoice_is_blocked(db, user, warehouse, widget):
    """روی فاکتورِ باطل‌شده نباید برگشت خورد (وگرنه فروش دوبار برمی‌گردد)."""
    buy(db, user, warehouse, widget, 10, 1000)
    inv = sell(db, user, warehouse, widget, 5, 5000)
    void_sales_invoice(db, inv.id, reason="اشتباه", user=user)

    with pytest.raises(HTTPException) as exc:
        _return(db, user, inv, widget, 2)
    assert exc.value.status_code == 400


def test_void_is_blocked_when_invoice_has_return(db, user, warehouse, widget):
    """ابطالِ فاکتوری که برگشت خورده باید بسته باشد — اول باید برگشت برگردد."""
    buy(db, user, warehouse, widget, 10, 1000)
    inv = sell(db, user, warehouse, widget, 5, 5000)
    _return(db, user, inv, widget, 2)

    with pytest.raises(HTTPException) as exc:
        void_sales_invoice(db, inv.id, reason="اشتباه", user=user)
    assert exc.value.status_code == 409


# --- هسته: دفتر باید به حالت قبل برگردد ---------------------------------------------


def test_trial_balance_returns_to_where_it_was(db, user, warehouse, widget):
    """مهم‌ترین تست این پرونده.

    ابطال سند می‌نویسد و چیزی پاک نمی‌کند، پس اشتباهش به‌شکل خطا ظاهر نمی‌شود —
    فقط دفتر بی‌صدا غلط می‌ماند.
    """
    buy(db, user, warehouse, widget, qty=10, unit_cost=1000)
    before = trial_balance(db)

    invoice = sell(db, user, warehouse, widget, qty=4, unit_price=2500)
    assert trial_balance(db) != before, "فروش باید دفتر را عوض کرده باشد"

    void_sales_invoice(db, invoice.id, reason="ثبت اشتباه", user=user)
    assert trial_balance(db) == before, "بعد از ابطال، مانده‌ها به حالت قبل برنگشتند"


def test_every_entry_including_the_reversal_stays_balanced(db, user, warehouse, widget):
    buy(db, user, warehouse, widget, qty=10, unit_cost=1000)
    invoice = sell(db, user, warehouse, widget, qty=3, unit_price=2000)
    void_sales_invoice(db, invoice.id, reason="اشتباه", user=user)

    for entry in db.query(JournalEntry).all():
        debit = sum(Decimal(l.debit) for l in entry.lines)
        credit = sum(Decimal(l.credit) for l in entry.lines)
        assert debit == credit, f"سند {entry.number} متوازن نیست: بدهکار {debit} / بستانکار {credit}"


def test_the_original_document_is_kept_not_deleted(db, user, warehouse, widget):
    """حذف سند مالی در حسابداری قابل قبول نیست — ردِ حسابرسی باید بماند."""
    buy(db, user, warehouse, widget, qty=5, unit_cost=1000)
    invoice = sell(db, user, warehouse, widget, qty=2, unit_price=3000)
    invoice_id = invoice.id

    void_sales_invoice(db, invoice_id, reason="مشتری انصراف داد", user=user)

    still_there = db.get(SalesInvoice, invoice_id)
    assert still_there is not None, "فاکتور پاک شد — ردِ حسابرسی از بین رفت"
    assert still_there.is_voided
    assert still_there.void_reason == "مشتری انصراف داد"
    assert still_there.voided_by_id == user.id


def test_the_reversal_points_back_at_the_original(db, user, warehouse, widget):
    buy(db, user, warehouse, widget, qty=5, unit_cost=1000)
    invoice = sell(db, user, warehouse, widget, qty=2, unit_price=3000)
    original_entry_id = invoice.journal_entry_id

    reversal = void_sales_invoice(db, invoice.id, reason="اشتباه", user=user)
    assert reversal.reverses_entry_id == original_entry_id


# --- انبار ---------------------------------------------------------------------------


def test_stock_comes_back_after_voiding_a_sale(db, user, warehouse, widget):
    buy(db, user, warehouse, widget, qty=10, unit_cost=1000)
    invoice = sell(db, user, warehouse, widget, qty=4, unit_price=2500)
    assert get_stock_qty(db, widget.id, warehouse.id) == 6

    void_sales_invoice(db, invoice.id, reason="اشتباه", user=user)
    assert get_stock_qty(db, widget.id, warehouse.id) == 10


def test_stock_ledger_stays_append_only(db, user, warehouse, widget):
    """اصلاح باید ردیف جدید بنویسد، نه ردیف قبلی را دست بزند."""
    buy(db, user, warehouse, widget, qty=10, unit_cost=1000)
    invoice = sell(db, user, warehouse, widget, qty=4, unit_price=2500)
    before = db.query(StockLedger).filter(StockLedger.item_id == widget.id).count()

    void_sales_invoice(db, invoice.id, reason="اشتباه", user=user)
    after = db.query(StockLedger).filter(StockLedger.item_id == widget.id).count()
    assert after > before, "ردیف جبرانی نوشته نشد"

    sale_moves = (
        db.query(StockLedger)
        .filter(StockLedger.source_type == "sales_invoice", StockLedger.source_id == invoice.id)
        .all()
    )
    assert sale_moves, "حرکت اصلی فروش پاک شده — دفتر دیگر append-only نیست"


def test_average_cost_returns_to_its_previous_value(db, user, warehouse, widget):
    """بی‌سروصداترین حالت شکست.

    اگر میانگین موزون بعد از ابطال درست برنگردد هیچ خطایی رخ نمی‌دهد؛ فقط سودِ
    همه‌ی فروش‌های بعدی کمی غلط می‌شود و هیچ‌کس متوجه نمی‌شود.
    """
    buy(db, user, warehouse, widget, qty=10, unit_cost=1000)
    db.refresh(widget)
    assert Decimal(widget.average_cost) == 1000

    second = buy(db, user, warehouse, widget, qty=10, unit_cost=2000)
    db.refresh(widget)
    assert Decimal(widget.average_cost) == 1500, "میانگین موزون دو خرید باید ۱۵۰۰ باشد"

    void_purchase_invoice(db, second.id, reason="خرید اشتباه ثبت شد", user=user)
    db.refresh(widget)
    assert Decimal(widget.average_cost) == 1000, "میانگین موزون بعد از ابطال برنگشت"


def test_voiding_a_purchase_whose_goods_were_sold_is_refused(db, user, warehouse, widget):
    """ابطالی که موجودی را منفی کند باید رد شود، با پیامی که راه درست را بگوید."""
    purchase = buy(db, user, warehouse, widget, qty=5, unit_cost=1000)
    sell(db, user, warehouse, widget, qty=4, unit_price=2000)

    with pytest.raises(HTTPException) as exc:
        void_purchase_invoice(db, purchase.id, reason="اشتباه", user=user)
    assert exc.value.status_code == 409
    assert "منفی" in exc.value.detail
    assert get_stock_qty(db, widget.id, warehouse.id) == 1, "موجودی نباید عوض شده باشد"


# --- گاردها ---------------------------------------------------------------------------


def test_a_document_cannot_be_voided_twice(db, user, warehouse, widget):
    buy(db, user, warehouse, widget, qty=5, unit_cost=1000)
    invoice = sell(db, user, warehouse, widget, qty=2, unit_price=3000)
    void_sales_invoice(db, invoice.id, reason="اشتباه", user=user)

    with pytest.raises(HTTPException) as exc:
        void_sales_invoice(db, invoice.id, reason="دوباره", user=user)
    assert exc.value.status_code == 409


def test_voiding_into_a_closed_period_is_refused(db, user, warehouse, widget):
    """گارد روی تاریخِ *معکوس* اجرا می‌شود، نه تاریخ سند اصلی."""
    from app.schemas.period_close import FiscalPeriodCloseIn
    from app.services.period_close import close_period

    buy(db, user, warehouse, widget, qty=5, unit_cost=1000)
    invoice = sell(db, user, warehouse, widget, qty=2, unit_price=3000)
    close_period(db, FiscalPeriodCloseIn(closing_date=TODAY, description="بستن دوره"), user)

    with pytest.raises(HTTPException) as exc:
        void_sales_invoice(db, invoice.id, reason="اشتباه", user=user)
    assert exc.value.status_code in (400, 409)


def test_a_document_backed_entry_cannot_be_voided_as_a_plain_entry(db, user, warehouse, widget):
    """اگر سندِ فاکتور مستقیم باطل شود، فاکتور معتبر می‌ماند و انبار برنمی‌گردد."""
    buy(db, user, warehouse, widget, qty=5, unit_cost=1000)
    invoice = sell(db, user, warehouse, widget, qty=2, unit_price=3000)

    with pytest.raises(HTTPException) as exc:
        void_journal_entry(db, invoice.journal_entry_id, reason="اشتباه", user=user)
    assert exc.value.status_code == 409
    assert "اصلی" in exc.value.detail


def test_a_reversal_cannot_itself_be_voided(db, user, warehouse, widget):
    buy(db, user, warehouse, widget, qty=5, unit_cost=1000)
    invoice = sell(db, user, warehouse, widget, qty=2, unit_price=3000)
    reversal = void_sales_invoice(db, invoice.id, reason="اشتباه", user=user)

    with pytest.raises(HTTPException) as exc:
        void_journal_entry(db, reversal.id, reason="باز هم", user=user)
    assert exc.value.status_code == 409


def test_void_reason_is_required(db):
    """سند باطلِ بی‌دلیل، یک سؤال بی‌جواب در دفتر است."""
    from pydantic import ValidationError

    from app.schemas.voiding import VoidIn

    for bad in ("", "  ", "a"):
        with pytest.raises(ValidationError):
            VoidIn(reason=bad)

    assert VoidIn(reason="  ثبت اشتباه  ").reason == "ثبت اشتباه"


def test_average_cost_replay_does_not_depend_on_primary_key_order(db, user, warehouse, widget):
    """بازپخش باید به ترتیب *ثبت* تکیه کند، نه به ترتیب کلید اصلی.

    این تست بعد از یک شکست واقعی نوشته شد: بازپخش با `ORDER BY id` مرتب می‌شد،
    شناسه UUID تصادفی است، و نتیجه هر بار می‌توانست فرق کند. در اجرای تنهای پرونده
    سبز بود و در اجرای کامل قرمز — که بدترین نوع تست است.

    برای اینکه سنجش قطعی باشد و نه شانسی، شناسه‌ها **دستی** طوری داده می‌شوند که
    ترتیبشان دقیقاً برعکس ترتیب ثبت باشد. با ORDER BY id نتیجه ۱۳۳۳ می‌شود و با
    ORDER BY seq، ۱۵۰۰ — پس جهش هر بار گرفته می‌شود، نه پنج بار از شش بار.

    خرید ۱۰@۱۰۰۰ ← فروش ۵ ← خرید ۵@۲۰۰۰ باید ۱۵۰۰ بدهد:
    فروش میانگین را عوض نمی‌کند، پس (۵×۱۰۰۰ + ۵×۲۰۰۰) ÷ ۱۰ = ۱۵۰۰.
    """
    import uuid as _uuid

    from app.models.inventory import StockLedger
    from app.services.voiding import recompute_average_cost

    # شناسه‌ها نزولی، ترتیب ثبت صعودی — پس ORDER BY id دقیقاً برعکس واقعیت است.
    ids = sorted((_uuid.uuid4() for _ in range(3)), reverse=True)
    plan = [(ids[0], 10, 1000), (ids[1], -5, 1000), (ids[2], 5, 2000)]

    for row_id, qty, cost in plan:
        db.add(
            StockLedger(
                id=row_id,
                item_id=widget.id,
                warehouse_id=warehouse.id,
                qty=qty,
                unit_cost=cost,
                entry_date=TODAY,
                source_type="purchase_invoice" if qty > 0 else "sales_invoice",
                source_id=_uuid.uuid4(),
            )
        )
        db.flush()  # هر ردیف جدا، تا seq ترتیب واقعی ثبت را بگیرد

    recompute_average_cost(db, widget)
    assert Decimal(widget.average_cost) == 1500, (
        "بازپخش به ترتیب کلید اصلی تکیه کرده، نه ترتیب ثبت — "
        f"نتیجه {widget.average_cost} به‌جای ۱۵۰۰"
    )
