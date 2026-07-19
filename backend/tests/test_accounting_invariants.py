"""ناوردهای حسابداری — تور ایمنی اصلی این کدبیس.

این فایل عمداً *رفتار یک سرویس خاص* را تست نمی‌کند. یک دنباله‌ی عملیات مالی اجرا
می‌کند و بعد سه چیزی را می‌سنجد که در هیچ حالتی نباید نقض شوند:

  ۱. هر سند حسابداری متوازن است (جمع بدهکار = جمع بستانکار).
  ۲. تراز آزمایشی روی کل حساب‌ها صفر می‌شود.
  ۳. هویت حسابداری برقرار است: دارایی = بدهی + سرمایه + سود دوره.

ارزشش این است که با یک تست، خطای ثبت در هر ۱۳ سرویس گرفته می‌شود و حین بازنویسی
برای multi-tenancy (که هر کوئری را لمس می‌کند) همچنان معنادار می‌ماند.
"""
import random
from datetime import date
from decimal import Decimal

import pytest

from app.models.accounting import Account, JournalLine
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.reports import get_balance_sheet, get_income_statement, get_trial_balance
from tests.factories import main_warehouse, make_contact, make_item

TODAY = date(2026, 3, 15)
# سرمایه نقش سیستمی ندارد چون هیچ ثبت خودکاری رویش نمی‌نویسد؛ فقط اینجا برای
# آورده‌ی اولیه لازم است، پس با کد پیدا می‌شود نه با get_account.
CAPITAL_CODE = "3101"


def inject_capital(db, user, amount: Decimal | int = 500_000_000):
    """آورده‌ی نقدی مالک: بدهکار نقد، بستانکار سرمایه.

    بدون این، حساب‌های سرمایه در تست‌ها مانده‌ی صفر دارند و سنجش هویت حسابداری
    عملاً «۰ = ۰» می‌شود — یعنی اگر علامت مانده‌ی سرمایه غلط محاسبه شود کسی
    متوجه نمی‌شود. این با mutation testing کشف شد.
    """
    amount = Decimal(amount)
    make_journal_entry(
        db,
        TODAY,
        "آورده‌ی نقدی مالک",
        "manual",
        user,
        [
            JournalLine(account_id=get_account(db, cc.CASH).id, debit=amount, credit=0, description="آورده"),
            JournalLine(
                account_id=db.query(Account).filter(Account.code == CAPITAL_CODE).one().id,
                debit=0,
                credit=amount,
                description="آورده",
            ),
        ],
    )
    db.commit()


# --- خود ناوردها -------------------------------------------------------------


def assert_every_entry_balances(db):
    from app.models.accounting import JournalEntry

    entries = db.query(JournalEntry).all()
    assert entries, "هیچ سندی ثبت نشده — تست عملاً چیزی را نسنجیده"
    for entry in entries:
        debit = sum((Decimal(line.debit) for line in entry.lines), Decimal(0))
        credit = sum((Decimal(line.credit) for line in entry.lines), Decimal(0))
        assert debit == credit, f"سند {entry.number} نامتوازن است: بدهکار={debit} بستانکار={credit}"
        assert debit > 0, f"سند {entry.number} مبلغ صفر دارد"


def assert_trial_balance_nets_to_zero(db):
    rows = get_trial_balance(db, None, None)
    total_debit = sum((Decimal(r["total_debit"]) for r in rows), Decimal(0))
    total_credit = sum((Decimal(r["total_credit"]) for r in rows), Decimal(0))
    assert total_debit == total_credit, f"تراز آزمایشی صفر نشد: {total_debit} در برابر {total_credit}"


def assert_accounting_identity(db, as_of=TODAY):
    sheet = get_balance_sheet(db, as_of)
    assets = Decimal(sheet["total_assets"])
    liabilities = Decimal(sheet["total_liabilities"])
    equity = Decimal(sheet["total_equity"])
    profit = Decimal(sheet["current_period_profit"])
    assert assets == liabilities + equity + profit, (
        f"هویت حسابداری نقض شد: دارایی={assets} ≠ "
        f"بدهی={liabilities} + سرمایه={equity} + سود={profit} "
        f"(اختلاف {assets - (liabilities + equity + profit)})"
    )


def assert_equity_and_liabilities_are_exercised(db, as_of=TODAY):
    """نگهبانِ خودِ تست‌ها.

    سنجش هویت حسابداری وقتی سرمایه و بدهی صفرند بی‌معناست. این تأیید می‌کند که
    سناریو واقعاً هر دو طرف معادله را پر کرده، وگرنه تست بی‌سروصدا بی‌اثر می‌شود.
    """
    sheet = get_balance_sheet(db, as_of)
    assert Decimal(sheet["total_equity"]) != 0, "سناریو هیچ مانده‌ی سرمایه‌ای نساخته؛ سنجش هویت بی‌اثر است"
    assert Decimal(sheet["total_liabilities"]) != 0, "سناریو هیچ مانده‌ی بدهی نساخته؛ سنجش هویت بی‌اثر است"


