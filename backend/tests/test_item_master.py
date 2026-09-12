"""فصلِ «تعریف کالا و خدمت» — یک شناسنامه، رفتارِ وابسته به نوع.

این فایل سه چیز را می‌سنجد که هیچ‌کدام پیش از این سنجیده نمی‌شدند، و هر سه از
جنسِ خطاهایی‌اند که **تراز را به‌هم نمی‌زنند**:

  ۱. خریدِ خدمت به حسابِ هزینه می‌نشیند، نه به موجودیِ کالا.
  ۲. قلمِ معاف مالیات نمی‌خورد — نه در فروش، نه در خرید، نه در برگشت، نه در
     بسته‌ی مؤدیان.
  ۳. «قابل فروش» و «ثبت سریالی» واقعاً قاعده‌اند، نه برچسب.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account, JournalLine
from app.schemas.inventory import ItemUpdateIn
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.schemas.returns import (
    PurchaseReturnIn,
    PurchaseReturnLineIn,
    SalesReturnIn,
    SalesReturnLineIn,
)
from app.services import chart_codes as cc
from app.services import items as items_svc
from app.services.common import get_account
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.reports import get_income_statement, get_inventory_report
from app.services.returns import post_purchase_return, post_sales_return
from tests.factories import main_warehouse, make_contact, make_item

TODAY = date(2026, 3, 15)


def balance_of_account(db, account_id) -> Decimal:
    rows = (
        db.query(JournalLine.debit, JournalLine.credit)
        .filter(JournalLine.account_id == account_id)
        .all()
    )
    return sum((Decimal(d) - Decimal(c) for d, c in rows), Decimal(0))


class Ledger:
    """عکسِ ماندهٔ حساب‌ها پیش از سناریو، تا **تغییر** سنجیده شود نه ماندهٔ مطلق.

    تست‌های همزمانی عمداً خارج از تراکنشِ تست commit می‌کنند، پس ماندهٔ اولیه‌ی
    پایگاهِ آزمون در اجرای کامل صفر نیست. سنجشِ دلتا هم مقاوم‌تر است و هم دقیقاً
    همان چیزی است که این تست‌ها ادعا می‌کنند: «این سند چه کرد».
    """

    def __init__(self, db):
        self.db = db
        self.before = {}

    def snap(self, key, account_id):
        self.before[key] = balance_of_account(self.db, account_id)
        return account_id

    def delta(self, key, account_id):
        return balance_of_account(self.db, account_id) - self.before[key]


def buy(db, user, item, *, qty=10, unit_cost=5_000_000, tax_rate=0, contact=None):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            contact_id=contact.id if contact else None,
            tax_rate=Decimal(tax_rate),
            lines=[
                PurchaseInvoiceLineIn(
                    item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost)
                )
            ],
        ),
        user,
    )


def stock(db, user, *items, qty=50):
    """کالا باید پیش از فروش موجود باشد — خدمت موجودی نمی‌خواهد."""
    for item in items:
        if not item.is_service:
            buy(db, user, item, qty=qty, unit_cost=1)


def sell(db, user, lines, *, tax_rate=0, contact=None):
    return post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            contact_id=contact.id if contact else None,
            tax_rate=Decimal(tax_rate),
            lines=[
                SalesInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_price=Decimal(price))
                for item, qty, price in lines
            ],
        ),
        user,
    )


# ─────────────────── ۱. خدمت وارد موجودی نمی‌شود (§۱۵ §۱۶) ───────────────────


def test_buying_a_service_never_lands_in_inventory(db, user):
    """نقصِ ریشه‌ای.

    پیش از این کلِ مبلغِ فاکتور بدهکارِ «موجودی کالا» می‌شد — چه کالا بود چه
    خدمت. خدمت حرکتِ انباری نمی‌سازد، پس آن مبلغ دارایی‌ای بود که وجود نداشت و
    هرگز خارج نمی‌شد؛ گزارشِ انبار صفر می‌گفت و هیچ ترازی به‌هم نمی‌خورد.
    """
    service = make_item(db, name="مشاوره حقوقی", is_service=True)
    supplier = make_contact(db, name="دفتر حقوقی", type_="supplier")
    ledger = Ledger(db)
    inventory = ledger.snap("inv", get_account(db, cc.INVENTORY).id)
    before_report = Decimal(get_inventory_report(db, None, as_of=TODAY)["total_value"])

    buy(db, user, service, contact=supplier)

    moved = ledger.delta("inv", inventory)
    report_moved = Decimal(get_inventory_report(db, None, as_of=TODAY)["total_value"]) - before_report
    assert moved == report_moved == Decimal(0), (
        f"خریدِ خدمت دفتر را {moved} و گزارشِ انبار را {report_moved} تکان داد"
    )


def test_buying_a_service_reaches_the_income_statement(db, user):
    """و هزینه واقعاً هزینه می‌شود — پیش از این هرگز به سود و زیان نمی‌رسید."""
    service = make_item(db, name="مشاوره حقوقی", is_service=True)
    ledger = Ledger(db)
    expense = ledger.snap("exp", get_account(db, cc.SERVICE_EXPENSE).id)
    before = Decimal(get_income_statement(db, None, TODAY)["total_expenses"])

    buy(db, user, service, qty=10, unit_cost=5_000_000)

    assert ledger.delta("exp", expense) == Decimal(50_000_000)
    after = Decimal(get_income_statement(db, None, TODAY)["total_expenses"])
    assert after - before == Decimal(50_000_000)


def test_a_service_with_its_own_account_uses_it(db, user):
    """§۱۵ — معینِ اختصاصیِ کالا بر پیش‌فرضِ نقش مقدم است."""
    rent = db.query(Account).filter(Account.code == "5103").one()
    service = make_item(db, name="اجاره انبار", is_service=True, expense_account_id=rent.id)
    ledger = Ledger(db)
    ledger.snap("rent", rent.id)
    inventory = ledger.snap("inv", get_account(db, cc.INVENTORY).id)

    buy(db, user, service, qty=1, unit_cost=80_000_000)

    assert ledger.delta("rent", rent.id) == Decimal(80_000_000)
    assert ledger.delta("inv", inventory) == Decimal(0)


def test_a_product_still_lands_in_the_warehouse_account(db, user):
    """رفتارِ کالا نباید تکان بخورد."""
    product = make_item(db, name="لیوان قرمز")
    ledger = Ledger(db)
    inventory = ledger.snap("inv", get_account(db, cc.INVENTORY).id)
    expense = ledger.snap("exp", get_account(db, cc.SERVICE_EXPENSE).id)

    buy(db, user, product, qty=10, unit_cost=3_000_000)

    assert ledger.delta("inv", inventory) == Decimal(30_000_000)
    assert ledger.delta("exp", expense) == Decimal(0)


def test_one_invoice_can_hold_both_and_they_split(db, user):
    """§۴۷ — هویتِ مشترک یعنی یک جدول، نه یک رفتار."""
    product = make_item(db, name="کاغذ")
    service = make_item(db, name="حمل", is_service=True)
    ledger = Ledger(db)
    inventory = ledger.snap("inv", get_account(db, cc.INVENTORY).id)
    expense = ledger.snap("exp", get_account(db, cc.SERVICE_EXPENSE).id)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[
                PurchaseInvoiceLineIn(
                    item_id=product.id, qty=Decimal(4), unit_cost=Decimal(1_000_000)
                ),
                PurchaseInvoiceLineIn(
                    item_id=service.id, qty=Decimal(1), unit_cost=Decimal(2_000_000)
                ),
            ],
        ),
        user,
    )
    assert ledger.delta("inv", inventory) == Decimal(4_000_000)
    assert ledger.delta("exp", expense) == Decimal(2_000_000)


def test_returning_a_service_purchase_credits_the_expense_account(db, user):
    """برگشت باید قرینه باشد؛ وگرنه موجودیِ دفتری بی‌آنکه کالایی جابه‌جا شود کم می‌شود."""
    service = make_item(db, name="مشاوره", is_service=True)
    supplier = make_contact(db, name="مشاور", type_="supplier")
    ledger = Ledger(db)
    inventory = ledger.snap("inv", get_account(db, cc.INVENTORY).id)
    expense = ledger.snap("exp", get_account(db, cc.SERVICE_EXPENSE).id)
    invoice = buy(db, user, service, qty=4, unit_cost=2_500_000, contact=supplier)

    post_purchase_return(
        db,
        PurchaseReturnIn(
            return_date=TODAY,
            purchase_invoice_id=invoice.id,
            lines=[PurchaseReturnLineIn(item_id=service.id, qty=Decimal(4))],
        ),
        user,
    )
    assert ledger.delta("exp", expense) == Decimal(0)
    assert ledger.delta("inv", inventory) == Decimal(0)


# ───────────────────── ۲. معافیت واقعاً معافیت است (§۱۳) ─────────────────────


def test_an_exempt_line_is_not_taxed_on_sale(db, user):
    """`vat_status` ذخیره و گزارش می‌شد ولی در *محاسبه* هیچ اثری نداشت.

    یعنی گزارشِ ارزش افزوده می‌گفت «فروشِ معاف: X» در حالی که همان فاکتور روی
    X مالیات بسته بود.
    """
    taxable = make_item(db, name="کالای مشمول")
    exempt = make_item(db, name="نان", vat_status="exempt")
    stock(db, user, taxable, exempt)
    invoice = sell(db, user, [(taxable, 1, 1_000_000), (exempt, 1, 1_000_000)], tax_rate=10)
    # فقط ردیفِ مشمول: ۱۰٪ از ۱٬۰۰۰٬۰۰۰
    assert Decimal(invoice.tax_amount) == Decimal(100_000)


def test_an_exempt_line_is_not_taxed_on_purchase(db, user):
    exempt = make_item(db, name="نان", purchase_vat_status="exempt")
    invoice = buy(db, user, exempt, qty=1, unit_cost=1_000_000, tax_rate=10)
    assert Decimal(invoice.tax_amount) == Decimal(0)


def test_purchase_and_sales_exemption_are_independent(db, user):
    """§۱۳ — «وضعیت مالیاتی خرید و فروش الزاماً یکی نیست»."""
    item = make_item(db, name="کالای نیم‌معاف", vat_status="taxable", purchase_vat_status="exempt")
    purchase = buy(db, user, item, qty=10, unit_cost=1_000_000, tax_rate=10)
    assert purchase is not None
    assert Decimal(purchase.tax_amount) == Decimal(0)

    sale = sell(db, user, [(item, 1, 2_000_000)], tax_rate=10)
    assert Decimal(sale.tax_amount) == Decimal(200_000)


def test_the_item_rate_overrides_the_invoice_rate(db, user):
    """§۱۳ — نرخِ کالا مقدم؛ صفر یعنی «نرخِ سرِ فاکتور»، نه معافیت."""
    special = make_item(db, name="کالای نرخ‌ویژه", tax_rate=Decimal(5))
    plain = make_item(db, name="کالای عادی")
    stock(db, user, special, plain)
    invoice = sell(db, user, [(special, 1, 1_000_000), (plain, 1, 1_000_000)], tax_rate=10)
    assert Decimal(invoice.tax_amount) == Decimal(50_000) + Decimal(100_000)


def test_line_tax_snapshots_sum_to_the_invoice_tax(db, user):
    """دفتر و ردیف‌ها نباید از هم جدا بیفتند — بسته‌ی مؤدیان از ردیف می‌خواند."""
    a = make_item(db, name="الف")
    b = make_item(db, name="ب", vat_status="exempt")
    stock(db, user, a, b)
    invoice = sell(db, user, [(a, 3, 333_333), (b, 1, 500_000)], tax_rate=9)

    assert sum((Decimal(line.tax_amount_snapshot) for line in invoice.lines), Decimal(0)) == Decimal(
        invoice.tax_amount
    )
    exempt_line = next(line for line in invoice.lines if line.item_id == b.id)
    assert Decimal(exempt_line.tax_amount_snapshot) == Decimal(0)


def test_changing_the_item_rate_leaves_old_invoices_alone(db, user):
    """§۱۴ — «نرخ مالیات جاری نباید تاریخ گذشته را تغییر دهد»."""
    item = make_item(db, name="کالا", tax_rate=Decimal(5))
    stock(db, user, item)
    invoice = sell(db, user, [(item, 1, 1_000_000)], tax_rate=10)
    before = Decimal(invoice.tax_amount)

    item.tax_rate = Decimal(25)
    db.flush()
    db.refresh(invoice)

    assert Decimal(invoice.tax_amount) == before == Decimal(50_000)
    assert Decimal(invoice.lines[0].tax_rate_snapshot) == Decimal(5)


def test_returning_an_exempt_line_releases_no_tax(db, user):
    """برگشتِ قلمِ معاف نباید مالیاتی را آزاد کند که هرگز بسته نشده بود."""
    exempt = make_item(db, name="نان", vat_status="exempt")
    buy(db, user, exempt, qty=5, unit_cost=100_000)
    customer = make_contact(db, name="مشتری")
    invoice = sell(db, user, [(exempt, 2, 500_000)], tax_rate=10, contact=customer)
    assert Decimal(invoice.tax_amount) == Decimal(0)

    sales_return = post_sales_return(
        db,
        SalesReturnIn(
            return_date=TODAY,
            sales_invoice_id=invoice.id,
            lines=[SalesReturnLineIn(item_id=exempt.id, qty=Decimal(2))],
        ),
        user,
    )
    assert Decimal(sales_return.tax_amount) == Decimal(0)


def test_the_moadian_packet_does_not_tax_an_exempt_line(db, user):
    """بسته‌ی مؤدیان نرخِ سربرگ را به *هر* ردیف می‌زد — قلمِ معاف با مالیات اظهار می‌شد."""
    from app.models.moadian import MoadianSettings
    from app.services.moadian import build_invoice_packet

    taxable = make_item(db, name="مشمول", tax_stuff_id="1" * 13)
    exempt = make_item(db, name="معاف", vat_status="exempt", tax_stuff_id="2" * 13)
    stock(db, user, taxable, exempt)
    invoice = sell(db, user, [(taxable, 1, 1_000_000), (exempt, 1, 1_000_000)], tax_rate=10)

    settings = MoadianSettings(memory_id="A" * 6, economic_code="1" * 11, national_id="")
    packet = build_invoice_packet(invoice, settings, "TAXID", None, {"عدد": "164"})

    by_name = {row["sstt"]: row for row in packet["body"]}
    assert by_name["معاف"]["vam"] == 0
    assert by_name["معاف"]["vra"] == 0
    assert by_name["مشمول"]["vam"] == 100_000
    assert sum(row["vam"] for row in packet["body"]) == packet["header"]["tvam"]


# ────────────────── ۳. پرچم‌ها قاعده‌اند، نه برچسب (§۷ §۹) ──────────────────


def test_a_non_sellable_item_is_refused_in_sales(db, user):
    """§۷ — «هر چیزی که در انبار داریم الزاماً کالای قابل فروش نیست»."""
    raw = make_item(db, name="مواد اولیه", is_sellable=False)
    buy(db, user, raw, qty=10, unit_cost=1_000_000)

    with pytest.raises(HTTPException) as err:
        sell(db, user, [(raw, 1, 2_000_000)])
    assert err.value.status_code == 400
    assert "مواد اولیه" in err.value.detail


def test_a_non_sellable_item_still_moves_through_the_warehouse(db, user):
    """غیرقابل‌فروش یعنی «نمی‌فروشیمش»، نه «کاری با آن نداریم»."""
    raw = make_item(db, name="مواد اولیه", is_sellable=False)
    buy(db, user, raw, qty=10, unit_cost=1_000_000)
    report = get_inventory_report(db, None, as_of=TODAY)
    assert any(row["name"] == "مواد اولیه" for row in report["rows"])


def test_serial_tracking_cannot_be_toggled_after_movement(db, user):
    """§۹ — موجودیِ قدیمی سریال ندارد؛ روشن‌کردنِ این پرچم ردیابی را مبهم می‌کند."""
    item = make_item(db, name="لپ‌تاپ")
    buy(db, user, item, qty=3, unit_cost=200_000_000)

    with pytest.raises(HTTPException) as err:
        items_svc.assert_serial_toggle_allowed(db, item, True)
    assert err.value.status_code == 409


def test_serial_tracking_is_free_before_any_movement(db, user):
    item = make_item(db, name="لپ‌تاپ تازه")
    items_svc.assert_serial_toggle_allowed(db, item, True)  # بدون خطا


# ───────────────────── گاردهای نگاشتِ حساب و شناسه ─────────────────────


def test_an_account_owned_by_another_module_is_refused(db, user):
    """نگاشتِ خدمت به «صندوق» یعنی دو موتور روی یک حساب با دو معنی بنویسند."""
    cash = get_account(db, cc.CASH)
    with pytest.raises(HTTPException) as err:
        items_svc.assert_expense_account(db, cash.id)
    assert err.value.status_code == 400
    assert cash.name in err.value.detail


def test_a_group_account_is_refused(db, user):
    group = db.query(Account).filter(Account.is_group.is_(True), Account.code == "5").one()
    with pytest.raises(HTTPException) as err:
        items_svc.assert_expense_account(db, group.id)
    assert err.value.status_code == 400


def test_the_default_expense_account_is_allowed_explicitly(db, user):
    """انتخابِ صریحِ همان چیزی که خالی‌گذاشتن می‌دهد نباید رد شود."""
    default = items_svc.service_expense_account(db)
    items_svc.assert_expense_account(db, default.id)  # بدون خطا


def test_three_identifiers_stay_separate(db, user):
    """§۴ §۱۱ §۱۲ — کدِ داخلی، بارکد، ایران‌کد و بارکدِ دوبعدی یکی نیستند."""
    item = make_item(
        db,
        sku="1001",
        name="لیوان",
        barcode="6260000000017",
        iran_code="2100123456789",
        barcode2="https://cubita.ir/p/1001",
    )
    assert {item.sku, item.barcode, item.iran_code, item.barcode2} == {
        "1001",
        "6260000000017",
        "2100123456789",
        "https://cubita.ir/p/1001",
    }


def test_the_item_type_cannot_be_changed(db, user):
    """§۵۱ — تبدیلِ کالا به خدمت پس از گردش، تاریخ را غیرمنطقی می‌کند."""
    assert "is_service" not in ItemUpdateIn.model_fields


def test_the_code_can_be_corrected(db, user):
    """§۴ — کد شناسه‌ی کسب‌وکاری است؛ روابطِ داخلی رویش بسته نیستند."""
    assert "sku" in ItemUpdateIn.model_fields
