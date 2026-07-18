"""security: نقش «دمو» wildcard خود را از دست می‌دهد (مهار نشت داده‌ی مشتریان)

نقش demo با permissions برابر {"*": ["view"]} ساخته شده بود. چون Role.has_permission
روی کلید "*" هم مچ می‌کند، این نقش شرط require_permission("billing", "view") را پاس
می‌کرد و به /api/admin/purchases دسترسی داشت — که نام، ایمیل، تلفن و کد رهگیری زرین‌پال
همه‌ی مشتریان پولی را برمی‌گرداند. رمز این حساب روی صفحه‌ی عمومی بازاریابی نمایش داده
می‌شود، پس عملاً این داده بدون احراز هویت در دسترس بود.

seed() نقش‌های موجود را به‌روز نمی‌کند (فقط اگر وجود نداشته باشند می‌سازد)، بنابراین
تغییر DEFAULT_ROLES به‌تنهایی دیتابیس‌های موجود را اصلاح نمی‌کند و این migration لازم است.

اصلاح ساختاری اصلی جای دیگری است: اندپوینت‌های /api/admin/purchases از RBAC مستأجر به
require_platform_admin منتقل شدند. این migration لایه‌ی دوم دفاع است.

Revision ID: 0014
Revises: 0013
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEMO_PERMISSIONS = {
    "accounting": ["view"],
    "invoices": ["view"],
    "inventory": ["view"],
    "checks_bank": ["view"],
    "payroll": ["view"],
}


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE roles SET permissions = CAST(:perms AS jsonb) WHERE key = 'demo'").bindparams(
            perms=json.dumps(DEMO_PERMISSIONS, ensure_ascii=False)
        )
    )


def downgrade() -> None:
    # هشدار: این downgrade آسیب‌پذیری را برمی‌گرداند و فقط برای کامل بودن زنجیره است.
    op.execute(
        sa.text("UPDATE roles SET permissions = CAST(:perms AS jsonb) WHERE key = 'demo'").bindparams(
            perms=json.dumps({"*": ["view"]}, ensure_ascii=False)
        )
    )
