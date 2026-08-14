"""نشت بین مستأجرها.

این مهم‌ترین تست امنیتی سیستم است. بقیه‌ی تست‌های ایزوله‌سازی *ساختار* را می‌سنجند
(ستون هست؟ سیاست هست؟)؛ این یکی *رفتار* را می‌سنجد: داده‌ی واقعیِ یک کسب‌وکار در
یک چرخه‌ی کامل مالی ثبت می‌شود و بعد بررسی می‌شود که کسب‌وکار دیگر اصلاً آن را
نمی‌بیند.

حالت شکستی که اینجا گرفته می‌شود، حالتی است که یک نرم‌افزار حسابداری را نابود
می‌کند: دفتر یک مشتری در حساب مشتری دیگر ظاهر شود.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.database import Base, SessionLocal
from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.inventory import Item, StockLedger, Warehouse
from app.models.invoices import SalesInvoice
from app.models.user import Role
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.seed import provision_tenant
from app.services import inventory as inventory_service
from app.services.provisioning import purge_tenant
from app.tenancy import tenant_tables
from app.tenant_context import set_current_tenant

from tests.conftest import SEED_OWNER_EMAIL, tenant_session

TENANT_TABLES = tenant_tables(Base.metadata)


@pytest.fixture
def other_tenant(_schema):
    """مستأجر دوم، کامل provision‌شده و با یک چرخه‌ی مالی واقعی."""
    slug = f"other-{uuid.uuid4().hex[:8]}"
    session = SessionLocal()
    try:
        tenant = provision_tenant(
            session,
            name="کسب‌وکار دوم",
            slug=slug,
            owner_email=f"owner-{slug}@example.invalid",
            owner_password="OtherTenantPassword!2026",
        )
        session.commit()
        tenant_id = tenant.id
    finally:
        session.close()

    # یک خرید و یک فروش واقعی در مستأجر دوم ثبت می‌شود تا داده‌ی قابل نشت وجود داشته باشد
    with tenant_session(tenant_id) as s:
        from app.models.user import User

        owner = s.query(User).filter(User.email == f"owner-{slug}@example.invalid").one()
        # فیلتر صریح روی مستأجر، هرچند RLS هم باید همین کار را بکند: fixture نباید
        # جایی باشد که نشتی کشف می‌شود، وگرنه به‌جای assertion شکست می‌خورد و
        # پیام خطا ربطی به مشکل واقعی ندارد.
        warehouse = (
            s.query(Warehouse).filter(Warehouse.code == "MAIN", Warehouse.tenant_id == tenant_id).one()
        )
        item = Item(sku="SECRET-SKU-001", name="کالای محرمانه مستأجر دوم", sales_price=Decimal(9_000_000))
        s.add(item)
        s.flush()
        inventory_service.post_purchase_invoice(
            s,
            PurchaseInvoiceIn(
                invoice_date=date(2026, 4, 1),
                warehouse_id=warehouse.id,
                lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(20), unit_cost=Decimal(4_000_000))],
            ),
            owner,
        )
        inventory_service.post_sales_invoice(
            s,
            SalesInvoiceIn(
                invoice_date=date(2026, 4, 5),
                warehouse_id=warehouse.id,
                lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(3), unit_price=Decimal(9_000_000))],
            ),
            owner,
        )
        s.commit()

    yield tenant_id

    set_current_tenant(None)
    cleanup = SessionLocal()
    try:
        # حذف مستأجر آبشاری است، پس همه‌ی ردیف‌هایش با آن می‌روند. از مسیر واقعی
        # عبور می‌کند و نه DELETE خام، چون دفتر حسابرسی فقط‌افزودنی است و تنها
        # جایی که دریچه‌اش باز می‌شود همان تابع است — اگر تست راه خودش را می‌ساخت،
        # مسیر واقعی offboarding هرگز سنجیده نمی‌شد.
        purge_tenant(cleanup, tenant_id)
        cleanup.commit()
    finally:
        cleanup.close()


# --- نشت خواندن ------------------------------------------------------------------


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_no_table_ever_returns_another_tenants_rows(db, tenant_id, other_tenant, table):
    """برای هر جدول: هیچ ردیفی با tenant_id غیر از مستأجر جاری دیده نشود.

    پارامتری روی metadata است تا جدول سی‌وششم هم خودکار پوشش بگیرد.
    """
    leaked = db.execute(
        text(f"SELECT count(*) FROM {table} WHERE tenant_id <> :t"), {"t": tenant_id}
    ).scalar()
    assert leaked == 0, f"جدول «{table}» ردیف مستأجر دیگری را برگرداند"


def test_the_other_tenant_really_has_data(other_tenant):
    """محافظ: اگر مستأجر دوم خالی باشد، تست‌های بالا بی‌معنا سبز می‌شوند."""
    with tenant_session(other_tenant) as s:
        assert s.query(Item).filter(Item.sku == "SECRET-SKU-001").count() == 1
        assert s.query(SalesInvoice).count() >= 1
        assert s.query(JournalEntry).count() >= 2
        assert s.query(Account).count() > 20


def test_primary_tenant_cannot_see_the_secret_item(db, other_tenant):
    assert db.query(Item).filter(Item.sku == "SECRET-SKU-001").count() == 0, "کالای مستأجر دیگر دیده شد"


def test_reports_do_not_aggregate_across_tenants(db, tenant_id, other_tenant):
    """گزارش‌ها مستقیم روی journal_lines تجمیع می‌کنند — خطرناک‌ترین مسیر نشت.

    اگر journal_lines سیاست نداشت، تراز آزمایشی ارقام دو کسب‌وکار را با هم جمع
    می‌کرد و هیچ خطایی هم نمی‌داد؛ فقط اعداد غلط می‌شدند.
    """
    foreign = db.execute(text("SELECT count(*) FROM journal_lines WHERE tenant_id <> :t"), {"t": tenant_id}).scalar()
    assert foreign == 0, "ردیف سند مستأجر دیگر در تجمیع گزارش وارد شد"


def test_stock_ledger_is_isolated(db, tenant_id, other_tenant):
    foreign = db.execute(text("SELECT count(*) FROM stock_ledger WHERE tenant_id <> :t"), {"t": tenant_id}).scalar()
    assert foreign == 0, "دفتر موجودی مستأجر دیگر دیده شد"


# --- نشت نوشتن -------------------------------------------------------------------


def test_cannot_write_a_row_belonging_to_another_tenant(db, other_tenant):
    """WITH CHECK باید جلوی جعل tenant_id را بگیرد.

    بدون آن، یک باگ (یا سوءاستفاده) می‌توانست ردیفی را مستقیماً داخل دفتر مستأجر
    دیگر بنویسد — نشتِ نوشتن، که از نشتِ خواندن هم بدتر است.
    """
    from sqlalchemy.exc import ProgrammingError

    with pytest.raises(ProgrammingError):
        db.execute(
            text(
                "INSERT INTO warehouses (id, tenant_id, code, name, is_active, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :t, 'HACK', 'انبار جعلی', true, now(), now())"
            ),
            {"t": other_tenant},
        )
        db.flush()


# --- هویت اتصال ------------------------------------------------------------------


def test_app_role_cannot_bypass_rls(db):
    """نقشی که اپ با آن وصل می‌شود نباید BYPASSRLS داشته باشد.

    این همان تستی است که جلوی «رفع مشکل» اشتباه در production را می‌گیرد: کسی به
    خطای دسترسی برمی‌خورد، به نقش اپ superuser می‌دهد، و بی‌آنکه بداند همه‌ی
    سیاست‌های ایزوله‌سازی را خاموش می‌کند.
    """
    row = db.execute(
        text("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user")
    ).first()
    bypass, is_super = row
    assert not bypass, "نقش اپ BYPASSRLS دارد — همه‌ی سیاست‌های ایزوله‌سازی بی‌اثرند"
    assert not is_super, "نقش اپ superuser است — RLS برایش اعمال نمی‌شود"


def test_force_rls_protects_even_the_table_owner(db):
    """اپ امروز با همان نقشی وصل می‌شود که مالک جدول‌هاست.

    بدون FORCE، مالک از سیاست رد می‌شود و ایزوله‌سازی فقط روی کاغذ است. این تست
    تأیید می‌کند که آن حالت برقرار نیست.
    """
    owner_of_accounts = db.execute(
        text(
            "SELECT pg_get_userbyid(c.relowner) FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relname = 'accounts' AND n.nspname = current_schema()"
        )
    ).scalar()
    current = db.execute(text("SELECT current_user")).scalar()

    if owner_of_accounts == current:
        forced = db.execute(
            text(
                "SELECT c.relforcerowsecurity FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.relname = 'accounts' AND n.nspname = current_schema()"
            )
        ).scalar()
        assert forced, (
            "اپ با نقش مالک جدول وصل می‌شود ولی FORCE ROW LEVEL SECURITY فعال نیست — "
            "یعنی سیاست‌ها اصلاً اعمال نمی‌شوند"
        )

