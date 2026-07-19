"""ساخت خودکار کسب‌وکار جدید.

جایگزین تحویل دستی. تا امروز تنها راه ساخت مشتری جدید اجرای `python -m app.seed`
روی سرور بود؛ مدل billing هم صراحتاً می‌گفت Purchase فقط «صف تحویل دستی» است.

دو مسیر ورودی دارد و هر دو به یک تابع می‌رسند:
  - ثبت‌نام مستقیم از سایت
  - callback تأییدشده‌ی زرین‌پال بعد از خرید پلن
"""
import re
import unicodedata
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.tenant import Membership, Tenant
from app.models.user import User
from app.seed import provision_tenant

MAX_SLUG_LEN = 60


def make_slug(name: str) -> str:
    """اسلاگ امن از نام کسب‌وکار.

    نام‌ها فارسی‌اند و اسلاگ لاتین از آن‌ها درنمی‌آید، پس وقتی چیزی باقی نماند به
    شناسه‌ی تصادفی برمی‌گردیم. اسلاگ فقط شناسه‌ی فنی است و به کاربر نشان داده
    نمی‌شود، پس خوانا بودنش مهم نیست — یکتا بودنش مهم است.
    """
    normalized = unicodedata.normalize("NFKD", name)
    ascii_only = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    if not ascii_only:
        return f"biz-{uuid4().hex[:12]}"
    return ascii_only[:MAX_SLUG_LEN]


def unique_slug(db: Session, name: str) -> str:
    base = make_slug(name)
    if not db.query(Tenant).filter(Tenant.slug == base).first():
        return base
    # برخورد اسلاگ نباید ثبت‌نام را شکست بدهد؛ کاربر ربطی به آن ندارد.
    for _ in range(5):
        candidate = f"{base[:MAX_SLUG_LEN - 9]}-{uuid4().hex[:8]}"
        if not db.query(Tenant).filter(Tenant.slug == candidate).first():
            return candidate
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "ساخت شناسه‌ی یکتا برای کسب‌وکار ناموفق بود")


def signup_new_business(
    db: Session,
    *,
    business_name: str,
    owner_name: str,
    email: str,
    password: str,
) -> tuple[Tenant, User]:
    """کاربر و کسب‌وکارش را در یک تراکنش می‌سازد.

    تراکنشی بودن اینجا اهمیت دارد: کسب‌وکاری که نیمه‌ساخته بماند — مثلاً بدون
    شمارنده‌ی سند — در ظاهر سالم است و اولین باری که کاربر بخواهد فاکتور بزند
    شکست می‌خورد. get_db کل درخواست را یک تراکنش می‌کند، پس یا همه‌چیز ساخته
    می‌شود یا هیچ‌چیز.
    """
    email = email.strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing is not None:
        # عمداً مبهم: تأیید وجود یا نبود ایمیل به مهاجم فهرست کاربران می‌دهد.
        raise HTTPException(status.HTTP_409_CONFLICT, "امکان ثبت‌نام با این ایمیل نیست")

    tenant = provision_tenant(
        db,
        name=business_name,
        slug=unique_slug(db, business_name),
        owner_email=email,
        owner_password=password,
        owner_name=owner_name,
    )
    user = db.query(User).filter(User.email == email).one()
    return tenant, user


def provision_for_purchase(db: Session, purchase) -> tuple[Tenant, str] | None:
    """بعد از پرداخت تأییدشده، کسب‌وکار مشتری را می‌سازد.

    idempotent است چون callback زرین‌پال می‌تواند دوباره بیاید و کاربر هم ممکن
    است صفحه را رفرش کند. اگر این کاربر از قبل مستأجری دارد، چیزی ساخته نمی‌شود
    و همان برگردانده می‌شود.

    رمز موقت برمی‌گرداند تا فراخواننده ایمیلش کند. ذخیره نمی‌شود.
    """
    email = (purchase.customer_email or "").strip().lower()
    if not email:
        return None

    user = db.query(User).filter(User.email == email).first()
    if user is not None:
        membership = db.query(Membership).filter(Membership.user_id == user.id).first()
        if membership is not None:
            # از قبل مشتری است — خرید جدید یعنی تمدید/ارتقا، نه کسب‌وکار جدید.
            return db.get(Tenant, membership.tenant_id), ""

    temp_password = uuid4().hex[:16]
    tenant = provision_tenant(
        db,
        name=purchase.business_name or purchase.customer_name or "کسب‌وکار جدید",
        slug=unique_slug(db, purchase.business_name or purchase.customer_name or "business"),
        owner_email=email,
        owner_password=temp_password,
        owner_name=purchase.customer_name or "مدیر",
    )
    return tenant, temp_password
