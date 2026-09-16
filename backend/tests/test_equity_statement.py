"""صورت تغییرات در حقوق صاحبان سهام — چهارمین صورتِ الزامی.

**چرا تا امروز ممکن نبود.** ورودی‌اش وجود نداشت: آورده و برداشتِ مالک فقط سندِ
دستی بودند. مهاجرتِ ۰۱۵۹ داده را ساخت؛ این گزارش مصرفش می‌کند.

**تلهٔ اصلی که این فایل گاردش می‌کند:** وسوسه این بود که گزارش از جدولِ
`owner_transactions` ساخته شود. آن کار **غلط** است — روی تولید یک آورده‌ی ۲۰۰
میلیونی به‌صورتِ سندِ دستی ثبت شده که هیچ `OwnerTransaction`ی ندارد. اگر فقط
جدول خوانده شود، آن مبلغ از گزارش می‌افتد و «ماندهٔ پایان دوره» با ترازنامه
نمی‌خواند — نقضِ قاعده‌ی ۱۶۲.

پس مرجع، **دفتر** است و طبقه‌بندی از تراکنش‌ها می‌آید.
"""
from datetime import date, timedelta
from decimal import Decimal

from app.models.accounting import JournalEntry, JournalLine
from app.models.inventory import Contact
from app.schemas.owner_transactions import OwnerTransactionIn
from app.services import chart_codes as cc
from app.services.common import get_account, get_or_create_account, number_lines
from app.services.owner_transactions import create_owner_transaction
from app.services.reports import get_balance_sheet, get_equity_statement
from tests.factories import make_contact

TODAY = date(2026, 6, 15)
PERIOD_FROM = date(2026, 6, 1)
PERIOD_TO = date(2026, 6, 30)


def _partner(db, name="شریکِ آزمون") -> Contact:
    contact = make_contact(db, name=name)
    contact.is_shareholder = True
    contact.share_percent = Decimal(50)
    db.flush()
    return contact


def _post(db, user, contact, kind, amount, on=TODAY):
    return create_owner_transaction(
        db,
        OwnerTransactionIn(
            type=kind, transaction_date=on, contact_id=contact.id,
            amount=Decimal(amount), method="cash",
        ),
        user,
    )


def _manual_capital_entry(db, user, amount, on=TODAY) -> JournalEntry:
    """همان شکلی که آورده‌ی ۲۰۰ میلیونی روی تولید ثبت شده: سندِ دستی."""
    capital = get_account(db, cc.OWNER_CAPITAL)
    cash = get_account(db, cc.CASH)
    entry = JournalEntry(
        number=90_000 + int(amount) % 1000,
        entry_date=on,
        description="آورده‌ی نقدیِ مالک",
        source_type="manual",
        created_by_id=user.id,
        lines=number_lines([
            JournalLine(account_id=cash.id, debit=Decimal(amount), credit=0),
            JournalLine(account_id=capital.id, debit=0, credit=Decimal(amount)),
        ]),
    )
    db.add(entry)
    db.flush()
    return entry


def _statement(db, **kw):
    return get_equity_statement(db, kw.get("date_from", PERIOD_FROM), kw.get("date_to", PERIOD_TO))


# ─────────────── تلهٔ اصلی: سندِ دستی نباید بیفتد ───────────────


def test_a_manual_capital_entry_is_not_lost(db, user):
    """**هسته‌ی این گزارش.**

    آورده‌ای که با سندِ دستی ثبت شده هیچ `OwnerTransaction`ی ندارد. اگر گزارش از
    جدولِ تراکنش‌ها ساخته می‌شد، این مبلغ بی‌صدا از گزارش می‌افتاد.
    """
    _manual_capital_entry(db, user, 200_000_000)
    result = _statement(db)

    assert result["closing_equity"] >= Decimal(200_000_000), (
        "*** آورده‌ی سندِ دستی از گزارش افتاد ***"
    )
    #: نوع‌دار نیست، پس در «سایر تغییرات» می‌نشیند — نه در «آورده‌ی سرمایه».
    assert result["other_changes"] >= Decimal(200_000_000)
    assert result["contributions"] == Decimal(0)


