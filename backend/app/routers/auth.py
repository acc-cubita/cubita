from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.rate_limit import (
    limit_login,
    limit_password_reset,
    limit_password_reset_for_email,
    limit_signup,
)
from app.deps import Principal, get_current_user, get_principal
from app.models.auth_token import PURPOSE_PASSWORD_RESET
from app.models.tenant import Membership, Tenant
from app.models.user import Role, User
from app.schemas.auth import (
    BusinessUpdateIn,
    LoginIn,
    MeOut,
    ProfileUpdateIn,
    SignupIn,
    SwitchTenantIn,
    TenantMembershipOut,
    TokenOut,
)
from app.schemas.members import (
    AcceptInviteIn,
    ChangePasswordIn,
    ForgotPasswordIn,
    ResetPasswordIn,
)
from app.security import create_access_token, record_login, set_password, verify_password
from app.services import members
from app.services.mailer import send_password_reset
from app.services.provisioning import signup_new_business
from app.services.tokens import PASSWORD_RESET_HOURS, consume, issue_password_reset
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


def _me_out(principal: Principal) -> MeOut:
    """پاسخِ استانداردِ «من» — یک منبعِ حقیقت برای /me و اندپوینت‌های ویرایشِ پروفایل."""
    return MeOut(
        id=principal.user.id,
        name=principal.user.name,
        email=principal.user.email,
        phone=principal.user.phone,
        role_key=principal.role.key,
        role_name=principal.role.name,
        permissions=principal.role.permissions,
        tenant_id=principal.tenant_id,
        tenant_name=principal.membership.tenant.name,
        is_platform_admin=principal.user.email.strip().lower() in get_settings().platform_admin_emails_list,
        is_super_admin=principal.user.email.strip().lower() in get_settings().super_admin_emails_list,
    )


@router.post("/signup", response_model=TokenOut, status_code=201, dependencies=[Depends(limit_signup)])
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
    return TokenOut(access_token=create_access_token(user, tenant.id))


@router.post("/login", response_model=TokenOut, dependencies=[Depends(limit_login)])
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if user is None or not user.active or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "ایمیل یا رمز عبور نادرست است")

    memberships = _active_memberships(db, user)
    if not memberships:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "عضویت فعالی در هیچ کسب‌وکاری ندارید")

    # توکن همیشه به یک کسب‌وکار مشخص گره می‌خورد. کاربری که چند عضویت دارد با
    # اولی وارد می‌شود و بعد می‌تواند از /switch-tenant جابه‌جا شود.
    record_login(user)
    return TokenOut(access_token=create_access_token(user, memberships[0].tenant_id))


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

    return TokenOut(access_token=create_access_token(principal.user, target.tenant_id))


@router.post("/forgot-password", status_code=202)
def forgot_password(
    data: ForgotPasswordIn,
    _limit=Depends(limit_password_reset),
    db: Session = Depends(get_db),
):
    """لینک بازیابی می‌فرستد — و همیشه ۲۰۲ برمی‌گرداند.

    پاسخ عمداً به وجود یا نبودِ ایمیل حساس نیست. اگر برای ایمیل ناموجود ۴۰۴ بدهیم،
    این اندپوینت به ابزار فهرست‌برداری کاربران تبدیل می‌شود: مهاجم ایمیل‌ها را یکی
    یکی می‌فرستد و می‌فهمد کدام‌ها مشتری کوبیتا هستند. همان دلیل، سقفِ مبتنی بر
    ایمیل هم اینجا به‌جای ۴۲۹ بی‌صدا رد می‌شود.
    """
    email = data.email.strip().lower()
    if limit_password_reset_for_email(email):
        user = db.query(User).filter(User.email == email).first()
        if user is not None and user.active:
            raw = issue_password_reset(db, user.id)
            send_password_reset(to=user.email, name=user.name, token=raw, valid_hours=PASSWORD_RESET_HOURS)

    return {"detail": "اگر این ایمیل در سیستم ثبت شده باشد، لینک بازیابی برایش ارسال شد"}


