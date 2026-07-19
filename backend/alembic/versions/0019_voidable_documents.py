"""ابطال سند: ستون‌های ابطال و پیوند سند معکوس

Revision ID: 0019
Revises: 0018

تا امروز هیچ راهی برای تصحیح فاکتور اشتباه نبود — نه ابطال، نه ویرایش، نه حذف.

ستون‌ها عمداً روی خودِ سند می‌نشینند و نه در یک جدول جداگانه‌ی «ابطال‌ها»: هر
کوئری‌ای که اسناد را می‌خواند باید بتواند بدون join بفهمد کدام باطل است. جدول
جداگانه یعنی اولین گزارشی که join را فراموش کند، اسناد باطل را هم جمع می‌زند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VOIDABLE = ("sales_invoices", "purchase_invoices", "journal_entries")


def upgrade() -> None:
    for table in VOIDABLE:
        op.add_column(table, sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("void_reason", sa.Text(), nullable=False, server_default=""))
        op.add_column(
            table,
            sa.Column("voided_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        )
        # ایندکس روی voided_at: گزارش‌ها اسناد باطل را کنار می‌گذارند، پس این ستون
        # در شرط WHERE بیشتر کوئری‌های مالی ظاهر می‌شود.
        op.create_index(f"ix_{table}_voided_at", table, ["voided_at"])

    op.add_column(
        "journal_entries",
        sa.Column(
            "reverses_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_journal_entries_reverses_entry_id", "journal_entries", ["reverses_entry_id"])

    # ترتیب قطعی برای دفتر موجودی. بدون آن، بازمحاسبه‌ی میانگین موزون ترتیب
    # نداشت — کلید اصلی UUID تصادفی است و entry_date فقط روز را دارد — و همان
    # تابع می‌توانست هر بار عدد متفاوتی بدهد.
    op.execute("CREATE SEQUENCE IF NOT EXISTS stock_ledger_seq")
    op.add_column(
        "stock_ledger",
        sa.Column("seq", sa.BigInteger(), nullable=True, server_default=sa.text("nextval('stock_ledger_seq')")),
    )
    # ردیف‌های موجود شماره می‌گیرند. ترتیبشان از روی تاریخ است و برای ردیف‌های
    # هم‌تاریخ دلخواه — که بهترین چیزی است که از داده‌ی موجود درمی‌آید؛ از این
    # به بعد ترتیب واقعیِ ثبت است.
    op.execute("UPDATE stock_ledger SET seq = nextval('stock_ledger_seq') WHERE seq IS NULL")
    op.alter_column("stock_ledger", "seq", nullable=False)
    # یکتا نیست: SEQUENCE خودش تضمین یکتایی می‌دهد، و ایندکس یکتای سراسری روی
    # جدول مستأجرمحور همان چیزی است که تست انحراف رد می‌کند.
    op.create_index("ix_stock_ledger_seq", "stock_ledger", ["seq"])


def downgrade() -> None:
    op.drop_index("ix_stock_ledger_seq", table_name="stock_ledger")
    op.drop_column("stock_ledger", "seq")
    op.execute("DROP SEQUENCE IF EXISTS stock_ledger_seq")
    op.drop_index("ix_journal_entries_reverses_entry_id", table_name="journal_entries")
    op.drop_column("journal_entries", "reverses_entry_id")
    for table in VOIDABLE:
        op.drop_index(f"ix_{table}_voided_at", table_name=table)
        op.drop_column(table, "voided_by_id")
        op.drop_column(table, "void_reason")
        op.drop_column(table, "voided_at")
