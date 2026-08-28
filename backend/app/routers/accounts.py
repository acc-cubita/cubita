from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.accounting import Account, JournalLine
from app.schemas.accounting import AccountCreateIn, AccountOut, AccountUpdateIn
from app.models.tenant import Tenant
from app.services import account_coding as coding
from app.services import chart_templates as templates
from pydantic import BaseModel

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountCodeIn(BaseModel):
    code: str


class CodingLevelOut(BaseModel):
    name: str
    #: رقمِ افزوده در این سطح.
    width: int
    #: طولِ کلِ کد در این سطح.
    total: int
    #: نمونه‌ی کد.
    example: str


class CodingRuleOut(BaseModel):
    widths: list[int]
    levels: list[CodingLevelOut]


class CodingRuleIn(BaseModel):
    widths: list[int]


def _coding_out(widths: list[int]) -> CodingRuleOut:
    samples = coding.preview(widths)
    return CodingRuleOut(
        widths=widths,
        levels=[
            CodingLevelOut(
                name=coding.level_name(i),
                width=coding.width_for(widths, i),
                total=len(samples[i]),
                example=samples[i],
            )
            for i in range(len(widths))
        ],
    )


class ChartTemplateOut(BaseModel):
    key: str
    label: str
    hint: str
    #: چند حساب در این قالب تعریف شده (بدونِ سرفصل‌های مشترک).
    total: int
    #: چند تای آن‌ها هنوز در چارتِ این کسب‌وکار نیست.
    missing: int


class ChartSetupOut(BaseModel):
    """آیا «کدینگ حساب‌ها» انجام شده — برای نشانِ گامِ «عملیات اول دوره».

    هر کسب‌وکار از لحظه‌ی ساخت یک چارتِ پایه دارد، پس «حساب دارد یا نه» سؤالِ بی‌معنایی
    است و همیشه بله جواب می‌دهد. سؤالِ درست این است: آیا کاربر چارت را *گسترش* داده —
    چه با درجِ قالبِ صنفی، چه با ساختنِ حسابِ خودش.
    """

    #: کلِ حساب‌های چارت.
    total: int
    #: حساب‌هایی که در چارتِ پایه نبوده‌اند — یعنی کارِ خودِ کاربر.
    custom: int
    #: کلیدِ قالبی که کاملاً درج شده (اگر چند تا، اولی). None = هیچ قالبی کامل نیست.
    applied_template: str | None


class ApplyTemplateOut(BaseModel):
    created: int
    skipped: int
    #: کدهایی که تازه ساخته شدند — تا رابط کاربری دقیقاً بگوید چه اضافه شد.
    codes: list[str]


def _missing_rows(db: Session, key: str):
    """ردیف‌هایی از قالب که کدشان هنوز در چارت نیست."""
    existing = {code for (code,) in db.query(Account.code).all()}
    return [row for row in templates.rows_for(key) if row[0] not in existing]


@router.get("/coding-rule", response_model=CodingRuleOut)
def get_coding_rule(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("accounting", "view")),
):
    """قاعده‌ی کدینگِ چارت: چند رقم در هر سطح."""
    return _coding_out(coding.get_widths(db.get(Tenant, principal.tenant_id)))


@router.patch("/coding-rule", response_model=CodingRuleOut)
def set_coding_rule(
    data: CodingRuleIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("accounting", "approve")),
):
    """قاعده را عوض می‌کند. حساب‌های موجود دست نمی‌خورند — فقط کدِ تازه."""
    tenant = db.get(Tenant, principal.tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کسب‌وکار یافت نشد")
    clean = coding.set_widths(tenant, data.widths)
    db.flush()
    return _coding_out(clean)


@router.get("/next-code", response_model=dict)
def next_code(
    parent_id: UUID | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("accounting", "view")),
):
    """کدِ آزادِ بعدی زیرِ یک سرفصل، طبقِ قاعده — تا فرم حدس نزند."""
    parent = db.get(Account, parent_id) if parent_id else None
    widths = coding.get_widths(db.get(Tenant, principal.tenant_id))
    depth = coding.depth_of(db, parent)
    try:
        code = coding.suggest_code(db, parent=parent, widths=widths)
    except ValueError as err:
        raise HTTPException(status.HTTP_409_CONFLICT, str(err)) from None
    return {
        "code": code,
        "level": coding.level_name(depth),
        "digits": coding.effective_width(db, parent, widths, depth),
    }