@router.post("/reset-password", response_model=TokenOut)
def reset_password(data: ResetPasswordIn, db: Session = Depends(get_db)):
    """رمز تازه را ست می‌کند و کاربر را وارد می‌کند.

    ورود خودکار عمدی است: کسی که همین حالا مالکیت صندوق ایمیل را اثبات کرده، لازم
    نیست بلافاصله رمزی را که تازه ساخته دوباره تایپ کند.

    ترتیب اهمیت دارد: توکن **بعد از** `set_password` صادر می‌شود تا نسل تازه را
    داشته باشد. اگر قبلش صادر می‌شد، همان بررسی‌ای که نشست‌های قدیمی را می‌کشد این
    توکنِ تازه را هم می‌کشت و کاربر بلافاصله بعد از بازیابی بیرون می‌ماند.
    """
    token = consume(db, data.token, purpose=PURPOSE_PASSWORD_RESET)
    if token is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این لینک نامعتبر یا منقضی شده است")

    user = db.get(User, token.user_id)
    if user is None or not user.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این لینک نامعتبر یا منقضی شده است")

    set_password(user, data.password)
    db.flush()

    memberships = _active_memberships(db, user)
    if not memberships:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "عضویت فعالی در هیچ کسب‌وکاری ندارید")

    record_login(user)
    return TokenOut(access_token=create_access_token(user, memberships[0].tenant_id))


@router.post("/accept-invite", response_model=TokenOut)
def accept_invite(data: AcceptInviteIn, db: Session = Depends(get_db)):
    """دعوت همکار (یا اولین ورود مشتریِ تازه‌خریده) را می‌پذیرد."""
    user, tenant_id = members.accept_invite(
        db, raw_token=data.token, password=data.password, name=data.name
    )
    return TokenOut(access_token=create_access_token(user, tenant_id))


@router.post("/change-password", response_model=TokenOut)
def change_password(
    data: ChangePasswordIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """تغییر رمز توسط کاربری که وارد شده.

    رمز فعلی دوباره پرسیده می‌شود: بدون آن، هر کسی که لپ‌تاپِ باز یا توکنِ دزدیده‌شده
    داشته باشد می‌تواند رمز را عوض کند و صاحب اصلی را برای همیشه بیرون بگذارد.
    """
    if not verify_password(data.current_password, principal.user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "رمز عبور فعلی نادرست است")

    set_password(principal.user, data.new_password)
    db.flush()

    # همه‌ی نشست‌های دیگر همین حالا باطل شدند؛ توکن تازه جای همین نشست را می‌گیرد.
    return TokenOut(access_token=create_access_token(principal.user, principal.tenant_id))


@router.get("/me", response_model=MeOut)
def me(principal: Principal = Depends(get_principal)):
    return _me_out(principal)


@router.patch("/me", response_model=MeOut)
def update_profile(
    data: ProfileUpdateIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """ویرایشِ پروفایلِ خودِ کاربر — نام و تلفن آزادانه، ایمیل با رمزِ فعلی.

    نام و تلفن حساس نیستند و بی‌درنگ تغییر می‌کنند. ایمیل هویتِ ورود است: تغییرش هم
    رمزِ فعلی می‌خواهد (تا نشستِ ربوده‌شده نتواند حساب را بدزدد) و هم یکتا بودنش سنجیده
    می‌شود. برای پرهیز از فهرست‌برداریِ کاربران، پیامِ «تکراری بودن» عمداً مبهم است.
    """
    user = principal.user

    if data.name is not None:
        user.name = data.name
    if data.phone is not None:
        user.phone = data.phone.strip() or None

    if data.email is not None:
        new_email = data.email.strip().lower()
        if new_email != user.email:
            if not data.current_password or not verify_password(data.current_password, user.hashed_password):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای تغییر ایمیل، رمز فعلی را درست وارد کنید")
            taken = db.query(User).filter(User.email == new_email, User.id != user.id).first()
            if taken is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, "امکان استفاده از این ایمیل نیست")
            user.email = new_email

    db.flush()
    return _me_out(principal)


@router.patch("/business", response_model=MeOut)
def update_business(
    data: BusinessUpdateIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """تغییرِ نامِ کسب‌وکارِ جاری — فقط مالک.

    نقشِ مالک با wildcardِ «*» شناخته می‌شود؛ نقش‌های دیگر (حسابدار، فروشنده و …) اجازه
    ندارند نامِ کسب‌وکار را عوض کنند. فقط مستأجرِ جاری دست می‌خورد، پس جدولِ سراسریِ
    tenants امن می‌ماند.
    """
    if "*" not in principal.role.permissions:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "فقط مالک می‌تواند نام کسب‌وکار را تغییر دهد")
    principal.membership.tenant.name = data.name
    db.flush()
    return _me_out(principal)
