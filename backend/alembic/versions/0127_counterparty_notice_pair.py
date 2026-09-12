"""اعلامیه‌ی بدهکار/بستانکار دو سمت دارد، نه یکی

Revision ID: 0127
Revises: 0126

اعلامیه از فصلِ قبل ساخته شده بود، ولی با یک فرضِ نانوشته: یک طرف حساب، یک مبلغ،
و طرفِ دومِ سند **همیشه حسابِ فروش**. سه چیز از این فرض بیرون می‌آید که هیچ‌کدام
درست نیست:

* تعدیلِ مانده، **درآمد** می‌ساخت. هر اعلامیه‌ی بدهکار فروش را باد می‌کرد و هر
  بستانکار کمش می‌کرد؛ شکلِ صورتِ سود و زیان با سندی عوض می‌شد که هیچ فروشی در
  آن اتفاق نیفتاده.
* سمتِ **تأمین‌کننده** اصلاً وجود نداشت. تهاترِ «بدهیِ ما به فلانی در برابرِ طلبِ
  ما از او» — کارِ اصلیِ این سند — ناممکن بود، و برای طرف‌حسابی که تأمین‌کننده
  است سند روی معینِ *دریافتنی* می‌نشست.
* و چون سمتِ دوم ثابت بود، سند هیچ‌وقت لازم نداشت بگوید «کدام حساب، کدام تفصیلی».

پس این مهاجرت جدولِ ردیف می‌سازد و هر ردیف یک **جفتِ کامل** می‌شود: سمتِ بدهکار
(طرف حساب + معین) و سمتِ بستانکار (طرف حساب + معین) با یک مبلغِ مشترک. ردیف ذاتاً
تراز است و سند جمعِ ردیف‌هایش.

**هیچ backfillی در کار نیست و هیچ ردیفی نوشته نمی‌شود.** روی تولید و در هر شش
مستأجر، `credit_debit_notes` **خالی** است — این قابلیت هرگز استفاده نشده. پس
مهاجرت فقط ساختار را عوض می‌کند و به هیچ داده‌ای دست نمی‌زند؛ همان دلیلی که
اجازه می‌دهد `contact_id` و `kind` بدونِ ترسِ از دست رفتنِ چیزی nullable شوند.

`kind` و `contact_id` **حذف نمی‌شوند**: ستونِ مرده بی‌آزار است، ولی حذفِ ستون از
جدولی که روی تولید نشسته یک‌طرفه است. از این پس هیچ‌کس نمی‌نویسدشان و سمتِ سند از
خودِ ردیف‌ها می‌آید.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.tenancy import policy_name

revision: str = "0127"
down_revision: Union[str, None] = "0126"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "credit_debit_note_lines"


def _enable_rls(table: str) -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name(table)} ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
    )


def upgrade() -> None:
    # ── سربرگ: ارز و نرخ، مثلِ هر سندِ دیگری در کوبیتا ──────────────────────
    op.add_column(
        "credit_debit_notes",
        sa.Column("currency_code", sa.String(3), server_default="IRR", nullable=False),
    )
    op.add_column(
        "credit_debit_notes",
        sa.Column("exchange_rate", sa.Numeric(18, 4), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        "ck_credit_debit_notes_exchange_rate_positive", "credit_debit_notes", "exchange_rate > 0"
    )

    # ── ستون‌های تک‌سمتیِ قدیمی: دیگر نوشته نمی‌شوند ────────────────────────
    #: `amount` می‌ماند و معنایش عوض می‌شود: جمعِ ردیف‌ها. همان الگوی
    #: `settlements.total_amount` — عکسِ لحظه‌ی ثبت، با راستی‌آزمایی در سرویس.
    op.alter_column("credit_debit_notes", "contact_id", existing_type=UUID(as_uuid=True), nullable=True)
    op.alter_column("credit_debit_notes", "kind", existing_type=sa.String(10), nullable=True)
    #: قیدِ `kind IN ('debit','credit')` روی `NULL` صدق نمی‌کند و Postgres قیدِ
    #: NULL را درست می‌گذراند؛ پس دست‌نخورده می‌ماند و ردیف‌های تازه از آن رد
    #: می‌شوند.

    # ── ردیف: یک جفتِ کامل، ذاتاً تراز ────────────────────────────────────────
    op.create_table(
        TABLE,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "note_id",
            UUID(as_uuid=True),
            sa.ForeignKey("credit_debit_notes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        #: طرف حسابِ هر سمت **اختیاری** است: سمتِ مقابلِ یک تعدیل می‌تواند حسابی
        #: باشد که طرف حساب ندارد. ولی حسابش هیچ‌وقت اختیاری نیست.
        sa.Column("debit_contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True, index=True),
        sa.Column("debit_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("credit_contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True, index=True),
        sa.Column("credit_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_credit_debit_note_lines_amount_positive"),
        #: بی‌اثر بودنِ آشکار رد می‌شود: همان حساب و همان تفصیلی در دو سمت،
        #: سندی است که هیچ‌چیز را جابه‌جا نمی‌کند. (فصل، §۲۱)
        sa.CheckConstraint(
            "debit_account_id <> credit_account_id "
            "OR debit_contact_id IS DISTINCT FROM credit_contact_id",
            name="ck_credit_debit_note_lines_not_noop",
        ),
        sa.UniqueConstraint("tenant_id", "note_id", "seq", name="uq_credit_debit_note_lines_seq"),
    )
    _enable_rls(TABLE)


def downgrade() -> None:
    op.drop_table(TABLE)
    op.drop_constraint("ck_credit_debit_notes_exchange_rate_positive", "credit_debit_notes", type_="check")
    op.drop_column("credit_debit_notes", "exchange_rate")
    op.drop_column("credit_debit_notes", "currency_code")
    #: `kind`/`contact_id` به NOT NULL برنمی‌گردند: اگر بعد از این مهاجرت
    #: اعلامیه‌ای ثبت شده باشد، ردیف‌هایش این دو را خالی گذاشته‌اند و برگرداندنِ
    #: قید، `downgrade` را روی داده‌ی واقعی می‌شکند.
