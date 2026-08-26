"""رجیستریِ ماژول‌ها و منطقِ «مجاز/فعال» — منبعِ واحدِ حقیقتِ سیستمِ شخصی‌سازیِ پنل.

دو لایه:
  1) **حقِ دسترسی (allowed):** کدام ماژول‌ها را این کسب‌وکار *مجاز* است داشته باشد.
     ماژول‌های عادی برای همه مجازند؛ ماژول‌های **محدود** (`RESTRICTED_MODULES`) فقط اگر
     سوپرادمین در `tenant.granted_modules` گذاشته باشد. این لایه در بک‌اند اعمال می‌شود
     (`require_module` در deps) — پس پنهان‌کردنِ منو کافی نیست، دسترسیِ API هم بسته است.
  2) **نمایش (enabled):** مالکِ کسب‌وکار از میانِ ماژول‌های مجاز، هرکدام را خواست در پنل
     روشن/خاموش می‌کند. خاموش = فقط پنهان از منو، بی‌حذفِ داده. در `tenant.enabled_modules`
     (per-tenant) ذخیره می‌شود؛ `None` یعنی «هنوز شخصی‌سازی نشده» → همه‌ی ماژول‌های مجاز
     دیده می‌شوند (سازگاریِ عقب‌رو برای حساب‌های موجود).

ماژول‌های `CORE` همیشه روشن و مجازند و خاموش‌شدنی نیستند (ستونِ فقراتِ برنامه).
برچسب‌های فارسی سمتِ فرانت (navModel) می‌مانند تا دوباره‌کاری نشود؛ این‌جا فقط کلیدها،
دسته‌ها و قالب‌های صنفی تعریف می‌شوند.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.tenant import Tenant

#: ماژول‌های ستونِ فقرات — همیشه روشن، همیشه مجاز، غیرقابلِ خاموش‌کردن.
CORE_MODULES: tuple[str, ...] = ("overview", "contacts", "reports")

#: ماژول‌های اختیاری که مالک می‌تواند روشن/خاموش کند (ترتیب = ترتیبِ نمایش در تنظیمات).
OPTIONAL_MODULES: tuple[str, ...] = (
    "sales",
    "pos",
    "installments",
    "crm",
    "purchases",
    "inventory",
    "manufacturing",
    "accounting",
    "banking",
    "fixedassets",
    "payroll",
    "integration",
    "calendar",
    "onboarding",
)

#: زیرمجموعه‌ی اختیاری‌ها که «حقِ دسترسی»شان فقط با گرنتِ سوپرادمین باز می‌شود و در
#: بک‌اند هم گیت می‌شوند (require_module). «تولید» نمونه‌ی اصلی است.
#:
#: «اتصال فروشگاه» هم این‌جاست: راه‌اندازیِ فروشگاه (دامنه، درگاه، کلیدِ publishable)
#: کاری است که پشتیبانی همراهِ مشتری انجام می‌دهد، نه چیزی که هر حسابِ تازه باید
#: نیمه‌تنظیم‌شده در منو ببیند. پیش‌فرض خاموش؛ سوپرادمین برای هر اکانت بازش می‌کند.
RESTRICTED_MODULES: tuple[str, ...] = ("manufacturing", "integration")

#: همه‌ی کلیدهای ماژولِ کسب‌وکار (core + اختیاری) — برای اعتبارسنجی.
ALL_BUSINESS_MODULES: tuple[str, ...] = CORE_MODULES + OPTIONAL_MODULES

#: قالب‌های صنفی — مجموعه‌ی *اختیاری‌های* پیش‌فرضِ روشن برای هر صنف. core همیشه روشن است
#: پس این‌جا نمی‌آید. کلیدِ صنف با `INDUSTRIES` سمتِ فرانت (برچسب فارسی) یکی است.
INDUSTRY_TEMPLATES: dict[str, tuple[str, ...]] = {
    # عمومی: همه‌ی اختیاری‌ها جز محدودها (تولید با گرنتِ سوپرادمین می‌آید).
    "general": (
        "sales", "pos", "installments", "crm", "purchases", "inventory",
        "accounting", "banking", "fixedassets", "payroll",
        "calendar", "onboarding",
    ),
    # تولیدی: خط تولید فعال، بدونِ صندوق/باشگاه/اقساط.
    "manufacturing": (
        "sales", "purchases", "inventory", "manufacturing", "accounting",
        "banking", "fixedassets", "payroll", "calendar", "onboarding",
    ),
    # خرده‌فروشی: صندوق و باشگاه پررنگ، بدونِ تولید/حقوق/دارایی.
    "retail": (
        "sales", "pos", "installments", "crm", "purchases", "inventory",
        "accounting", "banking", "calendar", "onboarding",
    ),
    # خدماتی: بدونِ انبار/صندوق/تولید.
    "services": (
        "sales", "crm", "accounting", "banking", "payroll", "calendar", "onboarding",
    ),
    # پخش: تمرکز روی خرید/انبار (ماژولِ «پخشِ من» جدا با tenant.kind می‌آید).
    "distribution": (
        "sales", "purchases", "inventory", "accounting", "banking", "calendar", "onboarding",
    ),
}

#: صنفِ پیش‌فرضِ حسابِ تازه.
DEFAULT_INDUSTRY = "general"


def allowed_modules(tenant: "Tenant") -> set[str]:
    """مجموعه‌ی ماژول‌هایی که این کسب‌وکار مجازِ داشتنشان است (لایه‌ی حقِ دسترسی)."""
    granted = set(tenant.granted_modules or [])
    allowed = set(CORE_MODULES)
    for key in OPTIONAL_MODULES:
        if key in RESTRICTED_MODULES:
            if key in granted:
                allowed.add(key)
        else:
            allowed.add(key)
    return allowed


def enabled_modules(tenant: "Tenant") -> list[str]:
    """کلیدهای ماژولِ *روشن* (ترجیحِ مالک) — شاملِ core (همیشه روشن).

    `None` (شخصی‌سازی‌نشده) = همه‌ی اختیاری‌ها روشن، تا حساب‌های موجود چیزی از دست ندهند.
    فیلترِ «مجاز» این‌جا اعمال نمی‌شود؛ فرانت `enabled ∩ allowed` را برای نمایش حساب می‌کند
    و صفحه‌ی تنظیمات می‌تواند «روشنِ ولی قفل» را از «مجازِ ولی خاموش» تشخیص دهد.
    """
    if tenant.enabled_modules is None:
        optional_on = list(OPTIONAL_MODULES)
    else:
        stored = set(tenant.enabled_modules)
        optional_on = [k for k in OPTIONAL_MODULES if k in stored]
    return list(CORE_MODULES) + optional_on


def is_module_visible(tenant: "Tenant", key: str) -> bool:
    """آیا ماژول باید در پنل دیده شود = روشن و مجاز."""
    return key in set(enabled_modules(tenant)) and key in allowed_modules(tenant)


def set_enabled(tenant: "Tenant", keys: list[str]) -> list[str]:
    """ترجیحِ نمایشِ مالک را ذخیره می‌کند — فقط اختیاری‌های *مجاز*.

    core خودکار روشن است پس ذخیره نمی‌شود؛ کلیدهای نامعتبر/غیرمجاز کنار گذاشته می‌شوند
    (fail-safe: مالک نمی‌تواند با این مسیر ماژولِ محدودِ گرنت‌نشده را روشن کند).

    یک استثنا: ماژولِ محدودی که *از قبل* روشن بوده روشن می‌ماند. وگرنه هر بار که مالک
    تنظیماتِ پنل را ذخیره می‌کرد، ترجیحش پاک می‌شد و گرنتِ بعدیِ سوپرادمین بی‌اثر
    می‌ماند — یعنی سوپرادمین «فعال» می‌کرد و مالک همچنان چیزی نمی‌دید. نگه‌داشتنِ
    ترجیح روشن‌کردن نیست؛ گیتِ واقعی همچنان `allowed` است.
    """
    allowed = allowed_modules(tenant)
    already = set(tenant.enabled_modules or [])
    clean = [
        k for k in OPTIONAL_MODULES if k in set(keys) and (k in allowed or k in already)
    ]
    tenant.enabled_modules = clean
    return clean


def set_industry(tenant: "Tenant", industry: str, *, grant_restricted: bool = True) -> None:
    """صنف را می‌گذارد و نمایش را به قالبِ همان صنف بازنشانی می‌کند.

    `grant_restricted`: اگر True (پیش‌فرض، فراخوانِ سوپرادمین) ماژول‌های محدودِ داخلِ قالب
    هم گرنت می‌شوند. در **ثبت‌نامِ خودسرویس** با False صدا می‌شود تا کاربر با اعلامِ صنف،
    ماژولِ محدود (مثلِ تولید) را خودش باز نکند — آن در نمایش می‌ماند ولی تا گرنتِ سوپرادمین
    «قفل» است.
    """
    if industry not in INDUSTRY_TEMPLATES:
        raise ValueError("صنفِ نامعتبر")
    template = INDUSTRY_TEMPLATES[industry]
    tenant.industry = industry
    if grant_restricted:
        granted = set(tenant.granted_modules or [])
        granted.update(k for k in template if k in RESTRICTED_MODULES)
        tenant.granted_modules = sorted(granted)

    # بازنشانی به قالب، *به‌جز* ماژول‌های محدودی که سوپرادمین صریحاً به این اکانت داده.
    # گرنت یک تصمیمِ موردیِ اوست و نباید با عوض‌کردنِ صنف — که یک پیش‌فرضِ کلی است —
    # بی‌صدا پس گرفته شود. «اتصال فروشگاه» در هیچ قالبی نیست، پس بدونِ این استثنا هر
    # تغییرِ صنف آن را از منو حذف می‌کرد.
    on = set(template) | {k for k in (tenant.granted_modules or []) if k in RESTRICTED_MODULES}
    tenant.enabled_modules = [k for k in OPTIONAL_MODULES if k in on]


def set_grants(tenant: "Tenant", granted_keys: list[str]) -> list[str]:
    """گرنتِ سوپرادمین برای ماژول‌های محدود را می‌گذارد (فقط کلیدهای محدودِ معتبر).

    ماژولی که *تازه* گرنت می‌شود در نمایش هم روشن می‌شود. بدونِ این، گرنت روی حسابی
    که قبلاً پنلش را شخصی‌سازی کرده هیچ اثری در منو نداشت: `allowed` باز می‌شد ولی کلید
    در `enabled_modules` نبود (قالبِ صنفش هرگز نداشته)، پس سوپرادمین «فعال» می‌کرد و
    مالک همچنان چیزی نمی‌دید. گرنت یک تصمیمِ صریحِ موردی است و باید یک کلید باشد، نه دو.

    لغوِ گرنت ترجیح را دست نمی‌زند — نمایش با `allowed` بسته می‌شود، و اگر بعداً دوباره
    گرنت داده شود ماژول همان‌جا برمی‌گردد.
    """
    clean = sorted({k for k in granted_keys if k in RESTRICTED_MODULES})
    before = set(tenant.granted_modules or [])
    tenant.granted_modules = clean

    added = [k for k in clean if k not in before]
    # `None` یعنی «شخصی‌سازی‌نشده» = همه‌ی اختیاری‌ها روشن‌اند؛ آن‌جا کاری لازم نیست.
    if added and tenant.enabled_modules is not None:
        on = set(tenant.enabled_modules) | set(added)
        tenant.enabled_modules = [k for k in OPTIONAL_MODULES if k in on]
    return clean
