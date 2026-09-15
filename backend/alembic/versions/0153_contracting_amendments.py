"""پیمانکاری — متممِ پیمان (فازِ ۲).

* `contracting_amendments`: تغییرِ الحاقیِ مبلغ (`amount_delta`، می‌تواند منفی
  باشد) و/یا تاریخِ پایانِ یک پیمان. جدولِ تازه، بی ردیف در لحظه‌ی ساخت.
* شمارنده‌ی `contract_amendment` برای همه‌ی مستأجرها، زیرِ `rls_disabled`
  (الگوی `0152`).

هیچ `UPDATE`ی روی داده‌ی موجود ندارد.

**شماره‌گذاریِ مجدد:** این مهاجرت اول `0152` بود، پشتِ `0151`. چون پیمانِ فازِ ۱
به `0152` جابه‌جا شد (رفعِ دوسرِ مهاجرتِ master با #76 — نگاه کنید به
`fix/contracting-migration-renumber`)، این هم پشتِ سر به `0153` آمد.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0153"
down_revision: Union[str, None] = "0152"
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
        "contracting_amendments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("number", sa.Integer(), nullable=False, index=True),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("contracting_contracts.id"), nullable=False, index=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("amount_delta", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("new_end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    _enable_rls("contracting_amendments")

    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("""
            INSERT INTO document_counters
                (id, tenant_id, doc_type, last_number, created_at, updated_at)
            SELECT gen_random_uuid(), t.id, 'contract_amendment', 0, now(), now()
            FROM tenants t
            WHERE NOT EXISTS (
                SELECT 1 FROM document_counters dc
                WHERE dc.tenant_id = t.id AND dc.doc_type = 'contract_amendment'
            )
        """))


def downgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("DELETE FROM document_counters WHERE doc_type = 'contract_amendment'"))
    op.drop_table("contracting_amendments")
