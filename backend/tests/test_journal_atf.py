"""شماره عطف و شماره فرعیِ سند حسابداری.

قاعده‌هایی که این دو ستون بدونشان بی‌فایده‌اند:

* عطف را **سرور** می‌دهد، به هر سند، از هر مسیری که ساخته شود.
* عطف **هرگز** عوض نمی‌شود — نه با بازشماره‌گذاری، نه با دائم‌کردن.
* عطف در هر کسب‌وکار **یکتا** است و از شمارنده‌ی خودش می‌آید، نه از شماره‌ی سند.
* فرعی **مالِ کاربر** است: اختیاری، تکرارپذیر، قابلِ جستجو، و روی سندِ دائم قفل.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.accounting import JournalEntry, JournalLine
from app.models.counters import DOC_JOURNAL_ATF, DOC_JOURNAL_ENTRY
from app.services import accounting_ops as ops
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.numbering import next_document_number

TODAY = date(2026, 6, 15)


def _entry(db, user, *, day=TODAY, amount=1_000_000, desc="تست", source="manual"):
    cash = get_account(db, cc.CASH)
    sales = get_account(db, cc.SALES_REVENUE)
    return make_journal_entry(
        db,
        day,
        desc,
        source,
        user,
        [
            JournalLine(account_id=cash.id, debit=Decimal(amount), credit=0),
            JournalLine(account_id=sales.id, debit=0, credit=Decimal(amount)),
        ],
    )


def _api_payload(client) -> dict:
    """سندِ متوازنِ حداقلی از راهِ اندپوینت — حساب‌ها را از خودِ API می‌گیرد."""
    rows = client.get("/api/accounts").json()
    postable = [a for a in rows if not a["is_group"]]
    return {
        "entry_date": TODAY.isoformat(),
        "description": "سندِ تست",
        "lines": [
            {"account_id": postable[0]["id"], "debit": 5000, "credit": 0},
            {"account_id": postable[1]["id"], "debit": 0, "credit": 5000},
        ],
    }


# ───────────────────────────── شماره عطف ─────────────────────────────


def test_every_entry_gets_an_atf_number_without_anyone_asking(db, user):
    """هیچ‌کدام از مسیرهای ساختِ سند عطف را دستی نمی‌دهند — رویداد می‌دهد."""
    first = _entry(db, user)
    second = _entry(db, user)

    assert first.atf_number is not None
    assert second.atf_number == first.atf_number + 1


def test_atf_comes_from_its_own_counter_not_the_entry_number(db, user):
    """دو شمارنده‌ی جدا. اگر یکی بودند، بازشماره‌گذاری عطف را هم می‌شکست."""
    burned = next_document_number(db, DOC_JOURNAL_ATF)
    entry = _entry(db, user)

    assert entry.atf_number == burned + 1
    # شماره‌ی سند از شمارنده‌ی خودش آمد، پس این تست که یک عطف را سوزاند
    # دو دنباله را از هم جدا کرده است.
    assert entry.number != entry.atf_number


def test_renumbering_moves_the_number_and_leaves_the_atf_alone(db, user):
    """قلبِ ماجرا: شماره‌ی سند متغیر است، عطف ثابت."""
    older = _entry(db, user, day=date(2026, 6, 20), desc="دیرتر ثبت شد، تاریخش جلوتر")
    newer = _entry(db, user, day=date(2026, 6, 10), desc="زودتر")
    atf_before = {older.id: older.atf_number, newer.id: newer.atf_number}
    number_before = newer.number

    ops.renumber_entries(db, user, date(2026, 6, 1), date(2026, 6, 30), start_number=5000)
    db.refresh(older)
    db.refresh(newer)

    # شماره‌ها به‌ترتیبِ تاریخ جابه‌جا شدند …
    assert newer.number == 5000
    assert older.number == 5001
    assert number_before != newer.number
    # … و عطف تکان نخورد.
    assert older.atf_number == atf_before[older.id]
    assert newer.atf_number == atf_before[newer.id]


def test_renumber_preview_shows_the_atf_so_the_user_can_see_it_survives(db, user):
    entry = _entry(db, user)
    preview = ops.preview_renumber(db, date(2026, 6, 1), date(2026, 6, 30), start_number=900)

    row = next(r for r in preview["rows"] if r["id"] == entry.id)
    assert row["atf_number"] == entry.atf_number


def test_finalizing_does_not_touch_the_atf(db, user):
    entry = _entry(db, user)
    atf = entry.atf_number

    ops.finalize_entries(db, user, entry_ids=[entry.id])
    db.refresh(entry)

    assert entry.status == "permanent"
    assert entry.atf_number == atf


def test_atf_is_unique_within_a_tenant(db, user):
    """قیدِ دیتابیس، نه فقط ادبِ کد."""
    first = _entry(db, user)
    second = _entry(db, user)

    savepoint = db.begin_nested()
    second.atf_number = first.atf_number
    with pytest.raises(IntegrityError):
        db.flush()
    savepoint.rollback()


def test_a_merged_entry_gets_a_fresh_atf(db, user):
    """ادغام سندِ تازه می‌سازد، پس عطفِ تازه هم می‌گیرد — عطفِ اصل‌ها با خودشان می‌رود."""
    one = _entry(db, user, desc="الف")
    two = _entry(db, user, desc="ب")
    old_atfs = {one.atf_number, two.atf_number}

    result = ops.merge_entries(db, user, [one.id, two.id], "ادغام‌شده")
    merged = db.query(JournalEntry).filter(JournalEntry.id == result["entry_id"]).one()

    assert merged.atf_number is not None
    assert merged.atf_number not in old_atfs


def test_atf_order_follows_registration_even_inside_one_flush(db, user):
    """`session.new` مجموعه است و ترتیبش تصادفی؛ عطف باید ترتیبِ شماره را دنبال کند."""
    cash = get_account(db, cc.CASH)
    sales = get_account(db, cc.SALES_REVENUE)
    made = []
    for i in range(4):
        entry = JournalEntry(
            number=next_document_number(db, DOC_JOURNAL_ENTRY),
            entry_date=TODAY,
            description=f"سند {i}",
            source_type="manual",
            created_by_id=user.id,
            lines=[
                JournalLine(account_id=cash.id, debit=Decimal(1000), credit=0),
                JournalLine(account_id=sales.id, debit=0, credit=Decimal(1000)),
            ],
        )
        db.add(entry)
        made.append(entry)
    db.flush()  # هر چهار سند در یک فلاش

    atfs = [e.atf_number for e in sorted(made, key=lambda e: e.number)]
    assert atfs == sorted(atfs), "ترتیبِ عطف باید همان ترتیبِ شماره‌ی سند باشد"


# ───────────────────────────── شماره فرعی ────────────────────────────


def test_blank_sub_number_is_stored_as_empty_not_as_a_blank_string(client):
    """فیلدِ دست‌نخورده‌ی فرم رشته‌ی خالی می‌فرستد؛ ذخیره‌اش یعنی جستجو و
    «دارد/ندارد» بعداً دروغ می‌گویند."""
    payload = _api_payload(client)
    payload["sub_number"] = "   "

    created = client.post("/api/journal-entries", json=payload)
    assert created.status_code == 201
    assert created.json()["sub_number"] is None


def test_sub_number_round_trips_and_allows_duplicates(client):
    """چند سندِ یک دسته عمداً یک شماره فرعی می‌گیرند — همان کاری که باهاش می‌کنند."""
    for _ in range(2):
        payload = _api_payload(client)
        payload["sub_number"] = "ب-۱۴۰۴/۷"
        res = client.post("/api/journal-entries", json=payload)
        assert res.status_code == 201
        assert res.json()["sub_number"] == "ب-۱۴۰۴/۷"


def test_search_finds_an_entry_by_its_sub_number_and_by_its_atf(client):
    payload = _api_payload(client)
    payload["sub_number"] = "پرونده-۹۹"
    created = client.post("/api/journal-entries", json=payload).json()

    by_sub = client.get("/api/journal-entries", params={"q": "پرونده-۹۹"}).json()
    assert [e["id"] for e in by_sub["items"]] == [created["id"]]

    by_atf = client.get("/api/journal-entries", params={"q": str(created["atf_number"])}).json()
    assert created["id"] in [e["id"] for e in by_atf["items"]]


def test_sub_number_is_editable_while_the_entry_is_temporary(client):
    created = client.post("/api/journal-entries", json=_api_payload(client)).json()

    res = client.patch(
        f"/api/journal-entries/{created['id']}/sub-number", json={"sub_number": "اصلاح‌شده"}
    )
    assert res.status_code == 200
    assert res.json()["sub_number"] == "اصلاح‌شده"
    # ویرایشِ فرعی به عطف دست نمی‌زند
    assert res.json()["atf_number"] == created["atf_number"]


def test_sub_number_is_locked_once_the_entry_is_permanent(client):
    payload = _api_payload(client)
    payload["status"] = "permanent"
    created = client.post("/api/journal-entries", json=payload).json()

    res = client.patch(
        f"/api/journal-entries/{created['id']}/sub-number", json={"sub_number": "دیر شد"}
    )
    assert res.status_code == 409


def test_sub_number_longer_than_the_column_is_refused(client):
    payload = _api_payload(client)
    payload["sub_number"] = "x" * 31

    assert client.post("/api/journal-entries", json=payload).status_code == 422
