"""مستأجر، عضویت، و ادمین پلتفرم.

تفکیک عمدی «صفحه‌ی کنترل» از «صفحه‌ی داده»:

- Tenant/Membership/PlatformAdmin سراسری‌اند و RLS ندارند.
- کاربر هم سراسری است، چون یک حسابدار مستقل می‌تواند دفتر چند کسب‌وکار را ببرد.
  تعلقش با Membership بیان می‌شود، نه با ستونی روی خودش. این از همین ابتدا انجام
  می‌شود چون افزودن رابطه‌ی چند‌به‌چند بعد از داشتن مشتری یعنی مهاجرت دوباره‌ی auth.
- PlatformAdmin عمداً یک نقش در RBAC مستأجر نیست. ریشه‌ی نشتی قبلی همین بود که
  کنترل‌پنل فروش و دفتر مشتری یک سیستم مجوز مشترک داشتند و یک نقش با wildcard
  به داده‌ی همه‌ی مشتری‌ها رسید.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class TenantMixin:
    """ستون مستأجر. کنار UUIDPKMixin روی هر مدل مستأجرمحور می‌نشیند.

    اعلانی بودنش عمدی است: افزودن مستأجر به مدل جدید یک خط است و *نبودش* در
    بازبینی دیده می‌شود — و اگر دیده هم نشود، تست introspection می‌گیردش.
    """

    @declared_attr
    def tenant_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )


class Tenant(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | suspended | cancelled

    #: نوعِ حساب در بازارِ عمده‌فروشیِ درون‌پلتفرمی — انحصاری:
    #:   standard    = کسب‌وکارِ عادی (پیش‌فرض؛ حساب‌های موجود بی‌تغییر می‌مانند)
    #:   distributor = شرکتِ پخش (کاتالوگ منتشر می‌کند، سفارش می‌گیرد) → ماژولِ «پخشِ من»
    #:   retailer    = فروشگاه (از پخش‌کننده‌ها سفارش می‌دهد) → ماژولِ «بازارِ خرید»
    #: ماژول‌های بازار با همین فیلد گیت می‌شوند (مثلِ locked_features برای مؤدیان/فروشگاه‌ساز).
    kind: Mapped[str] = mapped_column(
        String(20), default="standard", server_default="standard", nullable=False
    )

    #: سقف کاربران. NULL یعنی نامحدود (پلن سازمانی).
    #:
    #: این مقدار موقع ساخت مستأجر از `Plan.max_users` گرفته می‌شود و بعد از آن ثابت
    #: می‌ماند. **این هنوز اشتراک نیست:** جدول subscriptions وجود ندارد، پس ارتقای
    #: پلن سقف را خودکار بالا نمی‌برد و باید دستی عوض شود. سقف ثابتِ قابل اعمال از
    #: `Plan.max_users`ی که تعریف شده بود ولی هیچ‌جا خوانده نمی‌شد بهتر است، چون
    #: بدون هیچ سقفی دعوت یک منبع نامحدود است.
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: حسابِ آزمایشیِ رایگان (۱۴ روزه). ثبت‌نامِ خودسرویس True می‌سازد و خریدِ پلن آن را
    #: False می‌کند (تبدیل به مشتریِ واقعی، در همان جا، بدون از دست رفتنِ دیتا). دو رفتار
    #: از این پرچم مشتق می‌شوند: مودیان/اتصال‌فروشگاه قفل‌اند، و بعد از انقضا کلِ حساب
    #: قفل می‌شود (نه فقط‌خواندنی) چون داده‌ی آزمایشی سندِ قانونیِ کسی نیست.
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    #: لحظه‌ی ارسالِ یادآوریِ «نزدیکِ انقضای آزمایشی» — تا کرون هر حساب را فقط یک بار
    #: یادآوری کند، نه هر روز.
    trial_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    #: ── شخصی‌سازیِ پنل بر اساسِ صنف/شرکت (سرویسِ منطق: app/services/modules.py) ──
    #: صنفِ کسب‌وکار — قالبِ پیش‌فرضِ ماژول‌ها را تعیین می‌کند (general | manufacturing | ...).
    industry: Mapped[str] = mapped_column(
        String(30), default="general", server_default="general", nullable=False
    )
    #: ترجیحِ نمایشِ مالک: فهرستِ کلیدِ ماژول‌های اختیاریِ *روشن*. NULL = شخصی‌سازی‌نشده →
    #: همه‌ی ماژول‌های مجاز دیده می‌شوند (سازگاریِ عقب‌رو). core هرگز این‌جا نمی‌آید.
    enabled_modules: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    #: قاعده‌ی کدینگِ چارت: رقمِ افزوده در هر سطح (گروه، کل، معین، تفصیلی).
    #: NULL = پیش‌فرضِ سرویس، پس حساب‌های موجود با ارتقا چیزی عوض نمی‌کنند.
    account_code_widths: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    #: سطحِ اجبارِ تفصیلی روی حساب‌های «تفصیلی پذیر» — انتخابِ خودِ کسب‌وکار:
    #:   strict   = اجباری همه‌جا (سندِ دستی و ردیفِ ماژول‌ها)
    #:   hybrid   = فقط سندِ دستی (پیش‌فرض)
    #:   floating = هیچ‌جا مسدود نشود؛ فقط گزارش
    #: NULL = پیش‌فرضِ سرویس. منطق در `app/services/tafsili.py`.
    #: گزارشِ «ردیف‌های بدونِ تفصیلی» در **هر سه** حالت کار می‌کند؛ این انتخاب فقط
    #: تعیین می‌کند چه چیزی مسدود شود، نه چه چیزی دیده شود.
    tafsili_enforcement: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: سیاستِ کنترلِ شماره‌ی چکِ پرداختنی:
    #:   off  = شماره آزاد است (پیش‌فرض — رفتارِ امروز)
    #:   book = چکِ پرداختنی باید از یک دسته‌چکِ باز صادر شود
    #: NULL = پیش‌فرضِ سرویس، پس هیچ کسب‌وکارِ موجودی با ارتقا رفتارش عوض نمی‌شود.
    #:
    #: **این پرچم بازه و تکراری‌نبودنِ برگ را کنترل نمی‌کند.** آن‌ها در هر دو حالت
    #: سنجیده می‌شوند: اگر کاربر دسته‌ای را انتخاب کرد، شماره باید واقعاً از همان
    #: دسته و خرج‌نشده باشد — وگرنه «برگِ مانده» عددِ دروغ می‌دهد. منطق در
    #: `app/services/checkbooks.py`.
    cheque_number_control: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: سیاستِ صدورِ فاکتور فروش — «ثبت فاکتور» چه‌قدر کار انجام دهد:
    #:   immediate = همان لحظه سندِ حسابداری و خروجِ انبار هم می‌زند (پیش‌فرض)
    #:   staged    = فاکتور فقط سندِ **تجاری** است؛ سند و خروج جدا صادر می‌شوند
    #: NULL = پیش‌فرضِ سرویس.
    #:
    #: **چرا پیش‌فرض `immediate` است و نه رفتارِ تازه.** جداسازیِ فاکتور از خروجِ
    #: انبار یک قابلیتِ درست است — کسب‌وکاری که فاکتور را امروز می‌دهد و کالا را
    #: هفته‌ی بعد، بدونش نمی‌تواند درست کار کند. ولی برای مغازه‌ای که فاکتور و
    #: تحویل یک لحظه‌اند، دو دکمه‌ی اضافه یعنی دو فراموشیِ ممکن: فاکتوری که سند
    #: ندارد و کالایی که از انبار کم نشده. پس **انتخاب** است، نه حکم.
    #:
    #: منطق در `app/services/sales_posting.py`.
    sales_invoice_posting: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: «حقِ دسترسی»: ماژول‌های محدودی که سوپرادمین به این اکانت داده (مثلِ تولید).
    granted_modules: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )

    memberships: Mapped[list["Membership"]] = relationship(back_populates="tenant")


class Membership(UUIDPKMixin, TimestampMixin, Base):
    """پیوند هویت سراسری به یک مستأجر، همراه با نقشِ همان مستأجر.

    نقش اینجا می‌نشیند و نه روی User، چون یک نفر می‌تواند در یک کسب‌وکار حسابدار
    و در کسب‌وکار دیگر فقط بیننده باشد.
    """

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "tenant_id", name="uq_memberships_user_tenant"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | invited | disabled

    #: مجوزِ اختصاصیِ همین کاربر در همین کسب‌وکار. NULL یعنی «همان مجوزِ نقش» —
    #: پس عضویت‌های موجود دقیقاً مثل قبل رفتار می‌کنند. مقدارِ غیرِ NULL کاملاً
    #: جایگزینِ مجوزِ نقش می‌شود، نه اینکه با آن ادغام شود: ادغام یعنی مالک هرگز
    #: نمی‌تواند دسترسی‌ای را که نقش می‌دهد *بگیرد*.
    permissions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(back_populates="memberships")  # noqa: F821
    role: Mapped["Role"] = relationship()  # noqa: F821


class PlatformAdmin(UUIDPKMixin, TimestampMixin, Base):
    """ادمین خودِ کوبیتا. جدا از RBAC مستأجر، عمداً."""

    __tablename__ = "platform_admins"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship()  # noqa: F821
