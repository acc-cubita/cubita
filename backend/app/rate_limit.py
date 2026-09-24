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
#: کدِ تأییدِ ایمیلِ ثبت‌نام. سقفِ IP کمی بازتر از پیامک است (ایمیل هزینه‌ی مستقیم ندارد و
#: کاربر ممکن است ایمیل را تصحیح کند)، ولی جلوی ارسالِ خودکارِ انبوه را می‌گیرد.
_email_code_limiter = SlidingWindowLimiter(max_events=8, window_seconds=900)
#: سقفِ جداگانه بر اساس خودِ ایمیل — تا مهاجم از چند IP صندوقِ یک نفر را با کدِ ثبت‌نام
#: بمباران نکند (خرابکاری علیه قربانی، که سقفِ IP نمی‌بیندش).
_email_code_per_email = SlidingWindowLimiter(max_events=4, window_seconds=3600)
#: بازیابیِ رمز با پیامک — سقفِ جداگانه بر اساس خودِ شماره (قرینه‌ی نسخه‌ی ایمیلی)، تا
#: مهاجم از چند IP شماره‌ی یک قربانیِ مشخص را با پیامکِ کد بمباران و اعتبار را تخلیه نکند.
_password_reset_per_phone = SlidingWindowLimiter(max_events=3, window_seconds=3600)
#: راستی‌آزماییِ کدِ بازیابیِ پیامکی — سقفِ IP روی خودِ «سنجشِ کد». `consume_code` سقفِ ۵
#: تلاش را per-code دارد؛ این، حدسِ توزیع‌شده از یک IP روی چند شماره را هم می‌بندد.
_sms_reset_verify_limiter = SlidingWindowLimiter(max_events=10, window_seconds=900)
#: ورودِ ستاد (admin.cubita.ir). سخت‌گیرانه‌تر از ورودِ مستأجر (۱۰/۵دقیقه) چون این
#: دامنه هدفِ به‌مراتب باارزش‌تری است و سطلِ IP‌اش با هیچ چیزِ دیگری مشترک نیست.
#: سقفِ واقعی اما `limit_req`ِ nginx است — شمارنده‌ی اینجا درون‌فرایندی است و با
#: چند worker ضرب می‌شود (بالای همین فایل توضیح داده شده).
_admin_login_limiter = SlidingWindowLimiter(max_events=5, window_seconds=900)
#: سقفِ جداگانه بر اساس خودِ ایمیل، تا حدسِ رمزِ یک کارمندِ مشخص از چند IP بسته شود.
_admin_login_per_email = SlidingWindowLimiter(max_events=10, window_seconds=3600)
#: نوشتن‌های کنترل‌پنل. هدف نه حدسِ رمز، که مهارِ اسکریپتی است که تصادفاً روی
#: اندپوینتِ مخرب حلقه می‌زند.
_admin_write_limiter = SlidingWindowLimiter(max_events=120, window_seconds=60)
#: فعال‌سازیِ آنلاینِ کوبیتا سازمانی — عمومی است (سرورِ مشتری توکنی از ما ندارد)، پس
#: سقف جلوی حدسِ کدِ فعال‌سازی را می‌گیرد. کدِ ۸۰بیتی خودش حدس‌ناپذیر است؛ این لایه‌ی دوم است.
_license_activate_limiter = SlidingWindowLimiter(max_events=10, window_seconds=3600)


def limit_login(request: Request) -> None:
    _login_limiter.check(f"login:{client_key(request)}")


def limit_signup(request: Request) -> None:
    _signup_limiter.check(f"signup:{client_key(request)}")


def limit_password_reset(request: Request) -> None:
    _password_reset_limiter.check(f"reset:{client_key(request)}")


def limit_sms_code(request: Request) -> None:
    _sms_code_limiter.check(f"sms-code:{client_key(request)}")


def limit_email_code(request: Request) -> None:
    _email_code_limiter.check(f"email-code:{client_key(request)}")


def limit_email_code_for_email(email: str) -> bool:
    """False یعنی این ایمیل به سقف خورده. مثلِ بازیابیِ رمز استثنا نمی‌اندازد تا پاسخِ
    اندپوینت یکنواخت بماند و از روی تفاوتِ ۴۲۹/۲۰۰ نشود وجودِ ایمیل را استخراج کرد."""
    try:
        _email_code_per_email.check(f"email-code-email:{email.strip().lower()}")
        return True
    except HTTPException:
        return False


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


def limit_password_reset_for_phone(phone: str) -> bool:
    """False یعنی این شماره به سقف خورده. مثلِ نسخه‌ی ایمیلی استثنا نمی‌اندازد تا پاسخِ
    اندپوینتِ بازیابیِ پیامکی یکنواخت بماند و از تفاوتِ ۴۲۹/۲۰۲ وجودِ شماره لو نرود."""
    try:
        _password_reset_per_phone.check(f"reset-phone:{phone}")
        return True
    except HTTPException:
        return False


def limit_sms_reset_verify(request: Request) -> None:
    _sms_reset_verify_limiter.check(f"sms-reset-verify:{client_key(request)}")


def limit_admin_login(request: Request) -> None:
    _admin_login_limiter.check(f"admin-login:{client_key(request)}")


def limit_admin_login_for_email(email: str) -> None:
    """برخلافِ بازیابیِ رمز، اینجا استثنا می‌اندازد.

    آنجا یکنواختیِ پاسخ لازم بود تا وجودِ ایمیل لو نرود؛ اینجا هر پاسخِ ناموفق
    **یکسان** است (۴۰۱ـِ واحد برای رمزِ غلط، کاربرِ غیرفعال و نبودِ ردیفِ ستاد)، پس
    ۴۲۹ چیزی درباره‌ی وجودِ ایمیل نمی‌گوید.
    """
    _admin_login_per_email.check(f"admin-login-email:{email.strip().lower()}")


def limit_admin_write(request: Request) -> None:
    _admin_write_limiter.check(f"admin-write:{client_key(request)}")


def limit_license_activate(request: Request) -> None:
    _license_activate_limiter.check(f"license-activate:{client_key(request)}")


def reset_all() -> None:
    """فقط برای تست — وگرنه تست‌ها به‌خاطر سقف مشترک روی هم اثر می‌گذارند."""
    _login_limiter.reset()
    _signup_limiter.reset()
    _password_reset_limiter.reset()
    _password_reset_per_email.reset()
    _password_reset_per_phone.reset()
    _sms_reset_verify_limiter.reset()
    _sms_code_limiter.reset()
    _email_code_limiter.reset()
    _email_code_per_email.reset()
    _admin_login_limiter.reset()
    _admin_login_per_email.reset()
    _admin_write_limiter.reset()
    _license_activate_limiter.reset()
