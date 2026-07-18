"""داده‌ی نمونه برای دمو وب سایت تجاری cubita.ir — روی یک دیتابیس کاملاً جدا و ایزوله اجرا می‌شود
(هرگز روی دیتابیس واقعی کسب‌وکار اجرا نشود). یک کاربر با نقش «دمو» (فقط‌خواندنی) می‌سازد و چند
فاکتور/سند نمونه ثبت می‌کند تا بازدیدکننده‌ی سایت دموی واقع‌گرایانه‌ای ببیند.

اجرا: python -m app.seed_demo
"""
import os
import sys
from datetime import date, timedelta

from app.database import SessionLocal
from app.models.accounting import JournalEntry, JournalLine
from app.models.banking import BankAccount
from app.models.inventory import Contact, Item, Warehouse
from app.models.user import Role, User
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.security import hash_password
from app.seed import seed
from app.services.common import get_account, make_journal_entry
from app.services.inventory import post_purchase_invoice, post_sales_invoice

# رمزها از محیط خوانده می‌شوند و هیچ مقدار پیش‌فرضی ندارند — تا چرخش رمز دمو نیازی به تغییر کد
# نداشته باشد و رمز واقعی هیچ‌وقت داخل مخزن ننشیند. رمز DEMO_LOGIN روی سایت تجاری عمومی نمایش
# داده می‌شود، ولی همچنان باید قابل چرخش باشد بدون build مجدد بک‌اند.
DEMO_OWNER_EMAIL = os.environ.get("DEMO_OWNER_EMAIL", "owner-demo@cubita.ir")
DEMO_OWNER_PASSWORD = os.environ.get("DEMO_OWNER_PASSWORD", "")
DEMO_LOGIN_EMAIL = os.environ.get("DEMO_LOGIN_EMAIL", "demo@cubita.ir")
DEMO_LOGIN_PASSWORD = os.environ.get("DEMO_LOGIN_PASSWORD", "")

SAMPLE_ITEMS = [
    ("CAM-001", "دوربین مداربسته دام ۲ مگاپیکسل", "دوربین", 3_200_000, 2_400_000),
    ("CAM-002", "دوربین بولت ۴ مگاپیکسل", "دوربین", 4_500_000, 3_300_000),
    ("DVR-001", "دستگاه ضبط ۸ کانال", "ضبط‌کننده", 6_800_000, 5_100_000),
    ("CBL-001", "کابل کواکسیال ۱۰۰ متری", "متفرقه", 950_000, 650_000),
    ("HDD-001", "هارد نظارتی ۲ ترابایت", "قطعات", 2_100_000, 1_600_000),
]

SAMPLE_CONTACTS = [
    ("فروشگاه ایمن‌نگار", "customer"),
    ("شرکت پارس حفاظت", "customer"),
    ("تأمین‌کننده الکترونیک مرکزی", "supplier"),
]


