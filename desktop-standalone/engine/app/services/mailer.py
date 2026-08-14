"""ارسال ایمیل — تک مسیر خروج پیام از سیستم.

تا امروز تنها ایمیل سیستم یک تابع مخصوص «اعلان خرید به مدیر» بود. حالا که بازیابی
رمز و دعوت همکار اضافه شده‌اند، ایمیل از یک اعلان جانبی به مسیر بحرانی تبدیل شده:
اگر ایمیل نرود، کاربر قفل بیرون می‌ماند.

**سه رفتار عمدی:**

۱. *در توسعه، بدون SMTP، متن کامل لاگ می‌شود.* بدون این، هیچ توسعه‌دهنده‌ای
   نمی‌توانست جریان بازیابی رمز را تست کند مگر با راه‌اندازی SMTP واقعی.

۲. *در production هرگز متن لاگ نمی‌شود.* لینک بازیابی عملاً یک رمز یک‌بارمصرف است؛
   نوشتنش در لاگ یعنی هر کسی با دسترسی لاگ می‌تواند حساب‌ها را تصاحب کند. این تنها
   جایی است که رفتار dev و production عمداً فرق می‌کند و دلیلش همین است.

۳. *نبودِ SMTP در production خطای بلند است، نه سکوت.* حالت شکست واقعی این نیست که
   ایمیل «کمی دیر» برسد؛ این است که کسی SMTP را کانفیگ نکند و ماه‌ها هیچ‌کس نفهمد
   چرا مشتری‌ها می‌گویند لینک بازیابی نمی‌آید.

تابع هیچ استثنایی بیرون نمی‌دهد و فقط موفقیت را برمی‌گرداند: شکست ارسال ایمیل نباید
تراکنشی را که همین حالا رمز را عوض کرده یا عضویت ساخته rollback کند.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> bool:
    """True اگر پیام تحویل SMTP شد (یا در dev لاگ شد)."""
    settings = get_settings()

    if not settings.smtp_host or not settings.smtp_user:
        if settings.is_production:
            logger.error(
                "SMTP کانفیگ نشده و این نمونه production است؛ ایمیل «%s» برای %s ارسال نشد. "
                "کاربرانی که رمزشان را فراموش کنند قفل بیرون می‌مانند.",
                subject,
                to,
            )
            return False
        # فقط توسعه: متن کامل لاگ می‌شود تا لینک قابل استفاده باشد.
        logger.warning("[ایمیل شبیه‌سازی‌شده] به: %s\nموضوع: %s\n\n%s", to, subject, body)
        return True

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_user
    message["To"] = to
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
        return True
    except Exception as exc:
        # موضوع لاگ می‌شود ولی متن هرگز — متن حاوی لینک یک‌بارمصرف است.
        logger.warning("ارسال ایمیل «%s» به %s ناموفق بود: %s", subject, to, exc)
        return False


def _link(action: str, token: str) -> str:
    """لینک به ریشه‌ی اپ با پارامتر action — عمداً نه مسیر جدا.

    اپ یک SPA است و روی هاست ایستا هر مسیری جز `/` نیاز به تنظیم fallback دارد.
    لینکی مثل `/reset-password?token=...` روی میزبانی که آن تنظیم را ندارد ۴۰۴
    می‌دهد — و این خرابی فقط در ایمیلِ مشتریِ قفل‌شده دیده می‌شود، نه در توسعه.
    پارامتر روی ریشه همیشه index.html را می‌آورد.
    """
    return f"{get_settings().app_url.rstrip('/')}/?action={action}&token={token}"


def send_password_reset(to: str, name: str, token: str, valid_hours: int) -> bool:
    return send_email(
        to,
        "بازیابی رمز عبور کوبیتا",
        f"{name} عزیز،\n\n"
        "برای حساب شما در کوبیتا درخواست بازیابی رمز عبور ثبت شد.\n"
        f"برای انتخاب رمز تازه روی این لینک بروید:\n\n{_link('reset-password', token)}\n\n"
        f"این لینک تا {valid_hours} ساعت معتبر است و فقط یک بار قابل استفاده است.\n\n"
        "اگر شما این درخواست را نداده‌اید، این ایمیل را نادیده بگیرید؛ رمز فعلی شما تغییر نکرده است.",
    )


def send_invitation(to: str, tenant_name: str, inviter_name: str, token: str, valid_days: int) -> bool:
    return send_email(
        to,
        f"دعوت به {tenant_name} در کوبیتا",
        f"سلام،\n\n"
        f"{inviter_name} شما را به «{tenant_name}» در کوبیتا دعوت کرده است.\n"
        f"برای فعال کردن حساب و انتخاب رمز عبور روی این لینک بروید:\n\n"
        f"{_link('accept-invite', token)}\n\n"
        f"این لینک تا {valid_days} روز معتبر است.",
    )


def send_trial_reminder(to: str, name: str, days_left: int, plans_url: str) -> bool:
    """یادآوریِ نزدیک‌شدنِ پایانِ نسخه‌ی آزمایشی — تنها اهرمِ نگه‌داشتنِ دیتای واردشده.

    لحن صریح است چون همین صراحت کاربر را به تصمیم می‌رساند: اگر پلن نخری، اطلاعاتت
    حذف می‌شود — و اگر بخری، همین اطلاعات حفظ می‌شود.
    """
    return send_email(
        to,
        "یادآوری: پایانِ نسخه‌ی آزمایشیِ کوبیتا نزدیک است",
        f"{name} عزیز،\n\n"
        f"نسخه‌ی آزمایشیِ رایگانِ شما در کوبیتا حدود {days_left} روزِ دیگر به پایان می‌رسد.\n"
        "برای اینکه اطلاعاتی که وارد کرده‌اید حفظ شود و کارتان بدون وقفه ادامه یابد، "
        "پیش از پایانِ دوره یک پلن تهیه کنید:\n\n"
        f"{plans_url}\n\n"
        "خرید با همین ایمیل، حساب شما را دقیقاً با همین اطلاعات فعال نگه می‌دارد.\n"
        "اگر تا پایانِ دوره پلن تهیه نکنید، اطلاعاتِ این حساب پس از مدتِ کوتاهی حذف خواهد شد.",
    )


def send_email_verification_code(to: str, name: str, code: str, valid_minutes: int) -> bool:
    """کدِ تأییدِ ایمیل هنگامِ ثبت‌نام — تا فقط ایمیلِ واقعی بتواند حساب بسازد.

    برخلافِ لینک‌های بازیابی/دعوت که یک راز ۲۵۶بیتی‌اند، این یک کدِ کوتاهِ عددی است که
    کاربر دستی وارد می‌کند؛ پس در متنِ ایمیل خودِ کد می‌آید، نه لینک.
    """
    greeting = f"{name} عزیز،\n\n" if name and name.strip() else "سلام،\n\n"
    return send_email(
        to,
        "کد تأیید ایمیل — کوبیتا",
        f"{greeting}"
        "برای تکمیلِ ثبت‌نام در کوبیتا، کدِ تأیید زیر را در همان صفحه وارد کنید:\n\n"
        f"    {code}\n\n"
        f"این کد تا {valid_minutes} دقیقه معتبر است.\n\n"
        "اگر شما درخواستِ ثبت‌نام نداده‌اید، این ایمیل را نادیده بگیرید.",
    )


def send_welcome_after_purchase(to: str, name: str, tenant_name: str, token: str, valid_days: int) -> bool:
    """اعتبارنامه‌ی مشتری بعد از پرداخت — به خودِ مشتری، نه به مدیر.

    قبلاً رمز موقت در ایمیل اعلان برای مدیر فرستاده می‌شد تا او دستی به مشتری بدهد.
    یعنی مشتری بعد از پرداخت منتظر یک انسان می‌ماند و رمزش از یک صندوق ایمیل دیگر
    عبور می‌کرد. حالا مشتری لینکی می‌گیرد که خودش رمز را انتخاب می‌کند و هیچ رمزی
    جایی نوشته نمی‌شود.
    """
    return send_email(
        to,
        "خرید شما تکمیل شد — کوبیتا",
        f"{name} عزیز،\n\n"
        f"خرید شما با موفقیت انجام شد و کسب‌وکار «{tenant_name}» برای شما ساخته شد.\n"
        f"برای انتخاب رمز عبور و ورود، روی این لینک بروید:\n\n"
        f"{_link('accept-invite', token)}\n\n"
        f"این لینک تا {valid_days} روز معتبر است.\n\n"
        "اگر لینک منقضی شد، از صفحه‌ی ورود گزینه‌ی «رمز عبور را فراموش کرده‌ام» را بزنید.",
    )
