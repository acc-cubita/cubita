"""ماژول انبارگردانی (شمارش فیزیکی موجودی)

Revision ID: 0032
Revises: 0031

دو جدولِ تازه (هر دو با RLS، همان الگوی 0026/0027/0028):

- `stock_count_sessions`: سرِ یک جلسه‌ی انبارگردانی برای یک انبار، با وضعیت
  (باز/ثبت‌شده/لغوشده) و — پس از ثبت — ارجاع به سندِ حسابداریِ تجمیعی.
- `stock_count_lines`: یک ردیف به‌ازای هر کالای غیرخدماتی، با موجودیِ سیستمیِ
  عکس‌برداری‌شده در لحظه‌ی ایجاد، بهای واحدِ عکس‌برداری‌شده (میانگین موزون)، و
  شمارشِ فیزیکیِ واردشده. مغایرت و ارزشِ ریالیِ آن هنگام نمایش/ثبت محاسبه می‌شوند.

هیچ داده‌ی موجودی را نمی‌شکند — فقط جدول‌های تازه اضافه می‌کند. تعدیلِ واقعیِ موجودی
هنگام «ثبت» از طریق `stock_ledger` (با `source_type='stock_count'`) و یک سندِ
دوطرفه‌ی موجودی↔مغایرت انبار انجام می‌شود، دقیقاً مثل تعدیلِ تک‌کالاییِ موجود.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0032"
down_revision: Union[str, None] = "0031"
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
    op.create_table(
        "stock_count_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("count_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_stock_count_sessions_tenant_id", "stock_count_sessions", ["tenant_id"])

    op.create_table(
        "stock_count_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stock_count_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("system_qty", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("counted_qty", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )
    op.create_index("ix_stock_count_lines_tenant_id", "stock_count_lines", ["tenant_id"])
    op.create_index("ix_stock_count_lines_session_id", "stock_count_lines", ["session_id"])

    conn = op.get_bind()
    _enable_rls(conn, "stock_count_sessions")
    _enable_rls(conn, "stock_count_lines")


def downgrade() -> None:
    op.drop_table("stock_count_lines")
    op.drop_table("stock_count_sessions")
