import uuid
from datetime import date as date_

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

# روش استهلاک — فعلاً فقط خط مستقیم. tuple نگه‌داشتنش یعنی schema و CheckConstraint
# از یک منبع می‌خوانند و از هم جدا نمی‌افتند.
DEPRECIATION_METHODS = ("straight_line",)
# ساختِ دستیِ فهرستِ IN — چون f-string روی tupleِ تک‌عضوی کامای انتهایی می‌گذارد
# (`('straight_line',)`) که در SQL خطای نحوی است.
_METHODS_IN_SQL = ", ".join(f"'{m}'" for m in DEPRECIATION_METHODS)


class FixedAsset(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک قلم دارایی ثابت (خودرو، تجهیزات، ...) که در طول عمر مفیدش مستهلک می‌شود.

    استهلاکِ انباشته روی خودِ دارایی نگه داشته می‌شود تا محاسبه‌ی ارزش دفتری یک
    تفریق ساده باشد؛ سندِ هر دوره‌ی استهلاک جدا در DepreciationEntry ثبت می‌شود تا
    هم ردِ حسابرسی بماند و هم یک دوره دوبار مستهلک نشود.
    """

    __tablename__ = "fixed_assets"
    __table_args__ = (
        CheckConstraint(f"method IN ({_METHODS_IN_SQL})", name="ck_fixed_assets_method"),
        CheckConstraint("cost >= 0 AND salvage_value >= 0", name="ck_fixed_assets_amounts_nonneg"),
        CheckConstraint("useful_life_months > 0", name="ck_fixed_assets_life_positive"),
        CheckConstraint("salvage_value <= cost", name="ck_fixed_assets_salvage_le_cost"),
    )

    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(100), default="")
    acquired_date: Mapped[date_] = mapped_column(Date, index=True)
    cost: Mapped[float] = mapped_column(Numeric(18, 0))
    #: ارزش اسقاط — بخشی که مستهلک نمی‌شود. مبنای استهلاک = cost − salvage_value.
    salvage_value: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    useful_life_months: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(20), default="straight_line", server_default="straight_line")
    #: مجموع استهلاکِ ثبت‌شده تا امروز. ارزش دفتری = cost − accumulated_depreciation.
    accumulated_depreciation: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    is_disposed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    disposed_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    depreciation_entries: Mapped[list["DepreciationEntry"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )


class DepreciationEntry(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """استهلاکِ یک دارایی برای یک دوره‌ی مشخص — گره‌خورده به سند حسابداری‌اش.

    قید یکتای (دارایی، دوره) عمداً است: بدون آن، اجرای دوباره‌ی استهلاکِ یک ماه دو
    برابر هزینه ثبت می‌کرد و ارزش دفتری را بی‌سر‌و‌صدا زیر واقعیت می‌برد.
    """

    __tablename__ = "depreciation_entries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "asset_id", "period_date", name="uq_depreciation_asset_period"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fixed_assets.id"))
    #: روزِ نماینده‌ی دوره (معمولاً پایان ماه). ذخیره‌ی میلادی؛ تبدیل شمسی فقط در UI.
    period_date: Mapped[date_] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    asset: Mapped["FixedAsset"] = relationship(back_populates="depreciation_entries")
