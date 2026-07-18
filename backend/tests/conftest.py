"""زیرساخت تست.

**روی PostgreSQL واقعی اجرا می‌شود، نه SQLite.** طراحی این سیستم به SEQUENCE بومی،
JSONB، و Numeric(18,0) وابسته است و در فاز بعد به RLS هم وابسته خواهد شد؛ SQLite
هیچ‌کدام را درست شبیه‌سازی نمی‌کند و تست سبز روی آن چیزی را اثبات نمی‌کرد.

**ایزوله‌سازی با schema جداست، نه دیتابیس جدا** — چون کاربر برنامه مجوز CREATE DATABASE
ندارد ولی CREATE SCHEMA دارد. search_path در سطح URL تزریق می‌شود تا `app.database.engine`
(که seed و همه‌ی سرویس‌ها از آن استفاده می‌کنند) خودکار داخل schema تست بیفتد. بدون این
کار، فراخوانی seed() مستقیماً روی داده‌ی واقعی می‌نوشت.

**هر تست در تراکنش خودش rollback می‌شود.** چون سرویس‌ها خودشان db.commit() صدا می‌زنند
(۳۸ نقطه)، session با join_transaction_mode="create_savepoint" ساخته می‌شود تا آن
commitها فقط تا savepoint بروند و rollback بیرونی همچنان همه‌چیز را پاک کند.
"""
import os
from urllib.parse import quote

import pytest

TEST_SCHEMA = "cubita_test"

# --- باید قبل از ساخته شدن engine اپ انجام شود ---------------------------------
# گاردهای production را برای تست خنثی می‌کنیم تا اجرای تست به محتوای .env توسعه‌دهنده
# وابسته نباشد (که ممکن است ZARINPAL_SANDBOX=false داشته باشد و boot را رد کند).
os.environ["ENV"] = "development"
os.environ["ZARINPAL_SANDBOX"] = "true"
os.environ["JWT_SECRET"] = "test-only-secret-not-used-outside-pytest-0123456789"
os.environ["PLATFORM_ADMIN_EMAILS"] = ""

from app.config import get_settings  # noqa: E402

_base_url = os.environ.get("TEST_DATABASE_URL") or get_settings().database_url
_sep = "&" if "?" in _base_url else "?"
os.environ["DATABASE_URL"] = f"{_base_url}{_sep}options={quote(f'-csearch_path={TEST_SCHEMA}')}"
get_settings.cache_clear()

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import Base, engine, get_db  # noqa: E402
from app.models.user import User  # noqa: E402

# seed در ماژول‌های زیر import می‌شود و همگی روی engine بالا سوارند
from app.seed import seed  # noqa: E402

SEED_OWNER_EMAIL = "test-owner@example.invalid"
SEED_OWNER_PASSWORD = "TestOwnerPassword!2026"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """schema تست را از صفر می‌سازد، در پایان کل session حذف می‌کند."""
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {TEST_SCHEMA}"))

    # ساخت جدول‌ها، دنباله‌ها، چارت حساب، نقش‌ها، انبارها و کاربر مالک — همان مسیر نصب واقعی
    seed(SEED_OWNER_EMAIL, SEED_OWNER_PASSWORD, owner_name="مالک تست")

    yield

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))


@pytest.fixture
def db(_schema):
    """Session ایزوله؛ هرچه تست بنویسد (حتی با commit) در پایان برمی‌گردد."""
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def user(db) -> User:
    """کاربر مالک seed‌شده — سرویس‌ها برای created_by به آن نیاز دارند."""
    return db.query(User).filter(User.email == SEED_OWNER_EMAIL).one()


@pytest.fixture
def client(db, user):
    """کلاینت HTTP روی همان session تست.

    برای سنجیدن قرارداد واقعی اندپوینت (شکل پاسخ، کدهای خطا، پارامترهای کوئری) لازم
    است، نه فقط تابع سرویس. احراز هویت override می‌شود چون هدف این تست‌ها منطق
    اندپوینت است نه مسیر توکن؛ آن جداگانه تست می‌شود.
    """
    from fastapi.testclient import TestClient

    from app.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
