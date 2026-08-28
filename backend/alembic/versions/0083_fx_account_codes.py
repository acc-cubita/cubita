"""جابه‌جاییِ کدِ حساب‌های تسعیر ارز از ۴۱۰۴/۵۱۰۷ به ۴۱۰۶/۵۱۱۶

Revision ID: 0083
Revises: 0082

مهاجرتِ ۰۰۸۲ دو حسابِ تسعیر ارز را با کدهای ۴۱۰۴ و ۵۱۰۷ به چارتِ پایه اضافه کرد —
ولی این دو کد از قبل مالِ **قالب‌های صنفی** بودند («تخفیفات و برگشت از فروش» و
«هزینه آب، برق، گاز و تلفن»). نتیجه‌اش یک خرابیِ بی‌صدا بود: `apply_template` هر کدی
را که از قبل وجود داشته باشد رد می‌کند، پس کسب‌وکارِ تازه‌ای که قالب می‌زد آن دو
حساب را هرگز نمی‌گرفت و در شمارشِ «چند حساب کم دارید» هم موجود حساب می‌شد.

کد متعلق به مشتری است و قالب‌ها زودتر آنجا بوده‌اند؛ پس حساب‌های تسعیر جابه‌جا
می‌شوند، نه قالب‌ها. جابه‌جایی فقط با تکیه بر `system_role` انجام می‌شود نه کد —
اگر کسی همان کد را دستی به حسابِ دیگری داده باشد، دست نمی‌خورد.

اگر کدِ مقصد در کسب‌وکاری اشغال باشد، آن ردیف عمداً رها می‌شود: شکستنِ کدِ حسابی که
مشتری خودش ساخته، بدتر از ماندنِ یک حسابِ تسعیر روی کدِ غیرایده‌آل است.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.migration_utils import rls_disabled

revision: str = "0083"
down_revision: Union[str, None] = "0082"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: (نقشِ سیستمی، کدِ قدیم، کدِ تازه)
MOVES = (("fx_gain", "4104", "4106"), ("fx_loss", "5107", "5116"))


def _move(conn, role: str, old: str, new: str) -> None:
    # `accounts` مستأجرمحور و FORCE-RLS است: بدونِ rls_disabled این UPDATE بی‌صدا
    # صفر ردیف می‌بیند و مهاجرت «موفق» گزارش می‌دهد.
    conn.execute(
        sa.text(
            """
            UPDATE accounts AS a
               SET code = :new
             WHERE a.system_role = :role
               AND a.code = :old
               AND NOT EXISTS (
                     SELECT 1 FROM accounts AS b
                      WHERE b.tenant_id = a.tenant_id AND b.code = :new
                   )
            """
        ),
        {"role": role, "old": old, "new": new},
    )


def upgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, ["accounts"]):
        for role, old, new in MOVES:
            _move(conn, role, old, new)


def downgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, ["accounts"]):
        for role, old, new in MOVES:
            _move(conn, role, new, old)
