"""اتصال فروشگاهِ پرمستأجر — تنظیماتِ هر کسب‌وکار + cutoverِ سفارش‌های قدیمی.

cutover: سایت هنگام ثبت سفارش خودش موجودی را کم می‌کند؛ چون موجودیِ اولیه‌ی حسابداری
برابرِ موجودیِ فعلیِ سایت گذاشته می‌شود، واردکردن دوباره‌ی سفارش‌های قدیمی موجودی را دوبار
کم می‌کند. آستانه باید آن‌ها را کنار بگذارد.
"""
from datetime import date
from decimal import Decimal

from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.schemas.storefront import StorefrontSettingsIn
from app.services import storefront_integration as si
from app.services.inventory import post_purchase_invoice
from tests.factories import make_item, other_warehouse


class _FakeClient:
    def __init__(self, orders):
        self._orders = orders

    def list_orders(self, page, per_page=50):
        return {"items": self._orders if page == 1 else []}


def _order(oid, product_id, qty, price=500):
    return {
        "id": oid,
        "created_at": "2026-03-01T10:00:00",
        "tracking_code": f"T{oid}",
        "items": [{"product_id": product_id, "qty": qty, "price": price}],
    }


def _mapped_item_with_stock(db, user, *, storefront_id=28, qty=10):
    wh = other_warehouse(db)  # انبار ONLINE
    item = make_item(db)
    item.storefront_product_id = storefront_id
    db.flush()
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 1, 1),
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(1000))],
        ),
        user,
    )
    return item


def test_cutover_skips_old_imports_new(db, user):
    _mapped_item_with_stock(db, user)
    client = _FakeClient([_order(3, 28, 1), _order(4, 28, 1), _order(5, 28, 2)])

    result = si.pull_new_orders(db, user, client=client, cutover=4)

    assert result.imported == [5]  # فقط سفارشِ بزرگ‌تر از آستانه
    assert all(s["order_id"] not in (3, 4) for s in result.skipped)  # قدیمی‌ها اصلاً پردازش نشدند


def test_no_cutover_imports_all(db, user):
    _mapped_item_with_stock(db, user)
    client = _FakeClient([_order(3, 28, 1), _order(5, 28, 1)])

    result = si.pull_new_orders(db, user, client=client, cutover=0)

    assert sorted(result.imported) == [3, 5]


def test_cutover_read_from_tenant_settings(db, user):
    """وقتی cutover صریح داده نشود، از ردیفِ تنظیماتِ همان کسب‌وکار خوانده می‌شود."""
    _mapped_item_with_stock(db, user)
    si.update_settings(
        db,
        StorefrontSettingsIn(base_url="https://x.ir", admin_email="a@x.ir", admin_password="p", cutover_order_id=4, is_active=True),
    )
    client = _FakeClient([_order(4, 28, 1), _order(5, 28, 1)])

    result = si.pull_new_orders(db, user, client=client)  # بدون cutover صریح

    assert result.imported == [5]


def test_settings_password_write_only(db):
    """رمز ذخیره می‌شود ولی با ارسالِ خالی پاک نمی‌شود (حفظِ رمزِ فعلی)."""
    si.update_settings(db, StorefrontSettingsIn(base_url="https://x.ir", admin_email="a@x.ir", admin_password="secret", is_active=True))
    row = si.get_settings_row(db)
    assert row.admin_password == "secret"

    # به‌روزرسانیِ بعدی بدونِ رمز → رمز دست‌نخورده می‌ماند
    si.update_settings(db, StorefrontSettingsIn(base_url="https://y.ir", admin_email="a@x.ir", admin_password="", is_active=True))
    row = si.get_settings_row(db)
    assert row.base_url == "https://y.ir"
    assert row.admin_password == "secret"


def test_inactive_settings_block_sync(db, user):
    import pytest

    from app.services.storefront_integration import StorefrontConfigError

    si.update_settings(db, StorefrontSettingsIn(base_url="https://x.ir", admin_email="a@x.ir", admin_password="p", is_active=False))
    with pytest.raises(StorefrontConfigError):
        si.sync_all(db, user)
