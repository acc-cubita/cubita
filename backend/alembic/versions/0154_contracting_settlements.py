"""پیمانکاری — تسویه‌حسابِ پیمان (فازِ ۴، آخرین فاز).

* `contracting_settlements`: تنها سندِ این ماژول که سندِ حسابداریِ واقعی می‌زند.
  Snapshotِ جمعِ صورت‌وضعیت‌های پیمان + `journal_entry_id` + سه ستونِ ابطال
  (`VoidableMixin`، مثلِ `credit_debit_notes`). جدولِ تازه، بی ردیف در لحظه‌ی ساخت.
* شمارنده‌ی `contract_settlement` برای همه‌ی مستأجرها، زیرِ `rls_disabled` (الگوی
  `0151`–`0153`).

هیچ `UPDATE`ی روی داده‌ی موجود ندارد. حساب‌های نقش‌دارِ تازه‌اش (درآمدِ پیمانکاری،
سپرده‌ی حسن انجامِ کار، پیش‌دریافتِ پیمان، سایرِ کسورات) اینجا ساخته نمی‌شوند —
`get_or_create_account` در لحظه‌ی اولین تسویه‌حساب تنبل می‌سازدشان (الگوی
`WORK_IN_PROCESS`/`CONTRACT_INSURANCE_PAYABLE`)، پس چارتِ کسب‌وکارهای موجود
دست‌نخورده می‌ماند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0154"
down_revision: Union[str, None] = "0153"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
        "contracting_settlements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("number", sa.Integer(), nullable=False, index=True),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("contracting_contracts.id"), nullable=False, index=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("gross_amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("retention_amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("advance_amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("other_deductions", sa.Numeric(18, 0), nullable=False),
        sa.Column("net_amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("contract_value_at_settlement", sa.Numeric(18, 0), nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("journal_entry_id", UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True, index=True),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("void_reason", sa.Text(), server_default="", nullable=False),
        sa.Column("voided_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    _enable_rls("contracting_settlements")

    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("""
            INSERT INTO document_counters
                (id, tenant_id, doc_type, last_number, created_at, updated_at)
            SELECT gen_random_uuid(), t.id, 'contract_settlement', 0, now(), now()
            FROM tenants t
            WHERE NOT EXISTS (
                SELECT 1 FROM document_counters dc
                WHERE dc.tenant_id = t.id AND dc.doc_type = 'contract_settlement'
            )
        """))


def downgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("DELETE FROM document_counters WHERE doc_type = 'contract_settlement'"))
    op.drop_table("contracting_settlements")
