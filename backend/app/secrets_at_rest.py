"""رمزگذاریِ رازها در حالتِ سکون — کلیدِ امضای سامانه‌ی مؤدیان.

## چه چیزی را حل می‌کند، و چه چیزی را نه

کلیدِ خصوصیِ امضای صورتحساب تا امروز متنِ خام در `moadian_settings` می‌نشست.
سه دفاع داشت و هر سه واقعی‌اند: هرگز از API برنمی‌گشت (خروجی فقط
`has_private_key` است)، در لاگ نمی‌آمد، و RLS بینِ کسب‌وکارها جدایش می‌کرد.

ولی هیچ‌کدام **یک نسخه‌ی پشتیبان** را پوشش نمی‌دادند. یک `pg_dump` یعنی کلیدِ
امضای همه‌ی کسب‌وکارها در دستِ کسی که آن فایل را دارد — یعنی توانِ فرستادنِ
صورتحسابِ رسمی به نامِ آن‌ها.

پس تهدیدی که این ماژول می‌بندد **دقیقاً همین است**: دیتابیسِ دزدیده‌شده. و
تهدیدی که نمی‌بندد هم باید صریح گفته شود: اگر خودِ سرورِ اپ در اختیار مهاجم
باشد، کلیدِ رمزگذاری هم در محیطش هست. این معاوضه آگاهانه است — رمزگذاری در
حالتِ سکون یک لایه است، نه همه‌ی لایه‌ها.

## چرا کلید از محیط می‌آید، نه از دیتابیس

اگر کلیدِ رمزگذاری کنارِ داده‌ی رمزشده بنشیند، رمزگذاری نمایشی است. پس
`SECRETS_KEY` از محیط خوانده می‌شود و **هرگز کامیت نمی‌شود** — همان قاعده‌ای که
برای `JWT_SECRET` هم برقرار است.

## شکلِ داده

    enc:v1:<fernet token>

پیشوند صریح است تا بشود متنِ رمزشده را از کلیدِ خامِ قدیمی تشخیص داد، و نسخه
دارد تا روزی که الگوریتم عوض شود مهاجرتش تعریف‌شدنی باشد. مقدارِ بی‌پیشوند
یعنی «هنوز رمز نشده» و همان‌طور خوانده می‌شود — پس این ماژول روی داده‌ی
مهاجرت‌نشده هم نمی‌شکند.

## از دست رفتنِ کلید

اگر `SECRETS_KEY` گم شود، کلیدهای امضا **برنمی‌گردند**. غیرقابل‌جبران نیست —
هر کسب‌وکار کلیدش را دوباره از کارپوشه می‌گیرد و آپلود می‌کند — ولی یعنی تا آن
لحظه هیچ صورتحسابی ارسال نمی‌شود. به همین دلیل خواندنِ ناموفق **خطای صریح**
می‌دهد، نه رشته‌ی خالی: «کلید نیست» و «کلید خوانده نشد» دو چیزِ متفاوتند و
قاطی‌کردنشان یعنی کاربر فکر کند اعتبارنامه‌اش پاک شده.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

PREFIX = "enc:v1:"


class SecretUnreadable(RuntimeError):
    """راز هست ولی باز نمی‌شود — کلیدِ اشتباه، یا کلیدِ گم‌شده."""


def _fernet() -> Fernet | None:
    """کلیدِ رمزگذاری از محیط. `None` یعنی تنظیم نشده.

    کلیدِ متنیِ کاربر با SHA-256 به ۳۲ بایت تبدیل می‌شود تا لازم نباشد کاربر
    حتماً یک کلیدِ Fernetِ base64 بسازد — همان راحتی‌ای که `JWT_SECRET` دارد.
    """
    raw = (getattr(get_settings(), "secrets_key", "") or "").strip()
    if not raw:
        return None
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def is_configured() -> bool:
    return _fernet() is not None


def is_encrypted(value: str | None) -> bool:
    return bool(value) and value.startswith(PREFIX)


def encrypt(value: str | None) -> str:
    """رمز می‌کند. بی‌کلید، **همان متنِ خام برمی‌گردد**.

    این عمدی است: نبودِ `SECRETS_KEY` نباید جلوی ذخیره‌ی اعتبارنامه را بگیرد و
    کسب‌وکار را از ارسالِ صورتحساب بیندازد. گاردِ راه‌اندازی در `config` هشدارش
    را می‌دهد؛ این‌جا جای شکستن نیست.
    """
    text = value or ""
    if not text.strip() or is_encrypted(text):
        return text
    box = _fernet()
    if box is None:
        return text
    return PREFIX + box.encrypt(text.encode("utf-8")).decode("ascii")


def decrypt(value: str | None) -> str:
    """باز می‌کند. مقدارِ بی‌پیشوند دست‌نخورده برمی‌گردد (داده‌ی مهاجرت‌نشده)."""
    text = value or ""
    if not is_encrypted(text):
        return text
    box = _fernet()
    if box is None:
        raise SecretUnreadable(
            "این اعتبارنامه رمزگذاری‌شده ذخیره شده ولی SECRETS_KEY تنظیم نیست؛ "
            "بدونِ آن کلیدِ امضا خوانده نمی‌شود."
        )
    try:
        return box.decrypt(text[len(PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretUnreadable(
            "کلیدِ امضا با SECRETS_KEYِ فعلی باز نمی‌شود — کلید عوض شده است. "
            "یا کلیدِ درست را برگردانید، یا اعتبارنامه را دوباره از کارپوشه آپلود کنید."
        ) from exc