def seed_demo() -> None:
    if not DEMO_OWNER_PASSWORD or not DEMO_LOGIN_PASSWORD:
        sys.exit(
            "DEMO_OWNER_PASSWORD و DEMO_LOGIN_PASSWORD باید در محیط تنظیم شوند.\n"
            'مثال: DEMO_OWNER_PASSWORD="..." DEMO_LOGIN_PASSWORD="..." python -m app.seed_demo'
        )

    # چارت حساب، انبار، نقش‌ها (از جمله «دمو»)، و پلن‌های نمونه — دقیقاً مثل نصب واقعی
    seed(DEMO_OWNER_EMAIL, DEMO_OWNER_PASSWORD, owner_name="مدیر نمونه")

    db = SessionLocal()
    try:
        owner = db.query(User).filter(User.email == DEMO_OWNER_EMAIL).first()
        demo_role = db.query(Role).filter(Role.key == "demo").first()
        warehouse = db.query(Warehouse).filter(Warehouse.code == "MAIN").first()

        if not db.query(User).filter(User.email == DEMO_LOGIN_EMAIL).first():
            db.add(
                User(
                    name="کاربر دمو",
                    email=DEMO_LOGIN_EMAIL,
                    hashed_password=hash_password(DEMO_LOGIN_PASSWORD),
                    role_id=demo_role.id,
                )
            )

        contacts_by_name: dict[str, Contact] = {}
        for name, type_ in SAMPLE_CONTACTS:
            contact = db.query(Contact).filter(Contact.name == name).first()
            if contact is None:
                contact = Contact(name=name, type=type_, phone="021-88000000")
                db.add(contact)
                db.flush()
            contacts_by_name[name] = contact

        items_by_sku: dict[str, Item] = {}
        for sku, name, category, sales_price, _cost in SAMPLE_ITEMS:
            item = db.query(Item).filter(Item.sku == sku).first()
            if item is None:
                item = Item(sku=sku, name=name, category=category, unit="عدد", sales_price=sales_price)
                db.add(item)
                db.flush()
            items_by_sku[sku] = item

        db.commit()

        # اگر قبلاً فاکتور نمونه ثبت شده، دوباره ثبت نکن (idempotent بودن اسکریپت)
        already_seeded = (
            db.query(JournalEntry).filter(JournalEntry.description == "دمو: افتتاح حساب صندوق").first()
        )
        if already_seeded:
            print("داده‌ی دمو قبلاً ثبت شده؛ کاری انجام نشد.")
            return

        # سند افتتاحیه: واریز سرمایه به صندوق تا بقیه‌ی تراکنش‌های نمونه معنا داشته باشند
        cash = get_account(db, "1101")
        capital = get_account(db, "3101")
        make_journal_entry(
            db,
            date.today() - timedelta(days=30),
            "دمو: افتتاح حساب صندوق",
            "manual",
            owner,
            [
                JournalLine(account_id=cash.id, debit=50_000_000, credit=0, description="واریز سرمایه اولیه"),
                JournalLine(account_id=capital.id, debit=0, credit=50_000_000, description="سرمایه‌گذاری اولیه"),
            ],
        )
        db.commit()

        # فاکتور خرید نمونه (برای ورود موجودی به انبار)
        purchase = post_purchase_invoice(
            db,
            PurchaseInvoiceIn(
                invoice_date=date.today() - timedelta(days=20),
                warehouse_id=warehouse.id,
                contact_id=contacts_by_name["تأمین‌کننده الکترونیک مرکزی"].id,
                description="دمو: خرید نمونه کالا از تأمین‌کننده",
                lines=[
                    PurchaseInvoiceLineIn(item_id=items_by_sku[sku].id, qty=20, unit_cost=cost, description="")
                    for sku, _name, _cat, _sp, cost in SAMPLE_ITEMS
                ],
            ),
            owner,
        )

        # دو فاکتور فروش نمونه
        post_sales_invoice(
            db,
            SalesInvoiceIn(
                invoice_date=date.today() - timedelta(days=10),
                warehouse_id=warehouse.id,
                contact_id=contacts_by_name["فروشگاه ایمن‌نگار"].id,
                description="دمو: فروش نمونه به فروشگاه ایمن‌نگار",
                lines=[
                    SalesInvoiceLineIn(item_id=items_by_sku["CAM-001"].id, qty=5, unit_price=3_200_000),
                    SalesInvoiceLineIn(item_id=items_by_sku["DVR-001"].id, qty=1, unit_price=6_800_000),
                ],
            ),
            owner,
        )
        post_sales_invoice(
            db,
            SalesInvoiceIn(
                invoice_date=date.today() - timedelta(days=3),
                warehouse_id=warehouse.id,
                contact_id=contacts_by_name["شرکت پارس حفاظت"].id,
                description="دمو: فروش نمونه به شرکت پارس حفاظت",
                lines=[
                    SalesInvoiceLineIn(item_id=items_by_sku["CAM-002"].id, qty=8, unit_price=4_500_000),
                    SalesInvoiceLineIn(item_id=items_by_sku["HDD-001"].id, qty=4, unit_price=2_100_000),
                    SalesInvoiceLineIn(item_id=items_by_sku["CBL-001"].id, qty=10, unit_price=950_000),
                ],
            ),
            owner,
        )

        print(f"دمو کامل شد. ورود دمو: {DEMO_LOGIN_EMAIL} / {DEMO_LOGIN_PASSWORD}  (نقش: فقط‌خواندنی)")
        print(f"خرید نمونه: {purchase.number}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo()
    sys.exit(0)
