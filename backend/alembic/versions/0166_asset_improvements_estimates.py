"""دارایی ثابت — تعمیراتِ اساسی، تغییرِ برآورد، و روشِ دومِ استهلاک.

فازِ ۳ ماژول. سه چیز:

* `asset_improvements` — مخارجِ **سرمایه‌ای** پس از تحصیل. مرزش با «هزینه‌ی تعمیرات»
  همان مرزِ استاندارد است: تعمیرِ نگه‌دارنده هزینه‌ی دوره است و اینجا نمی‌آید؛ مخارجی
  که ظرفیت/کیفیت/عمر را بالا می‌برد به بهای تمام‌شده اضافه می‌شود. ثبتِ نوعِ دوم
  به‌عنوانِ هزینه، سودِ امسال را الکی کم می‌کند و ترازنامه را کم‌ارزش نشان می‌دهد.
* `asset_estimate_changes` — ردِ حسابرسیِ تغییرِ روش/عمرِ مفید/ارزشِ اسقاط. **بی‌سند**،
  چون تغییر در برآوردِ حسابداری آینده‌نگر اعمال می‌شود نه با اصلاحِ گذشته.
* `ck_fixed_assets_method` باز می‌شود تا `declining_balance` (ماندهٔ نزولی) را هم
  بپذیرد — بدونِ روشِ دوم، «تغییرِ روش» صفحه‌ای بود با یک گزینه.

هیچ ستونی به `fixed_assets` اضافه نمی‌شود، پس `rls_disabled` لازم نیست؛ فقط قیدِ
`method` عوض می‌شود که داده را دست نمی‌زند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0166"
down_revision: Union[str, None] = "0165"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_METHODS = ("straight_line", "declining_balance")
_OLD_METHODS = ("straight_line",)


def _methods_sql(methods: tuple[str, ...]) -> str:
    return ", ".join(f"'{m}'" for m in methods)


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
    op.drop_constraint("ck_fixed_assets_method", "fixed_assets", type_="check")
    op.create_check_constraint(
        "ck_fixed_assets_method", "fixed_assets", f"method IN ({_methods_sql(_NEW_METHODS)})"
    )

    op.create_table(
        "asset_improvements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("fixed_assets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("improvement_date", sa.Date(), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("funding_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("extra_life_months", sa.Integer(), server_default="0", nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("journal_entry_id", UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True, index=True),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_asset_improvements_amount_positive"),
        sa.CheckConstraint("extra_life_months >= 0", name="ck_asset_improvements_extra_life_nonneg"),
    )
    _enable_rls("asset_improvements")

    op.create_table(
        "asset_estimate_changes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("fixed_assets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("change_date", sa.Date(), nullable=False, index=True),
        sa.Column("from_method", sa.String(20), nullable=False),
        sa.Column("to_method", sa.String(20), nullable=False),
        sa.Column("from_useful_life_months", sa.Integer(), nullable=False),
        sa.Column("to_useful_life_months", sa.Integer(), nullable=False),
        sa.Column("from_salvage_value", sa.Numeric(18, 0), nullable=False),
        sa.Column("to_salvage_value", sa.Numeric(18, 0), nullable=False),
        sa.Column("reason", sa.Text(), server_default="", nullable=False),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            f"to_method IN ({_methods_sql(_NEW_METHODS)})", name="ck_asset_estimate_changes_method"
        ),
        sa.CheckConstraint("to_useful_life_months > 0", name="ck_asset_estimate_changes_life_positive"),
    )
    _enable_rls("asset_estimate_changes")


def downgrade() -> None:
    op.drop_table("asset_estimate_changes")
    op.drop_table("asset_improvements")
    #: برگرداندنِ قید فقط وقتی ممکن است که داراییِ نزولی در کار نباشد؛ اگر باشد،
    #: برش می‌گردانیم به خط مستقیم — تنها روشی که نسخه‌ی قبلی می‌شناسد.
    #: **زیرِ `rls_disabled`،** وگرنه این `UPDATE` بی‌سروصدا صفر ردیف می‌بیند و
    #: ساختنِ قیدِ بعدی روی ردیف‌های `declining_balance` می‌شکند.
    with rls_disabled(op.get_bind(), ["fixed_assets"]):
        op.execute("UPDATE fixed_assets SET method = 'straight_line' WHERE method <> 'straight_line'")
    op.drop_constraint("ck_fixed_assets_method", "fixed_assets", type_="check")
    op.create_check_constraint(
        "ck_fixed_assets_method", "fixed_assets", f"method IN ({_methods_sql(_OLD_METHODS)})"
    )
