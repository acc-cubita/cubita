"""«مقدار حالا، بها بعداً» — و راهِ برگشتی که تا امروز نبود.

رسیدِ انبارِ مستقیم می‌تواند بی فی ثبت شود؛ این یک حالتِ خطا نیست، کالایی است که
خارج از سیستم تهیه شده و بهایش هنوز معلوم نیست. ولی چون رسید ویرایش نمی‌شود،
نتیجه‌اش این بود:

    ۱۵ واحد وارد انبار، فی = ۰، سند = هیچ، میانگین = ۰، **برای همیشه**

و وقتی آن ۱۵ واحد فروخته می‌شد، بهای فروش‌رفته صفر بود و سود به اندازه‌ی کلِ فروش
باد می‌کرد.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account, JournalEntry
from app.models.inventory import Item, StockLedger
from app.schemas.invoices import WarehouseReceiptIn, WarehouseReceiptLineIn
from app.services import chart_codes as cc
from app.services import production_pricing
from app.services.inventory import get_stock_qty
from app.services.warehouse_receipts import create_warehouse_receipt
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 3, 15)
SCOPE = {"date_from": date(2026, 3, 1), "date_to": date(2026, 3, 31)}


def _receipt(db, user, item, qty, *, unit_cost=Decimal(0), receipt_type="production", on=TODAY):
    return create_warehouse_receipt(
        db,
        None,
        WarehouseReceiptIn(
            receipt_date=on,
            warehouse_id=main_warehouse(db).id,
            receipt_type=receipt_type,
            lines=[WarehouseReceiptLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=unit_cost)],
        ),
        user,
    )


def _apply(db, user, prices, **over):
    scope = {"warehouse_id": main_warehouse(db).id, **SCOPE, **over}
    return production_pricing.apply_prices(db, prices=prices, user=user, **scope)


def _unpriced(db, **over):
    scope = {"warehouse_id": main_warehouse(db).id, **SCOPE, **over}
    return production_pricing.unpriced_outputs(db, **scope)


def _credit_of(db, entry, role) -> Decimal:
    account = db.query(Account).filter(Account.system_role == role).first()
    if account is None:
        return Decimal(0)
    return sum(
        (Decimal(l.credit) for l in entry.lines if l.account_id == account.id), Decimal(0)
    )


# --- کشف ---------------------------------------------------------------------


def test_unpriced_output_is_discoverable(db, user):
    item = make_item(db)
    receipt = _receipt(db, user, item, 15)
    db.flush()

    rows = [r for r in _unpriced(db) if r["item_id"] == item.id]
    assert len(rows) == 1
    assert rows[0]["qty"] == Decimal(15)
    assert [r["number"] for r in rows[0]["receipts"]] == [receipt.number]


def test_priced_output_is_not_listed(db, user):
    """چیزی که فی دارد در فهرستِ «بی‌فی» نمی‌آید."""
    item = make_item(db)
    _receipt(db, user, item, 15, unit_cost=Decimal(160_000))
    db.flush()
    assert not [r for r in _unpriced(db) if r["item_id"] == item.id]


def test_one_item_across_two_receipts_is_one_row(db, user):
    """گریدِ قیمت‌گذاری کالا‌محور است — یک فی برای یک کالا."""
    item = make_item(db)
    a = _receipt(db, user, item, 10)
    b = _receipt(db, user, item, 20, on=date(2026, 3, 20))
    db.flush()

    row = next(r for r in _unpriced(db) if r["item_id"] == item.id)
    assert row["qty"] == Decimal(30)
    assert sorted(r["number"] for r in row["receipts"]) == sorted([a.number, b.number])


def test_out_of_scope_is_not_listed(db, user):
    item = make_item(db)
    _receipt(db, user, item, 15, on=date(2026, 5, 2))
    db.flush()
    assert not [r for r in _unpriced(db) if r["item_id"] == item.id]


# --- اعمال -------------------------------------------------------------------


def test_apply_sets_cost_on_line_and_movement(db, user):
    """فی روی ردیف و روی **همان** حرکتِ انبار می‌نشیند."""
    item = make_item(db)
    receipt = _receipt(db, user, item, 15)
    db.flush()

    result = _apply(db, user, {item.id: Decimal(160_000)})
    assert result == {"receipts": 1, "lines": 1, "value": Decimal(2_400_000)}

    db.refresh(receipt)
    assert Decimal(receipt.lines[0].unit_cost) == Decimal(160_000)
    move = db.query(StockLedger).filter(StockLedger.source_id == receipt.id).one()
    assert Decimal(move.unit_cost) == Decimal(160_000)


def test_apply_creates_no_second_stock_movement(db, user):
    """گاردِ Double Movement: مقدار قبلاً وارد شده و دوباره وارد نمی‌شود."""
    item = make_item(db)
    _receipt(db, user, item, 15)
    db.flush()
    before = db.query(StockLedger).filter(StockLedger.item_id == item.id).count()

    _apply(db, user, {item.id: Decimal(160_000)})

    assert db.query(StockLedger).filter(StockLedger.item_id == item.id).count() == before
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(15)


def test_apply_posts_the_journal_that_never_happened(db, user):
    """رسیدِ بی‌فی سند نزده بود؛ حالا می‌زند — با بستانکارِ درستِ نوعِ خودش."""
    item = make_item(db)
    receipt = _receipt(db, user, item, 15)
    db.flush()
    assert receipt.journal_entry_id is None

    _apply(db, user, {item.id: Decimal(160_000)})
    db.refresh(receipt)

    entry = db.get(JournalEntry, receipt.journal_entry_id)
    assert entry is not None
    assert entry.entry_date == TODAY  # تاریخِ رسید، نه امروز
    assert sum(Decimal(l.debit) for l in entry.lines) == sum(Decimal(l.credit) for l in entry.lines)
    assert _credit_of(db, entry, cc.WORK_IN_PROCESS) == Decimal(2_400_000)
    assert _credit_of(db, entry, cc.CASH) == Decimal(0)


def test_apply_rebuilds_the_average_even_with_no_later_moves(db, user):
    """میانگین باید بازساخته شود حتی وقتی این آخرین حرکتِ کالاست.

    `settle_posting` این حالت را رد می‌کند (چون سندِ تازه با بازپخش یکی است)؛
    این‌جا **گذشته عوض شده**، پس بازمحاسبه‌ی کامل لازم است.
    """
    item = make_item(db)
    _receipt(db, user, item, 15)
    db.flush()
    assert Decimal(item.average_cost) == Decimal(0)

    _apply(db, user, {item.id: Decimal(160_000)})
    db.refresh(item)
    assert Decimal(item.average_cost) == Decimal(160_000)


def test_apply_reaches_every_receipt_in_scope(db, user):
    item = make_item(db)
    _receipt(db, user, item, 10)
    _receipt(db, user, item, 20, on=date(2026, 3, 20))
    db.flush()

    result = _apply(db, user, {item.id: Decimal(1_000)})
    assert result["receipts"] == 2
    assert result["value"] == Decimal(30_000)


# --- مرزها -------------------------------------------------------------------


def test_applying_twice_changes_nothing(db, user):
    """اجرای دوباره چیزی برای انجام‌دادن پیدا نمی‌کند — یکتاسازی از شکلِ داده."""
    item = make_item(db)
    _receipt(db, user, item, 15)
    db.flush()
    _apply(db, user, {item.id: Decimal(160_000)})

    again = _apply(db, user, {item.id: Decimal(999_999)})
    assert again == {"receipts": 0, "lines": 0, "value": Decimal(0)}
    db.refresh(item)
    assert Decimal(item.average_cost) == Decimal(160_000)


def test_already_priced_line_is_never_overwritten(db, user):
    """تغییرِ بهای یک ورودیِ قیمت‌خورده کارِ این مسیر نیست — ابطال و ثبتِ دوباره است."""
    item = make_item(db)
    receipt = _receipt(db, user, item, 15, unit_cost=Decimal(100_000))
    db.flush()

    _apply(db, user, {item.id: Decimal(160_000)})
    db.refresh(receipt)
    assert Decimal(receipt.lines[0].unit_cost) == Decimal(100_000)


def test_partial_pricing_leaves_the_rest_alone(db, user):
    """کالایی که فی نگرفته دست‌نخورده می‌ماند و هنوز در فهرستِ بی‌فی است."""
    priced, untouched = make_item(db), make_item(db)
    _receipt(db, user, priced, 10)
    _receipt(db, user, untouched, 20)
    db.flush()

    _apply(db, user, {priced.id: Decimal(5_000)})

    remaining = {r["item_id"] for r in _unpriced(db)}
    assert untouched.id in remaining
    assert priced.id not in remaining


def test_zero_price_is_rejected(db, user):
    item = make_item(db)
    _receipt(db, user, item, 15)
    db.flush()
    with pytest.raises(HTTPException) as err:
        _apply(db, user, {item.id: Decimal(0)})
    assert err.value.status_code == 400


def test_purchase_receipt_bought_outside_the_system_credits_cash(db, user):
    """کالایی که بیرون از سیستم خریده‌ایم هم قیمت‌گذاری می‌شود — با بستانکارِ خودش.

    بستانکار از نوعِ رسید می‌آید، نه از این ماژول؛ پس رسیدِ خرید نقد را می‌زند و
    رسیدِ تولید جریانِ ساخت را.
    """
    item = make_item(db)
    receipt = _receipt(db, user, item, 15, receipt_type="purchase_domestic")
    db.flush()

    _apply(db, user, {item.id: Decimal(160_000)})
    db.refresh(receipt)

    entry = db.get(JournalEntry, receipt.journal_entry_id)
    assert _credit_of(db, entry, cc.CASH) == Decimal(2_400_000)
    assert _credit_of(db, entry, cc.WORK_IN_PROCESS) == Decimal(0)
