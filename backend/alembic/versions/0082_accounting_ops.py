"""حسابداری: وضعیتِ موقت/دائم، بُعدِ ارز روی ردیف، و تفصیلیِ سایر

Revision ID: 0082
Revises: 0081

سه شکافِ ساختاری که هجده عملیاتِ تازه‌ی ماژولِ حسابداری بدونشان روی هوا می‌ماندند:

* **موقت/دائم** — «کارتابلِ صدور سند» و «تبدیل اسناد موقت به دائم» هر دو به یک
  وضعیت روی سند نیاز دارند. سندِ تازه *موقت* ساخته می‌شود (رویه‌ی استانداردِ
  دفترداری: ثبت، بازبینی، دائم‌کردن) ولی ردیف‌های *موجود* باید دائم بمانند —
  تاریخ‌اند و کسی قرار نیست بازبینی‌شان کند. پس ستون با پیش‌فرضِ `permanent`
  اضافه می‌شود (همین ردیف‌های امروز را دائم می‌کند) و بعد پیش‌فرضِ سمتِ پایگاه‌داده
  به `temporary` برمی‌گردد تا سندِ فردا موقت متولد شود.

* **ارز روی ردیف** — «صدور سند تسعیر ارز» بدونِ نگه‌داشتنِ مبلغِ ارزی معنا ندارد:
  اگر فقط ریال ذخیره شود، هیچ‌وقت نمی‌شود فهمید مانده‌ی ۲٬۰۰۰٬۰۰۰ ریالیِ یک حساب،
  ۱۰۰ دلار بوده یا ۲۰۰ دلار. سه ستونِ اختیاری روی ردیف (کدِ ارز، مبلغِ ارزی، نرخِ
  ثبت) این را حل می‌کند؛ `NULL` یعنی ردیفِ ریالی — یعنی همه‌ی ردیف‌های امروز.

* **تفصیلیِ سایر** — بُعدِ تحلیلیِ آزاد برای چیزهایی که نه طرف‌حساب‌اند نه مرکزِ
  هزینه (خودرو، قرارداد، شعبه‌ی موقت، …). جدولِ کوچکِ مستأجرمحور + یک FKِ اختیاری
  روی ردیفِ سند. `SET NULL` است نه `CASCADE`: حذفِ یک تفصیلی نباید ردیفِ سند را
  ببرد — دفتر باید سرِ جایش بماند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0082"
down_revision: Union[str, None] = "0081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUSES = "('temporary', 'permanent')"


def upgrade() -> None:
    # ── وضعیتِ سند ───────────────────────────────────────────────────────────
    # پیش‌فرضِ `permanent` عمدی است: این ALTER به همه‌ی ردیف‌های موجود همین مقدار را
    # می‌دهد. بلافاصله بعدش پیش‌فرض به `temporary` عوض می‌شود تا فقط سندِ *تازه* موقت
    # باشد. جای این دو خط اگر عوض شود، کلِ تاریخچه‌ی کسب‌وکار یک‌شبه «موقت» می‌شود.
    op.add_column(
        "journal_entries",
        sa.Column("status", sa.String(12), nullable=False, server_default="permanent"),
    )
    op.alter_column("journal_entries", "status", server_default="temporary")
    op.create_check_constraint("ck_journal_entries_status", "journal_entries", f"status IN {STATUSES}")
    op.add_column(
        "journal_entries", sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "journal_entries",
        sa.Column(
            "finalized_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
    )
    # کارتابل همیشه «موقت‌های این مستأجر، به‌ترتیبِ تاریخ» را می‌خواهد.
    op.create_index(
        "ix_journal_entries_tenant_status", "journal_entries", ["tenant_id", "status", "entry_date"]
    )

    # ── تفصیلیِ سایر ─────────────────────────────────────────────────────────
    op.create_table(
        "analytic_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        #: دسته‌ی آزاد («خودرو»، «قرارداد»، …) — فقط برای گروه‌بندی در فهرست.
        sa.Column("group_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "code", name="uq_analytic_accounts_tenant_code"),
    )
    op.create_index("ix_analytic_accounts_tenant", "analytic_accounts", ["tenant_id", "code"])

    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE analytic_accounts ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE analytic_accounts FORCE ROW LEVEL SECURITY"))
    conn.execute(
        sa.text(f"DROP POLICY IF EXISTS {policy_name('analytic_accounts')} ON analytic_accounts")
    )
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name('analytic_accounts')} ON analytic_accounts "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
    )

    # ── ابعادِ تازه‌ی ردیفِ سند ────────────────────────────────────────────────
    op.add_column("journal_lines", sa.Column("currency_code", sa.String(3), nullable=True))
    op.add_column("journal_lines", sa.Column("fx_amount", sa.Numeric(18, 4), nullable=True))
    op.add_column("journal_lines", sa.Column("fx_rate", sa.Numeric(18, 4), nullable=True))
    op.add_column(
        "journal_lines",
        sa.Column(
            "analytic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analytic_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_journal_lines_analytic", "journal_lines", ["tenant_id", "analytic_id"])
    # تسعیر همیشه «ردیف‌های ارزیِ یک حساب» را می‌خواهد؛ بدونِ این ایندکس هر بار کلِ
    # دفتر اسکن می‌شد.
    op.create_index(
        "ix_journal_lines_currency",
        "journal_lines",
        ["tenant_id", "currency_code"],
        postgresql_where=sa.text("currency_code IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_journal_lines_currency", table_name="journal_lines")
    op.drop_index("ix_journal_lines_analytic", table_name="journal_lines")
    op.drop_column("journal_lines", "analytic_id")
    op.drop_column("journal_lines", "fx_rate")
    op.drop_column("journal_lines", "fx_amount")
    op.drop_column("journal_lines", "currency_code")

    op.drop_index("ix_analytic_accounts_tenant", table_name="analytic_accounts")
    op.drop_table("analytic_accounts")

    op.drop_index("ix_journal_entries_tenant_status", table_name="journal_entries")
    op.drop_column("journal_entries", "finalized_by_id")
    op.drop_column("journal_entries", "finalized_at")
    op.drop_constraint("ck_journal_entries_status", "journal_entries", type_="check")
    op.drop_column("journal_entries", "status")
