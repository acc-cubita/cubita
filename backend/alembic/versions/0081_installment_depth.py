"""فروش اقساطی: قیمت نقدی و سود، جریمه‌ی دیرکرد، ضامن — و تاریخچه‌ی پرداخت

Revision ID: 0081
Revises: 0080

قراردادِ اقساطی تا امروز فقط «مبلغ کل ÷ تعداد» بود. چهار چیز کم داشت:

* **قیمت نقدی و سود.** فروشِ اقساطی در عمل یعنی «نقدی چقدر، اقساطی چقدر»؛ بدونِ این
  دو ستون، سودِ فروشِ اقساطی هیچ‌جا ثبت نمی‌شود و قرارداد نمی‌گوید مبلغِ کل از کجا
  آمده. `cash_price` برای ردیف‌های موجود برابرِ `total_amount` بک‌فیل می‌شود تا
  رابطه‌ی «نقدی + سود = کل» از همان اولین روز برقرار باشد.
* **جریمه‌ی دیرکرد.** نرخ روی قرارداد می‌نشیند و مبلغش *محاسبه* می‌شود، نه ذخیره —
  مثلِ وضعیتِ قسط، تا بدونِ زمان‌بندِ پس‌زمینه همیشه با تاریخِ امروز درست باشد.
* **ضامن.** امروز در «توضیحات» می‌نشیند و جست‌وجوپذیر نیست.
* **تاریخچه‌ی پرداخت.** تا امروز فقط جمعِ `paid_amount` می‌ماند؛ اینکه هر مبلغ کِی و
  با چه روشی و با کدام سندِ خزانه وصول شده، گم می‌شد. جدولِ `installment_payments`
  همان حلقه‌ی گم‌شده است و پرداختِ چندقسطی با یک فیش را هم ممکن می‌کند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0081"
down_revision: Union[str, None] = "0080"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "installment_plans",
        sa.Column("cash_price", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )
    op.add_column(
        "installment_plans",
        sa.Column("profit_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )
    op.add_column(
        "installment_plans",
        sa.Column("penalty_rate", sa.Numeric(6, 3), nullable=False, server_default="0"),
    )
    op.add_column(
        "installment_plans",
        sa.Column("guarantor_name", sa.String(200), nullable=False, server_default=""),
    )
    op.add_column(
        "installment_plans",
        sa.Column("guarantor_phone", sa.String(30), nullable=False, server_default=""),
    )
    op.add_column(
        "installment_plans",
        sa.Column("guarantor_national_id", sa.String(20), nullable=False, server_default=""),
    )

    conn = op.get_bind()
    # قراردادهای موجود سودی ثبت‌نشده دارند، پس کلِ مبلغشان «قیمت نقدی» است. بدونِ این
    # بک‌فیل، هر قراردادِ قدیمی قیمتِ نقدیِ صفر نشان می‌داد و رابطه‌ی نقدی+سود=کل می‌شکست.
    # `installment_plans` مستأجرمحور و FORCE-RLS است: بدونِ rls_disabled این UPDATE
    # بی‌صدا صفر ردیف می‌بیند.
    with rls_disabled(conn, ["installment_plans"]):
        conn.execute(sa.text("UPDATE installment_plans SET cash_price = total_amount"))

    op.create_table(
        "installment_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("installment_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "installment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("installments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("paid_on", sa.Date, nullable=False),
        sa.Column("method", sa.String(20), nullable=False, server_default="cash"),
        # سندِ خزانه‌ی متناظر. SET NULL نه CASCADE: اگر روزی تراکنشِ خزانه پاک شود،
        # ردِ پرداختِ قسط نباید با آن ناپدید شود.
        sa.Column(
            "treasury_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("treasury_transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_installment_payments_tenant_plan", "installment_payments", ["tenant_id", "plan_id"]
    )

    conn.execute(sa.text("ALTER TABLE installment_payments ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE installment_payments FORCE ROW LEVEL SECURITY"))
    conn.execute(
        sa.text(f"DROP POLICY IF EXISTS {policy_name('installment_payments')} ON installment_payments")
    )
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name('installment_payments')} ON installment_payments "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_installment_payments_tenant_plan", table_name="installment_payments")
    op.drop_table("installment_payments")
    op.drop_column("installment_plans", "guarantor_national_id")
    op.drop_column("installment_plans", "guarantor_phone")
    op.drop_column("installment_plans", "guarantor_name")
    op.drop_column("installment_plans", "penalty_rate")
    op.drop_column("installment_plans", "profit_amount")
    op.drop_column("installment_plans", "cash_price")
