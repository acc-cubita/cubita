"""آمادگیِ گزارش فصلی: کدام ردیف پیش از آپلود در سامانه رد خواهد شد.

گزارش از قبل کد ملی و کد اقتصادی و کد پستی را برمی‌گرداند و جدول جای خالی را
`—` نشان می‌دهد — ولی **هیچ‌چیز نمی‌گفت این یک مشکل است**. نه شمارشی، نه هشداری،
نه راهی برای پیداکردنشان بینِ صدها ردیف. حسابدار بعد از آپلود می‌فهمید.

بدتر از نبودن، بدشکل بودن است: کامنتِ `Contact.national_id` می‌گوید حقیقی ۱۰ رقم
و حقوقی ۱۱ رقم، ولی هیچ‌جا سنجیده نمی‌شد. کدِ ۱۰رقمی روی شخصِ حقوقی *پُر*
به‌نظر می‌رسد و سرِ آپلود رد می‌شود.

**گزارش است، نه گارد:** خروجی هرگز مسدود نمی‌شود.
"""
from app.jalali import jalali_to_gregorian

YEAR = 1404
SUMMER = jalali_to_gregorian(YEAR, 5, 15).isoformat()

COMPLETE = {
    "national_id": "1234567890",
    "economic_code": "411111111111",
    "postal_code": "1234567890",
}


def _wh(client):
    return client.post("/api/warehouses", json={"code": "RZ", "name": "انبار"}).json()["id"]


def _item(client, sku):
    return client.post("/api/items", json={"sku": sku, "name": "کالا"}).json()["id"]


def _customer(client, name="شرکت الف", **extra):
    body = {"name": name, "type": "customer", **extra}
    res = client.post("/api/contacts", json=body)
    assert res.status_code in (200, 201), res.text
    return res.json()["id"]


def _stock(client, wh, item_id):
    """بدونِ موجودی، فروش ۴۰۰ می‌گیرد — خریدِ تأمین‌کننده‌ی بی‌طرف‌حساب کافی است."""
    res = client.post(
        "/api/purchase-invoices",
        json={
            "invoice_date": SUMMER,
            "warehouse_id": wh,
            "contact_id": None,
            "lines": [{"item_id": item_id, "qty": 50, "unit_cost": 500_000}],
        },
    )
    assert res.status_code in (200, 201), res.text


def _sell(client, wh, item_id, date, contact_id=None):
    res = client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": date,
            "warehouse_id": wh,
            "contact_id": contact_id,
            "lines": [{"item_id": item_id, "qty": 1, "unit_price": 1_000_000}],
        },
    )
    assert res.status_code in (200, 201), res.text
    return res


def _rows(client, quarter=2) -> list[dict]:
    res = client.get(f"/api/reports/seasonal?year={YEAR}&quarter={quarter}")
    assert res.status_code == 200, res.text
    return res.json()["sales"]


def _row_for(section: dict, name: str) -> dict:
    return next(r for r in section["rows"] if r["contact_name"] == name)


# ── کمبودها دیده می‌شوند ────────────────────────────────────────────────────


def test_a_party_without_tax_identity_is_flagged(client):
    """**قیدِ اصلی.** پیش از این، ردیف با `—` رد می‌شد و کسی خبر نداشت."""
    wh, it = _wh(client), _item(client, "RZ-1")
    _stock(client, wh, it)
    _sell(client, wh, it, SUMMER, _customer(client, "بی‌هویت"))

    row = _row_for(_rows(client), "بی‌هویت")
    assert set(row["issues"]) == {
        "national_id_missing",
        "economic_code_missing",
        "postal_code_missing",
    }


def test_a_complete_party_has_no_issues(client):
    wh, it = _wh(client), _item(client, "RZ-2")
    _stock(client, wh, it)
    _sell(client, wh, it, SUMMER, _customer(client, "کامل", **COMPLETE))

    section = _rows(client)
    assert _row_for(section, "کامل")["issues"] == []
    assert section["ready_count"] >= 1


# ── طولِ شناسه، به تفکیکِ نوعِ شخص ───────────────────────────────────────────


def test_a_legal_entity_with_a_ten_digit_id_is_flagged(client):
    """شناسه‌ی ملیِ حقوقی ۱۱ رقم است؛ ۱۰ رقم *پُر* به‌نظر می‌رسد و رد می‌شود."""
    wh, it = _wh(client), _item(client, "RZ-3")
    _stock(client, wh, it)
    _sell(client, wh, it, SUMMER, _customer(client, "حقوقیِ کوتاه", entity_type="legal", **COMPLETE))

    assert "national_id_length" in _row_for(_rows(client), "حقوقیِ کوتاه")["issues"]


def test_a_legal_entity_with_eleven_digits_is_clean(client):
    wh, it = _wh(client), _item(client, "RZ-4")
    _stock(client, wh, it)
    _sell(
        client, wh, it, SUMMER,
        _customer(client, "حقوقیِ درست", entity_type="legal", **{**COMPLETE, "national_id": "12345678901"}),
    )

    assert _row_for(_rows(client), "حقوقیِ درست")["issues"] == []


def test_a_real_person_with_ten_digits_is_clean(client):
    """**رگرسیونِ معکوس:** قاعده نباید وارونه اعمال شود."""
    wh, it = _wh(client), _item(client, "RZ-5")
    _stock(client, wh, it)
    _sell(client, wh, it, SUMMER, _customer(client, "حقیقیِ درست", entity_type="real", **COMPLETE))

    assert _row_for(_rows(client), "حقیقیِ درست")["issues"] == []


# ── چیزهایی که نباید ایراد بگیرند ───────────────────────────────────────────


def test_the_walkin_aggregate_row_is_never_flagged(client):
    """ردیفِ «معاملاتِ خرد» طرف‌حساب نیست؛ هویتی ندارد که کم داشته باشد."""
    wh, it = _wh(client), _item(client, "RZ-6")
    _stock(client, wh, it)
    _sell(client, wh, it, SUMMER, None)  # فروشِ بدونِ طرف حساب

    aggregate = next(r for r in _rows(client)["rows"] if r["contact_id"] is None)
    assert aggregate["issues"] == []


def test_the_counters_match_the_rows(client):
    wh, it = _wh(client), _item(client, "RZ-7")
    _stock(client, wh, it)
    _sell(client, wh, it, SUMMER, _customer(client, "کامل‌۲", **COMPLETE))
    _sell(client, wh, it, SUMMER, _customer(client, "ناقص‌۲"))

    section = _rows(client)
    assert section["ready_count"] == sum(1 for r in section["rows"] if not r["issues"])
    assert section["incomplete_count"] == sum(1 for r in section["rows"] if r["issues"])
    assert section["incomplete_count"] >= 1


def test_the_money_is_untouched(client):
    """**رگرسیون.** این کار هیچ عددی را نباید تکان دهد."""
    wh, it = _wh(client), _item(client, "RZ-8")
    _stock(client, wh, it)
    _sell(client, wh, it, SUMMER, _customer(client, "مبلغی", **COMPLETE))

    row = _row_for(_rows(client), "مبلغی")
    from decimal import Decimal

    assert Decimal(row["net"]) == Decimal(1_000_000)
    assert Decimal(row["total"]) == Decimal(1_000_000)  # بدونِ مالیات
    assert row["invoice_count"] == 1
