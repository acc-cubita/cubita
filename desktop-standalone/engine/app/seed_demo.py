"""داده‌ی نمونه‌ی «دیجی‌مارکت» — یک فروشگاه اینترنتیِ لوازم دیجیتال به سبکِ دیجی‌کالا،
برای دموی عمومیِ cubita.ir. روی یک دیتابیس کاملاً جدا و ایزوله اجرا می‌شود (هرگز روی
دیتابیس واقعیِ کسب‌وکار). یک کاربر «دمو» (فقط‌خواندنی) می‌سازد و کاتالوگ کامل کالا،
مشتری/تأمین‌کننده، خرید، ماه‌ها فروش، بانک و چک، هزینه و پرسنل را پر می‌کند تا هر ماژول
با داده‌ی واقع‌گرایانه پر باشد.

اجرا: DEMO_OWNER_PASSWORD="..." DEMO_LOGIN_PASSWORD="..." python -m app.seed_demo
"""
import os
import random
import sys
from datetime import date, timedelta
from decimal import Decimal

from app.database import SessionLocal
from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.banking import BankAccount
from app.models.inventory import Contact, Item, Warehouse
from app.models.invoices import SalesInvoice
from app.models.payroll import Employee, SalaryContract
from app.models.tenant import Membership, Tenant
from app.models.user import Role, User
from app.schemas.banking import BankDepositWithdrawIn, CheckIn
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.security import hash_password
from app.seed import seed
from app.services import chart_codes as cc
from app.services.banking import create_bank_transaction, create_check
from app.services.common import get_account, make_journal_entry
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant

DEMO_TENANT_SLUG = "default"
STORE_NAME = "فروشگاه اینترنتی دیجی‌مارکت"
OPENING_MARKER = "افتتاحیه — سرمایه‌ی اولیه‌ی دیجی‌مارکت"

# رمزها از محیط خوانده می‌شوند و پیش‌فرض ندارند — تا چرخش رمزِ دمو نیازی به تغییر کد
# نداشته باشد و رمزِ واقعی هیچ‌وقت داخل مخزن ننشیند.
DEMO_OWNER_EMAIL = os.environ.get("DEMO_OWNER_EMAIL", "owner-demo@cubita.ir")
DEMO_OWNER_PASSWORD = os.environ.get("DEMO_OWNER_PASSWORD", "")
DEMO_LOGIN_EMAIL = os.environ.get("DEMO_LOGIN_EMAIL", "demo@cubita.ir")
DEMO_LOGIN_PASSWORD = os.environ.get("DEMO_LOGIN_PASSWORD", "")

