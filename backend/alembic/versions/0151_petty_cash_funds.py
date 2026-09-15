"""صندوقِ تنخواه به‌عنوان موجودیت — و استردادِ مانده که هیچ مسیری نداشت.

تا امروز تنخواه یک جدولِ تراکنشِ تخت بود با دو نوع (`charge`, `expense`) و
docstringش می‌گفت «یک صندوق تنخواه واحد». یعنی:

* **تنخواه‌دار جایی ثبت نمی‌شد.** عوض‌شدنش هیچ ردی نداشت چون صندوقی به‌عنوان
  موجودیت وجود نداشت که تاریخچه‌ای داشته باشد.
* **استردادِ ماندهٔ تنخواه هیچ نوعی نداشت.** تنخواه‌داری که می‌رفت، پولِ
  دستش را نمی‌توانست برگرداند مگر با یک «هزینه»ی جعلی.
* هیچ سقفی، هیچ وضعیتی، و هیچ پیوندی به مدرک.

## چه می‌سازد

* `petty_cash_funds`: نام، تنخواه‌دار (طرف حساب)، محل، سقف، وضعیت.
* `petty_cash_transactions.fund_id`: هر تراکنش به صندوقش.
* `petty_cash_transactions.evidence_ref`: شماره‌ی مدرکِ پشتوانه (قاعده ۶۵).
* نوعِ سومِ تراکنش: `return_balance`.

## Backfill — و چرا `rls_disabled` این‌جا **اجباری** است

برای هر مستأجری که تراکنشِ تنخواه دارد یک صندوقِ «تنخواه‌گردان» ساخته می‌شود و
تراکنش‌هایش به آن وصل. این کار هم `SELECT` روی `petty_cash_transactions` می‌خواهد
و هم `UPDATE` — و هر دو روی جدولی که `FORCE ROW LEVEL SECURITY` دارد **بی‌صدا صفر
ردیف** می‌بینند، چون مهاجرت هیچ `app.tenant_id`ی ست نکرده. بدونِ `rls_disabled`
این مهاجرت موفق گزارش می‌شد و هیچ تراکنشی صندوق نمی‌گرفت.

`fund_id` عمداً **تهی‌پذیر** می‌ماند: اجباری‌کردنش یعنی هر ردیفِ قدیمی باید
درست backfill شده باشد وگرنه مهاجرت وسطِ کار می‌افتد و کدِ قدیمی با اسکیمای تازه
می‌ماند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0151"
down_revision: Union[str, None] = "0150"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "petty_cash_funds"


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
    op.create_table(
        _TABLE,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        #: تنخواه‌دار **طرف حساب** است نه کاربر: ممکن است اصلاً حسابِ ورود نداشته
        #: باشد. تهی‌پذیر، چون صندوقِ backfill‌شده تنخواه‌دارِ ثبت‌شده‌ای ندارد.
        sa.Column("custodian_contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("location", sa.String(length=160), nullable=False, server_default=""),
        #: ۰ = بی‌سقف. سقف هشدار است نه گارد — «گزارش، نه گارد».
        sa.Column("spending_limit", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_petty_cash_funds_tenant_name"),
    )
    _enable_rls(_TABLE)

    op.add_column(
        "petty_cash_transactions",
        sa.Column("fund_id", UUID(as_uuid=True), sa.ForeignKey(f"{_TABLE}.id"), nullable=True),
    )
    op.create_index("ix_petty_cash_transactions_fund_id", "petty_cash_transactions", ["fund_id"])
    op.add_column(
        "petty_cash_transactions",
        sa.Column("evidence_ref", sa.String(length=120), nullable=False, server_default=""),
    )

    #: نوعِ سوم. قیدِ قبلی فقط charge/expense را می‌پذیرفت، پس بدونِ بازسازی‌اش
    #: اولین استرداد با خطای قید رد می‌شد.
    op.drop_constraint("ck_petty_cash_type", "petty_cash_transactions", type_="check")
    op.create_check_constraint(
        "ck_petty_cash_type",
        "petty_cash_transactions",
        "type IN ('charge', 'expense', 'return_balance')",
    )

    conn = op.get_bind()
    #: **هر دو جدول لازم‌اند:** خواندنِ تراکنش‌ها برای یافتنِ مستأجرها، و نوشتنِ
    #: صندوق. بدونِ `petty_cash_funds` در این فهرست، `INSERT` با سیاستِ
    #: `WITH CHECK` رد می‌شد چون زمینه‌ی مستأجری وجود ندارد.
    with rls_disabled(conn, (_TABLE, "petty_cash_transactions")):
        tenants = conn.execute(
            sa.text("SELECT DISTINCT tenant_id FROM petty_cash_transactions")
        ).scalars().all()
        for tenant_id in tenants:
            fund_id = conn.execute(
                sa.text(
                    f"INSERT INTO {_TABLE} (id, tenant_id, name, location, spending_limit, is_active, notes) "
                    "VALUES (gen_random_uuid(), :t, :n, '', 0, true, :notes) RETURNING id"
                ),
                {
                    "t": tenant_id,
                    "n": "تنخواه‌گردان",
                    "notes": "صندوقِ پیش‌فرض — تراکنش‌های پیش از مهاجرتِ ۰۱۵۱ به این صندوق نسبت داده شدند.",
                },
            ).scalar_one()
            conn.execute(
                sa.text(
                    "UPDATE petty_cash_transactions SET fund_id = :f "
                    "WHERE tenant_id = :t AND fund_id IS NULL"
                ),
                {"f": fund_id, "t": tenant_id},
            )


def downgrade() -> None:
    op.drop_constraint("ck_petty_cash_type", "petty_cash_transactions", type_="check")
    op.create_check_constraint(
        "ck_petty_cash_type", "petty_cash_transactions", "type IN ('charge', 'expense')"
    )
    op.drop_column("petty_cash_transactions", "evidence_ref")
    op.drop_index("ix_petty_cash_transactions_fund_id", table_name="petty_cash_transactions")
    op.drop_column("petty_cash_transactions", "fund_id")
    op.drop_table(_TABLE)
