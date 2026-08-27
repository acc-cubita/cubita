"""مراکز هزینه/پروژه — برچسبِ سند، انتقال به سندِ فاکتور، گزارشِ سود، و گاردِ حذف."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import JournalEntry, JournalLine
from app.schemas.cost_center import CostCenterIn
from app.schemas.invoices import SalesInvoiceIn, SalesInvoiceLineIn, PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.services import chart_codes as cc
from app.services import cost_centers as svc
from app.services.cost_centers import get_report as get_cost_center_report
from app.services.common import get_account, make_journal_entry
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.models.cost_center import CostCenter
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 3, 15)


def _center(db, user, name="پروژه الف", code="P1", **kw):
    """سرویس دیکشنری برمی‌گرداند؛ تست‌ها به شیءِ ORM نیاز دارند."""
    out = svc.create_cost_center(db, CostCenterIn(name=name, code=code, **kw), user)
    return db.get(CostCenter, out["id"])


def _tagged(db, user, account, *, debit=0, credit=0, center=None):
    other = get_account(db, cc.CASH)
    make_journal_entry(
        db,
        TODAY,
        "تست مرکز",
        "manual",
        user,
        [
            JournalLine(account_id=account.id, debit=Decimal(debit), credit=Decimal(credit),
                        cost_center_id=center.id if center else None),
            JournalLine(account_id=other.id, debit=Decimal(credit), credit=Decimal(debit),
                        cost_center_id=center.id if center else None),
        ],
    )
    db.flush()


def _row(report, cost_center_id):
    return next((r for r in report["rows"] if r["cost_center_id"] == cost_center_id), None)


def test_create_and_list(db, user):
    c = _center(db, user)
    centers = svc.list_cost_centers(db)
    assert any(x["id"] == c.id for x in centers)


def test_report_groups_income_and_expense_by_center(db, user):
    center = _center(db, user)
    rev = get_account(db, cc.SALES_REVENUE)
    exp = get_account(db, cc.PAYROLL_EXPENSE)
    _tagged(db, user, rev, credit=1_000_000, center=center)
    _tagged(db, user, exp, debit=400_000, center=center)

    report = get_cost_center_report(db, None, None)
    row = _row(report, center.id)
    assert row is not None
    assert row["income"] == Decimal(1_000_000)
    assert row["expense"] == Decimal(400_000)
    assert row["profit"] == Decimal(600_000)


def test_untagged_activity_falls_into_none_bucket(db, user):
    rev = get_account(db, cc.SALES_REVENUE)
    _tagged(db, user, rev, credit=500_000, center=None)

    report = get_cost_center_report(db, None, None)
    none_row = _row(report, None)
    assert none_row is not None
    assert none_row["cost_center_name"] == "بدون مرکز هزینه"
    assert none_row["income"] >= Decimal(500_000)


def test_sales_invoice_propagates_center_to_journal_lines(db, user):
    center = _center(db, user)
    wh = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(1_000_000))],
        ),
        user,
    )

    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            cost_center_id=center.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_price=Decimal(5_000_000))],
        ),
        user,
    )

    assert inv.cost_center_id == center.id
    entry = db.get(JournalEntry, inv.journal_entry_id)
    # همه‌ی ردیف‌های سندِ فاکتور باید برچسبِ مرکز را گرفته باشند
    assert entry.lines and all(l.cost_center_id == center.id for l in entry.lines)

    # و در گزارش، سود این پروژه = درآمد ۱۰م − COGS ۲م = ۸م
    report = get_cost_center_report(db, None, None)
    row = _row(report, center.id)
    assert row["income"] == Decimal(10_000_000)
    assert row["expense"] == Decimal(2_000_000)
    assert row["profit"] == Decimal(8_000_000)


def test_invalid_cost_center_on_invoice_is_rejected(db, user):
    from uuid import uuid4

    wh = main_warehouse(db)
    item = make_item(db)
    with pytest.raises(HTTPException) as exc:
        post_sales_invoice(
            db,
            SalesInvoiceIn(
                invoice_date=TODAY,
                warehouse_id=wh.id,
                cost_center_id=uuid4(),  # وجود ندارد
                lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(1_000))],
            ),
            user,
        )
    assert exc.value.status_code == 400


def test_delete_blocked_when_referenced(db, user):
    center = _center(db, user)
    rev = get_account(db, cc.SALES_REVENUE)
    _tagged(db, user, rev, credit=100_000, center=center)
    with pytest.raises(HTTPException) as exc:
        svc.delete_cost_center(db, center.id)
    assert exc.value.status_code == 400


def test_delete_ok_when_unreferenced(db, user):
    center = _center(db, user)
    svc.delete_cost_center(db, center.id)
    assert db.get(CostCenter, center.id) is None


# ── درخت ─────────────────────────────────────────────────────────────────────


def test_tree_path_and_depth(db, user):
    branch = _center(db, user, name="شعبه تهران", code="B1", kind="branch")
    project = _center(db, user, name="پروژه الف", code="B1-P1", parent_id=branch.id)
    rows = {r["id"]: r for r in svc.list_cost_centers(db)}
    assert rows[branch.id]["depth"] == 0
    assert rows[project.id]["depth"] == 1
    assert rows[project.id]["path"] == "شعبه تهران / پروژه الف"
    assert rows[branch.id]["child_count"] == 1


def test_tree_order_puts_child_right_after_parent(db, user):
    branch = _center(db, user, name="شعبه تهران", code="B1", kind="branch")
    child = _center(db, user, name="پروژه الف", code="ZZZ", parent_id=branch.id)
    # کدِ فرزند عمداً آخرِ الفباست؛ ترتیبِ درختی باید بر ترتیبِ کد بچربد.
    order = [r["id"] for r in svc.list_cost_centers(db)]
    assert order.index(child.id) == order.index(branch.id) + 1


def test_parent_cannot_be_self(db, user):
    center = _center(db, user)
    with pytest.raises(HTTPException) as exc:
        svc.update_cost_center(db, center.id, CostCenterIn(name=center.name, parent_id=center.id))
    assert exc.value.status_code == 400


def test_parent_cannot_be_own_descendant(db, user):
    root = _center(db, user, name="ریشه", code="R")
    mid = _center(db, user, name="میانی", code="M", parent_id=root.id)
    leaf = _center(db, user, name="برگ", code="L", parent_id=mid.id)
    # حلقه‌ی ریشه→میانی→برگ→ریشه باید رد شود، وگرنه تجمیع بی‌پایان می‌شود.
    with pytest.raises(HTTPException) as exc:
        svc.update_cost_center(db, root.id, CostCenterIn(name=root.name, parent_id=leaf.id))
    assert exc.value.status_code == 400


def test_delete_blocked_when_center_has_children(db, user):
    parent = _center(db, user, name="مادر", code="P")
    _center(db, user, name="فرزند", code="C", parent_id=parent.id)
    with pytest.raises(HTTPException) as exc:
        svc.delete_cost_center(db, parent.id)
    assert exc.value.status_code == 400


# ── تجمیع ────────────────────────────────────────────────────────────────────


def test_rollup_sums_descendants_but_total_counts_once(db, user):
    branch = _center(db, user, name="شعبه", code="B", kind="branch")
    project = _center(db, user, name="پروژه", code="B-P", parent_id=branch.id)
    rev = get_account(db, cc.SALES_REVENUE)
    _tagged(db, user, rev, credit=1_000_000, center=branch)
    _tagged(db, user, rev, credit=3_000_000, center=project)

    report = get_cost_center_report(db, None, None)
    branch_row = _row(report, branch.id)
    assert branch_row["income"] == Decimal(1_000_000)  # مستقیم
    assert branch_row["rollup_income"] == Decimal(4_000_000)  # با زیرشاخه
    # جمعِ کل از ارقامِ مستقیم است، پس ۴م نه ۵م — شعبه دوبار شمرده نمی‌شود.
    assert report["total_income"] == Decimal(4_000_000)


def test_untagged_share_reports_labelling_quality(db, user):
    center = _center(db, user)
    rev = get_account(db, cc.SALES_REVENUE)
    _tagged(db, user, rev, credit=750_000, center=center)
    _tagged(db, user, rev, credit=250_000, center=None)
    report = get_cost_center_report(db, None, None)
    assert report["untagged_share_pct"] == Decimal("25.0")


# ── بودجه ────────────────────────────────────────────────────────────────────


def _budget(db, user, center, account, amount, period=date(2026, 3, 1)):
    from app.schemas.budgeting import BudgetLineIn
    from app.services import budgeting

    return budgeting.create_budget_line(
        db,
        BudgetLineIn(
            account_id=account.id,
            period_date=period,
            amount=Decimal(amount),
            cost_center_id=center.id if center else None,
        ),
        user,
    )


def test_budget_variance_compares_plan_with_actual(db, user):
    center = _center(db, user)
    rev = get_account(db, cc.SALES_REVENUE)
    _budget(db, user, center, rev, 1_000_000)
    _tagged(db, user, rev, credit=1_200_000, center=center)

    report = get_cost_center_report(db, None, None)
    row = _row(report, center.id)
    assert row["budget_income"] == Decimal(1_000_000)
    assert row["profit_variance"] == Decimal(200_000)


def test_center_without_budget_has_no_variance(db, user):
    center = _center(db, user)
    rev = get_account(db, cc.SALES_REVENUE)
    _tagged(db, user, rev, credit=500_000, center=center)
    row = _row(get_cost_center_report(db, None, None), center.id)
    # صفر و «بی‌بودجه» دو چیزند: انحرافِ صفر یعنی دقیقاً طبقِ برنامه.
    assert row["profit_variance"] is None


def test_budget_upsert_is_per_center(db, user):
    a = _center(db, user, name="پروژه ۱", code="P1")
    b = _center(db, user, name="پروژه ۲", code="P2")
    rev = get_account(db, cc.SALES_REVENUE)
    _budget(db, user, a, rev, 100_000)
    _budget(db, user, b, rev, 200_000)
    from app.services import budgeting

    assert len(budgeting.list_budget_lines(db, cost_center_id=a.id)) == 1
    assert len(budgeting.list_budget_lines(db, cost_center_id=b.id)) == 1
    # همان حساب و همان ماه، ولی دو مرکز — دو برنامه‌ی متفاوت، نه ردیفِ تکراری.
    assert len(budgeting.list_budget_lines(db)) == 2


def test_budget_rejects_unknown_center(db, user):
    from uuid import uuid4

    from app.schemas.budgeting import BudgetLineIn
    from app.services import budgeting

    rev = get_account(db, cc.SALES_REVENUE)
    with pytest.raises(HTTPException) as exc:
        budgeting.create_budget_line(
            db,
            BudgetLineIn(
                account_id=rev.id,
                period_date=date(2026, 3, 1),
                amount=Decimal(1),
                cost_center_id=uuid4(),
            ),
            user,
        )
    assert exc.value.status_code == 400


# ── تحلیل و دفتر ─────────────────────────────────────────────────────────────


def test_analysis_breaks_down_by_account(db, user):
    center = _center(db, user)
    rev = get_account(db, cc.SALES_REVENUE)
    exp = get_account(db, cc.PAYROLL_EXPENSE)
    _tagged(db, user, rev, credit=1_000_000, center=center)
    _tagged(db, user, exp, debit=400_000, center=center)

    out = svc.get_analysis(db, center.id, None, None)
    assert out["income"] == Decimal(1_000_000)
    assert out["profit"] == Decimal(600_000)
    assert out["margin_pct"] == Decimal("60.0")
    assert [r["account_code"] for r in out["income_accounts"]] == [rev.code]
    assert out["expense_accounts"][0]["share_pct"] == Decimal("100.0")
    assert len(out["monthly"]) == svc.TREND_MONTHS


def test_analysis_include_children_toggle(db, user):
    parent = _center(db, user, name="مادر", code="P")
    child = _center(db, user, name="فرزند", code="P-C", parent_id=parent.id)
    rev = get_account(db, cc.SALES_REVENUE)
    _tagged(db, user, rev, credit=900_000, center=child)

    with_children = svc.get_analysis(db, parent.id, None, None)
    without = svc.get_analysis(db, parent.id, None, None, include_children=False)
    assert with_children["income"] == Decimal(900_000)
    assert without["income"] == Decimal(0)
    assert [c["name"] for c in with_children["children"]] == ["فرزند"]


def test_ledger_lists_tagged_lines_only(db, user):
    center = _center(db, user)
    rev = get_account(db, cc.SALES_REVENUE)
    _tagged(db, user, rev, credit=500_000, center=center)

    rows = svc.get_ledger(db, center.id, None, None)
    # سندِ آزمون دو ردیف دارد (درآمد و نقد) ولی فقط ردیفِ درآمد در سودِ مرکز می‌آید.
    assert len(rows) == 1
    assert rows[0]["account_code"] == rev.code
    assert rows[0]["credit"] == Decimal(500_000)
    assert rows[0]["cost_center_name"] == center.name


def test_elapsed_pct_needs_both_dates(db, user):
    open_ended = _center(db, user, name="بی‌بازه", code="X", start_date=date(2026, 1, 1))
    assert svc.get_analysis(db, open_ended.id, None, None)["elapsed_pct"] is None