# کاتالوگ: (کد کالا, نام, دسته, قیمت فروش, بهای خرید, موجودی انبار مرکزی, موجودی انبار آنلاین)
# قیمت‌ها به تومان و در بازه‌ی واقع‌گرایانه‌ی بازار لوازم دیجیتال‌اند.
SAMPLE_ITEMS = [
    # موبایل
    ("MOB-001", "گوشی سامسونگ Galaxy A55 5G ظرفیت ۲۵۶ گیگابایت", "موبایل", 21_500_000, 18_800_000, 12, 18),
    ("MOB-002", "گوشی سامسونگ Galaxy S24 Ultra ظرفیت ۲۵۶ گیگابایت", "موبایل", 62_000_000, 55_000_000, 8, 12),
    ("MOB-003", "گوشی شیائومی Redmi Note 13 Pro ظرفیت ۲۵۶ گیگابایت", "موبایل", 14_900_000, 12_800_000, 15, 22),
    ("MOB-004", "گوشی اپل iPhone 15 ظرفیت ۱۲۸ گیگابایت", "موبایل", 68_000_000, 61_000_000, 8, 12),
    ("MOB-005", "گوشی اپل iPhone 15 Pro Max ظرفیت ۲۵۶ گیگابایت", "موبایل", 105_000_000, 96_000_000, 6, 9),
    ("MOB-006", "گوشی شیائومی Poco X6 Pro ظرفیت ۵۱۲ گیگابایت", "موبایل", 17_200_000, 14_900_000, 14, 20),
    ("MOB-007", "گوشی سامسونگ Galaxy A15 ظرفیت ۱۲۸ گیگابایت", "موبایل", 8_900_000, 7_600_000, 18, 26),
    # لپ‌تاپ
    ("LAP-001", "لپ‌تاپ ایسوس VivoBook 15 Core i5 نسل ۱۳", "لپ‌تاپ", 32_000_000, 28_500_000, 7, 9),
    ("LAP-002", "لپ‌تاپ لنوو IdeaPad Gaming 3 Ryzen 7", "لپ‌تاپ", 45_000_000, 40_000_000, 6, 8),
    ("LAP-003", "لپ‌تاپ اپل MacBook Air M2 ۱۳ اینچ", "لپ‌تاپ", 78_000_000, 71_000_000, 5, 7),
    ("LAP-004", "لپ‌تاپ اچ‌پی Victus 15 Core i7 نسل ۱۲", "لپ‌تاپ", 52_000_000, 46_500_000, 6, 8),
    # تبلت
    ("TAB-001", "تبلت سامسونگ Galaxy Tab S9 FE", "تبلت", 28_000_000, 24_500_000, 8, 10),
    ("TAB-002", "تبلت اپل iPad 10.9 اینچ نسل ۱۰", "تبلت", 34_000_000, 30_000_000, 7, 10),
    # صوتی و هدفون
    ("AUD-001", "هندزفری اپل AirPods Pro 2", "صوتی", 12_500_000, 10_800_000, 25, 35),
    ("AUD-002", "هدفون بی‌سیم سونی WH-1000XM5", "صوتی", 18_900_000, 16_500_000, 15, 20),
    ("AUD-003", "هندزفری بلوتوث شیائومی Redmi Buds 5", "صوتی", 1_650_000, 1_250_000, 40, 60),
    ("AUD-004", "اسپیکر بلوتوث JBL Charge 5", "صوتی", 6_900_000, 5_800_000, 20, 28),
    # ساعت هوشمند
    ("WCH-001", "ساعت هوشمند اپل Watch Series 9 سایز ۴۵", "ساعت هوشمند", 29_500_000, 26_000_000, 12, 16),
    ("WCH-002", "ساعت هوشمند سامسونگ Galaxy Watch 6", "ساعت هوشمند", 17_000_000, 14_700_000, 14, 18),
    ("WCH-003", "مچ‌بند هوشمند شیائومی Smart Band 8", "ساعت هوشمند", 1_450_000, 1_050_000, 45, 65),
    # کنسول بازی
    ("GAM-001", "کنسول بازی سونی PlayStation 5 Slim", "کنسول بازی", 38_000_000, 34_000_000, 8, 12),
    ("GAM-002", "دسته بازی سونی DualSense", "کنسول بازی", 4_200_000, 3_500_000, 22, 30),
    # لوازم جانبی
    ("ACC-001", "پاوربانک انکر ۲۰۰۰۰ میلی‌آمپرساعت", "لوازم جانبی", 2_300_000, 1_800_000, 50, 80),
    ("ACC-002", "شارژر دیواری فست‌شارژ ۳۳ وات", "لوازم جانبی", 650_000, 430_000, 70, 100),
    ("ACC-003", "کابل شارژ Type-C به Type-C یک متری", "لوازم جانبی", 320_000, 190_000, 90, 120),
    ("ACC-004", "گلس محافظ صفحه‌نمایش فول‌چسب", "لوازم جانبی", 180_000, 90_000, 120, 160),
    ("ACC-005", "قاب محافظ گوشی سیلیکونی", "لوازم جانبی", 250_000, 130_000, 100, 140),
    ("ACC-006", "فلش مموری سن‌دیسک ۱۲۸ گیگابایت", "لوازم جانبی", 1_100_000, 820_000, 45, 60),
    ("ACC-007", "کارت حافظه microSD سن‌دیسک ۲۵۶ گیگابایت", "لوازم جانبی", 2_050_000, 1_650_000, 40, 55),
    # لوازم خانگی
    ("HOM-001", "جاروبرقی رباتیک شیائومی Robot Vacuum S10", "لوازم خانگی", 15_800_000, 13_500_000, 10, 12),
    ("HOM-002", "مایکروویو ال‌جی ۳۰ لیتری", "لوازم خانگی", 18_500_000, 16_000_000, 8, 10),
    ("HOM-003", "اتو بخار فیلیپس سری ۵۰۰۰", "لوازم خانگی", 3_400_000, 2_700_000, 20, 26),
    ("HOM-004", "آبمیوه‌گیری پارس‌خزر مدل ۲۲۰۰", "لوازم خانگی", 2_900_000, 2_200_000, 18, 22),
    # تلویزیون
    ("TV-001", "تلویزیون سامسونگ ۵۵ اینچ Crystal UHD 4K", "تلویزیون", 42_000_000, 37_000_000, 6, 8),
    ("TV-002", "تلویزیون ال‌جی ۶۵ اینچ OLED evo", "تلویزیون", 89_000_000, 80_000_000, 4, 6),
]

