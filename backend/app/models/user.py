import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

# نقش‌های پیش‌فرض و اکشن‌های هر ماژول - permissions مثال: {"invoices": ["view", "create"], "accounting": ["view"]}
DEFAULT_ROLES: list[dict] = [
    {
        "key": "owner",
        "name": "مدیر/مالک",
        "permissions": {"*": ["view", "create", "update", "delete", "approve"]},
    },
    {
        "key": "accountant",
        "name": "حسابدار",
        "permissions": {
            "accounting": ["view", "create", "update", "approve"],
            "invoices": ["view", "create", "update"],
            "checks_bank": ["view", "create", "update"],
            "payroll": ["view"],
            "assets": ["view", "create", "update", "approve"],
            # حسابدار می‌تواند صورتحساب را به سامانه بفرستد ولی «update» ندارد، پس
            # اعتبارنامه و کلید خصوصیِ امضا فقط در اختیار مالک می‌ماند.
            "moadian": ["view", "approve"],
            "calendar": ["view", "create", "update", "delete"],
            "crm": ["view"],
            "manufacturing": ["view", "create", "update"],
        },
    },
    {
        "key": "salesperson",
        "name": "فروشنده/صندوق‌دار",
        "permissions": {
            "invoices": ["view", "create"],
            "inventory": ["view"],
            "calendar": ["view", "create", "update"],
            # فروشنده متولیِ باشگاه مشتریان است: سرنخ می‌گیرد، پیگیری و امتیاز ثبت می‌کند
            "crm": ["view", "create", "update"],
        },
    },
    {
        "key": "warehouse_keeper",
        "name": "انباردار",
        "permissions": {
            "inventory": ["view", "create", "update"],
            "calendar": ["view", "create", "update"],
            # انباردار متولیِ تولید است: فرمول و سفارشِ تولید را می‌سازد و مدیریت می‌کند
            "manufacturing": ["view", "create", "update"],
        },
    },
    {
        "key": "payroll_officer",
        "name": "مسئول حقوق و دستمزد",
        "permissions": {
            "payroll": ["view", "create", "update", "approve"],
            "calendar": ["view", "create", "update"],
        },
    },
    {
        "key": "demo",
        "name": "دمو (فقط مشاهده)",
        # عمداً بدون wildcard: هر ماژول باید صراحتاً فهرست شود. قبلاً {"*": ["view"]} بود
        # که به‌طور ناخواسته ماژول billing را هم پوشش می‌داد و چون رمز این حساب روی سایت
        # عمومی نمایش داده می‌شود، داده‌ی هویتی همه‌ی مشتریان پولی قابل خواندن شده بود.
        "permissions": {
            "accounting": ["view"],
            "invoices": ["view"],
            "inventory": ["view"],
            "checks_bank": ["view"],
            "payroll": ["view"],
            "assets": ["view"],
            "calendar": ["view"],
            "crm": ["view"],
            "manufacturing": ["view"],
        },
    },
]


class Role(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_roles_tenant_key"),
    )

    key: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(100))
    permissions: Mapped[dict] = mapped_column(JSONB, default=dict)

    def has_permission(self, module: str, action: str) -> bool:
        for mod_key in (module, "*"):
            actions = self.permissions.get(mod_key)
            if actions and (action in actions or "*" in actions):
                return True
        return False


class User(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    #: لحظه‌ی تأییدِ شماره‌ی موبایل با کدِ پیامکی. NULL یعنی تأییدنشده. با هر تغییرِ
    #: `phone` دوباره NULL می‌شود، پس مقدارِ ناتهی همیشه یعنی «همین شماره تأیید شده» —
    #: مبنای بازیابیِ رمز با پیامک، که فقط به شماره‌ی تأییدشده کد می‌فرستد.
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    #: نسل توکن‌های معتبر. با هر تغییر رمز یکی زیاد می‌شود و همه‌ی توکن‌های نسل قبل
    #: را باطل می‌کند.
    #:
    #: توکن‌های ما stateless‌اند و لیست ابطال ندارند، پس بدون این ستون عوض کردن رمز
    #: هیچ اثری روی نشست‌های باز نداشت: کسی که توکن دزدیده بود تا انقضای طبیعی
    #: (۸ ساعت) دسترسی داشت، حتی بعد از اینکه قربانی رمزش را عوض می‌کرد. یعنی
    #: دقیقاً کاری که کاربر برای بیرون کردن مهاجم انجام می‌دهد، کار نمی‌کرد.
    #:
    #: **چرا شمارنده و نه مهر زمان:** نسخه‌ی اول این را با مقایسه‌ی `iat` توکن و
    #: زمان آخرین تغییر رمز پیاده کرده بودم. `iat` در JWT ثانیه‌ی صحیح است، پس
    #: توکنی که در *همان ثانیه‌ی* تغییر رمز صادر شده بود زنده می‌ماند — یک پنجره‌ی
    #: یک‌ثانیه‌ای که تستش گاهی سبز و گاهی قرمز می‌شد. شمارنده اصلاً ساعت را وارد
    #: مقایسه نمی‌کند و این دسته از باگ را حذف می‌کند، نه اینکه کوچکش کند.
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    #: آخرین ورودِ موفق. NULL یعنی هرگز وارد نشده (مثلاً مالکی که همین حالا دستی
    #: ساخته شده و رمزش را هنوز به او نداده‌ایم). فقط مسیرهای اعتبارسنجی‌شده‌ی ورود
    #: آن را جلو می‌برند؛ برای پنلِ مدیریت («آخرین فعالیت») خوانده می‌شود.
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # نقش روی User نمی‌نشیند: یک نفر می‌تواند در یک کسب‌وکار حسابدار و در دیگری فقط
    # بیننده باشد، پس نقش خاصیتِ «عضویت» است نه خاصیتِ «کاربر».
    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")  # noqa: F821
