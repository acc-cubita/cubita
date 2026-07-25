"""اسناد تکرارشونده — پیش‌رویِ تاریخ، تولیدِ بی‌تکرار، پایانِ دوره، و دوره‌ی بسته."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.accounting import JournalEntry, JournalLine
from app.models.period_close import FiscalPeriodClose
from app.schemas.recurring import RecurringEntryIn, RecurringLineIn
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.recurring import (
    _add_months,
    _advance,
    create_template,
    delete_template,
    run_due,
    run_one,
    set_active,
    update_template,
)

TODAY = date(2026, 3, 15)


def _entry_in(db, *, start, frequency="monthly", interval=1, end=None, amount=1_000_000, title="اجاره"):
    exp = get_account(db, cc.INVENTORY_ADJUSTMENT)  # یک حسابِ هزینه‌ی موجود
    cash = get_account(db, cc.CASH)
    return RecurringEntryIn(
        title=title,
        description="اجاره‌ی ماهانه",
        frequency=frequency,
        interval=interval,
        start_date=start,
        end_date=end,
        lines=[
            RecurringLineIn(account_id=exp.id, debit=Decimal(amount), credit=Decimal(0)),
            RecurringLineIn(account_id=cash.id, debit=Decimal(0), credit=Decimal(amount)),
        ],
    )


def _recurring_count(db):
    return db.query(JournalEntry).filter(JournalEntry.source_type == "recurring").count()


def test_add_months_clamps_month_end():
    assert _add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)  # فوریه‌ی ۲۰۲۶ ۲۸ روز
    assert _add_months(date(2026, 1, 15), 2) == date(2026, 3, 15)
    assert _add_months(date(2026, 12, 10), 1) == date(2027, 1, 10)  # پرشِ سال


def test_advance_frequencies():
    assert _advance(date(2026, 3, 1), "weekly", 2) == date(2026, 3, 15)
    assert _advance(date(2026, 3, 1), "monthly", 1) == date(2026, 4, 1)
    assert _advance(date(2026, 3, 1), "yearly", 1) == date(2027, 3, 1)


def test_create_sets_next_run_to_start(db, user):
    tpl = create_template(db, _entry_in(db, start=date(2026, 1, 1)), user)
    assert tpl.next_run_date == date(2026, 1, 1)
    assert tpl.last_run_date is None
    assert tpl.is_active is True


def test_run_generates_each_due_and_is_idempotent(db, user):
    create_template(db, _entry_in(db, start=date(2026, 1, 1)), user)
    result = run_due(db, user, as_of=TODAY)
    # ۱ ژانویه، ۱ فوریه، ۱ مارس = ۳ سند
    assert result["generated"] == 3
    assert _recurring_count(db) == 3

    again = run_due(db, user, as_of=TODAY)  # دوباره اجرا: چیزی ساخته نمی‌شود
    assert again["generated"] == 0
    assert _recurring_count(db) == 3


def test_next_run_advances_past_as_of(db, user):
    tpl = create_template(db, _entry_in(db, start=date(2026, 1, 1)), user)
    run_due(db, user, as_of=TODAY)
    assert tpl.last_run_date == date(2026, 3, 1)
    assert tpl.next_run_date == date(2026, 4, 1)  # فراتر از as_of


def test_end_date_stops_and_deactivates(db, user):
    tpl = create_template(db, _entry_in(db, start=date(2026, 1, 1), end=date(2026, 2, 1)), user)
    result = run_due(db, user, as_of=date(2026, 6, 1))
    assert result["generated"] == 2  # فقط ژانویه و فوریه
    assert tpl.is_active is False  # بعد از عبور از پایان، تمام‌شده


def test_closed_period_occurrence_skipped_but_advances(db, user):
    # دوره تا ۳۱ ژانویه بسته است — سررسیدِ ۱ ژانویه رد می‌شود ولی بقیه ساخته می‌شوند.
    exp = get_account(db, cc.INVENTORY_ADJUSTMENT)
    cash = get_account(db, cc.CASH)
    close_je = make_journal_entry(
        db,
        date(2026, 1, 31),
        "بستن آزمایشی",
        "period_close",
        user,
        [
            JournalLine(account_id=exp.id, debit=Decimal(1), credit=Decimal(0)),
            JournalLine(account_id=cash.id, debit=Decimal(0), credit=Decimal(1)),
        ],
    )
    db.add(
        FiscalPeriodClose(
            closing_date=date(2026, 1, 31),
            net_profit=Decimal(0),
            journal_entry_id=close_je.id,
            created_by_id=user.id,
        )
    )
    db.flush()

    create_template(db, _entry_in(db, start=date(2026, 1, 1)), user)
    result = run_due(db, user, as_of=TODAY)
    assert result["skipped"] == 1  # ۱ ژانویه در دوره‌ی بسته
    assert result["generated"] == 2  # ۱ فوریه و ۱ مارس
    assert _recurring_count(db) == 2


def test_weekly_generation(db, user):
    create_template(db, _entry_in(db, start=date(2026, 3, 1), frequency="weekly"), user)
    result = run_due(db, user, as_of=date(2026, 3, 20))
    # ۱، ۸، ۱۵ مارس = ۳ سند (۲۲ مارس فراتر از as_of)
    assert result["generated"] == 3


def test_run_one_only_that_template(db, user):
    create_template(db, _entry_in(db, start=date(2026, 1, 1), title="الف"), user)
    tpl_b = create_template(db, _entry_in(db, start=date(2026, 1, 1), title="ب"), user)
    result = run_one(db, tpl_b.id, user, as_of=TODAY)
    assert result["generated"] == 3
    assert _recurring_count(db) == 3  # فقط قالبِ ب اجرا شد


def test_update_resets_next_run_when_not_yet_run(db, user):
    tpl = create_template(db, _entry_in(db, start=date(2026, 1, 1)), user)
    update_template(db, tpl.id, _entry_in(db, start=date(2026, 5, 1)))
    assert tpl.next_run_date == date(2026, 5, 1)


def test_update_keeps_next_run_after_first_run(db, user):
    tpl = create_template(db, _entry_in(db, start=date(2026, 1, 1)), user)
    run_due(db, user, as_of=TODAY)
    next_before = tpl.next_run_date
    update_template(db, tpl.id, _entry_in(db, start=date(2020, 1, 1)))
    assert tpl.next_run_date == next_before  # ویرایش سندهای گذشته را دوباره نمی‌سازد


def test_inactive_template_not_generated(db, user):
    tpl = create_template(db, _entry_in(db, start=date(2026, 1, 1)), user)
    set_active(db, tpl.id, False)
    assert run_due(db, user, as_of=TODAY)["generated"] == 0


def test_delete_template_keeps_generated_entries(db, user):
    tpl = create_template(db, _entry_in(db, start=date(2026, 1, 1)), user)
    run_due(db, user, as_of=TODAY)
    delete_template(db, tpl.id)
    assert _recurring_count(db) == 3  # اسنادِ تولیدشده می‌مانند


def test_unbalanced_template_rejected(db):
    exp = uuid4()
    cash = uuid4()
    with pytest.raises(ValueError):
        RecurringEntryIn(
            title="نامتوازن",
            frequency="monthly",
            start_date=date(2026, 1, 1),
            lines=[
                RecurringLineIn(account_id=exp, debit=Decimal(1000), credit=Decimal(0)),
                RecurringLineIn(account_id=cash, debit=Decimal(0), credit=Decimal(500)),
            ],
        )


def test_unknown_template_404(db, user):
    with pytest.raises(HTTPException) as exc:
        run_one(db, uuid4(), user, as_of=TODAY)
    assert exc.value.status_code == 404
