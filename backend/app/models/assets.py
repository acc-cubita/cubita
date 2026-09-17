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

#: `placement` اولین استقرارِ دارایی است و `transfer` هر جابه‌جاییِ بعدی. جدا
#: نگه داشته می‌شوند چون در «فهرست جابه‌جایی‌ها و تحویل‌ها» دو معنای متفاوت‌اند:
#: یکی ورودِ دارایی به مجموعه، دیگری تغییرِ دستِ آن.
ASSIGNMENT_KINDS = ("placement", "transfer")

#: سه راهِ خروجِ دارایی از مجموعه. حسابداری‌شان یکی است (بهای تمام‌شده و استهلاکِ
#: انباشته از دفتر خارج می‌شوند و مابه‌التفاوت سود/زیان می‌شود)؛ فرقشان در مبلغِ
#: دریافتی است: `sale` معمولاً دارد، `scrap` (اسقاط/داغی) و `donation` (اهدا) صفر.
#: جدا نگه‌داشتنشان یعنی «چقدر دارایی فروختیم» و «چقدر اسقاط کردیم» دو عددِ
#: متفاوت می‌مانند — همان تفکیکی که گزارشِ خروج بر پایه‌اش ساخته می‌شود.
DISPOSAL_TYPES = ("sale", "scrap", "donation")
_DISPOSAL_IN_SQL = ", ".join(f"'{t}'" for t in DISPOSAL_TYPES)


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

    #: **وضعیتِ استقرارِ امروز** — همیشه برابرِ آخرین ردیفِ `assignments` است.
    #: روی خودِ دارایی هم نگه داشته می‌شود تا «الان دستِ کیست؟» یک خواندن باشد نه
    #: یک زیرپرس‌وجوی مرتب‌شده روی تاریخچه؛ تاریخچه جای خودش محفوظ است.
    custodian_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True, index=True
    )
    location: Mapped[str] = mapped_column(String(200), default="", server_default="")
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )

    depreciation_entries: Mapped[list["DepreciationEntry"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["AssetAssignment"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    disposals: Mapped[list["AssetDisposal"]] = relationship(
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
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    asset: Mapped["FixedAsset"] = relationship(back_populates="depreciation_entries")


class AssetAssignment(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """تحویل/استقرارِ دارایی و هر جابه‌جاییِ بعدی‌اش — دفترِ «الان دستِ کیست».

    **مبدأ هم ذخیره می‌شود، نه فقط مقصد.** بدونِ `from_*` تاریخچه فقط زنجیره‌ای از
    مقصدهاست و «از چه کسی به چه کسی» را باید از ردیفِ قبلی حدس زد — که با
    حذف/ابطالِ یک ردیف یا ثبتِ خارج از ترتیبِ تاریخ، غلط از آب درمی‌آید.

    هیچ اثرِ حسابداری ندارد: جابه‌جاییِ دارایی بینِ جمعداران مالکیت را عوض
    نمی‌کند، پس سندی هم نمی‌خورد.
    """

    __tablename__ = "asset_assignments"
    __table_args__ = (
        CheckConstraint(f"kind IN {ASSIGNMENT_KINDS}", name="ck_asset_assignments_kind"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fixed_assets.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20), default="placement", server_default="placement")
    assignment_date: Mapped[date_] = mapped_column(Date, index=True)

    to_custodian_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True, index=True
    )
    to_location: Mapped[str] = mapped_column(String(200), default="", server_default="")
    to_cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )

    from_custodian_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True
    )
    from_location: Mapped[str] = mapped_column(String(200), default="", server_default="")
    from_cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )

    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    asset: Mapped["FixedAsset"] = relationship(back_populates="assignments")


class AssetDisposal(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """خروجِ دارایی از دفاتر — فروش، اسقاط یا اهدا، همراه با سندش.

    **چرا اعدادِ لحظه‌ی خروج اینجا عکس‌برداری می‌شوند** (`cost_at_disposal`،
    `accumulated_at_disposal`، `book_value`): بعد از خروج، بهای تمام‌شده و استهلاکِ
    انباشته‌ی دارایی دیگر معنای «الان» ندارند و خودِ دارایی هم ممکن است بعداً ویرایش
    شود. بدونِ عکس، گزارشِ خروج با هر ویرایشِ بعدی بی‌صدا عوض می‌شد و سودِ گزارش‌شده
    دیگر با سندی که واقعاً خورده نمی‌خواند. `gain_loss` هم مشتق‌نشدنی نگه داشته
    می‌شود چون همان عددی است که در سند نشسته.

    `gain_loss` مثبت یعنی سود (مبلغِ دریافتی > ارزشِ دفتری)، منفی یعنی زیان.
    اسقاط و اهدا تقریباً همیشه منفی‌اند — و این همان چیزی است که تا پیش از این
    هیچ‌جا ثبت نمی‌شد: دارایی فقط یک پرچم می‌خورد و بهای کاملش تا ابد در ترازنامه
    می‌ماند.
    """

    __tablename__ = "asset_disposals"
    __table_args__ = (
        CheckConstraint(f"disposal_type IN ({_DISPOSAL_IN_SQL})", name="ck_asset_disposals_type"),
        CheckConstraint("proceeds >= 0", name="ck_asset_disposals_proceeds_nonneg"),
        #: یک دارایی دو بار خارج نمی‌شود. `is_disposed` هم همین را می‌گوید، ولی آن
        #: یک پرچمِ قابلِ‌ویرایش است و این یک قیدِ پایگاه‌داده.
        UniqueConstraint("tenant_id", "asset_id", name="uq_asset_disposal_once"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fixed_assets.id", ondelete="CASCADE"), index=True
    )
    disposal_type: Mapped[str] = mapped_column(String(20), default="sale", server_default="sale")
    disposal_date: Mapped[date_] = mapped_column(Date, index=True)
    #: مبلغِ دریافتی بابتِ واگذاری. برای اسقاط/اهدا صفر است.
    proceeds: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: حسابی که مبلغِ دریافتی رویش می‌نشیند (صندوق/بانک/دریافتنی). فقط وقتی
    #: `proceeds > 0` باشد لازم است.
    settlement_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    #: خریدار — اختیاری و فقط اطلاعاتی؛ اگر مبلغ به «دریافتنی» برود، تفصیلی هم می‌شود.
    buyer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True, index=True
    )

    cost_at_disposal: Mapped[float] = mapped_column(Numeric(18, 0))
    accumulated_at_disposal: Mapped[float] = mapped_column(Numeric(18, 0))
    book_value: Mapped[float] = mapped_column(Numeric(18, 0))
    gain_loss: Mapped[float] = mapped_column(Numeric(18, 0))

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    asset: Mapped["FixedAsset"] = relationship(back_populates="disposals")
