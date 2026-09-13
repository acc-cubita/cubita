"""خروجِ انبار دیگر فقط زیرِ فاکتورِ فروش نیست

Revision ID: 0133
Revises: 0132

تا امروز `warehouse_issues.sales_invoice_id` و `warehouse_issue_lines.sales_invoice_line_id`
اجباری بودند: خروج فقط از دلِ ردیفِ فاکتور ساخته می‌شد. پس سه چیزِ واقعی ثبت‌شدنی
نبود — مصرفِ داخلی، خروجِ «سایر»، و فروشی که کالایش پیش از فاکتور تحویل می‌شود —
و تنها راهِ کم‌کردنِ موجودی بیرون از فروش «تعدیلِ دستی» بود.

این مهاجرت:

* نوعِ خروج (`sale` / `consumption` / `other`) و منشأ (`invoice` / `direct`) را
  می‌افزاید. «انتقال بین انبار» عمداً نوعِ این جدول نیست؛ سندِ خودش را دارد.
* تحویل‌گیرنده، مرجعِ پیش‌فاکتور و مرکزِ هزینه را روی سربرگ می‌گذارد.
* روی ردیف: شماره‌ی ردیف، معینِ طرفِ بدهکار، مقدارِ فرعیِ نمایشی، و بهای واحد با
  چهار رقمِ اعشار (هم‌دقتِ `stock_ledger.unit_cost`).
* به `stock_transfers` ستون‌های ابطال و `journal_entry_id` می‌دهد.

**backfill:** تحویل‌گیرنده‌ی خروج‌های موجود = مشتریِ فاکتورشان؛ معینِ ردیف‌های
موجود = حسابِ نقشِ `cogs`ِ همان مستأجر، چون `create_warehouse_issue` همیشه همان را
سند می‌زد؛ شماره‌ی ردیف به ترتیبِ شناسه (ترتیبِ ورودِ واقعی دیگر در دسترس نیست).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled

revision: str = "0133"
down_revision: Union[str, None] = "0132"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ISSUE_TYPES = ("sale", "consumption", "other")
ISSUE_ORIGINS = ("invoice", "direct")

#: کلیدِ خارجی زیرِ `FORCE ROW LEVEL SECURITY` اسکنِ اعتبارسنجی راه می‌اندازد که
#: `app.tenant_id` را می‌خواند؛ هر دو سرِ هر رابطه باید این‌جا باشند. backfillها هم
#: بدونِ این فهرست بی‌صدا صفر ردیف می‌دیدند.
_TABLES = (
    "warehouse_issues",
    "warehouse_issue_lines",
    "sales_invoices",
    "contacts",
    "sales_quotations",
    "cost_centers",
    "accounts",
    "stock_transfers",
    "journal_entries",
    "users",
)


def _in(values: tuple[str, ...]) -> str:
    return "({})".format(", ".join(f"'{v}'" for v in values))


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column(
        "warehouse_issues", sa.Column("issue_type", sa.String(20), server_default="sale", nullable=False)
    )
    op.add_column(
        "warehouse_issues", sa.Column("origin", sa.String(10), server_default="invoice", nullable=False)
    )
    op.add_column("warehouse_issues", sa.Column("receiver_id", UUID(as_uuid=True), nullable=True))
    op.add_column("warehouse_issues", sa.Column("source_quotation_id", UUID(as_uuid=True), nullable=True))
    op.add_column("warehouse_issues", sa.Column("cost_center_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_warehouse_issues_receiver_id", "warehouse_issues", ["receiver_id"])
    op.create_index("ix_warehouse_issues_source_quotation_id", "warehouse_issues", ["source_quotation_id"])
    op.create_check_constraint("ck_warehouse_issues_type", "warehouse_issues", f"issue_type IN {_in(ISSUE_TYPES)}")
    op.create_check_constraint("ck_warehouse_issues_origin", "warehouse_issues", f"origin IN {_in(ISSUE_ORIGINS)}")
    op.alter_column("warehouse_issues", "sales_invoice_id", existing_type=UUID(as_uuid=True), nullable=True)

    op.add_column(
        "warehouse_issue_lines", sa.Column("seq", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("warehouse_issue_lines", sa.Column("account_id", UUID(as_uuid=True), nullable=True))
    op.add_column("warehouse_issue_lines", sa.Column("secondary_qty", sa.Numeric(18, 3), nullable=True))
    op.add_column(
        "warehouse_issue_lines",
        sa.Column("secondary_unit_snapshot", sa.String(20), server_default="", nullable=False),
    )
    op.alter_column(
        "warehouse_issue_lines", "sales_invoice_line_id", existing_type=UUID(as_uuid=True), nullable=True
    )
    op.alter_column(
        "warehouse_issue_lines",
        "unit_cost",
        existing_type=sa.Numeric(18, 0),
        type_=sa.Numeric(18, 4),
        existing_nullable=False,
    )

    op.add_column("stock_transfers", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_stock_transfers_voided_at", "stock_transfers", ["voided_at"])
    op.add_column("stock_transfers", sa.Column("void_reason", sa.Text(), server_default="", nullable=False))
    op.add_column("stock_transfers", sa.Column("voided_by_id", UUID(as_uuid=True), nullable=True))
    op.add_column("stock_transfers", sa.Column("journal_entry_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_stock_transfers_journal_entry_id", "stock_transfers", ["journal_entry_id"])

    with rls_disabled(conn, _TABLES):
        op.create_foreign_key(
            "fk_warehouse_issues_receiver", "warehouse_issues", "contacts", ["receiver_id"], ["id"]
        )
        op.create_foreign_key(
            "fk_warehouse_issues_source_quotation",
            "warehouse_issues",
            "sales_quotations",
            ["source_quotation_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_warehouse_issues_cost_center", "warehouse_issues", "cost_centers", ["cost_center_id"], ["id"]
        )
        op.create_foreign_key(
            "fk_warehouse_issue_lines_account", "warehouse_issue_lines", "accounts", ["account_id"], ["id"]
        )
        op.create_foreign_key(
            "fk_stock_transfers_voided_by", "stock_transfers", "users", ["voided_by_id"], ["id"]
        )
        op.create_foreign_key(
            "fk_stock_transfers_journal_entry",
            "stock_transfers",
            "journal_entries",
            ["journal_entry_id"],
            ["id"],
        )

        conn.execute(
            sa.text(
                """
                UPDATE warehouse_issues wi
                   SET receiver_id = si.contact_id
                  FROM sales_invoices si
                 WHERE si.id = wi.sales_invoice_id AND wi.receiver_id IS NULL
                """
            )
        )
        conn.execute(
            sa.text(
                """
                UPDATE warehouse_issue_lines l
                   SET seq = n.rn
                  FROM (
                        SELECT id, row_number() OVER (PARTITION BY issue_id ORDER BY id) AS rn
                          FROM warehouse_issue_lines
                       ) n
                 WHERE n.id = l.id
                """
            )
        )
        conn.execute(
            sa.text(
                """
                UPDATE warehouse_issue_lines l
                   SET account_id = a.id
                  FROM accounts a
                 WHERE a.tenant_id = l.tenant_id AND a.system_role = 'cogs' AND l.account_id IS NULL
                """
            )
        )


def downgrade() -> None:
    op.drop_constraint("fk_stock_transfers_journal_entry", "stock_transfers")
    op.drop_constraint("fk_stock_transfers_voided_by", "stock_transfers")
    op.drop_index("ix_stock_transfers_journal_entry_id", "stock_transfers")
    op.drop_index("ix_stock_transfers_voided_at", "stock_transfers")
    for column in ("journal_entry_id", "voided_by_id", "void_reason", "voided_at"):
        op.drop_column("stock_transfers", column)

    #: **بعد از اولین خروجِ مستقیمِ واقعی اجرا نمی‌شود:** `NOT NULL`ِ دوباره روی
    #: ردیفی که فاکتور ندارد شکست می‌خورد. بها هم به ریالِ صحیح گِرد می‌شود (بااتلاف).
    op.alter_column(
        "warehouse_issue_lines",
        "unit_cost",
        existing_type=sa.Numeric(18, 4),
        type_=sa.Numeric(18, 0),
        existing_nullable=False,
    )
    op.alter_column(
        "warehouse_issue_lines", "sales_invoice_line_id", existing_type=UUID(as_uuid=True), nullable=False
    )
    op.drop_constraint("fk_warehouse_issue_lines_account", "warehouse_issue_lines")
    for column in ("secondary_unit_snapshot", "secondary_qty", "account_id", "seq"):
        op.drop_column("warehouse_issue_lines", column)

    op.alter_column("warehouse_issues", "sales_invoice_id", existing_type=UUID(as_uuid=True), nullable=False)
    op.drop_constraint("fk_warehouse_issues_cost_center", "warehouse_issues")
    op.drop_constraint("fk_warehouse_issues_source_quotation", "warehouse_issues")
    op.drop_constraint("fk_warehouse_issues_receiver", "warehouse_issues")
    op.drop_constraint("ck_warehouse_issues_origin", "warehouse_issues")
    op.drop_constraint("ck_warehouse_issues_type", "warehouse_issues")
    op.drop_index("ix_warehouse_issues_source_quotation_id", "warehouse_issues")
    op.drop_index("ix_warehouse_issues_receiver_id", "warehouse_issues")
    for column in ("cost_center_id", "source_quotation_id", "receiver_id", "origin", "issue_type"):
        op.drop_column("warehouse_issues", column)
