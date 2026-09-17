"""تطبیقِ بانکی — چهار تابعی که پول را تطبیق می‌دهند و هیچ‌کدام تست نداشتند.

`GAPS.md` این را موردِ دوم اولویت گذاشته بود: «پنج تابعِ پول‌جابه‌جاکن با صفر
پوشش — بزرگ‌ترین ریسکِ درستیِ تکی». در بررسی معلوم شد `import_statement_lines`
از ۲۳ شهریور نُه تست دارد؛ **چهار تای دیگر واقعاً صفر بودند**:
`auto_match_statement` · `match_statement_line` · `unmatch_statement_line` ·
`get_reconciliation_summary`.

**چرا این‌ها خطرناک‌اند.** مغایرت‌گیری کارش پیداکردنِ اختلافِ دفترِ ما با دفترِ
بانک است. اگر خودش اشتباه جفت کند، اختلافِ واقعی **پنهان** می‌شود — و این تنها
جایی است که قرار بود پیدایش کند. خطایی هم در کار نیست؛ فقط عددی که درست
به‌نظر می‌آید.

**قیدی که این فایل نگه می‌دارد:** هیچ تراکنشی دوبار تطبیق نمی‌خورد، و هر
جفت‌شدنی که باز شود تراکنش را واقعاً آزاد می‌کند.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account
from app.models.banking import BankAccount, BankStatementLine, BankTransaction
from app.schemas.banking import BankStatementLineIn
from app.services.banking import (
    auto_match_statement,
    get_reconciliation_summary,
    import_statement_lines,
    match_statement_line,
    unmatch_statement_line,
)

TODAY = date(2026, 3, 15)
AMOUNT = Decimal(5_000_000)


def _bank(db, name="بانک تطبیق") -> BankAccount:
    gl = db.query(Account).filter(Account.is_group.is_(False)).first()
    row = BankAccount(name=name, account_number="۹۹۹", iban="IR99", gl_account_id=gl.id)
    db.add(row)
    db.flush()
    return row


def _txn(db, user, bank, *, amount=AMOUNT, on=TODAY) -> BankTransaction:
    """تراکنشِ سیستم — یعنی آنچه *ما* ثبت کرده‌ایم."""
    row = BankTransaction(
        bank_account_id=bank.id, transaction_date=on, amount=amount,
        description="سیستم", created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    return row


def _import(db, bank, *, amount=AMOUNT, on=TODAY, ref=None) -> BankStatementLine:
    """ردیفِ صورت‌حساب — یعنی آنچه *بانک* می‌گوید."""
    (line,) = import_statement_lines(
        db, bank.id, [BankStatementLineIn(line_date=on, amount=amount, description="بانک", external_ref=ref)]
    )
    return line


# ─────────────── تطبیقِ خودکار ───────────────


def test_a_matching_pair_is_linked_both_ways(db, user):
    """جفت‌شدن باید **هر دو سر** را علامت بزند، نه یکی را.

    اگر فقط ردیفِ صورت‌حساب علامت بخورد، همان تراکنش دفعه‌ی بعد دوباره کاندید
    می‌شود و به ردیفِ دیگری می‌چسبد.
    """
    bank = _bank(db)
    txn = _txn(db, user, bank)
    line = _import(db, bank)

    assert auto_match_statement(db, bank.id) == 1
    db.refresh(line)
    db.refresh(txn)
    assert line.matched_transaction_id == txn.id
    assert txn.is_reconciled is True


def test_a_transaction_is_never_used_twice(db, user):
    """**هسته‌ی این فایل.** دو ردیفِ هم‌مبلغ و یک تراکنش → فقط یکی جفت می‌شود.

    بدونِ `used_txn_ids`، هر دو ردیف به همان تراکنش می‌چسبیدند و مغایرت‌گیری
    می‌گفت همه‌چیز تطبیق شده در حالی که یک ردیفِ بانک بی‌پشتوانه است.
    """
    bank = _bank(db)
    _txn(db, user, bank)
    a = _import(db, bank, ref="A")
    b = _import(db, bank, ref="B")

    assert auto_match_statement(db, bank.id) == 1
    db.refresh(a)
    db.refresh(b)
    linked = [x for x in (a, b) if x.matched_transaction_id is not None]
    assert len(linked) == 1, "*** یک تراکنش به دو ردیف چسبید ***"


@pytest.mark.parametrize("delta_days", [0, 1, -1, 3, -3])
def test_dates_within_three_days_match(db, user, delta_days):
    bank = _bank(db)
    _txn(db, user, bank, on=TODAY)
    _import(db, bank, on=TODAY + timedelta(days=delta_days))
    assert auto_match_statement(db, bank.id) == 1


@pytest.mark.parametrize("delta_days", [4, -4, 10])
def test_dates_beyond_three_days_do_not_match(db, user, delta_days):
    """مرز **بسته** است: سه روز بله، چهار روز نه."""
    bank = _bank(db)
    _txn(db, user, bank, on=TODAY)
    _import(db, bank, on=TODAY + timedelta(days=delta_days))
    assert auto_match_statement(db, bank.id) == 0


def test_a_different_amount_does_not_match(db, user):
    bank = _bank(db)
    _txn(db, user, bank, amount=AMOUNT)
    _import(db, bank, amount=AMOUNT + 1)
    assert auto_match_statement(db, bank.id) == 0


def test_a_deposit_never_matches_a_withdrawal(db, user):
    """مبلغ **علامت‌دار** است در هر دو سو؛ قدرِ مطلق مقایسه نمی‌شود.

    اگر می‌شد، برداشتِ پنج میلیون به واریزِ پنج میلیون می‌چسبید — دو خطای
    قرینه که همدیگر را پنهان می‌کنند.
    """
    bank = _bank(db)
    _txn(db, user, bank, amount=AMOUNT)
    _import(db, bank, amount=-AMOUNT)
    assert auto_match_statement(db, bank.id) == 0


def test_another_bank_account_is_never_matched_against(db, user):
    bank_a = _bank(db, "حسابِ الف")
    bank_b = _bank(db, "حسابِ ب")
    _txn(db, user, bank_b)
    _import(db, bank_a)
    assert auto_match_statement(db, bank_a.id) == 0


def test_an_already_reconciled_transaction_is_not_reused(db, user):
    """تراکنشی که قبلاً تطبیق خورده، کاندیدِ دور بعد نیست."""
    bank = _bank(db)
    _txn(db, user, bank)
    _import(db, bank, ref="A")
    assert auto_match_statement(db, bank.id) == 1

    _import(db, bank, ref="B")
    assert auto_match_statement(db, bank.id) == 0


def test_running_twice_matches_nothing_new(db, user):
    """اجرای دوباره باید بی‌اثر باشد — وگرنه دکمه‌ی «تطبیق خودکار» خطرناک است."""
    bank = _bank(db)
    _txn(db, user, bank)
    _import(db, bank)
    assert auto_match_statement(db, bank.id) == 1
    assert auto_match_statement(db, bank.id) == 0


# ─────────────── تطبیقِ دستی ───────────────


def test_manual_match_links_both_sides(db, user):
    bank = _bank(db)
    txn = _txn(db, user, bank)
    line = _import(db, bank)

    out = match_statement_line(db, line.id, txn.id)
    db.refresh(txn)
    assert out.matched_transaction_id == txn.id
    assert txn.is_reconciled is True


def test_rematching_releases_the_previous_transaction(db, user):
    """**ظریف‌ترین رفتارِ این ماژول.** ردیفی که از تراکنشِ اول به دوم منتقل
    می‌شود، باید اولی را آزاد کند.

    بدونِ این، تراکنشِ اول برای همیشه «تطبیق‌شده» می‌ماند در حالی که هیچ ردیفی
    به آن اشاره نمی‌کند — یعنی از فهرستِ مغایرت‌ها ناپدید می‌شود بی‌آنکه واقعاً
    تطبیق شده باشد.
    """
    bank = _bank(db)
    first = _txn(db, user, bank)
    second = _txn(db, user, bank)
    line = _import(db, bank)

    match_statement_line(db, line.id, first.id)
    match_statement_line(db, line.id, second.id)

    db.refresh(first)
    db.refresh(second)
    assert first.is_reconciled is False, "*** تراکنشِ قبلی آزاد نشد ***"
    assert second.is_reconciled is True


def test_matching_across_bank_accounts_is_refused(db, user):
    bank_a = _bank(db, "الف")
    bank_b = _bank(db, "ب")
    line = _import(db, bank_a)
    foreign = _txn(db, user, bank_b)

    with pytest.raises(HTTPException) as err:
        match_statement_line(db, line.id, foreign.id)
    assert err.value.status_code == 400


def test_matching_an_unknown_line_is_404(db, user):
    import uuid
    bank = _bank(db)
    txn = _txn(db, user, bank)
    with pytest.raises(HTTPException) as err:
        match_statement_line(db, uuid.uuid4(), txn.id)
    assert err.value.status_code == 404


def test_matching_an_unknown_transaction_is_400(db, user):
    import uuid
    bank = _bank(db)
    line = _import(db, bank)
    with pytest.raises(HTTPException) as err:
        match_statement_line(db, line.id, uuid.uuid4())
    assert err.value.status_code == 400


# ─────────────── بازکردنِ تطبیق ───────────────


def test_unmatching_frees_the_transaction(db, user):
    """آزادکردن باید تراکنش را **واقعاً** به فهرستِ تطبیق‌نشده برگرداند."""
    bank = _bank(db)
    txn = _txn(db, user, bank)
    line = _import(db, bank)
    match_statement_line(db, line.id, txn.id)

    out = unmatch_statement_line(db, line.id)
    db.refresh(txn)
    assert out.matched_transaction_id is None
    assert txn.is_reconciled is False


def test_an_unmatched_line_can_be_unmatched_again(db, user):
    """بی‌اثر در تکرار — دو بار کلیک نباید خطا بدهد."""
    bank = _bank(db)
    line = _import(db, bank)
    assert unmatch_statement_line(db, line.id).matched_transaction_id is None
    assert unmatch_statement_line(db, line.id).matched_transaction_id is None


def test_unmatch_then_auto_match_pairs_again(db, user):
    """چرخه‌ی کامل: تراکنشِ آزادشده باید دوباره کاندید شود."""
    bank = _bank(db)
    txn = _txn(db, user, bank)
    line = _import(db, bank)
    assert auto_match_statement(db, bank.id) == 1

    unmatch_statement_line(db, line.id)
    assert auto_match_statement(db, bank.id) == 1
    db.refresh(line)
    assert line.matched_transaction_id == txn.id


def test_unmatching_an_unknown_line_is_404(db, user):
    import uuid
    with pytest.raises(HTTPException) as err:
        unmatch_statement_line(db, uuid.uuid4())
    assert err.value.status_code == 404


# ─────────────── خلاصه‌ی مغایرت ───────────────


def test_summary_counts_and_totals(db, user):
    bank = _bank(db)
    _txn(db, user, bank)
    _import(db, bank, ref="A")
    _import(db, bank, ref="B", amount=Decimal(3_000_000), on=TODAY + timedelta(days=30))

    auto_match_statement(db, bank.id)
    s = get_reconciliation_summary(db, bank.id)

    assert s["statement_total"] == Decimal(8_000_000)
    assert s["matched_count"] == 1
    assert len(s["unmatched_statement_lines"]) == 1
    assert s["unreconciled_system_transactions"] == []


def test_summary_is_scoped_to_one_bank_account(db, user):
    """خلاصه‌ی یک حساب نباید ردیف یا تراکنشِ حسابِ دیگر را بشمارد."""
    bank_a = _bank(db, "الف")
    bank_b = _bank(db, "ب")
    _import(db, bank_a, amount=Decimal(1_000))
    _import(db, bank_b, amount=Decimal(9_999))
    _txn(db, user, bank_b)

    s = get_reconciliation_summary(db, bank_a.id)
    assert s["statement_total"] == Decimal(1_000)
    assert s["unreconciled_system_transactions"] == []


def test_an_empty_account_summarises_to_zero_not_an_error(db, user):
    bank = _bank(db)
    s = get_reconciliation_summary(db, bank.id)
    assert s["statement_total"] == Decimal(0)
    assert s["matched_count"] == 0
    assert s["unmatched_statement_lines"] == []


def test_summary_reflects_an_unmatch(db, user):
    """بازکردنِ تطبیق باید هم شمارش و هم هر دو فهرست را برگرداند."""
    bank = _bank(db)
    _txn(db, user, bank)
    line = _import(db, bank)
    auto_match_statement(db, bank.id)

    unmatch_statement_line(db, line.id)
    s = get_reconciliation_summary(db, bank.id)
    assert s["matched_count"] == 0
    assert len(s["unmatched_statement_lines"]) == 1
    assert len(s["unreconciled_system_transactions"]) == 1
