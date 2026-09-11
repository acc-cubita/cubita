"""تسویه‌ی حسابِ طرف مقابل — تخصیصِ اقلامِ باز به هم

Revision ID: 0111
Revises: 0110

## چه چیزی نبود

کوبیتا تا امروز **«پرداخت» و «تسویه» را یکی می‌گرفت** — دقیقاً همان چیزی که §۲
هشدارش را می‌دهد. رسیدِ دریافت می‌گفت پول جابه‌جا شد؛ هیچ‌جا نمی‌گفت بابتِ کدام
فاکتور. پیامدها:

* **فاکتور نمی‌دانست چقدرش پرداخت شده.** نه ستونی، نه رابطه‌ای. تنها جایی که عددی
  شبیهِ آن ساخته می‌شد گزارشِ سنیِ مطالبات بود، و آن‌جا هم *در لحظه‌ی گزارش* با
  FIFO حدس زده می‌شد: جمعِ دریافت‌های شخص روی قدیمی‌ترین فاکتورهایش ریخته می‌شد.
  حدسی که هیچ‌وقت ذخیره نمی‌شد، دیده نمی‌شد و کاربر نمی‌توانست تصحیحش کند.
* **رابطه یک‌به‌یک هم نبود، هیچ بود.** نه `receipt.invoice_id`، نه جدولِ واسط. پس
  «این ۱۰۰ میلیون بابتِ کدام دو فاکتور بود؟» اصلاً قابلِ ثبت نبود (§۱۶ §۱۷).
* **پیش‌دریافت گم می‌شد.** دریافتی که هنوز فاکتوری ندارد (§۲۹) فقط مانده‌ی منفیِ
  یک شخص بود؛ «چقدرش هنوز تخصیص نیافته» جوابی نداشت.
* صفحه‌ی «تسویه حساب طرف مقابل» که از قبل در منو بود، در واقع **تسویه نبود**: یک
  دکمه بود که برای کلِ ماندهٔ شخص یک رسیدِ دریافت می‌ساخت. یعنی پولِ تازه ثبت
  می‌کرد، نه رابطه — همان اشتباهی که این فصل درباره‌اش نوشته شده.

## چه چیزی اینجا ساخته می‌شود

* `settlements` — سربرگ: شماره، تاریخ، طرف حساب، **معینِ طرف مقابل**، ارز، شرح.
* `settlement_allocations` — قلم‌ها: سمت، سندِ منبع، مبلغِ مصرف‌شده.
* شمارنده‌ی `settlement` برای مستأجرهای موجود.

## چرا هیچ داده‌ای نوشته نمی‌شود

برخلافِ ۰۱۰۹ و ۰۱۱۰، این مهاجرت **فقط اسکیماست** و این عمدی است:

۱. **تسویه سندِ حسابداری نمی‌زند (§۲۲ §۲۳)،** پس هیچ ردیفی در دفتر نیست که
   طبقه‌بندیِ دوباره بخواهد. ماندهٔ همه‌ی حساب‌ها پیش و پس از این مهاجرت یکی است.

۲. **تخصیصِ گذشته backfill نمی‌شود.** وسوسه‌اش هست: همان FIFOیی که گزارشِ سنی
   می‌زند را یک‌بار اجرا کنیم و تخصیص‌های واقعی بسازیم. ولی آن حدس است، نه
   حقیقت — کسی نگفته دریافتِ فروردین بابتِ فاکتورِ فروردین بوده. ثبت‌کردنِ حدس
   به‌عنوانِ سابقه، همان جعلِ تاریخچه است که در ۰۱۱۰ هم ردش کردیم. تخصیصِ خودکار
   اگر روزی بیاید باید **گزینه‌ی صریحِ کاربر** باشد، نه رفتارِ پنهانِ سیستم (§۴۷).

نتیجه: هر سندِ موجود از فردا «تسویه‌نشده» است و مانده‌ی قابلِ تسویه‌اش برابرِ
مبلغِ خودش. این حقیقت است: واقعاً هیچ‌کس تا امروز نگفته بود چه با چه تسویه شده.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0111"
down_revision: Union[str, None] = "0110"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

HEADER = "settlements"
LINES = "settlement_allocations"

SIDES = "('debit', 'credit')"


def upgrade() -> None:
    conn = op.get_bind()

    op.create_table(
        HEADER,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column("number", sa.BigInteger(), nullable=False),
        sa.Column("settlement_date", sa.Date(), nullable=False),
        sa.Column(
            "contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False, index=True
        ),
        #: معینِ طرف مقابل (§۵) — دریافتنی یا پرداختنی. بدونِ این، تهاترِ بینِ دو
        #: معین بی‌سروصدا اتفاق می‌افتاد (§۳۱).
        sa.Column(
            "account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False, index=True
        ),
        sa.Column("currency_code", sa.String(3), server_default="IRR", nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("description2", sa.Text(), server_default="", nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "voided_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.UniqueConstraint("tenant_id", "number", name="uq_settlements_tenant_number"),
    )
    op.create_index("ix_settlements_tenant_contact", HEADER, ["tenant_id", "contact_id"])

    op.create_table(
        LINES,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column(
            "settlement_id",
            UUID(as_uuid=True),
            sa.ForeignKey(f"{HEADER}.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("seq", sa.Integer(), server_default="0", nullable=False),
        sa.Column("side", sa.String(6), nullable=False),
        #: نوعِ منبع رشته است نه کلیدِ خارجی — منبع‌ها در جدول‌های مختلفی زندگی
        #: می‌کنند. همان الگویی که `journal_entries.source_type` دارد.
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.CheckConstraint(f"side IN {SIDES}", name="ck_settlement_allocations_side"),
        sa.CheckConstraint("amount > 0", name="ck_settlement_allocations_amount_positive"),
        sa.UniqueConstraint(
            "tenant_id",
            "settlement_id",
            "source_type",
            "source_id",
            name="uq_settlement_allocations_source",
        ),
    )
    op.create_index("ix_settlement_allocations_source", LINES, ["tenant_id", "source_type", "source_id"])

    #: **RLS بعد از ساختِ هر دو جدول.** درسِ مهاجرتِ ۰۱۰۹: افزودنِ کلیدِ خارجی به
    #: جدولی که از قبل FORCE RLS دارد، اسکنِ اعتبارسنجیِ Postgres را راه می‌اندازد
    #: و آن اسکن `app.tenant_id` را می‌خواند — که وسطِ مهاجرت وجود ندارد.
    for table in (HEADER, LINES):
        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
        conn.execute(
            sa.text(
                f"CREATE POLICY {policy_name(table)} ON {table} "
                "USING (tenant_id = current_setting('app.tenant_id')::uuid) "
                "WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)"
            )
        )

    with rls_disabled(conn, ["document_counters"]):
        #: بدونِ این ردیف، اولین تسویه‌ی هر مستأجرِ موجود ۵۰۰ می‌دهد —
        #: `next_document_number` عمداً بلند شکست می‌خورد تا شماره‌ی تکراری نسازد.
        conn.execute(
            sa.text(
                """
                INSERT INTO document_counters (id, tenant_id, doc_type, last_number,
                                               created_at, updated_at)
                SELECT gen_random_uuid(), t.id, 'settlement', 0, now(), now()
                  FROM tenants t
                 WHERE NOT EXISTS (
                       SELECT 1 FROM document_counters d
                        WHERE d.tenant_id = t.id AND d.doc_type = 'settlement')
                """
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    op.drop_table(LINES)
    op.drop_table(HEADER)
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("DELETE FROM document_counters WHERE doc_type = 'settlement'"))
