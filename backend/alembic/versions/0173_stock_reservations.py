"""رزروِ موجودی — دفترِ علامت‌دار، نه پرچمِ وضعیت

Revision ID: 0173
Revises: 0172

## چه چیزی اضافه می‌شود

جدولِ مستأجرمحورِ `stock_reservations`: ادعایی روی موجودی که هنوز از انبار
بیرون نرفته. تا امروز کوبیتا **هیچ مفهومی از رزرو نداشت** — موجودی فقط لحظه‌ی
ثبتِ خروج سنجیده می‌شد.

## چرا ردیفِ علامت‌دار و نه ستونِ وضعیت

لغوِ **جزئیِ** سفارش (§۱۰) با یک ستونِ `status` بیان نمی‌شود: یا باید `qty` را
بازنویسی کنی و تاریخچه را ببلعی، یا ردیفِ تازه بنویسی. همان راهی که
`stock_ledger` و `serial_events` رفته‌اند:

    qty > 0  →  رزرو
    qty < 0  →  آزادسازی یا مصرف
    رزروِ جاری = SUM(qty)

«تمام Reservationها باید Traceable باشند» (§۱۰) این‌طور **ذاتی** می‌شود، نه
افزودنی: هیچ ردیفی پاک یا بازنویسی نمی‌شود.

## چرا کالامحور، با `batch_id`ِ تهی‌پذیر

§۷ می‌گوید مشتری لازم نیست بار را انتخاب کند — و رزروِ بدونِ بار **دقیقاً همان
حالت است**. بعداً FEFO با یک ردیفِ آزادسازی و یک ردیفِ رزروِ بار‌دار بار را
می‌چسباند، و همان دو ردیف خودشان ردِ ممیزیِ جایگزینیِ §۱۳‌اند.

    available(کالا) = موجودی − Σ رزروها
    available(بار)  = موجودیِ بار − Σ رزروهای همان بار

دو فرمول از یک جدول.

## `event` در کلیدِ یکتا — و چرا بدونش کار نمی‌کرد

طرحِ اولیه ایندکسِ یکتا را روی `(سند، ردیف)` گذاشته بود، به تقلید از
`uq_serial_events_serial_source`. ولی آن‌جا هر سند فقط **یک** رویداد می‌سازد،
و این‌جا یک سفارش اول رزرو می‌کند و بعد آزاد یا مصرف می‌کند. بی `event` در
کلید، ردیفِ آزادسازی با ردیفِ رزروِ خودش برخورد می‌کرد و لغوِ سفارش شکست
می‌خورد — یعنی قید دقیقاً همان چیزی را می‌بست که باید ممکن باشد.

با `event` در کلید، §۳۵.۶ برآورده می‌شود: تلاشِ دوباره‌ی شبکه رزروِ دوم
نمی‌سازد، ولی چرخه‌ی طبیعیِ رزرو→آزادسازی باز می‌ماند.

شرطِ جزئیِ `source_id IS NOT NULL` لازم است تا انسدادِ **دستی** (که سندی ندارد)
بتواند چند بار تکرار شود.

## چرا `rls_disabled` این‌جا لازم نیست

جدول **تازه** است و هیچ ردیفی ندارد؛ اسکنِ اعتبارسنجیِ کلیدِ خارجی روی جدولِ
خالی اصلاً اجرا نمی‌شود. `_enable_rls` بعد از ساخت اعمال می‌شود، مثلِ هر جدولِ
مستأجرمحورِ دیگر.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.tenancy import policy_name

revision: str = "0173"
down_revision: Union[str, None] = "0172"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RESERVATION_KINDS = ("order", "hold", "blocked")
RESERVATION_EVENTS = ("reserve", "release", "consume")


def _enable_rls(table: str) -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
    conn.execute(sa.text(
        f"CREATE POLICY {policy_name(table)} ON {table} "
        "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
    ))


def upgrade() -> None:
    op.create_table(
        "stock_reservations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False, index=True),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False, index=True),
        #: تهی = «رزرو هست، بارش هنوز انتخاب نشده» — حالتِ صریحِ §۷.
        sa.Column(
            "batch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stock_batches.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("kind", sa.String(20), server_default="order", nullable=False),
        sa.Column("event", sa.String(20), server_default="reserve", nullable=False),
        sa.Column("source_type", sa.String(50), server_default="", nullable=False),
        #: بی کلیدِ خارجی و عمداً: ممکن است به ردیفی در جدولِ **سراسریِ** بازار
        #: اشاره کند (سفارشِ پخش)، و FKِ مستأجری→سراسری معنا ندارد.
        sa.Column("source_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_line_id", UUID(as_uuid=True), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        #: ردیفِ صفر یعنی ادعایی که هیچ نمی‌گوید — فقط نویز در دفتر.
        sa.CheckConstraint("qty <> 0", name="ck_stock_reservations_qty"),
        sa.CheckConstraint(f"kind IN {RESERVATION_KINDS}", name="ck_stock_reservations_kind"),
        sa.CheckConstraint(f"event IN {RESERVATION_EVENTS}", name="ck_stock_reservations_event"),
    )
    _enable_rls("stock_reservations")

    #: تکرارناپذیریِ **اعلانی**: تلاشِ دوباره‌ی شبکه رزروِ دوم نمی‌سازد.
    #:
    #: فقط روی `event = 'reserve'`. اگر همه‌ی رویدادها را می‌بست، لغوِ جزئیِ دومِ
    #: همان سند با ردیفِ لغوِ اول برخورد می‌کرد — یعنی قید دقیقاً همان چیزی را
    #: می‌بست که §۱۰ خواسته ممکن باشد. آزادسازیِ تکراری بی‌خطر است چون سرویس آن
    #: را به مانده‌ی باز محدود می‌کند.
    #:
    #: `COALESCE` هم لازم است و تزئینی نیست: در Postgres دو `NULL` در ایندکسِ
    #: یکتا با هم برابر شمرده نمی‌شوند. `batch_id` و `source_line_id` هر دو
    #: معمولاً تهی‌اند — یعنی بی این، قید روی حالتِ رایج اصلاً نمی‌بست و رزروِ
    #: تکراری بی‌صدا ثبت می‌شد. همان درسی که `uq_price_list_items_context` داده.
    #:
    #: (`NULLS NOT DISTINCT` از PG15 هست، ولی تولید روی **۱۴** است.)
    op.create_index(
        "uq_stock_reservations_source",
        "stock_reservations",
        [
            "tenant_id", "item_id", "warehouse_id",
            sa.text("COALESCE(batch_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            "source_type", "source_id",
            sa.text("COALESCE(source_line_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
        ],
        unique=True,
        postgresql_where=sa.text("source_id IS NOT NULL AND event = 'reserve'"),
    )
    #: پرسشِ همیشگی: «چه‌قدر از این کالا در این انبار رزرو است؟»
    op.create_index(
        "ix_stock_reservations_item",
        "stock_reservations",
        ["tenant_id", "item_id", "warehouse_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_stock_reservations_item", table_name="stock_reservations")
    op.drop_index("uq_stock_reservations_source", table_name="stock_reservations")
    op.drop_table("stock_reservations")
