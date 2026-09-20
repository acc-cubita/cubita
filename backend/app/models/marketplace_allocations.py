"""تخصیصِ بارِ ورودی به کاتالوگِ بازار (§۶).

بارِ ۱۰۰۰تایی در انبار لزوماً یعنی ۱۰۰۰ تا برای فروشِ عمده نیست. این جدول مرزی
را می‌گذارد که تا امروز وجود نداشت: «از این بار، این‌قدر در کاتالوگ عرضه شود».

## چرا مستأجرمحور است، برخلافِ بقیه‌ی `marketplace_*`

آن‌ها سراسری‌اند چون داده‌شان ذاتاً میان‌مستأجری است — کاتالوگی که مستأجرِ دیگری
می‌بیند. این یکی **موجودی** است: می‌گوید از انبارِ *من* چه‌قدر عرضه می‌شود.
موجودی هرگز سراسری نبوده و نباید بشود. پس `listing_id` بی کلیدِ خارجی می‌ماند،
همان‌طور که `MarketplaceOrder.distributor_sales_invoice_id` از سمتِ مقابل بی‌FK
به دفترِ مستأجر اشاره می‌کند.

## فقط «تخصیص‌داده‌شده» ستون دارد

§۶ سه عدد خواسته، ولی تنها اولی **تصمیم** است:

    allocated  = SUM(qty)                      ← همین ستون
    reserved   = رزروِ سفارش‌های همین لیستینگ    ← از دفترِ رزرو
    remaining  = allocated − reserved           ← تفریق

ستون‌کردنِ آن دو یعنی سه عدد که باید همیشه با هم بخوانند و روزی نمی‌خوانند —
دقیقاً همان چیزی که این مجموعه مهاجرت برای رفعش نوشته شد.
"""
import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class MarketplaceCatalogAllocation(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """«از این بار، این‌قدر در این لیستینگ عرضه می‌شود»."""

    __tablename__ = "marketplace_catalog_allocations"

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_mp_catalog_alloc_qty"),
        #: یک بار در یک لیستینگ فقط یک تخصیص دارد — دو ردیف یعنی دو جواب برای
        #: «چه‌قدر از این بار عرضه شده».
        UniqueConstraint("tenant_id", "listing_id", "batch_id", name="uq_mp_catalog_alloc"),
    )

    #: بی FK و عمداً: به جدولِ **سراسریِ** `marketplace_listings` اشاره می‌کند.
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_batches.id", ondelete="RESTRICT"), index=True
    )
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    #: غیرفعال یعنی «دیگر از این بار عرضه نکن» — بی آنکه تاریخچه پاک شود. §۱۶
    #: فراخوان را هم همین‌طور خاموش می‌کند، بی حذفِ ردیف.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
