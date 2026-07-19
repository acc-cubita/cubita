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
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.audit import PURGE_SETTING
from app.config import get_settings
from app.models.tenant import Membership, Tenant
from app.models.user import User
from app.seed import provision_tenant
from app.services import tokens

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
        # ثبت‌نام مستقیم هنوز پلنی نخریده، پس سقف آزمایشی می‌گیرد. بدون هیچ سقفی،
        # دعوت یک منبع نامحدود است و هر ثبت‌نام رایگان می‌تواند بی‌نهایت کاربر بسازد.
        max_users=get_settings().signup_default_max_users,
    )
    user = db.query(User).filter(User.email == email).one()
    return tenant, user


def provision_for_purchase(db: Session, purchase) -> tuple[Tenant, str] | None:
    """بعد از پرداخت تأییدشده، کسب‌وکار مشتری را می‌سازد.

    idempotent است چون callback زرین‌پال می‌تواند دوباره بیاید و کاربر هم ممکن
    است صفحه را رفرش کند. اگر این کاربر از قبل مستأجری دارد، کسب‌وکار تازه‌ای ساخته
    نمی‌شود و فقط سقف کاربرانش با پلن تازه به‌روز می‌شود (یعنی ارتقا).

    **توکن راه‌اندازی برمی‌گرداند، نه رمز موقت.** قبلاً رمز موقت ساخته می‌شد و در
    ایمیلِ اعلانِ *مدیر* می‌رفت تا او دستی به مشتری بدهد؛ یعنی مشتری بعد از پرداخت
    منتظر یک انسان می‌ماند و رمزش از یک صندوق ایمیل واسط عبور می‌کرد. حالا لینک
    مستقیماً به خودِ مشتری می‌رود و رمز را خودش انتخاب می‌کند، پس هیچ رمزی هیچ‌جا
    نوشته نمی‌شود.

    رشته‌ی خالی یعنی مشتریِ موجود بود و لینک راه‌اندازی لازم نیست.
    """
    email = (purchase.customer_email or "").strip().lower()
    if not email:
        return None

    plan_max_users = purchase.plan.max_users if purchase.plan else None

    user = db.query(User).filter(User.email == email).first()
    if user is not None:
        membership = db.query(Membership).filter(Membership.user_id == user.id).first()
        if membership is not None:
            # از قبل مشتری است — خرید جدید یعنی تمدید/ارتقا، نه کسب‌وکار جدید.
            tenant = db.get(Tenant, membership.tenant_id)
            if tenant is not None and _is_upgrade(tenant.max_users, plan_max_users):
                tenant.max_users = plan_max_users
                db.flush()
            return tenant, ""

    tenant = provision_tenant(
        db,
        name=purchase.business_name or purchase.customer_name or "کسب‌وکار جدید",
        slug=unique_slug(db, purchase.business_name or purchase.customer_name or "business"),
        owner_email=email,
        # رمز تصادفیِ دورانداختنی: حساب تا وقتی مشتری لینک راه‌اندازی را باز نکند
        # رمز قابل استفاده ندارد، و این رمز هرگز جایی نمایش داده یا ایمیل نمی‌شود.
        owner_password=uuid4().hex,
        owner_name=purchase.customer_name or "مدیر",
        max_users=plan_max_users,
    )
    owner = db.query(User).filter(User.email == email).one()
    return tenant, tokens.issue_invite(db, owner.id, tenant.id)


def purge_tenant(db: Session, tenant_id) -> None:
    """حذف کامل یک کسب‌وکار — قرینه‌ی provision_tenant.

    **چرا این تابع وجود دارد و کسی مستقیم DELETE نمی‌زند:** دفتر حسابرسی در سطح
    پایگاه‌داده فقط‌افزودنی است، پس حذف مستأجر به قید FK می‌خورد و شکست می‌خورد.
    دریچه‌ی `app.audit_purge` تنها راه عبور است، و عمداً اینجا و فقط اینجا باز
    می‌شود: اگر هر مسیری می‌توانست بازش کند، همان مسیر برای پاک کردن ردِ یک ابطال
    هم کار می‌کرد و کل خاصیت فقط‌افزودنی بودن تزئینی می‌شد.

    دریچه با `set_config(..., true)` به همین تراکنش محدود است، پس با پایان تراکنش
    خودش بسته می‌شود — نه با به‌یاد آوردنِ کسی.
    """
    db.execute(text("SELECT set_config(:k, 'on', true)"), {"k": PURGE_SETTING})
    db.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tenant_id})


def _is_upgrade(current: int | None, new: int | None) -> bool:
    """آیا پلن تازه سقف را بالا می‌برد؟

    None یعنی نامحدود، پس در مقایسه بزرگ‌ترین مقدار است — نه کوچک‌ترین. بدون این
    تفکیک، خریدِ پلن سازمانی (نامحدود) روی پلن حرفه‌ای (۵ کاربر) به‌عنوان «تنزل»
    خوانده می‌شد و سقف پایین می‌ماند.

    تنزل عمداً اعمال نمی‌شود: پایین آوردن سقف روی کسب‌وکاری که همین حالا کاربران
    فعال دارد باید تصمیم آگاهانه باشد، نه اثر جانبیِ یک callback پرداخت.
    """
    if current is None:
        return False  # از نامحدود بالاتر نمی‌رود
    if new is None:
        return True  # به نامحدود می‌رسد
    return new > current
