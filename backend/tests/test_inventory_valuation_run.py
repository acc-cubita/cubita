"""قیمت‌گذاری اسناد انبار — نوبتِ دوم: پیش‌نمایش، سندِ اصلاحی، ابطال.

سناریوی پایه‌ی بیشترِ تست‌ها همان سناریوی نوبتِ اول است: خرید ۱۰@۱۰۰ در یکم، خروجِ ۵تایی
در دهم (با ۱۰۰ سند خورد)، و خریدِ ۱۰@۴۰۰ به تاریخِ پنجم که **بعداً** ثبت می‌شود. بهای درستِ
آن خروج ۲۵۰ است؛ اجرای قیمت‌گذاری باید همین را با یک سندِ اصلاحیِ ۷۵۰ ریالی درست کند.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.inventory import StockLedger
from app.models.inventory_valuation import InventoryValuationRun
from app.schemas.inventory_valuation import ValuationRunIn
from app.schemas.invoices import (
    DirectWarehouseIssueIn,
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    WarehouseIssueLineIn,
)
from app.schemas.issue_returns import IssueReturnIn, IssueReturnLineIn
from app.schemas.transfers import StockTransferIn, StockTransferLineIn
from app.services import chart_codes as cc
from app.services import valuation, valuation_runs, warehouses
from app.services.common import get_account
from app.services.integrity import run_integrity_check
from app.services.inventory import post_purchase_invoice
from app.services.issue_returns import create_issue_return
from app.services.reports import get_kardex
from app.services.transfers import post_stock_transfer
from app.services.warehouse_issues import create_direct_warehouse_issue, void_warehouse_issue
from tests.factories import main_warehouse, make_contact, make_item, other_warehouse

D1 = date(2026, 1, 1)
D5 = date(2026, 1, 5)
D10 = date(2026, 1, 10)
D15 = date(2026, 1, 15)
D20 = date(2026, 1, 20)
END = date(2026, 2, 28)


def _item(db, tag: str):
    return make_item(db, sku=f"VR-{tag}-{uuid.uuid4().hex[:6]}")


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


def _issue(db, user, item, qty, on, *, issue_type="sale", account_id=None):
    return create_direct_warehouse_issue(
        db,
        DirectWarehouseIssueIn(
            issue_date=on,
            issue_type=issue_type,
            warehouse_id=main_warehouse(db).id,
            receiver_id=make_contact(db).id if issue_type == "sale" else None,
            account_id=account_id,
            lines=[WarehouseIssueLineIn(item_id=item.id, qty=Decimal(qty))],
        ),
        user,
    )


def _stale_scenario(db, user, item):
    _buy(db, user, item, 10, 100, D1)
    issue = _issue(db, user, item, 5, D10)
    late = _buy(db, user, item, 10, 400, D5)
    return issue, late


def _preview(db, item):
    return valuation_runs.calculate(db, date_from=None, date_to=END, item_id=item.id)


def _commit(db, user, item, plan=None, description=""):
    plan = plan if plan is not None else _preview(db, item)
    return valuation_runs.commit_run(
        db, ValuationRunIn(date_to=END, item_id=item.id, token=plan["token"], description=description), user
    )


def _accounts(plan) -> dict:
    return {row["account_id"]: row for row in plan["accounts"]}


def _issue_line(db, item) -> dict:
    return next(line for line in get_kardex(db, item.id, None, None, None)["lines"] if line["source_type"] == "warehouse_issue")


def _inventory_gap(db) -> Decimal:
    """اختلافِ معینِ «موجودی کالا» با ارزشِ انبار — با پیش و پس سنجیده می‌شود، نه مطلق."""
    account = get_account(db, cc.INVENTORY)
    check = next(c for c in run_integrity_check(db)["checks"] if c["key"] == "inventory_vs_ledger")
    rows = [row for row in check["rows"] if row["account_id"] == account.id]
    return Decimal(rows[0]["difference"]) if rows else Decimal(0)


# ─────────────────────────── پیش‌نمایش ───────────────────────────


def test_preview_shows_the_stale_issue_and_the_entry_that_would_fix_it(db, user):
    item = _item(db, "PRE")
    _stale_scenario(db, user, item)

    plan = _preview(db, item)

    assert plan["blocked"] is False and plan["token"]
    assert plan["move_count"] == 1
    [move] = plan["moves"]
    assert (move["previous_cost"], move["new_cost"], move["value_delta"]) == (100, 250, -750)
    assert move["source_label"] == "خروج انبار" and move["source_number"] is not None
    accounts = _accounts(plan)
    assert accounts[get_account(db, cc.COGS).id]["debit"] == 750
    assert accounts[get_account(db, cc.INVENTORY).id]["credit"] == 750
    assert db.query(InventoryValuationRun).filter(InventoryValuationRun.item_id == item.id).count() == 0


# ─────────────────────────── ثبت ───────────────────────────


def test_commit_posts_one_balanced_entry_and_clears_the_staleness(db, user):
    gap_before = _inventory_gap(db)
    item = _item(db, "COMMIT")
    _stale_scenario(db, user, item)

    run = _commit(db, user, item, description="پایانِ دی")

    assert run.move_count == 1 and Decimal(run.total_delta) == -750
    entry = db.get(JournalEntry, run.journal_entry_id)
    assert entry.source_type == "inventory_valuation" and entry.source_id == run.id and entry.entry_date == END
    lines = db.query(JournalLine).filter(JournalLine.entry_id == entry.id).all()
    assert sum(Decimal(line.debit) for line in lines) == sum(Decimal(line.credit) for line in lines) == 750

    line = _issue_line(db, item)
    assert line["stale"] is False and line["adjusted"] is True and line["recorded_unit_cost"] == 250
    assert not [entry for entry in valuation.stale_items(db) if entry["item_id"] == item.id]
    assert _inventory_gap(db) == gap_before, "پس از اصلاح، انبار و دفتر باید دوباره بخوانند"


def test_a_second_run_finds_nothing_to_fix(db, user):
    item = _item(db, "AGAIN")
    _stale_scenario(db, user, item)
    _commit(db, user, item)

    plan = _preview(db, item)
    assert plan["move_count"] == 0 and plan["accounts"] == []
    with pytest.raises(HTTPException) as exc:
        _commit(db, user, item, plan)
    assert exc.value.status_code == 400


def test_commit_on_a_ledger_that_changed_since_the_preview_is_refused(db, user):
    item = _item(db, "TOKEN")
    _stale_scenario(db, user, item)
    plan = _preview(db, item)
    _buy(db, user, item, 1, 300, D20)

    with pytest.raises(HTTPException) as exc:
        _commit(db, user, item, plan)
    assert exc.value.status_code == 409
    assert "محاسبه" in exc.value.detail


def test_negative_history_blocks_the_run(db, user):
    """میانگینِ موزون روی موجودیِ منفی تعریف ندارد — دفترِ پیش از گاردِ خطِ زمان ممکن است داشته باشد."""
    item = _item(db, "NEG")
    warehouse = main_warehouse(db)
    for qty, on, source in ((5, D1, "opening"), (-10, D5, "sales_invoice"), (10, D10, "opening")):
        db.add(StockLedger(
            item_id=item.id, warehouse_id=warehouse.id, qty=Decimal(qty), unit_cost=Decimal(100),
            entry_date=on, source_type=source, source_id=uuid.uuid4() if source == "sales_invoice" else None,
        ))
        db.flush()

    plan = _preview(db, item)
    assert plan["blocked"] is True
    [negative] = plan["negatives"]
    assert negative["entry_date"] == D5 and negative["qty"] == -5
    with pytest.raises(HTTPException) as exc:
        _commit(db, user, item, plan)
    assert exc.value.status_code == 409


# ─────────────────────────── ابطال ───────────────────────────


def test_voiding_the_run_reverses_its_entry_and_the_issue_is_stale_again(db, user):
    item = _item(db, "VOID")
    _stale_scenario(db, user, item)
    run = _commit(db, user, item)

    voided = valuation_runs.void_run(db, run.id, reason="اجرای آزمایشی", user=user)

    assert voided.voided_at is not None
    reversal = db.get(JournalEntry, voided.void_entry_id)
    assert reversal.reverses_entry_id == run.journal_entry_id
    line = _issue_line(db, item)
    assert line["stale"] is True and line["adjusted"] is False
    with pytest.raises(HTTPException) as exc:
        valuation_runs.void_run(db, run.id, reason="دوباره", user=user)
    assert exc.value.status_code == 409


def test_only_the_latest_run_can_be_voided(db, user):
    first_item, second_item = _item(db, "L1"), _item(db, "L2")
    _stale_scenario(db, user, first_item)
    _stale_scenario(db, user, second_item)
    first = _commit(db, user, first_item)
    second = _commit(db, user, second_item)

    with pytest.raises(HTTPException) as exc:
        valuation_runs.void_run(db, first.id, reason="ترتیبِ اشتباه", user=user)
    assert exc.value.status_code == 409 and str(second.number) in exc.value.detail

    valuation_runs.void_run(db, second.id, reason="اول آخری", user=user)
    valuation_runs.void_run(db, first.id, reason="بعد قبلی", user=user)


def test_an_adjusted_document_cannot_be_voided_before_its_run(db, user):
    """ابطالِ خروج سندِ اصلی‌اش را برمی‌گرداند؛ سندِ اصلاحی بی‌پشتوانه می‌ماند."""
    item = _item(db, "DOC")
    issue, _ = _stale_scenario(db, user, item)
    run = _commit(db, user, item)

    with pytest.raises(HTTPException) as exc:
        void_warehouse_issue(db, issue.id, reason="ثبتِ اشتباه", user=user)
    assert exc.value.status_code == 409 and "قیمت‌گذاری اسناد انبار" in exc.value.detail

    valuation_runs.void_run(db, run.id, reason="برای ابطالِ خروج", user=user)
    void_warehouse_issue(db, issue.id, reason="ثبتِ اشتباه", user=user)


# ─────────────────────────── طرفِ مقابلِ سند ───────────────────────────


def test_an_issue_return_follows_its_corrected_issue(db, user):
    """کالای برگشتی با بهای **اصلاح‌شده‌ی** همان خروج برمی‌گردد، نه با بهای کهنه‌اش."""
    item = _item(db, "RET")
    _buy(db, user, item, 10, 100, D1)
    issue = _issue(db, user, item, 5, D10)
    create_issue_return(
        db,
        IssueReturnIn(
            return_date=D15,
            warehouse_id=main_warehouse(db).id,
            deliverer_id=make_contact(db).id,
            lines=[IssueReturnLineIn(warehouse_issue_line_id=issue.lines[0].id, qty=Decimal(2))],
        ),
        user,
    )
    _buy(db, user, item, 10, 400, D5)

    plan = _preview(db, item)
    assert {move["source_type"]: move["value_delta"] for move in plan["moves"]} == {
        "warehouse_issue": -750,
        "warehouse_issue_return": 300,
    }
    #: بهای تمام‌شده فقط برای سه واحدی که واقعاً بیرون ماند اصلاح می‌شود.
    assert _accounts(plan)[get_account(db, cc.COGS).id]["debit"] == 450
    _commit(db, user, item, plan)
    db.refresh(item)
    assert Decimal(item.average_cost) == 250


def test_a_consumption_issue_is_corrected_against_its_own_expense_account(db, user):
    expense = (
        db.query(Account)
        .filter(Account.type == "expense", Account.is_group.is_(False), Account.system_role.is_(None))
        .order_by(Account.code)
        .first()
    )
    if expense is None:
        pytest.skip("چارتِ آزمون حسابِ هزینه‌ی بی‌نقش ندارد")
    item = _item(db, "USE")
    _buy(db, user, item, 10, 100, D1)
    _issue(db, user, item, 5, D10, issue_type="consumption", account_id=expense.id)
    _buy(db, user, item, 10, 400, D5)

    assert _accounts(_preview(db, item))[expense.id]["debit"] == 750


def test_production_consumption_is_listed_not_adjusted(db, user):
    item = _item(db, "PROD")
    _buy(db, user, item, 10, 100, D1)
    db.add(StockLedger(
        item_id=item.id, warehouse_id=main_warehouse(db).id, qty=Decimal(-2), unit_cost=Decimal(100),
        entry_date=D10, source_type="production",
    ))
    db.flush()
    _buy(db, user, item, 10, 400, D5)

    plan = _preview(db, item)
    assert plan["move_count"] == 0
    [skipped] = plan["skipped"]
    assert skipped["source_type"] == "production" and "محصول" in skipped["reason"]
    with pytest.raises(HTTPException):
        _commit(db, user, item, plan)


def test_a_transfer_pair_is_adjusted_on_both_ends(db, user):
    item = _item(db, "MOVE")
    source, target = main_warehouse(db), other_warehouse(db)
    _buy(db, user, item, 10, 100, D1)
    post_stock_transfer(
        db,
        StockTransferIn(
            transfer_date=D10, from_warehouse_id=source.id, to_warehouse_id=target.id,
            lines=[StockTransferLineIn(item_id=item.id, qty=Decimal(4))],
        ),
        user,
    )
    _buy(db, user, item, 10, 400, D5)

    plan = _preview(db, item)
    assert sorted(move["value_delta"] for move in plan["moves"]) == [-600, 600]
    same_account = warehouses.inventory_account_id(db, source.id) == warehouses.inventory_account_id(db, target.id)
    if same_account:
        assert plan["accounts"] == []
        run = _commit(db, user, item, plan)
        assert run.journal_entry_id is None and run.move_count == 2


# ─────────────────────────── مسیر ───────────────────────────


def test_the_api_previews_commits_lists_and_voids(db, user, client):
    item = _item(db, "API")
    _stale_scenario(db, user, item)

    preview = client.get(
        "/api/inventory-valuation/preview", params={"date_to": END.isoformat(), "item_id": str(item.id)}
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["move_count"] == 1

    created = client.post(
        "/api/inventory-valuation/runs",
        json={"date_to": END.isoformat(), "item_id": str(item.id), "token": body["token"]},
    )
    assert created.status_code == 201, created.text
    run = created.json()
    assert run["voidable"] is True and run["journal_entry_number"] is not None

    listed = client.get("/api/inventory-valuation/runs")
    assert listed.status_code == 200 and any(row["id"] == run["id"] for row in listed.json()["items"])
    detail = client.get(f"/api/inventory-valuation/runs/{run['id']}")
    assert detail.status_code == 200 and len(detail.json()["adjustments"]) == 1

    voided = client.post(f"/api/inventory-valuation/runs/{run['id']}/void", json={"reason": "آزمونِ مسیر"})
    assert voided.status_code == 200, voided.text
    assert voided.json()["voidable"] is False and voided.json()["void_entry_number"] is not None
