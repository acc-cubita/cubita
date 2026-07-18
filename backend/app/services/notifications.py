import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings
from app.models.billing import Purchase


def send_purchase_paid_notification(purchase: Purchase) -> None:
    """به مدیر ایمیل می‌زند که یک خرید جدید پرداخت شده و منتظر تحویل دستی است.
    عمداً هیچ استثنایی بیرون نمی‌اندازد — شکست ارسال ایمیل نباید verify کردن پرداخت واقعی را خراب کند."""
    settings = get_settings()
    if not settings.smtp_host or not settings.admin_notify_email:
        return

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
        f"شناسه خرید: {purchase.id}\n\n"
        "برای راه‌اندازی نسخه‌ی اختصاصی و ثبت تحویل، به صفحه‌ی «خریدهای سایت تجاری» در اپ مراجعه کنید.",
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    except Exception as e:
        logging.warning(f"ارسال ایمیل اعلان خرید ناموفق بود: {e}")
