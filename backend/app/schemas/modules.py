"""شکلِ ورودی/خروجیِ شخصی‌سازیِ پنل (ماژول‌ها)."""
from pydantic import BaseModel


class ModulesStateOut(BaseModel):
    """وضعیتِ کاملِ ماژول‌های یک کسب‌وکار — منبعِ صفحه‌ی «شخصی‌سازیِ پنل».

    فرانت وضعیتِ هر ماژول را از این می‌سازد:
      core → همیشه روشن · (کلید ∉ allowed) → «قفل» (محدود، گرنت‌نشده) · (∈ enabled) → روشن ·
      وگرنه خاموش.
    """
    industry: str
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
