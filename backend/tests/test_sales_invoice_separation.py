"""مرزهای فصل فاکتور فروش: حقیقت تجاری، حسابداری، انبار و وصول مستقل‌اند.

این‌ها **سیاستِ «دومرحله‌ای»** را می‌سنجند و صریح انتخابش می‌کنند: پیش‌فرضِ
کسب‌وکار «خودکار» است (فاکتور همان لحظه سند و خروج می‌زند)، چون بیشترِ
کاربران فاکتور و تحویل را یک لحظه دارند. جداسازی برای کسی است که لازمش دارد،
و همین فایل مرزهایش را نگه می‌دارد.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account, JournalEntry
from app.models.inventory import StockLedger
from app.models.invoices import SalesInvoice, WarehouseIssue
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.services import chart_codes as cc
from app.services.inventory import post_purchase_invoice
from app.services.sales_invoices import attach_sales_state
from app.services.warehouse_issues import void_warehouse_issue
from tests.factories import main_warehouse, make_contact, make_item


def _stock(db, user, item, warehouse, qty=10, cost=400):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(),
            warehouse_id=warehouse.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=qty, unit_cost=cost)],
        ),
        user,
    )



def _staged(client):
    """سیاستِ دومرحله‌ای — چیزی که این فایل می‌سنجدش."""
    r = client.patch("/api/sales-invoice-posting", json={"mode": "staged"})
    assert r.status_code == 200, r.text

def test_api_save_has_no_journal_or_stock_then_journal_is_idempotent(client, db, user):
    _staged(client)
    warehouse = main_warehouse(db)
    item = make_item(db, name="کالای فروش مستقل")
    customer = make_contact(db, name="مشتری تاریخی")
    _stock(db, user, item, warehouse)
    before_stock_rows = db.query(StockLedger).count()

    response = client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": date.today().isoformat(),
            "warehouse_id": str(warehouse.id),
            "contact_id": str(customer.id),
            "settlement_terms": "cash",
            "tax_rate": 10,
            "lines": [{
                "item_id": str(item.id), "qty": 2, "unit_price": 1000,
                "discount": 200, "addition": 50, "duty_amount": 20,
            }],
        },
    )

    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["journal_entry_id"] is None
    assert saved["accounting_status"] == "unposted"
    assert saved["fulfillment_status"] == "not_issued"
    assert Decimal(saved["final_amount"]) == Decimal(2050)
    assert db.query(StockLedger).count() == before_stock_rows
    assert db.query(StockLedger).filter(StockLedger.source_type == "sales_invoice").count() == 0

    first = client.post(f"/api/sales-invoices/{saved['id']}/journal")
    second = client.post(f"/api/sales-invoices/{saved['id']}/journal")
    assert first.status_code == second.status_code == 200
    assert first.json()["journal_entry_id"] == second.json()["journal_entry_id"]
    assert db.query(JournalEntry).filter(JournalEntry.source_type == "sales_invoice").count() == 1

    entry = db.get(JournalEntry, first.json()["journal_entry_id"])
    revenue = db.query(Account).filter(Account.system_role == cc.SALES_REVENUE).one()
    discount = db.query(Account).filter(Account.system_role == cc.SALES_DISCOUNT).one()
    assert sum(line.credit for line in entry.lines if line.account_id == revenue.id) == Decimal(2000)
    assert sum(line.debit for line in entry.lines if line.account_id == discount.id) == Decimal(200)
    assert all(line.account.system_role not in {cc.COGS, cc.INVENTORY} for line in entry.lines)


def test_immediate_sale_orchestrates_separate_documents_atomically(client, db, user):
    warehouse = main_warehouse(db)
    item = make_item(db, name="کالای صندوق")
    _stock(db, user, item, warehouse, qty=4, cost=300)

    response = client.post(
        "/api/sales-invoices/immediate",
        headers={"Idempotency-Key": "pos-immediate-sale"},
        json={
            "invoice_date": date.today().isoformat(),
            "warehouse_id": str(warehouse.id),
            "lines": [{"item_id": str(item.id), "qty": 2, "unit_price": 900}],
        },
    )

    assert response.status_code == 201, response.text
    invoice = response.json()
    assert invoice["journal_entry_id"]
    assert invoice["accounting_status"] == "posted"
    assert invoice["fulfillment_status"] == "fully_issued"
    issue = db.query(WarehouseIssue).filter(WarehouseIssue.sales_invoice_id == invoice["id"]).one()
    assert issue.journal_entry_id != invoice["journal_entry_id"]
    assert db.query(StockLedger).filter(
        StockLedger.source_type == "warehouse_issue", StockLedger.source_id == issue.id
    ).count() == 1


def test_partial_warehouse_issue_owns_stock_cogs_and_can_be_voided(client, db, user):
    _staged(client)
    warehouse = main_warehouse(db)
    item = make_item(db, name="کالای خروج جزئی")
    service = make_item(db, name="خدمت بدون خروج", is_service=True)
    _stock(db, user, item, warehouse, qty=5, cost=400)
    sale = client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": date.today().isoformat(),
            "contact_id": None,
            "lines": [
                {"item_id": str(item.id), "qty": 3, "unit_price": 1000},
                {"item_id": str(service.id), "qty": 1, "unit_price": 500},
            ],
        },
    ).json()
    product_line = next(line for line in sale["lines"] if line["item_id"] == str(item.id))
    body = {
        "issue_date": date.today().isoformat(),
        "warehouse_id": str(warehouse.id),
        "lines": [{"sales_invoice_line_id": product_line["id"], "qty": 2}],
    }
    headers = {"Idempotency-Key": "sales-warehouse-issue-retry"}

    first = client.post(
        f"/api/sales-invoices/{sale['id']}/warehouse-issues", json=body, headers=headers
    )
    second = client.post(
        f"/api/sales-invoices/{sale['id']}/warehouse-issues", json=body, headers=headers
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    issue_id = first.json()["id"]
    assert db.query(WarehouseIssue).filter(WarehouseIssue.sales_invoice_id == sale["id"]).count() == 1
    assert db.query(StockLedger).filter(
        StockLedger.source_type == "warehouse_issue", StockLedger.source_id == issue_id
    ).count() == 1
    issue = db.get(WarehouseIssue, issue_id)
    assert db.get(JournalEntry, issue.journal_entry_id).source_type == "warehouse_issue"

    invoice = db.get(SalesInvoice, sale["id"])
    attach_sales_state(db, [invoice])
    assert invoice.fulfillment_status == "partially_issued"
    assert invoice.issued_total_qty == Decimal(2)

    with pytest.raises(HTTPException) as error:
        from app.schemas.invoices import WarehouseIssueIn, WarehouseIssueLineIn
        from app.services.warehouse_issues import create_warehouse_issue

        create_warehouse_issue(
            db, invoice.id,
            WarehouseIssueIn(
                issue_date=date.today(), warehouse_id=warehouse.id,
                lines=[WarehouseIssueLineIn(sales_invoice_line_id=product_line["id"], qty=2)],
            ),
            user,
        )
    assert error.value.status_code == 409

    void_warehouse_issue(db, issue.id, reason="خروج اشتباه", user=user)
    attach_sales_state(db, [invoice])
    assert invoice.fulfillment_status == "not_issued"
    assert invoice.issued_total_qty == Decimal(0)
    assert sum(
        Decimal(qty) for (qty,) in db.query(StockLedger.qty).filter(
            StockLedger.item_id == item.id, StockLedger.warehouse_id == warehouse.id
        )
    ) == Decimal(5)


def test_sales_print_uses_transaction_time_customer_and_item_snapshots(client, db, user):
    _staged(client)
    item = make_item(db, name="کالای تاریخی", sku="HIST-1")
    customer = make_contact(db, name="مشتری زمان ثبت")
    customer.address = "نشانی زمان ثبت"
    db.flush()
    saved = client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": date.today().isoformat(),
            "contact_id": str(customer.id),
            "lines": [{"item_id": str(item.id), "qty": 1, "unit_price": 1000}],
        },
    ).json()

    customer.name = "مشتری تازه"
    customer.address = "نشانی تازه"
    item.name = "کالای تازه"
    db.flush()

    html = client.get(f"/api/sales-invoices/{saved['id']}/print").text
    assert "مشتری زمان ثبت" in html
    assert "نشانی زمان ثبت" in html
    assert "کالای تاریخی" in html
    assert "مشتری تازه" not in html
    assert "نشانی تازه" not in html
    assert "کالای تازه" not in html
