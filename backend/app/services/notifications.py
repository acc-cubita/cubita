import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings
from app.models.billing import Purchase


def send_purchase_paid_notification(purchase: Purchase, provisioned=None) -> None:
    """به مدیر ایمیل می‌زند که یک خرید جدید پرداخت شده.

    `provisioned` نتیجه‌ی provisioning خودکار است: (مستأجر، توکن راه‌اندازی) در صورت
    موفقیت، یا None اگر شکست خورده باشد. در حالت دوم ایمیل صراحتاً می‌گوید که تحویل
    دستی لازم است — چون پول گرفته شده و سکوت در این حالت یعنی مشتری منتظر می‌ماند
    بدون اینکه کسی بداند.

    **توکن راه‌اندازی عمداً در این ایمیل نمی‌آید.** قبلاً رمز موقت مشتری اینجا نوشته
    می‌شد تا مدیر دستی تحویلش دهد؛ حالا لینک مستقیم به خودِ مشتری می‌رود و این ایمیل
    فقط اطلاع‌رسانی است. نوشتن آن توکن اینجا یعنی صندوق ایمیل مدیر کلید ورود به حساب
    هر مشتری تازه را نگه می‌دارد.

    عمداً هیچ استثنایی بیرون نمی‌اندازد: شکست ارسال ایمیل نباید verify کردن پرداخت
    واقعی را خراب کند.
    """
    settings = get_settings()
    if not settings.smtp_host or not settings.admin_notify_email:
        return

    if provisioned:
        tenant, setup_token = provisioned
        if setup_token:
            delivery = (
                f"\n✅ کسب‌وکار خودکار ساخته شد و لینک راه‌اندازی به خودِ مشتری ایمیل شد.\n"
                f"   شناسه: {tenant.slug}\n"
                f"   ورود: {purchase.customer_email}\n"
                f"   اگر مشتری گفت لینک نرسیده، از او بخواهید «رمز عبور را فراموش کرده‌ام» را بزند.\n"
            )
        else:
            delivery = f"\n✅ این مشتری از قبل کسب‌وکار دارد ({tenant.slug}) — احتمالاً تمدید یا ارتقاست.\n"
    else:
        delivery = (
            "\n⚠️ ساخت خودکار کسب‌وکار انجام نشد — پرداخت موفق بوده ولی تحویل باید دستی انجام شود.\n"
        )

    msg = EmailMessage()
    msg["Subject"] = f"خرید جدید کوبیتا: پلن {purchase.plan_name} — {purchase.customer_name}"
    msg["From"] = settings.smtp_user
    msg["To"] = settings.admin_notify_email
    msg.set_content(
        "یک خرید جدید در سایت تجاری کوبیتا پرداخت شد:\n\n"
        f"پلن: {purchase.plan_name}\n"
        f"مبلغ: {int(purchase.amount_toman):,} تومان\n"
        f"نام مشتری: {purchase.customer_name}\n"
        f"کسب‌وکار: {purchase.business_name or '—'}\n"
        f"ایمیل: {purchase.customer_email}\n"
        f"شماره تماس: {purchase.customer_phone or '—'}\n"
        f"کد پیگیری زرین‌پال: {purchase.zarinpal_ref_id}\n"
        f"شناسه خرید: {purchase.id}\n"
        f"{delivery}",
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    except Exception as e:
        logging.warning(f"ارسال ایمیل اعلان خرید ناموفق بود: {e}")
