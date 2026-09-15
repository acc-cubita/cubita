"""وارداتِ صورت‌حساب باید در تکرار بی‌اثر باشد.

**چه کم بود.** `import_statement_lines` یک `add_all`ِ خام بود و
`bank_statement_lines` هیچ قیدِ یکتایی نداشت. پس وارد کردنِ دوباره‌ی یک فایل کلِ
ردیف‌ها را **دوبرابر** می‌کرد.

و بی‌اثر نبود: `auto_match_statement` با «مبلغِ برابر و تاریخِ ±۳ روز» جفت می‌کند،
پس نسخه‌های تکراری به تراکنش‌های دیگری می‌چسبیدند و مغایرت‌گیریِ بانک — که کارش
پیداکردنِ همین اختلاف‌هاست — خودش منبعِ اختلاف می‌شد.
"""
from datetime import date
from decimal import Decimal

from app.models.accounting import Account
from app.models.banking import BankAccount, BankStatementLine
from app.schemas.banking import BankStatementLineIn
from app.services.banking import import_statement_lines

TODAY = date(2026, 3, 15)


def _bank(db) -> BankAccount:
    gl = db.query(Account).filter(Account.is_group.is_(False)).first()
    row = BankAccount(
        name="بانک سامان", account_number="۱۲۳۴", iban="IR00", gl_account_id=gl.id
    )
    db.add(row)
    db.flush()
    return row


def _line(**kw) -> BankStatementLineIn:
    kw.setdefault("line_date", TODAY)
    kw.setdefault("amount", Decimal(5_000_000))
    kw.setdefault("description", "واریز نقدی")
    return BankStatementLineIn(**kw)


def _count(db, bank_id) -> int:
    return db.query(BankStatementLine).filter(BankStatementLine.bank_account_id == bank_id).count()


# ─────────── کلیدِ قطعی: شماره‌ی مرجعِ بانک ───────────


def test_reimporting_the_same_file_adds_nothing(db):
    """**هسته‌ی این اصلاح.**"""
    bank = _bank(db)
    rows = [_line(external_ref="REF-1"), _line(amount=Decimal(2_000_000), external_ref="REF-2")]

    assert len(import_statement_lines(db, bank.id, rows)) == 2
    assert len(import_statement_lines(db, bank.id, rows)) == 0, (
        "*** وارداتِ دوباره ردیف ساخت ***"
    )
    assert _count(db, bank.id) == 2


def test_a_file_with_its_own_duplicate_ref_does_not_explode(db):
    """بدونِ گاردِ درونِ دسته، ایندکسِ یکتا `IntegrityError` می‌داد و **کلِ**
    واردات می‌افتاد — به‌جای اینکه فقط همان ردیفِ تکراری رد شود."""
    bank = _bank(db)
    created = import_statement_lines(
        db, bank.id, [_line(external_ref="REF-9"), _line(external_ref="REF-9")]
    )
    assert len(created) == 1
    assert _count(db, bank.id) == 1


def test_a_new_row_in_a_reimported_file_still_lands(db):
    bank = _bank(db)
    import_statement_lines(db, bank.id, [_line(external_ref="A")])

    created = import_statement_lines(db, bank.id, [_line(external_ref="A"), _line(external_ref="B")])
    assert len(created) == 1
    assert created[0].external_ref == "B"


# ─────────── بی‌مرجع: شمارشِ ردیف‌های هم‌شکل ───────────


def test_rows_without_a_reference_are_matched_by_shape(db):
    """همه‌ی بانک‌ها شماره‌ی مرجع نمی‌دهند."""
    bank = _bank(db)
    rows = [_line(), _line(amount=Decimal(9_000_000), description="کارمزد")]

    assert len(import_statement_lines(db, bank.id, rows)) == 2
    assert len(import_statement_lines(db, bank.id, rows)) == 0
    assert _count(db, bank.id) == 2


def test_two_genuinely_identical_transactions_both_land(db):
    """**ظریف‌ترین حالت، و دلیلِ اینکه شمارش است نه حذفِ ساده.**

    دو واریزِ واقعیِ ۵ میلیونی در یک روز با یک شرح کاملاً ممکن است. گاردِ تکرار
    نباید دومی را قربانی کند.
    """
    bank = _bank(db)
    assert len(import_statement_lines(db, bank.id, [_line(), _line()])) == 2
    assert _count(db, bank.id) == 2


def test_a_third_identical_row_is_the_only_one_added(db):
    """فایل سه ردیفِ یکسان دارد و دوتا از قبل هست ⇒ فقط یکی اضافه می‌شود."""
    bank = _bank(db)
    import_statement_lines(db, bank.id, [_line(), _line()])

    created = import_statement_lines(db, bank.id, [_line(), _line(), _line()])
    assert len(created) == 1
    assert _count(db, bank.id) == 3


def test_whitespace_in_the_description_does_not_fake_a_new_row(db):
    """فایل‌های بانک همان تراکنش را با فاصله‌گذاریِ متفاوت صادر می‌کنند."""
    bank = _bank(db)
    import_statement_lines(db, bank.id, [_line(description="واریز نقدی")])

    created = import_statement_lines(db, bank.id, [_line(description="  واریز   نقدی  ")])
    assert len(created) == 0, "*** فاصله‌ی اضافه یک ردیفِ تکراری ساخت ***"


# ─────────── چیزهایی که نباید عوض شوند ───────────


def test_a_different_day_is_a_different_row(db):
    bank = _bank(db)
    import_statement_lines(db, bank.id, [_line()])

    created = import_statement_lines(db, bank.id, [_line(line_date=date(2026, 3, 16))])
    assert len(created) == 1


def test_another_bank_account_is_not_deduplicated_against(db):
    """گارد باید per-account باشد؛ دو حساب می‌توانند تراکنشِ هم‌شکل داشته باشند."""
    first, second = _bank(db), _bank(db)
    import_statement_lines(db, first.id, [_line(external_ref="SAME")])

    created = import_statement_lines(db, second.id, [_line(external_ref="SAME")])
    assert len(created) == 1
