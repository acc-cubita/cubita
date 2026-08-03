"""منطقِ ماژولِ «مدیریت اکانت‌ها» — کنترل‌پنلِ سوپرادمین.

روی جدول‌های **سراسری** (tenants/memberships/users/subscriptions — بدونِ RLS) کار
می‌کند، پس زیرِ زمینه‌ی مستأجرِ خودِ ادمین هم همه‌ی اکانت‌ها را می‌بیند. ساخت/تمدید/
تعلیق/بازنشانیِ رمز/حذف را با همان توابعِ آزموده‌ی provisioning و subscriptions انجام
می‌دهد تا منطق دوباره‌کاری نشود.
"""
from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.models.tenant import Membership, Tenant
from app.models.user import User
from app.security import set_password
from app.services import subscriptions
from app.services.provisioning import purge_tenant, signup_new_business

_FAR_FUTURE = datetime.max.replace(tzinfo=timezone.utc)
_LONG_AGO = datetime.min.replace(tzinfo=timezone.utc)


def _owner_membership(db: Session, tenant_id: UUID) -> Membership | None:
    """مالکِ اکانت = نخستین عضویتِ ساخته‌شده (provisioning اول مالک را می‌سازد)."""
    return (
        db.query(Membership)
        .filter(Membership.tenant_id == tenant_id)
        .order_by(Membership.created_at.asc())
        .first()
    )


def _login_key(dt: datetime | None) -> float:
    """کلیدِ مرتب‌سازیِ نزولیِ آخرین‌ورود؛ «هرگز وارد نشده» ته می‌نشیند."""
    return dt.timestamp() if dt is not None else float("-inf")


def _row(db: Session, tenant: Tenant, members: list[tuple[Membership, User]]) -> dict:
    owner = min(members, key=lambda mu: mu[0].created_at or _LONG_AGO)[1] if members else None
    state = subscriptions.state_for(db, tenant.id)
    sub = subscriptions.current_subscription(db, tenant.id)
    # اطلاعاتِ آزمایشیِ رایگان: حسابِ ۱۴روزه is_trial=True دارد و روزهای مانده‌اش با
    # همان منطقِ ceilِ trial_info حساب می‌شود (نه days_leftِ اشتراک که floor است و
    # روزِ صفر را ۱۳ نشان می‌دهد). expired بدونِ مهلتِ ارفاق است.
    tinfo = subscriptions.trial_info(db, tenant)

    logins = [u.last_login_at for _m, u in members if u.last_login_at is not None]
    last_activity = max(logins) if logins else None

    users = [
        {
            "name": u.name,
            "email": u.email,
            "status": m.status,
            "is_owner": owner is not None and u.id == owner.id,
            "last_login_at": u.last_login_at,
        }
        for m, u in members
    ]
    # مالک اول، سپس تازه‌ترین ورود بالاتر؛ «هرگز» ته فهرست.
    users.sort(key=lambda d: (not d["is_owner"], -_login_key(d["last_login_at"])))

    return {
        "tenant_id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "status": tenant.status,
        "owner_name": owner.name if owner else "",
        "owner_email": owner.email if owner else "",
        "created_at": tenant.created_at,
        "user_count": len(members),
        "max_users": tenant.max_users,
        "subscription_status": state.status,
        "expires_at": state.expires_at,
        "days_left": state.days_left,
        "plan_name": sub.plan.name if sub and sub.plan else "",
        "is_trial": tinfo.is_trial,
        "trial_days_left": tinfo.days_left,
        "trial_expired": tinfo.expired,
        "owner_last_login_at": owner.last_login_at if owner else None,
        "last_activity_at": last_activity,
        "users": users,
    }


def list_accounts(db: Session) -> list[dict]:
    tenants = db.query(Tenant).all()
    pairs = db.query(Membership, User).join(User, User.id == Membership.user_id).all()
    by_tenant: dict[UUID, list[tuple[Membership, User]]] = defaultdict(list)
    for m, u in pairs:
        by_tenant[m.tenant_id].append((m, u))

    rows = [_row(db, t, by_tenant.get(t.id, [])) for t in tenants]
    # نزدیک‌ترین انقضا اول؛ اکانت‌های بی‌اشتراک ته فهرست.
    rows.sort(key=lambda r: (r["expires_at"] is None, r["expires_at"] or _FAR_FUTURE))
    return rows


