"""نمای چاپی فاکتور.

تا امروز سیستم صفر قابلیت چاپ داشت — یعنی نمی‌شد فاکتور را به دست مشتری داد،
که برای نرم‌افزار حسابداری تجاری یک مانع واقعی فروش است.

تبدیل تاریخ شمسی اینجا با تاریخ‌های مرزی سنجیده می‌شود و نه با یک نمونه: خطای
یک‌روزه در تبدیل تقویم، روی هر فاکتوری می‌نشیند و کسی تا پایان سال مالی متوجه
نمی‌شود.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.services.printing import (
    amount_in_words,
    fa_number,
    format_jalali,
    gregorian_to_jalali,
    render_invoice,
)


# --- تقویم ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "gregorian,expected",
    [
        # لنگرهای تاریخیِ شناخته‌شده — این‌ها را می‌شود مستقل راستی‌آزمایی کرد
        (date(1979, 2, 11), (1357, 11, 22)),  # پیروزی انقلاب
        (date(2024, 3, 20), (1403, 1, 1)),    # نوروز ۱۴۰۳ (۲۰ مارس بود، نه ۲۱)
        (date(2025, 3, 21), (1404, 1, 1)),    # نوروز ۱۴۰۴
        (date(2026, 3, 21), (1405, 1, 1)),    # نوروز ۱۴۰۵
        (date(2026, 3, 20), (1404, 12, 29)),  # آخرین روز ۱۴۰۴ (کبیسه نیست)
        (date(2026, 7, 19), (1405, 4, 28)),
        (date(2000, 1, 1), (1378, 10, 11)),
    ],
)
def test_jalali_conversion_at_boundaries(gregorian, expected):
    assert gregorian_to_jalali(gregorian) == expected


def test_jalali_is_continuous_across_a_year_boundary():
    """هیچ روزی نباید جا بیفتد یا تکرار شود.

    خطای یک‌روزه در تبدیل تقویم روی هر فاکتوری می‌نشیند و تا پایان سال مالی
    نامرئی می‌ماند.
    """
    seen = []
    day = date(2026, 3, 15)
    for _ in range(20):
        seen.append(gregorian_to_jalali(day))
        day = date.fromordinal(day.toordinal() + 1)

    assert len(set(seen)) == len(seen), "تاریخ تکراری تولید شد"
    # باید دقیقاً یک بار از ۱۴۰۴ به ۱۴۰۵ عبور کند
    years = [y for y, _, _ in seen]
    assert years[0] == 1404 and years[-1] == 1405
    assert sum(1 for a, b in zip(years, years[1:]) if a != b) == 1


def test_format_jalali_is_persian():
    assert format_jalali(date(2026, 3, 21)) == "۱ فروردین ۱۴۰۵"
    assert format_jalali(None) == "—"


# --- اعداد ---------------------------------------------------------------------------


def test_numbers_get_separators_and_persian_digits():
    assert fa_number(1234567) == "۱٬۲۳۴٬۵۶۷".replace("٬", ",")
    assert fa_number(0) == "۰"
    assert fa_number(None) == "—"


@pytest.mark.parametrize(
    "amount,expected",
    [
        (0, "صفر"),
        (7, "هفت"),
        (15, "پانزده"),
        (42, "چهل و دو"),
        (100, "صد"),
        (1000, "یک هزار"),
        (1_500_000, "یک میلیون و پانصد هزار"),
        (2_000_000_000, "دو میلیارد"),
    ],
)
def test_amount_in_words(amount, expected):
    assert amount_in_words(amount) == expected


# --- خودِ سند --------------------------------------------------------------------------


def _render(**overrides):
    defaults = dict(
        kind="فاکتور فروش",
        business_name="فروشگاه نمونه",
        number=7,
        invoice_date=date(2026, 3, 21),
        party_name="مشتری تست",
        party_detail="۰۹۱۲۰۰۰۰۰۰۰",
        description="بابت فروش",
        lines=[{"name": "کالای الف", "description": "", "qty": 3, "unit": "عدد", "unit_price": 50000}],
        total=Decimal(150000),
    )
    defaults.update(overrides)
    return render_invoice(**defaults)


def test_rendered_invoice_is_self_contained_rtl_html():
    html = _render()
    assert html.startswith("<!doctype html>")
    assert 'dir="rtl"' in html
    assert "فروشگاه نمونه" in html
    assert "کالای الف" in html
    assert "۱ فروردین ۱۴۰۵" in html
    # هیچ منبع بیرونی: باید آفلاین و در چاپ هم درست باشد
    assert "http://" not in html and "https://" not in html


def test_totals_and_words_appear():
    html = _render()
    assert "۱۵۰,۰۰۰" in html
    assert "صد و پنجاه هزار" in html


def test_a_voided_invoice_says_so_on_the_page():
    """فاکتور باطل که بدون نشانه چاپ شود، به دست مشتری می‌رسد و معتبر به‌نظر می‌آید."""
    from datetime import datetime, timezone

    html = _render(voided_at=datetime.now(timezone.utc), void_reason="ثبت اشتباه")
    assert "باطل شده" in html
    assert "ثبت اشتباه" in html

    assert "باطل شده" not in _render()


def test_user_content_is_escaped():
    """نام کالا و طرف حساب را کاربر می‌نویسد و مستقیم در HTML می‌نشیند."""
    html = _render(party_name="<script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
