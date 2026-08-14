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
from contextlib import contextmanager
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

from app.audit import append_only_statements  # noqa: E402
from app.database import Base, SessionLocal, engine, get_db  # noqa: E402
from app.models.user import User  # noqa: E402
from app.tenancy import rls_statements, tenant_tables  # noqa: E402
from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant, set_current_tenant  # noqa: E402

# seed در ماژول‌های زیر import می‌شود و همگی روی engine بالا سوارند
from app.seed import provision_tenant, seed_platform  # noqa: E402

SEED_OWNER_EMAIL = "test-owner@example.invalid"
SEED_OWNER_PASSWORD = "TestOwnerPassword!2026"

#: مستأجر اصلی تست. تست‌های ایزوله‌سازی مستأجر دوم را خودشان می‌سازند.
PRIMARY_SLUG = "primary-test-tenant"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """schema تست را از صفر می‌سازد، RLS را اعمال می‌کند، و یک مستأجر آماده می‌کند.

    RLS اینجا دستی اعمال می‌شود چون create_all فقط جدول می‌سازد و از سیاست‌ها خبر
    ندارد؛ آن‌ها در مهاجرت زندگی می‌کنند. اگر این کار نشود، تست‌ها روی دنیایی
    اجرا می‌شوند که ایزوله‌سازی در آن خاموش است — یعنی دقیقاً چیزی را که باید
    بسنجند نمی‌سنجند.
    """
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {TEST_SCHEMA}"))

    Base.metadata.create_all(bind=engine)

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for stmt in rls_statements(tenant_tables(Base.metadata)):
            conn.execute(text(stmt))
        # trigger فقط‌افزودنیِ دفتر حسابرسی — به همان دلیل RLS بالا: create_all
        # فقط جدول می‌سازد و از trigger خبر ندارد. بدون این، تست‌ها روی جدولی
        # اجرا می‌شوند که می‌شود ویرایشش کرد، یعنی مهم‌ترین خاصیتش سنجیده نمی‌شود.
        for stmt in append_only_statements():
            conn.execute(text(stmt))

    session = SessionLocal()
    try:
        seed_platform(session)
        tenant = provision_tenant(
            session,
            name="کسب‌وکار تست",
            slug=PRIMARY_SLUG,
            owner_email=SEED_OWNER_EMAIL,
            owner_password=SEED_OWNER_PASSWORD,
            owner_name="مالک تست",
        )
        session.commit()
        tenant_id = tenant.id
    finally:
        session.close()

    yield tenant_id

    set_current_tenant(None)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """سقف نرخ بین تست‌ها ریست می‌شود.

    بدون این، تست‌ها روی هم اثر می‌گذارند: چند تست ثبت‌نام پشت‌سرهم به سقف ساعتی
    می‌خورند و تستِ بعدی به‌خاطر کارِ تستِ قبلی شکست می‌خورد — که اشکال‌زدایی‌اش
    گمراه‌کننده است.
    """
    from app.rate_limit import reset_all

    reset_all()
    yield


@pytest.fixture
def tenant_id(_schema):
    return _schema


@pytest.fixture
def db(_schema):
    """Session ایزوله با زمینه‌ی مستأجر ست‌شده؛ هرچه تست بنویسد در پایان برمی‌گردد.

    زمینه هم روی ContextVar و هم روی خودِ تراکنشِ بازِ فعلی نشانده می‌شود: رویداد
    after_begin فقط برای تراکنش‌های *بعدی* شلیک می‌کند، و این تراکنش از قبل باز شده.
    """
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    # مثل production: زمینه به خودِ Session بچسبد، نه فقط به ContextVar
    bind_session_tenant(session, _schema)
    apply_tenant_to_transaction(session, _schema)
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


@contextmanager
def tenant_session(tenant_id):
    """Session مستقل با زمینه‌ی مستأجر — برای تست‌هایی که به تراکنش واقعی نیاز دارند.

    تست‌های همزمانی و مرز تراکنش نمی‌توانند از fixture `db` استفاده کنند (آن همه‌چیز
    را برمی‌گرداند)، ولی بدون زمینه‌ی مستأجر هر نوشتنی با خطای RLS رد می‌شود.
    """
    session = SessionLocal()
    try:
        bind_session_tenant(session, tenant_id)
        apply_tenant_to_transaction(session, tenant_id)
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db, user):
    """کلاینت HTTP روی همان session تست.

    برای سنجیدن قرارداد واقعی اندپوینت (شکل پاسخ، کدهای خطا، پارامترهای کوئری) لازم
    است، نه فقط تابع سرویس. احراز هویت override می‌شود چون هدف این تست‌ها منطق
    اندپوینت است نه مسیر توکن؛ آن جداگانه تست می‌شود.
    """
    from fastapi.testclient import TestClient

    from app.deps import Principal, get_current_user, get_principal
    from app.main import app
    from app.models.tenant import Membership

    membership = db.query(Membership).filter(Membership.user_id == user.id).one()
    principal = Principal(user, membership)

    # get_principal باید override شود نه فقط get_current_user: مسیرها از طریق
    # require_permission به آن وابسته‌اند و بدون این، احراز هویت واقعی اجرا می‌شود.
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
