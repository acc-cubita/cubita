"""ویرایشِ بار باید **هر** فیلدی را که اسکیما می‌پذیرد واقعاً ذخیره کند.

این فایل از یک باگِ واقعی زاده شد: `PATCH /api/stock-batches/{id}` پنج فیلد را
دستی نسبت می‌داد، و شش ستونی که بعداً به `StockBatchIn` اضافه شدند — محلِ
قرارگیری، کدِ بارِ تأمین‌کننده، تأمین‌کننده، وضعیتِ QC و دو قیمتِ مصرف‌کننده —
**پذیرفته می‌شدند، ۲۰۰ می‌گرفتند و بی‌صدا دور ریخته می‌شدند**. هیچ خطایی در کار
نبود، پس انباردار محلِ قفسه را ست می‌کرد و ستونِ «محلِ قرارگیری» در برگه‌ی
جمع‌آوری تا ابد خالی می‌ماند.

پس تستِ اصلیِ این‌جا **فیلدها را از خودِ اسکیما می‌خواند**، نه از فهرستی که
خودش نوشته باشد: ستونِ بعدی که کسی اضافه کند خودبه‌خود سنجیده می‌شود، وگرنه
همین اتفاق دوباره می‌افتد و باز هم کسی نمی‌فهمد.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from app.routers.advanced_inventory import IMMUTABLE_BATCH_FIELDS
from app.schemas.advanced_inventory import StockBatchIn

TODAY = str(date.today())


def _main_wh(client):
    return next(w["id"] for w in client.get("/api/warehouses").json() if w["code"] == "MAIN")


def _setup(client, sku):
    wh = _main_wh(client)
    item = client.post("/api/items", json={"sku": sku, "name": f"کالای {sku}"}).json()["id"]
    r = client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": item, "qty": 10, "unit_cost": 1000}],
    })
    assert r.status_code == 201, r.text
    batch = client.get("/api/stock-batches", params={"item_id": item}).json()[0]
    return wh, item, batch


def _body(batch, **changes):
    """بدنه‌ی کاملِ ویرایش از خودِ بار — `StockBatchIn` ورودیِ جزئی نمی‌گیرد."""
    body = {
        "item_id": batch["item_id"], "warehouse_id": batch["warehouse_id"],
        "batch_number": batch["batch_number"], "received_date": batch["received_date"],
    }
    body.update(changes)
    return body


def test_patch_saves_every_field_the_schema_accepts(client, db):
    """نگهبانِ اصلی — و عمداً از روی اسکیما، نه از روی فهرستی دستی."""
    wh, item, batch = _setup(client, "PB-ALL")
    loc = client.post("/api/warehouse-locations", json={
        "warehouse_id": wh, "code": "Z-09-01", "name": "قفسه‌ی آزمون",
    }).json()
    supplier = client.post("/api/contacts", json={"name": "تأمین‌کننده‌ی آزمون", "type": "supplier"}).json()["id"]

    #: یک مقدارِ **متفاوت از پیش‌فرض** برای هر فیلدِ ویرایش‌پذیر.
    sent = {
        "batch_number": "EDITED-1",
        "expiry_date": str(date.today() + timedelta(days=90)),
        "production_date": str(date.today() - timedelta(days=10)),
        "unit_cost": "1234.0000",
        "consumer_price": "5678.0000",
        "received_date": str(date.today() - timedelta(days=3)),
        "notes": "یادداشتِ ویرایش‌شده",
        "supplier_batch_code": "SUP-77",
        "supplier_id": supplier,
        "location_id": loc["id"],
        "qc_status": "pending",
        "printed_consumer_price": "9100.0000",
        "maximum_retail_price": "9900.0000",
    }
    editable = set(StockBatchIn.model_fields) - IMMUTABLE_BATCH_FIELDS
    missing = editable - set(sent)
    assert not missing, f"فیلدِ تازه‌ای به اسکیما اضافه شده و این تست نمی‌سنجدش: {missing}"

    r = client.patch(f"/api/stock-batches/{batch['id']}", json=_body(batch, **sent))
    assert r.status_code == 200, r.text

    after = client.get("/api/stock-batches", params={"item_id": item}).json()[0]
    for field, value in sent.items():
        got, want = after[field], value
        #: مبلغ با تعدادِ رقمِ اعشارِ متفاوت برمی‌گردد («۵۶۷۸» در برابرِ
        #: «۵۶۷۸٫۰۰۰۰»)؛ چیزی که این تست می‌سنجد **ذخیره‌شدن** است نه قالب.
        try:
            assert Decimal(str(got)) == Decimal(str(want)), f"«{field}» ذخیره نشد: {got!r} ≠ {want!r}"
        except InvalidOperation:
            assert str(got) == str(want), f"«{field}» ذخیره نشد: {got!r} ≠ {want!r}"


def test_patch_does_not_move_a_batch_between_items_or_warehouses(client, db):
    """سه فیلدِ تغییرناپذیر — جابه‌جایی یعنی حرکت‌های دفتر به بارِ بی‌ربط گره بخورند."""
    wh, item, batch = _setup(client, "PB-LOCK")
    other = client.post("/api/items", json={"sku": "PB-OTHER", "name": "کالای دیگر"}).json()["id"]

    r = client.patch(f"/api/stock-batches/{batch['id']}", json={
        "item_id": other, "warehouse_id": batch["warehouse_id"],
        "batch_number": batch["batch_number"], "received_date": batch["received_date"],
        "qty": 999,
    })
    assert r.status_code == 200, r.text

    after = client.get("/api/stock-batches", params={"item_id": item}).json()
    assert len(after) == 1, "بار باید هنوز مالِ کالای اول باشد"
    assert after[0]["item_id"] == item
    assert float(after[0]["physical_qty"]) == 10, "مقدار با ویرایش عوض نمی‌شود"
    assert client.get("/api/stock-batches", params={"item_id": other}).json() == []


def test_patch_of_an_unknown_batch_is_a_clean_404(client, db):
    r = client.patch(f"/api/stock-batches/{uuid.uuid4()}", json={
        "item_id": str(uuid.uuid4()), "warehouse_id": str(uuid.uuid4()),
        "batch_number": "X", "received_date": TODAY,
    })
    assert r.status_code == 404
