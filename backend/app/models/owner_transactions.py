"""تراکنشِ مالک و شریک با شرکت — با نوعِ **صریح**.

**چه کم بود.** تا امروز آورده‌ی مالک، برداشتش، و وام‌های دوطرفه‌ی شریک هیچ
موجودیتی نداشتند. تنها راه، سندِ دستی بود — و سندِ دستی یعنی:

* قاعده‌ی پایدارِ ۲ («آورده ≠ درآمد، برداشت ≠ هزینه») هیچ گاردِ نرم‌افزاری نداشت؛
* «صورت تغییرات در حقوق صاحبان سهام» — یکی از چهار صورتِ الزامی — **ساختاراً**
  ناممکن بود، چون هیچ داده‌ای نمی‌گفت کدام سند آورده بوده و کدام برداشت.

**قاعده‌ی ۵۲ چه می‌خواهد.** `TransactionType` صریح: `LoanToEntity`،
`LoanFromEntity`، `CapitalContribution`، `CapitalReduction/Withdrawal`،
`Repayment`. و صریحاً: «Direction یا PartyRole به‌تنهایی نوعِ حسابداری را تعیین
نکند». برای همین `type` ستونِ خودش را دارد و از روی جهتِ پول **مشتق نمی‌شود**:
وقتی پول وارد می‌شود، هم می‌تواند آورده‌ی سرمایه باشد، هم وامِ شریک، هم
بازپرداختِ بدهی‌اش — سه رویدادِ متفاوت با سه معنای متفاوت در گزارش.

**و تعارضِ C-04 این‌جا حل می‌شود** — نه با انتخابِ یک طرف. پایگاه دانش می‌گوید
برداشتِ مالک «Equity withdrawal یا ReceivableFromOwner» است و «نوع باید صریح
باشد». پس کاربر خودش تصریح می‌کند: `capital_withdrawal` (کاهشِ دائمیِ سرمایه)
یا `loan_from_entity` (برداشتِ قابلِ بازپرداخت، که مطالبه می‌سازد).
"""
import uuid
from datetime import date as date_
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin, VoidableMixin
from app.models.tenant import TenantMixin

if TYPE_CHECKING:
    from app.models.inventory import Contact

#: شش نوعِ صریح. سه‌تای اولِ ورودی و سه‌تای خروجی نیستند — جهت از نوع مشتق
#: می‌شود، نه برعکس. دو جفتِ آخر از نظرِ **ثبت** یکسان‌اند و از نظرِ **معنا**
#: نه: «وامِ تازه» و «بازپرداختِ بدهیِ قبلی» هر دو جاری شرکا را تکان می‌دهند ولی
#: در گزارشِ شریک دو چیزِ متفاوت‌اند.
OWNER_TRANSACTION_TYPES = (
    "capital_contribution",   # آورده‌ی سرمایه       — بد: نقد/بانک · بس: سرمایه
    "capital_withdrawal",     # کاهشِ سرمایه         — بد: سرمایه    · بس: نقد/بانک
    "loan_to_entity",         # وامِ شریک به شرکت    — بد: نقد/بانک · بس: جاری شرکا
    "loan_from_entity",       # برداشتِ بازپرداختنی  — بد: جاری شرکا · بس: نقد/بانک
    "repayment_to_partner",   # بازپرداختِ شرکت      — بد: جاری شرکا · بس: نقد/بانک
    "repayment_from_partner", # بازپرداختِ شریک      — بد: نقد/بانک · بس: جاری شرکا
)

#: از کجا/به کجا. همان دو مقدارِ `TreasuryTransaction` تا رفتار یکی بماند.
OWNER_TRANSACTION_METHODS = ("cash", "bank")


class OwnerTransaction(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک رویدادِ مالی بینِ شرکت و یکی از مالکان/شرکا.

    **موجودیتِ حسابداری مستقل از مالک است** (قاعده‌ی پایدارِ ۱۱) — برای همین این
    یک *تراکنش* است، نه ویژگیِ طرفِ حساب: شرکت و شریک دو طرفِ یک رویدادند.
    """

    __tablename__ = "owner_transactions"
    __table_args__ = (
        CheckConstraint(f"type IN {OWNER_TRANSACTION_TYPES}", name="ck_owner_transactions_type"),
        CheckConstraint(f"method IN {OWNER_TRANSACTION_METHODS}", name="ck_owner_transactions_method"),
        CheckConstraint("amount > 0", name="ck_owner_transactions_amount_positive"),
    )

    type: Mapped[str] = mapped_column(String(30))
    transaction_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    #: شریک/مالک. سرویس می‌سنجد که `is_shareholder` باشد — نقشی که مدلِ طرفِ
    #: حساب از قبل داشت و هیچ‌کس استفاده‌اش نمی‌کرد.
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    method: Mapped[str] = mapped_column(String(10), default="cash")
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_accounts.id"), nullable=True
    )
    #: کدام صندوق. `NULL` = صندوقِ پیش‌فرض — همان قراردادِ `TreasuryTransaction`.
    cashbox_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cashboxes.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: شماره‌ی مدرکِ پشتوانه (فیش، حواله). سندِ پشتیبان ≠ سندِ حسابداری — قاعده‌ی
    #: پایدارِ ۶؛ این ستون فقط ردِ اولی است.
    evidence_ref: Mapped[str] = mapped_column(String(120), default="", server_default="")

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    contact: Mapped["Contact"] = relationship()
