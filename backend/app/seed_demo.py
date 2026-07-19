"""داده‌ی نمونه برای دمو وب سایت تجاری cubita.ir — روی یک دیتابیس کاملاً جدا و ایزوله اجرا می‌شود
(هرگز روی دیتابیس واقعی کسب‌وکار اجرا نشود). یک کاربر با نقش «دمو» (فقط‌خواندنی) می‌سازد و چند
فاکتور/سند نمونه ثبت می‌کند تا بازدیدکننده‌ی سایت دموی واقع‌گرایانه‌ای ببیند.

اجرا: python -m app.seed_demo
"""
import os
import sys
from datetime import date, timedelta

from app.database import SessionLocal
from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.inventory import Contact, Item, Warehouse
from app.models.invoices import SalesInvoice
from app.models.tenant import Membership, Tenant
from app.models.user import Role, User
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.security import hash_password
from app.seed import seed
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant

DEMO_TENANT_SLUG = "default"

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


def _count_persisted_invoices(tenant_id) -> int:
    """شمارش از یک نشست *تازه* — و این جزئیات کل نکته‌ی این تابع است.

    شمارش داخل همان نشستی که فاکتورها را ساخته، داده‌ی commit‌نشده‌ی تراکنش خودش را
    هم می‌بیند. یعنی اگر روزی کسی خط commit را بردارد، آن شمارش همچنان ۲ برمی‌گرداند
    و گارد سبز می‌ماند در حالی که پایگاه‌داده خالی است — دقیقاً همان باگی که این گارد
    برای گرفتنش هست. فقط اتصال جدا ثابت می‌کند داده واقعاً ماندگار شده.
    """
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

    # چارت حساب، انبار، نقش‌ها (از جمله «دمو»)، و پلن‌های نمونه — دقیقاً مثل نصب واقعی
    seed(DEMO_OWNER_EMAIL, DEMO_OWNER_PASSWORD, owner_name="مدیر نمونه")

    db = SessionLocal()
    try:
        # زمینه‌ی مستأجر باید قبل از هر کوئری بنشیند. بدون آن، RLS صفر ردیف
        # برمی‌گرداند و اسکریپت با «انبار MAIN پیدا نشد» می‌شکند — خطایی که به
        # نبودِ داده اشاره می‌کند، در حالی که مسئله نبودِ زمینه است.
        tenant = db.query(Tenant).filter(Tenant.slug == DEMO_TENANT_SLUG).first()
        if tenant is None:
            sys.exit(f"مستأجر «{DEMO_TENANT_SLUG}» ساخته نشد؛ seed اولیه شکست خورده است.")
        apply_tenant_to_transaction(db, tenant.id)
        bind_session_tenant(db, tenant.id)

        owner = db.query(User).filter(User.email == DEMO_OWNER_EMAIL).first()
        demo_role = db.query(Role).filter(Role.key == "demo", Role.tenant_id == tenant.id).first()
        warehouse = db.query(Warehouse).filter(Warehouse.code == "MAIN").first()

        # کاربر سراسری است و عضویت چیزی است که او را به این مستأجر و به نقش دمو
        # وصل می‌کند. تا مهاجرت ۰۰۱۵ نقش روی خودِ کاربر بود (`users.role_id`)؛ آن
        # ستون حذف شده و هر کدی که هنوز آن را بنویسد در زمان اجرا می‌شکند.
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
            db.add(
                Membership(
                    user_id=demo_user.id,
                    tenant_id=tenant.id,
                    role_id=demo_role.id,
                    status="active",
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
        cash = get_account(db, cc.CASH)
        # «سرمایه» نقش معنایی ندارد (فقط سود انباشته دارد)، پس با کد پیدا می‌شود.
        # برای یک seeder این درست است چون خودش همین چارت را ساخته و کدهایش را
        # می‌داند؛ چیزی که نباید از کد عبور کند منطقِ ثبت است، نه ساختِ داده‌ی نمونه.
        capital = db.query(Account).filter(Account.code == "3101", Account.tenant_id == tenant.id).one()
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

        # commit اجباری است. تا فاز ۱.۵ هر سرویس خودش commit می‌کرد، و این اسکریپت
        # روی همان حساب باز کرده بود. حالا تصمیم commit در get_db() گرفته می‌شود و
        # این اسکریپت اصلاً از آنجا عبور نمی‌کند — یعنی بدون این خط، هر سه فاکتور
        # ساخته می‌شوند، شماره می‌گیرند، و بعد موقع close بی‌صدا دور ریخته می‌شوند.
        # بدترین بخشش این بود که چاپِ پایین همچنان «کامل شد» می‌گفت.
        db.commit()
        invoices = _count_persisted_invoices(tenant.id)
        if invoices != 2:
            sys.exit(f"انتظار ۲ فاکتور فروش بود ولی {invoices} تا ماندگار شد — داده‌ی دمو ناقص است.")

        print(f"دمو کامل شد. ورود دمو: {DEMO_LOGIN_EMAIL} / {DEMO_LOGIN_PASSWORD}  (نقش: فقط‌خواندنی)")
        print(f"خرید نمونه: {purchase.number} — {invoices} فاکتور فروش ماندگار شد")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo()
    sys.exit(0)
