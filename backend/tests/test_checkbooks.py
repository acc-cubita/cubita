"""دسته‌چک — کنترلِ برگ، سیاستِ شماره، و ویرایشِ ساختاری.

**قیدِ اصلی (§۱۲):** یک برگِ فیزیکی فقط یک بار خرج می‌شود. تا پیش از این
`create_check` مقدارِ `checkbook_id` را بی‌هیچ سنجشی می‌نشاند، پس دو چک با شماره‌ی
یکسان از یک دسته هر دو ثبت می‌شدند و «برگِ مانده» — که مشتق است — عددِ دروغ می‌داد.

**مرزی که این فایل قفلش می‌کند:** سیاستِ `cheque_number_control` فقط تعیین می‌کند
چکِ پرداختنیِ **بی‌دسته** مجاز است یا نه. بازه و تکراری‌نبودن در هر دو حالت سنجیده
می‌شوند؛ آن‌ها یکپارچگیِ داده‌اند نه سیاست.

**چرا دسته‌ی اختصاصی در هر تست:** فیکسچرِ `db` برمی‌گردد ولی تست‌های `client` در
همان مستأجر کامیت می‌کنند، پس شمارشِ مطلق روی داده‌ی مشترک به ترتیبِ اجرا وابسته
می‌شود.
"""
import itertools
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.banking import BankAccount, Check
from app.models.tenant import Tenant
from app.schemas.banking import CheckbookIn, CheckbookUpdateIn, CheckIn
from app.services import chart_codes as cc
from app.services import checkbooks as svc
from app.services.check_ops import create_check, update_check_status
from app.services.common import get_account
from app.tenant_context import session_tenant

TODAY = date(1405, 3, 10)

_SEQ = itertools.count(1)


def _bank(db, name=None) -> BankAccount:
    acct = BankAccount(
        name=name or f"بانکِ آزمون {next(_SEQ)}",
        gl_account_id=get_account(db, cc.BANK).id,
    )
    db.add(acct)
    db.flush()
    return acct


def _book(db, user, bank=None, **kw):
    bank = bank or _bank(db)
    data = CheckbookIn(
        bank_account_id=bank.id,
        serial=kw.get("serial", f"SR-{next(_SEQ)}"),
        first_number=kw.get("first_number", "000101"),
        last_number=kw.get("last_number", "000110"),
        leaf_count=kw.get("leaf_count", 0),
        issue_date=TODAY,
    )
    return svc.create_checkbook(db, data, user)


def _issue(db, user, *, number, book=None, kind="payable", amount=1_000_000):
    return create_check(
        db,
        CheckIn(
            type=kind,
            number=number,
            amount=Decimal(amount),
            issue_date=TODAY,
            due_date=TODAY + timedelta(days=30),
            checkbook_id=book.id if book else None,
        ),
        user,
    )


def _set_mode(db, mode: str) -> None:
    tenant = db.get(Tenant, session_tenant(db))
    svc.set_control_mode(tenant, mode)
    db.flush()


# ── قیدِ اصلی: برگ دو بار خرج نمی‌شود ────────────────────────────────────────


def test_a_leaf_cannot_be_spent_twice(db, user):
    """§۱۲ — همان کاغذ، همان شماره، دو تعهد. این باید غیرممکن باشد."""
    book = _book(db, user)
    _issue(db, user, number="000103", book=book)

    with pytest.raises(HTTPException) as e:
        _issue(db, user, number="000103", book=book)
    assert e.value.status_code == 409
    assert "000103" in e.value.detail


def test_a_voided_cheque_does_not_free_its_leaf(db, user):
    """§۱۴ — برگی که یک بار نوشته شد سابقه دارد؛ برگشت‌خوردنش آزادش نمی‌کند."""
    book = _book(db, user)
    check = _issue(db, user, number="000104", book=book)
    update_check_status(db, check.id, "bounced", None, user)

    with pytest.raises(HTTPException) as e:
        _issue(db, user, number="000104", book=book)
    assert e.value.status_code == 409


