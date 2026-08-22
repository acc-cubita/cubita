from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.rate_limit import (
    limit_email_code,
    limit_email_code_for_email,
    limit_login,
    limit_password_reset,
    limit_password_reset_for_email,
    limit_password_reset_for_phone,
    limit_signup,
    limit_sms_code,
    limit_sms_reset_verify,
)
from app.deps import PREMIUM_FEATURES, Principal, get_current_user, get_principal
from app.models.auth_token import (
    PURPOSE_PASSWORD_RESET,
    PURPOSE_PHONE_VERIFY,
    PURPOSE_SMS_PASSWORD_RESET,
)
from app.models.tenant import Membership, Tenant
from app.models.user import Role, User
from app.schemas.auth import (
    BusinessUpdateIn,
    LoginIn,
    LogoutIn,
    MeOut,
    PhoneSendCodeIn,
    PhoneVerifyIn,
    ProfileUpdateIn,
    RefreshIn,
    SignupIn,
    SignupRequestCodeIn,
    SwitchTenantIn,
    TenantMembershipOut,
    TokenOut,
)
from app.schemas.members import (
    AcceptInviteIn,
    ChangePasswordIn,
    ForgotPasswordIn,
    ForgotPasswordSmsIn,
    ResetPasswordIn,
    ResetPasswordSmsIn,
)
from app.security import create_access_token, record_login, set_password, verify_password
from app.services import members, sms
from app.services import modules as modules_service
from app.services import refresh as refresh_svc
from app.services.email_verification import CODE_TTL_MINUTES as EMAIL_CODE_TTL_MINUTES
from app.services.email_verification import consume_email_code, issue_email_code
from app.services.mailer import send_email_verification_code, send_password_reset
from app.services.provisioning import signup_new_business
from app.services.subscriptions import trial_info
from app.services.tokens import (
    CODE_TTL_MINUTES,
    PASSWORD_RESET_HOURS,
    consume,
    consume_code,
    issue_code,
    issue_password_reset,
)
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


def _me_out(principal: Principal, db: Session) -> MeOut:
    """پاسخِ استانداردِ «من» — یک منبعِ حقیقت برای /me و اندپوینت‌های ویرایشِ پروفایل."""
    tinfo = trial_info(db, principal.membership.tenant)
    return MeOut(
        id=principal.user.id,
        name=principal.user.name,
        email=principal.user.email,
        phone=principal.user.phone,
        phone_verified=principal.user.phone_verified_at is not None,
        email_verified=principal.user.email_verified_at is not None,
        role_key=principal.role.key,
        role_name=principal.role.name,
        permissions=principal.role.permissions,
        tenant_id=principal.tenant_id,
        tenant_name=principal.membership.tenant.name,
        is_platform_admin=principal.user.email.strip().lower() in get_settings().platform_admin_emails_list,
        is_super_admin=principal.user.email.strip().lower() in get_settings().super_admin_emails_list,
        tenant_kind=principal.membership.tenant.kind,
        is_trial=tinfo.is_trial,
        trial_days_left=tinfo.days_left,
        trial_expired=tinfo.expired,
        locked_features=list(PREMIUM_FEATURES) if tinfo.is_trial else [],
        industry=principal.membership.tenant.industry,
        enabled_modules=modules_service.enabled_modules(principal.membership.tenant),
        allowed_modules=sorted(modules_service.allowed_modules(principal.membership.tenant)),
    )


def _mask_email(email: str) -> str:
    """a***@example.com — پاسخ بگوید کد کجا رفت بی‌آنکه کلِ نشانی را در لاگ/پاسخ تکرار کند."""
    local, _, domain = email.partition("@")
    if not domain:
        return email
    shown = local[0] if local else ""
    return f"{shown}{'*' * max(len(local) - 1, 1)}@{domain}"


@router.post("/signup/request-code", dependencies=[Depends(limit_email_code)])
def request_signup_code(data: SignupRequestCodeIn, db: Session = Depends(get_db)):
    """گامِ اولِ ثبت‌نام: کدِ تأیید را به ایمیل می‌فرستد — هنوز حسابی ساخته نمی‌شود.

    اگر ایمیل قبلاً ثبت شده، همان ۴۰۹ِ مبهمِ signup را می‌دهد (نه پیامِ صریح‌تر) تا
    درِ استخراجِ فهرستِ کاربران بازتر از امروز نشود. سقفِ جداگانه بر اساسِ خودِ ایمیل هم
    جلوی بمبارانِ صندوقِ یک نفر را می‌گیرد.

    پاسخ `sent=false` یعنی ایمیل تحویلِ SMTP نشد؛ فرانت باید صادقانه بگوید کد نرفت.
    """
    email = data.email.strip().lower()

    if db.query(User).filter(User.email == email).first() is not None:
        # عمداً مبهم و همسان با پیامِ signup — تأییدِ وجودِ ایمیل، فهرستِ کاربران را لو می‌دهد.
        raise HTTPException(status.HTTP_409_CONFLICT, "امکان ثبت‌نام با این ایمیل نیست")

    # سقفِ per-email بی‌صدا: اگر خورده باشد وانمود می‌کنیم فرستادیم (پاسخ یکنواخت) ولی
    # ایمیلِ تازه‌ای نمی‌رود — تا نه بمباران ممکن باشد، نه از تفاوتِ پاسخ چیزی فهمیده شود.
    if not limit_email_code_for_email(email):
        return {"sent": True, "email": _mask_email(email), "expires_in": EMAIL_CODE_TTL_MINUTES * 60}

    code = issue_email_code(db, email)
    sent = send_email_verification_code(email, "", code, EMAIL_CODE_TTL_MINUTES)
    return {"sent": sent, "email": _mask_email(email), "expires_in": EMAIL_CODE_TTL_MINUTES * 60}


