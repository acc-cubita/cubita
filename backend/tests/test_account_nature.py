"""ماهیتِ حساب: مشتق‌شدن از نوع، بازنویسیِ صریح، و گزارشِ خلافِ ماهیت.

قیدِ اصلیِ این قابلیت که تست‌ها نگهش می‌دارند: **ماهیت هیچ ثبتی را نمی‌شکند.**
خلافِ ماهیت شدن گاهی واقعاً درست است (اضافه‌برداشتِ بانکی، پیش‌دریافتِ مشتری)، پس
اگر روزی کسی این را به گارد تبدیل کند، `test_violation_does_not_block_posting`
قرمز می‌شود.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models.accounting import NATURE_BY_TYPE, Account, JournalEntry, JournalLine
from app.services import reports as reports_service


def _account(db, code: str) -> Account:
    return db.query(Account).filter(Account.code == code).one()


def _post(db, *, debit_code: str, credit_code: str, amount: int) -> JournalEntry:
    """یک سندِ ساده‌ی دوردیفه. مستقیم روی مدل، چون این تست‌ها کارِ روتر را نمی‌سنجند."""
    user_id = db.query(JournalEntry.created_by_id).scalar()
    if user_id is None:  # pragma: no cover — دیتابیسِ تستی همیشه یک سند دارد
        from app.models.user import User

        user_id = db.query(User.id).scalar()
    entry = JournalEntry(entry_date=date(2026, 1, 1), description="آزمون", created_by_id=user_id)
    entry.lines = [
        JournalLine(account_id=_account(db, debit_code).id, debit=Decimal(amount), credit=Decimal(0)),
        JournalLine(account_id=_account(db, credit_code).id, debit=Decimal(0), credit=Decimal(amount)),
    ]
    db.add(entry)
    db.flush()
    return entry


# ── مشتق‌شدن از نوع ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "code,expected",
    [("1101", "debit"), ("2101", "credit"), ("3101", "credit"), ("4101", "credit"), ("5101", "debit")],
)
def test_nature_is_derived_from_type_when_unset(db, code, expected):
    """چارتِ کاشته‌شده هیچ ماهیتِ صریحی ندارد و نباید هم داشته باشد.

    این همان چیزی است که مهاجرتِ ۰۰۸۷ را بی‌خطر می‌کند: هیچ ردیفی backfill نشد، پس
    هیچ حسابی معنایش عوض نشد.
    """
    acc = _account(db, code)
    assert acc.nature is None
    assert acc.effective_nature == expected


def test_derivation_covers_every_account_type(db):
    """اگر روزی نوعِ تازه‌ای به ACCOUNT_TYPES اضافه شود، این تست یادآوری می‌کند."""
    from app.models.accounting import ACCOUNT_TYPES

    assert set(NATURE_BY_TYPE) == set(ACCOUNT_TYPES)


def test_explicit_nature_overrides_the_type(db):
    acc = _account(db, "1101")
    acc.nature = "any"
    db.flush()
    assert acc.effective_nature == "any", "مقدارِ صریح باید بر مشتق‌شده بچربد"


# ── گزارش ────────────────────────────────────────────────────────────────────


def test_report_flags_an_account_against_its_nature(db):
    """صندوقِ بستانکار = پول از جایی خرج شده که در آن نبوده."""
    _post(db, debit_code="5104", credit_code="1101", amount=1_000_000)

    rows = reports_service.get_nature_violations(db, None, None)
    codes = {r["account_code"] for r in rows}

    assert "1101" in codes, "صندوقِ بستانکار باید گزارش شود"
    assert "5104" not in codes, "هزینه‌ی بدهکار طبیعی است و نباید گزارش شود"

    cash = next(r for r in rows if r["account_code"] == "1101")
    assert cash["nature"] == "debit"
    assert cash["balance_side"] == "credit"
    assert cash["balance"] == Decimal(1_000_000), "مانده باید قدرمطلق باشد، نه منفی"
    assert cash["nature_is_explicit"] is False


def test_nature_any_is_never_a_violation(db):
    """حسابِ واسط هر دو سمت برایش طبیعی است — به همین کار می‌آید."""
    cash = _account(db, "1101")
    cash.nature = "any"
    db.flush()

    _post(db, debit_code="5104", credit_code="1101", amount=1_000_000)

    codes = {r["account_code"] for r in reports_service.get_nature_violations(db, None, None)}
    assert "1101" not in codes


def test_explicit_nature_changes_what_counts_as_violation(db):
    """ماهیتِ صریح باید *واقعاً* معیار را عوض کند، نه فقط ذخیره شود."""
    cash = _account(db, "1101")
    cash.nature = "credit"  # عمداً خلافِ نوعِ دارایی
    db.flush()

    _post(db, debit_code="1101", credit_code="4101", amount=500_000)

    rows = reports_service.get_nature_violations(db, None, None)
    cash_row = next((r for r in rows if r["account_code"] == "1101"), None)
    assert cash_row is not None, "صندوقِ بدهکار با ماهیتِ بستانکار باید تخلف باشد"
    assert cash_row["nature_is_explicit"] is True


def test_zero_balance_is_not_a_violation(db):
    """حسابی که بدهکار و بستانکارش برابر است مانده ندارد، پس خلافِ ماهیت هم نیست."""
    _post(db, debit_code="5104", credit_code="1101", amount=300_000)
    _post(db, debit_code="1101", credit_code="4101", amount=300_000)

    codes = {r["account_code"] for r in reports_service.get_nature_violations(db, None, None)}
    assert "1101" not in codes


def test_violation_does_not_block_posting(db):
    """**قیدِ اصلی.** گزارش است، نه گارد — سند باید بی‌هیچ خطایی ثبت شود."""
    entry = _post(db, debit_code="5104", credit_code="1101", amount=2_000_000)

    assert entry.id is not None
    assert db.get(JournalEntry, entry.id) is not None
    assert reports_service.get_nature_violations(db, None, None), "و در عوض فقط گزارش شود"


# ── عنوانِ دوم ───────────────────────────────────────────────────────────────


def test_name2_defaults_to_empty_and_never_shadows_the_persian_name(db):
    acc = _account(db, "1101")
    assert acc.name2 == ""
    acc.name2 = "Cash"
    db.flush()
    assert acc.name == "صندوق", "عنوانِ دوم نباید نامِ فارسی را عوض کند"
    assert acc.name2 == "Cash"