def test_the_database_itself_refuses_a_duplicate_leaf(db, user):
    """گاردِ سرویس پیامِ خوب می‌دهد؛ ایندکسِ جزئی تضمینِ واقعی است.

    اگر فردا مسیرِ نوشتنِ تازه‌ای اضافه شود و سنجش را فراموش کند، این می‌گیردش.
    """
    from sqlalchemy.exc import IntegrityError

    book = _book(db, user)
    first = _issue(db, user, number="000105", book=book)
    db.add(
        Check(
            type="payable",
            number="000105",
            amount=Decimal(1),
            issue_date=TODAY,
            due_date=TODAY,
            status="issued",
            checkbook_id=book.id,
            created_by_id=first.created_by_id,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_the_same_number_in_two_books_is_fine(db, user):
    """یکتایی به دسته کلید خورده، نه به کلِ چک‌ها — دو بانک شماره‌ی مشترک دارند."""
    one = _book(db, user)
    two = _book(db, user)
    _issue(db, user, number="000102", book=one)
    _issue(db, user, number="000102", book=two)
    assert svc.used_count(db, one) == svc.used_count(db, two) == 1


# ── بازه ─────────────────────────────────────────────────────────────────────


def test_a_number_outside_the_range_is_refused(db, user):
    """§۵ — شماره‌ی بی‌ربط «مانده» را هم کم می‌کرد، پس شمارنده دروغ می‌گفت."""
    book = _book(db, user)
    with pytest.raises(HTTPException) as e:
        _issue(db, user, number="000999", book=book)
    assert e.value.status_code == 400
    assert "000101" in e.value.detail  # بازه در پیام می‌آید


def test_a_non_numeric_series_does_not_break_the_range_check(db, user):
    """§۲۱ — ساختارِ عددی فرضِ قطعی نیست؛ چیزی که نمی‌فهمیم را مسدود نمی‌کنیم.

    بازه‌ی غیرعددی تعدادِ برگ را صریح می‌خواهد (سرور نمی‌تواند حسابش کند) و بعد از
    آن هیچ سنجشِ بازه‌ای اعمال نمی‌شود — ولی یکتاییِ برگ سرِ جایش می‌ماند.
    """
    book = _book(db, user, first_number="AB-1", last_number="AB-50", leaf_count=50)
    check = _issue(db, user, number="AB-7", book=book)
    assert check.checkbook_id == book.id
    assert svc.next_number(db, book.id) == ""
    with pytest.raises(HTTPException) as e:
        _issue(db, user, number="AB-7", book=book)
    assert e.value.status_code == 409


def test_a_closed_book_issues_no_new_leaf(db, user):
    book = _book(db, user)
    svc.update_checkbook(db, book.id, CheckbookUpdateIn(is_active=False))
    with pytest.raises(HTTPException) as e:
        _issue(db, user, number="000101", book=book)
    assert e.value.status_code == 400


# ── حسابِ بانکی از دسته می‌آید ───────────────────────────────────────────────


def test_a_payable_cheque_inherits_its_bank_account_from_the_book(db, user):
    """§۱۱ — تا امروز تا لحظه‌ی وصول هیچ حسابی نداشت و آن‌وقت دوباره پرسیده می‌شد."""
    bank = _bank(db)
    book = _book(db, user, bank)
    check = _issue(db, user, number="000101", book=book)
    assert check.bank_account_id == bank.id


def test_clearing_does_not_ask_for_the_account_again(db, user):
    bank = _bank(db)
    book = _book(db, user, bank)
    check = _issue(db, user, number="000102", book=book)

    cleared = update_check_status(db, check.id, "cleared", None, user)
    assert cleared.status == "cleared"


def test_clearing_from_a_different_account_is_refused(db, user):
    """تعهد روی یک حساب ثبت شده بود؛ کم‌شدنِ پول از حسابِ دیگر بی‌صدا نمی‌گذرد."""
    book = _book(db, user)
    other = _bank(db)
    check = _issue(db, user, number="000103", book=book)

    with pytest.raises(HTTPException) as e:
        update_check_status(db, check.id, "cleared", other.id, user)
    assert e.value.status_code == 400


# ── سیاست ────────────────────────────────────────────────────────────────────


def test_the_default_policy_changes_nothing(db, user):
    """پیش‌فرض `off` است: چکِ بی‌دسته دقیقاً مثلِ امروز ثبت می‌شود."""
    assert svc.get_control_mode(db) == "off"
    check = _issue(db, user, number="777001")
    assert check.checkbook_id is None
    assert check.bank_account_id is None


def test_book_policy_refuses_a_cheque_without_a_book(db, user):
    _set_mode(db, "book")
    try:
        with pytest.raises(HTTPException) as e:
            _issue(db, user, number="777002")
        assert e.value.status_code == 400
        assert "دسته چک" in e.value.detail
    finally:
        _set_mode(db, "off")


def test_book_policy_never_touches_receivable_cheques(db, user):
    """کاغذِ چکِ دریافتنی مالِ ما نیست؛ دسته‌چکِ ما ربطی به شماره‌اش ندارد."""
    _set_mode(db, "book")
    try:
        check = _issue(db, user, number="777003", kind="receivable")
        assert check.checkbook_id is None
    finally:
        _set_mode(db, "off")


def test_the_range_check_applies_even_when_the_policy_is_off(db, user):
    """مرزِ سیاست و یکپارچگی: انتخابِ دسته یعنی سنجش، در هر حالتی."""
    assert svc.get_control_mode(db) == "off"
    book = _book(db, user)
    with pytest.raises(HTTPException):
        _issue(db, user, number="000999", book=book)


def test_an_invalid_policy_is_rejected(db, user):
    tenant = db.get(Tenant, session_tenant(db))
    with pytest.raises(ValueError):
        svc.set_control_mode(tenant, "whatever")


# ── هم‌پوشانیِ بازه ──────────────────────────────────────────────────────────


def test_overlapping_ranges_on_one_account_are_refused(db, user):
    """§۲۰ — یک شماره نباید از دو دسته قابلِ صدور باشد."""
    bank = _bank(db)
    _book(db, user, bank, first_number="000101", last_number="000150")
    with pytest.raises(HTTPException) as e:
        _book(db, user, bank, first_number="000140", last_number="000190")
    assert e.value.status_code == 409


def test_adjacent_ranges_are_fine(db, user):
    bank = _bank(db)
    _book(db, user, bank, first_number="000101", last_number="000150")
    book = _book(db, user, bank, first_number="000151", last_number="000200")
    assert book.leaf_count == 50


def test_the_same_range_on_another_account_is_fine(db, user):
    """دو بانکِ مختلف می‌توانند شماره‌ی یکسان بدهند؛ ربطی به هم ندارند."""
    _book(db, user, _bank(db), first_number="000101", last_number="000150")
    book = _book(db, user, _bank(db), first_number="000101", last_number="000150")
    assert book.leaf_count == 50


# ── ویرایش ───────────────────────────────────────────────────────────────────


def test_an_untouched_book_can_be_fixed(db, user):
    """§۱۸ — تا امروز هیچ راهی برای ویرایش نبود؛ غلطِ تایپی تا ابد می‌ماند."""
    book = _book(db, user)
    updated = svc.update_checkbook(db, book.id, CheckbookUpdateIn(last_number="000120"))
    assert (updated.last_number, updated.leaf_count) == ("000120", 20)


def test_a_used_book_refuses_structural_edits(db, user):
    book = _book(db, user)
    _issue(db, user, number="000101", book=book)
    with pytest.raises(HTTPException) as e:
        svc.update_checkbook(db, book.id, CheckbookUpdateIn(last_number="000120"))
    assert e.value.status_code == 409


def test_a_used_book_still_accepts_cosmetic_edits(db, user):
    book = _book(db, user)
    _issue(db, user, number="000101", book=book)
    updated = svc.update_checkbook(db, book.id, CheckbookUpdateIn(description="دفترِ اول"))
    assert updated.description == "دفترِ اول"
    assert updated.leaf_count == 10


def test_editing_one_field_leaves_the_rest_alone(db, user):
    """رگرسیون: همان اشکالی که در کارت‌خوان دیدیم — PATCHِ ناقص وضعیت را عوض می‌کرد."""
    book = _book(db, user)
    svc.update_checkbook(db, book.id, CheckbookUpdateIn(is_active=False))
    updated = svc.update_checkbook(db, book.id, CheckbookUpdateIn(description="یادداشت"))
    assert updated.is_active is False


# ── مشتق‌ها ──────────────────────────────────────────────────────────────────


def test_used_leaves_say_where_each_one_went(db, user):
    """§۲۳ — «۷ برگ خرج شده» بدونِ اینکه بشود دید کجا رفت، عددِ بی‌فایده است."""
    book = _book(db, user)
    _issue(db, user, number="000102", book=book, amount=5_000_000)
    _issue(db, user, number="000101", book=book, amount=2_000_000)

    leaves = svc.used_leaves(db, book)
    assert [leaf["number"] for leaf in leaves] == ["000101", "000102"]
    assert leaves[0]["status"] == "issued"
    assert leaves[1]["amount"] == Decimal(5_000_000)


def test_the_print_format_falls_back_to_the_bank_account(db, user):
    """§۸ — یک زنجیره، نه دو زیرساختِ موازیِ قالب."""
    bank = _bank(db)
    bank.cheque_print_format = "sayad-a4"
    db.flush()
    book = _book(db, user, bank)
    assert svc.print_format(db, book) == "sayad-a4"

    svc.update_checkbook(db, book.id, CheckbookUpdateIn(cheque_print_format="sayad-a5"))
    assert svc.print_format(db, book) == "sayad-a5"


# ── رگرسیون ──────────────────────────────────────────────────────────────────


def test_a_cheque_without_a_book_still_works(db, user):
    """چک‌های پیش از این تغییر و مسیرهای بدونِ دسته نباید بشکنند."""
    check = _issue(db, user, number="555001")
    assert check.checkbook_id is None
    assert check.status == "issued"


def test_a_receivable_cheque_is_untouched(db, user):
    check = _issue(db, user, number="555002", kind="receivable")
    assert (check.checkbook_id, check.status) == (None, "in_hand")


def test_a_used_book_cannot_be_deleted_but_can_be_closed(db, user):
    book = _book(db, user)
    _issue(db, user, number="000101", book=book)
    with pytest.raises(HTTPException) as e:
        svc.delete_checkbook(db, book.id)
    assert e.value.status_code == 409
    assert svc.update_checkbook(db, book.id, CheckbookUpdateIn(is_active=False)).is_active is False
