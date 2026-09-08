"""مشمول و معاف: «چقدر فروشِ معاف داشته‌ایم؟» تا امروز جوابی نداشت.

نه کالا وضعیتِ مالیاتی داشت، نه گزارش پایه را تفکیک می‌کرد؛ تنها چیزی که بود
`tax_rate` روی سربرگِ فاکتور. و `tax_rate = 0` **مبهم** است: سالِ بعد کسی
نمی‌تواند بگوید این کالا واقعاً معاف بوده یا فقط آن فاکتور بی‌مالیات صادر شده.

دو قیدِ اصلیِ این فایل:

* **جمعِ چهار سطل = `total_amount`** — تفکیک باید کامل باشد، نه تقریبی.
* **وضعیت روی ردیفِ فاکتور قفل می‌شود** — معاف‌شدنِ امسالِ یک کالا نباید فروشِ
  پارسال را هم معاف نشان دهد. قانون عوض می‌شود، تاریخ نه.
"""
from decimal import Decimal

DAY = "2026-06-01"


def _wh(client):
    return client.post("/api/warehouses", json={"code": "VT", "name": "انبار"}).json()["id"]


def _item(client, sku, *, vat_status="taxable", is_service=False):
    res = client.post(
        "/api/items",
        json={"sku": sku, "name": f"کالای {sku}", "vat_status": vat_status, "is_service": is_service},
    )
    assert res.status_code in (200, 201), res.text
    return res.json()["id"]


def _stock(client, wh, item_id, qty=100):
    res = client.post(
        "/api/purchase-invoices",
        json={
            "invoice_date": "2026-01-01",
            "warehouse_id": wh,
            "lines": [{"item_id": item_id, "qty": qty, "unit_cost": 1000}],
        },
    )
    assert res.status_code in (200, 201), res.text


def _sell(client, wh, lines, *, tax_rate=0, invoice_discount=0):
    body = {"invoice_date": DAY, "warehouse_id": wh, "tax_rate": tax_rate, "lines": lines}
    if invoice_discount:
        body["invoice_discount"] = invoice_discount
    res = client.post("/api/sales-invoices", json=body)
    assert res.status_code in (200, 201), res.text
    return res.json()


def _vat(client):
    res = client.get(f"/api/reports/vat?date_from={DAY}&date_to={DAY}")
    assert res.status_code == 200, res.text
    return res.json()


def _line(item_id, qty=1, price=1_000_000):
    return {"item_id": item_id, "qty": qty, "unit_price": price}


# ── تفکیک ───────────────────────────────────────────────────────────────────


def test_an_exempt_sale_lands_in_the_exempt_bucket(client):
    """**قیدِ اصلی.** تا امروز هر فروشی مشمول فرض می‌شد."""
    wh = _wh(client)
    it = _item(client, "VT-1", vat_status="exempt")
    _stock(client, wh, it)
    _sell(client, wh, [_line(it)])

    b = _vat(client)["sales_breakdown"]
    assert Decimal(b["exempt_goods"]) == Decimal(1_000_000)
    assert Decimal(b["taxable_goods"]) == 0


def test_services_are_split_from_goods(client):
    wh = _wh(client)
    goods = _item(client, "VT-2")
    service = _item(client, "VT-3", is_service=True)
    _stock(client, wh, goods)
    _sell(client, wh, [_line(goods), _line(service, price=400_000)])

    b = _vat(client)["sales_breakdown"]
    assert Decimal(b["taxable_goods"]) == Decimal(1_000_000)
    assert Decimal(b["taxable_services"]) == Decimal(400_000)


