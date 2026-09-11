from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.advanced_inventory import StockBatch
from app.models.inventory import StockLedger
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    WarehouseReceiptIn,
    WarehouseReceiptLineIn,
)
from app.services.inventory import post_purchase_invoice
from app.services.warehouse_receipts import create_warehouse_receipt, received_by_line, void_warehouse_receipt
from tests.factories import main_warehouse, make_contact, make_item


def test_purchase_without_warehouse_has_no_physical_stock_and_accepts_partial_receipts(db, user):
    item = make_item(db, name="کالای تحویل جزئی")
    supplier = make_contact(db, type_="supplier")
    warehouse = main_warehouse(db)
    invoice = post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(),
            contact_id=supplier.id,
            supplier_invoice_number="SUP-42",
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(1000))],
        ),
        user,
    )
    line = invoice.lines[0]
    assert invoice.warehouse_id is None
    assert db.query(StockLedger).filter(StockLedger.item_id == item.id).count() == 0

    first = create_warehouse_receipt(
        db,
        invoice.id,
        WarehouseReceiptIn(
            receipt_date=date.today(),
            warehouse_id=warehouse.id,
            lines=[WarehouseReceiptLineIn(purchase_invoice_line_id=line.id, qty=Decimal(4))],
        ),
        user,
    )
    assert first.number == 1
    assert received_by_line(db, invoice.id)[line.id] == Decimal(4)

    create_warehouse_receipt(
        db,
        invoice.id,
        WarehouseReceiptIn(
            receipt_date=date.today(),
            warehouse_id=warehouse.id,
            lines=[WarehouseReceiptLineIn(purchase_invoice_line_id=line.id, qty=Decimal(6))],
        ),
        user,
    )
    assert received_by_line(db, invoice.id)[line.id] == Decimal(10)
    assert db.query(StockLedger).filter(StockLedger.source_type == "warehouse_receipt").count() == 2

    with pytest.raises(HTTPException) as error:
        create_warehouse_receipt(
            db,
            invoice.id,
            WarehouseReceiptIn(
                receipt_date=date.today(),
                warehouse_id=warehouse.id,
                lines=[WarehouseReceiptLineIn(purchase_invoice_line_id=line.id, qty=Decimal(1))],
            ),
            user,
        )
    assert error.value.status_code == 409


def test_void_warehouse_receipt_reverses_stock_batch_and_reopens_remaining(db, user):
    item = make_item(db, name="کالای رسید باطل‌شونده")
    supplier = make_contact(db, type_="supplier")
    warehouse = main_warehouse(db)
    invoice = post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(),
            contact_id=supplier.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(5), unit_cost=Decimal(1200))],
        ),
        user,
    )
    line = invoice.lines[0]
    receipt = create_warehouse_receipt(
        db,
        invoice.id,
        WarehouseReceiptIn(
            receipt_date=date.today(),
            warehouse_id=warehouse.id,
            lines=[WarehouseReceiptLineIn(purchase_invoice_line_id=line.id, qty=Decimal(5))],
        ),
        user,
    )
    batch = db.query(StockBatch).filter(StockBatch.source_id == receipt.id).one()
    assert Decimal(batch.qty) == Decimal(5)
    assert Decimal(batch.received_qty) == Decimal(5)

    void_warehouse_receipt(db, receipt.id, reason="رسید اشتباه", user=user)

    assert received_by_line(db, invoice.id).get(line.id, Decimal(0)) == Decimal(0)
    assert sum(
        Decimal(qty)
        for (qty,) in db.query(StockLedger.qty).filter(
            StockLedger.item_id == item.id, StockLedger.warehouse_id == warehouse.id
        )
    ) == Decimal(0)
    assert Decimal(batch.qty) == Decimal(0)
    assert Decimal(batch.received_qty) == Decimal(5)

    replacement = create_warehouse_receipt(
        db,
        invoice.id,
        WarehouseReceiptIn(
            receipt_date=date.today(),
            warehouse_id=warehouse.id,
            lines=[WarehouseReceiptLineIn(purchase_invoice_line_id=line.id, qty=Decimal(5))],
        ),
        user,
    )
    assert replacement.id != receipt.id
    assert received_by_line(db, invoice.id)[line.id] == Decimal(5)


