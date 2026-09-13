"""قیمت‌گذاریِ اسنادِ انبار — نوبتِ اول.

هر تست یکی از شکاف‌های فصل را می‌سنجد:

* ترتیبِ زمانی: سندِ پیش‌تاریخ میانگینِ **همان روز** را می‌گیرد و کاردکس جای زمانی‌اش را؛
* گاردِ خطِ زمان: نه ثبتِ پیش‌تاریخ و نه ابطال، گذشته را منفی نمی‌کند؛
* یک تعریف از میانگین: بازپخش همان عددی را می‌دهد که ثبتِ لحظه‌ای داد (برگشت از خرید)،
  و ابطالِ خروج هم میانگین را بازمی‌سازد؛
* گزارشِ ریالی: ارزشِ «تا تاریخ» ارزشِ همان روز است، با مانده‌ی اول/ورود/خروج؛
* تطبیق و منقضی: اختلافِ انبار با دفتر و علتش از خودِ دفتر پیدا می‌شود؛
* ویرایشِ دستیِ میانگینِ کالای موجود بسته است.
"""
import pathlib
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import JournalLine
from app.schemas.inventory import StockAdjustmentIn
from app.schemas.invoices import (
    DirectWarehouseIssueIn,
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    WarehouseIssueLineIn,
)
from app.schemas.returns import PurchaseReturnIn, PurchaseReturnLineIn
from app.services import chart_codes as cc
from app.services import integrity, valuation
from app.services.common import get_account
from app.services.integrity import run_integrity_check
from app.services.inventory import post_purchase_invoice, post_stock_adjustment
from app.services.reports import get_inventory_report, get_kardex
from app.services.returns import post_purchase_return
from app.services.voiding import void_purchase_invoice
from app.services.warehouse_issues import create_direct_warehouse_issue, void_warehouse_issue
from tests.factories import main_warehouse, make_contact, make_item

D1 = date(2026, 1, 1)
D5 = date(2026, 1, 5)
D10 = date(2026, 1, 10)
D15 = date(2026, 1, 15)
FEB = date(2026, 2, 1)
FEB_END = date(2026, 2, 28)


def _buy(db, user, item, qty, cost, on):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=on,
            warehouse_id=main_warehouse(db).id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(cost))],
        ),
        user,
    )


def _issue(db, user, item, qty, on):
    return create_direct_warehouse_issue(
        db,
        DirectWarehouseIssueIn(
            issue_date=on,
            warehouse_id=main_warehouse(db).id,
            receiver_id=make_contact(db).id,
            lines=[WarehouseIssueLineIn(item_id=item.id, qty=Decimal(qty))],
        ),
        user,
    )


def _credit_total(db, entry_id) -> Decimal:
    return sum((Decimal(line.credit) for line in db.query(JournalLine).filter(JournalLine.entry_id == entry_id)), Decimal(0))


def _check(report, key):
    return next(check for check in report["checks"] if check["key"] == key)


def _inventory_row(db):
    """ردیفِ معینِ «موجودی کالا» در بررسیِ تطبیق — یا `None`.

    تست‌ها با **اختلافِ پیش و پس** می‌سنجند، نه با عددِ مطلق: این بررسی کلِ دفتر را
    می‌خواند و هر داده‌ای که تستِ دیگری در همان پایگاه‌داده گذاشته، در آن هست.
    """
    account = get_account(db, cc.INVENTORY)
    rows = [row for row in _check(run_integrity_check(db), "inventory_vs_ledger")["rows"] if row["account_id"] == account.id]
    return rows[0] if rows else None


def _inventory_gap(db) -> Decimal:
    row = _inventory_row(db)
    return Decimal(row["difference"]) if row is not None else Decimal(0)


# ─────────────────────────── ترتیبِ زمانی ───────────────────────────


