"""داده‌ی اولیه: نقش‌های پیش‌فرض، یک کاربر مدیر، و چارت حساب پایه برای یک کسب‌وکار فروشگاهی.

اجرا: python -m app.seed
"""
import sys
from datetime import date

from app.database import SessionLocal
from app.models.accounting import Account
from app.models.banking import BankAccount
from app.models.billing import Plan
from app.models.counters import DOC_TYPES, DocumentCounter
from app.models.inventory import Warehouse
from app.models.payroll import PayrollSettings
from app.models.tenant import Membership, Tenant
from app.models.user import DEFAULT_ROLES, Role, User
from app.security import hash_password
from app.services import chart_codes as cc
from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant

# پلن‌های سایت تجاری cubita.ir — سه دوره‌ی صورتحساب (ماهانه/شش‌ماهه/سالانه) با تخفیفِ
# پلکانی (۱۰٪ روی شش‌ماهه، ۲۰٪ روی سالانه نسبت به ماهانه)، هم‌ساختار با رقبای ابری.
# `price_toman` = قیمتِ سالانه (پیش‌فرضِ نمایش)؛ `prices` نگاشتِ کاملِ دوره→قیمت است.
# قیمت‌ها رقابتی و زیرِ رقبای هم‌ردیف‌اند؛ ادمین بعداً می‌تواند تغییرشان دهد.
SAMPLE_PLANS = [
    {
        "key": "basic",
        "name": "پایه",
        "description": "برای کسب‌وکارهای کوچک و تازه‌کار — کلِ چرخه‌ی فروش، خرید، انبار و حسابداریِ رسمی، آنلاین و بدون نیاز به دانش حسابداری.",
        "price_toman": 4_320_000,
        "billing_period": "yearly",
        "prices": {"monthly": 450_000, "semiannual": 2_430_000, "yearly": 4_320_000},
        "max_users": 2,
        "features": [
            "فاکتور فروش و خرید، پیش‌فاکتور، و برگشت از فروش/خرید",
            "انبارداری با کاردکس و موجودیِ لحظه‌ای (+ هشدار نقطه‌ی سفارش)",
            "مدیریت مشتریان و تأمین‌کنندگان + کارت حساب و مانده‌گیریِ سنی",
            "خزانه‌داری: دریافت و پرداخت وجه",
            "حسابداری دوطرفه‌ی کامل: سند دستی، دفتر کل، تراز آزمایشی",
            "مالیات بر ارزش افزوده روی فاکتور + گزارشِ معاملاتِ فصلی (ماده ۱۶۹)",
            "گزارش‌های مالی: ترازنامه، سود و زیان، جریان وجوه نقد",
            "تقویم و یادآوریِ چک‌ها و سررسیدها",
            "نسخه‌ی آنلاین/ابری — دسترسی از هر جا",
            "تا ۲ کاربر + پشتیبانی ایمیلی",
        ],
        "sort_order": 1,
        "highlighted": False,
    },
    {
        "key": "pro",
        "name": "حرفه‌ای",
        "description": "برای کسب‌وکارهای در حالِ رشد با چند کاربر — همه‌ی امکاناتِ پایه به‌علاوه‌ی چک‌وبانک، حقوق، صندوقِ فروشگاهی و کارِ آفلاین.",
        "price_toman": 8_544_000,
        "billing_period": "yearly",
        "prices": {"monthly": 890_000, "semiannual": 4_806_000, "yearly": 8_544_000},
        "max_users": 5,
        "features": [
            "همه‌ی امکاناتِ پلن پایه",
            "چک و بانک: دفتر چک، تنخواه، و تطبیقِ بانکی",
            "حقوق و دستمزد: فیش، بیمه و مالیات، خروجیِ لیستِ بیمه",
            "صندوقِ فروشگاهی (POS) با بارکد",
            "باشگاه مشتریان (CRM) و امتیازِ وفاداری",
            "فروش اقساطی و مدیریتِ اقساط",
            "انبارِ پیشرفته: چند انبار، لیستِ قیمت، بچ/تاریخِ انقضا",
            "اپ دسکتاپ با کارِ آفلاین + هم‌گام‌سازی",
            "تا ۵ کاربر + پشتیبانی تلفنی",
        ],
        "sort_order": 2,
        "highlighted": True,
    },
    {
        "key": "enterprise",
        "name": "سازمانی",
        "description": "برای مجموعه‌های بزرگ با چند شعبه و نیاز به سامانه مؤدیان و پشتیبانیِ اختصاصی.",
        "price_toman": 14_304_000,
        "billing_period": "yearly",
        "prices": {"monthly": 1_490_000, "semiannual": 8_046_000, "yearly": 14_304_000},
        "max_users": None,
        "features": [
            "همه‌ی امکاناتِ پلن حرفه‌ای",
            "کاربرانِ نامحدود",
            "اتصال به سامانه مؤدیان (ارسالِ خودکارِ صورتحساب)",
            "اتصال به فروشگاهِ آنلاین (هم‌گام‌سازیِ موجودی و سفارش)",
            "تولید و بهای تمام‌شده (BOM)",
            "بودجه‌بندی و مراکزِ هزینه/پروژه",
            "چندارزی و نرخِ ارز",
            "پشتیبان‌گیریِ روزانه‌ی اختصاصی + پشتیبانیِ اولویت‌دار",
        ],
        "sort_order": 3,
        "highlighted": False,
    },
]

