"""سال مالی: هم‌پوشانی، سالِ جاریِ یکتا، قفلِ تاریخِ اسناد، افتتاحیه و اختتامیه."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.jalali import persian_year_end, persian_year_start
from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.fiscal_year import STATUS_CLOSED, STATUS_OPEN
from app.schemas.fiscal_year import FiscalYearIn, FiscalYearUpdate
from app.services import chart_codes as cc
from app.services import fiscal_year as svc
from app.services.common import make_journal_entry
from app.services.period_close import assert_period_open


def _year(db, jy: int, *, activate: bool = True):
    return svc.create_year(
        db,
        FiscalYearIn(
            title=f"سال مالی {jy}",
            start_date=persian_year_start(jy),
            end_date=persian_year_end(jy),
            activate=activate,
        ),
    )


def _post(db, user, when: date, amount: int, *, income: bool):
    """یک سندِ دوطرفه: نقد در برابرِ درآمد یا هزینه."""
    cash = db.query(Account).filter(Account.system_role == cc.CASH).first()
    other_role = cc.SALES_REVENUE if income else cc.COGS
    other = db.query(Account).filter(Account.system_role == other_role).first()
    lines = (
        [
            JournalLine(account_id=cash.id, debit=Decimal(amount), credit=0),
            JournalLine(account_id=other.id, debit=0, credit=Decimal(amount)),
        ]
        if income
        else [
            JournalLine(account_id=other.id, debit=Decimal(amount), credit=0),
            JournalLine(account_id=cash.id, debit=0, credit=Decimal(amount)),
        ]
    )
    return make_journal_entry(db, when, "آزمون", "manual", user, lines)


# ── تعریفِ دوره ───────────────────────────────────────────────────────────────


def test_first_year_is_active_even_if_not_requested(db):
    year = _year(db, 1404, activate=False)
    assert year.is_active is True
    assert year.status == STATUS_OPEN


def test_only_one_active_year(db):
    first = _year(db, 1404)
    second = _year(db, 1405)
    db.refresh(first)
    assert second.is_active is True
    assert first.is_active is False


def test_overlapping_range_is_rejected(db):
    _year(db, 1404)
    with pytest.raises(HTTPException) as err:
        svc.create_year(
            db,
            FiscalYearIn(
                title="دوره‌ی هم‌پوشان",
                start_date=persian_year_start(1404),
                end_date=persian_year_start(1404).replace(day=1),
            ),
        )
    assert err.value.status_code == 400


def test_too_long_period_is_rejected(db):
    with pytest.raises(HTTPException) as err:
        svc.create_year(
            db,
            FiscalYearIn(title="دوره‌ی بلند", start_date=date(2024, 1, 1), end_date=date(2026, 1, 1)),
        )
    assert "روز" in err.value.detail


def test_suggest_follows_previous_year(db):
    _year(db, 1404)
    suggestion = svc.suggest_next(db)
    assert suggestion["jalali_year"] == 1405
    assert suggestion["start_date"] == persian_year_start(1405)
    assert suggestion["days"] in (365, 366)


def test_range_locked_after_entries_exist(db, user):
    year = _year(db, 1404)
    _post(db, user, persian_year_start(1404), 1_000, income=True)
    with pytest.raises(HTTPException) as err:
        svc.update_year(db, year.id, FiscalYearUpdate(end_date=persian_year_end(1404) - timedelta(days=30)))
    # تغییرِ عنوان همچنان مجاز است.
    renamed = svc.update_year(db, year.id, FiscalYearUpdate(title="سال ۱۴۰۴ (اصلاح‌شده)"))
    assert renamed.title == "سال ۱۴۰۴ (اصلاح‌شده)"
    assert err.value.status_code == 400


def test_delete_blocked_when_entries_exist(db, user):
    year = _year(db, 1404)
    _post(db, user, persian_year_start(1404), 1_000, income=True)
    with pytest.raises(HTTPException):
        svc.delete_year(db, year.id)


def test_delete_promotes_another_open_year(db):
    old = _year(db, 1404)
    new = _year(db, 1405)
    svc.delete_year(db, new.id)
    db.refresh(old)
    assert old.is_active is True


# ── قفلِ تاریخِ اسناد ──────────────────────────────────────────────────────────


def test_no_fiscal_year_means_no_restriction(db):
    # سازگاریِ عقب‌رو: حسابی که سال مالی تعریف نکرده، مثلِ قبل کار می‌کند.
    assert_period_open(db, date(2020, 5, 5)) is None


def test_date_outside_every_year_is_rejected(db):
    _year(db, 1404)
    with pytest.raises(HTTPException) as err:
        assert_period_open(db, persian_year_start(1402))
    assert "سال مالی" in err.value.detail


def test_date_inside_open_year_passes(db):
    _year(db, 1404)
    assert_period_open(db, persian_year_start(1404)) is None


def test_closed_year_rejects_new_entries(db, user):
    year = _year(db, 1404)
    _post(db, user, persian_year_start(1404), 5_000, income=True)
    svc.close_year(db, year.id, user)
    with pytest.raises(HTTPException):
        assert_period_open(db, persian_year_start(1404))


# ── اختتامیه ─────────────────────────────────────────────────────────────────


def test_close_year_posts_balanced_closing_entry(db, user):
    year = _year(db, 1404)
    _post(db, user, persian_year_start(1404), 10_000, income=True)
    _post(db, user, persian_year_start(1404), 4_000, income=False)

    closed = svc.close_year(db, year.id, user)
    assert closed.status == STATUS_CLOSED
    assert closed.closing_entry_id is not None

    entry = db.get(JournalEntry, closed.closing_entry_id)
    assert sum(line.debit for line in entry.lines) == sum(line.credit for line in entry.lines)
    retained = db.query(Account).filter(Account.system_role == cc.RETAINED_EARNINGS).first()
    # سودِ خالص ۶٬۰۰۰ به سودِ انباشته می‌رود.
    assert any(line.account_id == retained.id and line.credit == Decimal(6_000) for line in entry.lines)


def test_close_year_without_activity_still_closes(db):
    year = _year(db, 1404)
    closed = svc.close_year(db, year.id, _system_user(db))
    assert closed.status == STATUS_CLOSED
    assert closed.closing_entry_id is None


def test_close_requires_older_year_closed_first(db, user):
    old = _year(db, 1404)
    new = _year(db, 1405)
    with pytest.raises(HTTPException) as err:
        svc.close_year(db, new.id, user)
    assert old.title in err.value.detail


def test_closing_active_year_promotes_next(db, user):
    old = _year(db, 1404)
    new = _year(db, 1405)
    svc.activate_year(db, old.id)
    svc.close_year(db, old.id, user)
    db.refresh(new)
    assert new.is_active is True


# ── افتتاحیه ─────────────────────────────────────────────────────────────────


def test_carry_forward_moves_permanent_balances(db, user):
    old = _year(db, 1404)
    new = _year(db, 1405, activate=False)
    _post(db, user, persian_year_start(1404), 10_000, income=True)
    svc.close_year(db, old.id, user)

    result = svc.carry_forward(db, new.id, user)
    entry = db.get(JournalEntry, result["journal_entry_id"])
    assert entry.entry_date == persian_year_start(1405)
    assert sum(line.debit for line in entry.lines) == sum(line.credit for line in entry.lines)

    cash = db.query(Account).filter(Account.system_role == cc.CASH).first()
    retained = db.query(Account).filter(Account.system_role == cc.RETAINED_EARNINGS).first()
    assert any(line.account_id == cash.id and line.debit == Decimal(10_000) for line in entry.lines)
    assert any(line.account_id == retained.id and line.credit == Decimal(10_000) for line in entry.lines)


def test_carry_forward_requires_previous_year_closed(db, user):
    _year(db, 1404)
    new = _year(db, 1405, activate=False)
    with pytest.raises(HTTPException) as err:
        svc.carry_forward(db, new.id, user)
    assert "ببندید" in err.value.detail


def test_carry_forward_runs_once(db, user):
    old = _year(db, 1404)
    new = _year(db, 1405, activate=False)
    _post(db, user, persian_year_start(1404), 10_000, income=True)
    svc.close_year(db, old.id, user)
    svc.carry_forward(db, new.id, user)
    with pytest.raises(HTTPException) as err:
        svc.carry_forward(db, new.id, user)
    assert err.value.status_code == 409


def _system_user(db):
    from app.models.user import User

    return db.query(User).first()
