"""مدیریت کاربران یک کسب‌وکار: فهرست، دعوت، تغییر نقش، غیرفعال‌سازی.

تا امروز هیچ راهی برای افزودن کاربر دوم وجود نداشت. یعنی پلن «حرفه‌ای» با
`max_users: 5` فروخته می‌شد در حالی که کسب‌وکار برای همیشه تک‌کاربره می‌ماند.

**دو خطر ساختاری اینجا وجود دارد که RLS نمی‌گیردشان:**

۱. `memberships` و `users` جدول‌های سراسری‌اند و سیاست ایزوله‌سازی ندارند. هر کوئری
   در این ماژول باید *صراحتاً* روی tenant_id فیلتر کند. یک فیلتر فراموش‌شده اینجا
   یعنی فهرست کاربران همه‌ی مشتری‌ها — همان شکل نشتی که قبلاً در پنل صورتحساب رخ
   داد. `test_members.py` این را با تست جداگانه می‌سنجد.

۲. قفل شدن بیرون. اگر آخرین مالکِ فعال بتواند خودش را حذف یا تنزل دهد، کسب‌وکار
   بدون هیچ کسی می‌ماند که بتواند کاربر مدیریت کند و فقط با دسترسی مستقیم به
   دیتابیس قابل نجات است. گاردش پایین‌تر است.
"""
import secrets
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.tenant import Membership, Tenant
from app.models.user import Role, User
from app.security import hash_password, record_login, set_password
from app.services import tokens
from app.services.permissions import sanitize as sanitize_permissions

#: ماژول مجوز. هیچ نقش پیش‌فرضی جز «مالک» آن را ندارد، چون فقط مالک wildcard دارد —
#: یعنی مدیریت کاربر به‌طور پیش‌فرض فقط دست مالک است، بدون نیاز به تغییر seed.
PERMISSION_MODULE = "users"

OWNER_ROLE_KEY = "owner"

#: عضویت‌هایی که یک «صندلی» از سقف پلن را اشغال می‌کنند. کاربر غیرفعال‌شده حساب
#: نمی‌شود: هدف سقف، کاربران هم‌زمانِ واقعی است، و نگه داشتن ردیف غیرفعال برای
#: تاریخچه نباید مشتری را مجبور کند صندلی بخرد.
SEAT_STATUSES = ("active", "invited")

#: نقشی که صندلی مصرف نمی‌کند: حسابرسِ کوبیتا مهمانِ موقتِ ماست، نه کاربرِ مشتری.
#: بدونِ این، تأییدِ حسابرسی می‌توانست مشتریِ کنارِ سقف را وادار به خریدِ صندلی کند.
SEATLESS_ROLE_KEYS = ("auditor",)


def _tenant_memberships(db: Session, tenant_id: UUID):
    """پایه‌ی هر کوئری این ماژول — فیلتر مستأجر اینجا یک بار و صریح انجام می‌شود."""
    return db.query(Membership).filter(Membership.tenant_id == tenant_id)


def list_members(db: Session, tenant_id: UUID) -> list[Membership]:
    return _tenant_memberships(db, tenant_id).join(User, User.id == Membership.user_id).order_by(User.name).all()


def seats_used(db: Session, tenant_id: UUID) -> int:
    return (
        _tenant_memberships(db, tenant_id)
        .join(Role, Role.id == Membership.role_id)
        .filter(Membership.status.in_(SEAT_STATUSES), Role.key.notin_(SEATLESS_ROLE_KEYS))
        .count()
    )


def _role_by_key(db: Session, tenant_id: UUID, key: str) -> Role:
    """نقش را در همین مستأجر پیدا می‌کند.

    فیلتر tenant_id اینجا اضافه‌کاری نیست: نقش‌ها زیر RLS هستند و در حالت عادی فقط
    نقش مستأجر جاری دیده می‌شود، ولی این تابع از مسیرهایی هم صدا زده می‌شود که
    ممکن است زمینه‌ی متفاوتی داشته باشند و اتکا به لایه‌ی دیگر برای درستی، همان
    الگویی است که قبلاً به نشتی رسید.
    """
    role = db.query(Role).filter(Role.tenant_id == tenant_id, Role.key == key).first()
    if role is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"نقش «{key}» در این کسب‌وکار تعریف نشده است")
    return role


