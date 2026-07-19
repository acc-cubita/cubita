"""accounts.system_role: منطق ثبت را از کد حساب جدا می‌کند

Revision ID: 0016
Revises: 0015

کد حساب متعلق به مشتری است و بازشماره‌گذاری‌اش کار رایج حسابداران است. تا امروز
`get_account` با رشته‌ی کد (`"1101"`) جست‌وجو می‌کرد، پس اولین مشتری‌ای که چارتش را
مرتب می‌کرد، همه‌ی ثبت‌های خودکارش می‌شکست — و آن شکست هم در لحظه‌ی ثبت فاکتور
رخ می‌داد، نه در لحظه‌ی تغییر کد.

backfill از روی کدهای پیش‌فرض انجام می‌شود، که برای هر داده‌ی موجود درست است چون
همه‌ی مستأجرهای فعلی از همان چارت پیش‌فرض provision شده‌اند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.migration_utils import rls_disabled

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# عمداً اینجا تکرار شده و از app.services.chart_codes وارد نمی‌شود: مهاجرت باید
# همان نگاشتی را اعمال کند که در لحظه‌ی نوشتنش درست بوده، نه نگاشتی که کد فردا دارد.
ROLE_BY_CODE = {
    "1101": "cash",
    "1102": "bank",
    "1103": "petty_cash",
    "1104": "accounts_receivable",
    "1105": "inventory",
    "1106": "checks_receivable",
    "2101": "accounts_payable",
    "2102": "checks_payable",
    "2103": "insurance_tax_payable",
    "2104": "payroll_payable",
    "3102": "retained_earnings",
    "4101": "sales_revenue",
    "5101": "cogs",
    "5102": "payroll_expense",
    "5105": "inventory_adjustment",
}


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column("accounts", sa.Column("system_role", sa.String(40), nullable=True))
    op.create_index("ix_accounts_system_role", "accounts", ["system_role"])

    # بدون این، UPDATE زیر صفر ردیف را عوض می‌کند و مهاجرت با موفقیت گزارش می‌دهد:
    # مهاجرت زمینه‌ی مستأجر ندارد و سیاست RLS همه‌ی ردیف‌ها را از دیدش پنهان می‌کند.
    with rls_disabled(conn, ["accounts"]):
        total_accounts = conn.execute(sa.text("SELECT count(*) FROM accounts")).scalar()
        updated = 0
        for code, role in ROLE_BY_CODE.items():
            updated += conn.execute(
                sa.text("UPDATE accounts SET system_role = :r WHERE code = :c AND system_role IS NULL"),
                {"r": role, "c": code},
            ).rowcount

        # گارد در برابر همان حالتی که یک‌بار رخ داد: مهاجرت موفق، صفر ردیف عوض‌شده.
        # روی دیتابیس خالی چیزی برای علامت‌گذاری نیست و این درست است؛ ولی اگر حساب
        # وجود دارد و هیچ‌کدام علامت نخوردند، یعنی چیزی جلوی دید مهاجرت را گرفته.
        if total_accounts and not updated:
            raise RuntimeError(
                f"backfill هیچ ردیفی را علامت نزد در حالی که {total_accounts} حساب وجود دارد — "
                "احتمالاً مهاجرت ردیف‌ها را نمی‌بیند (RLS؟)"
            )

    # یک نقش، یک حساب، در هر کسب‌وکار. NULL از قید یکتا معاف است، پس حساب‌های
    # معمولی و سرفصل‌ها آزادند.
    op.create_unique_constraint(
        "uq_accounts_tenant_system_role", "accounts", ["tenant_id", "system_role"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_accounts_tenant_system_role", "accounts", type_="unique")
    op.drop_index("ix_accounts_system_role", table_name="accounts")
    op.drop_column("accounts", "system_role")
