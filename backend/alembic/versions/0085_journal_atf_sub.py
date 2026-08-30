"""شماره عطف و شماره فرعیِ سند حسابداری

Revision ID: 0085
Revises: 0084

سندِ حسابداری تا امروز یک شماره داشت، و همان یک شماره دو کارِ ناسازگار می‌کرد:

* دفترداری آخرِ ماه با «شماره‌گذاری مجدد» شماره‌ها را به‌ترتیبِ تاریخ مرتب می‌کند —
  یعنی شماره‌ی سند *متغیر* است.
* ارجاعِ بیرونی به سند (چاپ، پیوستِ پرونده، نامه‌ی حسابرس، ارجاع در سندِ دیگر) به
  شماره‌ای نیاز دارد که هرگز تکان نخورد.

یک ستون نمی‌تواند هر دو باشد. پس:

۱) **شماره عطف** (`atf_number`) — سرور لحظه‌ی ثبت و به‌ترتیبِ ورود می‌دهد و هیچ
   عملیاتی عوضش نمی‌کند. شمارنده‌ی جدا (`journal_atf`) دارد چون ترتیبش با ترتیبِ
   شماره‌ی سند یکی نیست.

۲) **شماره فرعی** (`sub_number`) — ارجاعِ آزادِ کاربر: شماره‌ی سند در سیستمِ قبلی،
   شماره‌ی پرونده، کدِ دسته. متن است نه عدد، یکتا نیست، و اختیاری.

بک‌فیل: سندهای موجود به‌ترتیبِ *ثبت* (`created_at`) عطف می‌گیرند، نه به‌ترتیبِ
شماره — چون همان چیزی که این ستون قرار است نگه دارد ترتیبِ ثبت است، و در دفتری که
یک‌بار بازشماره‌گذاری شده این دو یکی نیستند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.migration_utils import rls_disabled

revision: str = "0085"
down_revision: Union[str, None] = "0084"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column("journal_entries", sa.Column("atf_number", sa.BigInteger(), nullable=True))
    op.add_column("journal_entries", sa.Column("sub_number", sa.String(30), nullable=True))
    op.create_index("ix_journal_entries_atf_number", "journal_entries", ["atf_number"])
    op.create_index("ix_journal_entries_sub_number", "journal_entries", ["sub_number"])

    # بک‌فیلِ عطف برای اسنادِ موجود — به‌ترتیبِ ثبت و جدا برای هر مستأجر.
    # `rls_disabled` لازم است: مهاجرت زمینه‌ی مستأجر ندارد و بدونِ آن این UPDATE
    # بی‌صدا صفر ردیف را عوض می‌کند و مهاجرت موفق گزارش می‌دهد.
    with rls_disabled(conn, ["journal_entries", "document_counters"]):
        conn.execute(
            sa.text(
                """
                WITH ordered AS (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY tenant_id ORDER BY created_at, id
                           ) AS rn
                      FROM journal_entries
                )
                UPDATE journal_entries je
                   SET atf_number = ordered.rn
                  FROM ordered
                 WHERE je.id = ordered.id
                """
            )
        )

        # شمارنده‌ی عطف برای مستأجرهای موجود، نشسته روی بزرگ‌ترین عطفِ بک‌فیل‌شده.
        # مستأجرِ بی‌سند از صفر شروع می‌کند. بدونِ این ردیف، اولین ثبتِ سند ۵۰۰
        # می‌دهد — همان گاردِ عمدیِ `next_document_number`.
        conn.execute(
            sa.text(
                """
                INSERT INTO document_counters
                       (id, tenant_id, doc_type, last_number, created_at, updated_at)
                SELECT gen_random_uuid(), t.id, 'journal_atf',
                       COALESCE(m.mx, 0), now(), now()
                  FROM tenants t
                  LEFT JOIN (
                        SELECT tenant_id, MAX(atf_number) AS mx
                          FROM journal_entries
                         GROUP BY tenant_id
                  ) m ON m.tenant_id = t.id
                 WHERE NOT EXISTS (
                        SELECT 1 FROM document_counters dc
                         WHERE dc.tenant_id = t.id AND dc.doc_type = 'journal_atf'
                 )
                """
            )
        )

    # قیدِ یکتا *بعد* از بک‌فیل: پیش از آن همه‌ی ردیف‌ها NULL‌اند و قید بی‌معنی است.
    op.create_unique_constraint(
        "uq_journal_entries_tenant_atf", "journal_entries", ["tenant_id", "atf_number"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_journal_entries_tenant_atf", "journal_entries", type_="unique")
    op.drop_index("ix_journal_entries_sub_number", table_name="journal_entries")
    op.drop_index("ix_journal_entries_atf_number", table_name="journal_entries")
    op.drop_column("journal_entries", "sub_number")
    op.drop_column("journal_entries", "atf_number")
    op.execute("DELETE FROM document_counters WHERE doc_type = 'journal_atf'")
