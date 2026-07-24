"""بودجه‌بندی — گزارشِ بودجه در برابر عملکرد، منطقِ مطلوب/نامطلوب، و upsert."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account, JournalLine
from app.schemas.budgeting import BudgetLineIn
from app.services import budgeting as svc
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry


def _post(db, user, account: Account, *, debit=0, credit=0, on=date(2026, 1, 15)):
    """یک سندِ دوطرفه که یک طرفش حسابِ داده‌شده و طرفِ دیگرش صندوق است."""
    cash = get_account(db, cc.CASH)
    make_journal_entry(
        db,
        on,
        "تست بودجه",
        "manual",
        user,
        [
            JournalLine(account_id=account.id, debit=Decimal(debit), credit=Decimal(credit)),
            JournalLine(account_id=cash.id, debit=Decimal(credit), credit=Decimal(debit)),
        ],
    )
    db.flush()


def _set_budget(db, user, account: Account, amount, on=date(2026, 1, 1)):
    return svc.create_budget_line(
        db, BudgetLineIn(account_id=account.id, period_date=on, amount=Decimal(amount)), user
    )


JAN = (date(2026, 1, 1), date(2026, 1, 31))


def _row_for(report, account_id):
    return next(r for r in report["rows"] if r["account_id"] == account_id)


def test_expense_over_budget_is_unfavorable(db, user):
    expense = get_account(db, cc.PAYROLL_EXPENSE)
    _set_budget(db, user, expense, 1_000_000)
    _post(db, user, expense, debit=1_200_000)

    report = svc.get_budget_report(db, *JAN)
    row = _row_for(report, expense.id)
    assert row["budget"] == Decimal(1_000_000)
    assert row["actual"] == Decimal(1_200_000)
    assert row["variance"] == Decimal(200_000)
    assert row["variance_pct"] == Decimal("20.0")
    assert row["favorable"] is False  # هزینه‌ی بیشتر از بودجه نامطلوب است


def test_income_over_budget_is_favorable(db, user):
    revenue = get_account(db, cc.SALES_REVENUE)
    _set_budget(db, user, revenue, 1_000_000)
    _post(db, user, revenue, credit=1_500_000)

    report = svc.get_budget_report(db, *JAN)
    row = _row_for(report, revenue.id)
    assert row["actual"] == Decimal(1_500_000)
    assert row["variance"] == Decimal(500_000)
    assert row["favorable"] is True  # درآمدِ بیشتر از بودجه مطلوب است


def test_create_is_upsert_not_duplicate(db, user):
    expense = get_account(db, cc.PAYROLL_EXPENSE)
    _set_budget(db, user, expense, 1_000_000)
    _set_budget(db, user, expense, 1_500_000)  # همان حساب/ماه دوباره

    lines = [l for l in svc.list_budget_lines(db) if l["account_id"] == expense.id]
    assert len(lines) == 1
    assert lines[0]["amount"] == Decimal(1_500_000)


def test_budget_on_group_account_rejected(db, user):
    group = db.query(Account).filter(Account.is_group.is_(True)).first()
    with pytest.raises(HTTPException) as exc:
        _set_budget(db, user, group, 1_000_000)
    assert exc.value.status_code == 400


def test_report_lists_only_budgeted_accounts(db, user):
    budgeted = get_account(db, cc.PAYROLL_EXPENSE)
    unbudgeted = get_account(db, cc.COGS)
    _set_budget(db, user, budgeted, 1_000_000)
    _post(db, user, budgeted, debit=500_000)
    _post(db, user, unbudgeted, debit=900_000)  # فعالیت دارد ولی بودجه ندارد

    report = svc.get_budget_report(db, *JAN)
    ids = {r["account_id"] for r in report["rows"]}
    assert budgeted.id in ids
    assert unbudgeted.id not in ids


def test_totals_sum_rows(db, user):
    expense = get_account(db, cc.PAYROLL_EXPENSE)
    revenue = get_account(db, cc.SALES_REVENUE)
    _set_budget(db, user, expense, 1_000_000)
    _set_budget(db, user, revenue, 3_000_000)
    _post(db, user, expense, debit=800_000)
    _post(db, user, revenue, credit=2_500_000)

    report = svc.get_budget_report(db, *JAN)
    assert report["total_budget"] == Decimal(4_000_000)
    assert report["total_actual"] == Decimal(3_300_000)
    assert report["total_variance"] == Decimal(-700_000)
