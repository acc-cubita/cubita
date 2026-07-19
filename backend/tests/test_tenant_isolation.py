"""ایزوله‌سازی مستأجر.

این پرونده مهم‌ترین تضمین امنیتی سیستم را می‌سنجد و عمداً بر پایه‌ی introspection
نوشته شده، نه فهرست دستی جدول‌ها. دلیلش این است که فهرست دستی کهنه می‌شود: کسی
جدول سی‌وهشتم را اضافه می‌کند، یادش می‌رود tenant_id بگذارد، و هیچ‌چیز سر و صدا
نمی‌کند تا روزی که داده‌ی یک مشتری در حساب مشتری دیگر ظاهر شود.

با پیمایش Base.metadata.tables، جدول جدید **خودکار** ثبت‌نام می‌شود و بدون
tenant_id/RLS/سیاست، تست قرمز می‌شود. تنها راه معافیت، افزودن صریح نام به
GLOBAL_TABLES است که در diff دیده می‌شود.
"""
import pytest
from sqlalchemy import text

from app.database import Base
from app.tenancy import GLOBAL_TABLES, TENANT_SETTING, policy_name, tenant_tables
from tests.conftest import TEST_SCHEMA

TEST_UUID = "11111111-1111-1111-1111-111111111111"

TENANT_TABLES = tenant_tables(Base.metadata)


def test_there_are_tenant_tables_to_check():
    """محافظ خودِ تست: اگر روزی فهرست خالی شد، بقیه‌ی تست‌ها بی‌صدا سبز می‌شوند."""
    assert len(TENANT_TABLES) > 30, f"فهرست جدول‌های مستأجرمحور مشکوک است: {len(TENANT_TABLES)}"


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_tenant_table_has_tenant_id_column(table):
    columns = Base.metadata.tables[table].columns
    assert "tenant_id" in columns, (
        f"جدول «{table}» ستون tenant_id ندارد. یا TenantMixin را اضافه کنید، "
        f"یا اگر واقعاً سراسری است نامش را صراحتاً در GLOBAL_TABLES بگذارید."
    )


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_tenant_id_is_not_nullable(table):
    col = Base.metadata.tables[table].columns["tenant_id"]
    assert not col.nullable, f"tenant_id در «{table}» nullable است — ردیف بی‌مستأجر یعنی ردیف بی‌حفاظ"


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_row_level_security_is_enabled_and_forced(db, table):
    """FORCE حیاتی است: بدون آن مالک جدول از RLS رد می‌شود و اپ همان مالک است.

    فیلتر روی schema اجباری است: جدول هم‌نام در schema اصلی هم وجود دارد و بدون
    آن، تست ممکن است وضعیت جدول اشتباهی را بسنجد و بی‌جهت سبز یا قرمز شود.
    """
    row = db.execute(
        text(
            "SELECT c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relname = :t AND c.relkind = 'r' AND n.nspname = :s"
        ),
        {"t": table, "s": TEST_SCHEMA},
    ).first()
    assert row is not None, f"جدول «{table}» در schema تست پیدا نشد"
    enabled, forced = row
    assert enabled, f"RLS روی «{table}» فعال نیست"
    assert forced, f"FORCE ROW LEVEL SECURITY روی «{table}» فعال نیست — مالک جدول سیاست را دور می‌زند"


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_isolation_policy_exists(db, table):
    found = db.execute(
        text("SELECT count(*) FROM pg_policies WHERE tablename = :t AND policyname = :p AND schemaname = :s"),
        {"t": table, "p": policy_name(table), "s": TEST_SCHEMA},
    ).scalar()
    assert found == 1, f"سیاست ایزوله‌سازی روی «{table}» وجود ندارد"


def test_global_tables_are_deliberately_listed():
    """هر معافیت باید عمدی باشد، نه نتیجه‌ی غلط‌املایی."""
    known = set(Base.metadata.tables) | {"alembic_version"}
    unknown = GLOBAL_TABLES - known
    assert not unknown, f"نام‌های ناشناخته در GLOBAL_TABLES: {sorted(unknown)} — احتمالاً غلط تایپی"


def test_tenant_setting_is_transaction_scoped():
    """مقدار مستأجر نباید از تراکنش بیرون بزند و روی اتصال بماند.

    اگر روزی کسی set_config(..., true) را به SET ساده تغییر دهد، مقدار به اتصال
    می‌چسبد و اتصال به connection pool برمی‌گردد — یعنی درخواست بعدی، که می‌تواند
    مال مستأجر دیگری باشد، همان مقدار را به ارث می‌برد. بدترین حالت شکست ممکن.

    عمداً از fixture `db` استفاده نمی‌کند و زمینه را خالی می‌گذارد، وگرنه رویداد
    after_begin مقدار را روی تراکنش بعدی دوباره می‌نشاند و تست همیشه سبز می‌ماند.
    """
    from app.database import SessionLocal
    from app.tenant_context import get_current_tenant, set_current_tenant

    previous = get_current_tenant()
    set_current_tenant(None)
    session = SessionLocal()
    try:
        session.execute(text("SELECT set_config(:k, :v, true)"), {"k": TENANT_SETTING, "v": TEST_UUID})
        assert session.execute(text(f"SELECT current_setting('{TENANT_SETTING}', true)")).scalar() == TEST_UUID

        session.rollback()
        leaked = session.execute(text(f"SELECT current_setting('{TENANT_SETTING}', true)")).scalar()
        assert not leaked, f"مقدار مستأجر بعد از پایان تراکنش باقی ماند: {leaked!r} — نشت بین درخواست‌ها"
    finally:
        session.close()
        # بازگرداندن زمینه اجباری است: ContextVar بین تست‌های همین پروسه مشترک است
        # و خالی گذاشتنش تست‌های بعدی را با خطای RLS می‌شکند.
        set_current_tenant(previous)
