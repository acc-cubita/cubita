"""فروشنده و نوعِ فروش روی فاکتور — دو ستونی که هیچ‌وقت نوشته نمی‌شدند.

`sales_invoices.salesperson_id` و `sale_type_id` از روزِ اول روی جدول بودند ولی نه
در `SalesInvoiceIn` بودند، نه سرویس می‌نشاندشان، نه فرم می‌فرستدشان.

پیامدش ساکت و جدی بود: `preview_commission` با `salesperson_id.isnot(None)` فیلتر
می‌کند، پس **محاسبه‌ی پورسانت هر بار صفر ردیف برمی‌گرداند** — کاربر قاعده تعریف
می‌کرد، «محاسبه» می‌زد، و خالی می‌گرفت بی‌آنکه خطایی ببیند.

مهم‌ترین تستِ این فایل `test_commission_preview_finally_returns_rows` است: بقیه اجزا را
می‌سنجند، آن یکی می‌سنجد که **قابلیت واقعاً کار می‌کند**.
"""
from datetime import date
from decimal import Decimal

from app.models.invoices import SalesInvoice
from app.models.sales_ops import CommissionRule, SaleType
from app.models.tenant import Tenant
from app.tenant_context import session_tenant
from tests.factories import main_warehouse, make_item


def _hybrid(db) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = "hybrid"
    db.flush()


def _sale_type(db, *, name="نقدی", active=True) -> SaleType:
    row = SaleType(name=name, due_days=0, is_active=active)
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


def _sell(db, user, client, *, price=10_000_000, salesperson_id=None, sale_type_id=None):
    item = make_item(db, sales_price=Decimal(price))
    warehouse = main_warehouse(db)
    _stock_up(db, user, item, warehouse)
    body = {
        "invoice_date": "2026-06-01",
        "warehouse_id": str(warehouse.id),
        "lines": [{"item_id": str(item.id), "qty": 1, "unit_price": price}],
    }
    if salesperson_id is not None:
        body["salesperson_id"] = str(salesperson_id)
    if sale_type_id is not None:
        body["sale_type_id"] = str(sale_type_id)
    return client.post("/api/sales-invoices", json=body)


# ── این بود کلِ ماجرا ────────────────────────────────────────────────────────


def test_commission_preview_finally_returns_rows(db, user, client):
    """**قیدِ اصلیِ این کار.** محاسبه‌ی پورسانت دیگر همیشه خالی نیست.

    اگر این تست بشکند، دو صفحه‌ی «قاعده‌ی پورسانت» و «محاسبه پورسانت» دوباره
    بی‌فایده شده‌اند — بدونِ اینکه هیچ خطایی به کاربر نشان داده شود.
    """
    _hybrid(db)
    db.add(CommissionRule(salesperson_id=user.id, rate=Decimal(5), basis="net", is_active=True))
    db.flush()

    res = _sell(db, user, client, price=10_000_000, salesperson_id=user.id)
    assert res.status_code == 201, res.text

    from app.services.sales_ops import preview_commission

    result = preview_commission(db, date(2026, 1, 1), date(2026, 12, 31))

    assert result["rows"], "محاسبه‌ی پورسانت باید ردیف بدهد، نه فهرستِ خالی"
    row = result["rows"][0]
    assert row["salesperson_id"] == user.id
    assert Decimal(row["amount"]) == Decimal(500_000)  # ۵٪ از ده میلیون


# ── ذخیره و نمایش ───────────────────────────────────────────────────────────


def test_salesperson_is_stored_and_named(db, user, client):
    _hybrid(db)

    res = _sell(db, user, client, salesperson_id=user.id)

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["salesperson_id"] == str(user.id)
    assert body["salesperson_name"]  # نام یا ایمیل — ولی نه خالی


def test_sale_type_is_stored_and_named(db, user, client):
    _hybrid(db)
    sale_type = _sale_type(db, name="اعتباری")

    res = _sell(db, user, client, sale_type_id=sale_type.id)

    assert res.status_code == 201, res.text
    assert res.json()["sale_type_id"] == str(sale_type.id)
    assert res.json()["sale_type_name"] == "اعتباری"


def test_both_are_optional(db, user, client):
    """فاکتورِ بی‌فروشنده و بی‌نوع باید مثل قبل ثبت شود.

    این قابلیت نباید رفتارِ حساب‌های موجود را عوض کند — قاعده‌ی «پرچمِ تازه
    پیش‌فرضش هیچ‌چیز عوض نمی‌شود».
    """
    _hybrid(db)

    res = _sell(db, user, client)

    assert res.status_code == 201, res.text
    assert res.json()["salesperson_id"] is None
    assert res.json()["sale_type_id"] is None


# ── گاردها ──────────────────────────────────────────────────────────────────


def test_a_user_from_another_business_cannot_be_the_salesperson(db, user, client):
    """`memberships` بی‌RLS است، پس بدونِ فیلترِ صریحِ مستأجر هر کاربری می‌نشست."""
    import uuid

    _hybrid(db)

    res = _sell(db, user, client, salesperson_id=uuid.uuid4())

    assert res.status_code == 400, res.text
    assert "کاربرِ این کسب‌وکار نیست" in res.json()["detail"]


def test_an_inactive_sale_type_is_refused(db, user, client):
    """همان قاعده‌ی مرکز هزینه: «غیرفعال» باید در سرور معنا داشته باشد."""
    _hybrid(db)
    sale_type = _sale_type(db, name="امانی", active=False)

    res = _sell(db, user, client, sale_type_id=sale_type.id)

    assert res.status_code == 400, res.text
    assert "غیرفعال" in res.json()["detail"]


def test_an_unknown_sale_type_is_refused(db, user, client):
    import uuid

    _hybrid(db)

    res = _sell(db, user, client, sale_type_id=uuid.uuid4())

    assert res.status_code == 400, res.text


def test_a_voided_invoice_leaves_the_commission_base(db, user, client):
    """فاکتورِ باطل نباید پورسانت بسازد — محاسبه باطل‌ها را کنار می‌گذارد."""
    _hybrid(db)
    db.add(CommissionRule(salesperson_id=user.id, rate=Decimal(5), basis="net", is_active=True))
    db.flush()

    res = _sell(db, user, client, price=10_000_000, salesperson_id=user.id)
    assert res.status_code == 201, res.text
    invoice_id = res.json()["id"]

    from app.services.voiding import void_sales_invoice

    void_sales_invoice(db, invoice_id, reason="آزمون", user=user, void_date=date(2026, 6, 2))
    db.flush()

    from app.services.sales_ops import preview_commission

    result = preview_commission(db, date(2026, 1, 1), date(2026, 12, 31))

    assert not result["rows"], "فاکتورِ باطل نباید در مبنای پورسانت بماند"
    assert db.get(SalesInvoice, invoice_id).voided_at is not None
