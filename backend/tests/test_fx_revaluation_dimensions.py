"""سندِ تسعیر باید بُعدهای همان مانده‌ای را که تسعیر می‌کند نگه دارد.

پیش از این، پیش‌نمایش فقط روی `(حساب، ارز)` گروه می‌شد. یعنی «دریافتنیِ ارزی» با
سه مشتری یک ردیف می‌شد و ردیفِ سندِ تسعیر بی‌تفصیلی و بی‌مرکز می‌نشست. دو پیامد
داشت و هر دو واقعی بودند:

* در حالتِ `strict`، `assert_entry_has_tafsili` جلوی صدورِ سند را می‌گرفت — یعنی
  تسعیر روی حسابِ تفصیلی‌پذیر **اصلاً کار نمی‌کرد**.
* در `hybrid` و `floating` بی‌صدا دفترِ تفصیلی را از حساب جدا می‌کرد: جمعِ حساب
  درست، تفکیکش غلط، و چون سند ویرایشِ ردیف ندارد، برای همیشه.

`models/analytic.py` می‌گوید سه بُعد روی ردیف می‌نشیند و «هرکدام جای خودش را
دارد». این فایل همان را برای تسعیر قفل می‌کند.
"""
from datetime import date, timedelta
from decimal import Decimal

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.analytic import AnalyticAccount
from app.models.cost_center import CostCenter
from app.models.currency import Currency, ExchangeRate
from app.models.tenant import Tenant
from app.services import accounting_ops as ops
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.tenant_context import session_tenant

TODAY = date(2026, 6, 1)


def _set_mode(db, mode: str) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = mode
    db.flush()


def _analytic(db, user, code: str, name: str) -> AnalyticAccount:
    row = AnalyticAccount(code=code, name=name, created_by_id=user.id)
    db.add(row)
    db.flush()
    return row


def _center(db, user, name: str) -> CostCenter:
    row = CostCenter(code="", name=name, kind="project", created_by_id=user.id)
    db.add(row)
    db.flush()
    return row


def _usd(db, user, rate: int = 60_000, on: date = TODAY) -> None:
    db.add(Currency(code="USD", name="دلار", created_by_id=user.id))
    db.add(
        ExchangeRate(currency_code="USD", rate_date=on, rate=Decimal(rate), created_by_id=user.id)
    )
    db.flush()


def _fx_line(account_id, *, fx: int, rial: int, **dims) -> JournalLine:
    return JournalLine(
        account_id=account_id,
        debit=Decimal(rial),
        credit=0,
        currency_code="USD",
        fx_amount=Decimal(fx),
        fx_rate=Decimal(rial) / Decimal(fx),
        **dims,
    )


def _post(db, user, lines: list[JournalLine], balance: int) -> JournalEntry:
    """ردیف‌های ارزی به‌علاوه‌ی یک طرفِ ریالیِ متوازن‌کننده."""
    equity = get_account(db, cc.RETAINED_EARNINGS)
    return make_journal_entry(
        db,
        TODAY,
        "خریدِ ارز",
        "manual",
        user,
        [*lines, JournalLine(account_id=equity.id, debit=0, credit=Decimal(balance))],
    )


def _receivable(db) -> Account:
    """حسابِ ارزیِ تفصیلی‌پذیر — همان «دریافتنیِ ارزی»ِ بندِ ۱۲."""
    account = get_account(db, cc.BANK)
    account.accepts_tafsili = True
    db.flush()
    return account


# ── تفکیک بر تفصیلی ─────────────────────────────────────────────────────────