# ساختار درختی چارت حساب: (کد, نام, نوع, is_group, کد والد یا None)
CHART_OF_ACCOUNTS = [
    ("1", "دارایی‌ها", "asset", True, None),
    ("11", "دارایی‌های جاری", "asset", True, "1"),
    ("1101", "صندوق", "asset", False, "11"),
    ("1102", "بانک", "asset", False, "11"),
    ("1103", "تنخواه‌گردان", "asset", False, "11"),
    ("1104", "حساب‌های دریافتنی (مشتریان)", "asset", False, "11"),
    ("1105", "موجودی کالا", "asset", False, "11"),
    ("1106", "چک‌های دریافتنی", "asset", False, "11"),
    ("1107", "مالیات بر ارزش افزوده / اعتبار مالیاتی", "asset", False, "11"),
    ("12", "دارایی‌های غیرجاری", "asset", True, "1"),
    ("1201", "دارایی‌های ثابت (بهای تمام‌شده)", "asset", False, "12"),
    ("1202", "استهلاک انباشته", "asset", False, "12"),
    ("2", "بدهی‌ها", "liability", True, None),
    ("21", "بدهی‌های جاری", "liability", True, "2"),
    ("2101", "حساب‌های پرداختنی (تأمین‌کنندگان)", "liability", False, "21"),
    ("2102", "چک‌های پرداختنی", "liability", False, "21"),
    ("2103", "بیمه و مالیات پرداختنی", "liability", False, "21"),
    ("2104", "حقوق پرداختنی کارکنان", "liability", False, "21"),
    ("2105", "مالیات بر ارزش افزوده پرداختنی", "liability", False, "21"),
    ("3", "حقوق صاحبان سرمایه", "equity", True, None),
    ("3101", "سرمایه", "equity", False, "3"),
    ("3102", "سود و زیان انباشته", "equity", False, "3"),
    # دو حسابِ واسطِ پایانِ سال. مانده‌ی واقعی نمی‌سازند — در سندِ اختتامیه یک طرف و
    # در افتتاحیه‌ی سالِ بعد طرفِ دیگرشان می‌نشیند و جمعشان صفر می‌شود.
    ("3901", "حساب اختتامیه", "equity", False, "3"),
    ("3902", "حساب افتتاحیه", "equity", False, "3"),
    ("4", "درآمدها", "income", True, None),
    ("4101", "فروش کالا - حضوری", "income", False, "4"),
    ("4102", "فروش کالا - آنلاین", "income", False, "4"),
    ("4103", "درآمد متفرقه", "income", False, "4"),
    # ۴۱۰۴ و ۵۱۰۷ مالِ قالب‌های صنفی‌اند («تخفیفات و برگشت از فروش» و «هزینه آب و
    # برق…»)؛ گرفتنشان اینجا باعث می‌شد اعمالِ قالب آن دو حساب را بی‌صدا رد کند.
    ("4106", "سود تسعیر ارز", "income", False, "4"),
    ("5", "هزینه‌ها", "expense", True, None),
    ("5101", "بهای تمام‌شده کالای فروش‌رفته", "expense", False, "5"),
    ("5102", "هزینه حقوق و دستمزد", "expense", False, "5"),
    ("5103", "هزینه اجاره", "expense", False, "5"),
    ("5104", "هزینه‌های عمومی و اداری", "expense", False, "5"),
    ("5105", "مغایرت انبار (کسری/اضافی)", "expense", False, "5"),
    ("5106", "هزینه استهلاک", "expense", False, "5"),
    # نام عمداً دقیقاً همانِ قالب‌های صنفی است تا کدِ مشترک تصادمِ نام نسازد.
    ("5111", "کارمزد و هزینه‌های بانکی", "expense", False, "5"),
    ("5116", "زیان تسعیر ارز", "expense", False, "5"),
]


