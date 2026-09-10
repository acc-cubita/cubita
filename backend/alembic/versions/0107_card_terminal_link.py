"""کارت‌خوان: شماره‌ی پایانه، ارز، و کلیدِ خارجیِ گم‌شده روی تراکنش.

`pos_terminals` از مهاجرتِ ۰۰۶۴ هست و دستگاه را با `bank_account_id` به بانک وصل
می‌کند — ولی **هیچ‌وقت به تراکنش‌های خودش وصل نبود**. تنها ردِ دستگاه روی رسید،
ستونِ متنیِ `terminal_no` بود که در تسویه دستی تایپ می‌شد و با `==` مقایسه؛ یک
فاصله‌ی اضافی یعنی صفر نتیجه بدونِ هیچ خطایی. و طنزِ ماجرا اینکه خودِ
`pos_terminals` ستونِ `terminal_no` **نداشت**، پس دستگاهِ تعریف‌شده نمی‌دانست
دستگاهِ واقعی چه شماره‌ای گزارش می‌کند.

این مهاجرت هر دو سر را می‌بندد: شماره روی دستگاه می‌نشیند، و
`treasury_transactions.pos_terminal_id` حلقه‌ی واقعی را می‌سازد.

**`analytic_id` عمداً اضافه نمی‌شود.** تفصیلیِ کارت‌خوان (§۱۰ §۱۱) فقط وقتی معنا
دارد که رسیدِ کارتی روی یک حسابِ واسط بنشیند (§۲۸)، چون `journal_lines` تنها یک
`analytic_id` دارد و آن را از مهاجرتِ ۰۱۰۶ حسابِ بانکی گرفته. آن دو یک تصمیم‌اند
و در `OPEN_DECISIONS` ثبت شده‌اند.

**هیچ `INSERT/UPDATE`ای اینجا نیست.** ستون‌ها `server_default` دارند و
`pos_terminal_id` عمداً nullable است: `NULL` یعنی «رسیدِ پیش از این مهاجرت»، که
همان حقیقت است — نمی‌شود با حدس به دستگاهی نسبتش داد.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0107"
down_revision = "0106"
branch_labels = None
depends_on = None

TERMINALS = "pos_terminals"
TRANSACTIONS = "treasury_transactions"
UNIQUE_INDEX = "uq_pos_terminals_tenant_terminal_no"


def upgrade() -> None:
    op.add_column(TERMINALS, sa.Column("name2", sa.String(120), server_default="", nullable=False))
    op.add_column(
        TERMINALS, sa.Column("terminal_no", sa.String(30), server_default="", nullable=False)
    )
    op.add_column(
        TERMINALS, sa.Column("currency_code", sa.String(3), server_default="IRR", nullable=False)
    )

    #: یکتا **فقط وقتی پر شده**. دستگاه‌های موجود شماره ندارند و همه رشته‌ی خالی
    #: می‌گیرند؛ بدونِ شرطِ جزئی، دومین دستگاه بلافاصله قید را می‌شکست.
    op.create_index(
        UNIQUE_INDEX,
        TERMINALS,
        ["tenant_id", "terminal_no"],
        unique=True,
        postgresql_where=sa.text("terminal_no <> ''"),
    )

    op.add_column(
        TRANSACTIONS,
        sa.Column(
            "pos_terminal_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pos_terminals.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(TRANSACTIONS, "pos_terminal_id")
    op.drop_index(UNIQUE_INDEX, table_name=TERMINALS)
    for name in ("currency_code", "terminal_no", "name2"):
        op.drop_column(TERMINALS, name)
