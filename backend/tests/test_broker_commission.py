"""کارمزدِ واسطه روی فاکتور فروش.

نقشِ «واسط» روی طرف‌حساب از قبل بود و نرخِ کارمزدش هم ذخیره می‌شد، ولی به هیچ
معامله‌ای نمی‌چسبید. این‌ها قیدهایی‌اند که آن اتصال را نگه می‌دارند:

* واسطه روی فاکتور ذخیره می‌شود و کارمزدش **در لحظه‌ی ثبت قفل می‌شود**.
* مبنا خالصِ پس از تخفیف و **پیش از مالیات** است.
* طرف‌حسابی که تیکِ «واسط» ندارد واسطه نمی‌شود — وگرنه آن تیک تزئینی است.
* **تغییرِ بعدیِ نرخ گذشته را بازنویسی نمی‌کند.** این تنها دلیلِ ذخیره‌شدنِ مبلغ
  به‌جای مشتق‌شدنش است؛ اگر این تست بشکند، ذخیره‌کردن دیگر توجیهی ندارد.
"""
from datetime import date
from decimal import Decimal

from app.models.inventory import Contact
from app.models.invoices import SalesInvoice
from app.models.tenant import Tenant
from app.tenant_context import session_tenant
from tests.factories import main_warehouse, make_item


def _hybrid(db) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = "hybrid"
    db.flush()


def _broker(db, *, rate: int, is_broker: bool = True) -> Contact:
    row = Contact(
        name="واسطه‌ی آزمون",
        type="customer",
        is_broker=is_broker,
        commission_rate=Decimal(rate),
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


def _sell(db, user, client, *, price, broker_id=None, tax_rate=0, discount=0):
    item = make_item(db, sales_price=Decimal(price))
    warehouse = main_warehouse(db)
    _stock_up(db, user, item, warehouse)
    body = {
        "invoice_date": "2026-06-01",
        "warehouse_id": str(warehouse.id),
        "tax_rate": tax_rate,
        "invoice_discount": discount,
        "lines": [{"item_id": str(item.id), "qty": 1, "unit_price": price}],
    }
    if broker_id is not None:
        body["broker_id"] = str(broker_id)
    return client.post("/api/sales-invoices", json=body)


# ── کارمزد محاسبه و قفل می‌شود ───────────────────────────────────────────────


def test_commission_is_calculated_and_stored(db, user, client):
    """**قیدِ اصلی.** واسطه می‌چسبد و کارمزدش حساب می‌شود."""
    _hybrid(db)
    broker = _broker(db, rate=5)

    res = _sell(db, user, client, price=10_000_000, broker_id=broker.id)

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["broker_id"] == str(broker.id)
    assert Decimal(body["broker_commission"]) == Decimal(500_000)  # ۵٪ از ده میلیون
    assert body["broker_name"] == "واسطه‌ی آزمون"


def test_an_invoice_without_a_broker_stores_zero(db, user, client):
    """قرینه‌اش: بی‌واسطه یعنی NULL و صفر، نه خطا."""
    _hybrid(db)

    res = _sell(db, user, client, price=10_000_000)

    assert res.status_code == 201, res.text
    assert res.json()["broker_id"] is None
    assert Decimal(res.json()["broker_commission"]) == Decimal(0)


def test_a_broker_with_a_zero_rate_gets_no_commission_but_is_still_recorded(db, user, client):
    """نرخِ صفر یعنی «کارمزد ندارد»، نه «واسطه نبوده».

    ثبتِ واسطه مستقل از کارمزد است: کسی که معامله را آورده باید در سابقه بماند
    حتی اگر این‌بار چیزی نگیرد.
    """
    _hybrid(db)
    broker = _broker(db, rate=0)

    res = _sell(db, user, client, price=10_000_000, broker_id=broker.id)

    assert res.status_code == 201, res.text
    assert res.json()["broker_id"] == str(broker.id)
    assert Decimal(res.json()["broker_commission"]) == Decimal(0)


# ── مبنای محاسبه ─────────────────────────────────────────────────────────────


def test_the_base_is_net_after_discount_and_before_tax(db, user, client):
    """مالیات پولِ دولت است نه فروشِ ما، پس وارد مبنای کارمزد نمی‌شود.

    ده میلیون با یک میلیون تخفیفِ کل و ۱۰٪ مالیات: مبنا ۹٬۰۰۰٬۰۰۰ است — نه
    ۱۰٬۰۰۰٬۰۰۰ (پیش از تخفیف) و نه ۹٬۹۰۰٬۰۰۰ (با مالیات).
    """
    _hybrid(db)
    broker = _broker(db, rate=10)

    res = _sell(
        db, user, client,
        price=10_000_000, broker_id=broker.id,
        tax_rate=10, discount=1_000_000,
    )

    assert res.status_code == 201, res.text
    assert Decimal(res.json()["broker_commission"]) == Decimal(900_000)


# ── گاردِ نقش ────────────────────────────────────────────────────────────────


def test_a_contact_without_the_broker_role_is_refused(db, user, client):
    """بدونِ این گارد، تیکِ «واسط» در فرمِ طرف حساب هیچ معنایی ندارد."""
    _hybrid(db)
    not_a_broker = _broker(db, rate=5, is_broker=False)

    res = _sell(db, user, client, price=10_000_000, broker_id=not_a_broker.id)

    assert res.status_code == 400, res.text
    assert "نقشِ واسط ندارد" in res.json()["detail"]


# ── چرا مبلغ ذخیره می‌شود و مشتق نیست ────────────────────────────────────────


def test_a_later_rate_change_does_not_rewrite_past_commission(db, user, client):
    """**دلیلِ وجودِ ستونِ `broker_commission`.**

    اگر کارمزد در لحظه‌ی خواندن از `commission_rate` حساب می‌شد، بالابردنِ نرخ
    صورت‌حسابِ تسویه‌شده‌ی ماهِ پیش را هم بالا می‌برد. این تست همان را می‌بندد.
    """
    _hybrid(db)
    broker = _broker(db, rate=5)

    res = _sell(db, user, client, price=10_000_000, broker_id=broker.id)
    assert res.status_code == 201, res.text
    invoice_id = res.json()["id"]

    broker.commission_rate = Decimal(20)
    db.flush()

    stored = db.get(SalesInvoice, invoice_id)
    assert Decimal(stored.broker_commission) == Decimal(500_000), (
        "کارمزدِ گذشته باید همان ۵٪ لحظه‌ی فروش بماند، نه ۲۰٪ امروز"
    )
