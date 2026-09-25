from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.accounting import Account, JournalLine
from app.schemas.accounting import AccountCreateIn, AccountOut, AccountUpdateIn
from app.models.tenant import Tenant
from app.services import account_coding as coding
from app.services import chart_templates as templates
from app.services import tafsili
from pydantic import BaseModel

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

#: یک پیام برای ساخت و ویرایش، تا کاربر دو جمله‌ی متفاوت برای یک قاعده نبیند.
_FX_REVALUABLE_ERROR = "«تسعیر پذیر» فقط روی حسابِ ارزی معنا دارد؛ اول «ارزی» را روشن کنید"


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


class KeptAccountOut(BaseModel):
    """حسابی که برگرداندنِ قالب نگهش داشت، همراهِ دلیلش."""

    code: str
    name: str
    #: «حسابِ سیستمی» · «زیرحساب دارد» · «در سند استفاده شده» · «جای دیگری استفاده شده».
    reason: str


class RevertTemplateOut(BaseModel):
    """نتیجه‌ی برگرداندنِ یک قالب.

    `kept` عمداً فهرستِ دلیل‌دار است، نه فقط عدد: کاربری که «برگردان» می‌زند و
    می‌بیند چند حساب مانده، باید بداند چرا مانده‌اند — وگرنه فکر می‌کند عملیات
    نصفه‌کاره شکست خورده.
    """

    removed: int
    codes: list[str]
    kept: list[KeptAccountOut]


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


class TafsiliModeOut(BaseModel):
    """سطحِ اجبارِ تفصیلی و همه‌ی گزینه‌های ممکن، با توضیحِ هرکدام."""

    mode: str
    #: کلید، برچسب و توضیحِ هر حالت — تا رابط متنِ گزینه‌ها را تکرار نکند.
    options: list[dict]
    #: True یعنی کاربر خودش انتخاب کرده؛ False یعنی هنوز روی پیش‌فرضِ سرویس است.
    is_explicit: bool


class TafsiliModeIn(BaseModel):
    mode: str


def _tafsili_out(tenant: Tenant) -> TafsiliModeOut:
    return TafsiliModeOut(
        mode=tenant.tafsili_enforcement or tafsili.DEFAULT_TAFSILI_MODE,
        is_explicit=tenant.tafsili_enforcement is not None,
        options=[
            {
                "key": key,
                "label": tafsili.TAFSILI_MODE_LABELS[key],
                "hint": tafsili.TAFSILI_MODE_HINTS[key],
                #: پیامدِ تفکیک‌شده — تا رابط بگوید «اگر این را بزنی چه می‌شود»
                #: به‌جای یک جمله‌ی کلی که کاربر باید خودش تفسیرش کند.
                "effects": tafsili.TAFSILI_MODE_EFFECTS[key],
                "is_default": key == tafsili.DEFAULT_TAFSILI_MODE,
            }
            for key in tafsili.TAFSILI_MODES
        ],
    )


@router.get("/tafsili-mode", response_model=TafsiliModeOut)
def get_tafsili_mode(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("accounting", "view")),
):
    """سطحِ اجبارِ تفصیلی روی حساب‌های «تفصیلی پذیر»."""
    tenant = db.get(Tenant, principal.tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کسب‌وکار یافت نشد")
    return _tafsili_out(tenant)


@router.patch("/tafsili-mode", response_model=TafsiliModeOut)
def set_tafsili_mode(
    data: TafsiliModeIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("accounting", "approve")),
):
    """تغییرِ سطحِ اجبار.

    مجوزش `approve` است نه `update`، مثلِ قاعده‌ی کدینگ: تصمیمی در سطحِ کلِ
    کسب‌وکار است که روی هر ثبتِ بعدی اثر می‌گذارد، نه ویرایشِ یک رکورد.

    **روی ردیف‌های گذشته اثری ندارد** و عمداً هم ندارد: سختگیرتر کردنِ قاعده نباید
    سندی را که دیروز درست ثبت شده بود امروز نامعتبر کند. آنچه از قبل بی‌تفصیلی ثبت
    شده در گزارشِ «ردیف‌های بدونِ تفصیلی» دیده می‌شود — در هر سه حالت.
    """
    tenant = db.get(Tenant, principal.tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کسب‌وکار یافت نشد")
    try:
        tafsili.set_mode(tenant, data.mode)
    except ValueError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err)) from None
    db.flush()
    return _tafsili_out(tenant)


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


