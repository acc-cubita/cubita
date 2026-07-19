from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"

    database_url: str = "postgresql+psycopg://hesabdari:hesabdari@localhost:5432/hesabdari"

    jwt_secret: str = "changeme"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    allowed_origins: str = "http://localhost:5173"

    # ادمین پلتفرم (کنترل‌پنل فروش خودِ کوبیتا) — عمداً از RBAC مستأجر جداست، چون آن سیستم
    # wildcard دارد و هر نقشی با "*" به‌طور ناخواسته به داده‌ی همه‌ی مشتریان دسترسی می‌گرفت.
    # خالی = دسترسی برای همه بسته (fail closed). فهرست ایمیل با کاما جدا شود.
    platform_admin_emails: str = ""

    # اکانت سرویس ادمین روی سایت فروشگاهی؛ هر sync دوباره لاگین می‌کند تا نیازی به نگهداری توکن بلندمدت نباشد
    storefront_api_base_url: str = ""
    storefront_admin_email: str = ""
    storefront_admin_password: str = ""

    # درگاه پرداخت زرین‌پال برای خرید پلن‌های سایت تجاری cubita.ir
    zarinpal_merchant_id: str = "00000000-0000-0000-0000-000000000000"
    zarinpal_sandbox: bool = True
    backend_url: str = "http://localhost:8000"  # برای ساخت callback_url که زرین‌پال بعد از پرداخت به آن بازمی‌گردد
    marketing_site_url: str = "http://localhost:5174"  # سایت تجاری cubita.ir؛ بعد از verify کاربر به اینجا ریدایرکت می‌شود

    # خودِ نرم‌افزار حسابداری (جایی که کاربر لاگین می‌کند). لینک بازیابی رمز و پذیرش دعوت
    # به اینجا می‌روند، نه به سایت تجاری — این دو دامنه‌ی متفاوت‌اند و اشتباه گرفتنشان
    # یعنی لینک بازیابی به صفحه‌ای می‌رود که فرم بازیابی ندارد.
    app_url: str = "http://localhost:5173"

    # سقف کاربر برای کسب‌وکاری که خودش ثبت‌نام کرده (هنوز پلنی نخریده).
    # ۱ یعنی نمی‌تواند هیچ همکاری دعوت کند و قابلیت تیمی را اصلاً نمی‌بیند؛ عدد کوچکِ
    # بزرگ‌تر از ۱ اجازه می‌دهد ارزش را بچشد بدون اینکه ثبت‌نام رایگان بی‌سقف شود.
    signup_default_max_users: int = 3

    # اعلان ایمیلی به مدیر وقتی یک خرید جدید در سایت تجاری پرداخت می‌شود (SMTP روی Gmail)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    admin_notify_email: str = ""

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def platform_admin_emails_list(self) -> list[str]:
        return [e.strip().lower() for e in self.platform_admin_emails.split(",") if e.strip()]


KNOWN_ENVS = ("development", "staging", "production")
WEAK_JWT_SECRETS = ("changeme", "", "secret", "changeit", "test")
MIN_JWT_SECRET_LENGTH = 32


def _validate(settings: Settings) -> None:
    """گاردهای fail-closed.

    گارد قبلی فقط وقتی ENV=production بود فعال می‌شد، و همین باعث شد نمونه‌ی واقعی با
    ENV=development اجرا شود در حالی که با پول واقعی کار می‌کرد — که هم بررسی قدرت
    JWT_SECRET را دور می‌زد و هم /api/docs را عمومی نگه می‌داشت. معیار درست «چه چیزی
    در فایل نوشته شده» نیست، «آیا این نمونه با پول واقعی کار می‌کند» است.
    """
    if settings.env not in KNOWN_ENVS:
        raise RuntimeError(f"ENV نامعتبر است: {settings.env!r}. مقادیر مجاز: {', '.join(KNOWN_ENVS)}")

    handles_real_money = not settings.zarinpal_sandbox

    if handles_real_money and not settings.is_production:
        raise RuntimeError(
            "ZARINPAL_SANDBOX=false یعنی این نمونه کارت واقعی شارژ می‌کند، ولی "
            f"ENV={settings.env!r} است. یا ENV=production بگذارید (و گاردهای production فعال شود) "
            "یا ZARINPAL_SANDBOX=true کنید."
        )

    if settings.is_production or handles_real_money:
        if settings.jwt_secret.strip().lower() in WEAK_JWT_SECRETS:
            raise RuntimeError("JWT_SECRET مقدار پیش‌فرض/ضعیف دارد؛ اجرا با پول واقعی مجاز نیست.")
        if len(settings.jwt_secret) < MIN_JWT_SECRET_LENGTH:
            raise RuntimeError(
                f"JWT_SECRET کوتاه است ({len(settings.jwt_secret)} کاراکتر)؛ "
                f"حداقل {MIN_JWT_SECRET_LENGTH} کاراکتر لازم است. "
                'تولید: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    _validate(settings)
    return settings
