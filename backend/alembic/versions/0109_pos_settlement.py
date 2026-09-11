"""تسویه‌ی کارت‌خوان: سندِ انتقالِ وجه از «در راه» به بانک

Revision ID: 0109
Revises: 0108

## چه چیزی غلط بود

رسیدِ کارتی از همان لحظه‌ی کارت‌کشیدن **معینِ بانک** را بدهکار می‌کرد. ولی پول آن
لحظه به بانک نرسیده؛ شبکه‌ی پرداخت چند روز بعد جمعِ چند تراکنش را منهای کارمزد
واریز می‌کند. سه پیامدِ سنجیدنی داشت:

1. مانده‌ی بانک — که از دفتر می‌آید — **دقیقاً به اندازه‌ی پولِ تسویه‌نشده باد کرده
   بود**.
2. برای واریزِ واقعیِ PSP هیچ `bank_transactions`ی ساخته نمی‌شد، پس مغایرت‌گیری
   هرگز نمی‌توانست آن خطِ صورت‌حساب را تطبیق دهد. تنها ردیفِ سیستمی یک «منهای
   کارمزد» بود که با هیچ خطی نمی‌خواند.
3. تسویه رکورد نبود: نه شماره داشت، نه فهرست، نه راهی برای ابطال، و
   `settlement_txn_id` **فقط وقتی کارمزد بزرگ‌تر از صفر بود** پر می‌شد — یعنی
   تسویه‌ی بی‌کارمزد هیچ ردی نمی‌گذاشت.

## چه چیزی اینجا عوض می‌شود

* جدولِ `pos_settlements` — خودِ سندِ تسویه.
* `pos_terminals.analytic_id` — تا وجوهِ در راهِ هر دستگاه در دفتر جدا بماند.
* `treasury_transactions.settlement_id` — «این رسید با کدام تسویه رفت».
* شمارنده‌ی `pos_settlement` برای مستأجرهای موجود.
* **طبقه‌بندیِ دوباره‌ی رسیدهای کارتیِ تسویه‌نشده** از معینِ بانک به معینِ وجوهِ
  در راه.

## چرا این‌بار نوشتنِ داده لازم است (و در `rls_disabled` می‌رود)

قاعده‌ی پروژه «در مهاجرت روی جدولِ RLS ننویس» است، و در ۰۱۰۵/۰۱۰۶/۰۱۰۷ رعایت شد
چون `NULL` معنا داشت و داده‌ی مستقر بی‌تغییر درست می‌ماند. **اینجا نمی‌شود.**

اگر رسیدهای تسویه‌نشده‌ی امروز روی بانک بمانند، تسویه‌ی آینده‌شان معینِ *وجوهِ در
راه* را به اندازه‌ی ناخالص بستانکار می‌کند — حسابی که هرگز بدهکار نشده. نتیجه
مانده‌ی منفیِ وجوهِ در راه و مانده‌ی بانکِ دوباره‌شمرده است. یعنی بی‌عملی اینجا
داده‌ی غلط می‌سازد، نه داده‌ی دست‌نخورده.

دامنه‌ی نوشتن عمداً باریک است: **فقط رسیدهای کارتیِ تسویه‌نشده.** رسیدهای
تسویه‌شده دست نمی‌خورند و درست هم هستند — پولشان واقعاً به بانک رسیده.

شمارنده‌ها هم چاره‌ای ندارند: `next_document_number` برای مستأجرِ بی‌شمارنده عمداً
۵۰۰ می‌دهد تا بی‌صدا از ۱ شروع نکند، پس بدونِ این INSERT اولین تسویه‌ی هر
کسب‌وکارِ موجود شکست می‌خورد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0109"
down_revision: Union[str, None] = "0108"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "pos_settlements"

CLEARING_ROLE = "pos_clearing"
CLEARING_CODE = "1112"
CLEARING_NAME = "وجوهِ در راهِ کارت‌خوان"

#: جدول‌هایی که نوشتنِ داده‌ی این مهاجرت لمسشان می‌کند.
WRITE_TABLES = [
    "accounts",
    "journal_lines",
    "treasury_transactions",
    "bank_accounts",
    "document_counters",
]

#: مستأجرهایی که پولِ کارتیِ تسویه‌نشده دارند — تنها جایی که حسابِ واسط لازم است.
TENANTS_WITH_UNSETTLED = """
    SELECT DISTINCT tenant_id
      FROM treasury_transactions
     WHERE paid_via = 'pos_terminal' AND settled_at IS NULL
