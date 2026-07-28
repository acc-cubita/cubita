"""تقویم شمسی — درستیِ تبدیل و مرزهای سال/ماه.

ماژول حقوق و مزایا روی این تبدیل‌ها حساب می‌کند (عیدیِ سالِ شمسی، فیشِ ماهِ شمسی)،
پس یک خطای یک‌روزه یعنی سند با تاریخِ اشتباه و عیدیِ نادرست. round-trip روی هر روزِ
~۲۵۰ سال تضمین می‌کند رفت‌وبرگشت بی‌خطاست.
"""
from datetime import date, timedelta

from app.jalali import (
    days_in_jalali_year,
    gregorian_to_jalali,
    jalali_to_gregorian,
    persian_month_end,
    persian_year_end,
    persian_year_start,
)


def test_roundtrip_every_day_250_years():
    d, end, mism = date(1850, 1, 1), date(2100, 12, 31), 0
    while d <= end:
        jy, jm, jd = gregorian_to_jalali(d)
        if jalali_to_gregorian(jy, jm, jd) != d:
            mism += 1
        d += timedelta(days=1)
    assert mism == 0


def test_nowruz_anchors():
    # اولِ فروردین = نوروز؛ لنگرهای مستقلاً راستی‌آزمایی‌پذیر
    assert jalali_to_gregorian(1403, 1, 1) == date(2024, 3, 20)
    assert jalali_to_gregorian(1404, 1, 1) == date(2025, 3, 21)
    assert jalali_to_gregorian(1405, 1, 1) == date(2026, 3, 21)


def test_leap_year_length():
    assert days_in_jalali_year(1403) == 366  # کبیسه
    assert days_in_jalali_year(1404) == 365


def test_year_bounds():
    assert persian_year_start(1404) == date(2025, 3, 21)
    assert persian_year_end(1404) == date(2026, 3, 20)


def test_month_end():
    # شش ماهِ اولِ سالِ شمسی ۳۱ روزه‌اند، شش ماهِ دوم ۳۰ (اسفند ۲۹/۳۰)
    assert persian_month_end(1404, 1) == date(2025, 4, 20)  # پایانِ فروردین
    assert persian_month_end(1404, 7) == jalali_to_gregorian(1404, 7, 30)
    assert persian_month_end(1403, 12) == date(2025, 3, 20)  # پایانِ اسفندِ سالِ کبیسه