def test_two_analytics_on_one_account_are_two_balances(db, user):
    """**قیدِ اصلی.** هر مشتری مانده‌ی ارزیِ خودش را دارد، نه یک کاسه‌ی مشترک."""
    _usd(db, user)
    account = _receivable(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    beta = _analytic(db, user, "B1", "شرکت بتا")
    _post(
        db,
        user,
        [
            _fx_line(account.id, fx=100, rial=5_000_000, analytic_id=alpha.id),
            _fx_line(account.id, fx=40, rial=2_000_000, analytic_id=beta.id),
        ],
        7_000_000,
    )

    rows = [r for r in ops.fx_revaluation_preview(db, TODAY)["items"] if r["account_id"] == account.id]
    assert len(rows) == 2
    by_name = {r["analytic_name"]: r for r in rows}
    assert by_name["شرکت آلفا"]["fx_balance"] == Decimal(100)
    assert by_name["شرکت آلفا"]["difference"] == Decimal(1_000_000)  # ۱۰۰ × (۶۰k − ۵۰k)
    assert by_name["شرکت بتا"]["fx_balance"] == Decimal(40)
    assert by_name["شرکت بتا"]["difference"] == Decimal(400_000)  # ۴۰ × (۶۰k − ۵۰k)
    assert by_name["شرکت آلفا"]["analytic_code"] == "A1"


def test_the_issued_lines_carry_the_dimensions(db, user):
    """ردیفِ سند باید همان بُعدی را داشته باشد که مانده از آن آمده."""
    _usd(db, user)
    account = _receivable(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    center = _center(db, user, "دفتر مرکزی")
    _post(
        db,
        user,
        [_fx_line(account.id, fx=100, rial=5_000_000, analytic_id=alpha.id, cost_center_id=center.id)],
        5_000_000,
    )

    out = ops.issue_fx_revaluation(db, user, TODAY, "")
    entry = db.get(JournalEntry, out["entry_id"])
    line = next(line for line in entry.lines if line.account_id == account.id)
    assert line.analytic_id == alpha.id
    assert line.cost_center_id == center.id
    assert "شرکت آلفا" in line.description  # وگرنه دو ردیفِ یک حساب در چاپ یکی‌اند


def test_a_balance_without_dimensions_is_still_one_row(db, user):
    """رگرسیون: نبودِ بُعد نباید چیزی را عوض کند — همان رفتارِ امروز."""
    _usd(db, user)
    bank = get_account(db, cc.BANK)
    _post(db, user, [_fx_line(bank.id, fx=100, rial=5_000_000)], 5_000_000)

    rows = [r for r in ops.fx_revaluation_preview(db, TODAY)["items"] if r["account_id"] == bank.id]
    assert len(rows) == 1
    assert rows[0]["analytic_id"] is None and rows[0]["cost_center_id"] is None


# ── حالتِ «اجباری» دیگر تسعیر را نمی‌بندد ────────────────────────────────────


def test_strict_mode_no_longer_blocks_revaluation(db, user):
    """**رگرسیونِ همان تله.** پیش از این `strict` صدورِ سند را رد می‌کرد."""
    _set_mode(db, "strict")
    _usd(db, user)
    account = _receivable(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    _post(db, user, [_fx_line(account.id, fx=100, rial=5_000_000, analytic_id=alpha.id)], 5_000_000)

    out = ops.issue_fx_revaluation(db, user, TODAY, "")
    assert out["net_difference"] == Decimal(1_000_000)


def test_strict_mode_does_not_strand_a_legacy_balance(db, user):
    """مانده‌ای که *پیش از* سخت‌گیرترشدنِ تنظیم بی‌تفصیلی ثبت شده.

    استدلالش همان است که `tafsili.py` برای سندِ برگشتی نوشته: قاعده‌ای که بعد از
    ثبتِ اصل سخت‌تر شده نباید کاربر را در مانده‌ای گیر بیندازد که نه می‌تواند
    تفصیلی‌دارش کند (سند ویرایشِ ردیف ندارد) نه تسعیرش.
    """
    _set_mode(db, "floating")  # روزی که مانده ثبت شد، تفصیلی خواسته نمی‌شد
    _usd(db, user)
    account = _receivable(db)
    _post(db, user, [_fx_line(account.id, fx=100, rial=5_000_000)], 5_000_000)
    _set_mode(db, "strict")  # و حالا قاعده سخت‌گیر شده

    out = ops.issue_fx_revaluation(db, user, TODAY, "")
    entry = db.get(JournalEntry, out["entry_id"])
    line = next(line for line in entry.lines if line.account_id == account.id)
    assert line.analytic_id is None  # سوراخ پنهان نشده — فقط مسدود نشده

    #: و همان ردیف در گزارشِ «بدونِ تفصیلی» دیده می‌شود: گزارش، نه گارد.
    from app.services.tafsili import find_missing_tafsili

    assert any(r["entry_id"] == entry.id for r in find_missing_tafsili(db))


# ── خاصیت‌هایی که نباید بشکنند ───────────────────────────────────────────────


def test_repeating_the_revaluation_still_finds_nothing(db, user):
    """§۱۹ با تفصیلی هم برقرار است: سند خودش ارزشِ دفتریِ هر بُعد را اصلاح می‌کند."""
    _usd(db, user)
    account = _receivable(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    beta = _analytic(db, user, "B1", "شرکت بتا")
    _post(
        db,
        user,
        [
            _fx_line(account.id, fx=100, rial=5_000_000, analytic_id=alpha.id),
            _fx_line(account.id, fx=40, rial=2_000_000, analytic_id=beta.id),
        ],
        7_000_000,
    )

    ops.issue_fx_revaluation(db, user, TODAY, "")
    again = ops.fx_revaluation_preview(db, TODAY)
    assert all(r["difference"] == 0 for r in again["items"])


def test_a_stale_rate_reports_its_own_date(db, user):
    """§۱۶ — نرخِ کهنه حدس نیست، ولی نرخِ روز هم نیست و باید دیده شود."""
    stale_day = TODAY - timedelta(days=90)
    _usd(db, user, on=stale_day)
    bank = get_account(db, cc.BANK)
    _post(db, user, [_fx_line(bank.id, fx=100, rial=5_000_000)], 5_000_000)

    row = next(r for r in ops.fx_revaluation_preview(db, TODAY)["items"] if r["account_id"] == bank.id)
    assert row["rate_date"] == stale_day
    assert row["rate"] == Decimal(60_000)
