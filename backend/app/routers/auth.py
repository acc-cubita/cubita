from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_current_user, get_principal
from app.models.tenant import Membership, Tenant
from app.models.user import Role, User
from app.schemas.auth import (
    LoginIn,
    MeOut,
    SignupIn,
    SwitchTenantIn,
    TenantMembershipOut,
    TokenOut,
)
from app.security import create_access_token, verify_password
from app.services.provisioning import signup_new_business
from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant, tenant_scope

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _active_memberships(db: Session, user: User) -> list[Membership]:
    return (
        db.query(Membership)
        .filter(Membership.user_id == user.id, Membership.status == "active")
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .filter(Tenant.status == "active")
        .all()
    )


@router.post("/signup", response_model=TokenOut, status_code=201)
def signup(data: SignupIn, db: Session = Depends(get_db)):
    """ثبت‌نام self-serve — کاربر و کسب‌وکارش با هم ساخته می‌شوند.

    تا امروز مسیر ساخت مشتری جدید فقط `python -m app.seed` روی سرور بود، یعنی
    تحویل دستی. این اندپوینت همان کار را در یک تراکنش انجام می‌دهد.
    """
    tenant, user = signup_new_business(
        db,
        business_name=data.business_name,
        owner_name=data.owner_name,
        email=data.email,
        password=data.password,
    )
    return TokenOut(access_token=create_access_token(user.id, tenant.id))


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if user is None or not user.active or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "ایمیل یا رمز عبور نادرست است")

    memberships = _active_memberships(db, user)
    if not memberships:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "عضویت فعالی در هیچ کسب‌وکاری ندارید")

    # توکن همیشه به یک کسب‌وکار مشخص گره می‌خورد. کاربری که چند عضویت دارد با
    # اولی وارد می‌شود و بعد می‌تواند از /switch-tenant جابه‌جا شود.
    return TokenOut(access_token=create_access_token(user.id, memberships[0].tenant_id))


@router.get("/tenants", response_model=list[TenantMembershipOut])
def my_tenants(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    """کسب‌وکارهایی که این کاربر به آن‌ها دسترسی دارد.

    برای حسابدار مستقلی که دفتر چند کسب‌وکار را می‌برد لازم است — سهم بزرگی از
    بازار همین‌هاست.

    نکته‌ی پیاده‌سازی: `roles` مستأجرمحور است، پس نقشِ کسب‌وکارهای دیگر زیر زمینه‌ی
    فعلی نامرئی است و m.role برابر None درمی‌آید. به‌جای سراسری کردن roles (که یک
    استثنا در ایزوله‌سازی می‌شد و استثناها همان‌جایی‌اند که نشتی پنهان می‌شود)،
    زمینه برای هر عضویت موقتاً عوض می‌شود و در پایان به مستأجر جاری برمی‌گردد.
    این یک خواندنِ باریکِ صفحه‌ی کنترل است، نه دسترسی به دفتر.
    """
    memberships = _active_memberships(db, principal.user)
    rows: list[TenantMembershipOut] = []

    for m in memberships:
        with tenant_scope(db, m.tenant_id):
            role = db.get(Role, m.role_id)
            rows.append(
                TenantMembershipOut(
                    tenant_id=m.tenant_id,
                    tenant_name=m.tenant.name,
                    tenant_slug=m.tenant.slug,
                    role_key=role.key if role else "",
                    role_name=role.name if role else "",
                    is_current=(m.tenant_id == principal.tenant_id),
                )
            )

    # زمینه باید به مستأجر جاری برگردد، وگرنه ادامه‌ی همین درخواست دفتر اشتباهی را می‌بیند
    apply_tenant_to_transaction(db, principal.tenant_id)
    bind_session_tenant(db, principal.tenant_id)
    return rows


@router.post("/switch-tenant", response_model=TokenOut)
def switch_tenant(
    data: SwitchTenantIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """توکن تازه برای کسب‌وکار دیگر صادر می‌کند.

    عضویت اینجا دوباره سنجیده می‌شود و نه فقط در get_principal: اگر این بررسی
    نبود، هر کاربری می‌توانست شناسه‌ی هر مستأجری را بفرستد و توکنی برای دفتر
    کسب‌وکاری بگیرد که هیچ ربطی به او ندارد.
    """
    target = (
        db.query(Membership)
        .filter(
            Membership.user_id == principal.user.id,
            Membership.tenant_id == data.tenant_id,
            Membership.status == "active",
        )
        .first()
    )
    if target is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "عضویت فعالی در این کسب‌وکار ندارید")

    return TokenOut(access_token=create_access_token(principal.user.id, target.tenant_id))


@router.get("/me", response_model=MeOut)
def me(principal: Principal = Depends(get_principal)):
    return MeOut(
        id=principal.user.id,
        name=principal.user.name,
        email=principal.user.email,
        role_key=principal.role.key,
        role_name=principal.role.name,
        permissions=principal.role.permissions,
        tenant_id=principal.tenant_id,
        tenant_name=principal.membership.tenant.name,
    )