def seed_platform(db) -> None:
    """داده‌ی سراسری پلتفرم — به هیچ مستأجری تعلق ندارد. یک‌بار برای کل نصب."""
    for plan_def in SAMPLE_PLANS:
        if not db.query(Plan).filter(Plan.key == plan_def["key"]).first():
            db.add(Plan(**plan_def))
    db.flush()


def provision_tenant(
    db,
    *,
    name: str,
    slug: str,
    owner_email: str,
    owner_password: str,
    owner_name: str = "مدیر سیستم",
    max_users: int | None = None,
    is_trial: bool = False,
    kind: str = "standard",
) -> Tenant:
    """یک مستأجر کامل و آماده‌ی کار می‌سازد.

    تراکنشی و idempotent است چون از webhook پرداخت فراخوانی می‌شود و آن webhook
    می‌تواند دوباره تلاش کند؛ اجرای دوباره نباید مستأجر تکراری بسازد.

    زمینه‌ی مستأجر همین اول ست می‌شود، چون از آن به بعد هر INSERT زیر سیاست RLS
    می‌رود و بدون زمینه، WITH CHECK آن را رد می‌کند.
    """
    tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
    if tenant is None:
        tenant = Tenant(
            name=name, slug=slug, status="active", max_users=max_users, is_trial=is_trial, kind=kind
        )
        db.add(tenant)
        db.flush()

    apply_tenant_to_transaction(db, tenant.id)
    bind_session_tenant(db, tenant.id)

    roles_by_key: dict[str, Role] = {}
    for role_def in DEFAULT_ROLES:
        role = db.query(Role).filter(Role.key == role_def["key"], Role.tenant_id == tenant.id).first()
        if role is None:
            role = Role(
                tenant_id=tenant.id,
                key=role_def["key"],
                name=role_def["name"],
                permissions=role_def["permissions"],
            )
            db.add(role)
            db.flush()
        roles_by_key[role.key] = role

    accounts_by_code: dict[str, Account] = {}
    for code, name_, type_, is_group, parent_code in CHART_OF_ACCOUNTS:
        account = db.query(Account).filter(Account.code == code, Account.tenant_id == tenant.id).first()
        if account is None:
            parent = accounts_by_code.get(parent_code) if parent_code else None
            account = Account(
                tenant_id=tenant.id,
                code=code,
                # نقش از کد پیش‌فرض گرفته می‌شود، ولی از این به بعد نقش است که
                # اهمیت دارد: مشتری می‌تواند کد را عوض کند بدون اینکه چیزی بشکند.
                system_role=cc.ROLE_BY_DEFAULT_CODE.get(code),
                name=name_,
                type=type_,
                is_group=is_group,
                parent_id=parent.id if parent else None,
            )
            db.add(account)
            db.flush()
        accounts_by_code[code] = account

    for wh_code, wh_name in (("MAIN", "انبار اصلی"), ("ONLINE", "انبار آنلاین")):
        if not db.query(Warehouse).filter(Warehouse.code == wh_code, Warehouse.tenant_id == tenant.id).first():
            db.add(Warehouse(tenant_id=tenant.id, code=wh_code, name=wh_name))

    if not db.query(BankAccount).filter(BankAccount.name == "حساب اصلی", BankAccount.tenant_id == tenant.id).first():
        db.add(BankAccount(tenant_id=tenant.id, name="حساب اصلی", gl_account_id=accounts_by_code["1102"].id))

    # شمارنده‌ی هر نوع سند. بدون این‌ها اولین ثبت سند شکست می‌خورد — عمداً، چون
    # جایگزین بی‌صدا از ۱ یعنی شماره‌ی تکراری.
    for doc_type in DOC_TYPES:
        exists = (
            db.query(DocumentCounter)
            .filter(DocumentCounter.tenant_id == tenant.id, DocumentCounter.doc_type == doc_type)
            .first()
        )
        if exists is None:
            db.add(DocumentCounter(tenant_id=tenant.id, doc_type=doc_type, last_number=0))

    _seed_payroll_settings(db, tenant)
    _create_owner(db, tenant, roles_by_key, owner_email, owner_password, owner_name)
    db.flush()
    return tenant


