"""«جلوگیری کن» در سقفِ اعتبار — و اینکه چرا فاکتورِ آفلاین از آن معاف است.

`contacts.credit_action` از روزِ اول ذخیره می‌شد و **هیچ‌جا اعمال نمی‌شد**: کاربر
«جلوگیری کن» را انتخاب می‌کرد و فاکتور همچنان ثبت می‌شد. یک تنظیمِ دروغین.

قیدهایی که این تست‌ها نگه می‌دارند:

* `block` واقعاً جلو می‌گیرد، `warn` و `none` هرگز.
* سقفِ صفر یعنی «بدون سقف»، نه «هیچ اعتباری».
* مبنا مبلغِ **نهایی** است (پس از تخفیف، مالیات و گِرد)، همان که به دریافتنی می‌نشیند.
* **فاکتورِ آفلاین رد نمی‌شود.** آن فروش قبلاً انجام شده و کالایش رفته؛ ردّش سرِ
  همگام‌سازی یعنی نابودکردنِ کارِ فروشنده.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models.inventory import Contact
from app.models.tenant import Tenant
from app.tenant_context import session_tenant
from tests.factories import main_warehouse, make_item


def _hybrid(db) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = "hybrid"
    db.flush()


def _contact(db, *, action: str, limit: int) -> Contact:
    row = Contact(
        name="مشتریِ سقف‌دار",
        type="customer",
        credit_limit=Decimal(limit),
        credit_action=action,
    )
    db.add(row)
    db.flush()
    return row


def _stock_up(db, user, item, warehouse, qty=100) -> None:
    from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
    from app.services.inventory import post_purchase_invoice

    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 1, 1),
            warehouse_id=warehouse.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(1000))],
        ),
        user,
    )


def _sell(db, user, client, contact, *, price, headers=None):
    item = make_item(db, sales_price=Decimal(price))
    warehouse = main_warehouse(db)
    _stock_up(db, user, item, warehouse)
    body = {
        "invoice_date": "2026-06-01",
        "warehouse_id": str(warehouse.id),
        "contact_id": str(contact.id),
        "lines": [{"item_id": str(item.id), "qty": 1, "unit_price": price}],
    }
    return client.post("/api/sales-invoices", json=body, headers=headers or {})


# ── گارد می‌گیرد ─────────────────────────────────────────────────────────────


def test_block_refuses_an_invoice_that_crosses_the_limit(db, user, client):
    """**قیدِ اصلی.** «جلوگیری کن» باید واقعاً جلو بگیرد."""
    _hybrid(db)
    contact = _contact(db, action="block", limit=5_000_000)

    res = _sell(db, user, client, contact, price=9_000_000)

    assert res.status_code == 409, res.text
    detail = res.json()["detail"]
    assert "سقفِ اعتبار" in detail
    #: پیام باید بگوید حالا چه کار کند، نه فقط «نه».
    assert "هشدار بده" in detail


def test_block_allows_an_invoice_that_stays_under_the_limit(db, user, client):
    """قرینه‌اش: زیرِ سقف هیچ اتفاقی نمی‌افتد."""
    _hybrid(db)
    contact = _contact(db, action="block", limit=50_000_000)

    res = _sell(db, user, client, contact, price=9_000_000)

    assert res.status_code == 201, res.text


@pytest.mark.parametrize("action", ["none", "warn"])
def test_the_other_two_actions_never_block(db, user, client, action):
    """`warn` هشدار است نه گارد — هشدارش کارِ بنرِ اعتبار در فرم است."""
    _hybrid(db)
    contact = _contact(db, action=action, limit=1_000_000)

    res = _sell(db, user, client, contact, price=9_000_000)

    assert res.status_code == 201, res.text


def test_a_zero_limit_means_no_limit_not_no_credit(db, user, client):
    """سقفِ صفر یعنی «بدون سقف» — همان قاعده‌ی `get_credit_status`.

    اگر روزی صفر «هیچ اعتباری» معنا شود، هر مشتری‌ای که سقف برایش تعیین نشده
    یک‌شبه بلاک می‌شود.
    """
    _hybrid(db)
    contact = _contact(db, action="block", limit=0)

    res = _sell(db, user, client, contact, price=900_000_000)

    assert res.status_code == 201, res.text


def test_a_cash_invoice_without_a_contact_is_never_blocked(db, user, client):
    """فروشِ نقدیِ بی‌طرف‌حساب اصلاً اعتبار ندارد که از سقفش رد شود."""
    _hybrid(db)
    item = make_item(db, sales_price=Decimal(9_000_000))
    warehouse = main_warehouse(db)
    _stock_up(db, user, item, warehouse)

    res = client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": "2026-06-01",
            "warehouse_id": str(warehouse.id),
            "lines": [{"item_id": str(item.id), "qty": 1, "unit_price": 9_000_000}],
        },
    )

    assert res.status_code == 201, res.text


# ── معافیتِ آفلاین ───────────────────────────────────────────────────────────


def test_an_offline_replay_is_not_blocked(db, user, client):
    """**قیدِ مهم.** فاکتورِ آفلاین سرِ همگام‌سازی رد نمی‌شود.

    آن فروش قبلاً انجام شده و کالایش تحویل رفته. ردّش این‌جا یعنی کارِ فروشنده از
    بین برود و دفتر با واقعیتِ انبار نخواند. تصمیمِ «نفروش» باید در لحظه‌ی فروش
    گرفته شود — و همان‌جا هم گرفته می‌شود: فرمِ فروش دکمه‌ی ثبت را می‌بندد.
    """
    _hybrid(db)
    contact = _contact(db, action="block", limit=5_000_000)

    res = _sell(
        db, user, client, contact,
        price=9_000_000,
        headers={"X-Cubita-Offline-Replay": "1"},
    )

    assert res.status_code == 201, res.text


def test_the_limit_counts_what_is_already_outstanding(db, user, client):
    """مبنا مانده‌ی جاری است، نه فقط همین فاکتور.

    دو فاکتورِ زیرِ سقف که *جمعشان* از سقف رد می‌شود، باید دومی گرفته شود.
    """
    _hybrid(db)
    contact = _contact(db, action="block", limit=15_000_000)

    first = _sell(db, user, client, contact, price=9_000_000)
    second = _sell(db, user, client, contact, price=9_000_000)

    assert first.status_code == 201, first.text
    assert second.status_code == 409, "جمعِ دو فاکتور از سقف رد می‌شود"
