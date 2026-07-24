"""صورت جریان وجوه نقد — طبقه‌بندیِ سه فعالیت، نادیده‌گرفتنِ انتقالِ داخلی، و آشتیِ مانده."""
from datetime import date
from decimal import Decimal

from app.models.accounting import Account, JournalLine
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.reports import _cash_account_ids, _cash_balance, get_cash_flow

PERIOD = (date(2026, 1, 1), date(2026, 1, 31))


def _post(db, user, lines, on=date(2026, 1, 10)):
    """lines: فهرست (حساب، بدهکار، بستانکار)."""
    make_journal_entry(
        db,
        on,
        "تست جریان نقد",
        "manual",
        user,
        [JournalLine(account_id=a.id, debit=Decimal(d), credit=Decimal(c)) for a, d, c in lines],
    )
    db.flush()


def _amount(report, category, account_id):
    return next((r["amount"] for r in report[category] if r["account_id"] == account_id), Decimal(0))


def test_operating_sale_and_expense(db, user):
    cash = get_account(db, cc.CASH)
    rev = get_account(db, cc.SALES_REVENUE)
    exp = get_account(db, cc.PAYROLL_EXPENSE)
    _post(db, user, [(cash, 1_000_000, 0), (rev, 0, 1_000_000)])  # فروش نقدی
    _post(db, user, [(exp, 300_000, 0), (cash, 0, 300_000)])  # هزینه‌ی نقدی

    r = get_cash_flow(db, *PERIOD)
    assert r["net_operating"] == Decimal(700_000)
    assert r["net_investing"] == Decimal(0)
    assert r["net_financing"] == Decimal(0)
    assert r["net_change"] == Decimal(700_000)
    assert _amount(r, "operating", rev.id) == Decimal(1_000_000)  # ورود نقد
    assert _amount(r, "operating", exp.id) == Decimal(-300_000)  # خروج نقد


def test_investing_fixed_asset_purchase(db, user):
    cash = get_account(db, cc.CASH)
    fixed = get_account(db, cc.FIXED_ASSETS)
    _post(db, user, [(fixed, 5_000_000, 0), (cash, 0, 5_000_000)])

    r = get_cash_flow(db, *PERIOD)
    assert r["net_investing"] == Decimal(-5_000_000)
    assert _amount(r, "investing", fixed.id) == Decimal(-5_000_000)
    assert r["net_operating"] == Decimal(0)


def test_financing_capital_injection(db, user):
    cash = get_account(db, cc.CASH)
    capital = db.query(Account).filter(Account.code == "3101").first()
    _post(db, user, [(cash, 8_000_000, 0), (capital, 0, 8_000_000)])

    r = get_cash_flow(db, *PERIOD)
    assert r["net_financing"] == Decimal(8_000_000)
    assert _amount(r, "financing", capital.id) == Decimal(8_000_000)


def test_internal_transfer_is_ignored(db, user):
    bank = get_account(db, cc.BANK)
    petty = get_account(db, cc.PETTY_CASH)
    _post(db, user, [(petty, 500_000, 0), (bank, 0, 500_000)])  # انتقال بانک ← تنخواه

    r = get_cash_flow(db, *PERIOD)
    assert r["net_operating"] == Decimal(0)
    assert r["net_investing"] == Decimal(0)
    assert r["net_financing"] == Decimal(0)
    assert r["net_change"] == Decimal(0)  # جابه‌جاییِ درون‌سازمانی نقد را عوض نمی‌کند


def test_net_change_reconciles_with_cash_balance(db, user):
    cash = get_account(db, cc.CASH)
    rev = get_account(db, cc.SALES_REVENUE)
    fixed = get_account(db, cc.FIXED_ASSETS)
    _post(db, user, [(cash, 2_000_000, 0), (rev, 0, 2_000_000)], on=date(2026, 1, 5))
    _post(db, user, [(fixed, 1_200_000, 0), (cash, 0, 1_200_000)], on=date(2026, 1, 20))

    r = get_cash_flow(db, *PERIOD)
    cash_ids = _cash_account_ids(db)
    opening_actual = _cash_balance(db, cash_ids, upto=date(2026, 1, 1), inclusive=False)
    closing_actual = _cash_balance(db, cash_ids, upto=date(2026, 1, 31), inclusive=True)
    # هویتِ بنیادین: جمعِ سه فعالیت = تغییرِ واقعیِ ماندهٔ نقد
    assert r["opening_cash"] == opening_actual
    assert r["net_change"] == closing_actual - opening_actual
    assert r["closing_cash"] == closing_actual
