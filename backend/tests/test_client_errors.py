"""گزارشِ کرشِ کلاینت.

قراردادی که اپِ موبایل به آن تکیه می‌کند اینجا سنجیده می‌شود — مخصوصاً دو چیز که
اگر بشکنند، *بی‌صدا* گزارش‌ها را از دست می‌دهیم: ثبتِ بدونِ توکن، و بی‌اثر بودنِ
ارسالِ دوباره‌ی یک صف.
"""
from datetime import datetime, timezone

import pytest

from app.models.client_error import ClientError


def _report(client_id: str, **over) -> dict:
    base = {
        "id": client_id,
        "at": datetime.now(timezone.utc).isoformat(),
        "fatal": False,
        "name": "TypeError",
        "message": "چیزی شکست",
        "stack": "at Foo (bar.ts:1:1)",
        "screen": "Dashboard",
        "app_version": "1.7.0",
        "platform": "android",
        "os_version": "14",
        "device": "Pixel 7",
    }
    base.update(over)
    return base


def test_accepts_reports_without_any_token(client, db):
    """مهم‌ترین تست: کرشِ *پیش از ورود* باید ثبت شود.

    اگر این بشکند، دقیقاً ارزشمندترین گزارش‌ها (خطای راه‌اندازی و صفحه‌ی ورود)
    هرگز نمی‌رسند — و هیچ خطایی هم دیده نمی‌شود.
    """
    res = client.post("/api/client-errors", json={"reports": [_report("c-1")]})
    assert res.status_code == 202, res.text
    assert res.json() == {"stored": 1, "duplicates": 0}

    row = db.query(ClientError).filter_by(client_id="c-1").one()
    assert row.message == "چیزی شکست"
    assert row.screen == "Dashboard"
    assert row.user_id is None


def test_resending_the_same_queue_does_not_duplicate(client, db):
    """دستگاه تا پاسخِ موفق نگیرد صف را نگه می‌دارد و دوباره می‌فرستد — رفتارِ درست.

    بدونِ بی‌اثر بودنِ ارسالِ دوباره، یک قطعیِ شبکه یعنی چند رکورد از یک کرش.
    """
    batch = {"reports": [_report("c-2"), _report("c-3")]}
    first = client.post("/api/client-errors", json=batch)
    second = client.post("/api/client-errors", json=batch)

    assert first.json() == {"stored": 2, "duplicates": 0}
    assert second.json() == {"stored": 0, "duplicates": 2}
    assert db.query(ClientError).filter(ClientError.client_id.in_(["c-2", "c-3"])).count() == 2


def test_attaches_the_user_when_a_valid_token_is_sent(client, db, user):
    # توکنِ واقعی ساخته می‌شود چون این اندپوینت عمداً هدر را خودش می‌خواند و از
    # وابستگیِ احراز استفاده نمی‌کند — پس overrideِ fixture رویش اثری ندارد.
    from app.security import create_access_token

    token = create_access_token(user)
    res = client.post(
        "/api/client-errors",
        json={"reports": [_report("c-4")]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 202
    assert db.query(ClientError).filter_by(client_id="c-4").one().user_id == user.id


def test_a_broken_token_is_ignored_not_rejected(client, db):
    """توکنِ خراب نباید گزارش را دور بیندازد — گزارشِ بی‌کاربر از هیچ بهتر است."""
    res = client.post(
        "/api/client-errors",
        json={"reports": [_report("c-5")]},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert res.status_code == 202
    assert db.query(ClientError).filter_by(client_id="c-5").one().user_id is None


def test_a_long_stack_is_trimmed_not_refused(client, db):
    """بریدن به‌جای رد کردن: گزارشِ بریده از هیچ گزارشی بهتر است."""
    res = client.post(
        "/api/client-errors",
        json={"reports": [_report("c-6", stack="x" * 50_000, message="y" * 5_000)]},
    )
    assert res.status_code == 202
    row = db.query(ClientError).filter_by(client_id="c-6").one()
    assert len(row.stack) == 10_000
    assert len(row.message) == 1_000


def test_an_oversized_batch_is_refused(client):
    """سقفِ دسته — وگرنه اندپوینتِ بی‌احراز دری برای پرکردنِ دیتابیس است."""
    res = client.post(
        "/api/client-errors",
        json={"reports": [_report(f"big-{i}") for i in range(51)]},
    )
    assert res.status_code == 422


def test_an_empty_batch_is_harmless(client):
    res = client.post("/api/client-errors", json={"reports": []})
    assert res.status_code == 202
    assert res.json() == {"stored": 0, "duplicates": 0}


def test_listing_refuses_an_ordinary_user(client):
    """stack trace داده‌ی عملیاتیِ ماست، نه دفترِ مشتری.

    خواندنِ گزارش‌ها به `/api/admin/client-errors` منتقل شد؛ مسیرِ قدیمی دیگر
    وجود ندارد و ingestِ عمومی سرِ جایش ماند.
    """
    assert client.get("/api/client-errors").status_code == 405
    assert client.get("/api/admin/client-errors").status_code in (401, 403)


def test_staff_can_read_the_reports(client, staff_client, db):
    client.post("/api/client-errors", json={"reports": [_report("visible")]})
    r = staff_client(role="owner").get("/api/admin/client-errors")
    assert r.status_code == 200, r.text
    assert any(row["name"] for row in r.json())


@pytest.mark.parametrize("fatal", [True, False])
def test_fatal_flag_round_trips(client, db, fatal):
    res = client.post("/api/client-errors", json={"reports": [_report(f"f-{fatal}", fatal=fatal)]})
    assert res.status_code == 202
    assert db.query(ClientError).filter_by(client_id=f"f-{fatal}").one().fatal is fatal
