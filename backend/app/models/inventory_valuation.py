"""قیمت‌گذاری اسناد انبار — اجرای ثبت‌شده و اصلاحِ بهای هر حرکت (نوبتِ دومِ فصل).

**دفترِ موجودی دست نمی‌خورد.** `stock_ledger` فقط‌افزودنی می‌ماند و بهایی که هر سند در
لحظه‌ی ثبت نوشته سر جایش است. اصلاح در جدولِ جدا با بهای **قبل و بعد** ثبت می‌شود و
«بهای فعالِ» هر حرکت = بهای آخرین اصلاحِ باطل‌نشده، وگرنه بهای خودِ حرکت.

**یک اجرا = یک سندِ اصلاحی.** طرفینِ سند همان حساب‌هایی‌اند که حرکتِ اصلی خورده بود
(بهای تمام‌شده، هزینه‌ی مصرف، مغایرتِ انبار…) در برابرِ معینِ موجودیِ انبارِ همان حرکت.
ابطالِ اجرا سندش را معکوس و اصلاح‌هایش را غیرفعال می‌کند.
"""
import uuid
from datetime import date as date_

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin, VoidableMixin
from app.models.tenant import TenantMixin


class InventoryValuationRun(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_valuation_runs"
    __table_args__ = (UniqueConstraint("tenant_id", "number", name="uq_inventory_valuation_runs_tenant_number"),)

    number: Mapped[int] = mapped_column(Integer)
    #: دامنه‌ی اصلاح: حرکاتِ منقضیِ این بازه. بازپخش همیشه از ابتدای دفتر است.
    date_from: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date_] = mapped_column(Date)
    #: انبار فقط **کالاها** را انتخاب می‌کند (کالاهای دارای حرکت در آن)؛ میانگین مالِ کلِ شرکت است.
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=True
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: وضعیتِ دفتر در لحظه‌ی محاسبه — ثبت روی داده‌ی کهنه رد می‌شود.
    ledger_token: Mapped[str] = mapped_column(String(80), default="", server_default="")
    move_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    item_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    #: اثرِ علامت‌دارِ اجرا بر ارزشِ موجودی (ریال).
    total_delta: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: `NULL` وقتی اصلاح‌ها در سطحِ حساب هم را خنثی می‌کنند (مثلاً دو سرِ یک انتقالِ هم‌معین).
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    void_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    adjustments: Mapped[list["InventoryValuationAdjustment"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="InventoryValuationAdjustment.entry_date"
    )


class InventoryValuationAdjustment(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "inventory_valuation_adjustments"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_valuation_runs.id", ondelete="CASCADE"), index=True
    )
    #: حرکتی که بهایش اصلاح شد — خودِ ردیفِ دفتر هرگز ویرایش نمی‌شود.
    stock_ledger_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_ledger.id"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    entry_date: Mapped[date_] = mapped_column(Date)
    source_type: Mapped[str] = mapped_column(String(50))
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    previous_cost: Mapped[float] = mapped_column(Numeric(18, 4))
    new_cost: Mapped[float] = mapped_column(Numeric(18, 4))
    #: اثرِ علامت‌دار بر ارزشِ موجودی: ریالِ «مقدار × بهای تازه» منهای ریالِ «مقدار × بهای قبلی».
    value_delta: Mapped[float] = mapped_column(Numeric(18, 0))
    inventory_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    #: طرفِ مقابلِ سند: همان حسابی که حرکتِ اصلی خورد. `NULL` برای انتقال — دو سرش هم را می‌پوشانند.
    counter_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )

    run: Mapped["InventoryValuationRun"] = relationship(back_populates="adjustments")
