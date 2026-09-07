"""ردِ حسابرسیِ بازشماره‌گذاری — و انتخابِ دستیِ اسناد.

## باگی که این تست‌ها می‌بندند

`renumber_entries` برای دور زدنِ قیدِ یکتای (مستأجر، شماره) دومرحله‌ای می‌نویسد: اول
همه‌ی شماره‌ها منفی می‌شوند، بعد نهایی. و `JournalEntry` تحتِ حسابرسیِ **خودکار**
است که روی *هر* flush شلیک می‌کند.

نتیجه‌اش برای هر سند دو رکورد بود:

    ۱) «سند حسابداری شماره -۱ ویرایش شد»   {number: {from: 5,  to: -1}}
    ۲) «سند حسابداری شماره ۳ ویرایش شد»    {number: {from: -1, to: 3}}

یعنی رکوردِ اول وضعیتی را ثبت می‌کرد که هرگز واقعیت نداشت، و **هیچ رکوردی «۵ → ۳»
را نشان نمی‌داد** — همان تنها چیزی که کسی در دفترِ حسابرسی دنبالش می‌گردد.

دفترِ حسابرسی با trigger فقط‌افزودنی است و هرگز پاک نمی‌شود؛ رکوردِ غلطش برای همیشه
می‌ماند.
"""
from datetime import date

import pytest

from app.models.accounting import JournalEntry, JournalLine
from app.models.audit import AuditLog
from app.services import chart_codes as cc
from app.services.accounting_ops import renumber_entries
from app.services.common import get_account, make_journal_entry


def _entry(db, user, *, day: int, desc: str) -> JournalEntry:
    cash = get_account(db, cc.CASH).id
    inventory = get_account(db, cc.INVENTORY).id
    return make_journal_entry(
        db,
        date(2026, 6, day),
        desc,
        "manual",
        user,
        [
            JournalLine(account_id=inventory, debit=100, credit=0),
            JournalLine(account_id=cash, debit=0, credit=100),
        ],
    )


def _audit_rows(db, entry_id) -> list[AuditLog]:
    return (
        db.query(AuditLog)
        .filter(AuditLog.entity_id == entry_id, AuditLog.action == "update")
        .all()
    )


# ── ردِ حسابرسی ──────────────────────────────────────────────────────────────


def test_renumbering_writes_one_truthful_record_per_entry(db, user):
    """**قیدِ اصلی.** یک رکورد با شماره‌ی واقعیِ قبل و بعد — نه دو تا."""
    first = _entry(db, user, day=3, desc="سومِ ماه")
    second = _entry(db, user, day=1, desc="اولِ ماه")
    was_first, was_second = first.number, second.number

    renumber_entries(db, user, date(2026, 6, 1), date(2026, 6, 30), 501)
    db.flush()

    #: «اولِ ماه» باید ۵۰۱ بگیرد چون ترتیب بر تاریخ است، نه بر شماره‌ی قبلی.
    assert second.number == 501
    assert first.number == 502

    rows = _audit_rows(db, second.id)
    assert len(rows) == 1, "باید دقیقاً یک رکورد باشد، نه یکی برای پاسِ منفی"
    assert rows[0].changes == {"number": {"from": was_second, "to": 501}}
    assert str(was_second) in rows[0].summary and "501" in rows[0].summary

    assert len(_audit_rows(db, first.id)) == 1
    assert _audit_rows(db, first.id)[0].changes["number"]["from"] == was_first


def test_no_audit_record_ever_mentions_a_negative_number(db, user):
    """شماره‌ی منفی یک ترفندِ پیاده‌سازی است و نباید به دفترِ دائمی نشت کند."""
    _entry(db, user, day=1, desc="یک")
    _entry(db, user, day=2, desc="دو")
    _entry(db, user, day=3, desc="سه")

    renumber_entries(db, user, date(2026, 6, 1), date(2026, 6, 30), 700)
    db.flush()

    for row in db.query(AuditLog).filter(AuditLog.entity_type == "JournalEntry").all():
        assert "-" not in row.summary.replace("—", ""), row.summary
        if row.changes and "number" in row.changes:
            for side in ("from", "to"):
                value = row.changes["number"][side]
                assert value is None or int(value) > 0, row.changes


