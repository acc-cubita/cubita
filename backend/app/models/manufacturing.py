"""تولید و بهای تمام‌شده — فرمولِ ساخت (BOM)، سفارشِ تولید (برنامه) و سندِ تولید (اجرا).

پنج جدولِ مستأجرمحور (RLS):
  - boms: فرمولِ ساختِ یک محصولِ نهایی (چه چیزی از چه اجزایی و با چه بازدهی ساخته می‌شود).
  - bom_lines: اجزای فرمول (کالای جزء + مقدار برای هر «بازده»).
  - production_plans: سفارشِ تولید — فقط برنامه‌ریزی، بدونِ اثرِ انبار/بها.
  - production_orders: سندِ تولید — بارِ واقعیِ تولید (مصرفِ اجزا و تولیدِ محصول).
  - production_order_lines: عکس‌برداری از اجزای مصرف‌شده و بهایشان در لحظه‌ی تولید (برای ممیزی).

منطقِ بهای تمام‌شده: اجزا با «میانگینِ موزون»ِ خودشان از انبار خارج می‌شوند؛ بهای هر واحدِ
محصول = (جمعِ بهای اجزا + سربار) ÷ تعدادِ تولید. چون اجزا و محصول هر دو در همان حسابِ
«موجودی کالا»اند، تنها زمانی سند می‌خورد که سرباری اضافه شده باشد (بدهکار موجودی/بستانکار صندوق).

**سفارش ≠ سند.** تا امروز «سفارشِ تولید» بلافاصله مواد را مصرف و محصول را تولید
می‌کرد — هیچ مرحله‌ی «برنامه‌ریزی، بعد اجرا»یی نبود. `ProductionPlan` این شکاف را
می‌بندد: فقط برنامه (فرمول، انبار، تاریخِ برنامه، مقدار)، بدونِ ستونِ بها یا اثرِ
موجودی. `ProductionOrder` (نامش برای سازگاری با دیتای موجود دست‌نخورده ماند) همان
اجرای واقعی‌ست که همیشه بود؛ فقط یک FKِ اختیاریِ `production_plan_id` گرفت تا اگر
از رویِ یک برنامه اجرا شد، ردش بماند.
"""
import uuid
from datetime import date as date_

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

#: گذارِ مجازِ وضعیتِ سفارش (برنامه). همان الگوی Contract در پیمانکاری.
PRODUCTION_PLAN_STATUSES = ("draft", "started", "in_progress", "stopped", "finished", "cancelled")


class Bom(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """فرمولِ ساخت — یک محصولِ نهایی و اجزایش."""

    __tablename__ = "boms"

    finished_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    #: هر «اجرای» این فرمول چند واحدِ محصول می‌سازد (مثلاً یک قالب = ۱۲ عدد).
    yield_qty: Mapped[float] = mapped_column(Numeric(18, 3), default=1, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["BomLine"]] = relationship(
        back_populates="bom", cascade="all, delete-orphan"
    )


class BomLine(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک جزء از فرمول — کالای جزء + مقدارِ لازم برای هر «بازده»."""

    __tablename__ = "bom_lines"

    bom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boms.id", ondelete="CASCADE"), index=True
    )
    component_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3))

    bom: Mapped["Bom"] = relationship(back_populates="lines")


class ProductionPlan(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """سفارشِ تولید — فقط برنامه. بدونِ ستونِ بها یا اثرِ انبار."""

    __tablename__ = "production_plans"
    __table_args__ = (
        CheckConstraint(f"status IN {PRODUCTION_PLAN_STATUSES}", name="ck_production_plans_status"),
    )

    number: Mapped[int] = mapped_column(index=True)
    bom_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("boms.id"))
    finished_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    planned_date: Mapped[date_] = mapped_column(Date)
    qty_planned: Mapped[float] = mapped_column(Numeric(18, 3))
    #: جمعِ qty_produced همه‌ی اسنادِ تولیدی که به این برنامه وصل شده‌اند — برای
    #: نمایشِ «چقدر از این برنامه اجرا شد»، نه مبنای محاسبه‌ی چیزِ دیگری.
    qty_produced: Mapped[float] = mapped_column(Numeric(18, 3), default=0, server_default="0")
    #: جمعِ بهای همه‌ی حواله‌های موادِ متصل به این برنامه — مبنای بهای رسیدِ
    #: محصول (`material_cost_issued ÷ qty_planned`)، پیش از افزودنِ دستمزد/سربار.
    material_cost_issued: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: جمعِ دستمزد و سربارِ نشسته روی این سفارش — هر بار که «محاسبه قیمت
    #: تمام‌شده» اجرا شود بالا می‌رود. جدا نگه داشته می‌شوند چون گزارشِ بهای
    #: تمام‌شده باید سه جزء را از هم تفکیک کند، نه یک جمعِ مبهم.
    labor_cost_applied: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    overhead_cost_applied: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class ProductionOrder(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """سندِ تولید — اجرای واقعی: اجزا مصرف و محصول تولید می‌شود."""

    __tablename__ = "production_orders"

    number: Mapped[int | None] = mapped_column(nullable=True, index=True)
    bom_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("boms.id"))
    finished_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    #: اگر این سند از رویِ یک سفارش (برنامه) اجرا شد — اختیاری، تولیدِ بی‌برنامه هم مجاز است.
    production_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("production_plans.id"), nullable=True, index=True
    )
    production_date: Mapped[date_] = mapped_column(Date)
    qty_produced: Mapped[float] = mapped_column(Numeric(18, 3))
    component_cost: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    overhead_cost: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["ProductionOrderLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class ProductionOrderLine(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """عکس‌برداری از یک جزءِ مصرف‌شده در یک سفارشِ تولید (مقدار و بهای لحظه‌ای)."""

    __tablename__ = "production_order_lines"

    production_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("production_orders.id", ondelete="CASCADE"), index=True
    )
    component_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    order: Mapped["ProductionOrder"] = relationship(back_populates="lines")
