"""انحراف بین مهاجرت‌ها و مدل‌ها.

این پرونده بعد از یک باگ واقعی نوشته شد: مستأجر دوم نمی‌توانست ساخته شود چون
ایندکس‌های یکتای سراسری `ix_<جدول>_<ستون>` روی دیتابیس باقی مانده بودند، و اولین
ثبت‌نام واقعی با UniqueViolation شکست خورد. هیچ‌کدام از ۲۹۳ تست ندیدندش.

**اما این تست‌ها آن باگ خاص را بازتولید نمی‌کنند، و صادقانه باید گفت چرا.**
ریشه‌ی آن باگ در مهاجرت‌ها نبود: دیتابیس واقعی با `Base.metadata.create_all()`
ساخته شده بود (کد قدیمی seed)، نه با alembic. آن مسیر برای `unique=True,
index=True` ایندکس یکتا می‌ساخت، در حالی که مهاجرت 0001 همان یکتایی را به‌شکل
CONSTRAINT می‌سازد. مهاجرت 0015 فقط CONSTRAINTها را حذف کرد — که برای دیتابیسِ
مهاجرت‌ساخته کافی بود ولی برای دیتابیسِ create_all‌ساخته نبود. مهاجرت 0017
همان انحراف تاریخی را ترمیم می‌کند.

پس این تست‌ها دو ساختِ تمیز را مقایسه می‌کنند و **انحراف آینده** را می‌گیرند:
مهاجرتی که با مدل‌ها جور نباشد، جدولی که مهاجرت نساخته باشد، یا RLSای که فقط در
create_all اعمال شده باشد. برای سنجیدن انحرافِ دیتابیسِ زنده باید همین مقایسه را
مقابل خودِ production اجرا کرد، که کار یک اسکریپت عملیاتی است نه تست واحد.
"""
import os
from urllib.parse import quote

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.config import get_settings
from app.database import Base
from tests.conftest import TEST_SCHEMA

MIGRATED_SCHEMA = "cubita_migrated"


@pytest.fixture(scope="module")
def migrated_schema():
    """یک schema که واقعاً از صفر مهاجرت کرده — همان چیزی که production است."""
    base_url = get_settings().database_url.split("?")[0]
    admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {MIGRATED_SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {MIGRATED_SCHEMA}"))

    # alembic/env.py خودش URL را از get_settings() می‌خواند و هرچه در Config
    # بگذاریم بازنویسی می‌کند، پس مسیر باید از طریق محیط عوض شود.
    opts = quote(f"-csearch_path={MIGRATED_SCHEMA}")
    previous = os.environ["DATABASE_URL"]
    os.environ["DATABASE_URL"] = f"{base_url}?options={opts}"
    get_settings.cache_clear()
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()

    yield MIGRATED_SCHEMA

    with admin.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {MIGRATED_SCHEMA} CASCADE"))
    admin.dispose()


#: alembic_version دفترچه‌ی خودِ alembic است و در مدل‌ها تعریف نمی‌شود — نبودش
#: در متادیتا درست است، نه انحراف.
IGNORED_TABLES = {"alembic_version"}


def unique_indexes(db, schema: str) -> set[tuple[str, str]]:
    """(جدول، ستون‌ها) برای هر ایندکس یکتا."""
    rows = db.execute(
        text(
            "SELECT tablename, regexp_replace(indexdef, '.*\\((.*)\\)', '\\1') "
            "FROM pg_indexes WHERE schemaname = :s AND indexdef LIKE '%UNIQUE%'"
        ),
        {"s": schema},
    ).all()
    return {(t, c.replace(" ", "")) for t, c in rows if t not in IGNORED_TABLES}


def test_migrations_and_models_agree_on_unique_indexes(db, migrated_schema):
    """مهم‌ترین تست این پرونده — دقیقاً همان باگی که رخ داد را می‌گیرد."""
    from_models = unique_indexes(db, TEST_SCHEMA)
    from_migrations = unique_indexes(db, migrated_schema)

    only_in_migrations = from_migrations - from_models
    only_in_models = from_models - from_migrations

    assert not only_in_migrations, (
        "پایگاه‌داده‌ی مهاجرت‌شده قیدهای یکتایی دارد که در مدل‌ها نیست: "
        f"{sorted(only_in_migrations)}\n"
        "این یعنی production محدودیتی دارد که تست‌ها نمی‌بینند."
    )
    assert not only_in_models, (
        f"مدل‌ها قیدهای یکتایی دارند که مهاجرت نساخته: {sorted(only_in_models)}"
    )


def test_no_tenant_scoped_column_has_a_global_unique_index(db, migrated_schema):
    """هر یکتایی روی جدول مستأجرمحور باید tenant_id را در بر بگیرد.

    یکتای سراسری روی چنین جدولی یعنی مستأجر دوم نمی‌تواند همان مقدار را داشته
    باشد — و شکستش موقع ثبت‌نام مشتری بعدی ظاهر می‌شود، نه در توسعه.
    """
    from app.tenancy import GLOBAL_TABLES

    rows = db.execute(
        text(
            "SELECT tablename, indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = :s AND indexdef LIKE '%UNIQUE%'"
        ),
        {"s": migrated_schema},
    ).all()

    offenders = [
        f"{t}.{name}"
        for t, name, definition in rows
        if t not in GLOBAL_TABLES and "tenant_id" not in definition and not name.endswith("_pkey")
    ]
    assert not offenders, (
        f"ایندکس یکتای سراسری روی جدول مستأجرمحور: {offenders}\n"
        "مستأجر دوم با همان مقدار شکست می‌خورد."
    )


def test_migrations_produce_every_table_the_models_define(db, migrated_schema):
    """جدولی که مهاجرت نساخته باشد فقط در production گم است، نه در تست."""
    migrated = {
        r[0]
        for r in db.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = :s"), {"s": migrated_schema}
        )
    }
    expected = set(Base.metadata.tables)
    missing = expected - migrated - IGNORED_TABLES
    assert not missing, f"مهاجرت‌ها این جدول‌ها را نمی‌سازند: {sorted(missing)}"


