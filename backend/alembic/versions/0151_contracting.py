"""پیمانکاری — پیمان (فازِ ۱).

* `contracting_contracts`: کارفرما، موضوع، مبلغ، بازه و وضعیت. جدولِ تازه، بی ردیف
  در لحظه‌ی ساخت — نیازی به `rls_disabled` برای خودِ کلیدهای خارجی‌اش نیست.
* شمارنده‌ی `contract` برای همه‌ی مستأجرها، زیرِ `rls_disabled` (الگوی `0149`).

هیچ `UPDATE`ی روی داده‌ی موجود ندارد.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0151"
down_revision: Union[str, None] = "0149"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONTRACT_STATUSES = ("draft", "active", "suspended", "terminated", "completed", "cancelled")


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
    op.create_table(
        "contracting_contracts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("number", sa.Integer(), nullable=False, index=True),
        sa.Column("external_reference", sa.String(80), server_default="", nullable=False),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False, index=True),
        sa.Column("subject", sa.String(300), server_default="", nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("retention_percent", sa.Numeric(5, 2), server_default="0", nullable=False),
        sa.Column("advance_percent", sa.Numeric(5, 2), server_default="0", nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("cost_center_id", UUID(as_uuid=True), sa.ForeignKey("cost_centers.id"), nullable=True),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(f"status IN {CONTRACT_STATUSES}", name="ck_contracting_contracts_status"),
    )
    _enable_rls("contracting_contracts")

    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("""
            INSERT INTO document_counters
                (id, tenant_id, doc_type, last_number, created_at, updated_at)
            SELECT gen_random_uuid(), t.id, 'contract', 0, now(), now()
            FROM tenants t
            WHERE NOT EXISTS (
                SELECT 1 FROM document_counters dc
                WHERE dc.tenant_id = t.id AND dc.doc_type = 'contract'
            )
        """))


def downgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("DELETE FROM document_counters WHERE doc_type = 'contract'"))
    op.drop_table("contracting_contracts")
