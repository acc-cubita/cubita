"""داده‌ی اولیه: نقش‌های پیش‌فرض، یک کاربر مدیر، و چارت حساب پایه برای یک کسب‌وکار فروشگاهی.

اجرا: python -m app.seed
"""
import sys

from sqlalchemy import text

from datetime import date

from app.database import Base, SessionLocal, engine
from app.models.accounting import Account
from app.models.banking import BankAccount
from app.models.billing import Plan
from app.models.inventory import Warehouse
from app.models.payroll import PayrollSettings
from app.models.user import DEFAULT_ROLES, Role, User
from app.security import hash_password

# پلن‌های نمونه‌ی سایت تجاری cubita.ir — قیمت‌ها placeholder هستند، بعداً توسط ادمین قابل تغییرند
SAMPLE_PLANS = [
    {
        "key": "basic",
        "name": "پایه",
        "description": "برای کسب‌وکارهای کوچک که تازه حسابداری منظم را شروع می‌کنند.",
        "price_toman": 4_800_000,
        "billing_period": "yearly",
        "max_users": 1,
        "features": [
            "فاکتور فروش/خرید و انبارداری",
            "حسابداری دوطرفه کامل و گزارش‌های استاندارد",
            "پشتیبانی ایمیلی",
        ],
        "sort_order": 1,
        "highlighted": False,
    },
    {
        "key": "pro",
        "name": "حرفه‌ای",
        "description": "برای کسب‌وکارهایی با چند کاربر هم‌زمان که به چک و بانک و حقوق هم نیاز دارند.",
        "price_toman": 12_000_000,
        "billing_period": "yearly",
        "max_users": 5,
        "features": [
            "همه‌ی امکانات پلن پایه",
            "چک و بانک و تطبیق بانکی",
            "حقوق و دستمزد",
            "اپ دسکتاپ آفلاین + هم‌گام‌سازی",
            "پشتیبانی تلفنی",
        ],
        "sort_order": 2,
        "highlighted": True,
    },
    {
        "key": "enterprise",
        "name": "سازمانی",
        "description": "برای مجموعه‌های بزرگ‌تر با چند شعبه/انبار و نیاز به پشتیبانی اختصاصی.",
        "price_toman": 24_000_000,
        "billing_period": "yearly",
        "max_users": None,
        "features": [
            "همه‌ی امکانات پلن حرفه‌ای",
            "کاربران نامحدود",
            "اتصال به سامانه مؤدیان",
            "پشتیبان‌گیری روزانه اختصاصی",
            "پشتیبانی اولویت‌دار",
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
    ("2", "بدهی‌ها", "liability", True, None),
    ("21", "بدهی‌های جاری", "liability", True, "2"),
    ("2101", "حساب‌های پرداختنی (تأمین‌کنندگان)", "liability", False, "21"),
    ("2102", "چک‌های پرداختنی", "liability", False, "21"),
    ("2103", "بیمه و مالیات پرداختنی", "liability", False, "21"),
    ("2104", "حقوق پرداختنی کارکنان", "liability", False, "21"),
    ("3", "حقوق صاحبان سرمایه", "equity", True, None),
    ("3101", "سرمایه", "equity", False, "3"),
    ("3102", "سود و زیان انباشته", "equity", False, "3"),
    ("4", "درآمدها", "income", True, None),
    ("4101", "فروش کالا - حضوری", "income", False, "4"),
    ("4102", "فروش کالا - آنلاین", "income", False, "4"),
    ("4103", "درآمد متفرقه", "income", False, "4"),
    ("5", "هزینه‌ها", "expense", True, None),
    ("5101", "بهای تمام‌شده کالای فروش‌رفته", "expense", False, "5"),
    ("5102", "هزینه حقوق و دستمزد", "expense", False, "5"),
    ("5103", "هزینه اجاره", "expense", False, "5"),
    ("5104", "هزینه‌های عمومی و اداری", "expense", False, "5"),
    ("5105", "مغایرت انبار (کسری/اضافی)", "expense", False, "5"),
]


def seed(owner_email: str, owner_password: str, owner_name: str = "مدیر سیستم") -> None:
    Base.metadata.create_all(bind=engine)  # فقط برای dev سریع؛ در production از alembic استفاده کنید
    with engine.begin() as conn:
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS journal_entry_number_seq START 1"))
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS sales_invoice_number_seq START 1"))
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS purchase_invoice_number_seq START 1"))
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS payslip_number_seq START 1"))
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS sales_quotation_number_seq START 1"))
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS sales_return_number_seq START 1"))
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS purchase_return_number_seq START 1"))
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS stock_transfer_number_seq START 1"))
    db = SessionLocal()
    try:
        roles_by_key: dict[str, Role] = {}
        for role_def in DEFAULT_ROLES:
            role = db.query(Role).filter(Role.key == role_def["key"]).first()
            if role is None:
                role = Role(key=role_def["key"], name=role_def["name"], permissions=role_def["permissions"])
                db.add(role)
                db.flush()
            roles_by_key[role.key] = role

        accounts_by_code: dict[str, Account] = {}
        for code, name, type_, is_group, parent_code in CHART_OF_ACCOUNTS:
            account = db.query(Account).filter(Account.code == code).first()
            if account is None:
                parent = accounts_by_code.get(parent_code) if parent_code else None
                account = Account(
                    code=code,
                    name=name,
                    type=type_,
                    is_group=is_group,
                    parent_id=parent.id if parent else None,
                )
                db.add(account)
                db.flush()
            accounts_by_code[code] = account

        if not db.query(Warehouse).filter(Warehouse.code == "MAIN").first():
            db.add(Warehouse(code="MAIN", name="انبار اصلی"))

        if not db.query(Warehouse).filter(Warehouse.code == "ONLINE").first():
            # سفارش‌های وارداتی از سایت فروشگاهی (فاز Integration) از این انبار کسر می‌شوند
            db.add(Warehouse(code="ONLINE", name="انبار آنلاین"))

        if not db.query(BankAccount).filter(BankAccount.name == "حساب اصلی").first():
            db.add(BankAccount(name="حساب اصلی", gl_account_id=accounts_by_code["1102"].id))

        current_year = date.today().year
        if not db.query(PayrollSettings).filter(PayrollSettings.year == current_year).first():
            # نرخ سهم بیمه (۷٪ کارمند / ۲۳٪ کارفرما طبق ماده ۲۸ قانون تأمین اجتماعی) نرخ ساختاری و پایدار است،
            # اما سقف معافیت مالیاتی و پلکان‌ها هرسال با قانون بودجه عوض می‌شوند — این‌جا عمداً placeholder
            # و غیرفعال (نرخ صفر) گذاشته شده تا هیچ عدد نادرستی به‌عنوان مبنای قانونی فرض نشود.
            # قبل از صدور فیش واقعی حتماً از PUT /api/payroll-settings با ارقام تأییدشده‌ی همان سال بروزرسانی کنید.
            db.add(
                PayrollSettings(
                    year=current_year,
                    insurance_employee_rate="0.07",
                    insurance_employer_rate="0.23",
                    tax_exemption_annual="0",
                    tax_brackets=[{"up_to": None, "rate": "0"}],
                    notes="PLACEHOLDER — نرخ بیمه ساختاری تخمینی است، مالیات غیرفعال (۰٪). قبل از صدور فیش واقعی با ارقام رسمی همان سال جایگزین شود.",
                )
            )

        for plan_def in SAMPLE_PLANS:
            if not db.query(Plan).filter(Plan.key == plan_def["key"]).first():
                db.add(Plan(**plan_def))

        if not db.query(User).filter(User.email == owner_email).first():
            db.add(
                User(
                    name=owner_name,
                    email=owner_email,
                    hashed_password=hash_password(owner_password),
                    role_id=roles_by_key["owner"].id,
                )
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
