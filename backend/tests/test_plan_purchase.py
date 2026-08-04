"""خریدِ پلن از سایتِ تجاری — مبلغِ درگاه و طولِ اشتراک باید از دوره‌ی *انتخابیِ* مشتری بیاید.

بدونِ این، خریدِ ماهانه هم مبلغِ سالانه به درگاه می‌فرستاد یا یک سال اعتبار می‌گرفت.
"""
import pytest
from pydantic import ValidationError

from app.schemas.billing import PurchaseRequestIn
from app.services import billing
from app.services.subscriptions import days_for_period


@pytest.fixture
def fake_zarinpal(monkeypatch):
    """درگاه را جعل می‌کنیم تا مبلغِ ارسالی را بگیریم بی‌آنکه واقعاً تماس گرفته شود."""
    calls: list[dict] = []

    def fake_call(path, payload):
        calls.append(payload)
        return {"data": {"authority": "A" + str(len(calls))}}

    monkeypatch.setattr(billing, "_zarinpal_call", fake_call)
    return calls


def _req(period: str) -> PurchaseRequestIn:
    return PurchaseRequestIn(
        plan_key="basic", customer_name="آزمون", customer_email="buyer@example.com", billing_period=period
    )


def test_amount_and_period_follow_selected_period(db, fake_zarinpal):
    # قیمت‌های seed‌شده‌ی پلن پایه: ماهانه ۴۵۰٬۰۰۰ / شش‌ماهه ۲٬۴۳۰٬۰۰۰ / سالانه ۴٬۳۲۰٬۰۰۰
    expected = {"monthly": 450_000, "semiannual": 2_430_000, "yearly": 4_320_000}
    for period, toman in expected.items():
        purchase, url = billing.create_purchase_request(db, _req(period))
        assert int(purchase.amount_toman) == toman, period
        assert purchase.billing_period == period
        assert url  # لینکِ پرداخت ساخته شد
    # مبلغِ ارسالی به درگاه باید ریال (تومان×۱۰) و برابرِ همان دوره باشد
    assert fake_zarinpal[0]["amount"] == 450_000 * 10
    assert fake_zarinpal[-1]["amount"] == 4_320_000 * 10


def test_subscription_days_match_period():
    assert days_for_period("monthly") == 30
    assert days_for_period("semiannual") == 180
    assert days_for_period("yearly") == 365


def test_invalid_billing_period_is_rejected():
    with pytest.raises(ValidationError):
        _req("weekly")
