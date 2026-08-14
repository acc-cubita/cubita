import uuid
from datetime import date as date_

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

#: ارزِ پایه ضمنی است (ریال). این ثابت فقط برای نمایش در جایی که کد ارز خالی است.
BASE_CURRENCY_NAME = "ریال"


class Currency(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """ارزِ خارجیِ تعریف‌شده‌ی یک کسب‌وکار. پایه (ریال) ضمنی است و اینجا ثبت نمی‌شود."""

    __tablename__ = "currencies"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_currencies_tenant_code"),)

    code: Mapped[str] = mapped_column(String(3))  # مثل USD, EUR, AED
    name: Mapped[str] = mapped_column(String(100))
    symbol: Mapped[str] = mapped_column(String(10), default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class ExchangeRate(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """نرخِ برابریِ یک ارز در یک تاریخ: چند واحدِ پایه (ریال) به‌ازای یک واحدِ ارز."""

    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "currency_code", "rate_date", name="uq_exchange_rates_tenant_code_date"),
    )

    currency_code: Mapped[str] = mapped_column(String(3))
    rate_date: Mapped[date_] = mapped_column(Date)
    rate: Mapped[float] = mapped_column(Numeric(18, 4))
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
