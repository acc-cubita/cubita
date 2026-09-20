"""شکلِ ورودی/خروجیِ شخصی‌سازیِ پنل (ماژول‌ها و صنف)."""
from pydantic import BaseModel, field_validator

from app.services.trades import is_valid_trade


class ModulesStateOut(BaseModel):
    """وضعیتِ کاملِ ماژول‌های یک کسب‌وکار — منبعِ صفحه‌ی «شخصی‌سازیِ پنل».

    فرانت وضعیتِ هر ماژول را از این می‌سازد:
      core → همیشه روشن · (کلید ∉ allowed) → «قفل» (محدود، گرنت‌نشده) · (∈ enabled) → روشن ·
      وگرنه خاموش.
    """
    industry: str
    #: صنفِ ریز — «چه می‌فروشد». `None` یعنی هنوز اعلام نشده. فهرستِ گزینه‌ها از
    #: `/api/trades` می‌آید، نه از این‌جا: همان فهرست را صفحه‌ی ثبت‌نام هم می‌خواهد
    #: و آن‌جا هنوز توکنی نیست.
    trade: str | None = None
    #: کلیدِ ماژول‌های روشن (ترجیحِ مالک، شاملِ core).
    enabled: list[str]
    #: کلیدِ ماژول‌های مجاز (حقِ دسترسی).
    allowed: list[str]
    #: رجیستریِ سرور (منبعِ واحد) تا فرانت کلیدها را hardcode نکند.
    core: list[str]
    optional: list[str]
    restricted: list[str]
    industries: list[str]


class SetModulesIn(BaseModel):
    """ترجیحِ نمایشِ مالک — فهرستِ کلیدِ ماژول‌های اختیاریِ روشن. غیرمجاز/نامعتبرها
    سمتِ سرور کنار گذاشته می‌شوند."""
    enabled: list[str]


class SetTradeIn(BaseModel):
    """اعلامِ صنفِ کسب‌وکار توسطِ مالک. `None` یعنی «اعلام‌نشده» و پاک‌کردنش مجاز است."""

    trade: str | None = None

    @field_validator("trade")
    @classmethod
    def _trade(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not is_valid_trade(v):
            raise ValueError("صنف نامعتبر است")
        return v