def _seed_payroll_settings(db, tenant: Tenant) -> None:
    current_year = date.today().year
    if (
        not db.query(PayrollSettings)
        .filter(PayrollSettings.year == current_year, PayrollSettings.tenant_id == tenant.id)
        .first()
    ):
        # نرخ سهم بیمه (۷٪ کارمند / ۲۳٪ کارفرما طبق ماده ۲۸ قانون تأمین اجتماعی) نرخ ساختاری و پایدار است،
        # اما سقف معافیت مالیاتی و پلکان‌ها هرسال با قانون بودجه عوض می‌شوند — این‌جا عمداً placeholder
        # و غیرفعال (نرخ صفر) گذاشته شده تا هیچ عدد نادرستی به‌عنوان مبنای قانونی فرض نشود.
        # صدور فیش با همین مقدار توسط گاردِ generate_payslips_for_period رد می‌شود.
        db.add(
            PayrollSettings(
                tenant_id=tenant.id,
                year=current_year,
                insurance_employee_rate="0.07",
                insurance_employer_rate="0.23",
                tax_exemption_annual="0",
                tax_brackets=[{"up_to": None, "rate": "0"}],
                notes="PLACEHOLDER — نرخ بیمه ساختاری تخمینی است، مالیات غیرفعال (۰٪). قبل از صدور فیش واقعی با ارقام رسمی همان سال جایگزین شود.",
            )
        )


def _create_owner(db, tenant: Tenant, roles_by_key, email: str, password: str, name: str) -> User:
    """کاربر سراسری + عضویتش در این مستأجر.

    اگر کاربر از قبل وجود داشته باشد (یک حسابدار که دفتر چند کسب‌وکار را می‌برد)
    فقط عضویت جدید اضافه می‌شود، نه کاربر تکراری.
    """
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(name=name, email=email, hashed_password=hash_password(password))
        db.add(user)
        db.flush()

    membership = (
        db.query(Membership).filter(Membership.user_id == user.id, Membership.tenant_id == tenant.id).first()
    )
    if membership is None:
        db.add(
            Membership(
                user_id=user.id,
                tenant_id=tenant.id,
                role_id=roles_by_key["owner"].id,
                status="active",
            )
        )
    return user


def seed(owner_email: str, owner_password: str, owner_name: str = "مدیر سیستم") -> None:
    """نصب کامل یک نسخه‌ی تک‌مستأجری — برای dev و برای اولین راه‌اندازی."""
    db = SessionLocal()
    try:
        seed_platform(db)
        provision_tenant(
            db,
            name="کسب‌وکار اصلی",
            slug="default",
            owner_email=owner_email,
            owner_password=owner_password,
            owner_name=owner_name,
        )
        db.commit()
        print(f"seed کامل شد. کاربر مدیر: {owner_email}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m app.seed <owner_email> <owner_password>")
        sys.exit(1)
    seed(sys.argv[1], sys.argv[2])