def _active_owner_count(db: Session, tenant_id: UUID, *, excluding: UUID | None = None) -> int:
    query = (
        _tenant_memberships(db, tenant_id)
        .join(Role, Role.id == Membership.role_id)
        .filter(Membership.status == "active", Role.key == OWNER_ROLE_KEY)
    )
    if excluding is not None:
        query = query.filter(Membership.id != excluding)
    return query.count()


def _guard_last_owner(db: Session, tenant_id: UUID, membership: Membership) -> None:
    """جلوی خالی ماندن کسب‌وکار از مالکِ فعال را می‌گیرد.

    بدون این، آخرین مالک می‌توانست خودش را تنزل دهد یا غیرفعال کند و بعد هیچ‌کس
    اجازه‌ی مدیریت کاربر نداشت — وضعیتی که فقط با دسترسی مستقیم به دیتابیس قابل
    برگشت است. این تنها گاردی است که کاربر را از خودش محافظت می‌کند.
    """
    if membership.role.key != OWNER_ROLE_KEY or membership.status != "active":
        return
    if _active_owner_count(db, tenant_id, excluding=membership.id) == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این تنها مالکِ فعال کسب‌وکار است؛ اول یک مالک دیگر تعیین کنید",
        )


def _get_member(db: Session, tenant_id: UUID, membership_id: UUID) -> Membership:
    membership = _tenant_memberships(db, tenant_id).filter(Membership.id == membership_id).first()
    if membership is None:
        # ۴۰۴ و نه ۴۰۳: تفکیک «وجود ندارد» از «اجازه ندارید» به مهاجم می‌گوید کدام
        # شناسه‌ها در کسب‌وکارهای دیگر واقعی‌اند.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کاربر یافت نشد")
    return membership


def list_roles(db: Session, tenant_id: UUID) -> list[tuple[Role, int]]:
    """نقش‌های این کسب‌وکار به‌همراه شمارِ اعضای هر کدام.

    نقش‌ها مستأجرمحورند (هر کسب‌وکار نسخه‌ی خودش را از DEFAULT_ROLES می‌گیرد)، پس
    رابط کاربری نباید فهرست را حدس بزند.
    """
    roles = db.query(Role).filter(Role.tenant_id == tenant_id).order_by(Role.key).all()
    counts: dict[UUID, int] = {}
    for m in _tenant_memberships(db, tenant_id).filter(Membership.status.in_(SEAT_STATUSES)).all():
        counts[m.role_id] = counts.get(m.role_id, 0) + 1
    return [(r, counts.get(r.id, 0)) for r in roles]


def effective_permissions(membership: Membership) -> dict:
    """مجوزِ مؤثرِ یک عضویت — همان چیزی که deps هنگامِ بررسیِ دسترسی می‌بیند."""
    return membership.permissions or (membership.role.permissions or {})


def set_permissions(
    db: Session, *, tenant_id: UUID, membership_id: UUID, permissions: dict | None, actor: User
) -> Membership:
    """دسترسیِ اختصاصیِ یک عضو را می‌نشاند یا برمی‌گرداند به مجوزِ نقش.

    دو گارد، هر دو در برابرِ قفل‌شدنِ بیرونی:

    ۱. **روی خودت نه.** کاربر نمی‌تواند دسترسیِ خودش را عوض کند. بدونِ این، یک
       اشتباهِ ساده (برداشتنِ تیکِ «مدیریت کاربران») همان لحظه اجرا می‌شود و دیگر
       راهی برای برگرداندنش از داخلِ برنامه نمی‌ماند. جلوگیری از خودارتقایی هم
       رایگان از همین قاعده می‌آید.
    ۲. **آخرین مالکِ فعال.** حتی توسطِ شخصِ دیگر هم نباید محدود شود، وگرنه کسب‌وکار
       بدونِ هیچ مدیری می‌ماند — همان چیزی که `_guard_last_owner` می‌پاید.
    """
    membership = _get_member(db, tenant_id, membership_id)
    clean = sanitize_permissions(permissions)

    if membership.user_id == actor.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "دسترسیِ خودتان را نمی‌توانید تغییر دهید؛ این کار باید توسط مدیرِ دیگری انجام شود",
        )

    if (
        clean is not None
        and membership.role.key == OWNER_ROLE_KEY
        and membership.status == "active"
        and _active_owner_count(db, tenant_id, excluding=membership.id) == 0
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این تنها مالکِ فعالِ کسب‌وکار است؛ محدودکردنِ دسترسی او کسب‌وکار را بدون مدیر می‌گذارد",
        )

    _guard_auditor(db, membership)

    membership.permissions = clean
    db.flush()
    return membership


