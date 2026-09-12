"""تخفیف روی فاکتور — پایه‌ی مالیات، سند حسابداری، ارزش‌گذاری موجودی و برگشت‌ها."""
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.accounting import Account, JournalEntry
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.schemas.returns import SalesReturnIn, SalesReturnLineIn
from app.services import chart_codes as cc
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.reports import get_inventory_report
from app.services.returns import post_sales_return
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 3, 15)


def _stock_in(db, user, item, wh, qty, unit_cost, discount=0):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[
                PurchaseInvoiceLineIn(
                    item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost), discount=Decimal(discount)
                )
            ],
        ),
        user,
    )


def _entry(db, invoice) -> JournalEntry:
    return db.get(JournalEntry, invoice.journal_entry_id)


# --- اعتبارسنجی --------------------------------------------------------------

def test_discount_cannot_exceed_line_amount():
    with pytest.raises(ValidationError):
        SalesInvoiceLineIn(
            item_id="00000000-0000-0000-0000-000000000001",
            qty=Decimal(2),
            unit_price=Decimal(1_000),
            discount=Decimal(2_001),  # بیشتر از ۲٬۰۰۰
        )


def test_negative_discount_rejected():
    with pytest.raises(ValidationError):
        SalesInvoiceLineIn(
            item_id="00000000-0000-0000-0000-000000000001",
            qty=Decimal(1),
            unit_price=Decimal(1_000),
            discount=Decimal(-1),
        )


# --- فروش --------------------------------------------------------------------

def test_sales_discount_reduces_net_and_tax_base(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 20, 400_000)

    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(10),
            lines=[
                SalesInvoiceLineIn(
                    item_id=item.id, qty=Decimal(2), unit_price=Decimal(1_000_000), discount=Decimal(200_000)
                )
            ],
        ),
        user,
    )

    assert inv.total_discount == Decimal(200_000)
    assert inv.total_amount == Decimal(1_800_000)  # ۲م منهای تخفیف
    # مالیات روی پایه‌ی پس از تخفیف، نه قبل از آن
    assert inv.tax_amount == Decimal(180_000)


def test_journal_entry_records_gross_revenue_and_discount_separately(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 20, 400_000)

    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(10),
            lines=[
                SalesInvoiceLineIn(
                    item_id=item.id, qty=Decimal(2), unit_price=Decimal(1_000_000), discount=Decimal(200_000)
                )
            ],
        ),
        user,
    )

    entry = _entry(db, inv)
    assert sum(l.debit for l in entry.lines) == sum(l.credit for l in entry.lines)  # متوازن
    revenue = db.query(Account).filter(Account.system_role == cc.SALES_REVENUE).first()
    revenue_lines = [l for l in entry.lines if l.account_id == revenue.id]
    # درآمد ناخالص و تخفیف، دو حقیقت حسابداریِ مستقل‌اند.
    assert revenue_lines[0].credit == Decimal(2_000_000)
    discount = db.query(Account).filter(Account.system_role == cc.SALES_DISCOUNT).one()
    discount_lines = [line for line in entry.lines if line.account_id == discount.id]
    assert discount_lines[0].debit == Decimal(200_000)
    # بدهکارِ دریافتنی/صندوق = خالص + مالیات
    assert max(l.debit for l in entry.lines) == Decimal(1_980_000)


# --- خرید و ارزش‌گذاری موجودی ------------------------------------------------

def test_purchase_discount_lowers_inventory_valuation(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    # ۱۰ عدد × ۱۰۰٬۰۰۰ با تخفیفِ ۲۰۰٬۰۰۰ → خالص ۸۰۰٬۰۰۰ یعنی واحدی ۸۰٬۰۰۰
    inv = _stock_in(db, user, item, wh, 10, 100_000, discount=200_000)

    assert inv.total_discount == Decimal(200_000)
    assert inv.total_amount == Decimal(800_000)

    report = get_inventory_report(db, None, None)
    row = next(r for r in report["rows"] if r["item_id"] == item.id)
    assert row["qty_on_hand"] == Decimal(10)
    assert row["unit_cost"] == Decimal(80_000)  # پس از تخفیف
    assert row["stock_value"] == Decimal(800_000)


# --- برگشت -------------------------------------------------------------------

def test_return_credits_discounted_price_not_list_price(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 20, 400_000)

    sale = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[
                SalesInvoiceLineIn(
                    item_id=item.id, qty=Decimal(2), unit_price=Decimal(1_000_000), discount=Decimal(400_000)
                )
            ],
        ),
        user,
    )
    assert sale.total_amount == Decimal(1_600_000)  # واحدِ مؤثر ۸۰۰٬۰۰۰

    ret = post_sales_return(
        db,
        SalesReturnIn(
            return_date=TODAY,
            sales_invoice_id=sale.id,
            lines=[SalesReturnLineIn(item_id=item.id, qty=Decimal(1))],
        ),
        user,
    )
    # یک عدد از دو عدد → نصفِ مبلغِ پس از تخفیف، نه قیمتِ فهرستِ ۱٬۰۰۰٬۰۰۰
    assert ret.total_amount == Decimal(800_000)


# --- مؤدیان ------------------------------------------------------------------

def test_moadian_packet_carries_real_discount(db, user):
    from app.services import moadian as moadian_svc

    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 20, 400_000)
    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(10),
            lines=[
                SalesInvoiceLineIn(
                    item_id=item.id, qty=Decimal(2), unit_price=Decimal(1_000_000), discount=Decimal(200_000)
                )
            ],
        ),
        user,
    )

    settings = moadian_svc.get_settings(db)
    packet = moadian_svc.build_invoice_packet(inv, settings, "AB12CD00000000000000A1")

    assert packet["header"]["tprdis"] == 2_000_000  # قبل از تخفیف
    assert packet["header"]["tdis"] == 200_000  # تخفیف
    assert packet["header"]["tadis"] == 1_800_000  # پس از تخفیف
    assert packet["body"][0]["dis"] == 200_000
    assert packet["body"][0]["adis"] == 1_800_000


# --- سازگاری با گذشته --------------------------------------------------------

def test_no_discount_behaves_exactly_as_before(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 20, 500_000)
    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(10),
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_price=Decimal(1_000_000))],
        ),
        user,
    )
    assert inv.total_discount == Decimal(0)
    assert inv.total_amount == Decimal(2_000_000)
    assert inv.tax_amount == Decimal(200_000)
