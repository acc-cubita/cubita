"""ارسال پیامک — تک‌مسیرِ خروجِ پیامک از سیستم (قرینه‌ی mailer.py).

سرویسِ حاملِ پیام «ملی‌پیامک» (کنسولِ جدید، console.melipayamak.com) است. کلید در
`.env`ِ سراسری می‌نشیند، نه پرمستأجر — چون تنها یک حسابِ ملی‌پیامکِ خودِ کوبیتا وجود
دارد، درست مثلِ SMTP. جریان‌هایی که *قبل از* احرازِ هویت‌اند (کدِ فعال‌سازی، بازیابیِ
رمز با پیامک) و برندشان «کوبیتا» است طبیعتاً از همین حسابِ سراسری می‌روند.

**دو مسیرِ ارسال، عمداً جدا:**

۱. *الگو روی خطِ اشتراکی* (`send_verification_code`) — برای کدها. خطِ اشتراکیِ الگو
   فیلترِ کلمه‌ای ندارد و فوری می‌رسد؛ برای کدِ ورود که چند ثانیه تأخیر یعنی کاربرِ
   ناامید، این تنها انتخابِ درست است. متنِ الگو در پنل تأیید شده و فقط یک متغیر (کد)
   می‌گیرد.

۲. *متنِ آزاد از خطِ اختصاصی* (`send_text`) — برای یادآوری و رسیدِ فاکتور که متنشان
   بلند و متغیر است و در الگو نمی‌گنجد.

**سه رفتارِ عمدی — دقیقاً مثلِ mailer.py:**

۱. در توسعه، بدونِ کلید، متن (و کد) لاگ می‌شود تا جریان بدونِ ارسالِ واقعی تست شود.
۲. در production، بدونِ کلید، خطای بلند لاگ می‌شود — نه سکوت. حالتِ شکستِ واقعی این
   است که کسی کلید را کانفیگ نکند و کاربرها بی‌صدا کدشان را نگیرند.
۳. تابع هیچ استثنایی بیرون نمی‌دهد و فقط موفقیت را برمی‌گرداند: شکستِ ارسالِ پیامک
   نباید تراکنشی را که همین حالا رمز را عوض کرده یا فاکتور را ثبت کرده rollback کند.
"""
import logging
import re

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

#: کنسولِ جدیدِ ملی‌پیامک. کلید در مسیرِ URL می‌آید، نه هدر.
API_BASE = "https://console.melipayamak.com/api"

#: تبدیلِ ارقامِ فارسی/عربی به ASCII — کاربر ممکن است شماره را با کیبوردِ فارسی وارد کند.
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_phone(raw: str | None) -> str | None:
    """موبایلِ ایران را به فرمتِ ۰۹xxxxxxxxx یکدست می‌کند؛ None اگر معتبر نباشد.

    ورودی می‌تواند با ارقامِ فارسی، فاصله/خط‌تیره، یا پیش‌شماره‌ی +۹۸/۰۰۹۸/۹۸ باشد؛
    همه به یک شکل درمی‌آیند تا ملی‌پیامک قبولش کند. اعتبارسنجی این‌جا از هدررفتِ
    اعتبارِ پیامک روی شماره‌ی خراب جلوگیری می‌کند.
    """
    if not raw:
        return None
    s = re.sub(r"\D", "", raw.translate(_DIGITS))
    if s.startswith("0098"):
        s = s[4:]
    elif s.startswith("98") and len(s) == 12:
        s = s[2:]
    elif s.startswith("0"):
        s = s[1:]
    if re.fullmatch(r"9\d{9}", s):
        return "0" + s
    return None


def _ok(data: dict) -> bool:
    """پاسخِ موفقِ ملی‌پیامک: recId مثبت، یا وضعیتِ حاویِ «موفق»."""
    rec = data.get("recId")
    try:
        if rec is not None and int(rec) > 0:
            return True
    except (TypeError, ValueError):
        pass
    return "موفق" in str(data.get("status", ""))


