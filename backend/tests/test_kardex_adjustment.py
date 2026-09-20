"""کاردکسِ کالایی که تعدیل خورده نباید بشکند.

**این یک باگِ زنده بود، نه فرضیه.** `valuation.document_numbers` کورکورانه
`model.number` را می‌خواند، ولی `StockAdjustment` — که از مهاجرتِ ۰۱۵۸ در
`_SOURCE_MODELS` هست — اصلاً ستونِ `number` ندارد. نتیجه: **کاردکسِ هر کالایی که
یک بار تعدیل خورده باشد** با `AttributeError` و خطای ۵۰۰ برمی‌گشت.

با یک درخواستِ واقعی به `/api/reports/kardex/{id}` بازتولید شد. چون گزارشِ
کاردکس یکی از پرکاربردترین صفحه‌های انبار است، این تست می‌ماند تا دوباره
برنگردد.
"""
from datetime import date

TODAY = str(date.today())


def test_kardex_survives_an_adjusted_item(client):
    wh = next(w["id"] for w in client.get("/api/warehouses").json() if w["code"] == "MAIN")
    it = client.post("/api/items", json={"sku": "KX-ADJ", "name": "تعدیل‌خورده"}).json()["id"]
    client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 10, "unit_cost": 100}],
    })
    client.post("/api/stock-adjustments", json={
        "item_id": it, "warehouse_id": wh, "qty_diff": -2,
        "reason": "کسری", "adjustment_date": TODAY,
    })

    r = client.get(f"/api/reports/kardex/{it}")
    assert r.status_code == 200, r.text

    #: ردیفِ تعدیل باید برچسبِ خودش را داشته باشد و شماره‌اش **تهی** بماند —
    #: نه یک عددِ ساختگی و نه رشته‌ی «None» در متنِ سند.
    lines = r.json()["lines"]
    adjustment = next(x for x in lines if x["source_type"] == "adjustment")
    assert adjustment["source_label"] == "تعدیل انبار"
    assert adjustment["source_number"] is None
