"""ابطالِ خروجِ انبار نباید میانگینِ بهای تمام‌شده را منحرف کند.

از وقتی حرکتِ انبارِ فروش از خودِ فاکتور به سندِ مستقلِ «خروج انبار» منتقل شد،
`WarehouseIssue` یک سندِ ابطال‌پذیرِ **مالکِ حرکتِ انبار** است. اگر
`voiding._voided_sources` نشناسدش، ردیفِ جبرانیِ `void` در بازپخش نادیده گرفته
می‌شود ولی **خودِ حرکتِ اصلی شمرده می‌شود** — و مقدارِ پایه‌ی میانگین غلط می‌ماند.

خطا در لحظه دیده نمی‌شود: محاسبه‌ی افزایشی درست است. تازه وقتی چیزی
`recompute_average_cost` را صدا بزند — یعنی **ابطالِ هر سندِ دیگری در همان
کسب‌وکار** — عدد می‌پرد. هیچ ترازی هم لو نمی‌دهدش، چون هر دو سند متوازن‌اند.
"""
from datetime import date
from decimal import Decimal

from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
    WarehouseIssueIn,
    WarehouseIssueLineIn,
)
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.voiding import recompute_average_cost
from app.services.warehouse_issues import create_warehouse_issue, void_warehouse_issue
from tests.factories import main_warehouse, make_contact, make_item


def _buy(db, user, item, warehouse, qty, cost):
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(),
            warehouse_id=warehouse.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(cost))],
        ),
        user,
    )


def test_voiding_an_issue_leaves_the_average_where_it_was(db, user):
    warehouse = main_warehouse(db)
    item = make_item(db, name="لیوان")

    _buy(db, user, item, warehouse, 10, 1_000)
    invoice = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=date.today(),
            warehouse_id=warehouse.id,
            contact_id=make_contact(db).id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_price=Decimal(5_000))],
        ),
        user,
        move_inventory=False,
    )
    issue = create_warehouse_issue(
        db,
        invoice.id,
        WarehouseIssueIn(
            issue_date=date.today(),
            warehouse_id=warehouse.id,
            lines=[WarehouseIssueLineIn(sales_invoice_line_id=invoice.lines[0].id, qty=Decimal(10))],
        ),
        user,
    )

    void_warehouse_issue(db, issue.id, reason="اشتباه ثبت شد", user=user)
    _buy(db, user, item, warehouse, 10, 2_000)
    db.refresh(item)
    assert Decimal(item.average_cost) == Decimal(1_500)

    # و مهم‌تر: بازپخش هم باید همان را بدهد. این‌جا بود که عدد به ۲۰۰۰ می‌پرید.
    recompute_average_cost(db, item)
    db.flush()
    db.refresh(item)
    assert Decimal(item.average_cost) == Decimal(1_500)


def test_a_live_issue_still_counts(db, user):
    """قرینه‌اش: خروجی که باطل **نشده** باید در بازپخش شمرده شود."""
    warehouse = main_warehouse(db)
    item = make_item(db, sku="LIVE-1", name="بشقاب")

    _buy(db, user, item, warehouse, 10, 1_000)
    invoice = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=date.today(),
            warehouse_id=warehouse.id,
            contact_id=make_contact(db).id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_price=Decimal(5_000))],
        ),
        user,
        move_inventory=False,
    )
    create_warehouse_issue(
        db,
        invoice.id,
        WarehouseIssueIn(
            issue_date=date.today(),
            warehouse_id=warehouse.id,
            lines=[WarehouseIssueLineIn(sales_invoice_line_id=invoice.lines[0].id, qty=Decimal(10))],
        ),
        user,
    )
    _buy(db, user, item, warehouse, 10, 2_000)

    recompute_average_cost(db, item)
    db.flush()
    db.refresh(item)
    # موجودی صفر شده بود، پس خریدِ تازه میانگین را کاملاً تعیین می‌کند.
    assert Decimal(item.average_cost) == Decimal(2_000)