@router.get("/templates", response_model=list[ChartTemplateOut])
def list_templates(
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """قالب‌های آماده‌ی کدینگ و اینکه از هرکدام چند حساب هنوز ساخته نشده."""
    out = []
    for key, meta in templates.TEMPLATES.items():
        rows = templates.rows_for(key)
        out.append(
            ChartTemplateOut(
                key=key,
                label=meta["label"],
                hint=meta["hint"],
                # سرفصل‌های مشترک جزوِ «تعدادِ قالب» شمرده نمی‌شوند؛ آن‌ها زیرساخت‌اند.
                total=len(templates.COMMON) + len(meta["rows"]),
                missing=len([r for r in _missing_rows(db, key) if not r[3]]),
            )
        )
    return out


@router.get("/setup-status", response_model=ChartSetupOut)
def setup_status(
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """وضعیتِ آماده‌سازیِ چارت — پایه‌ی نشانِ «انجام شده» در «عملیات اول دوره»."""
    from app.seed import CHART_OF_ACCOUNTS

    baseline = {code for code, *_ in CHART_OF_ACCOUNTS}
    codes = [code for (code,) in db.query(Account.code).all()]
    applied = next(
        (key for key in templates.TEMPLATES if not [r for r in _missing_rows(db, key) if not r[3]]),
        None,
    )
    return ChartSetupOut(
        total=len(codes),
        custom=len([c for c in codes if c not in baseline]),
        applied_template=applied,
    )


@router.post("/templates/{key}", response_model=ApplyTemplateOut)
def apply_template(
    key: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "create")),
):
    """حساب‌های نبودِ یک قالب را می‌سازد.

    حسابِ موجود هرگز دست نمی‌خورد و نقشِ سیستمی داده نمی‌شود، پس اجرای دوباره بی‌اثر
    و بی‌خطر است. والد با کد پیدا می‌شود و اگر نبود، خودش ساخته می‌شود — به همین دلیل
    ترتیبِ ردیف‌ها (والد پیش از فرزند) در قالب رعایت شده است.
    """
    try:
        rows = templates.rows_for(key)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قالبِ کدینگ پیدا نشد") from None

    by_code: dict[str, Account] = {a.code: a for a in db.query(Account).all()}
    created: list[str] = []
    skipped = 0

    for code, name, acc_type, is_group, parent_code in rows:
        if code in by_code:
            skipped += 1
            continue
        parent = by_code.get(parent_code) if parent_code else None
        account = Account(
            code=code,
            name=name,
            type=acc_type,
            is_group=is_group,
            is_active=True,
            parent_id=parent.id if parent else None,
        )
        db.add(account)
        db.flush()
        by_code[code] = account
        created.append(code)

    return ApplyTemplateOut(created=len(created), skipped=skipped, codes=created)


@router.patch("/{account_id}/code", response_model=AccountOut)
def change_code(
    account_id: UUID,
    data: AccountCodeIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "update")),
):
    """تغییرِ کدِ حساب — همان «کدینگ» که حسابدارها با رویه‌ی خودشان انجام می‌دهند.

    امن است چون منطقِ ثبتِ خودکار حساب را با `system_role` پیدا می‌کند نه با کد
    (توضیحش در services/chart_codes). کدِ تکراری با ۴۰۹ رد می‌شود.
    """
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب پیدا نشد")

    new_code = data.code.strip()
    if not new_code:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کد حساب نمی‌تواند خالی باشد")
    if new_code == account.code:
        return account
    if db.query(Account).filter(Account.code == new_code, Account.id != account.id).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"کد {new_code} برای حساب دیگری استفاده شده است")

    account.code = new_code
    db.flush()
    db.refresh(account)
    return account



