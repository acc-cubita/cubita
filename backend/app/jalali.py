"""تقویم شمسی — تبدیل شمسی↔میلادی و مرزهای سال/ماهِ شمسی.

ماژول حقوق و دستمزد (دوره‌ها، تنظیمات، مزایا) بر پایه‌ی **سالِ شمسی** کار می‌کند:
عیدی برای سالِ شمسی صادر می‌شود، فیشِ حقوق برای ماهِ شمسی (فروردین..اسفند). دیتابیس
تاریخ‌ها را میلادی ذخیره می‌کند، پس این‌جا مرزِ هر دوره‌ی شمسی به تاریخِ میلادیِ
متناظرش تبدیل می‌شود.

`gregorian_to_jalali` از پیش در services/printing.py وجود دارد (همان الگوریتمِ ۳۳ساله
که فاکتورهای چاپی هم استفاده می‌کنند). این‌جا فقط معکوسش (`jalali_to_gregorian`) و چند
کمک‌تابعِ مرز اضافه می‌شود. درستیِ این جفت با round-trip روی هر روزِ ~۲۵۰ سال تست
می‌شود؛ اگر معکوسِ کامل نباشند، آن تست قرمز می‌شود.
"""
from datetime import date, timedelta

from app.services.printing import gregorian_to_jalali

__all__ = [
    "gregorian_to_jalali",
    "jalali_to_gregorian",
    "today_jalali",
    "persian_year_start",
    "persian_year_end",
    "persian_month_end",
    "days_in_jalali_year",
]


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> date:
    """تبدیل شمسی به میلادی — معکوسِ دقیقِ gregorian_to_jalali.

    همان الگوریتمِ استانداردِ ۳۳ساله؛ عمداً بدون کتابخانه‌ی بیرونی و هم‌خانواده‌ی
    تابعِ رفت تا رفت‌وبرگشت بی‌خطا باشد (تستِ round-trip تضمینش می‌کند).
    """
    if jy > 979:
        gy = 1600
        jy -= 979
    else:
        gy = 621

    days = (
        365 * jy
        + (jy // 33) * 8
        + ((jy % 33) + 3) // 4
        + 78
        + jd
        + ((jm - 1) * 31 if jm < 7 else (jm - 7) * 30 + 186)
    )

    gy += 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        gy += 100 * ((days - 1) // 36524)
        days = (days - 1) % 36524
        if days >= 365:
            days += 1

    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365

    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    month_days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1
    for dim in month_days:
        if gd <= dim:
            break
        gd -= dim
        gm += 1
    return date(gy, gm, gd)


def today_jalali() -> tuple[int, int, int]:
    return gregorian_to_jalali(date.today())


def persian_year_start(jy: int) -> date:
    """اولِ فروردینِ سالِ شمسیِ jy، به میلادی."""
    return jalali_to_gregorian(jy, 1, 1)


def persian_year_end(jy: int) -> date:
    """آخرین روزِ اسفندِ سالِ شمسیِ jy، به میلادی (یک‌روز پیش از فروردینِ سالِ بعد)."""
    return persian_year_start(jy + 1) - timedelta(days=1)


def persian_month_end(jy: int, jm: int) -> date:
    """آخرین روزِ ماهِ شمسیِ (jy, jm)، به میلادی — به‌عنوانِ «تاریخِ سررسیدِ» دوره‌ی حقوق."""
    if jm >= 12:
        nxt = jalali_to_gregorian(jy + 1, 1, 1)
    else:
        nxt = jalali_to_gregorian(jy, jm + 1, 1)
    return nxt - timedelta(days=1)


def days_in_jalali_year(jy: int) -> int:
    """۳۶۵ یا ۳۶۶ (سالِ کبیسه‌ی شمسی)."""
    return (persian_year_start(jy + 1) - persian_year_start(jy)).days
