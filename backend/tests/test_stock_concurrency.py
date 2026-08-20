"""همزمانی موجودی.

این تست‌ها fixture `db` را استفاده نمی‌کنند: آن یک تراکنش واحد است و ذاتاً نمی‌تواند
رقابت دو تراکنش موازی را نشان دهد. اینجا دو session واقعی و هم‌زمان باز می‌شود، هرکدام
با زمینه‌ی مستأجر خودشان — بدون آن، سیاست RLS هر نوشتنی را رد می‌کند.

**چرا با barrier و نه فقط دو نخ:** پنجره‌ی رقابت واقعی چند میلی‌ثانیه است، پس دو نخِ
ساده معمولاً پشت‌سرهم اجرا می‌شوند و تست از روی شانس سبز می‌ماند — یعنی تستی که باگ
را نمی‌گیرد. barrier هر دو تراکنش را وادار می‌کند *قبل از* اینکه یکی بنویسد، موجودی
را خوانده باشند. این دقیقاً همان حالتی است که زیر بار واقعی رخ می‌دهد، فقط قطعی.
"""
import threading
import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.accounting import JournalEntry, JournalLine
from app.models.advanced_inventory import StockBatch
from app.models.inventory import Item, StockLedger, Warehouse
from app.models.invoices import PurchaseInvoice, PurchaseInvoiceLine, SalesInvoice, SalesInvoiceLine
from app.models.user import User
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.services import inventory as inventory_service

from tests.conftest import SEED_OWNER_EMAIL, tenant_session

SALE_DATE = date(2026, 5, 20)
STARTING_STOCK = 10
EACH_SALE = 6  # دو تا از این‌ها با هم از موجودی بیشتر می‌شود

#: مستأجر جاری این ماژول. نخ‌های کارگر تابع ماژول‌اند و به fixture دسترسی ندارند،
#: پس شناسه از اینجا خوانده می‌شود.
_TENANT: list = [None]


@pytest.fixture(autouse=True)
def _bind_tenant(tenant_id):
    _TENANT[0] = tenant_id
    yield
    _TENANT[0] = None


def _owner(session) -> User:
    return session.query(User).filter(User.email == SEED_OWNER_EMAIL).one()


def _purge_items(*item_ids) -> None:
    """پاک‌سازی به‌ترتیب وابستگی کلید خارجی.

    نکته: یک فاکتور می‌تواند چند کالا داشته باشد، پس باید *همه‌ی* ردیف‌های فاکتورهای
    درگیر حذف شوند، نه فقط ردیف‌های کالای موردنظر — وگرنه فاکتور با ردیف باقی‌مانده
    می‌ماند و حذفش FK را نقض می‌کند.
    """
    ids = list(item_ids)
    with tenant_session(_TENANT[0]) as session:
        entry_ids: list = []
        for inv_model, line_model in ((SalesInvoice, SalesInvoiceLine), (PurchaseInvoice, PurchaseInvoiceLine)):
            inv_ids = [
                row[0]
                for row in session.query(inv_model.id)
                .join(line_model, line_model.invoice_id == inv_model.id)
                .filter(line_model.item_id.in_(ids))
                .distinct()
            ]
            if not inv_ids:
                continue
            entry_ids += [
                row[0] for row in session.query(inv_model.journal_entry_id).filter(inv_model.id.in_(inv_ids))
            ]
            session.query(line_model).filter(line_model.invoice_id.in_(inv_ids)).delete(synchronize_session=False)
            session.query(inv_model).filter(inv_model.id.in_(inv_ids)).delete(synchronize_session=False)

        session.query(StockLedger).filter(StockLedger.item_id.in_(ids)).delete(synchronize_session=False)
        # هر خرید حالا یک بارِ ورودی (StockBatch) می‌سازد که به کالا FK دارد؛ پیش از حذفِ کالا
        # پاک شود (سریال‌های کارتنش با ondelete CASCADE خودکار می‌روند).
        session.query(StockBatch).filter(StockBatch.item_id.in_(ids)).delete(synchronize_session=False)
        session.query(Item).filter(Item.id.in_(ids)).delete(synchronize_session=False)

        entry_ids = [e for e in entry_ids if e is not None]
        if entry_ids:
            session.query(JournalLine).filter(JournalLine.entry_id.in_(entry_ids)).delete(synchronize_session=False)
            session.query(JournalEntry).filter(JournalEntry.id.in_(entry_ids)).delete(synchronize_session=False)
        session.commit()