def account_row(db: Session, tenant_id: UUID) -> dict:
    tenant = _require(db, tenant_id)
    members = (
        db.query(Membership, User).join(User, User.id == Membership.user_id).filter(Membership.tenant_id == tenant_id).all()
    )
    return _row(db, tenant, members)


def _require(db: Session, tenant_id: UUID) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اکانت یافت نشد")
    return tenant


def create_account(db: Session, *, business_name: str, owner_name: str, email: str, password: str, days: int) -> UUID:
    """کسب‌وکار + کاربرِ مالک را می‌سازد و در صورتِ نیاز اشتراکِ اولیه می‌دهد.

    اگر ایمیل از قبل باشد، signup_new_business با 409 رد می‌کند (پیامِ مبهم، عمداً).
    """
    # اکانتِ دستیِ مدیر آزمایشی نیست: اشتراکش را همین‌جا با `days` تعیین می‌کنیم، پس
    # نباید is_trial=True بگیرد (که بنر/قفلِ مؤدیان و کرونِ حذفِ تریال را روشن می‌کند).
    tenant, _user = signup_new_business(
        db, business_name=business_name, owner_name=owner_name, email=email, password=password, trial=False
    )
    if days > 0:
        subscriptions.grant(db, tenant.id, days=days, note="ساختِ دستی توسط مدیرِ سامانه", source="manual")
    return tenant.id


def extend_account(db: Session, tenant_id: UUID, *, days: int | None = None, expires_at=None) -> None:
    """تمدید (افزودنِ روز، از انتهای دوره‌ی فعلی) یا تعیینِ تاریخِ انقضای مشخص."""
    tenant = _require(db, tenant_id)
    # تمدیدِ دستیِ مدیر یعنی این اکانت دیگر آزمایشیِ خودسرویس نیست: پرچمِ trial را پاک
    # می‌کنیم تا (۱) در فهرستِ مدیریت به‌غلط «آزمایشی» دیده نشود، (۲) مؤدیان/اتصال‌فروشگاه
    # قفل نماند، و (۳) کرونِ حذفِ تریال سراغش نرود. قرینه‌ی provision_for_purchase که با
    # خریدِ واقعی همین is_trial=False را ست می‌کند.
    tenant.is_trial = False
    if days:
        subscriptions.grant(db, tenant_id, days=days, note="تمدیدِ دستی توسط مدیرِ سامانه", source="manual")
        return
    # تنظیمِ تاریخِ انقضا: یک دوره‌ی تازه که در آن تاریخ تمام می‌شود (باید در آینده باشد).
    target = datetime(expires_at.year, expires_at.month, expires_at.day, tzinfo=timezone.utc)
    if target <= datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تاریخ انقضا باید در آینده باشد")
    db.add(
        Subscription(
            tenant_id=tenant_id,
            starts_at=datetime.now(timezone.utc),
            expires_at=target,
            note="تنظیمِ دستیِ انقضا توسط مدیرِ سامانه",
            source="manual",
        )
    )
    db.flush()


def set_status(db: Session, tenant_id: UUID, *, new_status: str, acting_tenant_id: UUID) -> None:
    """تعلیق/فعال‌سازیِ کسب‌وکار. مدیر نمی‌تواند اکانتِ خودش را تعلیق کند (قفلِ بیرون)."""
    if tenant_id == acting_tenant_id and new_status != "active":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نمی‌توانید اکانتِ خودتان را تعلیق کنید")
    tenant = _require(db, tenant_id)
    tenant.status = new_status
    db.flush()


def reset_owner_password(db: Session, tenant_id: UUID, *, password: str) -> None:
    """رمزِ مالکِ اکانت را تعیینِ تازه می‌کند (نسلِ توکن جلو می‌رود → نشست‌های باز باطل)."""
    membership = _owner_membership(db, tenant_id)
    owner = db.get(User, membership.user_id) if membership else None
    if owner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مالکِ اکانت یافت نشد")
    set_password(owner, password)
    db.flush()


def delete_account(db: Session, tenant_id: UUID, *, acting_tenant_id: UUID) -> None:
    """پاک‌سازیِ کاملِ اکانت. مدیر نمی‌تواند اکانتِ خودش را حذف کند."""
    if tenant_id == acting_tenant_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نمی‌توانید اکانتِ خودتان را حذف کنید")
    _require(db, tenant_id)
    purge_tenant(db, tenant_id)
