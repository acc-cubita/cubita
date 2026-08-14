"""درگاه‌های پرداختِ خریدارِ سایت — لایه‌ی آداپتور برای زرین‌پال/زیبال/آی‌دی‌پی.

هر درگاه سه کار می‌کند: (۱) `start` تراکنش می‌سازد و لینکِ پرداخت را برمی‌گرداند،
(۲) `parse_callback` از پارامترهای بازگشتِ درگاه شناسه‌ی تراکنش و علامتِ موفقیت را
درمی‌آورد، (۳) `verify` پرداخت را نزدِ درگاه قطعی می‌کند. `shop_payment.py` این‌ها را
از روی `gateway.provider` صدا می‌زند؛ خودش نمی‌داند کدام درگاه است.

مبلغِ ورودیِ همه‌ی درگاه‌ها **ریال** است (تبدیلِ تومان→ریال در `shop_payment` انجام
می‌شود). همه‌ی تماس‌های شبکه از `_post` رد می‌شوند تا در تست یک‌جا mock شوند.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger("cubita.payment")


@dataclass
class StartResult:
    #: لینکی که خریدار به آن هدایت می‌شود.
    redirect_url: str
    #: شناسه‌ی تراکنشِ درگاه که در `order.payment_authority` ذخیره و در callback با آن سفارش پیدا می‌شود.
    authority: str


@dataclass
class CallbackParse:
    #: شناسه‌ی تراکنشِ درگاه (برای یافتنِ سفارش).
    authority: str
    #: علامتِ سریعِ موفقیت از خودِ callback — باز هم verify لازم است.
    ok_signal: bool


class ProviderError(Exception):
    """خطای قابلِ نمایشِ درگاه هنگامِ ساختِ تراکنش (به ۵۰۲ نگاشت می‌شود)."""


def _post(url: str, *, json: dict | None = None, data: dict | None = None,
          headers: dict | None = None, raise_for_status: bool = True) -> dict:
    with httpx.Client(timeout=20.0) as client:
        res = client.post(url, json=json, data=data,
                          headers={"Accept": "application/json", **(headers or {})})
        if raise_for_status:
            res.raise_for_status()
        return res.json()


class PaymentProvider:
    key: str = ""

    def start(self, *, merchant_id: str, amount_rial: int, callback_url: str,
              description: str, mobile: str, email: str, order_ref: str,
              sandbox: bool) -> StartResult:  # pragma: no cover - رابط
        raise NotImplementedError

    def parse_callback(self, params: dict[str, str]) -> CallbackParse:  # pragma: no cover - رابط
        raise NotImplementedError

    def verify(self, *, merchant_id: str, amount_rial: int, authority: str,
               order_ref: str, sandbox: bool) -> tuple[bool, str]:  # pragma: no cover - رابط
        raise NotImplementedError


# ── زرین‌پال (v4) ────────────────────────────────────────────────────────────────
class Zarinpal(PaymentProvider):
    key = "zarinpal"
    _API_PROD = "https://payment.zarinpal.com/pg/v4/payment"
    _API_SANDBOX = "https://sandbox.zarinpal.com/pg/v4/payment"
    _STARTPAY_PROD = "https://payment.zarinpal.com/pg/StartPay"
    _STARTPAY_SANDBOX = "https://sandbox.zarinpal.com/pg/StartPay"

    def _base(self, sandbox: bool) -> str:
        return self._API_SANDBOX if sandbox else self._API_PROD

    def start(self, *, merchant_id, amount_rial, callback_url, description, mobile, email, order_ref, sandbox):
        res = _post(
            f"{self._base(sandbox)}/request.json",
            json={
                "merchant_id": merchant_id,
                "amount": amount_rial,
                "callback_url": callback_url,
                "description": description,
                "metadata": {"mobile": mobile or "", "email": email or ""},
            },
        )
        authority = (res.get("data") or {}).get("authority")
        if not authority:
            raise ProviderError((res.get("errors") or {}).get("message", "خطا در ایجاد تراکنشِ پرداخت"))
        startpay = self._STARTPAY_SANDBOX if sandbox else self._STARTPAY_PROD
        return StartResult(redirect_url=f"{startpay}/{authority}", authority=authority)

    def parse_callback(self, params):
        return CallbackParse(authority=params.get("Authority", ""), ok_signal=params.get("Status") == "OK")

    def verify(self, *, merchant_id, amount_rial, authority, order_ref, sandbox):
        res = _post(
            f"{self._base(sandbox)}/verify.json",
            json={"merchant_id": merchant_id, "amount": amount_rial, "authority": authority},
        )
        data = res.get("data") or {}
        if data.get("code") not in (100, 101):
            return False, ""
        return True, str(data.get("ref_id", authority))


# ── زیبال (v1) ───────────────────────────────────────────────────────────────────
class Zibal(PaymentProvider):
    key = "zibal"
    _REQUEST = "https://gateway.zibal.ir/v1/request"
    _VERIFY = "https://gateway.zibal.ir/v1/verify"
    _START = "https://gateway.zibal.ir/start"

    def _merchant(self, merchant_id: str, sandbox: bool) -> str:
        # زیبال URLِ سندباکسِ جدا ندارد؛ مرچنتِ ویژه‌ی «zibal» حالتِ آزمایشی است.
        return "zibal" if sandbox else merchant_id

    def start(self, *, merchant_id, amount_rial, callback_url, description, mobile, email, order_ref, sandbox):
        res = _post(
            self._REQUEST,
            json={
                "merchant": self._merchant(merchant_id, sandbox),
                "amount": amount_rial,
                "callbackUrl": callback_url,
                "description": description,
                "mobile": mobile or "",
                "orderId": order_ref,
            },
        )
        if res.get("result") != 100 or not res.get("trackId"):
            raise ProviderError(res.get("message", "خطا در ایجاد تراکنشِ پرداخت"))
        track_id = str(res["trackId"])
        return StartResult(redirect_url=f"{self._START}/{track_id}", authority=track_id)

    def parse_callback(self, params):
        return CallbackParse(authority=params.get("trackId", ""), ok_signal=params.get("success") == "1")

    def verify(self, *, merchant_id, amount_rial, authority, order_ref, sandbox):
        res = _post(
            self._VERIFY,
            json={"merchant": self._merchant(merchant_id, sandbox), "trackId": authority},
        )
        # ۱۰۰ = موفق، ۲۰۱ = قبلاً verify شده (باز هم پرداخت‌شده محسوب می‌شود).
        if res.get("result") not in (100, 201):
            return False, ""
        return True, str(res.get("refNumber", authority))


# ── آی‌دی‌پی (v1.1) ─────────────────────────────────────────────────────────────
class IDPay(PaymentProvider):
    key = "idpay"
    _REQUEST = "https://api.idpay.ir/v1.1/payment"
    _VERIFY = "https://api.idpay.ir/v1.1/payment/verify"

    def _headers(self, merchant_id: str, sandbox: bool) -> dict:
        h = {"X-API-KEY": merchant_id, "Content-Type": "application/json"}
        if sandbox:
            h["X-SANDBOX"] = "1"
        return h

    def start(self, *, merchant_id, amount_rial, callback_url, description, mobile, email, order_ref, sandbox):
        res = _post(
            self._REQUEST,
            json={
                "order_id": order_ref,
                "amount": amount_rial,
                "callback": callback_url,
                "phone": mobile or "",
                "mail": email or "",
                "desc": description,
            },
            headers=self._headers(merchant_id, sandbox),
            raise_for_status=False,
        )
        if not res.get("id") or not res.get("link"):
            raise ProviderError(res.get("error_message", "خطا در ایجاد تراکنشِ پرداخت"))
        return StartResult(redirect_url=res["link"], authority=str(res["id"]))

    def parse_callback(self, params):
        # callbackِ آی‌دی‌پی POSTِ فرم است؛ status=10 یعنی «در انتظارِ تأیید» که باید verify شود.
        return CallbackParse(authority=params.get("id", ""), ok_signal=params.get("status") in ("10", "100", "200"))

    def verify(self, *, merchant_id, amount_rial, authority, order_ref, sandbox):
        res = _post(
            self._VERIFY,
            json={"id": authority, "order_id": order_ref},
            headers=self._headers(merchant_id, sandbox),
            raise_for_status=False,
        )
        # ۱۰۰ = پرداختِ تأییدشده، ۲۰۰ = به حسابِ پذیرنده واریز شد.
        if res.get("status") not in (100, 200):
            return False, ""
        return True, str(res.get("track_id", authority))


_PROVIDERS: dict[str, PaymentProvider] = {p.key: p for p in (Zarinpal(), Zibal(), IDPay())}


def get_provider(key: str) -> PaymentProvider | None:
    return _PROVIDERS.get(key)
