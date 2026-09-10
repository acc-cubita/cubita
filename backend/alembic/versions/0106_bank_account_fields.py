"""حساب بانکی: تفصیلی، ارز، بلوکه و بقیه‌ی داده‌های پایه.

`bank_accounts` از مهاجرتِ ۰۰۰۳ ساخته شد و **از آن روز هیچ ALTERی نخورده**. شش
ستون داشت و از پانزده مفهومِ فصلِ «تعریف و مدیریت حساب بانکی» سه‌تا را پوشش
می‌داد.

**مهم‌ترینش `analytic_id` است.** تا امروز همه‌ی حساب‌های بانکی روی همان معینِ
«بانک» می‌نشستند و هیچ بُعدی برای تفکیکشان نبود — یعنی مانده‌ی «بانک سامان» در
برابر «بانک ملت» *قابلِ محاسبه نبود*. با این ستون، جفتِ
`(gl_account_id, analytic_id)` هویتِ حسابداریِ حساب می‌شود: همان جفتی که سمتِ
نوشتن روی ردیفِ سند می‌گذارد و سمتِ خواندن مانده را از آن درمی‌آورد.

**`NULL` معنا دارد، پس backfill لازم نیست.** ردیف‌های موجودِ دفتر همه
`analytic_id IS NULL` دارند؛ یعنی حسابِ بی‌تفصیلی دقیقاً همان گردشِ امروز را
می‌خواند. سرویس تضمین می‌کند فقط *یک* حساب بی‌تفصیلی بماند، وگرنه دو حساب یک
مانده می‌خواندند.

**هیچ `INSERT/UPDATE`ای اینجا نیست** — قاعده‌ی RLS پروژه: نوشتن در جدولِ RLS‌دار
داخلِ مهاجرت یا صفر ردیف می‌نشاند یا روی مستأجرِ اشتباه. همه‌ی ستون‌ها
`server_default` دارند، پس ردیف‌های موجود بدونِ هیچ نوشتنی معتبر می‌مانند.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0106"
down_revision = "0105"
branch_labels = None
depends_on = None

TABLE = "bank_accounts"

#: (نام، نوع، پیش‌فرضِ سمتِ سرور) — همه غیرِ NULL جز آن‌هایی که پایین‌تر جدا آمده‌اند.
TEXT_COLUMNS = [
    ("name2", sa.String(200), ""),
    ("branch_name", sa.String(100), ""),
    ("account_type", sa.String(50), ""),
    ("card_number", sa.String(30), ""),
    ("holder_name", sa.String(200), ""),
    ("holder_name2", sa.String(200), ""),
    ("cheque_print_format", sa.String(50), ""),
]


def upgrade() -> None:
    for name, kind, default in TEXT_COLUMNS:
        op.add_column(TABLE, sa.Column(name, kind, server_default=default, nullable=False))

    #: nullable عمدی — NULL یعنی «تفکیک‌نشده»، و همان ردیف‌های امروزِ دفتر است.
    op.add_column(
        TABLE,
        sa.Column(
            "analytic_id",
            UUID(as_uuid=True),
            sa.ForeignKey("analytic_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        TABLE, sa.Column("currency_code", sa.String(3), server_default="IRR", nullable=False)
    )
    #: تاریخِ افتتاح داده‌ی کسب‌وکار است و برای حساب‌های موجود نامعلوم — پس NULL،
    #: که گاردِ «عملیات پیش از افتتاح» را هم خاموش نگه می‌دارد.
    op.add_column(TABLE, sa.Column("opening_date", sa.Date(), nullable=True))
    op.add_column(
        TABLE, sa.Column("blocked_amount", sa.Numeric(18, 0), server_default="0", nullable=False)
    )


def downgrade() -> None:
    for name in ("blocked_amount", "opening_date", "currency_code", "analytic_id"):
        op.drop_column(TABLE, name)
    for name, _kind, _default in reversed(TEXT_COLUMNS):
        op.drop_column(TABLE, name)
