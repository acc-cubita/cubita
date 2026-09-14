"""انبارگردانی: شمارشِ کور، و عکسِ سیستمی در لحظه‌ی شمارش.

دو باگ که هر دو با پروب اثبات شدند و هر دو موجودیِ واقعی را خراب می‌کردند:

۱. **حرکتِ وسطِ شمارش دو بار شمرده می‌شد.** عکسِ سیستمی سرِ بازکردنِ جلسه گرفته
   می‌شد و شمارش ساعت‌ها بعد انجام می‌شد؛ فروشی که بینشان می‌افتاد یک‌بار خودش و
   یک‌بار داخلِ اختلاف از موجودی کم می‌شد.

۲. **«شمرده نشده» با «صفر شمردم» یکی بود.** `counted_qty` با `system_qty` پر
   می‌شد، پس شمارنده عددِ سیستم را از پیش نوشته می‌دید — و هیچ راهی نبود بفهمیم
   چه‌قدر از جلسه واقعاً شمرده شده.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.inventory import StockLedger
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.schemas.stock_count import CountLineUpdateIn
from app.services import stock_taking
from app.services.inventory import get_stock_qty, post_purchase_invoice, post_sales_invoice
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 3, 15)


def _stock_in(db, user, item, qty, cost=Decimal(1000)):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=cost)],
        ),
        user,
    )


def _sell(db, user, item, qty):
    return post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_price=Decimal(5000))],
        ),
        user,
    )


def _open(db, user, **kw):
    return stock_taking.create_session(db, main_warehouse(db).id, TODAY, user, **kw)


def _line_for(session, item):
    return next(line for line in session.lines if line.item_id == item.id)


def _count(db, user, session, line, qty):
    return stock_taking.set_counts(
        db, session.id, [CountLineUpdateIn(line_id=line.id, counted_qty=qty)], user
    )


# --- باگِ اصلی: حرکتِ وسطِ شمارش -------------------------------------------


def test_sale_during_the_count_is_not_counted_twice(db, user):
    """گاردِ همان پروب.

        موجودی ۱۰۰ → جلسه باز شد → ۱۰ تا فروخته شد → شمارنده ۹۰ می‌شمارد

    اختلاف باید صفر باشد، چون شمارش با واقعیتِ همان لحظه می‌خواند.
    """
    item = make_item(db)
    _stock_in(db, user, item, 100)
    db.flush()

    session = _open(db, user)
    line = _line_for(session, item)
    assert Decimal(line.system_qty) == Decimal(100)

    _sell(db, user, item, 10)
    db.flush()
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(90)

    _count(db, user, session, line, Decimal(90))
    #: عکسِ سیستمی تازه شده — همان چیزی که شمارنده دید.
    assert Decimal(line.system_qty) == Decimal(90)

    stock_taking.post_session(db, session.id, user)
    db.flush()

    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(90)
    assert not [
        m
        for m in db.query(StockLedger).filter(StockLedger.item_id == item.id).all()
        if m.source_type == "stock_count"
    ], "حرکتِ تعدیلی ساخته شد در حالی که اختلافی نبود"


def test_a_real_shortage_still_adjusts(db, user):
    """گاردِ متقابل: اصلاح نباید کسریِ واقعی را هم خفه کند."""
    item = make_item(db)
    _stock_in(db, user, item, 100)
    db.flush()

    session = _open(db, user)
    line = _line_for(session, item)
    _count(db, user, session, line, Decimal(95))  # پنج تا واقعاً گم شده
    stock_taking.post_session(db, session.id, user)
    db.flush()

    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(95)
    move = next(
        m
        for m in db.query(StockLedger).filter(StockLedger.item_id == item.id).all()
        if m.source_type == "stock_count"
    )
    assert Decimal(move.qty) == Decimal(-5)


def test_drift_report_names_what_moved_after_the_count(db, user):
    """حرکتِ پس از شمارش گزارش می‌شود — گزارش، نه گارد."""
    item = make_item(db)
    _stock_in(db, user, item, 100)
    db.flush()

    session = _open(db, user)
    line = _line_for(session, item)
    _count(db, user, session, line, Decimal(100))
    assert stock_taking.moved_since_count(db, session) == []

    _sell(db, user, item, 4)
    db.flush()
    drift = stock_taking.moved_since_count(db, session)
    assert len(drift) == 1
    assert drift[0]["system_qty_at_count"] == Decimal(100)
    assert drift[0]["system_qty_now"] == Decimal(96)


# --- شمارشِ کور -------------------------------------------------------------


def test_new_session_leaves_counts_blank(db, user):
    """عدد از شمارنده می‌آید، نه از سیستم — وگرنه شمارش شاهدِ مستقلی نیست."""
    item = make_item(db)
    _stock_in(db, user, item, 100)
    db.flush()

    session = _open(db, user)
    line = _line_for(session, item)
    assert line.counted_qty is None
    assert line.counted_at is None


def test_uncounted_lines_never_become_a_shortage(db, user):
    """خطرناک‌ترین حالتِ فصل: نیمه‌کاره ثبت‌کردن نباید انبار را خالی کند."""
    counted, untouched = make_item(db), make_item(db)
    _stock_in(db, user, counted, 40)
    _stock_in(db, user, untouched, 70)
    db.flush()

    session = _open(db, user)
    _count(db, user, session, _line_for(session, counted), Decimal(38))
    stock_taking.post_session(db, session.id, user)
    db.flush()

    assert get_stock_qty(db, counted.id, main_warehouse(db).id) == Decimal(38)
    assert get_stock_qty(db, untouched.id, main_warehouse(db).id) == Decimal(70)


def test_explicit_zero_is_a_real_shortage(db, user):
    """«شمردم، هیچ نبود» با «نشمردم» یکی نیست."""
    item = make_item(db)
    _stock_in(db, user, item, 25)
    db.flush()

    session = _open(db, user)
    _count(db, user, session, _line_for(session, item), Decimal(0))
    stock_taking.post_session(db, session.id, user)
    db.flush()
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(0)


def test_count_can_be_taken_back(db, user):
    item = make_item(db)
    _stock_in(db, user, item, 10)
    db.flush()
    session = _open(db, user)
    line = _line_for(session, item)

    _count(db, user, session, line, Decimal(9))
    assert line.counted_qty is not None
    _count(db, user, session, line, None)
    assert line.counted_qty is None and line.counted_at is None


def test_posting_a_session_with_no_counts_is_refused(db, user):
    item = make_item(db)
    _stock_in(db, user, item, 10)
    db.flush()
    session = _open(db, user)
    with pytest.raises(HTTPException) as err:
        stock_taking.post_session(db, session.id, user)
    assert err.value.status_code == 400


def test_coverage_is_visible(db, user):
    """«چه‌قدرش را واقعاً شمردیم؟» باید جواب داشته باشد."""
    a, b = make_item(db), make_item(db)
    _stock_in(db, user, a, 5)
    _stock_in(db, user, b, 5)
    db.flush()

    session = _open(db, user)
    _count(db, user, session, _line_for(session, a), Decimal(5))
    data = stock_taking.serialize_session(session)
    assert data["counted_line_count"] == 1
    assert data["line_count"] >= 2
    assert next(l for l in data["lines"] if l["item_id"] == b.id)["variance"] is None


# --- دامنه و برگه‌ی شمارش ----------------------------------------------------


def test_scope_defaults_to_items_seen_in_this_warehouse(db, user):
    """کاتالوگِ بزرگ نباید هر بار هزاران ردیفِ بی‌ربط بسازد."""
    stocked, never = make_item(db), make_item(db)
    _stock_in(db, user, stocked, 3)
    db.flush()

    session = _open(db, user)
    ids = {line.item_id for line in session.lines}
    assert stocked.id in ids
    assert never.id not in ids


def test_scope_can_be_a_handful_of_items(db, user):
    """شمارشِ چرخه‌ای: فقط چند قلمِ انتخاب‌شده."""
    a, b = make_item(db), make_item(db)
    _stock_in(db, user, a, 3)
    _stock_in(db, user, b, 4)
    db.flush()

    session = _open(db, user, item_ids=[a.id])
    assert {line.item_id for line in session.lines} == {a.id}


def test_count_tags_never_show_the_expected_quantity(db, user):
    """برگه‌ی شمارش کور است — قلبِ این فصل."""
    item = make_item(db)
    _stock_in(db, user, item, 123)
    db.flush()

    session = _open(db, user)
    projection = stock_taking.count_tag_projection(db, session)

    assert projection["session_number"] == session.number
    tag = next(t for t in projection["lines"] if t["sku"] == item.sku)
    assert tag["tag_no"] >= 1
    assert "system_qty" not in tag and "counted_qty" not in tag
    assert "123" not in str(projection["lines"])


def test_tag_numbers_are_stable_across_reprints(db, user):
    """چاپِ دوباره هویتِ تازه نمی‌سازد."""
    item = make_item(db)
    _stock_in(db, user, item, 5)
    db.flush()
    session = _open(db, user)

    first = stock_taking.count_tag_projection(db, session)["lines"]
    second = stock_taking.count_tag_projection(db, session)["lines"]
    assert [t["tag_no"] for t in first] == [t["tag_no"] for t in second]
    assert [t["sku"] for t in first] == [t["sku"] for t in second]
