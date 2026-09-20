"""برگشتِ خروجِ انبار — ورودِ دوباره‌ی کالایی که با یک خروج از انبار رفته بود.

**برگشتِ خروج ≠ فاکتور برگشتی ≠ تعدیلِ موجودی.** فاکتور برگشتی می‌گوید از نظرِ
تجاری چه مقدار از فروش برگشت خورد (درآمد، مالیات، طلبِ مشتری)؛ این سند می‌گوید چه
مقدار کالا **واقعاً** دوباره وارد انبار شد. مشتری ممکن است ده عدد را مرجوع کند و
امروز فقط پنج عدد را تحویل دهد.

**هر ردیف به ردیفِ خروجی که برمی‌گرداند گره می‌خورد — اجباری.** بدونِ خروجِ مبدأ نه
بهای برگشت معلوم است و نه حسابی که باید برگردد؛ کالای اضافه‌ی بی‌مبدأ جایش «تعدیل
موجودی» است. همین لنگر سقفِ برگشت را هم می‌سازد: از یک ردیفِ خروج بیش از آنچه
خارج شده برنمی‌گردد، از هر مسیری که بیاید.
"""

import uuid
from datetime import date as date_
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin, VoidableMixin
from app.models.returns import RETURN_CONDITIONS
from app.models.tenant import TenantMixin

#: سه نوع — **بدونِ «انتقال»**. فصل صریح می‌گوید فهرستِ نوع‌های خروج را کورکورانه
#: روی برگشت کپی نکنیم؛ انتقالِ برعکس یک انتقالِ دیگر است، نه برگشت.
ISSUE_RETURN_TYPES = ("sale", "consumption", "other")
ISSUE_RETURN_TYPE_LABELS = {"sale": "فروش", "consumption": "مصرف", "other": "سایر"}

#: `direct` = کاربر ثبت کرده؛ `sales_return` = «برگشت از فروش» در سیاستِ خودکار خودش
#: ساخته — همان‌طور که «ثبت فاکتور» خروجِ فاکتور را خودش می‌سازد.
ISSUE_RETURN_ORIGINS = ("direct", "sales_return")


class WarehouseIssueReturn(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "warehouse_issue_returns"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_warehouse_issue_returns_tenant_number"),
        CheckConstraint(f"return_type IN {ISSUE_RETURN_TYPES}", name="ck_warehouse_issue_returns_type"),
        CheckConstraint(f"origin IN {ISSUE_RETURN_ORIGINS}", name="ck_warehouse_issue_returns_origin"),
    )

    number: Mapped[int] = mapped_column(nullable=False, index=True)
    return_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    return_type: Mapped[str] = mapped_column(String(20), default="sale", server_default="sale")
    origin: Mapped[str] = mapped_column(String(12), default="direct", server_default="direct")
    #: انباری که کالا **به آن** برمی‌گردد — می‌تواند با انبارِ خروج فرق کند.
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False, index=True
    )
    #: **«تحویل‌دهنده»، نه «تحویل‌گیرنده».** در خروج کالا از شرکت می‌رود و کسی آن را
    #: می‌گیرد؛ در برگشت کسی آن را دوباره به انبار می‌دهد. فصل می‌گوید این دو نقش را
    #: در یک فیلدِ مبهم گم نکنیم.
    deliverer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True, index=True
    )
    #: فقط برای برگشتی که «برگشت از فروش» خودش ساخته — تا ابطالش آبشاری باشد.
    sales_return_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_returns.id"), nullable=True, index=True
    )
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["WarehouseIssueReturnLine"]] = relationship(
        back_populates="return_",
        cascade="all, delete-orphan",
        order_by="(WarehouseIssueReturnLine.seq, WarehouseIssueReturnLine.id)",
    )

    @property
    def total_qty(self) -> Decimal:
        return sum((Decimal(line.qty) for line in self.lines), Decimal(0))

    @property
    def total_cost(self) -> Decimal:
        """جمعِ بهای ردیف‌ها — همان عددی که سندِ حسابداری زده."""
        return sum((line.amount for line in self.lines), Decimal(0))


class WarehouseIssueReturnLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "warehouse_issue_return_lines"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_warehouse_issue_return_lines_qty_positive"),
        CheckConstraint(f"return_condition IN {RETURN_CONDITIONS}", name="ck_warehouse_issue_return_lines_condition"),
    )

    return_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouse_issue_returns.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    #: **§۱۴ — مرجوعی بارمحور است.** تا امروز برگشت فقط «چند تا» را می‌دانست،
    #: نه «از کدام بار» و نه «در چه حالی». تهی = برگشتی که بار ندارد (کالای
    #: بی‌ردیابی) — همان رفتارِ دیروز.
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_batches.id", ondelete="RESTRICT"), nullable=True
    )
    #: کالای سالم به موجودیِ قابلِ فروشِ همان بار برمی‌گردد؛ خراب/منقضی/قرنطینه
    #: فیزیکی برمی‌گردد ولی **قابلِ فروش نیست**. پیش‌فرض `sellable` یعنی رفتارِ
    #: دیروز: تا امروز هر برگشتی مستقیم قابلِ فروش می‌شد.
    return_condition: Mapped[str] = mapped_column(String(20), default="sellable", server_default="sellable")
    #: **ردیفِ خروجی که برمی‌گردد — اجباری.** سقفِ برگشت، بها و حسابِ برگشت همه از آن.
    warehouse_issue_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouse_issue_lines.id"), nullable=False, index=True
    )
    #: «مبنا»ی تجاری در نوعِ فروش. **یک ردیفِ فاکتور برگشتی با چند برگشتِ انبار**
    #: پُر می‌شود، پس رابطه روی این سمت است نه روی ردیفِ فاکتور برگشتی.
    sales_return_line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_return_lines.id"), nullable=True, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), index=True)
    #: به واحدِ اصلی.
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    #: بهای همان ردیفِ خروج — نه قیمتِ فروش، نه میانگینِ امروز.
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 4))
    #: حسابی که **بستانکار** شد: همان که خروج بدهکار کرده بود.
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )
    secondary_qty: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    secondary_unit_snapshot: Mapped[str] = mapped_column(String(20), default="", server_default="")
    item_code_snapshot: Mapped[str] = mapped_column(String(50), default="", server_default="")
    item_name_snapshot: Mapped[str] = mapped_column(String(300), default="", server_default="")
    unit_snapshot: Mapped[str] = mapped_column(String(20), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")

    return_: Mapped["WarehouseIssueReturn"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()

    @property
    def amount(self) -> Decimal:
        return (Decimal(self.qty) * Decimal(self.unit_cost or 0)).quantize(Decimal(1))
