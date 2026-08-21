"""نقشِ «مامور حمل/انتقال» + گردشِ کارِ تحویل در بازار

Revision ID: 0072
Revises: 0071

- نقش (مورد ۱): درجِ نقشِ `delivery_agent` برای همه‌ی مستأجرهای موجود (نقش مستأجرمحور است،
  پس seed فقط مستأجرهای تازه را می‌سازد؛ این migration موجودها را پر می‌کند). دسترسی فقط
  «بازار: view + deliver».
- تنظیمات: `marketplace_settings.require_delivery` — روشن‌کردنِ گردشِ کارِ تحویل.
- سفارش: `marketplace_orders.delivered_at` و `delivered_by_name` — زمان/ثبت‌کننده‌ی تحویل.

نکته‌ی RLS: مثلِ 0014/0039/0043، این درجِ میان‌مستأجری با اتصالِ مهاجرت (که از RLS عبور
می‌کند) انجام می‌شود؛ نیازی به ست‌کردنِ app.tenant_id نیست.
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.migration_utils import rls_disabled

revision: str = "0072"
down_revision: Union[str, None] = "0071"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DELIVERY_PERMISSIONS = {"marketplace": ["view", "deliver"]}


def upgrade() -> None:
    # ── تنظیماتِ گردشِ کارِ تحویل ──
    op.add_column(
        "marketplace_settings",
        sa.Column("require_delivery", sa.Boolean(), server_default="false", nullable=False),
    )
    # ── ردِ تحویل روی سفارش ──
    op.add_column("marketplace_orders", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "marketplace_orders",
        sa.Column("delivered_by_name", sa.String(200), server_default="", nullable=False),
    )

    # ── نقشِ «مامور حمل/انتقال» برای هر مستأجرِ موجود که هنوز ندارد ──
    # roles تحتِ FORCE RLS است؛ برای درجِ میان‌مستأجری، مثلِ 0039/0043 موقتاً غیرفعال می‌شود.
    conn = op.get_bind()
    with rls_disabled(conn, ["roles"]):
        conn.execute(
            sa.text(
                """
                INSERT INTO roles (id, tenant_id, key, name, permissions)
                SELECT gen_random_uuid(), t.id, 'delivery_agent', 'مامور حمل/انتقال',
                       CAST(:perms AS jsonb)
                FROM tenants t
                WHERE NOT EXISTS (
                    SELECT 1 FROM roles r WHERE r.tenant_id = t.id AND r.key = 'delivery_agent'
                )
                """
            ).bindparams(perms=json.dumps(DELIVERY_PERMISSIONS, ensure_ascii=False))
        )


def downgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, ["roles"]):
        conn.execute(sa.text("DELETE FROM roles WHERE key = 'delivery_agent'"))
    op.drop_column("marketplace_orders", "delivered_by_name")
    op.drop_column("marketplace_orders", "delivered_at")
    op.drop_column("marketplace_settings", "require_delivery")
