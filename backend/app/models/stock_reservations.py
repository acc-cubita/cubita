"""رزروِ موجودی — ادعایی روی کالایی که هنوز از انبار بیرون نرفته.

تا مهاجرتِ ۰۱۷۳ چنین چیزی در کوبیتا وجود نداشت: موجودی فقط **لحظه‌ی ثبتِ خروج**
سنجیده می‌شد. یعنی دو سفارشِ هم‌زمان می‌توانستند هر دو پذیرفته شوند و دومی روزِ
تحویل شکست بخورد.

## دفتر است، نه پرچم

`qty` علامت‌دار است و رزروِ جاری `SUM(qty)`. لغوِ **جزئیِ** سفارش (§۱۰) با ستونِ
`status` بیان نمی‌شد — یا باید `qty` بازنویسی می‌شد (و تاریخچه می‌رفت) یا ردیفِ
تازه نوشته می‌شد. همان انتخابی که `StockLedger` و `SerialEvent` کرده‌اند.

    reserve  +۱۵۰   سفارش ثبت شد
    release   −۵۰   نیمی لغو شد
    consume  −۱۰۰   بقیه بار زده شد
    ──────────────
    جاری        ۰

## چرا `batch_id` تهی‌پذیر است

§۷ می‌گوید مشتری لازم نیست بار را انتخاب کند. رزروِ بدونِ بار **همان حالت** است،
نه یک نقص. بعداً که بار مشخص شد، یک ردیفِ آزادسازیِ بی‌بار و یک ردیفِ رزروِ
بار‌دار نوشته می‌شود — و همان جفت، ردِ ممیزیِ جایگزینیِ §۱۳ است.
"""
import uuid
from datetime import date as date_

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

#: نوعِ ادعا — در طولِ چرخه‌ی یک رزرو ثابت می‌ماند.
RESERVATION_KINDS = ("order", "hold", "blocked")
#: چه اتفاقی افتاد. `release` (لغو) و `consume` (بار زده شد) هر دو منفی‌اند ولی
#: یکی نیستند: §۱۵ می‌خواهد «فروخته‌شده» را از «برگشت‌خورده» تفکیک کند.
RESERVATION_EVENTS = ("reserve", "release", "consume")


class StockReservation(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک ردیفِ دفترِ رزرو. هرگز ویرایش یا حذف نمی‌شود."""

    __tablename__ = "stock_reservations"

    __table_args__ = (
        CheckConstraint("qty <> 0", name="ck_stock_reservations_qty"),
        CheckConstraint(f"kind IN {RESERVATION_KINDS}", name="ck_stock_reservations_kind"),
        CheckConstraint(f"event IN {RESERVATION_EVENTS}", name="ck_stock_reservations_event"),
        #: **تکرارناپذیریِ اعلانی (§۳۵.۶).** تلاشِ دوباره‌ی شبکه رزروِ دوم نمی‌سازد.
        #:
        #: **فقط روی `reserve`.** اولین طرح همه‌ی رویدادها را می‌بست و غلط بود:
        #: لغوِ جزئیِ دوم از همان سند با ردیفِ لغوِ اول برخورد می‌کرد و بی‌صدا رد
        #: می‌شد — یعنی قید دقیقاً همان چیزی را می‌بست که §۱۰ خواسته بود ممکن
        #: باشد. رویدادی که تلاشِ دوباره‌ی شبکه تکرارش می‌کند «رزرو» است، نه
        #: «آزادسازی»؛ و آزادسازیِ تکراری هم بی‌خطر است چون `release` به
        #: مانده‌ی باز محدود می‌شود و نمی‌تواند منفی کند.
        #:
        #: `COALESCE` هم لازم است: در Postgres دو `NULL` در ایندکسِ یکتا برابر
        #: شمرده نمی‌شوند، و `batch_id`/`source_line_id` معمولاً تهی‌اند — یعنی
        #: بی آن، قید دقیقاً روی حالتِ رایج نمی‌بست. همان درسِ
        #: `uq_price_list_items_context`. (`NULLS NOT DISTINCT` از PG15 است و
        #: تولید روی ۱۴.)
        Index(
            "uq_stock_reservations_source",
            "tenant_id", "item_id", "warehouse_id",
            text("COALESCE(batch_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            "source_type", "source_id",
            text("COALESCE(source_line_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            unique=True,
            postgresql_where=text("source_id IS NOT NULL AND event = 'reserve'"),
        ),
        Index("ix_stock_reservations_item", "tenant_id", "item_id", "warehouse_id"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), index=True
    )
    #: تهی = «رزرو هست، بارش هنوز انتخاب نشده» (§۷).
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_batches.id", ondelete="RESTRICT"), nullable=True
    )
    #: علامت‌دار: + رزرو، − آزادسازی/مصرف.
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    kind: Mapped[str] = mapped_column(String(20), default="order", server_default="order")
    event: Mapped[str] = mapped_column(String(20), default="reserve", server_default="reserve")
    source_type: Mapped[str] = mapped_column(String(50), default="", server_default="")
    #: بی FK و عمداً: ممکن است به ردیفی در جدولِ **سراسریِ** بازار اشاره کند.
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_line_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    entry_date: Mapped[date_] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
