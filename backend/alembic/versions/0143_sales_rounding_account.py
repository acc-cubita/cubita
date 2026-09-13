"""نقشِ «تعدیلِ گِرد کردن فروش» از حسابِ درآمدِ فروشِ آنلاین جدا می‌شود.

Revision ID: 0143
Revises: 0142

**باگ.** `DEFAULT_CODE_BY_ROLE[SALES_ROUNDING]` کدِ `4102` بود، و `4102` در
`seed.py` «فروش کالا - آنلاین» است — درآمدِ واقعیِ یک کانالِ فروش. چون
`provision_tenant` نقش را از روی همین نگاشت مهر می‌زند
(`ROLE_BY_DEFAULT_CODE.get(code)`)، در چارتِ **هر** کسب‌وکاری نقشِ رند روی حسابِ
فروشِ آنلاین نشسته بود. نتیجه: هر اختلافِ گِردکردنِ فاکتور مستقیم داخلِ درآمدِ
فروشِ آنلاین می‌رفت و پرسشِ «چقدر آنلاین فروختیم؟» دیگر جواب نداشت.

این دقیقاً همان استدلالی است که خودِ کوبیتا برای جداکردنِ `SALES_RETURN` از
«فروش» نوشته («فروشِ یک‌میلیاردی با صد میلیون برگشتی در دفتر ۹۰۰ میلیون دیده
می‌شد») — و همان‌جا نقض شده بود.

**این مهاجرت چه می‌کند.** برای هر کسب‌وکار، اگر نقشِ `sales_rounding` هنوز روی
همان حسابِ فروشِ آنلاین است، نقش را برمی‌دارد و حسابِ اختصاصیِ تازه‌ای با کدِ
`4108` («تعدیلِ گِرد کردن فروش») می‌سازد و نقش را به آن می‌دهد. حسابِ تازه زیرِ
**همان والدِ حسابِ قبلی** می‌نشیند، پس اگر مشتری چارتش را بازشماره‌گذاری کرده
باشد، حساب در شاخه‌ی درستِ درختِ خودش می‌ماند.

**چه نمی‌کند: ردیف‌های سندِ گذشته را جابه‌جا نمی‌کند.** گذشته بازنویسی نمی‌شود.
رندهایی که تا امروز روی حسابِ فروشِ آنلاین نشسته‌اند همان‌جا می‌مانند و از فردا
فقط رندهای تازه به حسابِ اختصاصی می‌روند. برای همین مهاجرت تعدادِ ردیف‌های سندِ
حسابِ قبلی را **چاپ می‌کند**: اگر ناصفر بود، تصمیمِ طبقه‌بندیِ دوباره تصمیمِ
حسابدار است، نه تصمیمِ مهاجرت. (کوئریِ شمارش در `DEPLOY_NOTES.md` هم آمده تا
پیش از استقرار قابلِ اندازه‌گیری باشد.)

**معیارِ تشخیصِ «جابه‌جا نشده».** کد `4102` **یا** نامِ `فروش کالا - آنلاین` —
تا هم چارتِ بازشماره‌گذاری‌شده (نام مانده) و هم چارتِ تغییرِ نام‌داده (کد مانده)
پوشش داده شود. اگر هر دو عوض شده باشند، مشتری آن حساب را آگاهانه مالِ خودش کرده
و مهاجرت دست نمی‌زند — فقط گزارشش می‌کند.

چرا `rls_disabled` و نه حلقه‌ی مستأجر: نقشِ `cubita_app` `BYPASSRLS` ندارد و
`accounts` هم `FORCE ROW LEVEL SECURITY` دارد، پس `SELECT`ِ بی‌زمینه صفر ردیف
می‌دهد — بی هیچ خطایی. همان تله‌ای که یک‌بار مهاجرتِ `system_role` را بی‌صدا
بی‌اثر کرد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.migration_utils import rls_disabled

revision: str = "0143"
down_revision: Union[str, None] = "0142"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE = "sales_rounding"
OLD_CODE = "4102"
NEW_CODE = "4108"
NEW_NAME = "تعدیلِ گِرد کردن فروش"
#: نامی که `seed.CHART_OF_ACCOUNTS` به ۴۱۰۲ می‌دهد — دومین نشانه‌ی «هنوز جابه‌جا نشده».
ONLINE_SALES_NAME = "فروش کالا - آنلاین"

_TABLES = ("accounts", "journal_lines")


def _free_code(conn, tenant_id, wanted: str) -> str:
    """کدِ آزاد در چارتِ همین کسب‌وکار — همان قراردادِ `V`ِ `get_or_create_account`."""
    code = wanted
    while (
        conn.execute(
            sa.text("SELECT 1 FROM accounts WHERE tenant_id = :t AND code = :c"),
            {"t": tenant_id, "c": code},
        ).first()
        is not None
    ):
        code += "V"
    return code


def upgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, _TABLES):
        misplaced = conn.execute(
            sa.text(
                "SELECT id, tenant_id, parent_id, code, name FROM accounts "
                "WHERE system_role = :role AND (code = :code OR name = :name)"
            ),
            {"role": ROLE, "code": OLD_CODE, "name": ONLINE_SALES_NAME},
        ).fetchall()

        for row in misplaced:
            lines = conn.execute(
                sa.text("SELECT count(*) FROM journal_lines WHERE account_id = :a"),
                {"a": row.id},
            ).scalar_one()

            # ترتیب اجباری است: قیدِ `uq_accounts_tenant_system_role` دو حسابِ
            # هم‌نقش را در یک کسب‌وکار نمی‌پذیرد، پس اول نقش برداشته می‌شود.
            conn.execute(
                sa.text("UPDATE accounts SET system_role = NULL WHERE id = :a"),
                {"a": row.id},
            )
            new_code = _free_code(conn, row.tenant_id, NEW_CODE)
            conn.execute(
                sa.text(
                    "INSERT INTO accounts "
                    "(id, tenant_id, code, name, type, is_group, system_role, parent_id) "
                    "VALUES (gen_random_uuid(), :t, :c, :n, 'income', false, :role, :p)"
                ),
                {
                    "t": row.tenant_id,
                    "c": new_code,
                    "n": NEW_NAME,
                    "role": ROLE,
                    "p": row.parent_id,
                },
            )

            # ASCII عمدی: خروجیِ مهاجرت روی کنسولِ ویندوز هم باید چاپ شود.
            print(
                f"[0143] tenant={row.tenant_id} moved '{ROLE}' off account {row.code} "
                f"-> {new_code}; {lines} existing journal line(s) left on {row.code}"
            )

        stranded = conn.execute(
            sa.text(
                "SELECT tenant_id, code FROM accounts "
                "WHERE system_role = :role AND code NOT LIKE :new"
            ),
            {"role": ROLE, "new": NEW_CODE + "%"},
        ).fetchall()
        for row in stranded:
            print(
                f"[0143] tenant={row.tenant_id} left '{ROLE}' on account {row.code} "
                "(renamed and renumbered by the customer) - review manually"
            )


def downgrade() -> None:
    """نقش را به همان حسابِ فروشِ آنلاین برمی‌گرداند.

    **جزئاً پُرافت است:** حسابِ ۴۱۰۸ فقط وقتی حذف می‌شود که هیچ ردیفِ سندی
    نگرفته باشد. اگر گرفته باشد می‌ماند — بی‌نقش، ولی با تاریخچه‌اش. حذفِ حسابی
    که سند خورده در حسابداری قابلِ قبول نیست.
    """
    conn = op.get_bind()
    with rls_disabled(conn, _TABLES):
        created = conn.execute(
            sa.text(
                "SELECT id, tenant_id FROM accounts "
                "WHERE system_role = :role AND code LIKE :new AND name = :n"
            ),
            {"role": ROLE, "new": NEW_CODE + "%", "n": NEW_NAME},
        ).fetchall()

        for row in created:
            target = conn.execute(
                sa.text(
                    "SELECT id FROM accounts WHERE tenant_id = :t "
                    "AND system_role IS NULL AND (code = :code OR name = :name) "
                    "ORDER BY code LIMIT 1"
                ),
                {"t": row.tenant_id, "code": OLD_CODE, "name": ONLINE_SALES_NAME},
            ).scalar()
            if target is None:
                continue

            conn.execute(
                sa.text("UPDATE accounts SET system_role = NULL WHERE id = :a"), {"a": row.id}
            )
            conn.execute(
                sa.text("UPDATE accounts SET system_role = :role WHERE id = :a"),
                {"role": ROLE, "a": target},
            )

            lines = conn.execute(
                sa.text("SELECT count(*) FROM journal_lines WHERE account_id = :a"),
                {"a": row.id},
            ).scalar_one()
            if lines == 0:
                conn.execute(sa.text("DELETE FROM accounts WHERE id = :a"), {"a": row.id})