def test_warehouse_receipt_retry_does_not_move_stock_twice(client, db, user):
    item = make_item(db, name="کالای retry رسید")
    supplier = make_contact(db, type_="supplier")
    warehouse = main_warehouse(db)
    invoice = post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(),
            contact_id=supplier.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(3), unit_cost=Decimal(900))],
        ),
        user,
    )
    body = {
        "receipt_date": date.today().isoformat(),
        "warehouse_id": str(warehouse.id),
        "lines": [{"purchase_invoice_line_id": str(invoice.lines[0].id), "qty": 3}],
    }
    headers = {"Idempotency-Key": "warehouse-receipt-retry"}

    first = client.post(f"/api/purchase-invoices/{invoice.id}/warehouse-receipts", json=body, headers=headers)
    second = client.post(f"/api/purchase-invoices/{invoice.id}/warehouse-receipts", json=body, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert db.query(StockLedger).filter(
        StockLedger.source_type == "warehouse_receipt", StockLedger.source_id == first.json()["id"]
    ).count() == 1


def test_purchase_print_uses_transaction_time_supplier_identity(client, db, user):
    item = make_item(db, name="کالای چاپ تاریخی")
    supplier = make_contact(db, type_="supplier", name="فروشنده تاریخی")
    supplier.phone = "021-11111111"
    supplier.address = "نشانی زمان ثبت"
    supplier.national_id = "10101010101"
    db.flush()

    invoice = post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(),
            contact_id=supplier.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_cost=Decimal(5000))],
        ),
        user,
    )
    assert invoice.supplier_snapshot["name"] == "فروشنده تاریخی"

    supplier.name = "نام تازه فروشنده"
    supplier.phone = "021-99999999"
    supplier.address = "نشانی تازه"
    db.flush()

    html = client.get(f"/api/purchase-invoices/{invoice.id}/print").text
    assert "فروشنده تاریخی" in html
    assert "نشانی زمان ثبت" in html
    assert "10101010101" in html
    assert "نام تازه فروشنده" not in html
    assert "نشانی تازه" not in html

    pdf = client.get(f"/api/purchase-invoices/{invoice.id}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


def test_purchase_duplicate_is_a_new_draft_without_historical_links(client, db, user):
    item = make_item(db, name="کالای رونوشت")
    supplier = make_contact(db, type_="supplier")
    invoice = post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(),
            contact_id=supplier.id,
            supplier_invoice_number="SUP-UNIQUE-42",
            description="شرح قابل استفاده مجدد",
            description2="شرح دوم",
            tax_rate=Decimal(10),
            invoice_discount=Decimal(100),
            invoice_addition=Decimal(40),
            duty_amount=Decimal(20),
            lines=[
                PurchaseInvoiceLineIn(
                    item_id=item.id,
                    qty=Decimal(2),
                    unit_cost=Decimal(1000),
                    discount=Decimal(50),
                    addition=Decimal(10),
                    duty_amount=Decimal(5),
                )
            ],
        ),
        user,
    )

    before_count = db.query(type(invoice)).count()
    response = client.get(f"/api/purchase-invoices/{invoice.id}/duplicate")

    assert response.status_code == 200
    draft = response.json()
    assert db.query(type(invoice)).count() == before_count
    assert draft["source_invoice_number"] == invoice.number
    assert draft["contact_id"] == str(supplier.id)
    assert draft["description"] == "شرح قابل استفاده مجدد"
    assert draft["description2"] == "شرح دوم"
    assert "supplier_invoice_number" not in draft
    assert "invoice_date" not in draft
    assert "warehouse_id" not in draft
    assert Decimal(draft["invoice_discount"]) == Decimal(0)
    assert Decimal(draft["invoice_addition"]) == Decimal(0)
    assert Decimal(draft["duty_amount"]) == Decimal(0)
    assert Decimal(draft["lines"][0]["discount"]) == Decimal(invoice.lines[0].discount)
    assert Decimal(draft["lines"][0]["addition"]) == Decimal(invoice.lines[0].addition)
    assert Decimal(draft["lines"][0]["duty_amount"]) == Decimal(invoice.lines[0].duty_amount)
    assert "شماره فاکتور تأمین‌کننده" in draft["cleared_fields"]
