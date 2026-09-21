"""ماژولِ حسابرسی — قرارداد، اجرا و یافته

Revision ID: 0177
Revises: 0176

## سه جدول، دو ماهیت

* `assurance_engagements` — **سراسری، بدونِ RLS.** قرارداد پیمانی بینِ پلتفرم و
  مستأجر است (ساختاراً همان `subscriptions`) و کارتابلِ ستاد باید درخواست‌های
  همه‌ی کسب‌وکارها را کنارِ هم ببیند. نامش در `GLOBAL_TABLES`ِ `app/tenancy.py`
  ثبت شده، وگرنه تستِ درون‌نگریِ RLS این مهاجرت را رد می‌کرد. بهایش این است که
  جداسازی به کدِ روتر می‌رود — یک تابعِ دسترسیِ واحد و یک تستِ نشتیِ الزامی.
* `assurance_runs` و `assurance_findings` — **مستأجری، با RLS.** این‌ها دفترِ
  خودِ مشتری‌اند.

## چرا قرارداد ستونِ `expires_at` را روی عضویت لازم دارد

دسترسیِ حسابرس مهلت‌دار است و تنها نقطه‌ی دورزدن‌ناپذیرِ سنجشش `get_principal`
است، که ردیفِ عضویت را از قبل بارگذاری کرده. پس ستون روی `memberships` می‌نشیند
(عمومی، `NULL` = بی‌انقضا) و سنجشش هیچ کوئریِ اضافه‌ای به هیچ کاربری تحمیل نمی‌کند.

## چرا یکتاییِ «قراردادِ باز» ایندکسِ *جزئی* است

هر کسب‌وکار در هر لحظه یک پرونده‌ی باز دارد، ولی سالِ بعد پرونده‌ی خودش را با
دوره و تیم و اظهارنظرِ خودش می‌گیرد. یکتاییِ کامل روی `tenant_id` آن را ناممکن
می‌کرد و فازهای بعدی مجبور به شکستنِ جدول می‌شدند.

## چرا `last_run_id` کلیدِ خارجی ندارد

کلیدِ خارجی از والدِ **سراسری** به فرزندِ **RLS‌دار** یعنی اسکنِ راستی‌آزماییِ
پستگرس زیرِ سیاستی اجرا می‌شود که `current_setting('app.tenant_id')` می‌خواند —
همان خرابیِ مستندشده در `app/migration_utils.py`. جهتِ برعکس امن است، پس
`assurance_runs.engagement_id` کلیدِ خارجیِ واقعی دارد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0177"
down_revision: Union[str, None] = "0176"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENGAGEMENT_STATUSES = ("requested", "approved", "active", "rejected", "closed")
OPEN_STATUSES = ("requested", "approved", "active")
RUN_TRIGGERS = ("approval", "manual", "staff")
RUN_GRADES = ("healthy", "warning", "critical")


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
    op.add_column(
        "memberships",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "assurance_engagements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(20), server_default="requested", nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=True),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("contact_phone", sa.String(30), server_default="", nullable=False),
        sa.Column("request_note", sa.Text(), server_default="", nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reject_reason", sa.Text(), server_default="", nullable=False),
        sa.Column("auditor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "auditor_membership_id",
            UUID(as_uuid=True),
            sa.ForeignKey("memberships.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("last_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_note", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            f"status IN {ENGAGEMENT_STATUSES}", name="ck_assurance_engagements_status"
        ),
    )
    op.create_index(
        "ix_assurance_engagements_status_requested",
        "assurance_engagements",
        ["status", "requested_at"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_assurance_open_per_tenant "
        "ON assurance_engagements (tenant_id) "
        f"WHERE status IN {OPEN_STATUSES}"
    )

    op.create_table(
        "assurance_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "engagement_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assurance_engagements.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("ran_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("score", sa.Numeric(5, 2), server_default="0", nullable=False),
        sa.Column("grade", sa.String(20), server_default="healthy", nullable=False),
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warning_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("finding_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_debit", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("total_credit", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("summary", JSONB(), server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "number", name="uq_assurance_runs_tenant_number"),
        sa.CheckConstraint(f"trigger IN {RUN_TRIGGERS}", name="ck_assurance_runs_trigger"),
        sa.CheckConstraint(f"grade IN {RUN_GRADES}", name="ck_assurance_runs_grade"),
    )
    _enable_rls("assurance_runs")

    op.create_table(
        "assurance_findings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assurance_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("check_key", sa.String(60), nullable=False, index=True),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("seq", sa.Integer(), server_default="0", nullable=False),
        sa.Column("label", sa.String(300), server_default="", nullable=False),
        sa.Column("detail", sa.Text(), server_default="", nullable=False),
        sa.Column("debit", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("credit", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("difference", sa.Numeric(18, 0), server_default="0", nullable=False),
        # لنگرهای drill-down — عمداً بدونِ کلیدِ خارجی: این عکسِ گذشته است و
        # ابطال یا حذفِ بعدیِ سند نباید درجش را بشکند یا ردیف را ناپدید کند.
        sa.Column("entry_id", UUID(as_uuid=True), nullable=True),
        sa.Column("account_id", UUID(as_uuid=True), nullable=True),
        sa.Column("item_id", UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "severity IN ('error', 'warning')", name="ck_assurance_findings_severity"
        ),
    )
    op.create_index(
        "ix_assurance_findings_run_check", "assurance_findings", ["run_id", "check_key"]
    )
    _enable_rls("assurance_findings")

    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("""
            INSERT INTO document_counters
                (id, tenant_id, doc_type, last_number, created_at, updated_at)
            SELECT gen_random_uuid(), t.id, 'assurance_run', 0, now(), now()
            FROM tenants t
            WHERE NOT EXISTS (
                SELECT 1 FROM document_counters dc
                WHERE dc.tenant_id = t.id AND dc.doc_type = 'assurance_run'
            )
        """))


def downgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("DELETE FROM document_counters WHERE doc_type = 'assurance_run'"))
    op.drop_table("assurance_findings")
    op.drop_table("assurance_runs")
    op.execute("DROP INDEX IF EXISTS uq_assurance_open_per_tenant")
    op.drop_table("assurance_engagements")
    op.drop_column("memberships", "expires_at")