def test_backdated_issue_takes_that_days_average(db, user):
    """خروجِ پنجمِ ماه بهای خریدِ دهم را نمی‌خورد — و کاردکس آن را سرِ جای زمانی‌اش می‌گذارد."""
    item = make_item(db)
    _buy(db, user, item, 10, 100, D1)
    _buy(db, user, item, 10, 300, D10)  # میانگینِ امروز: ۲۰۰

    issue = _issue(db, user, item, 10, D5)

    assert Decimal(issue.lines[0].unit_cost) == 100
    assert _credit_total(db, issue.journal_entry_id) == 1000, "سندِ خروج باید با بهای همان روز بخورد"
    db.refresh(item)
    #: پنجم موجودی صفر شد، پس خریدِ دهم میانگین را کاملاً تعیین می‌کند.
    assert Decimal(item.average_cost) == 300

    kardex = get_kardex(db, item.id, None, None, None)
    assert [line["source_type"] for line in kardex["lines"]] == [
        "purchase_invoice",
        "warehouse_issue",
        "purchase_invoice",
    ], "کاردکس باید به ترتیبِ تاریخ باشد، نه ترتیبِ ثبت"
    assert [line["balance_qty"] for line in kardex["lines"]] == [10, 0, 10]
    assert [line["balance_value"] for line in kardex["lines"]] == [1000, 0, 3000]
    assert not any(line["stale"] for line in kardex["lines"])


def test_backdated_adjustment_uses_that_days_average(db, user):
    item = make_item(db)
    _buy(db, user, item, 10, 100, D1)
    _buy(db, user, item, 10, 300, D10)
    adjustment = post_stock_adjustment(
        db,
        StockAdjustmentIn(item_id=item.id, warehouse_id=main_warehouse(db).id, qty_diff=Decimal(-2), adjustment_date=D5),
        user,
    )
    assert Decimal(adjustment.unit_cost) == 100


def test_backdated_receipt_makes_a_later_issue_stale_and_says_why(db, user, monkeypatch):
    """خریدی که بعداً با تاریخِ گذشته ثبت شود، بهای خروجِ بعد از آن را کهنه می‌کند.

    سندِ حسابداریِ خروج دست نمی‌خورد (اصلاحش کارِ فرآیندِ قیمت‌گذاری است)، ولی میانگین
    از بازپخش ساخته می‌شود، کاردکس ردیف را «منقضی» نشان می‌دهد و بررسیِ یکپارچگی هم
    اختلافِ انبار با دفتر را می‌گوید و هم علتش را — با شماره‌ی همان فاکتور.
    """
    #: یافته‌ها به پنجاه ردیف بریده می‌شوند؛ داده‌ی تست‌های دیگر نباید ردیفِ این کالا را بیرون بیندازد.
    monkeypatch.setattr(integrity, "ROW_LIMIT", 100_000)
    gap_before = _inventory_gap(db)
    item = make_item(db)
    _buy(db, user, item, 10, 100, D1)
    _issue(db, user, item, 5, D10)  # با ۱۰۰ سند خورد
    late = _buy(db, user, item, 10, 400, D5)  # پیش‌تاریخ

    db.refresh(item)
    #: یکم ۱۰@۱۰۰، پنجم ۱۰@۴۰۰ → ۲۰@۲۵۰؛ خروجِ دهم میانگین را عوض نمی‌کند.
    assert Decimal(item.average_cost) == 250

    issue_line = next(line for line in get_kardex(db, item.id, None, None, None)["lines"] if line["source_type"] == "warehouse_issue")
    assert issue_line["stale"] is True
    assert issue_line["recorded_unit_cost"] == 100
    assert issue_line["unit_cost"] == 250

    [stale] = [entry for entry in valuation.stale_items(db) if entry["item_id"] == item.id]
    assert stale["from_date"] == D10
    assert stale["count"] == 1
    assert stale["difference"] == -750  # ۵ × (۲۵۰ − ۱۰۰) کمتر در انبار
    assert stale["causes"] == [("backdated", "purchase_invoice", late.id)]

    report = run_integrity_check(db)
    [row] = [row for row in _check(report, "stale_valuation")["rows"] if row["item_id"] == item.id]
    assert f"فاکتور خرید شماره {late.number}" in row["detail"]

    #: دفتر: ۱۰۰۰ + ۴۰۰۰ − ۵۰۰ = ۴۵۰۰؛ انبار: ۱۵ × ۲۵۰ = ۳۷۵۰.
    assert _inventory_gap(db) - gap_before == 750
    assert "ارزش‌گذاریِ منقضی" in _inventory_row(db)["detail"]


