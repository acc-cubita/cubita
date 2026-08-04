"""محدودیت نرخ روی اندپوینت‌های عمومی.

بدون این، `login` اجازه‌ی credential stuffing نامحدود می‌دهد و `signup` — که حالا
عمومی است — اجازه‌ی ساخت نامحدود مستأجر. هر مستأجر حدود ۴۰ ردیف می‌سازد (چارت
حساب، نقش‌ها، انبارها، شمارنده‌ها)، پس ثبت‌نام باز عملاً یک بردار پرکردن
پایگاه‌داده است.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.rate_limit import SlidingWindowLimiter, reset_all


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    reset_all()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        reset_all()


# --- خودِ الگوریتم ----------------------------------------------------------------


def test_limiter_allows_up_to_the_cap():
    limiter = SlidingWindowLimiter(max_events=3, window_seconds=60)
    for _ in range(3):
        limiter.check("k")  # نباید خطا بدهد


def test_limiter_blocks_past_the_cap():
    from fastapi import HTTPException

    limiter = SlidingWindowLimiter(max_events=2, window_seconds=60)
    limiter.check("k")
    limiter.check("k")
    with pytest.raises(HTTPException) as exc:
        limiter.check("k")
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers


def test_limiter_keys_are_independent():
    """سقف یک نفر نباید دیگری را قفل کند."""
    limiter = SlidingWindowLimiter(max_events=1, window_seconds=60)
    limiter.check("a")
    limiter.check("b")  # کلید دیگر، باید آزاد باشد


def test_window_slides_and_frees_capacity():
    limiter = SlidingWindowLimiter(max_events=1, window_seconds=0)
    limiter.check("k")
    limiter.check("k")  # پنجره‌ی صفر یعنی رویداد قبلی بلافاصله منقضی است


# --- اندپوینت‌ها ------------------------------------------------------------------


def test_repeated_failed_logins_are_eventually_blocked(client):
    payload = {"email": "nobody@cubita-test.ir", "password": "WrongPassword123"}
    statuses = [client.post("/api/auth/login", json=payload).status_code for _ in range(12)]

    assert 401 in statuses, "تلاش‌های اول باید به‌عنوان رمز غلط رد شوند"
    assert 429 in statuses, "بعد از چند تلاش ناموفق باید محدودیت نرخ اعمال شود"
    # محدودیت باید بعد از چند تلاش برسد، نه از همان اول
    assert statuses.index(429) >= 5, f"محدودیت خیلی زود اعمال شد: {statuses[:6]}"


def test_signup_is_capped(client, db):
    from app.services.email_verification import issue_email_code

    def attempt(i: int):
        email = f"rl-{uuid.uuid4().hex[:8]}@cubita-test.ir"
        return client.post(
            "/api/auth/signup",
            json={
                "business_name": f"کسب‌وکار {i}",
                "owner_name": "مالک",
                "email": email,
                "password": "AStrongPassword2026",
                "code": issue_email_code(db, email),
            },
        ).status_code

    statuses = [attempt(i) for i in range(6)]
    assert 201 in statuses, "ثبت‌نام‌های اول باید موفق باشند"
    assert 429 in statuses, "ثبت‌نام نامحدود یعنی هر کسی می‌تواند پایگاه‌داده را پر کند"


def test_a_blocked_client_gets_retry_after(client):
    payload = {"email": "nobody@cubita-test.ir", "password": "WrongPassword123"}
    for _ in range(12):
        res = client.post("/api/auth/login", json=payload)
        if res.status_code == 429:
            assert res.headers.get("retry-after"), "پاسخ ۴۲۹ باید Retry-After داشته باشد"
            return
    pytest.fail("محدودیت نرخ اصلاً اعمال نشد")
