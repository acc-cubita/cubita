"""محافظت در برابر ثبت دوباره‌ی سند مالی.

سه راهی که یک فاکتور دو بار ثبت می‌شود و هیچ‌کدام باگ کلاینت نیستند: دوبار کلیک،
گم شدن پاسخ در شبکه، و retry مرورگر یا پراکسی. هر سه دو سند مالی می‌سازند **بدون
هیچ خطایی** — که برای نرم‌افزار حسابداری بدترین شکل باگ است.

`test_two_concurrent_requests_create_only_one_invoice` مهم‌ترین تست پرونده است و
عمداً با دو نخ و یک Barrier نوشته شده: بدون همگام‌سازی صریح، دو نخ پشت سر هم اجرا
می‌شوند و تست حتی وقتی محافظت وجود ندارد سبز می‌ماند.
"""
import threading
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.models.accounting import JournalEntry
from app.models.idempotency import IdempotencyKey
from app.models.inventory import Item, StockLedger, Warehouse
from app.models.invoices import PurchaseInvoice, SalesInvoice
from app.services.idempotency import HEADER, request_fingerprint

TODAY = date.today().isoformat()


@pytest.fixture
def warehouse(db):
    return db.query(Warehouse).filter(Warehouse.code == "MAIN").one()


@pytest.fixture
def widget(db):
    item = Item(sku="IDEM-1", name="کالای یکتاسازی", unit="عدد", sales_price=5000)
    db.add(item)
    db.flush()
    return item


def purchase_body(warehouse, item, qty=10, cost=1000):
    return {
        "invoice_date": TODAY,
        "warehouse_id": str(warehouse.id),
        "contact_id": None,
        "description": "خرید",
        "lines": [{"item_id": str(item.id), "qty": qty, "unit_cost": cost, "description": ""}],
    }


def fresh_key() -> str:
    return uuid.uuid4().hex


# --- رفتار پایه ----------------------------------------------------------------------


def test_the_same_key_creates_only_one_invoice(client, db, warehouse, widget):
    key = fresh_key()
    body = purchase_body(warehouse, widget)
    headers = {HEADER: key}

    first = client.post("/api/purchase-invoices", json=body, headers=headers)
    second = client.post("/api/purchase-invoices", json=body, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"], "درخواست دوم سند تازه ساخت"
    assert db.query(PurchaseInvoice).count() == 1


def test_the_duplicate_does_not_post_a_second_journal_entry(client, db, warehouse, widget):
    """سند حسابداری دوم یعنی دفتر غلط — و این خاموش‌ترین بخش باگ است."""
    before = db.query(JournalEntry).count()
    key = fresh_key()
    body = purchase_body(warehouse, widget)

    client.post("/api/purchase-invoices", json=body, headers={HEADER: key})
    entries_after_first = db.query(JournalEntry).count()

    client.post("/api/purchase-invoices", json=body, headers={HEADER: key})
    assert db.query(JournalEntry).count() == entries_after_first
    assert entries_after_first == before + 1


def test_the_duplicate_does_not_move_stock_twice(client, db, warehouse, widget):
    from app.services.inventory import get_stock_qty

    key = fresh_key()
    body = purchase_body(warehouse, widget, qty=7)

    client.post("/api/purchase-invoices", json=body, headers={HEADER: key})
    client.post("/api/purchase-invoices", json=body, headers={HEADER: key})

    assert get_stock_qty(db, widget.id, warehouse.id) == 7


def test_different_keys_create_different_invoices(client, db, warehouse, widget):
    """محافظت نباید ثبت عمدیِ دو فاکتور مشابه را ببندد."""
    body = purchase_body(warehouse, widget)
    first = client.post("/api/purchase-invoices", json=body, headers={HEADER: fresh_key()})
    second = client.post("/api/purchase-invoices", json=body, headers={HEADER: fresh_key()})

    assert first.json()["id"] != second.json()["id"]
    assert db.query(PurchaseInvoice).count() == 2


def test_without_the_header_nothing_changes(client, db, warehouse, widget):
    """سازگاری با کلاینت مستقرشده: نبودِ هدر نباید درخواست را رد کند."""
    body = purchase_body(warehouse, widget)
    first = client.post("/api/purchase-invoices", json=body)
    second = client.post("/api/purchase-invoices", json=body)

    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] != second.json()["id"], "بدون هدر، محافظتی وجود ندارد — و این عمدی است"