def test_the_equation_always_holds(db, user):
    """اول دوره + آورده − برداشت + سایر = پایان دوره. قاعده‌ی ۱۶۲."""
    partner = _partner(db)
    _manual_capital_entry(db, user, 50_000_000)
    _post(db, user, partner, "capital_contribution", 30_000_000)
    _post(db, user, partner, "capital_withdrawal", 10_000_000)

    r = _statement(db)
    assert r["opening_equity"] + r["contributions"] - r["withdrawals"] + r["other_changes"] == r["closing_equity"]
    assert r["reconciled"] is True


# ─────────────── طبقه‌بندیِ درست ───────────────


def test_a_typed_contribution_lands_in_contributions(db, user):
    partner = _partner(db)
    _post(db, user, partner, "capital_contribution", 40_000_000)
    r = _statement(db)
    assert r["contributions"] == Decimal(40_000_000)
    assert r["withdrawals"] == Decimal(0)


def test_a_typed_withdrawal_lands_in_withdrawals(db, user):
    partner = _partner(db)
    _post(db, user, partner, "capital_withdrawal", 7_000_000)
    r = _statement(db)
    assert r["withdrawals"] == Decimal(7_000_000)
    assert r["contributions"] == Decimal(0)


def test_partner_loans_never_appear_in_equity(db, user):
    """**وامِ شریک حقوق صاحبان سهام نیست.**

    اگر «جاری شرکا» به این گزارش راه پیدا کند، سرمایه‌ی شرکت با پولِ قرضی باد
    می‌کند — دقیقاً همان چیزی که تفکیکِ بدهی/مالکیت جلویش را می‌گیرد.
    """
    partner = _partner(db)
    _post(db, user, partner, "loan_to_entity", 90_000_000)
    _post(db, user, partner, "repayment_to_partner", 20_000_000)

    r = _statement(db)
    assert r["contributions"] == Decimal(0)
    assert r["withdrawals"] == Decimal(0)
    assert r["other_changes"] == Decimal(0), "*** وامِ شریک وارد حقوق صاحبان سهام شد ***"


def test_a_voided_transaction_is_excluded(db, user):
    """تراکنشِ باطل نباید در تفکیکِ شریک بماند."""
    from app.models.owner_transactions import OwnerTransaction
    from datetime import datetime, timezone

    partner = _partner(db)
    txn = _post(db, user, partner, "capital_contribution", 15_000_000)
    before = _statement(db)["contributions"]

    txn.voided_at = datetime.now(timezone.utc)
    db.flush()
    after = _statement(db)

    assert before == Decimal(15_000_000)
    assert after["contributions"] == Decimal(0)
    assert not any(r["contributed"] for r in after["partner_rows"])


# ─────────────── تفکیکِ شریک ───────────────


def test_each_partner_gets_their_own_row(db, user):
    one = _partner(db, name="شریکِ الف")
    two = _partner(db, name="شریکِ ب")
    _post(db, user, one, "capital_contribution", 60_000_000)
    _post(db, user, two, "capital_contribution", 40_000_000)
    _post(db, user, two, "capital_withdrawal", 5_000_000)

    rows = {r["contact_name"]: r for r in _statement(db)["partner_rows"]}
    assert rows["شریکِ الف"]["contributed"] == Decimal(60_000_000)
    assert rows["شریکِ ب"]["contributed"] == Decimal(40_000_000)
    assert rows["شریکِ ب"]["withdrawn"] == Decimal(5_000_000)


def test_loans_stay_out_of_the_partner_rows(db, user):
    """تفکیکِ شریک فقط سرمایه است. وام آن‌جا جایی ندارد."""
    partner = _partner(db)
    _post(db, user, partner, "loan_to_entity", 80_000_000)
    assert _statement(db)["partner_rows"] == []


# ─────────────── بازه ───────────────


def test_movements_before_the_period_are_opening_not_change(db, user):
    partner = _partner(db)
    _post(db, user, partner, "capital_contribution", 25_000_000, on=PERIOD_FROM - timedelta(days=10))
    r = _statement(db)

    assert r["opening_equity"] == Decimal(25_000_000)
    assert r["contributions"] == Decimal(0), "*** حرکتِ پیش از دوره داخلِ دوره شمرده شد ***"
    assert r["closing_equity"] == Decimal(25_000_000)


