"""قالب‌های آماده‌ی کدینگِ حساب — عمومی + تخصصیِ هر صنف.

چارتِ پایه‌ای که هنگامِ ساختِ کسب‌وکار نشانده می‌شود (`seed.CHART_OF_ACCOUNTS`) عمداً
کوچک است: فقط حساب‌هایی که موتورِ ثبتِ خودکار به آن‌ها نیاز دارد. ولی یک دفترِ واقعی
ده‌ها حسابِ دیگر لازم دارد و ساختنِ تک‌تکشان با فرم، کارِ یک بعدازظهر است.

این‌جا چهار قالبِ صنفی تعریف شده و هرکدام = **حساب‌های عمومی + حساب‌های تخصصیِ همان
صنف**. اعمالِ قالب:

- فقط حسابِ **نبود** را می‌سازد. کدی که از قبل هست دست نمی‌خورد — نه نامش، نه نوعش.
- هرگز `system_role` نمی‌دهد؛ نقشِ سیستمی فقط از راهِ provisioning می‌آید.
- سرفصلِ والد با **کد** پیدا می‌شود، پس اگر مشتری چارت را بازشماره‌گذاری کرده باشد و
  سرفصل نباشد، همان‌جا ساخته می‌شود.
- تکرارِ اعمال بی‌خطر است (idempotent): بارِ دوم چیزی اضافه نمی‌شود.

**خودِ ردیف‌ها داده‌اند، نه کد** — در `app/data/chart_templates.json`. این ماژول فقط
می‌خواندشان و شکلشان را می‌سنجد. جداکردنشان یعنی اضافه‌کردنِ یک حساب به قالب، ویرایشِ
یک فایلِ داده است نه تغییرِ منطق؛ و `test_chart_templates.py` شکلِ فایل را قفل می‌کند
تا خرابیِ داده در زمانِ *بارگذاری* پیدا شود نه وسطِ درجِ قالب برای مشتری.
"""
from __future__ import annotations

import json
from pathlib import Path

#: هر ردیف: (کد, نام, نوع, is_group, کدِ والد)
Row = tuple[str, str, str, bool, str | None]

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "chart_templates.json"

#: نوع‌های مجاز — همان‌های `ACCOUNT_TYPES`، این‌جا تکرار می‌شوند تا بارگذاری به مدل
#: وابسته نباشد و بشود فایل را بدونِ بالاآوردنِ SQLAlchemy سنجید.
_VALID_TYPES = ("asset", "liability", "equity", "income", "expense")


def _row(raw: dict, where: str) -> Row:
    """یک ردیفِ JSON را به تاپل تبدیل می‌کند و همان‌جا اعتبارش را می‌سنجد.

    خطا این‌جا گرفته می‌شود — لحظه‌ی بارگذاریِ ماژول — نه وسطِ درجِ قالب. اگر ردیفی
    خراب باشد، برنامه بالا نمی‌آید؛ بهتر از آنکه مشتری وسطِ کار نصفه‌کاره بماند.
    """
    missing = {"code", "title", "type"} - raw.keys()
    if missing:
        raise ValueError(f"ردیفِ ناقص در {where}: فیلدهای {sorted(missing)} نیستند — {raw}")
    if raw["type"] not in _VALID_TYPES:
        raise ValueError(f"نوعِ نامعتبر «{raw['type']}» در {where} برای کدِ {raw['code']}")
    if not str(raw["code"]).isdigit():
        raise ValueError(f"کدِ غیرعددی «{raw['code']}» در {where}")
    return (
        str(raw["code"]),
        raw["title"],
        raw["type"],
        bool(raw.get("is_group", False)),
        raw.get("parent"),
    )


def _load() -> tuple[list[Row], list[Row], dict[str, dict]]:
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    parents = [_row(r, "parents") for r in raw["parents"]]
    common = [_row(r, "common") for r in raw["common"]]
    templates = {
        key: {
            "label": meta["label"],
            "hint": meta["hint"],
            "rows": [_row(r, f"templates.{key}") for r in meta["rows"]],
        }
        for key, meta in raw["templates"].items()
    }

    #: هر کدی که ردیف‌ها به‌عنوانِ والد نام می‌برند باید واقعاً تعریف شده باشد،
    #: وگرنه درجِ قالب سرفصلِ ناقص می‌سازد و درخت جای عجیبی رشد می‌کند.
    defined = {r[0] for r in (*parents, *common)} | {
        r[0] for meta in templates.values() for r in meta["rows"]
    }
    for scope, rows in [("parents", parents), ("common", common), *(
        (f"templates.{k}", m["rows"]) for k, m in templates.items()
    )]:
        for code, _name, _type, _group, parent in rows:
            if parent is not None and parent not in defined:
                raise ValueError(f"والدِ «{parent}» در {scope} (کدِ {code}) هیچ‌جا تعریف نشده")

    return parents, common, templates


_PARENTS, COMMON, TEMPLATES = _load()


def rows_for(key: str) -> list[Row]:
    """ردیف‌های یک قالب: سرفصل‌های لازم + عمومی + تخصصیِ همان صنف.

    ترتیب مهم است — والد باید پیش از فرزند ساخته شود.
    """
    template = TEMPLATES.get(key)
    if template is None:
        raise KeyError(key)
    return [*_PARENTS, *COMMON, *template["rows"]]