# ─────────────────────────── گاردِ خطِ زمان ───────────────────────────


def test_backdated_issue_that_empties_the_past_is_refused(db, user):
    """موجودیِ امروز کافی است، ولی پنجمِ ماه هنوز چیزی در انبار نبود."""
    item = make_item(db)
    _buy(db, user, item, 10, 100, D10)
    with pytest.raises(HTTPException) as exc:
        _issue(db, user, item, 5, D5)
    assert exc.value.status_code == 409
    assert "منفی" in exc.value.detail


def test_offline_replay_is_not_blocked_by_the_timeline(db, user):
    """فروشِ آفلاینِ دیروز که بعد از خریدِ امروز همگام می‌شود نباید رد شود."""
    item = make_item(db)
    _buy(db, user, item, 10, 100, D10)
    db.info[valuation.LENIENT_TIMELINE] = True
    try:
        issue = _issue(db, user, item, 5, D5)
    finally:
        db.info.pop(valuation.LENIENT_TIMELINE, None)
    assert issue.id is not None


def test_voiding_a_receipt_a_later_issue_relied_on_is_refused(db, user):
    """گاردِ قدیمی موجودیِ امروز (صفر) را می‌دید و پاس می‌کرد."""
    item = make_item(db)
    first = _buy(db, user, item, 10, 100, D1)
    _issue(db, user, item, 10, D5)
    _buy(db, user, item, 10, 100, D10)

    with pytest.raises(HTTPException) as exc:
        void_purchase_invoice(db, first.id, reason="ثبتِ اشتباه", user=user)
    assert exc.value.status_code == 409
    assert "منفی" in exc.value.detail
    assert "خروج انبار شماره" in exc.value.detail


# ─────────────────────────── یک تعریف از میانگین ───────────────────────────


def test_voiding_an_issue_rebuilds_the_average(db, user):
    """خروج وزنِ ورودهای بعدی را عوض می‌کند؛ ابطالش هم باید میانگین را بازسازد."""
    item = make_item(db)
    _buy(db, user, item, 10, 1000, D1)
    issue = _issue(db, user, item, 10, D5)
    _buy(db, user, item, 10, 2000, D10)
    db.refresh(item)
    assert Decimal(item.average_cost) == 2000

    void_warehouse_issue(db, issue.id, reason="ثبتِ اشتباه", user=user)
    db.refresh(item)
    assert Decimal(item.average_cost) == 1500


def test_purchase_return_replays_the_way_it_was_posted(db, user):
    """برگشت از خرید با بهای خودش بیرون می‌رود؛ بازپخشِ قدیمی آن را بی‌اثر می‌گرفت."""
    item = make_item(db)
    _buy(db, user, item, 10, 100, D1)
    second = _buy(db, user, item, 10, 200, D1)  # میانگین ۱۵۰
    post_purchase_return(
        db,
        PurchaseReturnIn(
            return_date=D1,
            purchase_invoice_id=second.id,
            lines=[PurchaseReturnLineIn(purchase_invoice_line_id=second.lines[0].id, qty=Decimal(5))],
        ),
        user,
    )
    db.flush()
    db.refresh(item)
    posted = Decimal(item.average_cost)
    assert posted == Decimal("133.3333")  # (۲۰ × ۱۵۰ − ۵ × ۲۰۰) ÷ ۱۵

    valuation.recompute(db, item)
    assert Decimal(item.average_cost) == posted


# ─────────────────────────── گزارشِ ریالی ───────────────────────────


def test_inventory_report_as_of_uses_that_days_value(db, user):
    item = make_item(db)
    _buy(db, user, item, 10, 100, D1)
    _buy(db, user, item, 10, 300, FEB)

    [then] = [row for row in get_inventory_report(db, None, D15)["rows"] if row["item_id"] == item.id]
    assert then["qty_on_hand"] == 10
    assert then["unit_cost"] == 100
    assert then["stock_value"] == 1000, "ارزشِ نیمه‌ی دی نباید با میانگینِ بهمن حساب شود"

    [now] = [row for row in get_inventory_report(db, None, None)["rows"] if row["item_id"] == item.id]
    assert now["stock_value"] == 4000


