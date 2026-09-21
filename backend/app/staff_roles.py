"""نقش‌های ستادِ کوبیتا — مجوزِ کارکنانِ پلتفرم، نه RBACِ مستأجر.

عمداً همان شکلِ `Role.permissions` را دارد (`{حوزه: [کنش‌ها]}` با وایلدکاردِ `"*"`)
تا در کلِ مخزن **یک** مدلِ ذهنیِ مجوز وجود داشته باشد نه دو تا. ولی فضای نام
کاملاً جداست: حوزه‌های اینجا (`accounts`، `billing`، …) بخش‌های کنترل‌پنلِ ستادند،
نه ماژول‌های حسابداری، و هیچ نقشِ مستأجری هرگز به آن‌ها نمی‌رسد.

دو قدرت **صرف‌نظر از مجوز** فقط دستِ `owner` است و در خودِ اندپوینت گارد می‌شود:
حذفِ کاملِ یک اکانت، و مدیریتِ خودِ کاربرانِ ستاد. مجوزِ دلخواه نمی‌تواند آن‌ها را
باز کند — وگرنه یک `admin` می‌توانست خودش را `owner` کند و گارد بی‌معنا می‌شد.
"""

#: حوزه‌های شناخته‌شده. تستِ `test_staff_roles` نمی‌گذارد نقشی به حوزه‌ی ناشناخته
#: مجوز بدهد — غلطِ املایی در یک کلید وگرنه بی‌صدا یعنی «دسترسی ندارد».
STAFF_AREAS = frozenset(
    {
        "accounts",      # مدیریتِ اکانت‌های مشتری
        "assurance",     # کارتابلِ حسابرسی
        "billing",       # خریدهای سایتِ تجاری و پلن‌ها
        "commissions",   # کمیسیونِ بازارِ عمده‌فروشی
        "errors",        # گزارش‌های خطای کلاینت
        "metrics",       # داشبوردِ درآمد و رشد
        "audit",         # ردِ کارهای ستاد
        "support",       # نشستِ «دیدن به‌نامِ مشتری»
        "staff",         # کاربرانِ ستاد
    }
)

STAFF_ROLES = ("owner", "admin", "finance", "support")

#: برچسبِ فارسی برای نمایش در اپِ ستاد و در ردِ کارها.
STAFF_ROLE_LABELS = {
    "owner": "مالکِ سامانه",
    "admin": "مدیر",
    "finance": "مالی",
    "support": "پشتیبانی",
}

STAFF_ROLE_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "owner": {"*": ["*"]},
    "admin": {
        "accounts": ["view", "create", "edit", "extend", "status", "reset_password"],
        "assurance": ["*"],
        "billing": ["*"],
        "commissions": ["*"],
        "errors": ["view"],
        "metrics": ["view"],
        "audit": ["view"],
        "support": ["*"],
    },
    "finance": {
        "accounts": ["view"],
        "billing": ["*"],
        "commissions": ["*"],
        "metrics": ["view"],
        "audit": ["view"],
    },
    "support": {
        "accounts": ["view"],
        "assurance": ["view"],
        "errors": ["view"],
        "support": ["view", "create", "revoke"],
    },
}


def permissions_for(role: str, override: dict | None = None) -> dict:
    """مجوزِ مؤثر: override اگر تعریف شده باشد، وگرنه پیش‌فرضِ نقش.

    دقیقاً معناشناسیِ `Principal.permissions` (`app/deps.py`) — `None` یعنی «چیزی
    تعریف نشده»، نه «هیچ مجوزی ندارد». نقشِ ناشناخته عمداً `{}` می‌دهد (fail closed)
    و نه خطا، چون ردیفی که در دیتابیس نقشِ عجیب گرفته نباید کلِ اپِ ستاد را بخواباند.
    """
    if override:
        return override
    return STAFF_ROLE_PERMISSIONS.get(role, {})


def has_permission(permissions: dict, area: str, action: str) -> bool:
    """همان معناشناسیِ `Role.has_permission`، روی مجوزِ ستادی."""
    for key in (area, "*"):
        actions = permissions.get(key)
        if actions and (action in actions or "*" in actions):
            return True
    return False