# --- سوءاستفاده و حالت‌های مرزی --------------------------------------------------------


def test_reusing_a_key_with_different_content_is_rejected(client, db, warehouse, widget):
    """اگر بی‌صدا نتیجه‌ی قبلی برگردد، فاکتور دومِ کاربر خاموش گم می‌شود."""
    key = fresh_key()
    client.post("/api/purchase-invoices", json=purchase_body(warehouse, widget, qty=5), headers={HEADER: key})
    res = client.post("/api/purchase-invoices", json=purchase_body(warehouse, widget, qty=99), headers={HEADER: key})

    assert res.status_code == 409
    assert db.query(PurchaseInvoice).count() == 1


def test_the_same_key_on_a_different_operation_is_rejected(client, db, warehouse, widget):
    key = fresh_key()
    client.post("/api/purchase-invoices", json=purchase_body(warehouse, widget), headers={HEADER: key})

    sale = {
        "invoice_date": TODAY,
        "warehouse_id": str(warehouse.id),
        "contact_id": None,
        "description": "فروش",
        "lines": [{"item_id": str(widget.id), "qty": 1, "unit_price": 2000, "description": ""}],
    }
    res = client.post("/api/sales-invoices", json=sale, headers={HEADER: key})
    assert res.status_code == 409


def test_key_order_in_json_does_not_change_the_fingerprint():
    """ترتیب کلیدها در JSON معنایی ندارد و نباید اثر انگشت را عوض کند.

    **این تست عمداً یک مدل محلی با فیلد dict آزاد می‌سازد، و دلیلش را باید صادقانه
    گفت:** شِماهای فعلیِ فاکتور هیچ فیلد dict آزادی ندارند، پس `model_dump` همیشه
    ترتیب یکسانِ اعلانِ فیلدها را می‌دهد و `sort_keys` امروز روی آن مسیر بی‌اثر
    است. با شِمای واقعی، این تست حتی بدون sort_keys هم سبز می‌ماند — یعنی چیزی
    را که ادعا می‌کند نمی‌سنجید.

    ولی قرارداد خودِ تابع همین است، و لحظه‌ای که شِمایی فیلد dict بگیرد (تنظیمات،
    فراداده، هر چیزی که کلاینت به‌شکل JSON آزاد می‌فرستد) نبودِ sort_keys محافظت
    را بی‌صدا بی‌اثر می‌کند. پس قرارداد سنجیده می‌شود، نه یک مسیر خاص.
    """
    from pydantic import BaseModel

    class Payload(BaseModel):
        meta: dict

    a = Payload.model_validate({"meta": {"z": 1, "a": 2}})
    b = Payload.model_validate({"meta": {"a": 2, "z": 1}})
    assert request_fingerprint(a) == request_fingerprint(b), (
        "همان محتوا با ترتیب کلید متفاوت اثر انگشت متفاوت گرفت — "
        "یعنی ارسال تکراری به‌عنوان درخواست تازه دیده می‌شود"
    )


def test_an_overlong_key_is_rejected(client, warehouse, widget):
    res = client.post(
        "/api/purchase-invoices",
        json=purchase_body(warehouse, widget),
        headers={HEADER: "x" * 500},
    )
    assert res.status_code == 400


def test_a_blank_key_is_treated_as_absent(client, warehouse, widget):
    res = client.post("/api/purchase-invoices", json=purchase_body(warehouse, widget), headers={HEADER: "   "})
    assert res.status_code == 201


