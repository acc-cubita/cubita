"""نوشتن از مسیر کامل HTTP.

این پرونده به این دلیل وجود دارد که یک باگ واقعی از زیر ۲۷۱ تست رد شد.

زمینه‌ی مستأجر روی ContextVar نگه داشته می‌شد. FastAPI اندپوینت‌های sync را در
threadpool اجرا می‌کند و هر dependency در نخ خودش با یک *کپی* از زمینه کار می‌کند،
پس مقداری که در get_principal ست می‌شد هرگز به نخ اندپوینت نمی‌رسید. خواندن‌ها
درست کار می‌کردند — آن‌ها زمینه را از اتصال پایگاه‌داده می‌گیرند نه از پایتون — ولی
هر *نوشتنی* در production می‌شکست.

هیچ‌کدام از تست‌های موجود این را نگرفتند چون همه‌شان یا سرویس را مستقیم صدا می‌زنند
یا get_principal را override می‌کنند. درس: مسیر واقعیِ dependency باید حداقل یک‌بار
واقعاً اجرا شود، وگرنه هر چیزی که فقط در آن مسیر می‌شکند نامرئی می‌ماند.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.inventory import Warehouse
from app.security import create_access_token

from tests.conftest import SEED_OWNER_EMAIL


@pytest.fixture
def real_auth_client(db, user, tenant_id):
    """کلاینتی که get_principal واقعی را اجرا می‌کند — بدون override احراز هویت.

    فقط get_db جایگزین می‌شود تا تست در همان تراکنشِ برگشت‌پذیر بماند؛ زنجیره‌ی
    هویت و زمینه‌ی مستأجر دست‌نخورده اجرا می‌شود، که دقیقاً همان چیزی است که
    باگ در آن پنهان شده بود.
    """
    from app.tenant_context import get_current_tenant, set_current_tenant

    app.dependency_overrides[get_db] = lambda: db
    token = create_access_token(user.id, tenant_id)

    # ContextVar عمداً خالی می‌شود. fixture `db` آن را از قبل پر می‌کند و همان
    # پر بودن، باگ اصلی را پوشانده بود: در سرور واقعی هیچ‌چیز از قبل ستش نمی‌کند،
    # پس تستی که رویش حساب کند، شکستِ production را نمی‌بیند.
    previous = get_current_tenant()
    set_current_tenant(None)
    try:
        client = TestClient(app)
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client
    finally:
        set_current_tenant(previous)
        app.dependency_overrides.clear()


def test_manual_journal_entry_can_be_written_through_http(real_auth_client, db):
    """ثبت سند دستی: کوتاه‌ترین مسیر نوشتنی که به شماره‌گذاری و مهر مستأجر نیاز دارد."""
    from app.models.accounting import Account

    cash = db.query(Account).filter(Account.system_role == "cash").one()
    capital = db.query(Account).filter(Account.code == "3101").one()

    res = real_auth_client.post(
        "/api/journal-entries",
        json={
            "entry_date": "2026-09-01",
            "description": "تست نوشتن از مسیر HTTP",
            "lines": [
                {"account_id": str(cash.id), "debit": 1000, "credit": 0, "description": ""},
                {"account_id": str(capital.id), "debit": 0, "credit": 1000, "description": ""},
            ],
        },
    )
    assert res.status_code == 201, f"نوشتن از مسیر HTTP شکست خورد: {res.status_code} {res.text[:300]}"
    body = res.json()
    assert body["number"] is not None, "سند شماره‌ی رسمی نگرفت"


def test_sales_invoice_can_be_written_through_http(real_auth_client, db, user):
    """مسیر کامل: شماره‌گذاری، مهر مستأجر روی چند جدول، و سیاست WITH CHECK."""
    from decimal import Decimal

    from tests.factories import make_item

    item = make_item(db, sales_price=Decimal(500_000))
    warehouse = db.query(Warehouse).filter(Warehouse.code == "MAIN").one()

    # اول موجودی بده
    buy = real_auth_client.post(
        "/api/purchase-invoices",
        json={
            "invoice_date": "2026-09-01",
            "warehouse_id": str(warehouse.id),
            "lines": [{"item_id": str(item.id), "qty": 5, "unit_cost": 200_000}],
        },
    )
    assert buy.status_code == 201, f"فاکتور خرید شکست خورد: {buy.text[:300]}"

    sell = real_auth_client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": "2026-09-02",
            "warehouse_id": str(warehouse.id),
            "lines": [{"item_id": str(item.id), "qty": 2, "unit_price": 500_000}],
        },
    )
    assert sell.status_code == 201, f"فاکتور فروش شکست خورد: {sell.text[:300]}"
    assert sell.json()["total_amount"] == "1000000"


def test_written_rows_carry_the_right_tenant(real_auth_client, db, tenant_id):
    """مهر مستأجر باید خودکار خورده باشد، نه اینکه سرویس دستی ستش کرده باشد."""
    from app.models.accounting import Account, JournalEntry

    cash = db.query(Account).filter(Account.system_role == "cash").one()
    capital = db.query(Account).filter(Account.code == "3101").one()

    res = real_auth_client.post(
        "/api/journal-entries",
        json={
            "entry_date": "2026-09-03",
            "description": "بررسی مهر مستأجر",
            "lines": [
                {"account_id": str(cash.id), "debit": 500, "credit": 0, "description": ""},
                {"account_id": str(capital.id), "debit": 0, "credit": 500, "description": ""},
            ],
        },
    )
    assert res.status_code == 201

    entry = db.query(JournalEntry).filter(JournalEntry.id == res.json()["id"]).one()
    assert entry.tenant_id == tenant_id, "سند با مستأجر اشتباه ثبت شد"
    for line in entry.lines:
        assert line.tenant_id == tenant_id, "ردیف سند مهر مستأجر نخورد"