@router.post("/signup", response_model=TokenOut, status_code=201, dependencies=[Depends(limit_signup)])
def signup(data: SignupIn, db: Session = Depends(get_db)):
    """گامِ دومِ ثبت‌نام self-serve — با کدِ تأییدِ ایمیل، کاربر و کسب‌وکارش ساخته می‌شوند.

    کد **قبل از** ساختِ حساب سنجیده می‌شود، پس هیچ حسابی با ایمیلِ تأییدنشده به‌وجود
    نمی‌آید. consume_email_code خودش انقضا و سقفِ تلاش را اعمال و کدِ درست را یک‌بارمصرف می‌کند.
    """
    if not consume_email_code(db, data.email, data.code):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "کد تأیید نادرست یا منقضی است؛ دوباره کد بگیرید.",
        )

    tenant, user = signup_new_business(
        db,
        business_name=data.business_name,
        owner_name=data.owner_name,
        email=data.email,
        password=data.password,
    )
    # ایمیل همین حالا با کد تأیید شد؛ ثبتش می‌کنیم تا نشانِ «تأییدشده» درست باشد.
    user.email_verified_at = datetime.now(timezone.utc)
    db.flush()
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
    tenant_id = memberships[0].tenant_id
    # رفرش فقط برای «همیشه‌واردمانده»ی اپ موبایل است؛ وب/دسکتاپ آن را نادیده می‌گیرند.
    refresh = refresh_svc.issue_refresh(db, user=user, tenant_id=tenant_id)
    return TokenOut(access_token=create_access_token(user, tenant_id), refresh_token=refresh)


@router.post("/refresh", response_model=TokenOut)
def refresh(data: RefreshIn, db: Session = Depends(get_db)):
    """رفرشِ معتبر را با یک accessِ تازه + رفرشِ چرخشیِ تازه تعویض می‌کند.

    عمداً بدونِ get_principal: کلاینت اینجا accessِ منقضی دارد و فقط رفرش را می‌فرستد.
    اعتبارسنجی (وجود، ابطال، انقضا، نسلِ رمز، عضویتِ فعال) در سرویسِ refresh است؛
    هر شکستی یک ۴۰۱ِ یکسان می‌گیرد تا تفاوتِ پیام چیزی لو ندهد.
    """
    result = refresh_svc.rotate(db, data.refresh_token)
    if result is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "نشست نامعتبر است؛ دوباره وارد شوید")
    user, tenant_id, new_refresh = result
    return TokenOut(access_token=create_access_token(user, tenant_id), refresh_token=new_refresh)


@router.post("/logout", status_code=204)
def logout(data: LogoutIn, db: Session = Depends(get_db)):
    """خروجِ اپ موبایل: رفرش را باطل می‌کند. بی‌صدا و همیشه ۲۰۴ (رفرشِ ناموجود هم «باطل»)."""
    refresh_svc.revoke(db, data.refresh_token)


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


def _verified_user_by_phone(db: Session, phone: str) -> User | None:
    """کاربرِ فعالِ دارای این شماره — فقط اگر شماره «تأییدشده» و **یکتا** باشد.

    دو شرط عمدی: (۱) شماره باید قبلاً با OTP تأیید شده باشد، وگرنه هرکس با دانستنِ
    شماره‌ی قربانی می‌تواند برایش کدِ بازیابی بفرستد یا رمزش را عوض کند — شماره‌ی
    تأییدنشده اثباتِ مالکیت نیست. (۲) اگر بیش از یک حساب به این شماره خورد، نمی‌دانیم
    کد را برای کدام صادر کنیم، پس هیچ‌کدام؛ ابهام باید مثلِ «نبود» رفتار کند نه اینکه
    به‌شانس یکی را انتخاب کنیم.
    """
    users = (
        db.query(User)
        .filter(
            User.phone == phone,
            User.phone_verified_at.is_not(None),
            User.active.is_(True),
        )
        .all()
    )
    return users[0] if len(users) == 1 else None


