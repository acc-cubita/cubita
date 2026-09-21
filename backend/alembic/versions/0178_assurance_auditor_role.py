"""نقشِ «حسابرس» برای مستأجرهای موجود

Revision ID: 0178
Revises: 0177

## چرا مهاجرت لازم است

`DEFAULT_ROLES` فقط هنگامِ **ساختِ** کسب‌وکار seed می‌شود (`app/seed.py`)، پس نقشِ
تازه به هیچ حسابِ موجودی نمی‌رسد. بدونِ این بک‌فیل، تأییدِ حسابرسی برای هر مشتریِ
فعلی با خطای «نقشِ auditor در این کسب‌وکار تعریف نشده است» شکست می‌خورد — یعنی
دقیقاً برای همه‌ی مشتری‌هایی که داریم.

## چرا `rls_disabled` این‌جا **الزامی** است

`roles` جدولِ مستأجرمحور است و سیاستِ `FORCE ROW LEVEL SECURITY` دارد. مهاجرت
بدونِ زمینه‌ی مستأجر اجرا می‌شود، پس `current_setting('app.tenant_id')` تهی است و
سیاست صفر ردیف می‌بیند: `INSERT` با `WITH CHECK` رد می‌شود یا `SELECT`ِ داخلِ
`NOT EXISTS` هیچ‌چیز نمی‌بیند و ردیفِ تکراری می‌سازد. همان کلاسِ خرابی که
`app/migration_utils.py` مستندش کرده («مهاجرت موفق اعلام شد و هیچ حسابی علامت
نخورد»).

## مجوزها

عینِ `DEFAULT_ROLES["auditor"]`: فقط `view` روی ماژول‌های کاری، به‌علاوه‌ی
`assurance: [view, refresh]`. بدونِ wildcard و بدونِ `users`.
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.migration_utils import rls_disabled

revision: str = "0178"
down_revision: Union[str, None] = "0177"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

AUDITOR_PERMISSIONS = {
    "accounting": ["view"],
    "invoices": ["view"],
    "inventory": ["view"],
    "checks_bank": ["view"],
    "assets": ["view"],
    "payroll": ["view"],
    "crm": ["view"],
    "manufacturing": ["view"],
    "contracting": ["view"],
    "moadian": ["view"],
    "calendar": ["view"],
    "audit": ["view"],
    "assurance": ["view", "refresh"],
}


def upgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, ["roles"]):
        conn.execute(
            sa.text(
                """
                INSERT INTO roles (id, tenant_id, key, name, permissions, created_at, updated_at)
                SELECT gen_random_uuid(), t.id, 'auditor', 'حسابرس', CAST(:perms AS jsonb), now(), now()
                FROM tenants t
                WHERE NOT EXISTS (
                    SELECT 1 FROM roles r WHERE r.tenant_id = t.id AND r.key = 'auditor'
                )
                """
            ),
            {"perms": json.dumps(AUDITOR_PERMISSIONS, ensure_ascii=False)},
        )


def downgrade() -> None:
    #: حذفِ امن است: کلیدِ `auditor` پیش از این مهاجرت در هیچ مستأجری وجود نداشت،
    #: پس هرچه هست از همین‌جا آمده. عضویت‌هایی که به آن اشاره می‌کنند با
    #: مهاجرتِ ۰۱۷۱ (که قرارداد را هم می‌برد) برمی‌گردند.
    conn = op.get_bind()
    with rls_disabled(conn, ["roles"]):
        conn.execute(sa.text("DELETE FROM roles WHERE key = 'auditor'"))