def send_text(to: str, text: str) -> bool:
    """پیامکِ متنیِ آزاد از خطِ اختصاصی (یادآوری، رسیدِ فاکتور). True اگر تحویلِ سامانه شد."""
    settings = get_settings()
    phone = normalize_phone(to)
    if phone is None:
        logger.warning("ارسالِ پیامکِ متنی لغو شد: شماره‌ی نامعتبر %r", to)
        return False

    if not settings.melipayamak_api_key or not settings.melipayamak_sender:
        if settings.is_production:
            logger.error(
                "ملی‌پیامک کانفیگ نشده و این نمونه production است؛ پیامکِ متنی برای %s ارسال نشد.",
                phone,
            )
            return False
        logger.warning("[پیامکِ شبیه‌سازی‌شده] به: %s\n%s", phone, text)
        return True

    url = f"{API_BASE}/send/simple/{settings.melipayamak_api_key}"
    body = {"from": settings.melipayamak_sender, "to": phone, "text": text}
    try:
        res = httpx.post(url, json=body, timeout=20.0)
        data = res.json() if res.content else {}
        if _ok(data):
            return True
        logger.warning("ارسالِ پیامکِ متنی به %s ناموفق بود: %s", phone, data.get("status"))
        return False
    except Exception as exc:
        logger.warning("ارسالِ پیامکِ متنی به %s خطا داد: %s", phone, exc)
        return False


def send_pattern(to: str, args: list[str]) -> bool:
    """ارسال با الگوی خطِ اشتراکی (bodyId). برای کدها. True اگر تحویلِ سامانه شد."""
    settings = get_settings()
    phone = normalize_phone(to)
    if phone is None:
        logger.warning("ارسالِ الگو لغو شد: شماره‌ی نامعتبر %r", to)
        return False

    if not settings.melipayamak_api_key or not settings.melipayamak_otp_pattern_id:
        if settings.is_production:
            logger.error(
                "ملی‌پیامک/الگو کانفیگ نشده و این نمونه production است؛ کد برای %s ارسال نشد. "
                "کاربرانی که منتظرِ کدِ ورود یا بازیابی‌اند بی‌صدا قفل می‌مانند.",
                phone,
            )
            return False
        # فقط توسعه: خودِ کد لاگ می‌شود تا جریان قابلِ تست باشد.
        logger.warning("[پیامکِ الگوی شبیه‌سازی‌شده] به: %s | args=%s", phone, args)
        return True

    url = f"{API_BASE}/send/shared/{settings.melipayamak_api_key}"
    body = {"bodyId": int(settings.melipayamak_otp_pattern_id), "to": phone, "args": list(args)}
    try:
        res = httpx.post(url, json=body, timeout=20.0)
        data = res.json() if res.content else {}
        if _ok(data):
            return True
        logger.warning("ارسالِ الگو به %s ناموفق بود: %s", phone, data.get("status"))
        return False
    except Exception as exc:
        logger.warning("ارسالِ الگو به %s خطا داد: %s", phone, exc)
        return False


def send_verification_code(to: str, code: str) -> bool:
    """کدِ تأیید (فعال‌سازی/بازیابیِ رمز) را با الگوی تأییدشده می‌فرستد."""
    return send_pattern(to, [code])


def get_credit() -> float | None:
    """اعتبارِ باقی‌ماندهٔ حساب (رایگان)؛ None اگر کلید نبود یا خطا خورد.

    برای نمایش در پنلِ ادمین و هشدارِ «اعتبار رو به اتمام» پیش از آنکه ارسال‌ها بی‌صدا رد شوند.
    """
    settings = get_settings()
    if not settings.melipayamak_api_key:
        return None
    try:
        res = httpx.get(f"{API_BASE}/receive/credit/{settings.melipayamak_api_key}", timeout=15.0)
        data = res.json() if res.content else {}
        amount = data.get("amount")
        return float(amount) if amount is not None else None
    except Exception as exc:
        logger.warning("خواندنِ اعتبارِ ملی‌پیامک خطا داد: %s", exc)
        return None
