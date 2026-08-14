"""ابزارهای پیشرفته‌ی باشگاه مشتریان — سطوح، جوایز، بازخرید، تولد

Revision ID: 0055
Revises: 0054

چهار ابزارِ بازاریابیِ پیشرفته روی «باشگاه مشتریان»:
  - **بخش‌بندی (RFM):** بدونِ جدول — از رویِ فاکتورهای فروش محاسبه می‌شود.
  - **سطوحِ باشگاه:** جدولِ `loyalty_tiers` (برنز/نقره/طلا/…)، هر سطح آستانه و تخفیفِ خودش.
  - **جوایز و بازخرید:** جدولِ `loyalty_rewards` + ستونِ `reward_id` روی تراکنشِ امتیاز
    (بازخرید = تراکنشِ منفیِ گره‌خورده به جایزه).
  - **تولد/مناسبت:** ستونِ `contacts.birthday` + تنظیماتِ هدیه‌ی تولد.

تنظیماتِ `loyalty_settings` هم گسترش می‌یابد (مبنای سطح، تخفیفِ خودکار، امتیازِ تولد).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0055"
down_revision: Union[str, None] = "0054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_rls(conn, table: str) -> None:
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name(table)} ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
    )


def upgrade() -> None:
    # ── تولد روی مشتری ─────────────────────────────────────
    op.add_column("contacts", sa.Column("birthday", sa.Date(), nullable=True))

    # ── تنظیماتِ گسترش‌یافته‌ی باشگاه ─────────────────────
    op.add_column(
        "loyalty_settings",
        sa.Column("tier_basis", sa.String(length=10), nullable=False, server_default="points"),
    )
    op.add_column(
        "loyalty_settings",
        sa.Column("tier_discount_auto", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "loyalty_settings",
        sa.Column("birthday_gift_points", sa.Integer(), nullable=False, server_default="0"),
    )

    # ── سطوحِ باشگاه ──────────────────────────────────────
    op.create_table(
        "loyalty_tiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("threshold", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_loyalty_tiers_tenant_id", "loyalty_tiers", ["tenant_id"])

    # ── کاتالوگِ جوایز ────────────────────────────────────
    op.create_table(
        "loyalty_rewards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("points_cost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kind", sa.String(length=10), nullable=False, server_default="gift"),
        sa.Column("value", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_loyalty_rewards_tenant_id", "loyalty_rewards", ["tenant_id"])

    # ── گره‌خوردنِ بازخرید به جایزه ───────────────────────
    op.add_column(
        "crm_loyalty_transactions",
        sa.Column(
            "reward_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("loyalty_rewards.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    conn = op.get_bind()
    _enable_rls(conn, "loyalty_tiers")
    _enable_rls(conn, "loyalty_rewards")


def downgrade() -> None:
    op.drop_column("crm_loyalty_transactions", "reward_id")
    op.drop_table("loyalty_rewards")
    op.drop_table("loyalty_tiers")
    op.drop_column("loyalty_settings", "birthday_gift_points")
    op.drop_column("loyalty_settings", "tier_discount_auto")
    op.drop_column("loyalty_settings", "tier_basis")
    op.drop_column("contacts", "birthday")
