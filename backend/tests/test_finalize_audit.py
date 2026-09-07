"""دائم‌کردنِ سند باید کنشِ خودش را در دفترِ حسابرسی داشته باشد.

سؤالی که یک حسابرس یا مدیر می‌پرسد: **«چه کسی این سند را نهایی کرد؟»**

تا امروز جوابش هست ولی مستقیم نیست: تغییرِ `status` به‌عنوان `action="update"` ثبت
می‌شد و خلاصه‌اش می‌گفت «سند حسابداری شماره ۱۲۵ **ویرایش شد**» — که غلط توصیف
می‌کند، چون هیچ‌چیز ویرایش نشده؛ سند رسمی شده. برای یافتنش باید `update`ها را
فیلتر کرد و بعد داخلِ JSONِ `changes` دنبالِ `status` گشت.

`models/audit.py` همین استدلال را از قبل درباره‌ی **ابطال** پذیرفته بود: «اگر با
بقیه‌ی UPDATEها در یک دسته بیفتد، پیدا کردنش نیاز به فیلتر روی محتوای JSON دارد».
این فایل همان قاعده را برای دائم‌شدن قفل می‌کند.
"""
from datetime import date

from app.models.accounting import JournalEntry, JournalLine
from app.models.audit import AuditLog
from app.services import chart_codes as cc
from app.services.accounting_ops import finalize_entries
from app.services.common import get_account, make_journal_entry


def _entry(db, user, *, day: int = 1) -> JournalEntry:
    cash = get_account(db, cc.CASH).id
    inventory = get_account(db, cc.INVENTORY).id
    return make_journal_entry(
        db,
        date(2026, 6, day),
        f"سندِ روزِ {day}",
        "manual",
        user,
        [
            JournalLine(account_id=inventory, debit=100, credit=0),
            JournalLine(account_id=cash, debit=0, credit=100),
        ],
    )


def _rows(db, entry_id, action: str) -> list[AuditLog]:
    return (
        db.query(AuditLog)
        .filter(AuditLog.entity_id == entry_id, AuditLog.action == action)
        .all()
    )


# ── کنشِ تازه ────────────────────────────────────────────────────────────────


def test_finalizing_is_recorded_as_its_own_action(db, user):
    """**قیدِ اصلی.** «چه کسی نهایی‌اش کرد؟» باید یک کوئریِ ساده باشد."""
    entry = _entry(db, user)

    finalize_entries(db, user, entry_ids=[entry.id])
    db.flush()

    assert _rows(db, entry.id, "update") == [], "دیگر نباید update ثبت شود"
    rows = _rows(db, entry.id, "finalize")
    assert len(rows) == 1
    assert "دائم شد" in rows[0].summary
    assert "ویرایش" not in rows[0].summary


def test_the_record_answers_who_and_when(db, user):
    """همان چیزی که بندِ ۱۲ می‌خواهد: کنشگر، زمان، و وضعیتِ قبل و بعد.

    `bind_session_actor` صریح صدا زده می‌شود — همان الگوی `test_audit_log.py`.
    در برنامه‌ی واقعی این کار را وابستگیِ `deps.py` انجام می‌دهد؛ بدونش رکورد
    «سیستم» ثبت می‌شود، که برای اسکریپت و مهاجرت درست است ولی چیزی نیست که این
    تست می‌خواهد بسنجد.
    """
    from app.audit import bind_session_actor

    entry = _entry(db, user)
    bind_session_actor(db, user)

    finalize_entries(db, user, entry_ids=[entry.id])
    db.flush()

    row = _rows(db, entry.id, "finalize")[0]
    assert row.actor_id == user.id
    assert row.actor_email == user.email
    assert row.at is not None
    assert row.changes["status"] == {"from": "temporary", "to": "permanent"}
    #: هر سه ستونِ وضعیت باید در رد بمانند، نه فقط `status`.
    assert "finalized_at" in row.changes
    assert "finalized_by_id" in row.changes


def test_a_bulk_finalize_records_each_entry_separately(db, user):
    """عملیاتِ گروهی نباید یک رکوردِ مبهم برای همه بسازد.

    حسابرس دنبالِ *یک سند* می‌گردد، نه دنبالِ «عملیاتی که ۲۳ سند را دائم کرد».
    """
    first = _entry(db, user, day=1)
    second = _entry(db, user, day=2)

    finalize_entries(db, user, entry_ids=[first.id, second.id])
    db.flush()

    assert len(_rows(db, first.id, "finalize")) == 1
    assert len(_rows(db, second.id, "finalize")) == 1


# ── کنش‌های دیگر دزدیده نشده‌اند ─────────────────────────────────────────────


def test_voiding_is_still_recorded_as_void(db, user):
    """**رگرسیونِ مهم.** تشخیصِ تازه نباید ابطال را بدزدد.

    ترتیبِ شرط‌ها این را تضمین می‌کند: ابطال اول سنجیده می‌شود.
    """
    entry = _entry(db, user)

    from app.services.voiding import void_journal_entry

    void_journal_entry(db, entry.id, reason="آزمون", user=user, void_date=date(2026, 6, 5))
    db.flush()

    assert len(_rows(db, entry.id, "void")) == 1
    assert _rows(db, entry.id, "finalize") == []


def test_an_ordinary_edit_is_still_an_update(db, user, client):
    """ویرایشی که وضعیت را عوض نمی‌کند باید همان `update` بماند."""
    entry = _entry(db, user)
    db.flush()

    res = client.patch(
        f"/api/journal-entries/{entry.id}/sub-number",
        json={"sub_number": "ب-۱۴۰۵/۷"},
    )
    assert res.status_code == 200, res.text

    updates = _rows(db, entry.id, "update")
    assert len(updates) == 1
    assert updates[0].changes["sub_number"]["to"] == "ب-۱۴۰۵/۷"
    assert _rows(db, entry.id, "finalize") == []