# مشتریان: مخلوطی از خریدارانِ حقیقی و کسب‌وکارها
SAMPLE_CUSTOMERS = [
    ("علی رضایی", "09121002030"),
    ("مریم حسینی", "09123004050"),
    ("حسین محمدی", "09354006070"),
    ("زهرا کریمی", "09197008090"),
    ("رضا اکبری", "09361009010"),
    ("فاطمه صادقی", "09129001122"),
    ("محمد نوری", "09372003344"),
    ("سارا جعفری", "09195005566"),
    ("فروشگاه موبایل ایران", "021-88770011"),
    ("شرکت پخش الکترونیک آسیا", "021-88990022"),
    ("مجتمع تجاری پایتخت", "021-77660033"),
    ("فروشگاه دیجیتال شهر", "031-36660044"),
    ("شرکت تجهیزات اداری نگین", "021-44550055"),
    ("فروشگاه لوازم خانگی مرکزی", "051-38880066"),
]

# تأمین‌کنندگان
SAMPLE_SUPPLIERS = [
    "واردکننده موبایل خاورمیانه",
    "پخش لوازم جانبی پارسیان",
    "نمایندگی رسمی سامسونگ ایران",
    "تأمین‌کننده محصولات اپل",
    "بازرگانی لوازم خانگی البرز",
    "پخش قطعات دیجیتال تهران",
]

# پرسنل: (نام, نام‌خانوادگی, کدملی, سمت, حقوق پایه‌ی ماهانه, تلفن, روزهای‌پیش‌از استخدام)
SAMPLE_EMPLOYEES = [
    ("علی", "رضوانی", "0079542158", "مدیر فروش", 32_000_000, "09121110022", 540),
    ("نگار", "موسوی", "0068741239", "حسابدار", 26_000_000, "09122220033", 420),
    ("امیر", "تهرانی", "0451236987", "انباردار", 18_000_000, "09123330044", 300),
    ("سمیرا", "عباسی", "0025874136", "کارشناس پشتیبانی", 17_000_000, "09124440055", 210),
]


def _persisted_sales_count(tenant_id) -> int:
    """شمارش از یک نشستِ *تازه* — اثبات می‌کند داده واقعاً commit شده، نه فقط داخلِ
    تراکنشِ همین اسکریپت. (اگر روزی خطِ commit برداشته شود، این گارد آن را می‌گیرد.)"""
    check = SessionLocal()
    try:
        apply_tenant_to_transaction(check, tenant_id)
        bind_session_tenant(check, tenant_id)
        return check.query(SalesInvoice).count()
    finally:
        check.close()


