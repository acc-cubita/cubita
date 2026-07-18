"""صفحه‌بندی keyset.

مهم‌ترین چیزی که اینجا سنجیده می‌شود این نیست که «صفحه برمی‌گردد»، بلکه این است که
پیمایش همه‌ی صفحه‌ها **دقیقاً یک‌بار** هر ردیف را برگرداند — نه تکرار، نه جاافتادگی.
حالت خطرناک، ردیف‌های هم‌تاریخ است: اگر کلید مرتب‌سازی یکتا نباشد، ردیف‌ها سر مرز
صفحه گم می‌شوند و کاربر یک سند را اصلاً نمی‌بیند.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.accounting import JournalEntry, JournalLine
from app.pagination import MAX_LIMIT, decode_cursor, encode_cursor
from app.services import chart_codes as cc
from app.services.common import get_account, next_journal_number

BASE_DATE = date(2026, 3, 1)


def make_entries(db, user, count: int, *, all_same_date: bool = False):
    """count سند می‌سازد. با all_same_date همه هم‌تاریخ می‌شوند تا مرز صفحه تست شود."""
    cash = get_account(db, cc.CASH).id
    capital = get_account(db, "3101").id
    for i in range(count):
        entry_date = BASE_DATE if all_same_date else BASE_DATE + timedelta(days=i)
        db.add(
            JournalEntry(
                number=next_journal_number(db),
                entry_date=entry_date,
                description=f"سند تست {i}",
                source_type="manual",
                created_by_id=user.id,
                lines=[
                    JournalLine(account_id=cash, debit=Decimal(1000), credit=0, description=""),
                    JournalLine(account_id=capital, debit=0, credit=Decimal(1000), description=""),
                ],
            )
        )
    db.flush()


def walk_all_pages(client, url: str, limit: int) -> list[dict]:
    """همه‌ی صفحه‌ها را دنبال می‌کند و ردیف‌ها را به‌ترتیب برمی‌گرداند."""
    collected: list[dict] = []
    cursor = None
    for _ in range(100):  # سقف ایمنی در برابر حلقه‌ی بی‌پایان
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        body = client.get(url, params=params).json()
        collected.extend(body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            return collected
    pytest.fail("صفحه‌بندی تمام نشد — احتمالاً کرسر پیش نمی‌رود")


# --- شکل پاسخ ------------------------------------------------------------------


def test_response_uses_page_envelope(db, user, client):
    make_entries(db, user, 3)
    body = client.get("/api/journal-entries").json()
    assert set(body) == {"items", "next_cursor"}
    assert isinstance(body["items"], list)


def test_last_page_has_null_cursor(db, user, client):
    make_entries(db, user, 3)
    body = client.get("/api/journal-entries", params={"limit": 50}).json()
    assert body["next_cursor"] is None


def test_limit_is_respected(db, user, client):
    make_entries(db, user, 10)
    body = client.get("/api/journal-entries", params={"limit": 4}).json()
    assert len(body["items"]) == 4
    assert body["next_cursor"] is not None


# --- درستی پیمایش (مهم‌ترین بخش) ------------------------------------------------


def test_full_traversal_returns_every_row_exactly_once(db, user, client):
    make_entries(db, user, 23)
    seen = walk_all_pages(client, "/api/journal-entries", limit=5)

    numbers = [row["number"] for row in seen]
    assert len(numbers) == len(set(numbers)), "بعضی سندها تکراری برگشتند"
    assert len(numbers) >= 23, f"انتظار حداقل ۲۳ سند، {len(numbers)} برگشت — ردیف جا افتاده"


def test_traversal_is_correct_when_all_rows_share_a_date(db, user, client):
    """حالت خطرناک: اگر کلید فقط تاریخ بود، این تست ردیف‌های گم‌شده را نشان می‌داد."""
    make_entries(db, user, 17, all_same_date=True)
    seen = walk_all_pages(client, "/api/journal-entries", limit=4)

    numbers = [row["number"] for row in seen if row["description"].startswith("سند تست")]
    assert len(numbers) == len(set(numbers)), "ردیف‌های هم‌تاریخ تکرار شدند"
    assert len(numbers) == 17, f"از ۱۷ سند هم‌تاریخ فقط {len(numbers)} برگشت"


def test_pages_are_in_descending_order(db, user, client):
    make_entries(db, user, 12)
    seen = walk_all_pages(client, "/api/journal-entries", limit=5)
    keys = [(row["entry_date"], row["number"]) for row in seen]
    assert keys == sorted(keys, reverse=True), "ترتیب نزولی بین صفحه‌ها حفظ نشد"


def test_page_size_of_one_still_traverses_correctly(db, user, client):
    """مرزی‌ترین حالت limit — هر ردیف صفحه‌ی خودش."""
    make_entries(db, user, 6, all_same_date=True)
    seen = walk_all_pages(client, "/api/journal-entries", limit=1)
    numbers = [r["number"] for r in seen if r["description"].startswith("سند تست")]
    assert len(numbers) == len(set(numbers)) == 6


# --- اعتبارسنجی ورودی ----------------------------------------------------------


@pytest.mark.parametrize("bad", ["not-base64!!", "eyJub3QiOiAibGlzdCJ9", "###"])
def test_malformed_cursor_returns_400_not_500(db, user, client, bad):
    make_entries(db, user, 2)
    assert client.get("/api/journal-entries", params={"cursor": bad}).status_code == 400


def test_cursor_with_wrong_field_count_returns_400(db, user, client):
    make_entries(db, user, 2)
    bad = encode_cursor(["2026-03-01"])  # لیست انتظار دو مقدار دارد
    assert client.get("/api/journal-entries", params={"cursor": bad}).status_code == 400


@pytest.mark.parametrize("limit", [0, -1, MAX_LIMIT + 1])
def test_out_of_range_limit_is_rejected(db, user, client, limit):
    assert client.get("/api/journal-entries", params={"limit": limit}).status_code == 422


# --- کدگذاری کرسر ---------------------------------------------------------------


def test_cursor_roundtrip_preserves_values():
    assert decode_cursor(encode_cursor([date(2026, 3, 15), 42])) == ["2026-03-15", 42]


def test_cursor_is_opaque_base64():
    """کرسر نباید مقادیر را به‌صورت خوانا لو بدهد تا کلاینت به ساختارش وابسته نشود."""
    cursor = encode_cursor([date(2026, 3, 15), 42])
    assert "2026" not in cursor
    assert "=" not in cursor, "padding باید حذف شده باشد تا در URL امن بماند"


# --- سایر اندپوینت‌ها ------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "/api/sales-invoices",
        "/api/purchase-invoices",
        "/api/sales-quotations",
        "/api/sales-returns",
        "/api/purchase-returns",
        "/api/stock-transfers",
        "/api/checks",
        "/api/bank-transactions",
        "/api/petty-cash",
        "/api/treasury",
        "/api/contacts",
        "/api/items",
        "/api/stock-adjustments",
        "/api/payslips",
    ],
)
def test_every_paginated_list_uses_the_envelope(db, user, client, url):
    body = client.get(url).json()
    assert set(body) == {"items", "next_cursor"}, f"{url} پوشش صفحه‌بندی ندارد"


def test_filters_and_pagination_coexist(db, user, client):
    """payslips هم فیلتر دارد هم صفحه‌بندی.

    ریسک واقعی این است که کرسر فیلتر را از دست بدهد و ردیف‌های دوره‌ی دیگر نشت کنند،
    یا کلاینت به مسیری که از قبل ? دارد یک ? دوم بچسباند.
    """
    from uuid import uuid4

    other_period = uuid4()
    res = client.get("/api/payslips", params={"period_id": str(other_period), "limit": 5})
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"items", "next_cursor"}
    assert body["items"] == [], "فیلتر روی دوره‌ی ناموجود باید خالی برگرداند"


# --- جهت صعودی (مسیر کد جداگانه) -----------------------------------------------


def test_ascending_traversal_returns_every_row_exactly_once(db, user, client):
    """contacts صعودی مرتب می‌شود؛ مقایسه‌ی tuple باید > باشد نه <."""
    from tests.factories import make_contact

    for i in range(14):
        make_contact(db, name=f"طرف‌حساب {i:02d}")
    db.flush()

    seen = walk_all_pages(client, "/api/contacts", limit=4)
    names = [row["name"] for row in seen]
    assert len(names) == len(set(names)), "طرف‌حساب تکراری برگشت"
    assert len(names) >= 14, f"از ۱۴ طرف‌حساب فقط {len(names)} برگشت"
    assert names == sorted(names), "ترتیب صعودی بین صفحه‌ها حفظ نشد"


def test_ascending_traversal_handles_duplicate_names(db, user, client):
    """نام یکتا نیست — id باید تساوی را بشکند وگرنه ردیف‌ها گم می‌شوند."""
    from tests.factories import make_contact

    for _ in range(9):
        make_contact(db, name="نام تکراری")
    db.flush()

    seen = walk_all_pages(client, "/api/contacts", limit=2)
    ids = [row["id"] for row in seen if row["name"] == "نام تکراری"]
    assert len(ids) == len(set(ids)), "ردیف‌های هم‌نام تکرار شدند"
    assert len(ids) == 9, f"از ۹ طرف‌حساب هم‌نام فقط {len(ids)} برگشت"
