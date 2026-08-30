"""عملیاتِ دریافت و پرداخت: دسته‌چک، استردادِ چک، تسویه‌ی کارتخوان

Revision ID: 0084
Revises: 0083

سه شکافِ ساختاری که سه عملیاتِ خواسته‌شده بدونشان فقط یک صفحه‌ی تزئینی می‌شدند:

۱) **دسته چک** — تا امروز چک «پرداختنی» با شماره‌ی دستی ثبت می‌شد و هیچ‌جا معلوم
   نبود از کدام دسته آمده، چند برگ مانده، و آیا شماره تکراری است. `checkbooks` همین
   را نگه می‌دارد و `checks.checkbook_id` هر برگ را به دسته‌اش وصل می‌کند.

۲) **استرداد چک** — وضعیتِ `returned`: چکِ دریافتنی که بدونِ وصول به صاحبش پس داده
   می‌شود (مثلاً معامله فسخ شده). با `bounced` فرق دارد: آن‌جا بانک برگشت می‌زند و
   طلب برمی‌گردد؛ اینجا ما خودمان چک را پس می‌دهیم.

۳) **تسویه‌ی کارتخوان** — فروشِ کارتی همان‌روز به حساب نمی‌نشیند؛ PSP چند روز بعد
   یک‌جا واریز می‌کند (منهای کارمزد). `settled_at` و `settlement_txn_id` می‌گویند
   کدام تراکنشِ کارتی در کدام واریزِ بانکی تسویه شده — بدونشان «کارتخوانِ تسویه‌نشده»
   قابلِ محاسبه نیست.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0084"
down_revision: Union[str, None] = "0083"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: وضعیت‌های چک پس از این مهاجرت.
STATUSES = "('in_hand', 'deposited', 'cleared', 'bounced', 'endorsed', 'issued', 'returned')"
OLD_STATUSES = "('in_hand', 'deposited', 'cleared', 'bounced', 'endorsed', 'issued')"


def upgrade() -> None:
    conn = op.get_bind()

    # ── دسته چک ──────────────────────────────────────────────────────────────
    op.create_table(
        "checkbooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "bank_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bank_accounts.id"),
            nullable=False,
        ),
        #: شناسه‌ی دسته روی جلد (سریِ ۱۶ رقمیِ صیاد یا شماره‌ی داخلیِ بانک).
        sa.Column("serial", sa.String(40), nullable=False, server_default=""),
        #: بازه‌ی شماره‌ی برگ‌ها. رشته‌اند نه عدد: بانک‌ها صفرِ ابتدایی می‌گذارند.
        sa.Column("first_number", sa.String(30), nullable=False),
        sa.Column("last_number", sa.String(30), nullable=False),
        sa.Column("leaf_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("issue_date", sa.Date, nullable=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        #: بسته‌شده = دیگر برگِ تازه از آن صادر نمی‌شود (تمام شد یا باطل شد).
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "bank_account_id", "serial", name="uq_checkbooks_tenant_serial"),
    )
    op.create_index("ix_checkbooks_tenant", "checkbooks", ["tenant_id", "bank_account_id"])

    conn.execute(sa.text("ALTER TABLE checkbooks ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE checkbooks FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name('checkbooks')} ON checkbooks"))
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name('checkbooks')} ON checkbooks "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
    )

    op.add_column(
        "checks",
        sa.Column(
            "checkbook_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("checkbooks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # ── استردادِ چک ───────────────────────────────────────────────────────────
    op.drop_constraint("ck_checks_status", "checks", type_="check")
    op.create_check_constraint("ck_checks_status", "checks", f"status IN {STATUSES}")

    # ── تسویه‌ی کارتخوان ─────────────────────────────────────────────────────
    op.add_column(
        "treasury_transactions", sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "treasury_transactions",
        sa.Column(
            "settlement_txn_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bank_transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    # «کارتی‌های تسویه‌نشده» پرسشِ همیشگیِ صفحه‌ی تسویه است.
    op.create_index(
        "ix_treasury_unsettled",
        "treasury_transactions",
        ["tenant_id", "paid_via", "settled_at"],
    )

    # ── نقشِ «کارمزد بانکی» روی حسابِ موجود ──────────────────────────────────
    # کد ۵۱۱۱ («کارمزد و هزینه‌های بانکی») از قبل در قالب‌های صنفی هست. اگر
    # مشتری آن را دارد، همان را نقش‌دار می‌کنیم؛ وگرنه سرویس هنگامِ اولین کارمزد
    # خودش می‌سازدش. بدونِ این، کسب‌وکارِ قالب‌زده یک حسابِ دومِ هم‌معنی می‌گرفت.
    with rls_disabled(conn, ["accounts"]):
        conn.execute(
            sa.text(
                "UPDATE accounts SET system_role = 'bank_fee' "
                "WHERE code = '5111' AND is_group = false AND system_role IS NULL"
            )
        )


def downgrade() -> None:
    op.drop_index("ix_treasury_unsettled", table_name="treasury_transactions")
    op.drop_column("treasury_transactions", "settlement_txn_id")
    op.drop_column("treasury_transactions", "settled_at")

    # چکِ مسترد پیش از برگرداندنِ قید باید وضعیتِ معتبر بگیرد، وگرنه قید نمی‌نشیند.
    op.get_bind().execute(sa.text("UPDATE checks SET status = 'in_hand' WHERE status = 'returned'"))
    op.drop_constraint("ck_checks_status", "checks", type_="check")
    op.create_check_constraint("ck_checks_status", "checks", f"status IN {OLD_STATUSES}")

    op.drop_column("checks", "checkbook_id")
    op.drop_index("ix_checkbooks_tenant", table_name="checkbooks")
    op.drop_table("checkbooks")