def assert_all_invariants(db, as_of=TODAY):
    assert_every_entry_balances(db)
    assert_trial_balance_nets_to_zero(db)
    assert_equity_and_liabilities_are_exercised(db, as_of)
    assert_accounting_identity(db, as_of)


# --- سناریوهای مشخص ----------------------------------------------------------


def test_invariants_hold_after_cash_purchase_then_cash_sale(db, user):
    wh = main_warehouse(db)
    item = make_item(db, sales_price=5_000_000)
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    inject_capital(db, user)

    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            contact_id=supplier.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(3_000_000))],
        ),
        user,
    )
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(4), unit_price=Decimal(5_000_000))],
        ),
        user,
    )

    assert_all_invariants(db)

    # سود باید دقیقاً (۴ × ۵٬۰۰۰٬۰۰۰) − (۴ × ۳٬۰۰۰٬۰۰۰) باشد
    net = Decimal(get_income_statement(db, None, TODAY)["net_profit"])
    assert net == Decimal(8_000_000), f"سود انتظاری ۸٬۰۰۰٬۰۰۰ بود، {net} شد"


def test_invariants_hold_for_credit_sale_to_contact(db, user):
    """فروش نسیه مسیر حساب دریافتنی را می‌رود نه نقد — هویت باید همچنان برقرار بماند."""
    wh = main_warehouse(db)
    item = make_item(db)
    contact = make_contact(db)
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    inject_capital(db, user)

    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            contact_id=supplier.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(5), unit_cost=Decimal(2_000_000))],
        ),
        user,
    )
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            contact_id=contact.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_price=Decimal(4_000_000))],
        ),
        user,
    )

    assert_all_invariants(db)


def test_invariants_hold_for_service_item_with_no_stock_movement(db, user):
    """کالای خدماتی موجودی و بهای تمام‌شده ندارد؛ سند باید فقط دو ردیفه و متوازن باشد."""
    wh = main_warehouse(db)
    service = make_item(db, name="خدمات نصب", is_service=True)
    stocked = make_item(db, name="کالای انباری")
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    inject_capital(db, user)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            contact_id=supplier.id,
            lines=[PurchaseInvoiceLineIn(item_id=stocked.id, qty=Decimal(1), unit_cost=Decimal(1_000_000))],
        ),
        user,
    )

    invoice = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[SalesInvoiceLineIn(item_id=service.id, qty=Decimal(3), unit_price=Decimal(1_500_000))],
        ),
        user,
    )

    assert Decimal(invoice.total_cost) == 0
    assert_all_invariants(db)


# --- دنباله‌ی تصادفی ---------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_invariants_hold_after_randomized_operation_sequence(db, user, seed):
    """دنباله‌ی تصادفی خرید و فروش.

    هدف پوشش ترکیب‌هایی است که دستی نمی‌نویسیم: چند کالا، چند طرف‌حساب، نقد و نسیه
    درهم، و فروش‌هایی که گاهی همه‌ی موجودی را خالی می‌کنند. هر بذر تکرارپذیر است تا
    شکست قابل بازتولید باشد.
    """
    rng = random.Random(seed)
    wh = main_warehouse(db)
    inject_capital(db, user)
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    items = [make_item(db, sales_price=rng.randrange(1_000_000, 9_000_000, 1_000_000)) for _ in range(4)]
    contacts = [make_contact(db, name=f"مشتری {i}") for i in range(2)]
    on_hand: dict = {item.id: Decimal(0) for item in items}

    for _ in range(25):
        item = rng.choice(items)
        if rng.random() < 0.45 or on_hand[item.id] <= 0:
            qty = Decimal(rng.randint(1, 20))
            post_purchase_invoice(
                db,
                PurchaseInvoiceIn(
                    invoice_date=TODAY,
                    warehouse_id=wh.id,
                    contact_id=supplier.id,  # همیشه نسیه، تا حساب پرداختنی مانده داشته باشد
                    lines=[
                        PurchaseInvoiceLineIn(
                            item_id=item.id,
                            qty=qty,
                            unit_cost=Decimal(rng.randrange(500_000, 4_000_000, 100_000)),
                        )
                    ],
                ),
                user,
            )
            on_hand[item.id] += qty
        else:
            qty = Decimal(rng.randint(1, int(on_hand[item.id])))
            post_sales_invoice(
                db,
                SalesInvoiceIn(
                    invoice_date=TODAY,
                    warehouse_id=wh.id,
                    contact_id=rng.choice(contacts).id if rng.random() < 0.5 else None,
                    lines=[SalesInvoiceLineIn(item_id=item.id, qty=qty, unit_price=Decimal(item.sales_price))],
                ),
                user,
            )
            on_hand[item.id] -= qty

    assert_all_invariants(db)