def test_an_entry_whose_number_did_not_change_gets_no_record(db, user):
    """رویدادی رخ نداده که ثبت شود.

    بدونِ این، هر بازشماری برای *همه‌ی* اسنادِ بازه رکورد می‌ساخت — حتی آن‌هایی که
    شماره‌شان همان بود — و دفتر پر از «تغییرِ ۵ به ۵» می‌شد.
    """
    only = _entry(db, user, day=1, desc="تنها سند")
    same = only.number
    assert same is not None

    renumber_entries(db, user, date(2026, 6, 1), date(2026, 6, 30), same)
    db.flush()

    assert only.number == same
    assert _audit_rows(db, only.id) == []


def test_suppression_does_not_leak_to_later_operations(db, user):
    """**قیدِ مهم.** خاموشیِ موقت نباید بعد از عملیات باز بماند.

    اگر پرچم باز می‌ماند، هر تغییرِ مالیِ بعدی در همان درخواست بی‌رد می‌شد — یعنی
    این اصلاح خودش یک سوراخِ بزرگ‌تر می‌ساخت.
    """
    first = _entry(db, user, day=1, desc="یک")
    _entry(db, user, day=2, desc="دو")
    renumber_entries(db, user, date(2026, 6, 1), date(2026, 6, 30), 900)
    db.flush()

    from app.services.voiding import void_journal_entry

    void_journal_entry(db, first.id, reason="آزمون", user=user, void_date=date(2026, 6, 5))
    db.flush()

    voids = (
        db.query(AuditLog)
        .filter(AuditLog.entity_id == first.id, AuditLog.action == "void")
        .all()
    )
    assert len(voids) == 1, "ابطالِ بعدی باید مثل همیشه ثبت شود"


# ── انتخابِ دستی ─────────────────────────────────────────────────────────────


def test_manual_selection_touches_only_the_chosen_entries(db, user):
    """انتخابِ دستی جایگزینِ بازه است، نه افزوده بر آن."""
    picked = _entry(db, user, day=1, desc="انتخاب‌شده")
    untouched = _entry(db, user, day=2, desc="دست‌نخورده")
    before = untouched.number

    result = renumber_entries(db, user, None, None, 400, [picked.id])
    db.flush()

    assert result["count"] == 1
    assert picked.number == 400
    assert untouched.number == before, "سندِ انتخاب‌نشده نباید تکان بخورد"


def test_manual_selection_still_skips_permanent_entries(db, user):
    """گاردهای موجود با انتخابِ دستی هم برقرارند.

    اگر انتخابِ دستی از فیلترِ «فقط موقت» رد می‌شد، کاربر می‌توانست با تیک‌زدن،
    شماره‌ی سندِ امضاشده را عوض کند.
    """
    temporary = _entry(db, user, day=1, desc="موقت")
    permanent = _entry(db, user, day=2, desc="دائم")
    permanent.status = "permanent"
    db.flush()
    frozen = permanent.number

    result = renumber_entries(db, user, None, None, 300, [temporary.id, permanent.id])
    db.flush()

    assert result["count"] == 1, "سندِ دائم نباید وارد نقشه شود"
    assert permanent.number == frozen


def test_an_empty_selection_is_refused(db, user):
    """پیامِ روشن به‌جای عملیاتِ بی‌صدا روی صفر سند."""
    _entry(db, user, day=1, desc="یک")

    with pytest.raises(Exception) as err:
        renumber_entries(db, user, None, None, 1, [])

    assert "موقت" in str(err.value) or "نیست" in str(err.value)