def test_rls_is_enabled_on_the_migrated_schema(db, migrated_schema):
    """RLS در مهاجرت زندگی می‌کند، نه در create_all.

    schema تست سیاست‌ها را دستی اعمال می‌کند؛ اگر مهاجرت این کار را نکند،
    production بدون ایزوله‌سازی بالا می‌آید و هیچ تستی متوجه نمی‌شود.
    """
    from app.tenancy import tenant_tables

    unprotected = [
        t
        for t in tenant_tables(Base.metadata)
        if not db.execute(
            text(
                "SELECT c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.relname = :t AND n.nspname = :s"
            ),
            {"t": t, "s": migrated_schema},
        ).scalar()
    ]
    assert not unprotected, f"مهاجرت‌ها FORCE RLS را روی این جدول‌ها فعال نکرده‌اند: {unprotected}"


def test_every_model_module_is_registered_in_the_package():
    """هر ماژول مدل باید در app/models/__init__.py وارد شده باشد.

    این تست بعد از یک باگ واقعی نوشته شد: `document_counters` هیچ‌وقت در
    `app/models/__init__.py` وارد نشده بود و فقط به‌خاطر import غیرمستقیم از
    `app.seed` در متادیتا ظاهر می‌شد.

    نتیجه‌اش این بود که `alembic/env.py` — که فقط `from app.models import *`
    می‌کند — آن جدول را نمی‌دید، و اولین کسی که autogenerate می‌زد مهاجرتی
    می‌گرفت که **جدول شمارنده‌ها را DROP می‌کرد**. تست‌ها این را نمی‌دیدند چون
    conftest تصادفاً `app.seed` را وارد می‌کند و ترتیب import مسئله را می‌پوشاند.

    مهم است که این تست *فقط* از `app.models` وارد کند و نه چیز دیگری، وگرنه
    دوباره همان اثرِ پوشاننده رخ می‌دهد.
    """
    import importlib
    import pkgutil

    import app.models as models_pkg

    declared = set(Base.metadata.tables)
    missing: list[str] = []

    for module in pkgutil.iter_modules(models_pkg.__path__):
        if module.name in ("base",):
            continue  # فقط mixin دارد، جدولی تعریف نمی‌کند
        mod = importlib.import_module(f"app.models.{module.name}")
        for attr in vars(mod).values():
            table = getattr(attr, "__tablename__", None)
            if isinstance(table, str) and table not in declared:
                missing.append(f"{module.name}.{attr.__name__} → {table}")

    assert not missing, (
        "این مدل‌ها در app/models/__init__.py وارد نشده‌اند و alembic آن‌ها را نمی‌بیند: "
        f"{sorted(set(missing))}\n"
        "autogenerate برایشان دستور DROP تولید می‌کند."
    )