def test_movements_after_the_period_are_excluded(db, user):
    partner = _partner(db)
    _post(db, user, partner, "capital_contribution", 12_000_000, on=PERIOD_TO + timedelta(days=5))
    r = _statement(db)
    assert r["contributions"] == Decimal(0)
    assert r["closing_equity"] == Decimal(0)


# ─────────────── سود دوره بیرونِ تساوی است ───────────────


def test_net_profit_is_reported_but_not_folded_into_equity(db, user):
    """تا سندِ اختتامیه زده نشود، سودِ دوره در هیچ حسابِ حقوق صاحبان سهامی ننشسته.

    یکی‌کردنشان یعنی دوبار شمردنِ سود در سالی که بسته شده — همان تفکیکی که
    ترازنامه با `current_period_profit` رعایت می‌کند.
    """
    partner = _partner(db)
    _post(db, user, partner, "capital_contribution", 10_000_000)

    sales = get_or_create_account(
        db, "test_income_for_equity", code="4199", name="درآمدِ آزمون",
        acc_type="income", parent_code="4",
    )
    cash = get_account(db, cc.CASH)
    db.add(JournalEntry(
        number=91_001, entry_date=TODAY, description="فروشِ آزمون", source_type="manual",
        created_by_id=user.id,
        lines=number_lines([
            JournalLine(account_id=cash.id, debit=Decimal(3_000_000), credit=0),
            JournalLine(account_id=sales.id, debit=0, credit=Decimal(3_000_000)),
        ]),
    ))
    db.flush()

    r = _statement(db)
    assert r["net_profit"] == Decimal(3_000_000)
    #: سود در مانده‌ی پایان دوره نیست — تساوی بی آن برقرار است.
    assert r["opening_equity"] + r["contributions"] - r["withdrawals"] + r["other_changes"] == r["closing_equity"]
    assert r["closing_equity"] == Decimal(10_000_000)


def test_the_closing_equity_matches_the_balance_sheet(db, user):
    """قاعده‌ی ۱۶۲ — `EndingEquity → StatementOfFinancialPosition`."""
    partner = _partner(db)
    _manual_capital_entry(db, user, 100_000_000)
    _post(db, user, partner, "capital_contribution", 20_000_000)
    _post(db, user, partner, "capital_withdrawal", 5_000_000)

    statement = _statement(db)
    sheet = get_balance_sheet(db, PERIOD_TO)
    assert statement["closing_equity"] == sheet["total_equity"], (
        "*** مانده‌ی پایان دوره با ترازنامه نمی‌خواند ***"
    )


# ─────────────── اجزاء ───────────────


def test_components_show_each_equity_account(db, user):
    partner = _partner(db)
    _post(db, user, partner, "capital_contribution", 8_000_000)
    capital_code = get_account(db, cc.OWNER_CAPITAL).code

    rows = {c["account_code"]: c for c in _statement(db)["components"]}
    assert capital_code in rows
    assert rows[capital_code]["change"] == Decimal(8_000_000)
    assert rows[capital_code]["closing"] == rows[capital_code]["opening"] + Decimal(8_000_000)


def test_untouched_equity_accounts_are_omitted(db, user):
    """حسابِ اختتامیه/افتتاحیه که هیچ حرکتی ندارد، ردیفِ صفر نمی‌سازد."""
    partner = _partner(db)
    _post(db, user, partner, "capital_contribution", 1_000_000)
    for c in _statement(db)["components"]:
        assert c["opening"] or c["change"]


# ─────────────── اندپوینت ───────────────


def test_the_endpoint_returns_the_statement(client, db, user):
    partner = _partner(db)
    _post(db, user, partner, "capital_contribution", 55_000_000)
    db.commit()

    response = client.get(
        "/api/reports/equity-statement",
        params={"date_from": PERIOD_FROM.isoformat(), "date_to": PERIOD_TO.isoformat()},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(body["contributions"]) == Decimal(55_000_000)
    assert body["reconciled"] is True


def test_date_to_is_required(client, db):
    """«مانده‌ی پایان دوره» بی تاریخِ پایان معنا ندارد."""
    assert client.get("/api/reports/equity-statement").status_code == 422