def test_inventory_report_period_columns(db, user):
    item = make_item(db)
    _buy(db, user, item, 10, 100, D1)
    _issue(db, user, item, 4, D10)
    _buy(db, user, item, 10, 300, FEB)

    report = get_inventory_report(db, None, FEB_END, D5)
    [row] = [row for row in report["rows"] if row["item_id"] == item.id]
    assert (row["opening_qty"], row["opening_value"]) == (10, 1000)
    assert (row["in_qty"], row["in_value"]) == (10, 3000)
    assert (row["out_qty"], row["out_value"]) == (4, 400)
    assert (row["qty_on_hand"], row["stock_value"]) == (16, 3600)
    assert row["stale_from"] is None
    assert row["book_value"] == row["stock_value"]


def test_kardex_opening_value_with_date_filter(db, user):
    item = make_item(db)
    _buy(db, user, item, 10, 100, D1)
    _buy(db, user, item, 10, 300, D10)

    kardex = get_kardex(db, item.id, None, D5, None)
    assert (kardex["opening_qty"], kardex["opening_value"]) == (10, 1000)
    assert len(kardex["lines"]) == 1
    assert kardex["lines"][0]["value_in"] == 3000
    assert (kardex["closing_qty"], kardex["closing_value"]) == (20, 4000)
    assert kardex["average_cost"] == 200


def test_inventory_matches_the_ledger_when_nothing_is_stale(db, user):
    gap_before = _inventory_gap(db)
    item = make_item(db)
    _buy(db, user, item, 10, 100, D1)
    _issue(db, user, item, 4, D5)
    assert _inventory_gap(db) == gap_before, "خرید و خروجِ هم‌ترتیب نباید اختلافی میانِ انبار و دفتر بسازند"


def test_inventory_checks_skip_a_narrowed_scope(db, user):
    """با فیلترِ شماره‌ی سند، مانده‌ی معین از یک سند می‌آمد و ارزشِ انبار از همه — بی‌معنا."""
    from app.services.reports import ReportFilters

    item = make_item(db)
    _buy(db, user, item, 10, 100, D1)
    _issue(db, user, item, 5, D10)
    _buy(db, user, item, 10, 400, D5)
    report = run_integrity_check(db, ReportFilters(entry_from=1, entry_to=1))
    for key in ("inventory_vs_ledger", "stale_valuation"):
        check = _check(report, key)
        assert check["ok"] and check["rows"] == [] and "اجرا نمی‌شود" in check["description"]


# ─────────────────────────── ویرایشِ دستی و ساختار ───────────────────────────


def test_manual_average_edit_is_refused_while_the_item_has_stock(db, user, client):
    item = make_item(db, average_cost=0)
    _buy(db, user, item, 5, 100, D1)
    res = client.patch(f"/api/items/{item.id}", json={"average_cost": 900})
    assert res.status_code == 409, res.text
    db.refresh(item)
    assert Decimal(item.average_cost) == 100


def test_every_stock_writer_goes_through_valuation():
    """هر سرویسی که `StockLedger` می‌سازد باید از `valuation` بگذرد.

    ثبتی که `settle_posting`/`settle_void` را صدا نزند، نه گاردِ خطِ زمان را دارد نه
    بازسازیِ میانگینِ پیش‌تاریخ را — و هیچ خطایی هم نمی‌دهد. این تست جلوی نویسنده‌ی
    تازه‌ای را می‌گیرد که فقط `db.add(StockLedger(...))` می‌نویسد.
    """
    services = pathlib.Path(__file__).resolve().parents[1] / "app" / "services"
    missing = []
    for path in sorted(services.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if path.name != "valuation.py" and "StockLedger(" in text and "valuation." not in text:
            missing.append(path.name)
    assert not missing, f"این سرویس‌ها حرکتِ انبار می‌نویسند ولی از valuation نمی‌گذرند: {missing}"
