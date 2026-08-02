"""داشبورد فروش — سطل‌بندیِ شمسیِ ماهانه، پرفروش‌ترین کالاها و بهترین مشتریان."""
from datetime import date
from decimal import Decimal

from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.schemas.returns import SalesReturnIn, SalesReturnLineIn
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.printing import gregorian_to_jalali
from app.services.reports import get_sales_dashboard
from app.services.returns import post_sales_return
from tests.factories import main_warehouse, make_contact, make_item

TODAY = date.today()


def _stock_in(db, user, item, wh, qty, unit_cost):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost))],
        ),
        user,
    )


def _sell(db, user, wh, item, contact, qty, price, discount=0):
    return post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            contact_id=contact.id if contact else None,
            lines=[
                SalesInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_price=Decimal(price), discount=Decimal(discount))
            ],
        ),
        user,
    )


def test_current_month_sales_land_in_last_bucket(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 100, 200_000)
    _sell(db, user, wh, item, None, 3, 1_000_000)

    dash = get_sales_dashboard(db, months=12)
    assert len(dash["monthly"]) == 12
    last = dash["monthly"][-1]
    cy, cm, _ = gregorian_to_jalali(TODAY)
    assert (last["jy"], last["jm"]) == (cy, cm)  # آخرین سطل = ماه جاری شمسی
    assert last["sales"] == Decimal(3_000_000)


def test_top_items_ranked_by_after_discount_revenue(db, user):
    wh = main_warehouse(db)
    cheap = make_item(db, name="کالای ارزان")
    pricey = make_item(db, name="کالای گران")
    _stock_in(db, user, cheap, wh, 100, 100_000)
    _stock_in(db, user, pricey, wh, 100, 100_000)

    _sell(db, user, wh, cheap, None, 2, 500_000)  # درآمد ۱٬۰۰۰٬۰۰۰
    _sell(db, user, wh, pricey, None, 2, 2_000_000, discount=500_000)  # درآمد ۳٬۵۰۰٬۰۰۰

    dash = get_sales_dashboard(db, months=12)
    names = [r["name"] for r in dash["top_items"]]
    assert names[0] == "کالای گران"  # درآمدِ پس از تخفیفِ بیشتر، رتبه‌ی اول
    top = dash["top_items"][0]
    assert top["revenue"] == Decimal(3_500_000)


def test_top_customers_ranked_by_sales(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 100, 200_000)
    big = make_contact(db, name="مشتری بزرگ")
    small = make_contact(db, name="مشتری کوچک")
    _sell(db, user, wh, item, big, 5, 1_000_000)
    _sell(db, user, wh, item, small, 1, 1_000_000)

    dash = get_sales_dashboard(db, months=12)
    assert dash["top_customers"][0]["name"] == "مشتری بزرگ"
    assert dash["top_customers"][0]["total"] == Decimal(5_000_000)


def _return(db, user, inv, item, qty):
    return post_sales_return(
        db,
        SalesReturnIn(
            return_date=TODAY,
            sales_invoice_id=inv.id,
            lines=[SalesReturnLineIn(item_id=item.id, qty=Decimal(qty))],
        ),
        user,
    )


def test_returns_reduce_net_sales(db, user):
    """داشبورد باید فروشِ **خالص** (منهای برگشت) را نشان دهد، نه ناخالص."""
    wh = main_warehouse(db)
    item = make_item(db)
    cust = make_contact(db, name="مشتری")
    _stock_in(db, user, item, wh, 100, 200_000)
    inv = _sell(db, user, wh, item, cust, 3, 1_000_000)  # فروش ۳٬۰۰۰٬۰۰۰
    _return(db, user, inv, item, 1)  # برگشتِ ۱٬۰۰۰٬۰۰۰ → خالص ۲٬۰۰۰٬۰۰۰

    dash = get_sales_dashboard(db, months=12)
    assert dash["monthly"][-1]["sales"] == Decimal(2_000_000)
    assert dash["top_items"][0]["revenue"] == Decimal(2_000_000)
    assert dash["top_items"][0]["qty"] == Decimal(2)
    assert dash["top_customers"][0]["total"] == Decimal(2_000_000)


def test_voided_invoice_excluded(db, user):
    from app.services.voiding import void_sales_invoice

    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 100, 200_000)
    inv = _sell(db, user, wh, item, None, 2, 1_000_000)
    void_sales_invoice(db, inv.id, reason="اشتباه", user=user)

    dash = get_sales_dashboard(db, months=12)
    assert dash["monthly"][-1]["sales"] == Decimal(0)
    assert dash["top_items"] == []
