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

    # اکانت سرویس ادمین روی سایت فروشگاهی؛ هر sync دوباره لاگین می‌کند تا نیازی به نگهداری توکن بلندمدت نباشد
    storefront_api_base_url: str = ""
    storefront_admin_email: str = ""
    storefront_admin_password: str = ""

    # درگاه پرداخت زرین‌پال برای خرید پلن‌های سایت تجاری cubita.ir
    zarinpal_merchant_id: str = "00000000-0000-0000-0000-000000000000"
    zarinpal_sandbox: bool = True
    backend_url: str = "http://localhost:8000"  # برای ساخت callback_url که زرین‌پال بعد از پرداخت به آن بازمی‌گردد
    marketing_site_url: str = "http://localhost:5174"  # سایت تجاری cubita.ir؛ بعد از verify کاربر به اینجا ریدایرکت می‌شود

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


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production and settings.jwt_secret in ("changeme", ""):
        raise RuntimeError("JWT_SECRET تنظیم نشده؛ اجرا در production با مقدار پیش‌فرض مجاز نیست.")
    return settings
