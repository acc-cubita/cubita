"""انبار پیشرفته — لیستِ قیمت و ردیابیِ بچ/تاریخِ انقضا.

سه جدولِ مستأجرمحور (RLS):
  - price_lists: لیست‌های قیمت (عمده، خرده، ویژه، ...).
  - price_list_items: قیمتِ هر کالا در هر لیست (جایگزینِ قیمتِ پایه هنگام فروش/صندوق).
  - stock_batches: ثبتِ بچ/سریِ کالا با تاریخِ انقضا — برای دیده‌بانی و هشدارِ انقضا.

نکته: `stock_batches` یک «دفترِ ثبتِ بچ» است (نه موتورِ مصرفِ بچ‌محور)؛ برای شفافیت و
هشدارِ انقضا کافی است بی‌آنکه موتورِ اصلیِ موجودی بازنویسی شود.
"""
import uuid
from datetime import date as date_

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class PriceList(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک لیستِ قیمت (مثلاً «عمده» یا «خرده»)."""

    __tablename__ = "price_lists"

    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    items: Mapped[list["PriceListItem"]] = relationship(
        back_populates="price_list", cascade="all, delete-orphan"
    )


class PriceListItem(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """قیمتِ یک کالا در یک لیستِ قیمت (هر کالا حداکثر یک قیمت در هر لیست)."""

    __tablename__ = "price_list_items"
    # tenant_id در قید هست تا با گاردِ «ایندکسِ یکتا باید مستأجر داشته باشد» بخواند
    # (price_list خودش مستأجرمحور است، ولی قید باید صراحتاً مستأجر را ببیند).
    __table_args__ = (
        UniqueConstraint("tenant_id", "price_list_id", "item_id", name="uq_price_list_items_list_item"),
    )

    price_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_lists.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), index=True)
    price: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    price_list: Mapped["PriceList"] = relationship(back_populates="items")


class StockBatch(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک **بارِ ورودیِ کالا** (بچ/سری) — هر خرید جداگانه ثبت می‌شود تا اگر کسری/معیوب/
    ضایعات پیش آمد، معلوم شود کدام بار مشکل داشته است. همچنین تاریخِ انقضا و سریال‌های
    کارتنِ همان بار را نگه می‌دارد.

    `qty` = مقدارِ **باقی‌مانده‌ی سالمِ** این بار (received_qty منهای کسری/معیوبِ ثبت‌شده).
    `received_qty` = مقدارِ اولیه‌ای که هنگامِ ورود ثبت شد. اختلافشان = مجموعِ کسری/معیوب.
    این جدول «دفترِ ردیابیِ بار» است، نه موتورِ مصرفِ بچ‌محور: فروش، بچِ خاصی را مصرف
    نمی‌کند؛ موتورِ اصلیِ موجودی همان میانگینِ موزون می‌ماند.
    """

    __tablename__ = "stock_batches"

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    batch_number: Mapped[str] = mapped_column(String(80))
    expiry_date: Mapped[date_ | None] = mapped_column(Date, nullable=True, index=True)
    qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0, server_default="0")
    #: مقدارِ اولیه‌ی ورودیِ این بار (پیش از کسر کسری/معیوب). با qty برابر است تا وقتی
    #: تعدیلی ثبت شود.
    received_qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0, server_default="0")
    #: بهای واحدِ این بار (ریالِ صحیح) — از فاکتورِ خرید snapshot می‌شود؛ برای مبلغِ زیانِ
    #: کسری/معیوب و گزارشِ ارزشِ بار. همان «قیمتِ خرید» است.
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: قیمتِ مصرف‌کننده (فروشِ پیشنهادی) برای این بار — تا حاشیه‌ی سود (فروش − خرید) معلوم
    #: باشد. هنگامِ خریدِ بازار خودکار از قیمتِ لیستینگ می‌آید؛ در ورودِ دستی وارد می‌شود. ۰ = نامشخص.
    consumer_price: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: تاریخِ تولیدِ این بار (اختیاری) — کنارِ تاریخِ انقضا برای ردیابیِ عمرِ کالا.
    production_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    #: منشأِ بار: purchase_invoice | manual | marketplace. با source_id به سندِ مبدأ می‌رسد.
    source_type: Mapped[str] = mapped_column(String(30), default="manual", server_default="manual")
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    received_date: Mapped[date_] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    serials: Mapped[list["StockBatchSerial"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", order_by="StockBatchSerial.serial"
    )


class StockBatchSerial(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """سریالِ کارتنِ یک بار — هر کارتن یک ردیف. اپراتورِ انبار دستی اضافه می‌کند
    (یا با تولیدِ توالیِ خودکار). وضعیت: ok = سالم، defect = معیوب."""

    __tablename__ = "stock_batch_serials"

    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_id", "serial", name="uq_batch_serials_batch_serial"),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_batches.id", ondelete="CASCADE"), index=True
    )
    serial: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="ok", server_default="ok")  # ok | defect
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")

    batch: Mapped["StockBatch"] = relationship(back_populates="serials")
