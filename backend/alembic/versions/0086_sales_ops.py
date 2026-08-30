"""عملیاتِ ماژولِ فروش: قیمت‌گذاری، بسته، پورسانت، گمرک، اعلامیه، بستنِ فاکتور

Revision ID: 0086
Revises: 0085

ماژولِ فروش تا امروز سه کار می‌کرد (فاکتور، پیش‌فاکتور، برگشت) و هرچه دورِ فروش
می‌چرخد بیرونِ سامانه انجام می‌شد. این مهاجرت پایه‌ی هفده عملیاتِ خواسته‌شده را
می‌گذارد.

**اعلامیه‌ی قیمت جدولِ تازه نگرفت.** `price_lists` از قبل هست (انبار پیشرفته) و به
کالاها هم وصل شده؛ جدولِ دوم یعنی دو حقیقتِ ممکن برای «قیمتِ این کالا چند است». فقط
`effective_from` به همان اضافه شد، چون اعلامیه بدونِ تاریخِ اجرا اعلامیه نیست.

**تخفیف و عاملِ افزاینده یک جدول‌اند** (`pricing_factors` با ستونِ `kind`): شکلشان
یکی است و تنها فرقشان جهتِ اثر. دو جدولِ آینه‌ای یعنی دو مسیرِ محاسبه که بی‌سروصدا
از هم جدا می‌افتند.

**بستنِ فاکتور** دو ستون روی `sales_invoices` است، نه جدولِ وضعیت — همان الگویی که
`finalized_at` برای سند دارد. فاکتورِ بسته دیگر ویرایش و ابطال نمی‌شود.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0086"
down_revision: Union[str, None] = "0085"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)

#: جدول‌های تازه — همه مستأجرمحور، همه با RLS اجباری.
NEW_TABLES = (
    "sale_types",
    "discount_item_groups",
    "discount_item_group_members",
    "pricing_factors",
    "product_bundles",
    "product_bundle_lines",
    "commission_rules",
    "commission_runs",
    "commission_run_lines",
    "customs_declarations",
    "credit_debit_notes",
)


def _tenant_col():
    return sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)


def _stamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def upgrade() -> None:
    conn = op.get_bind()

    # ── نوعِ فروش ────────────────────────────────────────────────────────────
    op.create_table(
        "sale_types",
        sa.Column("id", UUID, primary_key=True),
        _tenant_col(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("due_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("default_tax_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        *_stamps(),
        sa.UniqueConstraint("tenant_id", "name", name="uq_sale_types_tenant_name"),
    )

    # ── گروهِ کالای تخفیف ────────────────────────────────────────────────────
    op.create_table(
        "discount_item_groups",
        sa.Column("id", UUID, primary_key=True),
        _tenant_col(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        *_stamps(),
        sa.UniqueConstraint("tenant_id", "name", name="uq_discount_item_groups_tenant_name"),
    )
    op.create_table(
        "discount_item_group_members",
        sa.Column("id", UUID, primary_key=True),
        _tenant_col(),
        sa.Column(
            "group_id", UUID, sa.ForeignKey("discount_item_groups.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("item_id", UUID, sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("tenant_id", "group_id", "item_id", name="uq_discount_group_member"),
    )
    op.create_index("ix_discount_group_members_group", "discount_item_group_members", ["group_id"])

    # ── تخفیف و عاملِ افزاینده (یک جدول) ─────────────────────────────────────
    op.create_table(
        "pricing_factors",
        sa.Column("id", UUID, primary_key=True),
        _tenant_col(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False, server_default="percent"),
        sa.Column("value", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("scope", sa.String(10), nullable=False, server_default="all"),
        sa.Column("item_id", UUID, sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=True),
        sa.Column(
            "group_id", UUID, sa.ForeignKey("discount_item_groups.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        *_stamps(),
        sa.CheckConstraint("kind IN ('discount', 'markup')", name="ck_pricing_factors_kind"),
        sa.CheckConstraint("mode IN ('percent', 'amount')", name="ck_pricing_factors_mode"),
        sa.CheckConstraint("scope IN ('all', 'item', 'group')", name="ck_pricing_factors_scope"),
        sa.CheckConstraint("value >= 0", name="ck_pricing_factors_value_nonneg"),
    )
    op.create_index("ix_pricing_factors_kind", "pricing_factors", ["tenant_id", "kind"])

    # ── بسته‌ی محصول ─────────────────────────────────────────────────────────
    op.create_table(
        "product_bundles",
        sa.Column("id", UUID, primary_key=True),
        _tenant_col(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("bundle_price", sa.Numeric(18, 0), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        *_stamps(),
        sa.UniqueConstraint("tenant_id", "name", name="uq_product_bundles_tenant_name"),
    )
    op.create_table(
        "product_bundle_lines",
        sa.Column("id", UUID, primary_key=True),
        _tenant_col(),
        sa.Column("bundle_id", UUID, sa.ForeignKey("product_bundles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", UUID, sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False, server_default="1"),
        sa.UniqueConstraint("tenant_id", "bundle_id", "item_id", name="uq_product_bundle_line_item"),
        sa.CheckConstraint("qty > 0", name="ck_product_bundle_lines_qty_positive"),
    )
    op.create_index("ix_product_bundle_lines_bundle", "product_bundle_lines", ["bundle_id"])

    # ── پورسانت ──────────────────────────────────────────────────────────────
    op.create_table(
        "commission_rules",
        sa.Column("id", UUID, primary_key=True),
        _tenant_col(),
        sa.Column("salesperson_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("basis", sa.String(10), nullable=False, server_default="net"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        *_stamps(),
        sa.CheckConstraint("basis IN ('net', 'profit')", name="ck_commission_rules_basis"),
        sa.CheckConstraint("rate >= 0 AND rate <= 100", name="ck_commission_rules_rate_range"),
        # هر فروشنده یک قاعده. دو قاعده یعنی محاسبه باید بینشان انتخاب کند و
        # هر انتخابی دلبخواه است.
        sa.UniqueConstraint("tenant_id", "salesperson_id", name="uq_commission_rules_tenant_person"),
    )
    op.create_index("ix_commission_rules_person", "commission_rules", ["salesperson_id"])

    op.create_table(
        "commission_runs",
        sa.Column("id", UUID, primary_key=True),
        _tenant_col(),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        *_stamps(),
    )
    op.create_table(
        "commission_run_lines",
        sa.Column("id", UUID, primary_key=True),
        _tenant_col(),
        sa.Column("run_id", UUID, sa.ForeignKey("commission_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("salesperson_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invoice_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("base_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("basis", sa.String(10), nullable=False, server_default="net"),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )
    op.create_index("ix_commission_run_lines_run", "commission_run_lines", ["run_id"])

    # ── اظهارنامه‌ی گمرکی ────────────────────────────────────────────────────
    op.create_table(
        "customs_declarations",
        sa.Column("id", UUID, primary_key=True),
        _tenant_col(),
        sa.Column("declaration_no", sa.String(40), nullable=False),
        sa.Column("declaration_date", sa.Date(), nullable=False),
        sa.Column("customs_office", sa.String(120), nullable=False, server_default=""),
        sa.Column("hs_code", sa.String(20), nullable=False, server_default=""),
        sa.Column("destination_country", sa.String(80), nullable=False, server_default=""),
        sa.Column("declared_value", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="IRR"),
        sa.Column(
            "invoice_id", UUID, sa.ForeignKey("sales_invoices.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        *_stamps(),
        sa.UniqueConstraint("tenant_id", "declaration_no", name="uq_customs_declarations_tenant_no"),
    )
    op.create_index("ix_customs_declarations_invoice", "customs_declarations", ["invoice_id"])

    # ── اعلامیه‌ی بدهکار/بستانکار ────────────────────────────────────────────
    op.create_table(
        "credit_debit_notes",
        sa.Column("id", UUID, primary_key=True),
        _tenant_col(),
        sa.Column("number", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("note_date", sa.Date(), nullable=False),
        sa.Column("contact_id", UUID, sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "invoice_id", UUID, sa.ForeignKey("sales_invoices.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("journal_entry_id", UUID, sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        *_stamps(),
        sa.CheckConstraint("kind IN ('debit', 'credit')", name="ck_credit_debit_notes_kind"),
        sa.CheckConstraint("amount > 0", name="ck_credit_debit_notes_amount_positive"),
        sa.UniqueConstraint("tenant_id", "number", name="uq_credit_debit_notes_tenant_number"),
    )
    op.create_index("ix_credit_debit_notes_contact", "credit_debit_notes", ["tenant_id", "contact_id"])
    op.create_index("ix_credit_debit_notes_kind", "credit_debit_notes", ["kind"])
    op.create_index("ix_credit_debit_notes_number", "credit_debit_notes", ["number"])

    # ── ایندکسِ مستأجر + RLS برای همه ────────────────────────────────────────
    for table in NEW_TABLES:
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
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

    # ── اعلامیه‌ی قیمت: تاریخِ اجرا روی جدولِ *موجود* ────────────────────────
    op.add_column(
        "price_lists",
        sa.Column("effective_from", sa.Date(), nullable=False, server_default=sa.func.current_date()),
    )

    # ── فاکتور فروش: بستن، فروشنده، نوعِ فروش ────────────────────────────────
    op.add_column("sales_invoices", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "sales_invoices", sa.Column("closed_by_id", UUID, sa.ForeignKey("users.id"), nullable=True)
    )
    op.add_column(
        "sales_invoices", sa.Column("salesperson_id", UUID, sa.ForeignKey("users.id"), nullable=True)
    )
    op.add_column(
        "sales_invoices",
        sa.Column("sale_type_id", UUID, sa.ForeignKey("sale_types.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_sales_invoices_closed_at", "sales_invoices", ["closed_at"])
    op.create_index("ix_sales_invoices_salesperson", "sales_invoices", ["salesperson_id"])

    # ── شمارنده‌ی اعلامیه برای مستأجرهای موجود ───────────────────────────────
    # provisioningِ تازه خودش می‌سازد؛ مستأجرِ قدیمی این ردیف را ندارد و اولین
    # اعلامیه با ۵۰۰ شکست می‌خورد — همان گاردِ عمدیِ next_document_number.
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(
            sa.text(
                "INSERT INTO document_counters (id, tenant_id, doc_type, last_number, created_at, updated_at) "
                "SELECT gen_random_uuid(), t.id, 'credit_debit_note', 0, now(), now() FROM tenants t "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM document_counters dc "
                "   WHERE dc.tenant_id = t.id AND dc.doc_type = 'credit_debit_note')"
            )
        )


def downgrade() -> None:
    op.drop_index("ix_sales_invoices_salesperson", table_name="sales_invoices")
    op.drop_index("ix_sales_invoices_closed_at", table_name="sales_invoices")
    for col in ("sale_type_id", "salesperson_id", "closed_by_id", "closed_at"):
        op.drop_column("sales_invoices", col)
    op.drop_column("price_lists", "effective_from")
    # ترتیبِ معکوس: فرزندها پیش از والدها.
    for table in reversed(NEW_TABLES):
        op.drop_table(table)
    op.execute("DELETE FROM document_counters WHERE doc_type = 'credit_debit_note'")
