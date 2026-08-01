"""محدودیت نرخ برای اندپوینت‌های عمومی.

**محدودیت مهم این پیاده‌سازی:** شمارنده در حافظه‌ی همین پروسه است. با چند worker
یا چند نمونه، هر کدام سهم خودش را دارد و سقف مؤثر ضربدر تعداد پروسه‌ها می‌شود.
برای استقرار واقعی باید به Redis منتقل شود.

با این حال همین نسخه ارزش دارد: امروز هیچ محدودیتی وجود ندارد، یعنی credential
stuffing نامحدود روی login و ساخت نامحدود مستأجر روی signup — و هر مستأجر حدود
۴۰ ردیف می‌سازد، پس ثبت‌نام خودکار عملاً یک بردار پرکردن پایگاه‌داده است.
سقف پر‌سوراخ از نبود سقف بهتر است، به شرطی که کسی فکر نکند مسئله حل شده.
"""
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: int):
        self.max_events = max_events
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.max_events:
                retry_after = int(self.window - (now - hits[0])) + 1
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "تعداد درخواست‌ها بیش از حد مجاز است؛ کمی بعد دوباره تلاش کنید",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_key(request: Request) -> str:
    """کلید محدودیت از روی IP.

    وقتی پشت پراکسی است، X-Forwarded-For اولین مقدارش IP واقعی کاربر است. این
    هدر قابل جعل است، ولی برای محدودیت نرخ قابل قبول است: بدترین حالت این است که
    مهاجم سقف خودش را دور بزند، نه اینکه کاربر دیگری را قفل کند — چون کلید فقط
    برای شمارش خودِ همان درخواست‌ها استفاده می‌شود.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# سقف‌ها عمداً سخت‌گیرانه نیستند: هدف جلوگیری از سوءاستفاده‌ی خودکار است، نه اذیت
# کردن کاربری که رمزش را چند بار اشتباه می‌زند.
_login_limiter = SlidingWindowLimiter(max_events=10, window_seconds=300)
_signup_limiter = SlidingWindowLimiter(max_events=3, window_seconds=3600)
_password_reset_limiter = SlidingWindowLimiter(max_events=5, window_seconds=900)
#: سقف جداگانه بر اساس خودِ ایمیل، نه IP. بدون این، مهاجم از چند IP می‌تواند صندوق
#: یک نفر مشخص را با ایمیل بازیابی پر کند — که خرابکاری علیه قربانی است، نه علیه ما،
#: و سقف مبتنی بر IP اصلاً نمی‌بیندش.
_password_reset_per_email = SlidingWindowLimiter(max_events=3, window_seconds=3600)
#: ارسالِ کدِ پیامکی هزینه‌ی واقعی دارد (هر پیامک از اعتبارِ ملی‌پیامک کم می‌کند)، پس
#: سقفش سخت‌گیرانه‌تر است: هدف جلوگیری از تخلیه‌ی اعتباب با درخواستِ پیاپیِ کد است.
_sms_code_limiter = SlidingWindowLimiter(max_events=5, window_seconds=900)


def limit_login(request: Request) -> None:
    _login_limiter.check(f"login:{client_key(request)}")


def limit_signup(request: Request) -> None:
    _signup_limiter.check(f"signup:{client_key(request)}")


def limit_password_reset(request: Request) -> None:
    _password_reset_limiter.check(f"reset:{client_key(request)}")


def limit_sms_code(request: Request) -> None:
    _sms_code_limiter.check(f"sms-code:{client_key(request)}")


def limit_password_reset_for_email(email: str) -> bool:
    """False یعنی این ایمیل به سقف خورده.

    برخلاف بقیه استثنا نمی‌اندازد: پاسخِ اندپوینت بازیابی باید در همه‌ی حالت‌ها یکسان
    بماند، وگرنه ۴۲۹ برای ایمیل‌های موجود و ۲۰۲ برای ایمیل‌های ناموجود دقیقاً همان
    نشت شمارش کاربران را می‌دهد که کل طراحی برای جلوگیری از آن است.
    """
    try:
        _password_reset_per_email.check(f"reset-email:{email.strip().lower()}")
        return True
    except HTTPException:
        return False


def reset_all() -> None:
    """فقط برای تست — وگرنه تست‌ها به‌خاطر سقف مشترک روی هم اثر می‌گذارند."""
    _login_limiter.reset()
    _signup_limiter.reset()
    _password_reset_limiter.reset()
    _password_reset_per_email.reset()
    _sms_code_limiter.reset()