def _stock_items(specs: list[tuple[str, int, int]]):
    """کالاها را می‌سازد و با یک فاکتور خرید موجودی می‌دهد."""
    with tenant_session(_TENANT[0]) as session:
        user = _owner(session)
        warehouse = session.query(Warehouse).filter(Warehouse.code == "MAIN").one()
        created = []
        for name, qty, cost in specs:
            item = Item(sku=f"CONC-{uuid.uuid4().hex[:8]}", name=name, sales_price=Decimal(1_000_000))
            session.add(item)
            session.flush()
            created.append((item, qty, cost))
        inventory_service.post_purchase_invoice(
            session,
            PurchaseInvoiceIn(
                invoice_date=date(2026, 5, 1),
                warehouse_id=warehouse.id,
                lines=[
                    PurchaseInvoiceLineIn(item_id=i.id, qty=Decimal(q), unit_cost=Decimal(c)) for i, q, c in created
                ],
            ),
            user,
        )
        session.commit()
        return [i.id for i, _, _ in created], warehouse.id


@pytest.fixture
def stocked_item():
    ids, warehouse_id = _stock_items([("کالای تست همزمانی", STARTING_STOCK, 500_000)])
    yield ids[0], warehouse_id
    _purge_items(ids[0])


@pytest.fixture
def two_stocked_items():
    ids, warehouse_id = _stock_items([("کالا الف", 100, 50), ("کالا ب", 100, 50)])
    yield ids[0], ids[1], warehouse_id
    _purge_items(ids[0], ids[1])


def _sell(item_ids, warehouse_id, qty: int, errors: list):
    """در session مستقل خودش می‌فروشد — تراکنش جدا، مثل دو درخواست موازی."""
    with tenant_session(_TENANT[0]) as session:
        try:
            inventory_service.post_sales_invoice(
                session,
                SalesInvoiceIn(
                    invoice_date=SALE_DATE,
                    warehouse_id=warehouse_id,
                    lines=[
                        SalesInvoiceLineIn(item_id=i, qty=Decimal(qty), unit_price=Decimal(1_000_000))
                        for i in item_ids
                    ],
                ),
                _owner(session),
            )
            session.commit()
        except Exception as exc:  # noqa: BLE001 - می‌خواهیم بدانیم کدام تلاش رد شد
            session.rollback()
            errors.append(f"{type(exc).__name__}: {exc}"[:140])


def test_shared_items_in_opposite_order_do_not_deadlock(two_stocked_items):
    """کلاسیک‌ترین حالت deadlock: دو فاکتور هم‌زمان روی کالاهای مشترک، به ترتیب معکوس.

    قفل باید با ترتیب قطعی (ORDER BY id) گرفته شود؛ بدون آن پایگاه‌داده یکی از دو
    تراکنش را با DeadlockDetected می‌کشد و کاربر خطای بی‌ربط می‌گیرد.
    """
    a_id, b_id, warehouse_id = two_stocked_items
    errors: list = []

    threads = [
        threading.Thread(target=_sell, args=([a_id, b_id], warehouse_id, 1, errors)),
        threading.Thread(target=_sell, args=([b_id, a_id], warehouse_id, 1, errors)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert errors == [], f"هر دو فاکتور باید موفق می‌شدند، ولی: {errors}"


def test_parallel_sales_cannot_oversell(stocked_item, monkeypatch):
    """موجودی ۱۰، دو فروش هم‌زمان ۶تایی: دقیقاً یکی باید رد شود."""
    item_id, warehouse_id = stocked_item
    errors: list = []
    # وقتی قفل سطری سر جایش باشد نخ دوم پشت قفل می‌ماند و اصلاً به barrier نمی‌رسد،
    # پس timeout شدنِ barrier نشانه‌ی سلامت است نه خرابی — فقط باید کوتاه باشد.
    barrier = threading.Barrier(2, timeout=3)
    real_get_stock_qty = inventory_service.get_stock_qty

    def synced_get_stock_qty(db, i_id, w_id):
        """بعد از خواندن موجودی منتظر می‌ماند تا نخ دیگر هم خوانده باشد."""
        qty = real_get_stock_qty(db, i_id, w_id)
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            pass
        return qty

    monkeypatch.setattr(inventory_service, "get_stock_qty", synced_get_stock_qty)

    threads = [threading.Thread(target=_sell, args=([item_id], warehouse_id, EACH_SALE, errors)) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=40)
    barrier.abort()

    with tenant_session(_TENANT[0]) as check:
        remaining = real_get_stock_qty(check, item_id, warehouse_id)

    assert remaining >= 0, (
        f"موجودی منفی شد ({remaining}): هر دو فروش {EACH_SALE}تایی از موجودی {STARTING_STOCK} پاس شدند "
        "— کالایی فروخته شد که وجود نداشت"
    )
    assert len(errors) == 1, f"باید دقیقاً یک فروش رد می‌شد، ولی {len(errors)} تا رد شد: {errors}"