# --- همزمانی ---------------------------------------------------------------------------


def test_two_concurrent_requests_create_only_one_invoice(tenant_id, warehouse, widget, db):
    """مهم‌ترین تست این پرونده.

    Barrier اجباری است و تزئینی نیست: بدون آن دو نخ عملاً پشت سر هم اجرا می‌شوند و
    تست حتی وقتی هیچ محافظتی وجود ندارد سبز می‌ماند — یعنی چیزی را که ادعا می‌کند
    نمی‌سنجد.

    اینجا از fixture `db` برای نوشتن استفاده نمی‌شود چون آن همه‌چیز را برمی‌گرداند؛
    هر نخ Session و تراکنش خودش را می‌گیرد تا رقابت واقعی باشد.
    """
    from app.models.user import User
    from tests.conftest import SEED_OWNER_EMAIL, tenant_session

    # کالا باید در تراکنشی ساخته شود که واقعاً commit می‌شود. fixture `db` با
    # join_transaction_mode="create_savepoint" کار می‌کند، پس commit روی آن فقط تا
    # savepoint می‌رود و برای نخ‌های دیگر نامرئی می‌ماند.
    warehouse_id = warehouse.id
    with tenant_session(tenant_id) as setup:
        shared = Item(sku="IDEM-CONC", name="کالای همزمانی", unit="عدد", sales_price=5000)
        setup.add(shared)
        setup.commit()
        item_id = shared.id

    key = fresh_key()
    barrier = threading.Barrier(2)
    results: list = []
    errors: list = []

    def submit():
        try:
            with tenant_session(tenant_id) as session:
                from app.schemas.invoices import PurchaseInvoiceIn
                from app.services.idempotency import idempotent

                user = session.query(User).filter(User.email == SEED_OWNER_EMAIL).one()
                data = PurchaseInvoiceIn.model_validate(
                    {
                        "invoice_date": TODAY,
                        "warehouse_id": str(warehouse_id),
                        "contact_id": None,
                        "description": "همزمان",
                        "lines": [{"item_id": str(item_id), "qty": 3, "unit_cost": 500, "description": ""}],
                    }
                )

                class FakeRequest:
                    headers = {HEADER: key}

                barrier.wait(timeout=10)  # هر دو نخ دقیقاً با هم شروع کنند
                from app.services.inventory import post_purchase_invoice

                out = idempotent(
                    session,
                    FakeRequest(),
                    user,
                    operation="create_purchase_invoice",
                    payload=data,
                    run=lambda: post_purchase_invoice(session, data, user),
                    replay=lambda rid: session.get(PurchaseInvoice, rid),
                )
                session.commit()
                results.append(out.id)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=submit) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    try:
        # یکی موفق می‌شود؛ دومی یا همان شناسه را بازپخش می‌کند یا ۴۰۹ می‌گیرد.
        # هر دو درست‌اند — چیزی که مجاز نیست، دو فاکتور است.
        assert len(results) + len(errors) == 2, f"خطاها: {[repr(e) for e in errors]}"
        if len(results) == 2:
            assert results[0] == results[1], "دو فاکتور جدا ساخته شد — محافظت کار نکرد"

        with tenant_session(tenant_id) as check:
            made = check.query(PurchaseInvoice).filter(PurchaseInvoice.description == "همزمان").count()
            assert made == 1, f"{made} فاکتور ساخته شد، انتظار ۱"
    finally:
        with tenant_session(tenant_id) as cleanup:
            for inv in cleanup.query(PurchaseInvoice).filter(PurchaseInvoice.description == "همزمان").all():
                cleanup.delete(inv)
            cleanup.query(IdempotencyKey).filter(IdempotencyKey.key == key).delete()
            for it in cleanup.query(Item).filter(Item.sku == "IDEM-CONC").all():
                cleanup.query(StockLedger).filter(StockLedger.item_id == it.id).delete()
                cleanup.delete(it)
            cleanup.commit()