@router.get("", response_model=list[AccountOut])
def list_accounts(
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return db.query(Account).order_by(Account.code).all()


@router.post("", response_model=AccountOut, status_code=201)
def create_account(
    data: AccountCreateIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("accounting", "create")),
):
    """ساختِ حسابِ تازه در چارت — زیرِ یک سرفصل یا در ریشه.

    نقشِ سیستمی هرگز از این راه ست نمی‌شود؛ فقط منطقِ ثبتِ خودکار حسابِ نقش‌دار
    می‌سازد. زیرحساب باید نوعش با سرفصلش یکی باشد (زیرحسابِ «دارایی‌ها» خودش دارایی
    است) وگرنه گزارش‌ها ناسازگار می‌شوند.
    """
    if db.query(Account).filter(Account.code == data.code).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "حسابی با این کد از قبل وجود دارد")

    parent = None
    if data.parent_id is not None:
        parent = db.get(Account, data.parent_id)
        if parent is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "سرفصلِ والد یافت نشد")
        if not parent.is_group:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "فقط زیرِ یک سرفصل (گروه) می‌توان حساب ساخت")
        if data.type != parent.type:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوعِ زیرحساب باید با نوعِ سرفصلش یکی باشد")

    # قاعده‌ی کدینگِ همین کسب‌وکار — طولِ کد باید با سطحِ حساب جور باشد.
    tenant = db.get(Tenant, principal.tenant_id)
    try:
        coding.validate_new_code(
            db, code=data.code, parent=parent, widths=coding.get_widths(tenant)
        )
    except ValueError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err)) from None

    account = Account(
        code=data.code,
        name=data.name,
        type=data.type,
        is_group=data.is_group,
        parent_id=data.parent_id,
        system_role=None,  # فقط منطقِ ثبتِ خودکار نقش می‌دهد، نه کاربر
    )
    db.add(account)
    db.flush()
    db.refresh(account)
    return account


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: UUID,
    data: AccountUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "update")),
):
    """تغییرِ نام یا فعال/غیرفعال‌سازیِ حساب. حسابِ سیستمی را نمی‌توان غیرفعال کرد."""
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب یافت نشد")

    if data.is_active is False and account.system_role is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این حسابِ سیستمی است و برای ثبتِ خودکار لازم است؛ نمی‌توان غیرفعالش کرد",
        )

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(account, key, value)
    db.flush()
    db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=204)
def delete_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "delete")),
):
    """حذفِ حساب — فقط اگر سیستمی نباشد، زیرحساب نداشته باشد و در هیچ سندی نیامده باشد.

    حسابی که سند دارد نباید پاک شود (دفتر را می‌شکند)؛ به‌جایش «غیرفعال» شود. قیدهای
    کلیدِ خارجی مرجعِ حقیقت‌اند: تلاشِ حذف داخل SAVEPOINT انجام می‌شود و اگر سند
    مانع شد فقط همان savepoint برمی‌گردد، نه کلِ تراکنش/زمینه‌ی RLS.
    """
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب یافت نشد")
    if account.system_role is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "حسابِ سیستمی قابلِ حذف نیست؛ آن را غیرفعال کنید")
    if db.query(Account).filter(Account.parent_id == account_id).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این سرفصل زیرحساب دارد؛ اول زیرحساب‌ها را جابه‌جا/حذف کنید")
    if db.query(JournalLine).filter(JournalLine.account_id == account_id).first() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این حساب در سند استفاده شده و قابلِ حذف نیست؛ به‌جای حذف، آن را «غیرفعال» کنید",
        )
    try:
        with db.begin_nested():
            db.delete(account)
            db.flush()
    except IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این حساب در جای دیگری استفاده شده و قابلِ حذف نیست؛ آن را «غیرفعال» کنید",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
