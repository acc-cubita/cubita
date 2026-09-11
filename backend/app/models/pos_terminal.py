import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

if TYPE_CHECKING:
    from app.models.analytic import AnalyticAccount
    from app.models.banking import BankAccount

#: روشِ اتصالِ نرم‌افزار به دستگاهِ کارتخوان. simulator = شبیه‌سازِ نرم‌افزاری (بدونِ
#: سخت‌افزار، برای توسعه/دمو). network = کارتخوانِ تحت‌شبکه (TCP روی IP:Port).
#: serial = پورتِ سریال/USB (COM). sdk = SDK/DLLِ مخصوصِ شرکتِ پرداخت.
POS_TRANSPORTS = ("simulator", "network", "serial", "sdk")


class PosTerminal(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """پروفایلِ یک دستگاهِ کارتخوان که به این کسب‌وکار وصل است.

    فقط بخشِ حسابداری‌محور (نامِ نمایشی، حسابِ بانکیِ تسویه، فعال/پیش‌فرض) و سرنخِ
    اتصال (transport/host/port/COM) اینجاست؛ خودِ ارتباط با سخت‌افزار در پروسه‌ی
    اصلیِ الکترون انجام می‌شود، نه سرور.

    **دو حسابِ متفاوت، و این تفاوت مهم است.** کارت‌کشیِ مشتری روی معینِ «وجوهِ در
    راهِ کارت‌خوان» با تفصیلیِ `analytic_id` می‌نشیند؛ `bank_account_id` جایی است
    که *تسویه* پول را به آن می‌برد. تا مهاجرتِ ۰۱۰۹ هر دو یکی بودند — یعنی مانده‌ی
    بانک از همان لحظه‌ی کارت‌کشی بالا می‌رفت، چند روز پیش از آنکه پولی برسد.
    """

    __tablename__ = "pos_terminals"
    __table_args__ = (
        CheckConstraint(f"transport IN {POS_TRANSPORTS}", name="ck_pos_terminals_transport"),
        #: یکتا فقط وقتی پر شده — ایندکسِ جزئی. دستگاه‌های تعریف‌شده‌ی پیش از
        #: مهاجرتِ ۰۱۰۷ شماره ندارند و نباید با هم تصادم کنند.
        Index(
            "uq_pos_terminals_tenant_terminal_no",
            "tenant_id",
            "terminal_no",
            unique=True,
            postgresql_where=text("terminal_no <> ''"),
        ),
    )

    label: Mapped[str] = mapped_column(String(120), default="")
    #: عنوانِ دوم — همان نقشی که `name2` در صندوق و حسابِ بانکی دارد.
    name2: Mapped[str] = mapped_column(String(120), default="", server_default="")
    #: شماره‌ی پایانه‌ای که خودِ دستگاه گزارش می‌کند. **هویتِ رکورد نیست** (§۴) —
    #: آن `id` است؛ این شماره عوض‌شدنی است. تا مهاجرتِ ۰۱۰۷ اصلاً روی دستگاه
    #: نبود و فقط روی تراکنش می‌نشست، یعنی دستگاهِ تعریف‌شده نمی‌دانست دستگاهِ
    #: واقعی چه شماره‌ای برمی‌گرداند.
    terminal_no: Mapped[str] = mapped_column(String(30), default="", server_default="")
    #: ارزِ عملیاتیِ دستگاه؛ باید با ارزِ حسابِ بانکیِ تسویه بخواند (§۹).
    currency_code: Mapped[str] = mapped_column(String(3), default="IRR", server_default="IRR")
    psp: Mapped[str] = mapped_column(String(30), default="", server_default="")
    transport: Mapped[str] = mapped_column(String(20), default="simulator", server_default="simulator")
    host: Mapped[str] = mapped_column(String(120), default="", server_default="")
    port: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    com_port: Mapped[str] = mapped_column(String(20), default="", server_default="")
    #: تفصیلیِ این دستگاه روی حسابِ «وجوهِ در راهِ کارت‌خوان» — همان نقشی که
    #: `analytic_id` در صندوق و حسابِ بانکی دارد. بدونِ آن، همه‌ی دستگاه‌ها روی یک
    #: معین می‌نشینند و «وجوهِ در راهِ دستگاهِ شعبه‌ی ۲» از دفتر درنمی‌آید.
    #:
    #: `NULL` معنا دارد و backfill نمی‌خواهد: دستگاهِ بی‌تفصیلی روی ردیف‌های
    #: بی‌تفصیلیِ همان معین می‌نشیند، که دقیقاً همان چیزی است که داده‌ی امروز هست.
    analytic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analytic_accounts.id", ondelete="SET NULL"), nullable=True
    )
    #: حسابِ بانکیِ تسویه‌ی این کارتخوان — **مقصدِ تسویه**، نه جایی که کارت‌کشی
    #: می‌نشیند. رسیدِ کارتی به «وجوهِ در راه» می‌رود و تسویه آن را به اینجا می‌آورد.
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_accounts.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    bank_account: Mapped["BankAccount | None"] = relationship("BankAccount")
    analytic: Mapped["AnalyticAccount | None"] = relationship("AnalyticAccount")
