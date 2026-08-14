"""ریاضی حقوق و دستمزد — پلکان مالیات، اضافه‌کار، بیمه.

اینها توابع خالص‌اند و به دیتابیس نیاز ندارند، ولی پرخطرترین محاسبات سیستم‌اند:
خروجی‌شان مستقیماً به فیش حقوقی و لیست بیمه می‌رود و اشتباهشان مسئولیت قانونی
کارفرماست. مرزهای پلکان جایی است که این نوع محاسبه معمولاً می‌شکند.
"""
from decimal import Decimal

import pytest

from app.services.payroll import (
    OVERTIME_MULTIPLIER,
    STANDARD_MONTHLY_HOURS,
    _is_placeholder_tax_config,
    calc_annual_tax,
    calc_insurance_shares,
    calc_monthly_tax,
    calc_overtime_pay,
)

# پلکان نمونه: تا ۱۰۰ معاف، ۱۰۰ تا ۳۰۰ نرخ ۱۰٪، مازاد ۲۰٪
BRACKETS = [
    {"up_to": "100", "rate": "0"},
    {"up_to": "300", "rate": "0.10"},
    {"up_to": None, "rate": "0.20"},
]


# --- مالیات پلکانی سالانه -----------------------------------------------------


@pytest.mark.parametrize(
    "taxable,expected,why",
    [
        (0, 0, "درآمد صفر"),
        (-50, 0, "درآمد منفی نباید مالیات منفی بدهد"),
        (100, 0, "دقیقاً روی سقف پلکان معاف"),
        (101, 0.1, "یک واحد بالای مرز، فقط همان یک واحد مشمول ۱۰٪"),
        (300, 20, "دقیقاً روی سقف پلکان دوم: ۲۰۰ × ۱۰٪"),
        (301, 20.2, "یک واحد بالای مرز دوم: ۲۰ + ۱ × ۲۰٪"),
        (500, 60, "پلکان آخر: ۲۰ + ۲۰۰ × ۲۰٪"),
    ],
)
def test_annual_tax_at_bracket_boundaries(taxable, expected, why):
    got = calc_annual_tax(Decimal(str(taxable)), BRACKETS)
    assert got == Decimal(str(expected)).quantize(Decimal("1")), why


def test_annual_tax_is_progressive_not_cliff():
    """عبور از مرز نباید جهش ناگهانی بسازد — فقط مازاد باید نرخ بالاتر بخورد."""
    just_below = calc_annual_tax(Decimal(300), BRACKETS)
    just_above = calc_annual_tax(Decimal(301), BRACKETS)
    assert just_above - just_below < Decimal(1), "عبور از مرز پلکان جهش غیرمنطقی ساخت"


def test_annual_tax_never_exceeds_income():
    for amount in [1, 99, 100, 250, 300, 1000, 10_000]:
        tax = calc_annual_tax(Decimal(amount), BRACKETS)
        assert tax <= Decimal(amount), f"مالیات {tax} از خود درآمد {amount} بیشتر شد"


def test_annual_tax_is_monotonic():
    """درآمد بیشتر هرگز نباید مالیات کمتر بدهد."""
    prev = Decimal(-1)
    for amount in range(0, 1000, 37):
        tax = calc_annual_tax(Decimal(amount), BRACKETS)
        assert tax >= prev, f"مالیات در درآمد {amount} کاهش یافت"
        prev = tax


# --- مالیات ماهانه ------------------------------------------------------------


def test_monthly_tax_applies_annual_exemption_before_brackets():
    """معافیت سالانه باید قبل از پلکان کسر شود، نه بعد از آن."""
    monthly = Decimal(50)  # سالانه ۶۰۰
    with_exemption = calc_monthly_tax(monthly, Decimal(600), BRACKETS)
    assert with_exemption == 0, "درآمد سالانه دقیقاً برابر معافیت باید مالیات صفر بدهد"


def test_monthly_tax_below_exemption_is_zero():
    assert calc_monthly_tax(Decimal(10), Decimal(1000), BRACKETS) == 0


def test_monthly_tax_is_annual_tax_divided_by_twelve():
    monthly = Decimal(100)
    annual_after_exemption = monthly * 12 - Decimal(200)
    expected = (calc_annual_tax(annual_after_exemption, BRACKETS) / 12).quantize(Decimal("1"))
    assert calc_monthly_tax(monthly, Decimal(200), BRACKETS) == expected


# --- تشخیص تنظیمات placeholder -------------------------------------------------


def test_placeholder_detection_blocks_seeded_zero_rate_config():
    """پیکربندی seed‌شده باید مسدود شود؛ پلکان واقعی نباید."""

    class S:
        def __init__(self, b):
            self.tax_brackets = b

    assert _is_placeholder_tax_config(S([{"up_to": None, "rate": "0"}])) is True
    assert _is_placeholder_tax_config(S([])) is True
    assert _is_placeholder_tax_config(S(None)) is True
    assert _is_placeholder_tax_config(S(BRACKETS)) is False, "پلکان واقعی نباید placeholder تشخیص داده شود"


# --- اضافه‌کار ----------------------------------------------------------------


def test_overtime_follows_labour_law_formula():
    """قانون کار: نرخ ساعتی = حقوق پایه ÷ ۱۹۴، با ضریب ۱.۴"""
    base = Decimal(194_000_000)
    pay = calc_overtime_pay(base, Decimal(10))
    expected = (base / STANDARD_MONTHLY_HOURS * OVERTIME_MULTIPLIER * 10).quantize(Decimal("1"))
    assert pay == expected
    assert STANDARD_MONTHLY_HOURS == 194
    assert OVERTIME_MULTIPLIER == Decimal("1.4")


@pytest.mark.parametrize("hours", [0, -1, -100])
def test_overtime_is_zero_for_non_positive_hours(hours):
    assert calc_overtime_pay(Decimal(10_000_000), Decimal(hours)) == 0


# --- بیمه ---------------------------------------------------------------------


def test_insurance_shares_use_statutory_rates():
    """ماده ۲۸: سهم کارمند ۷٪، سهم کارفرما ۲۳٪."""
    employee, employer = calc_insurance_shares(Decimal(100_000_000), Decimal("0.07"), Decimal("0.23"))
    assert employee == Decimal(7_000_000)
    assert employer == Decimal(23_000_000)


def test_insurance_rounds_to_whole_toman():
    """مبالغ Numeric(18,0) هستند؛ نباید کسر اعشاری تولید شود."""
    employee, employer = calc_insurance_shares(Decimal(3_333_333), Decimal("0.07"), Decimal("0.23"))
    assert employee == employee.quantize(Decimal("1"))
    assert employer == employer.quantize(Decimal("1"))