def seed_demo() -> None:
    if not DEMO_OWNER_PASSWORD or not DEMO_LOGIN_PASSWORD:
        sys.exit(
            "DEMO_OWNER_PASSWORD و DEMO_LOGIN_PASSWORD باید در محیط تنظیم شوند.\n"
            'مثال: DEMO_OWNER_PASSWORD="..." DEMO_LOGIN_PASSWORD="..." python -m app.seed_demo'
        )

    # چارت حساب، انبارها (MAIN/ONLINE)، نقش‌ها (از جمله «دمو»)، پلن‌ها — مثل نصب واقعی
    seed(DEMO_OWNER_EMAIL, DEMO_OWNER_PASSWORD, owner_name="مدیر فروشگاه")

    db = SessionLocal()
    rng = random.Random(1404)
    today = date.today()

    def d(days_ago: int) -> date:
        return today - timedelta(days=days_ago)

    try:
        tenant = db.query(Tenant).filter(Tenant.slug == DEMO_TENANT_SLUG).first()
        if tenant is None:
            sys.exit(f"مستأجر «{DEMO_TENANT_SLUG}» ساخته نشد؛ seed اولیه شکست خورده است.")
        apply_tenant_to_transaction(db, tenant.id)
        bind_session_tenant(db, tenant.id)

        # نامِ فروشگاه را واقع‌گرایانه کن (در هدرِ برنامه دیده می‌شود)
        tenant.name = STORE_NAME

        owner = db.query(User).filter(User.email == DEMO_OWNER_EMAIL).first()
        demo_role = db.query(Role).filter(Role.key == "demo", Role.tenant_id == tenant.id).first()

        def acc(code: str) -> Account:
            return db.query(Account).filter(Account.code == code, Account.tenant_id == tenant.id).one()

        main_wh = db.query(Warehouse).filter(Warehouse.code == "MAIN").first()
        online_wh = db.query(Warehouse).filter(Warehouse.code == "ONLINE").first()
        bank_account = db.query(BankAccount).filter(BankAccount.tenant_id == tenant.id).first()

        # کاربرِ دموِ فقط‌خواندنی (روی سایت تجاری نمایش داده می‌شود)
        demo_user = db.query(User).filter(User.email == DEMO_LOGIN_EMAIL).first()
        if demo_user is None:
            demo_user = User(
                name="کاربر دمو",
                email=DEMO_LOGIN_EMAIL,
                hashed_password=hash_password(DEMO_LOGIN_PASSWORD),
            )
            db.add(demo_user)
            db.flush()
        if not db.query(Membership).filter(
            Membership.user_id == demo_user.id, Membership.tenant_id == tenant.id
        ).first():
            db.add(Membership(user_id=demo_user.id, tenant_id=tenant.id, role_id=demo_role.id, status="active"))

        # اگر قبلاً پر شده، دوباره پر نکن (idempotent)
        if db.query(JournalEntry).filter(JournalEntry.description == OPENING_MARKER).first():
            db.commit()
            print("داده‌ی دموِ دیجی‌مارکت قبلاً ثبت شده؛ فقط نام/کاربر به‌روزرسانی شد.")
            return

        # ── مشتریان و تأمین‌کنندگان ──────────────────────────────────────────
        customers: list[Contact] = []
        for name, phone in SAMPLE_CUSTOMERS:
            c = Contact(name=name, type="customer", phone=phone)
            db.add(c)
            customers.append(c)
        suppliers: list[Contact] = []
        for name in SAMPLE_SUPPLIERS:
            s = Contact(name=name, type="supplier", phone="021-66000000")
            db.add(s)
            suppliers.append(s)

        # ── کالاها ───────────────────────────────────────────────────────────
        items: list[Item] = []
        meta: dict = {}  # item -> (cost, qmain, qonline)
        for sku, name, category, price, cost, qmain, qonline in SAMPLE_ITEMS:
            it = Item(sku=sku, name=name, category=category, unit="عدد", sales_price=price)
            db.add(it)
            items.append(it)
            meta[sku] = (Decimal(cost), qmain, qonline)
        db.flush()

        # ── سند افتتاحیه: سرمایه به صندوق و بانک ──────────────────────────────
        make_journal_entry(
            db,
            d(120),
            OPENING_MARKER,
            "manual",
            owner,
            [
                JournalLine(account_id=acc("1101").id, debit=300_000_000, credit=0, description="موجودی صندوق اولیه"),
                JournalLine(account_id=acc("1102").id, debit=1_200_000_000, credit=0, description="موجودی بانک اولیه"),
                JournalLine(account_id=acc("3101").id, debit=0, credit=1_500_000_000, description="سرمایه‌گذاری اولیه"),
            ],
        )
        db.commit()

        # ── خریدهای اولیه (ورود موجودی به هر دو انبار) ────────────────────────
        stock: dict[tuple, Decimal] = {}
        chunks = [items[i::4] for i in range(4)]  # ۴ گروهِ کالا، هر گروه از یک تأمین‌کننده
        for g, chunk in enumerate(chunks):
            supplier = suppliers[g % len(suppliers)]
            for wh, qty_idx, day in ((main_wh, 1, 116 - g), (online_wh, 2, 113 - g)):
                lines = []
                for it in chunk:
                    cost, qmain, qonline = meta[it.sku]
                    qty = qmain if qty_idx == 1 else qonline
                    if qty <= 0:
                        continue
                    lines.append(PurchaseInvoiceLineIn(item_id=it.id, qty=qty, unit_cost=cost, description=""))
                    stock[(wh.id, it.id)] = stock.get((wh.id, it.id), Decimal(0)) + qty
                if not lines:
                    continue
                post_purchase_invoice(
                    db,
                    PurchaseInvoiceIn(
                        invoice_date=d(day),
                        warehouse_id=wh.id,
                        contact_id=supplier.id,
                        description=f"خرید کالا از {supplier.name} — انبار {wh.name}",
                        lines=lines,
                        tax_rate=Decimal(0),
                    ),
                    owner,
                )
        db.commit()

        # ── ماه‌ها فروش (ترکیب حضوری/انبار مرکزی و آنلاین) ─────────────────────
        n_sales = 52
        for _ in range(n_sales):
            days_ago = rng.randint(2, 100)
            wh = online_wh if rng.random() < 0.62 else main_wh
            customer = rng.choice(customers)
            picks = rng.sample(items, rng.choice([1, 1, 2, 2, 3]))
            lines = []
            for it in picks:
                available = stock.get((wh.id, it.id), Decimal(0))
                if available <= 0:
                    continue
                want = Decimal(rng.choice([1, 1, 1, 2, 2, 3]))
                qty = min(want, available)
                price = Decimal(it.sales_price)
                # گاهی تخفیفِ کوچک (۵٪) روی ردیف
                discount = (price * qty * Decimal("0.05")).quantize(Decimal(1)) if rng.random() < 0.25 else Decimal(0)
                lines.append(SalesInvoiceLineIn(item_id=it.id, qty=qty, unit_price=price, discount=discount))
                stock[(wh.id, it.id)] = available - qty
            if not lines:
                continue
            tax = Decimal(10) if rng.random() < 0.5 else Decimal(0)
            channel = "آنلاین" if wh is online_wh else "حضوری"
            post_sales_invoice(
                db,
                SalesInvoiceIn(
                    invoice_date=d(days_ago),
                    warehouse_id=wh.id,
                    contact_id=customer.id,
                    description=f"فروش {channel} به {customer.name}",
                    lines=lines,
                    tax_rate=tax,
                ),
                owner,
            )
        db.commit()

        # ── دریافت/پرداختِ بانکی (تسویه‌ی بخشی از مشتریان و تأمین‌کنندگان) ─────
        for days_ago, amount in ((70, 180_000_000), (45, 240_000_000), (20, 150_000_000)):
            create_bank_transaction(
                db,
                BankDepositWithdrawIn(
                    bank_account_id=bank_account.id,
                    transaction_date=d(days_ago),
                    amount=Decimal(amount),
                    counter_account_id=acc("1104").id,
                    description="دریافت از مشتری بابت تسویه‌ی حساب",
                ),
                owner,
            )
        for days_ago, amount in ((60, 320_000_000), (30, 210_000_000)):
            create_bank_transaction(
                db,
                BankDepositWithdrawIn(
                    bank_account_id=bank_account.id,
                    transaction_date=d(days_ago),
                    amount=Decimal(-amount),
                    counter_account_id=acc("2101").id,
                    description="پرداخت به تأمین‌کننده بابت خرید کالا",
                ),
                owner,
            )
        db.commit()

        # ── چک‌های دریافتنی و پرداختنی ────────────────────────────────────────
        recv_checks = [
            ("11/524478", "بانک ملت", 95_000_000, 80, 15),
            ("22/998120", "بانک صادرات", 140_000_000, 55, 8),
            ("33/447701", "بانک ملی", 62_000_000, 40, 25),
        ]
        for i, (number, bank_name, amount, issue_ago, due_ahead) in enumerate(recv_checks):
            create_check(
                db,
                CheckIn(
                    type="receivable",
                    number=number,
                    bank_name=bank_name,
                    amount=Decimal(amount),
                    issue_date=d(issue_ago),
                    due_date=today + timedelta(days=due_ahead),
                    contact_id=customers[i].id,
                    description="چک دریافتی بابت فروش کالا",
                ),
                owner,
            )
        pay_checks = [
            ("44/300215", "بانک تجارت", 220_000_000, 50, 10),
            ("55/771904", "بانک پاسارگاد", 180_000_000, 35, 20),
        ]
        for i, (number, bank_name, amount, issue_ago, due_ahead) in enumerate(pay_checks):
            create_check(
                db,
                CheckIn(
                    type="payable",
                    number=number,
                    bank_name=bank_name,
                    amount=Decimal(amount),
                    issue_date=d(issue_ago),
                    due_date=today + timedelta(days=due_ahead),
                    contact_id=suppliers[i].id,
                    description="چک پرداختی بابت خرید کالا",
                ),
                owner,
            )
        db.commit()

        # ── هزینه‌های ماهانه (اجاره، عمومی/اداری، حقوق) ───────────────────────
        for month_ago in (3, 2, 1):
            day = month_ago * 30
            make_journal_entry(
                db, d(day), f"هزینه اجاره فروشگاه و انبار — ماه {month_ago}", "manual", owner,
                [
                    JournalLine(account_id=acc("5103").id, debit=55_000_000, credit=0, description="اجاره ماهانه"),
                    JournalLine(account_id=acc("1102").id, debit=0, credit=55_000_000, description="پرداخت از بانک"),
                ],
            )
            make_journal_entry(
                db, d(day - 2), f"هزینه‌های عمومی و اداری — ماه {month_ago}", "manual", owner,
                [
                    JournalLine(account_id=acc("5104").id, debit=12_000_000, credit=0, description="آب/برق/اینترنت/بسته‌بندی"),
                    JournalLine(account_id=acc("1101").id, debit=0, credit=12_000_000, description="پرداخت نقدی"),
                ],
            )
            make_journal_entry(
                db, d(day - 3), f"هزینه حقوق و دستمزد کارکنان — ماه {month_ago}", "manual", owner,
                [
                    JournalLine(account_id=acc("5102").id, debit=93_000_000, credit=0, description="حقوق ماهانه‌ی پرسنل"),
                    JournalLine(account_id=acc("1102").id, debit=0, credit=93_000_000, description="پرداخت حقوق از بانک"),
                ],
            )
        db.commit()

        # ── پرسنل و احکام حقوقی (پرونده‌ی پرسنلیِ ماژول حقوق) ──────────────────
        for first, last, national_id, _title, base_salary, phone, hire_ago in SAMPLE_EMPLOYEES:
            emp = Employee(
                tenant_id=tenant.id,
                first_name=first,
                last_name=last,
                national_id=national_id,
                phone=phone,
                hire_date=d(hire_ago),
                is_active=True,
            )
            db.add(emp)
            db.flush()
            db.add(
                SalaryContract(
                    tenant_id=tenant.id,
                    employee_id=emp.id,
                    effective_from=d(hire_ago),
                    base_salary=base_salary,
                    housing_allowance=9_000_000,
                    food_allowance=6_000_000,
                    other_allowance=0,
                )
            )
        db.commit()

        sales_count = _persisted_sales_count(tenant.id)
        if sales_count < 20:
            sys.exit(f"انتظار حداقل ۲۰ فاکتور فروش بود ولی {sales_count} تا ماندگار شد — داده‌ی دمو ناقص است.")

        print(f"دموِ «{STORE_NAME}» کامل شد.")
        print(f"  کالا: {len(items)} | مشتری: {len(customers)} | تأمین‌کننده: {len(suppliers)} | پرسنل: {len(SAMPLE_EMPLOYEES)}")
        print(f"  فاکتور فروشِ ماندگار: {sales_count}")
        print(f"  ورودِ دمو (فقط‌خواندنی): {DEMO_LOGIN_EMAIL} / {DEMO_LOGIN_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo()
    sys.exit(0)
