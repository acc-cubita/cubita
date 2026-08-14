"""حذفِ کالا — فقط وقتی در هیچ سند/موجودی رد پا ندارد (DELETE /api/items/{id})."""
import uuid
from datetime import date
from decimal import Decimal

from app.models.inventory import Item
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.services.inventory import post_purchase_invoice
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 3, 15)


def test_delete_unused_item(db, user, client):
    item = make_item(db, name="کالای بی‌استفاده")
    item_id = item.id

    res = client.delete(f"/api/items/{item_id}")

    assert res.status_code == 204
    assert db.get(Item, item_id) is None


def test_delete_referenced_item_is_blocked(db, user, client):
    wh = main_warehouse(db)
    item = make_item(db)
    # یک خریدِ ساده، کالا را در سند و موجودی درگیر می‌کند
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(3), unit_cost=Decimal(1_000_000))],
        ),
        user,
    )
    db.flush()

    res = client.delete(f"/api/items/{item.id}")

    assert res.status_code == 409
    # حذف نباید انجام شده باشد — SAVEPOINT فقط تلاشِ ناموفق را برگردانده، نه کالا را
    assert db.get(Item, item.id) is not None


def test_delete_missing_item_is_404(db, user, client):
    res = client.delete(f"/api/items/{uuid.uuid4()}")
    assert res.status_code == 404