def test_the_four_buckets_sum_to_the_total(client):
    """**قیدِ دقت.** تفکیک باید کامل باشد، حتی با تخفیفِ سطحِ فاکتور.

    این کار می‌کند چون تخفیفِ فاکتور از قبل بینِ ردیف‌ها تسهیم می‌شود؛ اگر روزی
    آن رفتار عوض شود، این تست اولین چیزی است که قرمز می‌شود.
    """
    wh = _wh(client)
    taxable = _item(client, "VT-4")
    exempt = _item(client, "VT-5", vat_status="exempt")
    _stock(client, wh, taxable)
    _stock(client, wh, exempt)
    invoice = _sell(
        client, wh, [_line(taxable), _line(exempt, price=500_000)], invoice_discount=120_000
    )

    b = _vat(client)["sales_breakdown"]
    total = sum(Decimal(b[k]) for k in b)
    assert total == Decimal(invoice["total_amount"])


# ── قفل‌شدنِ وضعیت در لحظه‌ی معامله ──────────────────────────────────────────


def test_reclassifying_an_item_does_not_rewrite_past_sales(client):
    """**مهم‌ترین رگرسیون.** قانون عوض می‌شود، تاریخ نه.

    فروشی که در زمانِ مشمول‌بودن انجام شده باید تا ابد مشمول گزارش شود، حتی اگر
    کالا بعداً معاف شود.
    """
    wh = _wh(client)
    it = _item(client, "VT-6")  # مشمول
    _stock(client, wh, it)
    _sell(client, wh, [_line(it)])

    res = client.patch(f"/api/items/{it}", json={"vat_status": "exempt"})
    assert res.status_code == 200, res.text

    b = _vat(client)["sales_breakdown"]
    assert Decimal(b["taxable_goods"]) == Decimal(1_000_000), "فروشِ گذشته نباید بازنویسی شود"
    assert Decimal(b["exempt_goods"]) == 0


# ── فاکتورِ ترکیبی ──────────────────────────────────────────────────────────


def test_a_mixed_invoice_with_tax_is_reported(client):
    """ردیفِ معاف هم مالیات خورده، چون مالیات یک نرخ روی کلِ فاکتور است."""
    wh = _wh(client)
    taxable = _item(client, "VT-7")
    exempt = _item(client, "VT-8", vat_status="exempt")
    _stock(client, wh, taxable)
    _stock(client, wh, exempt)
    _sell(client, wh, [_line(taxable), _line(exempt, price=300_000)], tax_rate=10)

    mixed = _vat(client)["mixed_sales_invoices"]
    assert len(mixed) == 1
    assert Decimal(mixed[0]["exempt_net"]) == Decimal(300_000)
    assert Decimal(mixed[0]["tax_amount"]) > 0


def test_a_single_status_invoice_is_not_reported(client):
    """فاکتورِ یکدست — حتی با مالیات — مشکلی ندارد و نباید هشدار بگیرد."""
    wh = _wh(client)
    it = _item(client, "VT-9")
    _stock(client, wh, it)
    _sell(client, wh, [_line(it)], tax_rate=10)

    assert _vat(client)["mixed_sales_invoices"] == []


def test_a_mixed_invoice_without_tax_is_not_reported(client):
    """بدونِ نرخ، ردیفِ معاف مالیاتی نخورده — پس چیزی برای هشدار نیست."""
    wh = _wh(client)
    taxable = _item(client, "VT-10")
    exempt = _item(client, "VT-11", vat_status="exempt")
    _stock(client, wh, taxable)
    _stock(client, wh, exempt)
    _sell(client, wh, [_line(taxable), _line(exempt)], tax_rate=0)

    assert _vat(client)["mixed_sales_invoices"] == []


# ── چیزی که نباید عوض شود ───────────────────────────────────────────────────


def test_the_existing_totals_are_untouched(client):
    """**رگرسیون.** تفکیک هیچ‌کدام از ارقامِ قبلی را تکان نمی‌دهد."""
    wh = _wh(client)
    it = _item(client, "VT-12")
    _stock(client, wh, it)
    _sell(client, wh, [_line(it)], tax_rate=10)

    report = _vat(client)
    assert Decimal(report["sales_net"]) == Decimal(1_000_000)
    assert Decimal(report["output_vat"]) == Decimal(100_000)
    assert Decimal(report["net_vat"]) == Decimal(report["output_vat"]) - Decimal(report["input_vat"])
