"""پُرکردنِ `stock_ledger.source_id` در مهاجرتِ ۰۱۵۸ — روی دادهٔ واقعیِ پیش از اصلاح.

روی تولید **۱۱ حرکتِ تعدیل** وجود دارد که هر ۱۱ تا `source_id` تهی دارند، چون
`post_stock_adjustment` هیچ‌وقت آن را نمی‌نوشت. تا وقتی این ردیف‌ها به سندشان گره
نخورند، هیچ‌کدامشان ابطال‌پذیر نیستند و `valuation._VOIDABLE` هم به آن‌ها نمی‌خورد.

این فایل **خودِ SQLِ مهاجرت** را اجرا می‌کند، نه رونوشتش: اگر آن SQL عوض شود و
خراب شود، این تست‌ها می‌شکنند.

قیدِ سختِ تطبیق: **هیچ حرکتی نباید به سندِ اشتباه بخورد.** کلیدِ (کالا، انبار،
تاریخ، مقدار) روی تولید یکتاست، ولی دو تعدیلِ کاملاً یکسانِ هم‌روز چیزی است که
هر روز می‌تواند ثبت شود — و آن‌جاست که تطبیقِ ساده دو حرکت را به یک سند می‌بندد
و سندِ دیگر برای همیشه بی‌حرکت می‌ماند.
"""
import importlib.util
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa

from app.models.inventory import StockLedger
from app.schemas.inventory import StockAdjustmentIn
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.services.inventory import post_purchase_invoice, post_stock_adjustment
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 6, 1)

_MIGRATION = (
    Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0158_stock_adjustment_void.py"
)


def _migration_sql():
    """SQLِ backfill از خودِ فایلِ مهاجرت — تا تست رونوشتِ کهنه را نسنجد."""
    spec = importlib.util.spec_from_file_location("_m0158", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._BACKFILL, module._LEFTOVER


def _stocked(db, user, qty=50):
    warehouse = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY - timedelta(days=1),
            warehouse_id=warehouse.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(1_000))],
        ),
        user,
    )
    return item, warehouse


def _adjust(db, user, item, warehouse, qty_diff, *, on=TODAY):
    return post_stock_adjustment(
        db,
        StockAdjustmentIn(
            item_id=item.id, warehouse_id=warehouse.id,
            qty_diff=Decimal(qty_diff), reason="آزمون", adjustment_date=on,
        ),
        user,
    )


def _make_it_look_pre_0158(db, adjustments):
    """همان شکلی که دادهٔ تولید دارد: حرکت هست، گره نیست."""
    ids = [a.id for a in adjustments]
    db.query(StockLedger).filter(
        StockLedger.source_type == "adjustment", StockLedger.source_id.in_(ids)
    ).update({StockLedger.source_id: None}, synchronize_session=False)
    db.flush()


def _run_backfill(db) -> tuple[int, int]:
    backfill, leftover = _migration_sql()
    matched = db.execute(sa.text(backfill)).rowcount
    remaining = db.execute(sa.text(leftover)).scalar_one()
    return matched, remaining


def _source_of(db, adjustment):
    return [
        row.source_id
        for row in db.query(StockLedger)
        .filter(StockLedger.source_type == "adjustment")
        .filter(StockLedger.item_id == adjustment.item_id)
        .filter(StockLedger.qty == adjustment.qty_diff)
        .filter(StockLedger.entry_date == adjustment.adjustment_date)
        .all()
    ]


def test_an_orphan_move_finds_its_adjustment(db, user):
    """حالتِ سرراست — همان چیزی که هر ۱۱ ردیفِ تولید هستند."""
    item, warehouse = _stocked(db, user)
    adjustment = _adjust(db, user, item, warehouse, -4)
    _make_it_look_pre_0158(db, [adjustment])

    matched, remaining = _run_backfill(db)
    assert matched >= 1
    assert remaining == 0, "*** حرکتی بی‌جفت ماند ***"
    assert _source_of(db, adjustment) == [adjustment.id]


def test_two_identical_adjustments_on_one_day_get_one_move_each(db, user):
    """**تلهٔ اصلی.** دو تعدیلِ کاملاً یکسانِ هم‌روز.

    تطبیقِ ساده روی (کالا، انبار، تاریخ، مقدار) هر دو حرکت را به هر دو سند
    می‌بندد — یکی دو حرکت می‌گیرد و دیگری هیچ. `row_number()` روی همان کلید
    آن‌ها را به ترتیبِ ثبت جفت می‌کند.
    """
    item, warehouse = _stocked(db, user)
    first = _adjust(db, user, item, warehouse, -3)
    second = _adjust(db, user, item, warehouse, -3)
    assert first.id != second.id
    _make_it_look_pre_0158(db, [first, second])

    matched, remaining = _run_backfill(db)
    assert matched == 2
    assert remaining == 0

    owners = _source_of(db, first)
    assert sorted(map(str, owners)) == sorted([str(first.id), str(second.id)]), (
        "*** دو حرکت به یک سند بسته شدند ***"
    )


def test_adjustments_that_differ_are_never_crossed(db, user):
    """دو تعدیلِ متفاوت نباید حرکتِ همدیگر را بگیرند."""
    item, warehouse = _stocked(db, user)
    smaller = _adjust(db, user, item, warehouse, -2)
    larger = _adjust(db, user, item, warehouse, -7)
    _make_it_look_pre_0158(db, [smaller, larger])

    _run_backfill(db)

    assert _source_of(db, smaller) == [smaller.id]
    assert _source_of(db, larger) == [larger.id]


def test_the_backfill_leaves_other_sources_alone(db, user):
    """فقط `source_type='adjustment'` — حرکتِ فاکتور و رسید دست‌نخورده می‌مانند."""
    item, warehouse = _stocked(db, user)
    adjustment = _adjust(db, user, item, warehouse, -1)
    _make_it_look_pre_0158(db, [adjustment])

    before = {
        row.id: row.source_id
        for row in db.query(StockLedger).filter(StockLedger.source_type != "adjustment").all()
    }
    _run_backfill(db)
    after = {
        row.id: row.source_id
        for row in db.query(StockLedger).filter(StockLedger.source_type != "adjustment").all()
    }
    assert before == after


def test_running_the_backfill_twice_changes_nothing(db, user):
    """مهاجرت باید بی‌خطر باشد اگر دوباره اجرا شود — شرطِ `source_id IS NULL` همین است."""
    item, warehouse = _stocked(db, user)
    adjustment = _adjust(db, user, item, warehouse, -5)
    _make_it_look_pre_0158(db, [adjustment])

    _run_backfill(db)
    owners_once = _source_of(db, adjustment)
    matched_again, remaining = _run_backfill(db)

    assert matched_again == 0, "*** اجرای دوم دوباره نوشت ***"
    assert remaining == 0
    assert _source_of(db, adjustment) == owners_once