"""


def upgrade() -> None:
    conn = op.get_bind()

    # ── سندِ تسویه ───────────────────────────────────────────────────────────
    op.create_table(
        TABLE,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("number", sa.BigInteger(), nullable=False),
        sa.Column("settlement_date", sa.Date(), nullable=False),
        #: برشِ انتخابِ رسیدها — با تاریخِ بالا یکی نیست و نباید بشود (§۸ §۹).
        sa.Column("settle_through", sa.Date(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column(
            "pos_terminal_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pos_terminals.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "bank_account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("bank_accounts.id"),
            nullable=False,
        ),
        sa.Column("gross_amount", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("fee_amount", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("net_amount", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column(
            "journal_entry_id",
            UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "bank_transaction_id",
            UUID(as_uuid=True),
            sa.ForeignKey("bank_transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sa.Text(), server_default="", nullable=False),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.UniqueConstraint("tenant_id", "number", name="uq_pos_settlements_tenant_number"),
    )

    # ── تفصیلیِ دستگاه و پیوندِ رسید به تسویه ─────────────────────────────────
    op.add_column(
        "pos_terminals",
        sa.Column(
            "analytic_id",
            UUID(as_uuid=True),
            sa.ForeignKey("analytic_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "treasury_transactions",
        sa.Column(
            "settlement_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pos_settlements.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    #: **RLS بعد از کلیدِ خارجی روشن می‌شود، نه قبلش.** افزودنِ
    #: `treasury_transactions.settlement_id` یک اسکنِ اعتبارسنجیِ Postgres روی
    #: `pos_settlements` راه می‌اندازد؛ اگر سیاست از قبل روشن باشد، آن اسکن
    #: `current_setting('app.tenant_id')` را می‌خواند — که در مهاجرت تنظیم نیست —
    #: و مهاجرت با «unrecognized configuration parameter» می‌شکند.
    conn.execute(sa.text(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(TABLE)} ON {TABLE}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name(TABLE)} ON {TABLE} "
            "USING (tenant_id = current_setting('app.tenant_id')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)"
        )
    )

    with rls_disabled(conn, WRITE_TABLES):
        # ── شمارنده‌ی نوعِ سندِ تازه، برای همه‌ی مستأجرهای موجود ──
        conn.execute(
            sa.text(
                """
                INSERT INTO document_counters (id, tenant_id, doc_type, last_number,
                                               created_at, updated_at)
                SELECT gen_random_uuid(), t.id, 'pos_settlement', 0, now(), now()
                  FROM tenants t
                 WHERE NOT EXISTS (
                       SELECT 1 FROM document_counters d
                        WHERE d.tenant_id = t.id AND d.doc_type = 'pos_settlement')
                """
            )
        )

        # ── حسابِ «وجوهِ در راهِ کارت‌خوان» ──
        #
        # فقط برای مستأجرهایی که واقعاً پولِ تسویه‌نشده دارند. بقیه بارِ اول از
        # مسیرِ `get_or_create_account` می‌سازندش — همان الگویی که حساب‌های
        # مالیات بر ارزشِ افزوده دارند.
        #
        # اگر کسب‌وکاری کدِ ۱۱۰۸ را خودش گرفته باشد، این INSERT ردش می‌کند و
        # سرویس بارِ اول با پسوندِ V می‌سازدش. بی‌صدا روی حسابِ کاربر نمی‌نویسیم.
        conn.execute(
            sa.text(
                f"""
                INSERT INTO accounts (id, tenant_id, code, system_role, name, type,
                                      is_group, parent_id, created_at, updated_at)
                SELECT gen_random_uuid(), t.tenant_id,
                       CAST(:code AS varchar), CAST(:role AS varchar),
                       CAST(:name AS varchar), 'asset', false,
                       (SELECT a.id FROM accounts a
                         WHERE a.tenant_id = t.tenant_id AND a.is_group AND a.code = '1'
                         LIMIT 1),
                       now(), now()
                  FROM ({TENANTS_WITH_UNSETTLED}) t
                 WHERE NOT EXISTS (
                       SELECT 1 FROM accounts a
                        WHERE a.tenant_id = t.tenant_id
                          AND (a.code = CAST(:code AS varchar)
                               OR a.system_role = CAST(:role AS varchar)))
                """
            ),
            {"code": CLEARING_CODE, "role": CLEARING_ROLE, "name": CLEARING_NAME},
        )

        # ── طبقه‌بندیِ دوباره: بانک ← وجوهِ در راه ──
        #
        # فقط ردیفِ بدهکارِ خودِ رسید، و فقط وقتی مبلغش دقیقاً برابرِ مبلغِ رسید
        # است. سندِ رسیدِ خزانه دو ردیف بیشتر ندارد، ولی این شرط تضمین می‌کند اگر
        # روزی سندی دست‌کاری شده باشد، مهاجرت ردیفِ اشتباه را نبرد.
        conn.execute(
            sa.text(
                """
                UPDATE journal_lines jl
                   SET account_id = c.id,
                       analytic_id = NULL
                  FROM treasury_transactions tt
                  JOIN bank_accounts ba ON ba.id = tt.bank_account_id
                  JOIN accounts c ON c.tenant_id = tt.tenant_id
                                 AND c.system_role = CAST(:role AS varchar)
                 WHERE jl.entry_id = tt.journal_entry_id
                   AND jl.tenant_id = tt.tenant_id
                   AND tt.paid_via = 'pos_terminal'
                   AND tt.settled_at IS NULL
                   AND jl.account_id = ba.gl_account_id
                   AND jl.debit = tt.amount
                """
            ),
            {"role": CLEARING_ROLE},
        )


def downgrade() -> None:
    conn = op.get_bind()

    with rls_disabled(conn, WRITE_TABLES):
        #: برگرداندنِ همان ردیف‌ها به معینِ بانک و تفصیلیِ خودش. تسویه‌های ثبت‌شده‌ی
        #: پس از این مهاجرت برنمی‌گردند — جدولشان که برود، سندشان می‌ماند و باید
        #: دستی بررسی شود. برای همین downgrade اینجا فقط شبکه‌ی ایمنیِ توسعه است.
        conn.execute(
            sa.text(
                """
                UPDATE journal_lines jl
                   SET account_id = ba.gl_account_id,
                       analytic_id = ba.analytic_id
                  FROM treasury_transactions tt
                  JOIN bank_accounts ba ON ba.id = tt.bank_account_id
                  JOIN accounts c ON c.tenant_id = tt.tenant_id
                                 AND c.system_role = CAST(:role AS varchar)
                 WHERE jl.entry_id = tt.journal_entry_id
                   AND jl.tenant_id = tt.tenant_id
                   AND tt.paid_via = 'pos_terminal'
                   AND tt.settled_at IS NULL
                   AND jl.account_id = c.id
                   AND jl.debit = tt.amount
                """
            ),
            {"role": CLEARING_ROLE},
        )
        conn.execute(
            sa.text("DELETE FROM document_counters WHERE doc_type = 'pos_settlement'")
        )
        conn.execute(sa.text("DELETE FROM accounts WHERE system_role = CAST(:role AS varchar)"), {"role": CLEARING_ROLE})

    op.drop_column("treasury_transactions", "settlement_id")
    op.drop_column("pos_terminals", "analytic_id")
    op.drop_table(TABLE)
