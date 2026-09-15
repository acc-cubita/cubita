"""پیمانکاری — پیمان (فازِ ۱) و متممِ پیمان (فازِ ۲).

`contracting_contracts`: ثبتِ یک پیمان و مفادش. رکوردِ اصلی است، نه سندِ حسابداری —
ثبتش هیچ سندی نمی‌زند (مثلِ `CostCenter`/`Bom`، نه مثلِ فاکتور)، پس `VoidableMixin`
ندارد؛ لغو از راهِ `status="cancelled"` انجام می‌شود، نه ابطال.

`contracting_amendments`: متممِ پیمان — رکوردِ افزایشی/الحاقی، نه بازنویسیِ پیمان.
`Contract.total_amount` **ثابت** می‌ماند (مبلغِ اولیه)؛ مبلغِ روزِ پیمان از جمعِ
`total_amount` + همه‌ی `amount_delta`های متمم‌هایش مشتق می‌شود (تصمیمِ بازِ #۲ در
پلن، این‌طور بسته شد — چون پیمانِ اصلی و تاریخچه‌ی تغییراتش هر دو باید قابلِ‌رجوع
بمانند، نه اینکه متمم مقدارِ قبلی را پاک کند). به همین دلیل متمم ابطال/تغییرِ
وضعیتِ خودش را ندارد — فقط رکوردِ الحاقی است؛ اگر روزی لازم شد لغوِ یک متمم، آن هم
یک متممِ اصلاحی با `amount_delta` وارونه است.

فازهای بعد (صورت‌وضعیت، تسویه‌حساب) جدول‌های خودشان را می‌گیرند و به همین جدول با
`contract_id` ارجاع می‌دهند.
"""
import uuid
from datetime import date as date_
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

if TYPE_CHECKING:
    from app.models.inventory import Contact

#: گذارِ مجاز: draft→active→{suspended⇄active, terminated, completed}؛
#: cancelled فقط از draft. `services/contracting.py` همین را می‌سنجد.
CONTRACT_STATUSES = ("draft", "active", "suspended", "terminated", "completed", "cancelled")


class Contract(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک پیمان — کارفرما، موضوع، مبلغ و بازه‌ی زمانی."""

    __tablename__ = "contracting_contracts"
    __table_args__ = (CheckConstraint(f"status IN {CONTRACT_STATUSES}", name="ck_contracting_contracts_status"),)

    number: Mapped[int] = mapped_column(index=True)
    #: شماره‌ی قراردادِ خودِ کارفرما — متن آزاد، اختیاری؛ جدا از شماره‌ی داخلیِ ما.
    external_reference: Mapped[str] = mapped_column(String(80), default="", server_default="")
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), index=True)
    subject: Mapped[str] = mapped_column(String(300), default="", server_default="")
    total_amount: Mapped[float] = mapped_column(Numeric(18, 0))
    start_date: Mapped[date_] = mapped_column(Date)
    end_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    #: فازِ ۱ فقط اطلاعاتی — مصرفِ واقعی در تسویه‌حساب (فازِ ۴).
    retention_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    advance_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    contact: Mapped["Contact | None"] = relationship("Contact", viewonly=True)

    @property
    def contact_name(self) -> str:
        return self.contact.name if self.contact else ""


class ContractAmendment(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """متممِ یک پیمان — تغییرِ مبلغ و/یا تاریخِ پایان، به‌صورتِ رکوردِ الحاقی."""

    __tablename__ = "contracting_amendments"

    number: Mapped[int] = mapped_column(index=True)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracting_contracts.id"), index=True
    )
    date: Mapped[date_] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(300))
    #: می‌تواند منفی باشد (کاهشِ مبلغ). صفر مجاز است — متممی که فقط تاریخ را تغییر می‌دهد.
    amount_delta: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: اگر داده شود، `Contract.end_date` را جایگزین می‌کند.
    new_end_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    contract: Mapped["Contract | None"] = relationship("Contract", viewonly=True)

    @property
    def contract_number(self) -> int | None:
        return self.contract.number if self.contract else None
