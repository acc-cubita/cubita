"""گاردِ «دستِ‌کم یک فیلتر» در دائم‌کردنِ اسناد.

docstringِ `FinalizeIn` از روزِ اول می‌گفت «همه‌ی اسنادِ موقتِ تاریخ یک درخواستِ
خطرناکِ بی‌قصد است و باید صریح گفته شود» — و **هیچ‌چیز اعمالش نمی‌کرد**.

`POST /api/accounting/entries/finalize` با بدنه‌ی `{}` همه‌ی اسنادِ موقتِ کسب‌وکار را
دائم می‌کرد. دائم‌کردن **یک‌طرفه** است: خودِ سرویس می‌گوید «راهِ برگشتی عمداً وجود
ندارد». پس یک درخواستِ خالی، بی‌هیچ خطایی، کلِ دفتر را قفل می‌کرد.

قاعده‌ای که نوشته شده و اجرا نمی‌شود از نبودنش بدتر است: خواننده‌ی کد فکر می‌کند
محافظت هست.
"""
from datetime import date

import pytest

from app.models.accounting import JournalEntry, JournalLine
from app.services import chart_codes as cc
from app.services.accounting_ops import finalize_entries
from app.services.common import get_account, make_journal_entry


def _entry(db, user, *, day: int, source: str = "manual") -> JournalEntry:
    cash = get_account(db, cc.CASH).id
    inventory = get_account(db, cc.INVENTORY).id
    entry = make_journal_entry(
        db,
        date(2026, 6, day),
        f"سندِ روزِ {day}",
        source,
        user,
        [
            JournalLine(account_id=inventory, debit=100, credit=0),
            JournalLine(account_id=cash, debit=0, credit=100),
        ],
    )
    return entry


# ── گاردِ اصلی ───────────────────────────────────────────────────────────────


def test_finalizing_with_no_filter_at_all_is_refused(db, user):
    """**قیدِ اصلی.** درخواستِ بی‌فیلتر نباید کلِ دفتر را دائم کند."""
    first = _entry(db, user, day=1)
    second = _entry(db, user, day=2)

    with pytest.raises(Exception) as err:
        finalize_entries(db, user)

    assert "فیلتر" in str(err.value)
    assert first.status == "temporary"
    assert second.status == "temporary"


def test_an_explicitly_empty_selection_is_refused(db, user):
    """فهرستِ خالی یعنی «چیزی انتخاب نشد»، نه «فیلتری در کار نیست».

    با شرطِ truthy به فیلترِ تاریخ می‌افتاد و — چون بازه‌ای نبود — همه را دائم
    می‌کرد. همان تله‌ای که در بازشماره‌گذاری هم بود.
    """
    only = _entry(db, user, day=1)

    with pytest.raises(Exception) as err:
        finalize_entries(db, user, entry_ids=[])

    assert "انتخاب" in str(err.value)
    assert only.status == "temporary"


# ── مسیرهایی که باید کار کنند ────────────────────────────────────────────────


def test_a_date_range_still_works(db, user):
    _entry(db, user, day=1)
    _entry(db, user, day=2)

    result = finalize_entries(db, user, date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))

    assert result["count"] == 2


def test_a_source_type_alone_is_enough(db, user):
    """منشأ به‌تنهایی فیلترِ معتبری است — «همه‌ی فاکتورهای فروش» درخواستِ روشنی است."""
    manual = _entry(db, user, day=1, source="manual")
    _entry(db, user, day=2, source="stock_count")

    result = finalize_entries(db, user, source_type="manual")

    assert result["count"] == 1
    assert manual.status == "permanent"


def test_an_explicit_selection_alone_is_enough(db, user):
    picked = _entry(db, user, day=1)
    other = _entry(db, user, day=2)

    result = finalize_entries(db, user, entry_ids=[picked.id])

    assert result["count"] == 1
    assert picked.status == "permanent"
    assert other.status == "temporary"


# ── انتخاب جایگزینِ بازه است، نه افزوده بر آن ────────────────────────────────


def test_a_selection_outside_the_range_is_still_honoured(db, user):
    """**تغییرِ رفتار، عمدی.** پیش از این هر دو فیلتر اعمال می‌شدند.

    کاربری که سندی را تیک می‌زد ولی بازه‌اش جای دیگری بود، بی‌صدا هیچ‌چیز — یا
    زیرمجموعه‌ای از انتخابش — را دائم می‌کرد و پیام «۰ سند» می‌گرفت بی‌آنکه بفهمد
    چرا. حالا انتخاب برنده است.
    """
    picked = _entry(db, user, day=25)

    result = finalize_entries(
        db,
        user,
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 5),  # بازه‌ای که سندِ انتخابی در آن نیست
        entry_ids=[picked.id],
    )

    assert result["count"] == 1
    assert picked.status == "permanent"


# ── از طریقِ API ─────────────────────────────────────────────────────────────


def test_an_empty_request_body_is_refused_over_http(db, user, client):
    """گارد باید از مسیرِ واقعیِ HTTP هم بگیرد، نه فقط در تستِ واحد."""
    only = _entry(db, user, day=1)
    db.flush()

    res = client.post("/api/accounting/entries/finalize", json={})

    assert res.status_code == 400, res.text
    assert "فیلتر" in res.json()["detail"]
    assert only.status == "temporary"
