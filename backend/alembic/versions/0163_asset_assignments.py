"""دارایی ثابت — تحویل/استقرار و جابه‌جایی، با تاریخچه.

تا امروز دارایی ثابت فقط «چه چیزی و چند» را می‌دانست: نه معلوم بود **دستِ کیست**،
نه **کجاست**، نه اینکه تا حالا بینِ چه کسانی گشته. یعنی «فهرست جابه‌جایی‌ها و
تحویل‌ها» اصلاً داده‌ای نداشت که نشان بدهد.

* سه ستونِ وضعیتِ امروز روی `fixed_assets`: جمعدار، محلِ استقرار، مرکزِ هزینه.
  **جدولِ دارای ردیفِ واقعی + FKِ درون‌خطی → زیرِ `rls_disabled`** (باگِ مستندِ PG14).
* جدولِ تازه‌ی `asset_assignments`: هر تحویل و هر جابه‌جایی، با مبدأ **و** مقصد.

هیچ اثرِ حسابداری در کار نیست — جابه‌جاییِ دارایی بینِ جمعداران مالکیت را عوض
نمی‌کند، پس سندی هم نمی‌خورد.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0163"
down_revision: Union[str, None] = "0162"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ASSIGNMENT_KINDS = ("placement", "transfer")


def _enable_rls(table: str) -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
    conn.execute(sa.text(
        f"CREATE POLICY {policy_name(table)} ON {table} "
        "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
    ))


def upgrade() -> None:
    conn = op.get_bind()

    with rls_disabled(conn, ["fixed_assets", "contacts", "cost_centers"]):
        op.add_column(
            "fixed_assets",
            sa.Column("custodian_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True),
        )
        op.add_column(
            "fixed_assets",
            sa.Column("location", sa.String(200), server_default="", nullable=False),
        )
        op.add_column(
            "fixed_assets",
            sa.Column("cost_center_id", UUID(as_uuid=True), sa.ForeignKey("cost_centers.id"), nullable=True),
        )
    op.create_index("ix_fixed_assets_custodian_id", "fixed_assets", ["custodian_id"])

    op.create_table(
        "asset_assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("fixed_assets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(20), server_default="placement", nullable=False),
        sa.Column("assignment_date", sa.Date(), nullable=False, index=True),
        sa.Column("to_custodian_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True, index=True),
        sa.Column("to_location", sa.String(200), server_default="", nullable=False),
        sa.Column("to_cost_center_id", UUID(as_uuid=True), sa.ForeignKey("cost_centers.id"), nullable=True),
        sa.Column("from_custodian_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("from_location", sa.String(200), server_default="", nullable=False),
        sa.Column("from_cost_center_id", UUID(as_uuid=True), sa.ForeignKey("cost_centers.id"), nullable=True),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(f"kind IN {ASSIGNMENT_KINDS}", name="ck_asset_assignments_kind"),
    )
    _enable_rls("asset_assignments")


def downgrade() -> None:
    op.drop_table("asset_assignments")
    op.drop_index("ix_fixed_assets_custodian_id", table_name="fixed_assets")
    op.drop_column("fixed_assets", "cost_center_id")
    op.drop_column("fixed_assets", "location")
    op.drop_column("fixed_assets", "custodian_id")
