"""چک: تاریخچه‌ی عملیات، واگذاریِ دیده‌شدنی در دفتر، و نقد کردن

Revision ID: 0110
Revises: 0109

## چه چیزی نبود

**۱. واگذاری به بانک هیچ ردی در دفتر نمی‌گذاشت.** گذرِ `in_hand → deposited` فقط
`bank_account_id` را می‌نشاند و سندی نمی‌زد. یعنی مبلغِ چک تا لحظه‌ی وصول روی
«چک‌های دریافتنی» می‌ماند و دفتر نمی‌توانست بگوید چقدرش نزدِ ماست و چقدرش دستِ
بانک. سؤالِ «چقدر چک در جریانِ وصول داریم؟» فقط با شمردنِ ردیف‌ها جواب داشت،
نه از تراز.

**۲. هیچ تاریخچه‌ای نبود.** `checks.status` می‌گفت چک الان کجاست و تمام. و
`Check` **در رجیستریِ `audit.audited_models()` هم نبود** — موجودیتی با غنی‌ترین
چرخه‌ی عمرِ خزانه، تنها موجودیتی بود که هیچ ردی از خودش نمی‌گذاشت.

**۳. نقد کردن وجود نداشت.** چکِ دریافتنی فقط از راهِ بانک وصول می‌شد. کاربری که
چک را نقد کرده بود مجبور بود «وصول» ثبت کند — که پول را به بانکی می‌برد که
هرگز چیزی نگرفته بود.

**۴. استردادِ چکِ پرداختنی راه نداشت** و ردیف‌های حسابداری‌اش سمتِ دریافتنی
hard-code شده بودند؛ بازکردنِ آن گذر سندِ غلط می‌زد بی‌آنکه چیزی خطا بدهد.

## چه چیزی اینجا عوض می‌شود

* جدولِ `check_events` — تاریخچه، **فقط‌افزودنی** با همان گاردِ `audit_log`.
* `checks.sayad_id` و `checks.back_number` — شناسه‌هایی که روی هر برگِ بانکی
  هستند و در استعلام و مغایرت‌گیری لازم‌اند (§۸ §۲۵ §۲۸).
* `checks.cashbox_id` — مقصدِ نقد کردن.
* قیدِ وضعیت بازتر می‌شود تا `cashed` را بپذیرد.
* شمارنده‌ی `check_operation` برای مستأجرهای موجود.
* **طبقه‌بندیِ دوباره‌ی چک‌های واگذارشده** از «چک‌های دریافتنی» به حسابِ تازه‌ی
  «چک‌های واگذارشده به بانک».

## چرا نوشتنِ داده لازم است

همان استدلالِ ۰۱۰۹: اگر چک‌هایی که **الان** `deposited` هستند روی «چک‌های
دریافتنی» بمانند، وصولِ آینده‌شان حسابِ واسط را بستانکار می‌کند — حسابی که هرگز
بدهکار نشده. نتیجه مانده‌ی منفیِ واسط و «چک‌های دریافتنی»ِ دوباره‌شمرده. یعنی
بی‌عملی اینجا داده‌ی غلط می‌سازد، نه داده‌ی دست‌نخورده.

دامنه عمداً باریک است: **فقط چک‌های دریافتنیِ در وضعیتِ `deposited`.** چکِ
وصول‌شده، نقدنشده، خرج‌شده و مسترد دست نمی‌خورند.

**تاریخچه backfill نمی‌شود.** برای چک‌های موجود رویدادی ساخته نمی‌شود، چون
تاریخ و کاربرِ آن گذرها را نداریم و ساختنشان یعنی جعلِ تاریخچه — دقیقاً چیزی که
§۴۷ منعش می‌کند. تایم‌لاینِ چک‌های قدیمی از روزِ این مهاجرت شروع می‌شود.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.audit import append_only_statements
from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0110"
down_revision: Union[str, None] = "0109"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "check_events"

IN_COLLECTION_ROLE = "checks_in_collection"
IN_COLLECTION_CODE = "1113"
IN_COLLECTION_NAME = "چک‌های واگذارشده به بانک"

OLD_STATUSES = "('in_hand', 'deposited', 'cleared', 'bounced', 'endorsed', 'issued', 'returned')"
NEW_STATUSES = (
    "('in_hand', 'deposited', 'cleared', 'bounced', 'endorsed', 'issued', 'returned', 'cashed')"
)

WRITE_TABLES = ["accounts", "journal_lines", "checks", "document_counters"]

#: مستأجرهایی که چکِ واگذارشده دارند — تنها جایی که حسابِ واسط لازم است.
TENANTS_WITH_DEPOSITED = """
    SELECT DISTINCT tenant_id
      FROM checks
     WHERE type = 'receivable' AND status = 'deposited'