@router.delete("/templates/{key}", response_model=RevertTemplateOut)
def revert_template(
    key: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "delete")),
):
    """حساب‌های *بی‌استفاده‌ی* یک قالب را برمی‌دارد — راهِ برگشت از «درجِ اشتباه».

    قالب زدن آسان است و برگرداندنش تا امروز نبود؛ کاربری که چهار قالب را امتحان
    می‌کرد، چارتش پر از حسابِ بی‌ربط می‌شد و راهی جز حذفِ تک‌تک نداشت.

    **هرگز چیزی را که استفاده شده پاک نمی‌کند.** چهار چیز حساب را نگه می‌دارد:
    ردیفِ سند (دفتر می‌شکند)، زیرحساب (یتیم می‌شوند)، نقشِ سیستمی (ثبتِ خودکار
    می‌شکند)، و بودن در چارتِ پایه (مالِ قالب نیست). هرکدام با دلیلش در `kept`
    برمی‌گردد تا کاربر بداند چه ماند و چرا.

    ترتیبِ حذف از عمیق‌ترین کد به کم‌عمق‌ترین است، وگرنه سرفصل پیش از فرزندش حذف
    می‌شود و به «زیرحساب دارد» می‌خورد در حالی که فرزندش هم قرار بود برود.
    """
    from app.seed import CHART_OF_ACCOUNTS

    try:
        rows = templates.rows_for(key)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قالبِ کدینگ پیدا نشد") from None

    baseline = {code for code, *_ in CHART_OF_ACCOUNTS}
    wanted = {row[0] for row in rows}
    by_code = {a.code: a for a in db.query(Account).filter(Account.code.in_(wanted)).all()}

    removed: list[str] = []
    kept: list[KeptAccountOut] = []

    # عمیق‌ترین اول: کدِ بلندتر یعنی سطحِ پایین‌تر در درخت.
    for code in sorted(by_code, key=lambda c: (-len(c), c)):
        account = by_code[code]
        if code in baseline:
            continue  # مالِ چارتِ پایه است، نه این قالب — اصلاً نامزدِ حذف نیست
        reason = None
        if account.system_role is not None:
            reason = "حسابِ سیستمی"
        elif db.query(Account).filter(Account.parent_id == account.id).first() is not None:
            reason = "زیرحساب دارد"
        elif db.query(JournalLine).filter(JournalLine.account_id == account.id).first() is not None:
            reason = "در سند استفاده شده"
        if reason:
            kept.append(KeptAccountOut(code=code, name=account.name, reason=reason))
            continue
        try:
            #: SAVEPOINT چون کلیدِ خارجیِ جای دیگری (حسابِ بانکی، دارایی) هم ممکن است
            #: مانع شود؛ آن‌وقت فقط همین حذف برمی‌گردد نه کلِ تراکنش و زمینه‌ی RLS.
            with db.begin_nested():
                db.delete(account)
                db.flush()
            removed.append(code)
        except IntegrityError:
            kept.append(KeptAccountOut(code=code, name=account.name, reason="جای دیگری استفاده شده"))

    return RevertTemplateOut(removed=len(removed), codes=removed, kept=kept)


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

    والد می‌تواند سرفصل باشد یا حسابِ معین — دومی همان «تفصیلی زیرِ معین» است (بانک
    ملی زیرِ بانک)، **حتی اگر آن معین از قبل سند خورده باشد**. عمقِ درخت محدود نیست؛
    نامِ سطح و طولِ کد را قاعده‌ی کدینگِ همین کسب‌وکار تعیین می‌کند.
    """
    if db.query(Account).filter(Account.code == data.code).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "حسابی با این کد از قبل وجود دارد")

    parent = None
    if data.parent_id is not None:
        parent = db.get(Account, data.parent_id)
        if parent is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "سرفصلِ والد یافت نشد")
        #: زیرِ حسابِ معین هم می‌شود تفصیلی ساخت — همان سطحِ چهارمِ حسابداریِ ایران —
        #: **حتی اگر آن معین سند خورده باشد.** ردیف‌های قدیمیِ والد سرِ جایشان
        #: می‌مانند و به زیرحسابِ تازه منتقل نمی‌شوند.
        #:
        #: تا ۱۴۰۵/۰۷/۰۱ این‌جا گاردی بود که حسابِ سندخورده را از زیرحساب‌گرفتن منع
        #: می‌کرد، با این دلیل که «مانده‌اش دو منبع پیدا می‌کند و هر گزارشی باید حدس
        #: بزند کدام را جمع بزند». آن ترس سنجیده شد و **در هیچ‌جا واقعی نبود:**
        #:
        #: * درختِ چارت (`AccountTreePanel`) مانده‌ی گره را «مانده‌ی خودش + جمعِ
        #:   فرزندان» حساب می‌کند و کامنتش صریحاً همین حالت را پیش‌بینی کرده.
        #: * گزارش‌ها (`_leaf_account_totals` و همتاهایش) روی `is_group` صافی
        #:   می‌گذارند، نه روی «فرزند ندارد». والدِ زیرحساب‌دار `is_group=False` می‌ماند،
        #:   پس ردیف‌های خودش در تراز می‌آیند؛ و هر ردیفِ سند دقیقاً مالِ یک حساب است،
        #:   پس نه چیزی جا می‌افتد نه دوبار شمرده می‌شود.
        #:
        #: و گارد هزینه‌ی واقعی داشت: کاربری که «صندوق» را به «صندوقِ اصلی» و «صندوقِ
        #: فرعی» تقسیم می‌کرد، بعد از اولین سند دیگر راهی نداشت.
        #:
        #: **چرا ردیف‌ها منتقل نمی‌شوند.** جابه‌جاکردنشان `account_id`ِ ردیف‌های سندهای
        #: **دائم** را بازنویسی می‌کرد، و «دائم» در این برنامه یعنی امضاشده — حتی
        #: شماره‌ی فرعیِ آن قفل است (`journal.set_sub_number`). کسی که بخواهد مانده
        #: به زیرحساب برود، صفحه‌ی «انتقال مانده به حساب دیگر» همین را با یک سندِ روشنِ
        #: تاریخ‌دار انجام می‌دهد و اسنادِ قدیمی دست نمی‌خورند.
        #:
        #: **چرا ثبتِ سند روی والد بسته نمی‌شود.** والد ممکن است حسابِ سیستمی باشد
        #: (صندوق، بانک) که رسید و فاکتور خودکار رویش می‌نشینند؛ بستنش همه‌ی آن
        #: ثبت‌ها را می‌شکست — همان دامی که تفصیلیِ اجباری را به سندِ دستی محدود کرد.
        #: **این‌جا عمداً هیچ پرچمی سنجیده نمی‌شود.** یک نسخه پیش‌تر، `accepts_tafsili`
        #: ساختِ زیرحساب را هم گارد می‌کرد؛ برداشته شد چون دو چیزِ متفاوت را یکی
        #: گرفته بود. زیرشاخه‌ی درختی (بانک ملی زیرِ بانک) بخشی از *کدینگِ چهارسطحی*
        #: است — کم‌تعداد، ثابت، و قیدِ واقعی‌اش همان «والد سند نخورده باشد» است که
        #: بالا سنجیده شد. `accepts_tafsili` حالا فقط درباره‌ی *تفصیلیِ شناور* روی
        #: ردیفِ سند حرف می‌زند، که ابعادِ متغیرند (۵۰۰ مشتری) و اصلاً در کد نمی‌آیند.
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

    if data.fx_revaluable and not data.is_fx:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _FX_REVALUABLE_ERROR)

    account = Account(
        code=data.code,
        name=data.name,
        name2=data.name2,
        type=data.type,
        #: None یعنی «از نوعِ حساب مشتق شود» — حالتِ درست برای تقریباً همه.
        nature=data.nature,
        is_group=data.is_group,
        parent_id=data.parent_id,
        system_role=None,  # فقط منطقِ ثبتِ خودکار نقش می‌دهد، نه کاربر
        nature_control=data.nature_control,
        is_fx=data.is_fx,
        fx_revaluable=data.fx_revaluable,
        accepts_tafsili=data.accepts_tafsili,
        has_tracking=data.has_tracking,
        in_management_reports=data.in_management_reports,
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
    """تغییرِ نام، عنوانِ دوم، ماهیت، ویژگی‌ها، یا فعال/غیرفعال‌سازیِ حساب.

    **غیرفعال‌سازی برای هر حسابی مجاز است، حتی سیستمی.** گاردِ قبلی می‌گفت حسابِ
    سیستمی «برای ثبتِ خودکار لازم است»، ولی `get_account` اصلاً `is_active` را
    نگاه نمی‌کند — حسابِ غیرفعال را هم پیدا می‌کند و ثبتِ خودکار سرِ جایش کار
    می‌کند. آن گارد کاری را می‌بست که نمی‌شکست، و پیامش هم غلط بود.

    غیرفعال یعنی «از فهرست‌های انتخاب پنهان شو»؛ تاریخچه و ثبتِ خودکار دست‌نخورده
    می‌مانند. حذف داستانِ دیگری است و آن‌جا نقشِ سیستمی واقعاً مانع است.
    """
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب یافت نشد")

    changes = data.model_dump(exclude_unset=True)

    #: قیدِ «تسعیر پذیر فقط روی ارزی» روی *نتیجه* سنجیده می‌شود نه روی ورودی،
    #: چون فرم ممکن است فقط یکی از دو تیک را بفرستد. بدونِ این، خاموش‌کردنِ «ارزی»
    #: به‌تنهایی حساب را در حالتی می‌گذاشت که قیدِ پایگاه‌داده با خطای خامِ
    #: IntegrityError ردش می‌کرد و کاربر پیامِ نامفهوم می‌دید.
    is_fx = changes.get("is_fx", account.is_fx)
    fx_revaluable = changes.get("fx_revaluable", account.fx_revaluable)
    if fx_revaluable and not is_fx:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _FX_REVALUABLE_ERROR)

    #: قفلِ تفصیلی‌پذیری **یک‌طرفه** است: روشن‌کردن همیشه آزاد (ردیف‌های بعدی تفصیلی
    #: می‌گیرند و ضرری ندارد)، خاموش‌کردن فقط تا وقتی هیچ ردیفی تفصیلی نگرفته.
    #:
    #: مشخصاتِ سپیدار قفلِ دوطرفه می‌خواهد — «بعد از یک سند، پرچم قفل». در کوبیتا
    #: آن یعنی قفلِ ابدی، چون سند هرگز پاک نمی‌شود و فقط باطل می‌شود. قاعده‌ی
    #: نامتقارن همان ضرر را می‌بندد: گزارشی که نصفِ ردیف‌هایش تفصیلی دارند و نصفشان
    #: نه، بی‌آنکه هیچ نشانه‌ای بدهد.
    if changes.get("accepts_tafsili") is False and account.accepts_tafsili:
        used = (
            db.query(JournalLine.id)
            .filter(JournalLine.account_id == account.id, JournalLine.analytic_id.isnot(None))
            .first()
        )
        if used is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "ردیف‌هایی از این حساب تفصیلی خورده‌اند؛ برداشتنِ این گزینه گزارشِ "
                "تفصیلی را نصفه می‌کند — نصفِ ردیف‌ها تفصیلی دارند و نصفشان نه",
            )

    for key, value in changes.items():
        setattr(account, key, value)
    db.flush()
    db.refresh(account)
    return account


class DeletableAccountOut(BaseModel):
    """یک حساب و اینکه پاک‌شدنی هست یا نه — پایه‌ی «حذفِ حساب» در تنظیمات.

    `reason` وقتی پر است که نشود پاکش کرد. جدا کردنِ دلیل از خودِ پرچم عمدی است:
    کاربر باید بفهمد *چرا* نمی‌تواند، نه اینکه دکمه‌ای خاکستری ببیند.
    """

    id: UUID
    code: str
    name: str
    level: str
    is_group: bool
    can_delete: bool
    reason: str | None = None


@router.get("/deletable", response_model=list[DeletableAccountOut])
def list_deletable(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("accounting", "view")),
):
    """همه‌ی حساب‌ها با وضعیتِ پاک‌شدنی‌بودنشان.

    حذفِ حساب از درختواره برداشته شد و به تنظیمات آمد: درختواره کارِ روزمره است و
    دکمه‌ی حذف کنارِ دکمه‌ای که روزی صد بار زده می‌شود، دیر یا زود اشتباه زده
    می‌شود. این‌جا تصمیمِ آگاهانه است، با فهرستِ کامل و دلیلِ هر «نمی‌شود».

    شمارشِ ردیف‌های سند و فرزندان با دو کوئریِ تجمیعی گرفته می‌شود، نه یکی به ازای
    هر حساب — چارتِ واقعی صدها حساب دارد.
    """
    tenant = db.get(Tenant, principal.tenant_id)
    widths = coding.get_widths(tenant)

    accounts = db.query(Account).order_by(Account.code).all()
    posted = {
        aid
        for (aid,) in db.query(JournalLine.account_id).distinct().all()
    }
    parents = {pid for (pid,) in db.query(Account.parent_id).filter(Account.parent_id.isnot(None)).distinct().all()}

    out: list[DeletableAccountOut] = []
    for a in accounts:
        reason = None
        if a.system_role is not None:
            reason = "حسابِ سیستمی — ثبتِ خودکار به آن تکیه دارد"
        elif a.id in parents:
            reason = "زیرحساب دارد؛ اول زیرحساب‌ها را بردارید"
        elif a.id in posted:
            reason = "در سند استفاده شده؛ به‌جای حذف غیرفعالش کنید"
        out.append(
            DeletableAccountOut(
                id=a.id,
                code=a.code,
                name=a.name,
                level=coding.level_name(coding.depth_of(db, a.parent)),
                is_group=a.is_group,
                can_delete=reason is None,
                reason=reason,
            )
        )
    return out


class WipeChartOut(BaseModel):
    """نتیجه‌ی خام‌سازیِ درختواره."""

    deleted: int
    #: حساب‌هایی که ماندند چون جای دیگری (بانک، دارایی، تنظیمات) به آنها ارجاع دارد.
    kept: list[KeptAccountOut]


@router.delete("", response_model=WipeChartOut)
def wipe_chart(
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "delete")),
):
    """خام‌سازیِ کلِ درختواره — **فقط وقتی هیچ سندی در کلِ سیستم ثبت نشده باشد.**

    این گارد همه‌ی خطرِ مالی را برمی‌دارد: بدونِ سند، هیچ عددی به هیچ حسابی گره
    نخورده، پس پاک‌کردنِ چارت هیچ دفتری را نمی‌شکند. با یک سند هم، عملیات رد
    می‌شود — نه «تا جایی که می‌شود پاک کن»، چون نتیجه‌ی نصفه بدتر از انجام‌نشدن است.

    حسابِ سیستمی هم پاک می‌شود؛ همان چیزی است که «خام‌سازی» یعنی. منطقِ ثبتِ خودکار
    با `get_or_create_account` هر نقشی را که لازم شود دوباره می‌سازد، پس چیزی از کار
    نمی‌افتد — ولی کدِ دلخواهی که کاربر روی آن حساب گذاشته بود از دست می‌رود، و
    همین است که این عملیات را «آخرین راه» می‌کند نه یک دکمه‌ی روزمره.

    ارجاع‌های غیرِسند (حسابِ بانکی، دارایی ثابت، تنظیمات) با کلیدِ خارجی جلوی حذف را
    می‌گیرند؛ آن حساب‌ها در `kept` با دلیل برمی‌گردند.
    """
    posted = db.query(JournalLine.id).first()
    if posted is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "در این کسب‌وکار سند حسابداری ثبت شده و خام‌سازیِ درختواره ممکن نیست؛ "
            "حساب‌های بی‌استفاده را تک‌به‌تک حذف کنید یا قالب را برگردانید",
        )

    #: از عمیق‌ترین کد به بالا، تا فرزند پیش از والدش برود و کلیدِ خارجیِ
    #: `parent_id` وسطِ کار مانع نشود.
    accounts = db.query(Account).order_by(func.length(Account.code).desc(), Account.code.desc()).all()
    deleted = 0
    kept: list[KeptAccountOut] = []
    for account in accounts:
        try:
            with db.begin_nested():
                db.delete(account)
                db.flush()
            deleted += 1
        except IntegrityError:
            kept.append(
                KeptAccountOut(
                    code=account.code,
                    name=account.name,
                    reason="جای دیگری (حسابِ بانکی، دارایی، تنظیمات) به این حساب ارجاع دارد",
                )
            )
    return WipeChartOut(deleted=deleted, kept=kept)


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