def resend_invite(db: Session, *, tenant_id: UUID, membership_id: UUID) -> tuple[Membership, str]:
    """توکنِ دعوتِ تازه برای عضوی که هنوز دعوت را نپذیرفته.

    بدونِ این، کاربری که ایمیلِ دعوت را گم کرده بود گیر می‌کرد: `invite_member` روی
    عضوِ موجود ۴۰۹ می‌دهد و هیچ راهِ دیگری برای صدورِ لینکِ تازه نبود.
    """
    membership = _get_member(db, tenant_id, membership_id)
    if membership.status != "invited":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "این کاربر دعوت را پذیرفته است؛ ارسال دوباره‌ی دعوت معنا ندارد",
        )
    return membership, tokens.issue_invite(db, membership.user_id, tenant_id)


def invite_member(
    db: Session,
    *,
    tenant_id: UUID,
    inviter: User,
    email: str,
    name: str,
    role_key: str,
    permissions: dict | None = None,
) -> tuple[Membership, str]:
    """کاربر را به این کسب‌وکار دعوت می‌کند و توکن پذیرش را برمی‌گرداند.

    اگر ایمیل از قبل کاربر داشته باشد، کاربر تازه ساخته نمی‌شود و فقط عضویت اضافه
    می‌شود — همان حالتِ حسابدار مستقلی که دفتر چند کسب‌وکار را می‌برد. نام و رمز
    کاربرِ موجود **دست نمی‌خورد**: دعوت کردن کسی نباید به دعوت‌کننده اجازه دهد
    مشخصات حساب او را در کسب‌وکارهای دیگر عوض کند.
    """
    email = email.strip().lower()
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کسب‌وکار یافت نشد")

    if tenant.max_users is not None and seats_used(db, tenant_id) >= tenant.max_users:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"سقف کاربران این پلن ({tenant.max_users} کاربر) تکمیل است. "
            "برای افزودن کاربر بیشتر پلن را ارتقا دهید یا کاربری را غیرفعال کنید.",
        )

    role = _role_by_key(db, tenant_id, role_key)

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        # رمز تصادفیِ دورانداختنی: حساب تا وقتی دعوت پذیرفته نشود رمز قابل استفاده
        # ندارد، ولی ستون رمز nullable نیست و گذاشتن رشته‌ی خالی یعنی hash خالی.
        user = User(name=name.strip(), email=email, hashed_password=hash_password(secrets.token_urlsafe(32)))
        db.add(user)
        db.flush()

    existing = _tenant_memberships(db, tenant_id).filter(Membership.user_id == user.id).first()
    if existing is not None and existing.status in SEAT_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "این کاربر از قبل عضو این کسب‌وکار است")

    if existing is not None:
        # عضو غیرفعالِ قبلی دوباره دعوت می‌شود، نه اینکه ردیف دوم بسازیم — قید یکتای
        # (user_id, tenant_id) هم اجازه‌ی ردیف دوم را نمی‌دهد.
        existing.role_id = role.id
        existing.status = "invited"
        membership = existing
    else:
        membership = Membership(user_id=user.id, tenant_id=tenant_id, role_id=role.id, status="invited")
        db.add(membership)
    # دسترسیِ اختصاصی همان لحظه‌ی دعوت تعیین می‌شود، نه در یک مرحله‌ی بعدیِ فراموش‌شدنی.
    membership.permissions = sanitize_permissions(permissions)
    db.flush()

    return membership, tokens.issue_invite(db, user.id, tenant_id)


