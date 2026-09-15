"""رجیستریِ مجوزها — منبعِ واحدِ «چه ماژول‌هایی و چه اکشن‌هایی وجود دارد».

`require_permission(module, action)` در سراسرِ بک‌اند صدا زده می‌شود، ولی تا امروز
هیچ‌جا **فهرست** نشده بود که این ماژول‌ها کدام‌اند. نتیجه‌اش این بود که رابط کاربری
فقط می‌توانست نقشِ آماده بدهد و نمی‌شد دسترسیِ دقیقِ یک کاربر را انتخاب کرد.

این فهرست از روی فراخوانی‌های واقعیِ `require_permission` ساخته شده. اگر ماژول یا
اکشنِ تازه‌ای اضافه شد، این‌جا هم باید بیاید — `test_permission_registry` همین را
می‌سنجد و اگر جا بماند قرمز می‌شود.

**توجه:** این کلیدها با کلیدهای «شخصی‌سازیِ پنل» (`services/modules.py`) یکی نیستند.
آن‌ها کنترل می‌کنند چه چیزی در منو *دیده* شود؛ این‌ها کنترل می‌کنند کاربر چه کاری
*بتواند بکند*.
"""
from __future__ import annotations

#: برچسبِ فارسیِ هر اکشن — رابط کاربری همین را نشان می‌دهد، نه کلیدِ انگلیسی.
ACTION_LABELS: dict[str, str] = {
    "view": "مشاهده",
    "create": "ثبت",
    "update": "ویرایش",
    "delete": "حذف",
    "approve": "تأیید/نهایی‌سازی",
    "deliver": "ثبت تحویل",
}

#: ماژول‌های مجوز و اکشن‌هایی که هرکدام واقعاً پشتیبانی می‌کنند.
PERMISSION_MODULES: list[dict] = [
    {
        "key": "invoices",
        "label": "فاکتور فروش و خرید",
        "hint": "فاکتور، پیش‌فاکتور، برگشتی و صندوق فروشگاهی",
        "actions": ["view", "create", "update", "delete"],
    },
    {
        "key": "inventory",
        "label": "انبار و کالا",
        "hint": "کالاها، موجودی، تعدیل، انتقال و انبارگردانی",
        "actions": ["view", "create", "update", "delete"],
    },
    {
        "key": "accounting",
        "label": "حسابداری",
        "hint": "اسناد، دفاتر، سال مالی و بستن دوره",
        "actions": ["view", "create", "update", "delete", "approve"],
    },
    {
        "key": "checks_bank",
        "label": "چک و بانک",
        "hint": "چک‌ها، حساب‌های بانکی و دریافت/پرداخت",
        "actions": ["view", "create", "update"],
    },
    {
        "key": "assets",
        "label": "دارایی ثابت",
        "hint": "دارایی‌ها و استهلاک",
        "actions": ["view", "create", "update", "delete", "approve"],
    },
    {
        "key": "payroll",
        "label": "حقوق و دستمزد",
        "hint": "پرسنل، فیش حقوقی و مزایا",
        "actions": ["view", "create", "update", "approve"],
    },
    {
        "key": "crm",
        "label": "باشگاه مشتریان",
        "hint": "سرنخ‌ها، پیگیری‌ها و وفاداری",
        "actions": ["view", "create", "update", "delete"],
    },
    {
        "key": "manufacturing",
        "label": "تولید",
        "hint": "فرمول ساخت و سفارش تولید",
        "actions": ["view", "create", "update", "delete"],
    },
    {
        "key": "contracting",
        "label": "پیمانکاری",
        "hint": "پیمان‌ها، متمم‌ها و صورت‌وضعیت‌ها",
        "actions": ["view", "create", "update"],
    },
    {
        "key": "moadian",
        "label": "سامانه مؤدیان",
        "hint": "ارسال صورتحساب الکترونیکی. «ویرایش» یعنی دسترسی به کلید و اعتبارنامه.",
        "actions": ["view", "update", "approve"],
    },
    {
        "key": "marketplace",
        "label": "بازار عمده‌فروشی",
        "hint": "اتصال‌ها، سفارش‌ها و تحویل",
        "actions": ["view", "create", "update", "delete", "approve", "deliver"],
    },
    {
        "key": "calendar",
        "label": "تقویم و یادآوری",
        "actions": ["view", "create", "update", "delete"],
    },
    {
        "key": "audit",
        "label": "گزارش حسابرسی",
        "hint": "دیدن تاریخچه‌ی تغییرات",
        "actions": ["view"],
    },
    {
        "key": "users",
        "label": "مدیریت کاربران",
        "hint": "دعوت کاربر، تغییر نقش و دسترسی. با احتیاط بدهید.",
        "actions": ["view", "create", "update"],
    },
]

MODULE_KEYS: frozenset[str] = frozenset(m["key"] for m in PERMISSION_MODULES)
ACTIONS_BY_MODULE: dict[str, frozenset[str]] = {
    m["key"]: frozenset(m["actions"]) for m in PERMISSION_MODULES
}


def sanitize(raw: dict | None) -> dict[str, list[str]] | None:
    """ورودیِ کاربر را به یک نقشه‌ی مجوزِ معتبر تبدیل می‌کند.

    ماژول و اکشنِ ناشناخته **دور ریخته می‌شود** نه اینکه خطا بدهد: رابط کاربری ممکن
    است از نسخه‌ی قدیمی‌تر بیاید، و پذیرفتنِ کلیدِ ناشناخته یعنی ذخیره‌ی مجوزی که هیچ
    معنایی ندارد. `*` عمداً پذیرفته نمی‌شود — دسترسیِ کامل فقط از راهِ نقشِ مالک
    می‌آید، نه از یک ویرایشِ دستیِ دسترسی.
    """
    if raw is None:
        return None
    clean: dict[str, list[str]] = {}
    for module, actions in raw.items():
        allowed = ACTIONS_BY_MODULE.get(module)
        if allowed is None or not isinstance(actions, (list, tuple)):
            continue
        picked = [a for a in dict.fromkeys(actions) if a in allowed]
        if picked:
            # «مشاهده» پیش‌نیازِ هر کارِ دیگری است؛ بدونِ آن، کاربر اجازه‌ی ثبت دارد
            # ولی صفحه‌ای برای دیدنش ندارد — حالتی که فقط گیج‌کننده است.
            if "view" in allowed and "view" not in picked:
                picked.insert(0, "view")
            clean[module] = picked
    return clean
