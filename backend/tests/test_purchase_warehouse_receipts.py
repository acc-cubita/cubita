from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.inventory import StockLedger
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    WarehouseReceiptIn,
    WarehouseReceiptLineIn,
)
from app.services.inventory import post_purchase_invoice
from app.services.warehouse_receipts import create_warehouse_receipt, received_by_line
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
