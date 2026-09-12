import uuid
from datetime import date as date_
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin, VoidableMixin
from app.models.tenant import TenantMixin


class SalesReturnReason(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """علتِ برگشتِ کالا — مِسترِ مستقل، نه متنِ آزاد.

    **چرا جدول و نه یک `String` روی ردیف:** «خرابی»، «خراب بود»، «کالا خراب» سه
    نوشته‌ی یک علت‌اند. با متنِ آزاد، گزارشِ «برگشت به تفکیکِ علت» هیچ‌وقت ساخته
    نمی‌شود چون هیچ دو ردیفی با هم جمع نمی‌شوند. با مِستر، همان گزارش بدونِ
    تغییرِ مدلِ تراکنش در می‌آید.

    `is_active` غیرفعال می‌کند ولی حذف نمی‌کند: علتِ غیرفعال در انتخابِ تازه
    نمی‌آید ولی روی برگشت‌های تاریخی همچنان دیده می‌شود — وگرنه سندِ پارسال با
    یک تصمیمِ امروز بی‌علت می‌شد.
    """

    __tablename__ = "sales_return_reasons"

    __table_args__ = (
        UniqueConstraint("tenant_id", "title", name="uq_sales_return_reasons_tenant_title"),
    )

    title: Mapped[str] = mapped_column(String(120))
    #: عنوانِ دوم (لاتین یا نامِ جایگزین) — همان الگویی که فرمِ مرجع نشان می‌دهد.
    title2: Mapped[str] = mapped_column(String(120), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class SalesReturn(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    """برگشت از فروش: بازگشت کالا از مشتری بابت یک فاکتور فروش مشخص. موجودی برمی‌گردد و درآمد/بهای تمام‌شده معکوس می‌شود."""

    __tablename__ = "sales_returns"

    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_sales_returns_tenant_number"),
    )

    number: Mapped[int | None] = mapped_column(nullable=True, index=True)
    return_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    sales_invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_invoices.id"))
    description: Mapped[str] = mapped_column(Text, default="")

    total_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    # مالیاتِ برگشتی — با همان نرخِ فاکتورِ اصلی. مبلغِ بازگرداندنی به مشتری = total_amount + tax_amount
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    tax_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["SalesReturnLine"]] = relationship(
        back_populates="return_", cascade="all, delete-orphan", order_by="SalesReturnLine.id"
    )


class SalesReturnLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "sales_return_lines"

    return_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_returns.id"))
    #: **ردیفِ فاکتورِ مبدأ.** بدونِ این، برگشت فقط می‌دانست «کدام کالا» و نه «کدام
    #: ردیف» — پس فاکتوری با دو ردیفِ یک کالا به دو قیمت، میانگین می‌گرفت و
    #: مشتری چیزی پس می‌گرفت که هرگز نپرداخته بود.
    #:
    #: nullable است چون ردیف‌های پیش از مهاجرتِ ۰۱۲۱ آن را ندارند و مهاجرت روی
    #: جدولِ RLS‌دار `UPDATE` نمی‌زند. `NULL` یعنی «کالا-محورِ قدیمی»، و
    #: `_drain_legacy` در سرویس مقدارشان را از استخرِ همان کالا کم می‌کند.
    sales_invoice_line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoice_lines.id"), nullable=True, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    unit_price: Mapped[float] = mapped_column(Numeric(18, 0))
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))
    #: علتِ برگشت — **جدا از `description`**. یکی بُعدِ گزارش است و دیگری یادداشتِ
    #: آزادِ همین ردیف؛ یکی‌کردنشان هر دو را بی‌مصرف می‌کند.
    return_reason_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_return_reasons.id"), nullable=True, index=True
    )
    description: Mapped[str] = mapped_column(Text, default="")

    return_: Mapped["SalesReturn"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()
    reason: Mapped["SalesReturnReason"] = relationship()


#: انواعِ برگشتِ رسید — **چهار تا، نه پنج تا.**
#:
#: فرمِ برگشت «موجودی اول دوره» را ندارد، و فصل صریح هشدار می‌دهد فهرستِ
#: نوع‌های رسید را کورکورانه کپی نکنیم: «Do not blindly copy every Warehouse
#: Receipt type into Return.»
RETURN_TYPES = ("purchase_domestic", "purchase_import", "production", "other")
RETURN_TYPE_LABELS = {
    "purchase_domestic": "خرید (داخلی)",
    "purchase_import": "خرید (وارداتی)",
    "production": "تولید",
    "other": "سایر",
}


class PurchaseReturn(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    """برگشت کالا به طرفِ مقابل — با لنگر روی فاکتورِ خرید یا روی رسیدِ انبار.

    **یک سند، دو لنگر (و عمداً یک جدول).**

    فصلِ «برگشت رسید انبار» می‌پرسد آیا موجودیتِ دومی بسازیم، و خودش محدودش
    می‌کند: «نباید کورکورانه Entity دوم ساخته شود» و «Keep commercial and
    physical return distinguishable **even if Cubita intentionally combines
    them in one workflow**».

    این سند از قبل هر دو نیمه را انجام می‌داد — بدهیِ تأمین‌کننده را بدهکار
    می‌کند **و** موجودی را کم می‌کند. ساختنِ `WarehouseReceiptReturn` کنارش
    یعنی دو سند یک بدهی را برگردانند؛ دقیقاً همان دوباره‌ثبتی که §۳۷ فصلِ پیش
    ازش هشدار می‌دهد.

        PurchaseInvoiceLine   ──┐
                                ├──→  PurchaseReturnLine
        WarehouseReceiptLine  ──┘

    **چرا لنگرِ رسید لازم شد:** از مهاجرتِ ۰۱۲۷ فاکتورِ خرید `warehouse_id`
    ندارد و کالا با رسید وارد می‌شود. برگشت هنوز موجودی را در انبارِ فاکتور
    می‌جست و همیشه صفر می‌دید — یعنی روی گردشِ رسیدِ انبار اصلاً کار نمی‌کرد.
    """

    __tablename__ = "purchase_returns"

    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_purchase_returns_tenant_number"),
        CheckConstraint(
            "return_type IN ('purchase_domestic', 'purchase_import', 'production', 'other')",
            name="ck_purchase_returns_return_type",
        ),
    )

    number: Mapped[int | None] = mapped_column(nullable=True, index=True)
    return_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    #: **اختیاری.** برگشتی که به رسیدِ مستقیم لنگر می‌زند هیچ فاکتوری ندارد.
    purchase_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_invoices.id"), nullable=True
    )
    #: لنگرِ دوم: رسیدِ انباری که کالا از آن آمده بود.
    warehouse_receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouse_receipts.id"), nullable=True, index=True
    )
    #: انباری که کالا از آن خارج می‌شود. در مسیرِ رسید از خودِ رسید می‌آید.
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=True
    )
    #: **«تحویل‌گیرنده» — و با «تحویل‌دهنده»ی رسید یکی نیست.**
    #:
    #: در رسید کالا را شرکت تحویل می‌گیرد؛ در برگشت کالا از شرکت خارج می‌شود و
    #: کسی آن را می‌گیرد. فصل می‌گوید این دو را در یک فیلدِ مبهم گم نکنیم.
    receiver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True
    )
    return_type: Mapped[str] = mapped_column(
        String(20), default="purchase_domestic", server_default="purchase_domestic"
    )
    #: مبالغ همیشه پایه‌اند؛ این‌ها فقط برای نمایشِ معادل و نرخ‌اند — همان
    #: قراردادی که فاکتور و رسید دارند.
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 4), default=1, server_default="1")
    description: Mapped[str] = mapped_column(Text, default="")

    total_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    # مالیاتِ برگشتی — با همان نرخِ فاکتورِ اصلی. مبلغِ بازپس‌گرفتنی از تأمین‌کننده = total_amount + tax_amount
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    tax_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    #: `(seq, id)` و نه `id`: کلید اصلی UUIDِ تصادفی است، پس ستونِ «ردیف»ِ
    #: برگهٔ چاپی هر بار می‌توانست ترتیبِ دیگری بدهد (همان درسِ ۰۱۲۸).
    lines: Mapped[list["PurchaseReturnLine"]] = relationship(
        back_populates="return_",
        cascade="all, delete-orphan",
        order_by="(PurchaseReturnLine.seq, PurchaseReturnLine.id)",
    )

    @property
    def base_amount(self) -> Decimal:
        """ارزشِ موجودیِ کالایی که از انبار خارج می‌شود — «خالص» (پیش از مالیات).

        بهای تمام‌شده است، نه فی: سهمِ حملِ ورودِ همان کالا هم با آن می‌رود،
        وگرنه حمل روی موجودیِ صفر جا می‌ماند.
        """
        return sum((line.landed_amount for line in self.lines), Decimal(0))

    @property
    def agreed_total(self) -> Decimal:
        """**«خالص توافقی»** — آن‌چه طرفِ مقابل واقعاً پس می‌دهد.

        فصل صریح می‌گوید این با ارزشِ موجودی یکی نیست و نباید یکی فرض شود:
        «DO NOT assume Inventory Value = Agreed Commercial Return Value».
        فهرستِ مرجع هم هر دو ستون را کنارِ هم دارد.
        """
        return sum((Decimal(line.agreed_amount) for line in self.lines), Decimal(0))


class PurchaseReturnLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "purchase_return_lines"

    return_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_returns.id"))
    #: شماره‌ی ردیف در همین سند (از ۱). صفر یعنی «ردیفِ پیش از مهاجرتِ ۰۱۲۹».
    seq: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    #: قرینه‌ی `SalesReturnLine.sales_invoice_line_id` — همان دلیل، همان قاعده‌ی `NULL`.
    purchase_invoice_line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_invoice_lines.id"), nullable=True, index=True
    )
    #: **لنگرِ فیزیکی.** فصل می‌گوید وقتی ردیفِ رسید وجود دارد، برگشت را فقط
    #: «کالا + مقدار» مدل نکنیم: اگر یک کالا سه بار با سه بهای متفاوت وارد شده
    #: باشد، باید معلوم باشد کدام ورود برگشت می‌خورد — چون باقیمانده، بهای
    #: تمام‌شده، ردیابی و حسابداری همه به آن وابسته‌اند.
    warehouse_receipt_line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouse_receipt_lines.id"), nullable=True, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    #: «فی» — بهای خریدِ واحد، پیش از حمل.
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))
    #: سهمِ حملی که با این کالا برمی‌گردد (از سهمِ همان ردیفِ رسید، به نسبتِ مقدار).
    freight_share: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    #: **مبالغ مرجوعی توافقی — مستقل، و عمداً مستقل.**
    #:
    #: پیش‌فرضشان همان ارزشِ موجودی است، پس گردشِ عادی هیچ فرقی نمی‌کند. ولی
    #: وقتی توافق عددِ دیگری باشد، هر دو عدد در سند می‌مانند و گم نمی‌شوند.
    agreed_unit_value: Mapped[float] = mapped_column(Numeric(18, 4), default=0, server_default="0")
    agreed_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    #: مالیاتِ همین ردیف — تا «مالیات و عوارض»ِ برگهٔ چاپی از اجزای خودش
    #: توضیح‌پذیر باشد، نه از یک نرخِ سربرگ که برای ردیفِ معاف غلط است.
    tax_rate_snapshot: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    tax_amount_snapshot: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    description: Mapped[str] = mapped_column(Text, default="")

    return_: Mapped["PurchaseReturn"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()

    @property
    def goods_amount(self) -> Decimal:
        return Decimal(self.qty) * Decimal(self.unit_cost)

    @property
    def landed_amount(self) -> Decimal:
        """بهای تمام‌شده‌ی کالایی که از انبار خارج می‌شود = کالا + سهمِ حمل."""
        return self.goods_amount + Decimal(self.freight_share)
