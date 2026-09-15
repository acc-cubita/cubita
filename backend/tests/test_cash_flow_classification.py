"""طبقه‌بندیِ صورت جریان وجوه نقد باید به **نقشِ** حساب بچسبد، نه به متنِ کد.

**چه کم بود.** `_cash_flow_category` سمتِ بدهی را فقط با `code.startswith("22")`
تشخیص می‌داد. کدِ حساب مالِ مشتری است — همان چیزی که docstringِ `chart_codes`
می‌گوید: «لحظه‌ای که مشتری صندوق را از ۱۱۰۱ به چیز دیگری می‌برد، هر ثبتِ خودکاری
می‌شکست». پس حسابدارِ که چارتش را بازشماره‌گذاری می‌کرد، وامِ بلندمدتش از «تأمین
مالی» به «عملیاتی» می‌افتاد و صورت جریان وجوه نقد **بی‌صدا** غلط می‌شد.

و مشکلِ دوم: چارتِ پایه اصلاً **گروهِ ۲۲ نداشت**، پس آن شرط در یک کسب‌وکارِ
پیش‌فرض به هیچ حسابی نمی‌خورد.
"""
from app.models.accounting import Account
from app.services import chart_codes as cc
from app.services.reports import _cash_flow_category


def _account(**kw) -> Account:
    kw.setdefault("code", "2201")
    kw.setdefault("name", "وام بلندمدت")
    kw.setdefault("type", "liability")
    kw.setdefault("system_role", None)
    return Account(**kw)


# ─────────── نقش حرفِ آخر را می‌زند ───────────


def test_the_role_wins_even_when_the_code_says_otherwise(db):
    """**هسته‌ی این اصلاح.**

    حسابدار چارت را بازشماره‌گذاری کرده و وامِ بلندمدت حالا کدِ ۴۹۰۰ دارد. تا
    امروز این حساب «عملیاتی» می‌شد.
    """
    renumbered = _account(code="4900", system_role=cc.LONG_TERM_LIABILITY)
    assert _cash_flow_category(renumbered) == "financing", (
        "*** نقش نادیده گرفته شد و گزارش دوباره به کد تکیه کرد ***"
    )


def test_a_current_liability_stays_operating(db):
    assert _cash_flow_category(_account(code="2101", name="پرداختنی")) == "operating"


def test_equity_is_financing(db):
    assert _cash_flow_category(_account(code="3101", name="سرمایه", type="equity")) == "financing"


# ─────────── رفتارِ دیروز نباید عوض شود ───────────


def test_the_code_fallback_still_works_for_existing_charts(db):
    """**عمدی.** کسب‌وکارهای موجود حسابِ نقش‌دار ندارند — چارتِ پایه تا امروز
    اصلاً گروهِ ۲۲ نداشت. برداشتنِ این شرط یعنی تغییرِ بی‌اعلامِ گزارشِ آن‌ها."""
    legacy = _account(code="2201", system_role=None)
    assert _cash_flow_category(legacy) == "financing"


def test_an_asset_in_group_12_is_investing(db):
    assert _cash_flow_category(_account(code="1201", name="اموال", type="asset")) == "investing"


# ─────────── چارتِ پایه باید جایی برای بدهیِ بلندمدت داشته باشد ───────────


def test_the_base_chart_has_a_long_term_liability_group(db):
    """قاعده‌ی ۱۶۰: جاری/غیرجاری باید بُعدِ مستقل باشد.

    بدونِ گروهِ ۲۲ در چارتِ پایه، هیچ کسب‌وکارِ تازه‌ای نمی‌توانست بدهیِ بلندمدت
    ثبت کند و شرطِ قدیمیِ گزارش هرگز فعال نمی‌شد.
    """
    from app.seed import CHART_OF_ACCOUNTS

    codes = {code for code, *_ in CHART_OF_ACCOUNTS}
    assert "22" in codes, "*** گروهِ بدهی‌های بلندمدت از چارتِ پایه رفت ***"
    assert "2201" in codes


def test_the_long_term_role_maps_to_a_chart_code(db):
    """نقش باید در راه‌اندازی روی حسابی بنشیند، وگرنه نقشی است که کسی نمی‌تواند
    بدهدش — `system_role` از API قابلِ تنظیم نیست."""
    assert cc.DEFAULT_CODE_BY_ROLE[cc.LONG_TERM_LIABILITY] == "2201"
    assert cc.ROLE_BY_DEFAULT_CODE["2201"] == cc.LONG_TERM_LIABILITY
