"""رسید دریافت: سربرگی که نبود، پس یک رسید فقط یک ابزار داشت.

`treasury_transactions` هرچه دارد در سطحِ **ابزار** است — `cashbox_id`،
`bank_account_id`، `pos_terminal_id`، `reference_no`، `settled_at` — و هرچه ندارد
در سطحِ **سند**: شماره، نوعِ دریافت، ارز، طرفِ مقابل به‌عنوانِ صاحبِ سند. یعنی آن
جدول از اول «یک جزء» بوده. و چون سربرگی نبود که چند جزء را نگه دارد،
`CheckConstraint` روی `method` عملاً می‌گفت: یک رسید، یک ابزار.

این مهاجرت سربرگ را **بالای** اجزا می‌گذارد، نه ردیف را زیرشان:

    receipts <- treasury_transactions.receipt_id   (نقد · حواله · کارت‌خوان)
             <- checks.receipt_id                  (چک)

**چرا نه یک جدولِ ردیف زیرِ خزانه؟** آن هفت ستونِ سطحِ‌ابزار در نُه جای دیگر
مستقیم خوانده می‌شوند (`card_terminals.unsettled_balance`،
`banking.pos_pending_settlements`، `banking.settle_pos`، `cashboxes._in_use`،
`bank_accounts._in_use`، …). بردنشان به یک جدولِ فرزند یعنی نُه فرصت برای یک عددِ
غلطِ بی‌صدا. تسویه‌ی کارت‌خوان **دو مهاجرت پیش** ساخته شد؛ زیرِ پایش را خالی
نمی‌کنیم.

**چرا چک جزءِ خزانه نشد؟** چون `contact_balance` چک را جداگانه می‌شمارد؛ اگر چک
یک ردیفِ خزانه هم می‌شد، هر چکِ دریافتی **دو بار** از مانده کم می‌کرد.

سه دسته تغییر:

۱) **`receipts`** — سربرگ. یکتا روی `(tenant_id, number)`؛ شماره از
   `next_document_number` می‌آید نه SEQUENCE، پس بی‌شکاف است.

۲) **ستون‌های ابطال روی `receipts`، `treasury_transactions` و `checks`.** تا امروز
   رسیدِ اشتباه **هیچ راهِ اصلاحی نداشت** — نه حذف، نه ابطال، و
   `void_journal_entry` سندِ غیر‌دستی را رد می‌کند. این‌جا فقط ستون‌ها ساخته
   می‌شوند؛ منطقش در `services/receipts.py` است و از
   `voiding.reverse_journal_entry`ِ موجود استفاده می‌کند.

۳) **هویتِ چک** — `branch_name`/`branch_code`، `account_number`، `owner_name`،
   `description2`. **`sayad_id` و `back_number` این‌جا نیستند:** مهاجرتِ ۰۱۱۰
   (چرخه‌ی عمرِ چک) زودتر ساختشان و روی تولید نشسته‌اند. ولی ایندکسِ یکتای
   **جزئیِ** صیادی این‌جا ساخته می‌شود — آن مهاجرت فقط ستون را داد، نه قید را،
   و بدونِ قید یک کدِ صیادی می‌توانست روی دو چک بنشیند.

۴) **چهار مفهومِ مالیِ §۲۲ و `receipt_related_documents`** — قرینه‌ی `payments`
   در مهاجرتِ ۰۱۱۰. دو سندِ خواهر با دو توانِ متفاوت منتشر نمی‌شوند؛ سپیدار هم
   این دو را آینه‌ی هم می‌داند. **کارمزد استثناست** و فقط سمتِ پرداخت اضافه شد:
   معادلِ سمتِ دریافت، کارمزدِ وصولِ چکِ واگذاری است که مفهومِ دیگری است و
   به‌زور در تقارن جا نمی‌شود.

**هیچ `INSERT/UPDATE`ای اینجا نیست.** `receipt_id` روی ردیف‌های موجود `NULL`
می‌ماند و آن **حقیقت** است: یا پیش از این مهاجرت ثبت شده، یا اثرِ جانبیِ سندِ
دیگری است (قسط، بازارگاه) که سربرگِ خودش را دارد.

**و پیش‌پروازی هم ندارد — عمداً.** مهاجرتِ ۰۱۰۸ پیش از ساختنِ ایندکسِ یکتای برگ،
اول دنبالِ تکراری‌ها می‌گشت؛ آن‌جا لازم بود چون `checks.number` و `checkbook_id`
از قبل داده داشتند. این‌جا ستونِ `sayad_id` را **خودِ همین مهاجرت** می‌سازد و همه‌ی
ردیف‌ها رشته‌ی خالی می‌گیرند که ایندکسِ جزئی ردشان می‌کند. پس تکراری‌ای وجود
ندارد که پیدا شود، و گاردی که هرگز شلیک نمی‌کند فقط خواننده‌ی بعدی را فریب می‌دهد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.tenancy import policy_name

revision: str = "0111"
down_revision: Union[str, None] = "0110"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "receipts"
SAYAD_INDEX = "uq_checks_tenant_sayad"

#: ستون‌های ابطال — یک شکل روی هر سه جدول، تا «باطل است یا نه» یک معنا داشته باشد.
VOID_COLUMN_NAMES = ("voided_at", "void_reason", "voided_by_id")


def _void_columns() -> list[sa.Column]:
    """هر بار ستون‌های تازه — یک شیءِ `Column` را نمی‌شود دو جدول داد."""
    return [
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sa.Text(), server_default="", nullable=False),
        sa.Column("voided_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    ]


def _enable_rls(table: str) -> None:
    """همان سه دستورِ همیشگی — بدونِ این، جدولِ تازه بینِ مستأجرها نشت می‌کند."""
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
    op.create_table(
        TABLE,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("number", sa.Numeric(18, 0), nullable=False),
        sa.Column("receipt_type", sa.String(20), server_default="customer", nullable=False),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        #: حساب‌ها از نقشِ سیستمی resolve می‌شوند، ولی شناسه‌ی واقعیِ استفاده‌شده
        #: روی سند می‌ماند — تا سالِ بعد که چارت عوض شده، معلوم باشد کجا خورد.
        sa.Column("counterparty_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("discount_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("currency_code", sa.String(3), server_default="IRR", nullable=False),
        sa.Column("exchange_rate", sa.Numeric(18, 4), server_default="1", nullable=False),
        #: **چهار مفهومِ مستقل** (§۲۲) که در یک عدد ادغام نمی‌شوند:
        #: پولی که واقعاً رسید، معادلش به ارزِ پایه (همان که سند می‌خورد)، تخفیفی
        #: که پول نیست ولی بدهی را می‌بندد، و جمعِ تسویه که مانده‌ی طرف‌حساب را
        #: به اندازه‌ی آن حرکت می‌دهد.
        sa.Column("receipt_amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("base_currency_amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("discount_amount", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("settlement_total", sa.Numeric(18, 0), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("description2", sa.String(200), server_default="", nullable=False),
        #: §۲۹ — «استقرار» فقط ذخیره می‌شود. فصل صریح است: تا گردش‌کارش معلوم
        #: نشده، اثرِ مالی یا قاعده‌ای برایش حدس نزنید.
        sa.Column("establishment", sa.String(120), server_default="", nullable=False),
        sa.Column(
            "journal_entry_id",
            UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        *_void_columns(),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "number", name="uq_receipts_tenant_number"),
        sa.CheckConstraint(
            "receipt_type IN ('customer', 'supplier', 'intermediary', 'other', 'petty_holder')",
            name="ck_receipts_type",
        ),
        sa.CheckConstraint("receipt_amount > 0", name="ck_receipts_amount_positive"),
        sa.CheckConstraint("discount_amount >= 0", name="ck_receipts_nonnegative"),
        sa.CheckConstraint("exchange_rate > 0", name="ck_receipts_exchange_rate_positive"),
    )

    _enable_rls(TABLE)

    #: §۲۰ — پیوندِ قابلِ ردگیری بینِ رسید و سندِ کسب‌وکار. **تخصیصِ کاملِ
    #: فاکتور‌به‌فاکتور این‌جا نیست** و فصل هم نمی‌خواهدش: «منطق دقیق Allocation
    #: را بهتر است با قسمت تسویه حساب طرف مقابل نهایی کنیم». چیزی که هست، رابطه
    #: است — تا وقتی موتورِ تسویه آمد، تاریخچه‌ای برای خواندن داشته باشد.
    op.create_table(
        "receipt_related_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("receipt_id", UUID(as_uuid=True), sa.ForeignKey("receipts.id"), nullable=False, index=True),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "receipt_id", "document_type", "document_id", name="uq_receipt_related_document"
        ),
        sa.CheckConstraint("allocated_amount >= 0", name="ck_receipt_related_allocated_nonnegative"),
    )
    _enable_rls("receipt_related_documents")

    op.add_column(
        "treasury_transactions",
        sa.Column("receipt_id", UUID(as_uuid=True), sa.ForeignKey("receipts.id"), nullable=True),
    )
    op.create_index("ix_treasury_transactions_receipt_id", "treasury_transactions", ["receipt_id"])

    op.add_column(
        "checks",
        sa.Column("receipt_id", UUID(as_uuid=True), sa.ForeignKey("receipts.id"), nullable=True),
    )
    op.create_index("ix_checks_receipt_id", "checks", ["receipt_id"])

    # ── هویتِ برگ (§۱۰ §۱۱) — همه با پیش‌فرضِ خالی، پس هیچ ردیفی به‌روز نمی‌شود ──
    #: `sayad_id` و `back_number` این‌جا نیستند — مهاجرتِ ۰۱۱۰ (چرخه‌ی عمرِ چک)
    #: زودتر ساختشان و روی تولید نشسته‌اند. دوباره‌ساختنشان یعنی شکستِ استقرار.
    for name, length in (
        ("branch_name", 100),
        ("branch_code", 20),
        ("account_number", 40),
        ("owner_name", 120),
        ("description2", 200),
    ):
        op.add_column("checks", sa.Column(name, sa.String(length), server_default="", nullable=False))

    op.create_index(
        SAYAD_INDEX,
        "checks",
        ["tenant_id", "sayad_id"],
        unique=True,
        postgresql_where=sa.text("sayad_id <> ''"),
    )

    for table in ("treasury_transactions", "checks"):
        for column in _void_columns():
            op.add_column(table, column)
        op.create_index(f"ix_{table}_voided_at", table, ["voided_at"])


def downgrade() -> None:
    for table in ("treasury_transactions", "checks"):
        op.drop_index(f"ix_{table}_voided_at", table_name=table)
        for name in reversed(VOID_COLUMN_NAMES):
            op.drop_column(table, name)

    op.drop_index(SAYAD_INDEX, table_name="checks")
    for name in (
        "description2",
        "owner_name",
        "account_number",
        "branch_code",
        "branch_name",
    ):
        op.drop_column("checks", name)

    op.drop_index("ix_checks_receipt_id", table_name="checks")
    op.drop_column("checks", "receipt_id")
    op.drop_index("ix_treasury_transactions_receipt_id", table_name="treasury_transactions")
    op.drop_column("treasury_transactions", "receipt_id")

    op.drop_table("receipt_related_documents")
    op.drop_table(TABLE)
