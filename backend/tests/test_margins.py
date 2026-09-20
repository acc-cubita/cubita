"""محاسبه‌ی سود — از پرونده‌ی نمونه‌ی **مشترک** با تایپ‌اسکریپت.

`app/margins.py` و `desktop/src/lib/margins.ts` یک منطق را دو بار پیاده کرده‌اند،
چون §۲۶ محاسبه‌ی زنده می‌خواهد و درخواست به سرور به‌ازای هر کلید یعنی تأخیر.

دو نسخه یعنی دو جا برای واگرایی. راهِ بستنش این است که **هیچ‌کدام صاحبِ حقیقت
نباشد**: هر دو `desktop/src/lib/margin_cases.json` را می‌خوانند. اگر یکی عوض شود
و دیگری نه، همان پرونده لوش می‌دهد.
"""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from app import margins

#: پرونده در `desktop/src/lib/` است نه این‌جا: تایپ‌اسکریپت اجازه‌ی خواندن از
#: بیرونِ `src` را نمی‌دهد، ولی پایتون هیچ محدودیتی ندارد. یک پرونده می‌ماند.
_FIXTURE = Path(__file__).resolve().parents[2] / "desktop" / "src" / "lib" / "margin_cases.json"
CASES = json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _eq(got, expected) -> bool:
    """مقایسه‌ی عددی که `None` را هم می‌فهمد و اعشارِ بلند را تحمل می‌کند."""
    if expected is None:
        return got is None
    if got is None:
        return False
    return abs(Decimal(str(got)) - Decimal(str(expected))) < Decimal("0.0000001")


@pytest.mark.parametrize("case", CASES["net_purchase_price"], ids=lambda c: c["name"])
def test_net_purchase_price(case):
    got = margins.net_purchase_price(case["list_price"], case["discount"])
    assert _eq(got, case["expected"]), f"{case['name']}: {got}"


@pytest.mark.parametrize("case", CASES["percent_to_amount"], ids=lambda c: c["name"])
def test_percent_to_amount(case):
    got = margins.percent_to_amount(case["list_price"], case["percent"])
    assert _eq(got, case["expected"]), f"{case['name']}: {got}"


@pytest.mark.parametrize("case", CASES["gross_profit"], ids=lambda c: c["name"])
def test_gross_profit(case):
    got = margins.gross_profit(case["consumer_price"], case["net_cost"])
    assert _eq(got, case["expected"]), f"{case['name']}: {got}"


@pytest.mark.parametrize("case", CASES["markup_percent"], ids=lambda c: c["name"])
def test_markup_percent(case):
    got = margins.markup_percent(case["consumer_price"], case["net_cost"])
    assert _eq(got, case["expected"]), f"{case['name']}: {got}"


@pytest.mark.parametrize("case", CASES["margin_percent"], ids=lambda c: c["name"])
def test_margin_percent(case):
    got = margins.margin_percent(case["consumer_price"], case["net_cost"])
    assert _eq(got, case["expected"]), f"{case['name']}: {got}"


@pytest.mark.parametrize("case", CASES["effective_unit_cost"], ids=lambda c: c["name"])
def test_effective_unit_cost(case):
    got = margins.effective_unit_cost(case["total_paid"], case["total_received"])
    assert _eq(got, case["expected"]), f"{case['name']}: {got}"


@pytest.mark.parametrize("case", CASES["profit_per_pack"], ids=lambda c: c["name"])
def test_profit_per_pack(case):
    got = margins.profit_per_pack(case["unit_profit"], case["units_per_pack"])
    assert _eq(got, case["expected"]), f"{case['name']}: {got}"


@pytest.mark.parametrize("case", CASES["effective_consumer_price"], ids=lambda c: c["name"])
def test_effective_consumer_price(case):
    got = margins.effective_consumer_price(case["batch_price"], case["product_price"])
    assert _eq(got, case["expected"]), f"{case['name']}: {got}"


@pytest.mark.parametrize("case", CASES["order_analysis"], ids=lambda c: c["name"])
def test_order_analysis(case):
    got = margins.order_analysis(**case["input"])
    for key, expected in case["expected"].items():
        assert key in got, f"{case['name']}: کلیدِ «{key}» نیامد"
        assert _eq(got[key], expected), f"{case['name']} / {key}: {got[key]}"


def test_keys_that_cannot_be_computed_are_absent_not_zero():
    """§۲۶ — «فقط زمانی نمایش داده شوند که داده‌های لازم وجود داشته باشند».

    صفر یا خط تیره برگرداندن یعنی کاربر عددی ببیند که معنایی ندارد.
    """
    out = margins.order_analysis(qty=5, list_price=1000)
    assert "potential_gross_profit" not in out
    assert "markup_percent" not in out
    assert "profit_per_pack" not in out
    assert "bonus_quantity" not in out


def test_markup_and_margin_are_not_the_same_number():
    """اشتباهِ رایجی که فروشنده را درباره‌ی سودش گمراه می‌کند."""
    assert margins.markup_percent(450000, 300000) == Decimal("50.0")
    assert margins.margin_percent(450000, 300000) == Decimal("33.3")
