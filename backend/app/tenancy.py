"""مرز داده‌ی مستأجر — تک منبع حقیقت.

اینجا تصمیم می‌گیرد کدام جدول به مستأجر تعلق دارد و کدام سراسری است. تست
introspection و مهاجرت‌ها هر دو از همین فهرست می‌خوانند، پس اگر جدول جدیدی اضافه
شود و کسی یادش برود tenant_id بگذارد، تست قرمز می‌شود بدون اینکه هیچ بازبینی‌کننده‌ای
لازم باشد آن را به یاد بیاورد. تنها جایی که تصمیم انسانی ثبت می‌شود همین fileست و
هر تغییرش در diff دیده می‌شود.

**جدول‌های ردیف هم tenant_id خودشان را می‌گیرند** (journal_lines، sales_invoice_lines و…)
هرچند والدشان هم دارد. دلیلش این است که سیاست RLS per-table است: بدون ستون روی خودِ
جدول، یک کوئری مستقیم به journal_lines ردیف همه‌ی مستأجرها را برمی‌گرداند — و دقیقاً
همه‌ی گزارش‌های مالی مستقیم روی همین جدول تجمیع می‌کنند.
"""
from typing import Iterable

# نام متغیر جلسه‌ی Postgres که مستأجر جاری در آن ست می‌شود
TENANT_SETTING = "app.tenant_id"

#: جدول‌هایی که عمداً مستأجر ندارند.
#:
#: - alembic_version: فراداده‌ی مهاجرت
#: - tenants: خودِ فهرست مستأجرها
#: - plans / purchases: صفحه‌ی کنترل پلتفرم (قیف فروش خودِ کوبیتا)، نه دفتر مشتری
#: - users: هویت سراسری است؛ یک حسابدار مستقل می‌تواند عضو چند کسب‌وکار باشد،
#:   پس تعلقش از طریق memberships بیان می‌شود نه یک ستون روی خودش
#: - memberships / platform_admins: پیوند هویت به مستأجر و ادمین پلتفرم
#: - auth_tokens: بازیابی رمز و پذیرش دعوت *قبل از* احراز هویت اجرا می‌شوند، پس در
#:   لحظه‌ی مصرف هیچ زمینه‌ی مستأجری وجود ندارد و سیاست RLS هر لینک معتبری را هم
#:   «نامعتبر» نشان می‌داد. محافظت اینجا خودِ راز است نه سیاست؛ توضیح کامل در
#:   models/auth_token.py
GLOBAL_TABLES = frozenset(
    {
        "alembic_version",
        "tenants",
        "plans",
        "purchases",
        "users",
        "memberships",
        "platform_admins",
        "auth_tokens",
    }
)


def tenant_tables(metadata) -> list[str]:
    """جدول‌هایی که باید tenant_id، RLS و سیاست داشته باشند."""
    return sorted(name for name in metadata.tables if name not in GLOBAL_TABLES)


def is_tenant_table(name: str) -> bool:
    return name not in GLOBAL_TABLES


def policy_name(table: str) -> str:
    return f"{table}_tenant_isolation"


def rls_statements(tables: Iterable[str]) -> list[str]:
    """دستورهای فعال‌سازی RLS برای هر جدول مستأجرمحور.

    FORCE اختیاری نیست: بدون آن، مالکِ جدول کلاً RLS را دور می‌زند — و اپ امروز
    با همان کاربری وصل می‌شود که مالک جدول‌هاست. یعنی بدون FORCE، سیاست‌ها روی
    کاغذ فعال‌اند ولی در عمل هیچ‌چیز را محدود نمی‌کنند.

    آرگومان دوم current_setting برابر true است تا نبودِ متغیر به‌جای خطا، NULL
    برگرداند؛ NULL در مقایسه یعنی صفر ردیف. fail closed، نه fail loud — چون خطای
    بلند وسوسه می‌کند کسی سیاست را «برای رفع مشکل» غیرفعال کند.
    """
    out: list[str] = []
    for t in tables:
        out.append(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        out.append(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        out.append(f"DROP POLICY IF EXISTS {policy_name(t)} ON {t}")
        out.append(
            f"CREATE POLICY {policy_name(t)} ON {t} "
            f"USING (tenant_id = current_setting('{TENANT_SETTING}', true)::uuid) "
            f"WITH CHECK (tenant_id = current_setting('{TENANT_SETTING}', true)::uuid)"
        )
    return out