"""


def upgrade() -> None:
    conn = op.get_bind()

    # ── ستون‌های تازه‌ی خودِ چک ───────────────────────────────────────────────
    op.add_column("checks", sa.Column("back_number", sa.String(50), server_default="", nullable=False))
    op.add_column("checks", sa.Column("sayad_id", sa.String(20), server_default="", nullable=False))
    op.add_column(
        "checks",
        sa.Column("cashbox_id", UUID(as_uuid=True), sa.ForeignKey("cashboxes.id"), nullable=True),
    )

    #: قید باید *پیش از* آمدنِ داده‌ی `cashed` باز شود.
    op.drop_constraint("ck_checks_status", "checks", type_="check")
    op.create_check_constraint("ck_checks_status", "checks", f"status IN {NEW_STATUSES}")

    # ── تاریخچه ──────────────────────────────────────────────────────────────
    op.create_table(
        TABLE,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column(
            "check_id",
            UUID(as_uuid=True),
            sa.ForeignKey("checks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("operation", sa.String(30), nullable=False),
        #: NULL فقط برای رویدادِ اولِ چک که وضعیتِ قبلی ندارد.
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, index=True
        ),
        sa.Column("operation_no", sa.BigInteger(), nullable=True, index=True),
        sa.Column("batch_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column(
            "bank_account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("bank_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "cashbox_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cashboxes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "contact_id",
            UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "journal_entry_id",
            UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_check_events_check_at", TABLE, ["check_id", "at"])
    op.create_index("ix_check_events_tenant_at", TABLE, ["tenant_id", "at"])

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
    #: §۴۷ — تاریخچه بازنویسی نمی‌شود. همان گاردِ `audit_log`، با تریگرِ خودش.
    for stmt in append_only_statements(TABLE):
        conn.execute(sa.text(stmt))

    with rls_disabled(conn, WRITE_TABLES):
        # ── شمارنده‌ی عملیاتِ چک ──
        conn.execute(
            sa.text(
                """
                INSERT INTO document_counters (id, tenant_id, doc_type, last_number,
                                               created_at, updated_at)
                SELECT gen_random_uuid(), t.id, 'check_operation', 0, now(), now()
                  FROM tenants t
                 WHERE NOT EXISTS (
                       SELECT 1 FROM document_counters d
                        WHERE d.tenant_id = t.id AND d.doc_type = 'check_operation')
                """
            )
        )

        # ── حسابِ «چک‌های واگذارشده به بانک» ──
        #
        # فقط برای مستأجرهایی که واقعاً چکِ واگذارشده دارند؛ بقیه بارِ اول از
        # مسیرِ `get_or_create_account` می‌سازندش.
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
                  FROM ({TENANTS_WITH_DEPOSITED}) t
                 WHERE NOT EXISTS (
                       SELECT 1 FROM accounts a
                        WHERE a.tenant_id = t.tenant_id
                          AND (a.code = CAST(:code AS varchar)
                               OR a.system_role = CAST(:role AS varchar)))
                """
            ),
            {"code": IN_COLLECTION_CODE, "role": IN_COLLECTION_ROLE, "name": IN_COLLECTION_NAME},
        )

        # ── طبقه‌بندیِ دوباره: چک‌های دریافتنی ← چک‌های واگذارشده ──
        #
        # ردیفِ بدهکارِ سندِ *دریافتِ* چک است که جابه‌جا می‌شود، و فقط وقتی مبلغش
        # دقیقاً برابرِ مبلغِ چک باشد. سندِ دریافت دو ردیف بیشتر ندارد، ولی این
        # شرط تضمین می‌کند اگر سندی دست‌کاری شده باشد ردیفِ اشتباه برده نشود.
        conn.execute(
            sa.text(
                """
                UPDATE journal_lines jl
                   SET account_id = c.id
                  FROM checks ch
                  JOIN accounts recv ON recv.tenant_id = ch.tenant_id
                                    AND recv.system_role = 'checks_receivable'
                  JOIN accounts c ON c.tenant_id = ch.tenant_id
                                 AND c.system_role = CAST(:role AS varchar)
                 WHERE jl.tenant_id = ch.tenant_id
                   AND ch.type = 'receivable'
                   AND ch.status = 'deposited'
                   AND jl.account_id = recv.id
                   AND jl.debit = ch.amount
                   -- سندِ *دریافتِ* همین چک. EXISTS و نه JOIN: در UPDATE ... FROM
                   -- نمی‌شود در ONِ یک JOIN به خودِ جدولِ هدف ارجاع داد.
                   AND EXISTS (
                       SELECT 1 FROM journal_entries je
                        WHERE je.id = jl.entry_id
                          AND je.source_type = 'check'
                          AND je.description LIKE '%' || ch.number || '%')
                """
            ),
            {"role": IN_COLLECTION_ROLE},
        )


def downgrade() -> None:
    conn = op.get_bind()

    with rls_disabled(conn, WRITE_TABLES):
        #: برگرداندنِ ردیف‌ها به «چک‌های دریافتنی».
        conn.execute(
            sa.text(
                """
                UPDATE journal_lines jl
                   SET account_id = recv.id
                  FROM checks ch
                  JOIN accounts recv ON recv.tenant_id = ch.tenant_id
                                    AND recv.system_role = 'checks_receivable'
                  JOIN accounts c ON c.tenant_id = ch.tenant_id
                                 AND c.system_role = CAST(:role AS varchar)
                 WHERE jl.tenant_id = ch.tenant_id
                   AND ch.type = 'receivable'
                   AND ch.status = 'deposited'
                   AND jl.account_id = c.id
                   AND jl.debit = ch.amount
                """
            ),
            {"role": IN_COLLECTION_ROLE},
        )
        conn.execute(sa.text("DELETE FROM document_counters WHERE doc_type = 'check_operation'"))
        conn.execute(
            sa.text("DELETE FROM accounts WHERE system_role = CAST(:role AS varchar)"),
            {"role": IN_COLLECTION_ROLE},
        )
        #: چکِ نقدشده وضعیتِ معتبرِ قدیمی می‌خواهد، وگرنه قید برنمی‌گردد.
        conn.execute(sa.text("UPDATE checks SET status = 'cleared' WHERE status = 'cashed'"))

    op.drop_table(TABLE)
    op.drop_constraint("ck_checks_status", "checks", type_="check")
    op.create_check_constraint("ck_checks_status", "checks", f"status IN {OLD_STATUSES}")
    op.drop_column("checks", "cashbox_id")
    op.drop_column("checks", "sayad_id")
    op.drop_column("checks", "back_number")
