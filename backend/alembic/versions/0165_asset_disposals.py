"""دارایی ثابت — خروج (فروش/اسقاط/اهدا) با سندِ واقعی.

تا امروز «واگذاری» فقط `is_disposed` را روشن می‌کرد. یعنی دارایی از چرخه‌ی استهلاک
بیرون می‌آمد ولی **بهای تمام‌شده‌اش و استهلاکِ انباشته‌اش تا ابد در ترازنامه
می‌ماندند** — ترازنامه دارایی‌ای را نشان می‌داد که دیگر وجود نداشت. این یک باگِ
حسابداری بود، نه فقط قابلیتِ نداشته.

* جدولِ تازه‌ی `asset_disposals`: نوعِ خروج، مبلغِ دریافتی، عکسِ بها/استهلاک/ارزشِ
  دفتری در همان لحظه، سود یا زیان، و سندی که خورده.
* قیدِ یکتای (مستأجر، دارایی): یک دارایی دو بار خارج نمی‌شود.

هیچ ستونی به `fixed_assets` اضافه نمی‌شود، پس `rls_disabled` لازم نیست — فقط
ساختِ جدولِ تازه.

**شماره:** روی `0163` سوار است نه `0164`؛ `0164` مالِ شاخه‌ی بازِ همکار
(`feat/contact-role-flags`) است و هنوز در master نیست. اگر آن زودتر merge شود،
همین‌جا `down_revision` به `"0164"` تغییر می‌کند تا زنجیره یک سر بماند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.tenancy import policy_name

revision: str = "0165"
down_revision: Union[str, None] = "0163"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DISPOSAL_TYPES = ("sale", "scrap", "donation")
_TYPES_IN_SQL = ", ".join(f"'{t}'" for t in DISPOSAL_TYPES)


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
        "asset_disposals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("fixed_assets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("disposal_type", sa.String(20), server_default="sale", nullable=False),
        sa.Column("disposal_date", sa.Date(), nullable=False, index=True),
        sa.Column("proceeds", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("settlement_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("buyer_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True, index=True),
        sa.Column("cost_at_disposal", sa.Numeric(18, 0), nullable=False),
        sa.Column("accumulated_at_disposal", sa.Numeric(18, 0), nullable=False),
        sa.Column("book_value", sa.Numeric(18, 0), nullable=False),
        sa.Column("gain_loss", sa.Numeric(18, 0), nullable=False),
        sa.Column("journal_entry_id", UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True, index=True),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(f"disposal_type IN ({_TYPES_IN_SQL})", name="ck_asset_disposals_type"),
        sa.CheckConstraint("proceeds >= 0", name="ck_asset_disposals_proceeds_nonneg"),
        sa.UniqueConstraint("tenant_id", "asset_id", name="uq_asset_disposal_once"),
    )
    _enable_rls("asset_disposals")


def downgrade() -> None:
    op.drop_table("asset_disposals")