def accept_invite(db: Session, *, raw_token: str, password: str, name: str | None = None) -> tuple[User, UUID]:
    """دعوت را می‌پذیرد: رمز را ست می‌کند و عضویت را فعال می‌کند.

    بدون احراز هویت اجرا می‌شود — خودِ توکن مدرک است. هیچ زمینه‌ی مستأجری هم لازم
    نیست چون فقط جدول‌های سراسری (users، memberships، auth_tokens) لمس می‌شوند.
    """
    from app.models.auth_token import PURPOSE_INVITE

    token = tokens.consume(db, raw_token, purpose=PURPOSE_INVITE)
    if token is None or token.tenant_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این لینک نامعتبر یا منقضی شده است")

    user = db.get(User, token.user_id)
    membership = (
        _tenant_memberships(db, token.tenant_id).filter(Membership.user_id == token.user_id).first()
        if user is not None
        else None
    )
    if user is None or membership is None:
        # دعوت بین صدور و پذیرش لغو شده. پیام عمداً همان پیام لینک نامعتبر است.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این لینک نامعتبر یا منقضی شده است")

    set_password(user, password)
    user.active = True
    if name and name.strip():
        user.name = name.strip()
    membership.status = "active"
    record_login(user)  # پذیرشِ دعوت هم یک ورودِ موفق است
    db.flush()

    return user, token.tenant_id


def _guard_auditor(db: Session, membership: Membership) -> None:
    """دسترسیِ حسابرسِ گماشته را مالکِ مشتری تنظیم نمی‌کند.

    دامنه‌ی این عضویت با قراردادِ حسابرسی تعیین شده و پشتیبانیِ کوبیتا مسئولش
    است؛ پهن‌کردنش یعنی مهمانِ موقت دسترسی‌ای بگیرد که قرارداد نمی‌گوید.

    **غیرفعال‌کردن عمداً آزاد می‌ماند.** دفتر مالِ مشتری است و باید بتواند هر
    کسی را — از جمله ما — بیرون بگذارد.
    """
    from app.models.assurance import AssuranceEngagement

    linked = (
        db.query(AssuranceEngagement.id)
        .filter(AssuranceEngagement.auditor_membership_id == membership.id)
        .first()
    )
    if linked is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "دسترسیِ حسابرس را پشتیبانیِ کوبیتا تنظیم می‌کند؛ برای قطعِ دسترسی می‌توانید کاربر را غیرفعال کنید",
        )


def change_role(db: Session, *, tenant_id: UUID, membership_id: UUID, role_key: str) -> Membership:
    membership = _get_member(db, tenant_id, membership_id)
    role = _role_by_key(db, tenant_id, role_key)

    if role.id != membership.role_id:
        _guard_last_owner(db, tenant_id, membership)
        _guard_auditor(db, membership)

    membership.role_id = role.id
    db.flush()
    return membership


def set_member_status(db: Session, *, tenant_id: UUID, membership_id: UUID, active: bool, actor: User) -> Membership:
    membership = _get_member(db, tenant_id, membership_id)

    if not active:
        if membership.user_id == actor.id:
            # قفل شدنِ فوریِ خودی. برخلاف گارد آخرین مالک، این حتی وقتی مالک دیگری
            # هم هست اشتباه است: کاربر بلافاصله بیرون می‌افتد و معمولاً منظورش
            # غیرفعال کردن کس دیگری بوده.
            raise HTTPException(status.HTTP_409_CONFLICT, "نمی‌توانید دسترسی خودتان را قطع کنید")
        _guard_last_owner(db, tenant_id, membership)

    membership.status = "active" if active else "disabled"
    db.flush()
    return membership
