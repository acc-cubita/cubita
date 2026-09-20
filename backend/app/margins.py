"""سودِ فروشگاه: خالصِ خرید، سودِ ناخالص، مارک‌آپ و مارجین (§۲۱ تا §۲۷).

**ماژولِ خالص است و عمداً `Session` نمی‌گیرد.** همه‌ی سرویس‌های
`app/services/` اولین آرگومانشان `db` است؛ گذاشتنِ این‌جا یعنی دعوت به اینکه
روزی کسی وسطش کوئری بزند. الگوی موجود برای منطقِ بی‌حالت `app/pagination.py`
و `app/migration_utils.py` است، نه پوشه‌ی سرویس.

**و چرا دوقلوی TypeScript دارد.** §۲۶ می‌خواهد وقتی فروشگاه تعداد را عوض می‌کند
اعداد **زنده** عوض شوند. درخواست به سرور به‌ازای هر کلید یعنی تأخیر و بار؛ پس
همین فرمول‌ها در [desktop/src/lib/margins.ts](../../desktop/src/lib/margins.ts)
تکرار شده‌اند.

دو نسخه یعنی دو جا برای واگرایی — و راهِ بستنش یک **پرونده‌ی نمونه‌ی مشترک**
است: `tests/fixtures/margin_cases.json`. هر دو طرف همان را می‌خوانند و همان
جواب‌ها را می‌سنجند. هیچ‌کدام صاحبِ حقیقت نیست؛ پرونده هست.

## قاعده‌ی گِردکردن

درصدها با `ROUND_HALF_UP` و یک رقمِ اعشار گِرد می‌شوند. این انتخاب لازم است چون
پایتون `Decimal` دارد و جاوااسکریپت `float64`؛ مبلغِ ریالِ صحیح تا ۲^۵۳ در هر
دو دقیق است، ولی **درصد** در رقم‌های آخر فرق می‌کند. پس آنچه سنجیده می‌شود
عددِ *نمایشی* است، نه خامِ محاسبه.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

#: یک رقمِ اعشار برای درصد — همان چیزی که روی کارت دیده می‌شود.
_PERCENT_PLACES = Decimal("0.1")


def _d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value if value is not None else 0))


def net_purchase_price(list_price, discount=0) -> Decimal:
    """قیمتِ واقعیِ خریدِ فروشگاه پس از تخفیف (§۲۳).

    **تخفیف همیشه مبلغ است، نه درصد.** در کلِ این مخزن ردیفِ فاکتور تخفیف را
    به‌صورتِ مبلغ ذخیره می‌کند (`SalesInvoiceLineIn.discount`)، و §۲۴ درصد را
    هم می‌خواهد — ولی درصد یک **ویجتِ ورودی** است که پیش از ارسال به مبلغ
    تبدیل می‌شود. ستونِ درصد یعنی دو نمای یک داده، و تسهیمِ تخفیفِ سربرگ در
    `_allocate_discount` را هم می‌شکند.
    """
    return max(_d(list_price) - _d(discount), Decimal(0))


def percent_to_amount(list_price, percent) -> Decimal:
    """تبدیلِ تخفیفِ درصدی به مبلغ (§۲۴) — برای ویجتِ ورودی، پیش از ذخیره."""
    pct = _d(percent)
    if pct <= 0:
        return Decimal(0)
    return (_d(list_price) * pct / Decimal(100)).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def effective_unit_cost(total_paid, total_received) -> Decimal | None:
    """بهای واقعیِ هر واحد وقتی اشانتیون گرفته‌ای (§۲۵).

        ۱۲۰ کارتن پول داده‌ای، ۱۳۲ تا گرفته‌ای → بهای هر کارتن = پول ÷ ۱۳۲

    `None` وقتی چیزی دریافت نشده: تقسیم بر صفر جواب ندارد و صفر برگرداندن
    یعنی ادعای «رایگان بود».
    """
    received = _d(total_received)
    if received <= 0:
        return None
    return _d(total_paid) / received


def gross_profit(consumer_price, net_cost) -> Decimal:
    """سودِ ناخالصِ هر واحد (§۲۱) — **محاسبه می‌شود، دستی وارد نمی‌شود.**"""
    return _d(consumer_price) - _d(net_cost)


def markup_percent(consumer_price, net_cost) -> Decimal | None:
    """سود نسبت به **بهای خرید** (§۲۲). `None` وقتی بهای خرید صفر است."""
    cost = _d(net_cost)
    if cost <= 0:
        return None
    profit = gross_profit(consumer_price, cost)
    return (profit / cost * Decimal(100)).quantize(_PERCENT_PLACES, rounding=ROUND_HALF_UP)


def margin_percent(consumer_price, net_cost) -> Decimal | None:
    """سود نسبت به **قیمتِ فروش** (§۲۲). `None` وقتی قیمتِ فروش صفر است.

    مارک‌آپ و مارجین دو عددِ متفاوت‌اند و §۲۲ هر دو را می‌خواهد: ۱۵۰ روی ۳۰۰
    یعنی مارک‌آپِ ۵۰٪ ولی مارجینِ ۳۳٫۳٪. یکی‌گرفتنشان اشتباهِ رایجی است که
    فروشنده را درباره‌ی سودش گمراه می‌کند.
    """
    price = _d(consumer_price)
    if price <= 0:
        return None
    return (gross_profit(price, net_cost) / price * Decimal(100)).quantize(
        _PERCENT_PLACES, rounding=ROUND_HALF_UP
    )


def profit_per_pack(unit_profit, units_per_pack) -> Decimal | None:
    """سودِ هر کارتن (§۲۷) — از نسبتِ تبدیلِ **ثابتِ** خودِ کالا.

    `None` وقتی نسبت تعریف نشده. حدس‌زدنش (مثلاً «۱۲ تا در هر کارتن») یعنی
    عددی که کاربر باور می‌کند و ما از خودمان درآورده‌ایم.
    """
    per_pack = _d(units_per_pack)
    if per_pack <= 0:
        return None
    return _d(unit_profit) * per_pack


def effective_consumer_price(batch_price=None, product_price=None) -> Decimal | None:
    """§۱۹ — قیمتِ بار بر قیمتِ کالا می‌چربد.

        effective = batch ?? product

    هر بار می‌تواند قیمتِ چاپیِ خودش را داشته باشد: بسته‌ی پارسال ۴۵۰٬۰۰۰ و
    امسال ۵۲۰٬۰۰۰. قیمتِ کالا فقط پیش‌فرض است.

    `None` یعنی هیچ‌کدام اعلام نشده — و §۳۰ می‌گوید چنین فیلدی اصلاً نباید
    نمایش داده شود، نه اینکه صفر نشان داده شود.
    """
    if batch_price is not None:
        return _d(batch_price)
    if product_price is not None:
        return _d(product_price)
    return None


def order_analysis(*, qty, list_price, discount=0, consumer_price=None, units_per_pack=None, bonus_qty=0) -> dict:
    """تحلیلِ زنده‌ی سودِ یک سفارش (§۲۶).

    **فقط چیزی را برمی‌گرداند که واقعاً قابلِ محاسبه است.** §۲۶ صریح است:
    «این اطلاعات فقط زمانی نمایش داده شوند که داده‌های لازم وجود داشته باشند».
    پس کلیدهایی که ورودی‌شان نیست اصلاً در خروجی نمی‌آیند — نه با صفر، نه با
    خط تیره.
    """
    quantity = _d(qty)
    net_unit = net_purchase_price(list_price, discount)
    received = quantity + _d(bonus_qty)
    out: dict[str, Decimal] = {
        "order_quantity": quantity,
        "net_purchase_amount": net_unit * quantity,
    }
    if _d(bonus_qty) > 0:
        out["bonus_quantity"] = _d(bonus_qty)
        eff = effective_unit_cost(net_unit * quantity, received)
        if eff is not None:
            out["effective_unit_cost"] = eff
            net_unit = eff  # سودِ واقعی با بهای واقعی حساب می‌شود، نه با فیِ لیست

    if consumer_price is None:
        return out

    price = _d(consumer_price)
    out["potential_revenue"] = price * received
    out["potential_gross_profit"] = gross_profit(price, net_unit) * received
    markup = markup_percent(price, net_unit)
    if markup is not None:
        out["markup_percent"] = markup
    margin = margin_percent(price, net_unit)
    if margin is not None:
        out["margin_percent"] = margin
    per_pack = profit_per_pack(gross_profit(price, net_unit), units_per_pack)
    if per_pack is not None:
        out["profit_per_pack"] = per_pack
    return out
