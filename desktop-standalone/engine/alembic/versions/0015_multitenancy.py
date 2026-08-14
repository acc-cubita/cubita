"""multi-tenancy: tenants, memberships, per-tenant numbering, and row level security

Revision ID: 0015
Revises: 0014

استراتژی expand/migrate/contract در یک مهاجرت، چون داده‌ی موجود همه به یک مستأجر
تعلق دارد و backfill قطعی است:

۱. جدول‌های سراسری جدید (tenants / memberships / platform_admins / document_counters)
۲. یک مستأجر برای همه‌ی داده‌ی موجود ساخته می‌شود
۳. tenant_id به‌صورت nullable اضافه، backfill، سپس NOT NULL
۴. قیدهای یکتای سراسری با نسخه‌ی مرکب جایگزین می‌شوند
۵. مقدار دنباله‌ها به document_counters منتقل می‌شود تا شماره‌ها ادامه پیدا کنند
۶. RLS با FORCE و سیاست ایزوله‌سازی فعال می‌شود

downgrade کامل است ولی مقصدش تک‌مستأجری است: اگر بیش از یک مستأجر ساخته شده باشد
عمداً شکست می‌خورد، چون ادغام داده‌ی چند کسب‌وکار در یک دفتر بازگشت‌ناپذیر و فاجعه‌بار
است و نباید بی‌صدا اتفاق بیفتد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# جدول‌های مستأجرمحور. با app.tenancy.GLOBAL_TABLES هم‌راستاست ولی عمداً اینجا
# تکرار شده: مهاجرت باید همان چیزی را بسازد که در لحظه‌ی نوشتنش درست بوده، نه
# چیزی که مدل‌های امروز می‌گویند — وگرنه مهاجرت قدیمی با کد جدید عوض می‌شود.
TENANT_TABLES = [
    "accounts", "attendance", "bank_accounts", "bank_statement_lines", "bank_transactions",
    "checks", "contacts", "document_counters", "employees", "fiscal_period_closes", "items",
    "journal_entries", "journal_lines", "payroll_periods", "payroll_settings", "payslips",
    "petty_cash_transactions", "purchase_invoice_lines", "purchase_invoices",
    "purchase_return_lines", "purchase_returns", "roles", "salary_contracts",
    "sales_invoice_lines", "sales_invoices", "sales_quotation_lines", "sales_quotations",
    "sales_return_lines", "sales_returns", "stock_adjustments", "stock_ledger",
    "stock_transfer_lines", "stock_transfers", "treasury_transactions", "warehouses",
]

# (جدول، ستون، نام قید فعلی در پایگاه‌داده)
# نام‌ها از خودِ دیتابیس خوانده شده‌اند نه حدس زده: تقریباً همه الگوی <جدول>_<ستون>_key
# را دارند ولی source_order_id استثناست، و حدس زدنش یعنی مهاجرتی که وسط راه می‌شکند.
UNIQUES = [
    ("accounts", "code", "accounts_code_key"),
    ("warehouses", "code", "warehouses_code_key"),
    ("items", "sku", "items_sku_key"),
    ("journal_entries", "number", "journal_entries_number_key"),
    ("sales_invoices", "number", "sales_invoices_number_key"),
    ("sales_invoices", "source_order_id", "uq_sales_invoices_source_order_id"),
    ("purchase_invoices", "number", "purchase_invoices_number_key"),
    ("sales_quotations", "number", "sales_quotations_number_key"),
    ("sales_returns", "number", "sales_returns_number_key"),
    ("purchase_returns", "number", "purchase_returns_number_key"),
    ("stock_transfers", "number", "stock_transfers_number_key"),
    ("payslips", "number", "payslips_number_key"),
    ("employees", "national_id", "employees_national_id_key"),
    ("payroll_settings", "year", "payroll_settings_year_key"),
    ("fiscal_period_closes", "closing_date", "fiscal_period_closes_closing_date_key"),
    ("roles", "key", "roles_key_key"),
]

# قیدهایی که از قبل مرکب بودند و فقط tenant_id به ابتدایشان اضافه می‌شود
COMPOSITE_UNIQUES = [
    ("payroll_periods", "uq_payroll_periods_year_month", ["year", "month"]),
    ("attendance", "uq_attendance_employee_period", ["employee_id", "period_id"]),
    ("payslips", "uq_payslips_employee_period", ["employee_id", "period_id"]),
]

SEQUENCE_TO_DOC = [
    ("journal_entry_number_seq", "journal_entry"),
    ("sales_invoice_number_seq", "sales_invoice"),
    ("purchase_invoice_number_seq", "purchase_invoice"),
    ("payslip_number_seq", "payslip"),
    ("sales_quotation_number_seq", "sales_quotation"),
    ("sales_return_number_seq", "sales_return"),
    ("purchase_return_number_seq", "purchase_return"),
    ("stock_transfer_number_seq", "stock_transfer"),
]

POLICY = "{t}_tenant_isolation"


def upgrade() -> None:
    conn = op.get_bind()

    # --- ۱) جدول‌های سراسری جدید -------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"])

    op.create_table(
        "memberships",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_memberships_user_tenant"),
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_index("ix_memberships_tenant_id", "memberships", ["tenant_id"])

    op.create_table(
        "platform_admins",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # tenant_id عمداً اینجا نیست: حلقه‌ی مشترک پایین آن را برای همه‌ی جدول‌های
    # مستأجرمحور اضافه می‌کند و این جدول هم یکی از آن‌هاست.
    op.create_table(
        "document_counters",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("doc_type", sa.String(40), nullable=False),
        sa.Column("last_number", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- ۲) مستأجر پیش‌فرض برای داده‌ی موجود --------------------------------------
    # فقط اگر اصلاً داده‌ای هست؛ روی دیتابیس خالی مستأجر الکی ساخته نمی‌شود.
    has_data = conn.execute(sa.text("SELECT EXISTS (SELECT 1 FROM accounts)")).scalar()
    tenant_id = None
    if has_data:
        tenant_id = conn.execute(
            sa.text(
                "INSERT INTO tenants (id, name, slug, status) "
                "VALUES (gen_random_uuid(), :n, :s, 'active') RETURNING id"
            ),
            {"n": "کسب‌وکار اصلی", "s": "default"},
        ).scalar()

    # --- ۳) tenant_id: nullable -> backfill -> NOT NULL --------------------------
    for table in TENANT_TABLES:
        op.add_column(table, sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))

    if tenant_id is not None:
        for table in TENANT_TABLES:
            conn.execute(sa.text(f"UPDATE {table} SET tenant_id = :t WHERE tenant_id IS NULL"), {"t": tenant_id})

    for table in TENANT_TABLES:
        # روی جدول خالی هم امن است؛ ردیفی نیست که NULL بماند.
        op.alter_column(table, "tenant_id", nullable=False)
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
        op.create_foreign_key(
            f"fk_{table}_tenant_id", table, "tenants", ["tenant_id"], ["id"], ondelete="CASCADE"
        )

    # --- ۴) قیدهای یکتا: سراسری -> مرکب ------------------------------------------
    for table, col, old_constraint in UNIQUES:
        # ایندکس ix_<جدول>_<ستون> اینجا ساخته نمی‌شود: برای اکثر این ستون‌ها از قبل
        # وجود دارد (index=True روی مدل). برای بقیه، ایندکسِ خودِ قید مرکب که
        # tenant_id ستون پیشروی آن است، جست‌وجوی درون‌مستأجری را پوشش می‌دهد.
        conn.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {old_constraint}"))
        op.create_unique_constraint(f"uq_{table}_tenant_{col}"[:63], table, ["tenant_id", col])

    for table, old_name, cols in COMPOSITE_UNIQUES:
        conn.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {old_name}"))
        name = f"uq_{table}_tenant_{'_'.join(cols)}"[:63]
        op.create_unique_constraint(name, table, ["tenant_id"] + cols)

    op.create_unique_constraint(
        "uq_document_counters_tenant_doc", "document_counters", ["tenant_id", "doc_type"]
    )

    # --- ۴.۵) انتقال نقش کاربران به عضویت ------------------------------------------
    # نقش از users به memberships منتقل می‌شود چون یک نفر می‌تواند در کسب‌وکارهای
    # مختلف نقش‌های مختلف داشته باشد. بدون این backfill، هر کاربر موجود بعد از
    # مهاجرت با ۴۰۳ روبه‌رو می‌شد — یعنی همه از سیستم قفل بیرون می‌ماندند.
    if tenant_id is not None:
        conn.execute(
            sa.text(
                "INSERT INTO memberships (id, user_id, tenant_id, role_id, status) "
                "SELECT gen_random_uuid(), u.id, :t, u.role_id, "
                "       CASE WHEN u.active THEN 'active' ELSE 'disabled' END "
                "  FROM users u WHERE u.role_id IS NOT NULL"
            ),
            {"t": tenant_id},
        )

    op.drop_column("users", "role_id")

    # --- ۵) انتقال مقدار دنباله‌ها به شمارنده‌ها ------------------------------------
    if tenant_id is not None:
        for seq, doc_type in SEQUENCE_TO_DOC:
            exists = conn.execute(
                sa.text("SELECT EXISTS (SELECT 1 FROM pg_class WHERE relkind='S' AND relname=:s)"), {"s": seq}
            ).scalar()
            last = conn.execute(sa.text(f"SELECT last_value, is_called FROM {seq}")).first() if exists else None
            # is_called=false یعنی هنوز nextval نخورده، پس آخرین شماره‌ی مصرف‌شده صفر است
            last_number = (last[0] if last and last[1] else 0) if last else 0
            conn.execute(
                sa.text(
                    "INSERT INTO document_counters (id, tenant_id, doc_type, last_number) "
                    "VALUES (gen_random_uuid(), :t, :d, :n)"
                ),
                {"t": tenant_id, "d": doc_type, "n": last_number},
            )

    for seq, _ in SEQUENCE_TO_DOC:
        conn.execute(sa.text(f"DROP SEQUENCE IF EXISTS {seq}"))

    # --- ۶) RLS ------------------------------------------------------------------
    for table in TENANT_TABLES:
        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        # FORCE اجباری است: بدون آن مالک جدول از سیاست رد می‌شود و اپ همان مالک است
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"DROP POLICY IF EXISTS {POLICY.format(t=table)} ON {table}"))
        conn.execute(
            sa.text(
                f"CREATE POLICY {POLICY.format(t=table)} ON {table} "
                "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
                "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
            )
        )


def downgrade() -> None:
    conn = op.get_bind()

    count = conn.execute(sa.text("SELECT count(*) FROM tenants")).scalar()
    if count and count > 1:
        raise RuntimeError(
            f"downgrade متوقف شد: {count} مستأجر وجود دارد. برگشت به تک‌مستأجری یعنی ادغام "
            "دفاتر چند کسب‌وکار در یک دفتر، که بازگشت‌ناپذیر است. اگر واقعاً قصدتان همین است، "
            "ابتدا دستی به یک مستأجر برسانید."
        )

    for table in TENANT_TABLES:
        conn.execute(sa.text(f"DROP POLICY IF EXISTS {POLICY.format(t=table)} ON {table}"))
        conn.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

    for seq, doc_type in SEQUENCE_TO_DOC:
        last = conn.execute(
            sa.text("SELECT last_number FROM document_counters WHERE doc_type = :d LIMIT 1"), {"d": doc_type}
        ).scalar()
        conn.execute(sa.text(f"CREATE SEQUENCE IF NOT EXISTS {seq} START 1"))
        if last:
            conn.execute(sa.text(f"SELECT setval('{seq}', :n, true)"), {"n": int(last)})

    # نقش را از عضویت به users برمی‌گرداند. اگر کاربری عضو چند مستأجر باشد، یکی
    # انتخاب می‌شود — ولی گارد بالای این تابع از قبل جلوی چندمستأجری بودن را گرفته.
    op.add_column("users", sa.Column("role_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    conn.execute(
        sa.text(
            "UPDATE users u SET role_id = m.role_id "
            "  FROM (SELECT DISTINCT ON (user_id) user_id, role_id FROM memberships ORDER BY user_id) m "
            " WHERE m.user_id = u.id"
        )
    )
    op.create_foreign_key("users_role_id_fkey", "users", "roles", ["role_id"], ["id"])

    for table, old_name, cols in COMPOSITE_UNIQUES:
        name = f"uq_{table}_tenant_{'_'.join(cols)}"[:63]
        conn.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}"))
        op.create_unique_constraint(old_name, table, cols)

    for table, col, cols in UNIQUES:
        name = f"uq_{table}_tenant_{'_'.join(cols)}"[:63]
        conn.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}"))
        conn.execute(sa.text(f"DROP INDEX IF EXISTS ix_{table}_{col}"))
        op.create_index(f"ix_{table}_{col}", table, [col], unique=True)

    for table in TENANT_TABLES:
        conn.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS fk_{table}_tenant_id"))
        conn.execute(sa.text(f"DROP INDEX IF EXISTS ix_{table}_tenant_id"))
        op.drop_column(table, "tenant_id")

    op.drop_table("document_counters")
    op.drop_table("platform_admins")
    op.drop_table("memberships")
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