@router.post("/forgot-password/sms", status_code=202, dependencies=[Depends(limit_sms_code)])
def forgot_password_sms(data: ForgotPasswordSmsIn, db: Session = Depends(get_db)):
    """کدِ بازیابیِ رمز را پیامک می‌کند — همیشه ۲۰۲ و پیامِ یکسان (قرینه‌ی نسخه‌ی ایمیلی).

    پاسخ عمداً به وجود/نبودِ شماره حساس نیست تا این اندپوینت به ابزارِ فهرست‌برداری
    تبدیل نشود؛ به همین دلیل سقفِ per-phone هم بی‌صدا رد می‌شود. کد فقط برای شماره‌ی
    «تأییدشده‌ی یکتا» می‌رود (نگاه کن به `_verified_user_by_phone`). الگوی پیامکِ همان
    کدِ فعال‌سازی بازاستفاده می‌شود، پس نیازی به الگوی تازه در پنلِ ملی‌پیامک نیست.
    """
    phone = sms.normalize_phone(data.phone)
    if phone is not None and limit_password_reset_for_phone(phone):
        user = _verified_user_by_phone(db, phone)
        if user is not None:
            code = issue_code(db, user_id=user.id, purpose=PURPOSE_SMS_PASSWORD_RESET)
            sms.send_verification_code(phone, code)

    return {"detail": "اگر این شماره در سیستم ثبت و تأیید شده باشد، کد بازیابی برایش ارسال شد"}


@router.post("/reset-password/sms", response_model=TokenOut, dependencies=[Depends(limit_sms_reset_verify)])
def reset_password_sms(data: ResetPasswordSmsIn, db: Session = Depends(get_db)):
    """کدِ پیامکی را می‌سنجد، رمزِ تازه را ست و کاربر را وارد می‌کند (مثلِ بازیابیِ ایمیلی).

    خطای یکسان برای «شماره ناموجود/تأییدنشده» و «کدِ غلط یا منقضی» تا از تفاوتِ پیام
    وجودِ شماره استخراج نشود. `consume_code` خودش سقفِ ۵ تلاش و انقضا و یک‌بارمصرفی را
    اعمال می‌کند. ورودِ خودکار عمدی است: کسی که همین حالا مالکیتِ شماره را اثبات کرده
    لازم نیست رمزِ تازه‌اش را دوباره تایپ کند تا وارد شود.
    """
    phone = sms.normalize_phone(data.phone)
    user = _verified_user_by_phone(db, phone) if phone is not None else None
    if user is None or not consume_code(
        db, user_id=user.id, purpose=PURPOSE_SMS_PASSWORD_RESET, code=data.code
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کد نادرست یا منقضی است")

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
def me(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return _me_out(principal, db)


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
        new_phone = data.phone.strip() or None
        if new_phone != user.phone:
            # شماره‌ی تازه هنوز اثباتِ مالکیت ندارد؛ تأییدِ قبلی نباید به آن منتقل شود.
            user.phone = new_phone
            user.phone_verified_at = None

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
    return _me_out(principal, db)


def _mask_phone(phone: str) -> str:
    """۰۹۱۲****۸۷۸ — تا پاسخِ اندپوینت بگوید کد کجا رفت بی‌آنکه کلِ شماره را لو دهد."""
    if len(phone) < 7:
        return phone
    return phone[:4] + "*" * (len(phone) - 7) + phone[-3:]


@router.post("/phone/send-code")
def send_phone_code(
    data: PhoneSendCodeIn,
    _limit=Depends(limit_sms_code),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """کدِ تأییدِ شماره را پیامک می‌کند.

    کاربر همین‌جا احراز شده، پس مسئله‌ی «این شماره مالِ کیست» وجود ندارد؛ شماره روی
    خودِ او ذخیره می‌شود (تأییدنشده) و کد به همان می‌رود. تغییرِ شماره، تأییدِ قبلی را
    باطل می‌کند تا نشانِ «تأییدشده» همیشه به شماره‌ی فعلی اشاره کند.

    پاسخ `sent=false` یعنی ملی‌پیامک نپذیرفت (اعتبار یا کانفیگ) — فرانت باید صادقانه
    بگوید کد نرفت، نه اینکه کاربر بی‌خود منتظرِ پیامکی بماند که هرگز نمی‌آید.
    """
    phone = sms.normalize_phone(data.phone)
    if phone is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "شماره‌ی موبایل معتبر نیست")

    if principal.user.phone != phone:
        principal.user.phone = phone
        principal.user.phone_verified_at = None
    db.flush()

    code = issue_code(db, user_id=principal.user.id, purpose=PURPOSE_PHONE_VERIFY)
    sent = sms.send_verification_code(phone, code)
    return {"sent": sent, "phone": _mask_phone(phone), "expires_in": CODE_TTL_MINUTES * 60}


@router.post("/phone/verify", response_model=MeOut)
def verify_phone(
    data: PhoneVerifyIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """کدِ تأیید را می‌سنجد و شماره را تأییدشده می‌کند.

    consume_code خودش سقفِ تلاش و انقضا را اعمال می‌کند و کدِ درست را یک‌بارمصرف می‌کند؛
    این‌جا فقط لحظه‌ی تأیید ثبت می‌شود.
    """
    if not consume_code(db, user_id=principal.user.id, purpose=PURPOSE_PHONE_VERIFY, code=data.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کد نادرست یا منقضی است")

    principal.user.phone_verified_at = datetime.now(timezone.utc)
    db.flush()
    return _me_out(principal, db)


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
    return _me_out(principal, db)
