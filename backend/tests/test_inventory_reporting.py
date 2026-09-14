"""گزارش‌های انبار: ابعاد، تفکیکِ مجوزِ بها، و ردیابیِ سریال.

سه شکافِ فصلِ «گزارش‌های تأمین‌کنندگان و انبار»:

۱. **ردیابیِ سریال یک بن‌بست بود.** سریال به بچِ ورودش وصل بود و بس؛ فروش
   لمسش نمی‌کرد. با پروب اثبات شد: فروشِ ۲ عدد از ۳ عددِ سریالی هیچ سریالی را
   عوض نکرد، و `stock_batch_serials` ستونی برای سند نداشت.
۲. **مجوز در هر دو جهت غلط بود.** هر گزارشِ انبار `accounting.view` می‌خواست:
   انباردار موجودیِ انبارش را نمی‌دید، و هر که می‌دید بها را هم می‌دید.
۳. **گزارش فقط کالا و انبار را می‌شناخت** — نه تأمین‌کننده، نه مشتری، نه هدف.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.advanced_inventory import SerialEvent, StockBatch, StockBatchSerial
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.services import inventory_analytics, serials
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from tests.factories import main_warehouse, make_contact, make_item

TODAY = date(2026, 3, 15)
SCOPE = {"date_from": date(2026, 3, 1), "date_to": date(2026, 3, 31)}


def _buy(db, user, item, qty, contact=None, cost=Decimal(1000)):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            contact_id=contact.id if contact else None,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=cost)],
        ),
        user,
    )


def _sell(db, user, item, qty, contact=None):
    return post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            contact_id=contact.id if contact else None,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_price=Decimal(5000))],
        ),
        user,
    )


def _row_for(report, key):
    return next((r for r in report["rows"] if r["key"] == key), None)


# --- ابعاد -------------------------------------------------------------------


def test_supplier_dimension_sums_what_came_from_each_supplier(db, user):
    supplier = make_contact(db, name="تأمین‌کننده‌ی آزمون")
    item = make_item(db)
    _buy(db, user, item, 40, contact=supplier)
    db.flush()

    report = inventory_analytics.breakdown(db, dimension="supplier", **SCOPE)
    row = _row_for(report, str(supplier.id))
    assert row is not None
    assert row["label"] == "تأمین‌کننده‌ی آزمون"
    assert row["in_qty"] == Decimal(40)
    assert row["net_qty"] == Decimal(40)


def test_customer_dimension_sums_what_went_to_each_customer(db, user):
    customer = make_contact(db, name="مشتریِ آزمون")
    item = make_item(db)
    _buy(db, user, item, 50)
    _sell(db, user, item, 12, contact=customer)
    db.flush()

    report = inventory_analytics.breakdown(db, dimension="customer", **SCOPE)
    row = _row_for(report, str(customer.id))
    assert row is not None
    assert row["out_qty"] == Decimal(12)
    assert row["net_qty"] == Decimal(-12)


def test_a_supplier_never_appears_in_the_customer_view(db, user):
    """خرید در بُعدِ مشتری جایی ندارد — و برعکس."""
    supplier = make_contact(db, name="فقط تأمین‌کننده")
    item = make_item(db)
    _buy(db, user, item, 7, contact=supplier)
    db.flush()

    assert _row_for(inventory_analytics.breakdown(db, dimension="customer", **SCOPE), str(supplier.id)) is None


def test_purpose_dimension_separates_sale_from_purchase(db, user):
    item = make_item(db)
    _buy(db, user, item, 30)
    _sell(db, user, item, 4)
    db.flush()

    report = inventory_analytics.breakdown(db, dimension="purpose", **SCOPE)
    assert _row_for(report, "purchase_invoice")["in_qty"] == Decimal(30)
    #: خروجِ فروش در دفترِ موجودی `warehouse_issue` است نه `sales_invoice` —
    #: کوبیتا برای هر فروش سندِ خروجِ انبار می‌زند و **همان** حرکت را می‌سازد.
    #: بُعد از منشأِ واقعیِ حرکت می‌آید، نه از نامِ سندِ تجاری.
    assert _row_for(report, "warehouse_issue")["out_qty"] == Decimal(4)


def test_breakdown_agrees_with_the_kardex(db, user):
    """عددها از همان موتور می‌آیند، پس باید بخوانند — وگرنه دو تعریف داریم."""
    from app.services.reports import get_kardex

    item = make_item(db)
    _buy(db, user, item, 25)
    _sell(db, user, item, 6)
    db.flush()

    kardex = get_kardex(db, item.id, None, SCOPE["date_from"], SCOPE["date_to"])
    report = inventory_analytics.breakdown(db, dimension="purpose", **SCOPE)
    in_qty = sum((r["in_qty"] for r in report["rows"]), Decimal(0))
    out_qty = sum((r["out_qty"] for r in report["rows"]), Decimal(0))
    assert in_qty == Decimal(kardex["total_in"])
    assert out_qty == Decimal(kardex["total_out"])


def test_unknown_dimension_is_refused(db):
    with pytest.raises(ValueError):
        inventory_analytics.breakdown(db, dimension="warehouse_keeper_mood", **SCOPE)


# --- پوشاندنِ مبلغ ------------------------------------------------------------


def test_money_is_nulled_not_zeroed_for_the_unauthorised(db):
    """`None` است نه صفر — صفر عددِ واقعی است، «اجازه نداری» نیست."""
    from app.routers.reports import _redact_money

    payload = {"in_qty": Decimal(5), "in_value": Decimal(5000), "rows": [{"unit_cost": Decimal(7)}]}
    assert _redact_money(payload, True) == payload

    hidden = _redact_money(payload, False)
    assert hidden["in_qty"] == Decimal(5)  # مقدار دست‌نخورده
    assert hidden["in_value"] is None
    assert hidden["rows"][0]["unit_cost"] is None


def test_every_redacted_field_is_nullable_in_the_schema(db):
    """اگر نامی در فهرستِ پوشاندن باشد و در اسکیما تهی‌پذیر نباشد، پاسخ می‌شکند."""
    from app.routers.reports import _MONEY_FIELDS
    from app.schemas.reports import InventoryReportOut, InventoryRowOut, KardexLineOut, KardexReportOut

    for model in (InventoryRowOut, InventoryReportOut, KardexLineOut, KardexReportOut):
        for name, field in model.model_fields.items():
            if name in _MONEY_FIELDS:
                assert "None" in str(field.annotation), f"{model.__name__}.{name} تهی‌پذیر نیست"


# --- ردیابیِ سریال -----------------------------------------------------------


def _serial_rows(db, user, item, names, qty=None):
    _buy(db, user, item, qty or len(names))
    db.flush()
    batch = db.query(StockBatch).filter(StockBatch.item_id == item.id).first()
    rows = []
    for name in names:
        row = StockBatchSerial(batch_id=batch.id, serial=name)
        db.add(row)
        rows.append(row)
    db.flush()
    for row in rows:
        serials.record(
            db, row, event_type="receipt", source_type=batch.source_type,
            source_id=batch.source_id, entry_date=batch.received_date or TODAY, user=user,
        )
    db.flush()
    return batch, rows


def test_a_serial_remembers_where_it_came_from(db, user):
    item = make_item(db)
    _serial_rows(db, user, item, ["A-1"])

    found = serials.search(db, serial="A-1")
    assert len(found) == 1
    assert found[0]["in_stock"] is True
    assert [e["event_type"] for e in found[0]["events"]] == ["receipt"]
    assert found[0]["events"][0]["source_type"] == "purchase_invoice"


def test_assigning_to_a_sale_answers_who_bought_it(db, user):
    """گاردِ همان بن‌بست: «SN-1 به چه کسی فروخته شد؟» باید جواب داشته باشد."""
    customer = make_contact(db, name="خریدارِ سریال")
    item = make_item(db)
    _serial_rows(db, user, item, ["B-1", "B-2", "B-3"])
    invoice = _sell(db, user, item, 2, contact=customer)
    db.flush()

    serials.assign(
        db, serials=["B-1", "B-2"], item_id=item.id, source_type="sales_invoice",
        source_id=invoice.id, entry_date=TODAY, event_type="issue", user=user,
    )
    db.flush()

    sold = {s["serial"]: s for s in serials.search(db, item_id=item.id)}
    assert sold["B-1"]["in_stock"] is False
    assert sold["B-3"]["in_stock"] is True
    last = sold["B-1"]["events"][-1]
    assert last["event_type"] == "issue"
    assert last["counterparty"] == "خریدارِ سریال"
    assert last["source_number"] == invoice.number


def test_current_position_is_derived_not_stored(db, user):
    """هیچ ستونی موقعیت را نگه نمی‌دارد — تاریخچه کامل می‌ماند."""
    item = make_item(db)
    _, rows = _serial_rows(db, user, item, ["C-1"])
    invoice = _sell(db, user, item, 1)
    db.flush()
    serials.assign(
        db, serials=["C-1"], item_id=item.id, source_type="sales_invoice",
        source_id=invoice.id, entry_date=TODAY, event_type="issue", user=user,
    )
    db.flush()
    db.refresh(rows[0])

    assert len(rows[0].events) == 2  # ورود و خروج، هر دو باقی
    assert serials.current_state(rows[0])["in_stock"] is False
    assert "current_warehouse_id" not in {c.name for c in StockBatchSerial.__table__.columns}


def test_the_same_serial_cannot_leave_twice(db, user):
    item = make_item(db)
    _serial_rows(db, user, item, ["D-1"], qty=5)
    first = _sell(db, user, item, 1)
    second = _sell(db, user, item, 1)
    db.flush()
    serials.assign(
        db, serials=["D-1"], item_id=item.id, source_type="sales_invoice",
        source_id=first.id, entry_date=TODAY, event_type="issue", user=user,
    )
    db.flush()

    with pytest.raises(HTTPException) as err:
        serials.assign(
            db, serials=["D-1"], item_id=item.id, source_type="sales_invoice",
            source_id=second.id, entry_date=TODAY, event_type="issue", user=user,
        )
    assert err.value.status_code == 400


def test_reassigning_the_same_document_is_a_replay(db, user):
    """تلاشِ دوباره‌ی شبکه رویدادِ دوم نمی‌سازد — یکتاسازی از شکلِ داده."""
    item = make_item(db)
    _serial_rows(db, user, item, ["E-1"], qty=3)
    invoice = _sell(db, user, item, 1)
    db.flush()
    args = dict(
        serials=["E-1"], item_id=item.id, source_type="sales_invoice",
        source_id=invoice.id, entry_date=TODAY, event_type="issue", user=user,
    )
    first = serials.assign(db, **args)
    db.flush()
    again = serials.assign(db, **args)
    db.flush()

    assert first["created"] == 1
    assert again["created"] == 0 and again["replayed"] == 1
    assert db.query(SerialEvent).filter(SerialEvent.source_id == invoice.id).count() == 1


def test_an_unknown_serial_is_never_invented(db, user):
    """تایپ نباید یک قلمِ جعلی بسازد."""
    item = make_item(db)
    _serial_rows(db, user, item, ["F-1"], qty=3)
    invoice = _sell(db, user, item, 1)
    db.flush()
    with pytest.raises(HTTPException) as err:
        serials.assign(
            db, serials=["F-9"], item_id=item.id, source_type="sales_invoice",
            source_id=invoice.id, entry_date=TODAY, event_type="issue", user=user,
        )
    assert err.value.status_code == 400
    assert db.query(StockBatchSerial).filter(StockBatchSerial.serial == "F-9").count() == 0


def test_search_filters_by_document_type_but_returns_the_whole_history(db, user):
    """فیلتر روی رویداد است، تاریخچه کامل — وگرنه بن‌بستِ تازه ساخته‌ایم."""
    item = make_item(db)
    _serial_rows(db, user, item, ["G-1"], qty=3)
    invoice = _sell(db, user, item, 1)
    db.flush()
    serials.assign(
        db, serials=["G-1"], item_id=item.id, source_type="sales_invoice",
        source_id=invoice.id, entry_date=TODAY, event_type="issue", user=user,
    )
    db.flush()

    found = serials.search(db, source_type="sales_invoice", item_id=item.id)
    assert [s["serial"] for s in found] == ["G-1"]
    assert [e["event_type"] for e in found[0]["events"]] == ["receipt", "issue"]
