"""کسوراتِ خریدِ خدمت — مالیات تکلیفی و بیمه، به‌عنوان بدهیِ واقعی نه تخفیف.

**چرا دو فیلدِ ثابت روی فاکتور نساختیم.** فصل صریح است: قانون، نوعِ قرارداد و درصدها
عوض می‌شوند و ممکن است کسرِ دیگری هم بیاید. پس «نوعِ کسر» داده‌ی پایه است — عنوان،
ماهیت، مبنا، نرخِ پیش‌فرض و حساب — و فاکتور فقط Snapshotِ آنچه در لحظه‌ی ثبت خورد
را نگه می‌دارد.

**و چرا هیچ نرخی از پیش ساخته نمی‌شود.** ۳٪ و ۱۶٫۶۶۷٪ِ ویدیو مثال‌اند، نه قاعده.
کسب‌وکار خودش تعریف می‌کند؛ پیش‌فرض خالی است.

**ماهیت** (`nature`) فقط دو مقدار دارد چون فصل فقط همین دو را ثابت کرده. ماهیت
تعیین می‌کند اگر حسابی انتخاب نشده، پیش‌فرضِ کدام نقشِ حساب بخورد — و در فهرستِ
فاکتورها کدام ستون جمع شود.
"""
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

DEDUCTION_NATURES = ("withholding_tax", "insurance")
DEDUCTION_NATURE_LABELS = {"withholding_tax": "مالیات تکلیفی", "insurance": "بیمه"}

#: مبنای محاسبه. **خالص پیش از مالیات و عوارض** پیش‌فرض است: کسر از مبلغِ خدمت
#: است، نه از پولِ دولت. «ناخالص» برای قراردادی است که کسر را پیش از تخفیف می‌خواهد.
DEDUCTION_BASES = ("net_before_tax", "gross")
DEDUCTION_BASIS_LABELS = {
    "net_before_tax": "خالص پیش از مالیات و عوارض",
    "gross": "ناخالص (مقدار × فی)",
}


class PurchaseDeductionType(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """تعریفِ یک کسر — «مالیات تکلیفی ۳٪»، «حق بیمه قرارداد»."""

    __tablename__ = "purchase_deduction_types"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_purchase_deduction_types_tenant_name"),
        CheckConstraint(f"nature IN {DEDUCTION_NATURES}", name="ck_purchase_deduction_types_nature"),
        CheckConstraint(f"basis IN {DEDUCTION_BASES}", name="ck_purchase_deduction_types_basis"),
        CheckConstraint("rate >= 0 AND rate <= 100", name="ck_purchase_deduction_types_rate"),
    )

    code: Mapped[str] = mapped_column(String(30), default="", server_default="")
    name: Mapped[str] = mapped_column(String(100))
    nature: Mapped[str] = mapped_column(String(20))
    basis: Mapped[str] = mapped_column(String(20), default="net_before_tax", server_default="net_before_tax")
    #: درصدِ پیش‌فرض. فاکتور مبلغ را از این پیشنهاد می‌دهد و کاربر می‌تواند عوضش کند.
    rate: Mapped[Decimal] = mapped_column(Numeric(7, 3), default=0, server_default="0")
    #: `NULL` یعنی حسابِ پیش‌فرضِ نقشِ همین ماهیت — مثلِ معینِ هزینه‌ی خدمت.
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")


class PurchaseInvoiceDeduction(TenantMixin, UUIDPKMixin, Base):
    """کسری که روی یک فاکتور خورد — Snapshot، نه ارجاعِ زنده.

    اگر فردا نرخ یا حسابِ نوعِ کسر عوض شود، این ردیف همان می‌ماند که سند زده؛ و
    چاپ، فهرست و گزارش از همین می‌خوانند نه از تعریفِ امروز.
    """

    __tablename__ = "purchase_invoice_deductions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_purchase_invoice_deductions_amount_positive"),
        CheckConstraint(f"nature IN {DEDUCTION_NATURES}", name="ck_purchase_invoice_deductions_nature"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_invoices.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    deduction_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_deduction_types.id"), nullable=True, index=True
    )
    nature: Mapped[str] = mapped_column(String(20))
    name_snapshot: Mapped[str] = mapped_column(String(100), default="", server_default="")
    basis: Mapped[str] = mapped_column(String(20))
    basis_amount: Mapped[Decimal] = mapped_column(Numeric(18, 0))
    rate: Mapped[Decimal] = mapped_column(Numeric(7, 3), default=0, server_default="0")
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 0))
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))

    invoice = relationship("PurchaseInvoice", back_populates="deductions")
