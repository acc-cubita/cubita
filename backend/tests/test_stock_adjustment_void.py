"""تعدیلِ انبار — سندی که کارش اصلاحِ خطاست و تا امروز خودش اصلاح نمی‌شد.

**چه کم بود.** `stock_adjustments` تنها سندِ انباری بود که `VoidableMixin` نداشت.
تنها راهِ اصلاحِ یک تعدیلِ اشتباه، ثبتِ یک تعدیلِ معکوسِ دوم بود: عدد درست
درمی‌آمد، ولی کاردکسِ کالا **دو تعدیلِ ظاهراً واقعی** نشان می‌داد و هیچ‌جا نمی‌گفت
دومی اشتباهِ اولی را می‌پوشاند. روی تولید ۱۱ ردیفِ چنین سندی وجود داشت.

و یک نقصِ دوم که موقعِ ساختِ ابطال پیدا شد: `post_stock_adjustment` روی حرکتِ
انبار `source_id` نمی‌نوشت — **تنها سندِ انباری که این کار را نمی‌کرد**. بی آن،
ابطال حرکتِ خودش را هم پیدا نمی‌کرد و `valuation._VOIDABLE` به هیچ ردیفی نمی‌خورد.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import JournalEntry, JournalLine
from app.models.advanced_inventory import StockBatch
from app.schemas.inventory import StockAdjustmentIn
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.models.inventory import StockLedger
from app.services import valuation
from app.services.inventory import get_stock_qty, post_purchase_invoice, post_stock_adjustment
from app.services.voiding import void_stock_adjustment
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 6, 1)


def _stocked(db, user, qty=10, unit_cost=1_000):
    """کالایی با موجودیِ واقعی — تعدیلِ کسری بی موجودی رد می‌شود."""
    warehouse = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY - timedelta(days=1),
            warehouse_id=warehouse.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost))],
        ),
        user,
    )
    return item, warehouse


def _adjust(db, user, item, warehouse, qty_diff, *, on=TODAY, reason="آزمون"):
    return post_stock_adjustment(
        db,
        StockAdjustmentIn(
            item_id=item.id, warehouse_id=warehouse.id,
            qty_diff=Decimal(qty_diff), reason=reason, adjustment_date=on,
        ),
        user,
    )


# ───────────────── نقصِ دوم: حرکت باید به سندش گره بخورد ─────────────────


def test_the_ledger_move_points_back_at_its_adjustment(db, user):
    """بدونِ این، ابطال حتی نمی‌داند کدام حرکت مالِ اوست."""
    item, warehouse = _stocked(db, user)
    adjustment = _adjust(db, user, item, warehouse, -2)

    move = (
        db.query(StockLedger)
        .filter(StockLedger.source_type == "adjustment", StockLedger.source_id == adjustment.id)
        .one_or_none()
    )
    assert move is not None, "*** حرکتِ تعدیل دوباره بی‌شناسه ثبت شد ***"
    assert Decimal(move.qty) == Decimal(-2)


def test_the_registry_knows_adjustments_are_voidable(db, user):
    """`_VOIDABLE` جایی است که بازپخشِ میانگین سندِ باطل را کنار می‌گذارد.

    کامنتِ خودِ آن فهرست می‌گوید سندی که آن‌جا نباشد «بی‌صدا میانگین را منحرف
    می‌کند و هیچ ترازی لو نمی‌دهد» — چون هر دو سند متوازن‌اند.
    """
    item, warehouse = _stocked(db, user)
    adjustment = _adjust(db, user, item, warehouse, -1)
    void_stock_adjustment(db, adjustment.id, reason="اشتباه بود", user=user)

    assert ("adjustment", adjustment.id) in valuation.voided_sources(db)


# ───────────────────────── خودِ ابطال ─────────────────────────


def test_voiding_a_shortage_puts_the_stock_back(db, user):
    item, warehouse = _stocked(db, user, qty=10)
    before = get_stock_qty(db, item.id, warehouse.id)
    adjustment = _adjust(db, user, item, warehouse, -4)
    assert get_stock_qty(db, item.id, warehouse.id) == before - 4

    void_stock_adjustment(db, adjustment.id, reason="کسری اشتباه ثبت شده بود", user=user)
    assert get_stock_qty(db, item.id, warehouse.id) == before


def test_voiding_reverses_the_journal_entry(db, user):
    """سندِ حسابداری معکوس می‌شود، نه پاک — و به سندِ اصلی گره می‌خورد."""
    item, warehouse = _stocked(db, user)
    adjustment = _adjust(db, user, item, warehouse, -3)
    original_id = adjustment.journal_entry_id
    assert original_id is not None

    reversal = void_stock_adjustment(db, adjustment.id, reason="اشتباه بود", user=user)
    assert reversal is not None
    assert reversal.reverses_entry_id == original_id

    original = db.get(JournalEntry, original_id)
    assert original is not None, "*** سندِ اصلی پاک شد — ابطال یعنی معکوس، نه حذف ***"

    def _sum(entry_id):
        rows = db.query(JournalLine).filter(JournalLine.entry_id == entry_id).all()
        return sum(Decimal(r.debit) for r in rows), sum(Decimal(r.credit) for r in rows)

    debit_a, credit_a = _sum(original_id)
    debit_b, credit_b = _sum(reversal.id)
    assert debit_a == credit_b and credit_a == debit_b


def test_the_adjustment_keeps_its_row_and_gains_a_reason(db, user):
    item, warehouse = _stocked(db, user)
    adjustment = _adjust(db, user, item, warehouse, -1)
    void_stock_adjustment(db, adjustment.id, reason="دوبار ثبت شده بود", user=user)

    assert adjustment.is_voided
    assert adjustment.void_reason == "دوبار ثبت شده بود"
    assert adjustment.voided_by_id == user.id


def test_voiding_twice_is_refused(db, user):
    item, warehouse = _stocked(db, user)
    adjustment = _adjust(db, user, item, warehouse, -1)
    void_stock_adjustment(db, adjustment.id, reason="اشتباه بود", user=user)

    with pytest.raises(HTTPException) as err:
        void_stock_adjustment(db, adjustment.id, reason="دوباره", user=user)
    assert err.value.status_code == 409


def test_an_adjustment_without_a_journal_entry_still_voids(db, user):
    """تعدیلِ کالایی که بهایش صفر است سندِ حسابداری ندارد — و این درست است.

    مسیرِ مشترکِ `_apply_void` چنین سندی را ۴۰۹ می‌کند («سند حسابداری متناظر
    ندارد»)؛ برای همین تعدیل مسیرِ خودش را دارد. حرکتِ انبار باید برگردد حتی
    وقتی هیچ ریالی جابه‌جا نشده.
    """
    warehouse = main_warehouse(db)
    item = make_item(db, average_cost=0)
    adjustment = _adjust(db, user, item, warehouse, 5)
    assert adjustment.journal_entry_id is None
    assert get_stock_qty(db, item.id, warehouse.id) == 5

    assert void_stock_adjustment(db, adjustment.id, reason="اشتباه بود", user=user) is None
    assert get_stock_qty(db, item.id, warehouse.id) == 0


def test_voiding_a_surplus_that_was_already_sold_is_refused(db, user):
    """گاردِ موجودی: ابطالی که موجودی را منفی کند نباید بگذرد.

    تعدیلِ *اضافی* موجودی ساخته؛ اگر آن موجودی رفته باشد، برداشتنش انبار را
    منفی می‌کند — همان چیزی که هیچ گزارشی بعداً توضیحش نمی‌دهد.
    """
    warehouse = main_warehouse(db)
    item = make_item(db, average_cost=1_000)
    adjustment = _adjust(db, user, item, warehouse, 6)
    _adjust(db, user, item, warehouse, -6, reason="مصرف")
    assert get_stock_qty(db, item.id, warehouse.id) == 0

    with pytest.raises(HTTPException) as err:
        void_stock_adjustment(db, adjustment.id, reason="اشتباه بود", user=user)
    assert err.value.status_code == 409


def test_voiding_a_batch_adjustment_restores_the_batch(db, user):
    """کسریِ بار، `stock_batches.qty` را کم کرده؛ ابطال باید برگرداندش.

    بی این، باقی‌مانده‌ی آن بار **برای همیشه** کم می‌ماند — و هیچ گزارشی نمی‌گوید
    چرا، چون سندِ کسری دیگر باطل است.
    """
    item, warehouse = _stocked(db, user, qty=10)
    batch = StockBatch(
        item_id=item.id, warehouse_id=warehouse.id, batch_number="B-1",
        qty=Decimal(10), received_qty=Decimal(10), unit_cost=Decimal(1_000),
        received_date=TODAY, created_by_id=user.id,
    )
    db.add(batch)
    db.flush()

    adjustment = _adjust(db, user, item, warehouse, -3, reason="معیوبِ بار")
    adjustment.batch_id = batch.id
    batch.qty = Decimal(batch.qty) - Decimal(3)
    db.flush()

    void_stock_adjustment(db, adjustment.id, reason="بار سالم بود", user=user)
    assert Decimal(batch.qty) == Decimal(10), "*** باقی‌مانده‌ی بار برنگشت ***"


# ─────────────────── میانگین: چیزی که هیچ ترازی لو نمی‌دهد ───────────────────


def test_the_average_cost_forgets_a_voided_adjustment(db, user):
    """**هسته‌ی چرا `_VOIDABLE` لازم بود.**

    تعدیلِ اضافی با میانگین وارد می‌شود (`AVERAGE_INFLOWS`). اگر سندِ باطل از
    بازپخش کنار نرود، وزنش در میانگین می‌ماند و هیچ ترازی اعتراض نمی‌کند — هر
    دو سند متوازن‌اند.
    """
    warehouse = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY - timedelta(days=2),
            warehouse_id=warehouse.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(1_000))],
        ),
        user,
    )
    db.refresh(item)
    baseline = Decimal(item.average_cost)
    assert baseline == Decimal(1_000)

    adjustment = _adjust(db, user, item, warehouse, 5)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY + timedelta(days=1),
            warehouse_id=warehouse.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(5), unit_cost=Decimal(3_000))],
        ),
        user,
    )
    db.refresh(item)
    polluted = Decimal(item.average_cost)

    void_stock_adjustment(db, adjustment.id, reason="اضافی اشتباه بود", user=user)
    db.refresh(item)
    cleaned = Decimal(item.average_cost)

    #: بی تعدیل: (۱۰×۱۰۰۰ + ۵×۳۰۰۰) ÷ ۱۵ — با تعدیلِ ۵تاییِ میانگین، وزنِ خریدِ
    #: گران رقیق شده بود.
    assert cleaned != polluted, "*** میانگین هنوز سندِ باطل را می‌شمارد ***"
    expected = (Decimal(10) * Decimal(1_000) + Decimal(5) * Decimal(3_000)) / Decimal(15)
    assert abs(cleaned - expected) < Decimal("0.01")


# ─────────────────────────── اندپوینت ───────────────────────────


def test_the_endpoint_needs_a_written_reason(client, db, user):
    item, warehouse = _stocked(db, user)
    adjustment = _adjust(db, user, item, warehouse, -1)
    db.commit()

    response = client.post(f"/api/stock-adjustments/{adjustment.id}/void", json={"reason": " "})
    assert response.status_code == 422


def test_the_endpoint_voids_and_the_list_shows_it(client, db, user):
    """فهرست باید تعدیلِ باطل را از معتبر جدا نشان دهد — وگرنه ابطال فقط در دیتابیس است."""
    item, warehouse = _stocked(db, user)
    adjustment = _adjust(db, user, item, warehouse, -2)
    db.commit()

    response = client.post(
        f"/api/stock-adjustments/{adjustment.id}/void",
        json={"reason": "اشتباه ثبت شده بود"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["voided_at"] is not None

    rows = client.get("/api/stock-adjustments").json()["items"]
    row = next(r for r in rows if r["id"] == str(adjustment.id))
    assert row["voided_at"] is not None
    assert row["void_reason"] == "اشتباه ثبت شده بود"
