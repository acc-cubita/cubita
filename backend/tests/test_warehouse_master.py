"""انبار به‌عنوان داده‌ی پایه — نگاشتِ حساب، فعال‌بودن، و مرزهایش.

قیدِ اصلی که این فایل نگه می‌دارد: **انبار رکوردِ دارای موجودی نیست.** ساختنش
هیچ سندی نمی‌زند و هیچ موجودی‌ای نمی‌سازد؛ موجودی همیشه از حرکاتِ انبار می‌آید.
این اصلِ پایه‌ی کلِ فصلِ انبار است و اگر روزی بشکند، بقیه‌ی گزارش‌ها یکی‌یکی
دروغ می‌گویند.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.inventory import StockLedger, Warehouse
from app.schemas.inventory import StockAdjustmentIn
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.services import chart_codes as cc
from app.services import warehouses as svc
from app.services.common import get_account
from app.services.inventory import post_purchase_invoice, post_stock_adjustment
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 6, 1)


def _warehouse(db, code="W-2", name="انبار مواد اولیه", **kw) -> Warehouse:
    warehouse = Warehouse(code=code, name=name, **kw)
    db.add(warehouse)
    db.flush()
    return warehouse


def _scrap_account(db) -> Account:
    """حسابِ جدا برای موجودیِ یک انبارِ خاص — زیرِ همان والدِ موجودیِ کالا."""
    inventory = get_account(db, cc.INVENTORY)
    account = Account(
        code="11059", name="موجودی انبار ضایعات", type=inventory.type,
        is_group=False, parent_id=inventory.parent_id,
    )
    db.add(account)
    db.flush()
    return account


def _buy(db, user, warehouse, amount=1_000_000):
    item = make_item(db)
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=warehouse.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_cost=Decimal(amount))],
        ),
        user,
    ), item


def _entry_accounts(db, entry_id) -> set:
    return {line.account_id for line in db.query(JournalLine).filter(JournalLine.entry_id == entry_id).all()}


# ───────────────────────── انبار موجودی ندارد (§۲ §۱۸ §۳۲) ────────────────────


def test_creating_a_warehouse_moves_nothing(db, user):
    """**قیدِ اصلی.** تعریفِ انبار نه سند می‌زند، نه موجودی می‌سازد."""
    before_entries = db.query(JournalEntry).count()
    before_moves = db.query(StockLedger).count()

    _warehouse(db, code="W-NEW", name="انبار تازه")

    assert db.query(JournalEntry).count() == before_entries
    assert db.query(StockLedger).count() == before_moves


def test_the_warehouse_model_has_no_stock_column(db):
    """§۲ — موجودی یکی از ابعادِ انبار است، نه ستونی رویش.

    این تست عمداً ساختار را می‌سنجد نه رفتار را: اگر روزی کسی «برای سرعت» یک
    ستونِ موجودی اضافه کند، همان لحظه قرمز می‌شود.
    """
    columns = {c.name for c in Warehouse.__table__.columns}
    assert not {"stock", "quantity", "balance", "opening_balance"} & columns


# ───────────────────────── معینِ انبار (§۹ §۱۰ §۱۱ §۱۳) ───────────────────────


def test_without_a_mapping_the_default_inventory_account_is_used(db, user):
    """§۱۳ — نگاشت اختیاری است، و نبودنش دقیقاً رفتارِ امروزِ کوبیتاست.

    این مهم‌ترین خاصیتِ سازگاری است: هیچ مستأجری با افزودنِ این قابلیت رفتارش
    عوض نمی‌شود.
    """
    warehouse = main_warehouse(db)
    assert warehouse.gl_account_id is None
    assert svc.inventory_account_id(db, warehouse.id) == get_account(db, cc.INVENTORY).id


def test_a_mapped_warehouse_posts_to_its_own_account(db, user):
    """§۹ — انبارِ ضایعات و انبارِ مواد اولیه دیگر در دفتر یکی نیستند."""
    account = _scrap_account(db)
    warehouse = _warehouse(db, code="W-SCRAP", name="انبار ضایعات", gl_account_id=account.id)

    invoice, _ = _buy(db, user, warehouse)

    accounts = _entry_accounts(db, invoice.journal_entry_id)
    assert account.id in accounts
    assert get_account(db, cc.INVENTORY).id not in accounts


def test_two_warehouses_can_share_one_account(db, user):
    """§۱۴ — سیاستِ تجمیعی باید ممکن بماند؛ قیدِ یکتایی نگذاشتیم."""
    account = _scrap_account(db)
    first = _warehouse(db, code="W-A", name="انبار الف", gl_account_id=account.id)
    second = _warehouse(db, code="W-B", name="انبار ب", gl_account_id=account.id)

    assert svc.inventory_account_id(db, first.id) == account.id
    assert svc.inventory_account_id(db, second.id) == account.id


def test_a_group_account_is_refused_as_a_mapping(db):
    """حسابِ گروه ردیفِ سند نمی‌پذیرد؛ ردش این‌جا بهتر از شکستنِ اولین رسید است."""
    group = db.query(Account).filter(Account.is_group.is_(True)).first()
    with pytest.raises(HTTPException) as err:
        svc.assert_postable_account(db, group.id)
    assert "حسابِ گروه" in err.value.detail


def test_an_account_owned_by_another_module_is_refused(db):
    """**کشفِ آزمونِ زنده.** اولین باری که نگاشت را روی داده‌ی واقعی امتحان کردم،
    توانستم انبار را به حسابِ «صندوق» وصل کنم.

    نتیجه‌اش این بود که موتورِ خزانه و موتورِ انبار روی یک حساب بنویسند با دو
    معنی، و ماندهٔ صندوق بی‌صدا با بهای کالا قاطی شود. هیچ ترازی هم به‌هم
    نمی‌خورد که خبر بدهد.
    """
    cash = get_account(db, cc.CASH)
    with pytest.raises(HTTPException) as err:
        svc.assert_postable_account(db, cash.id)
    assert "حسابِ سیستمی" in err.value.detail

    #: ولی خودِ حسابِ موجودی باید بماند — همان پیش‌فرضِ انبارِ بی‌نگاشت است.
    svc.assert_postable_account(db, get_account(db, cc.INVENTORY).id)


def test_changing_the_mapping_leaves_old_entries_alone(db, user):
    """**§۳۴ — گذشته بازنویسی نمی‌شود.**

    حساب در لحظه‌ی ثبت روی ردیفِ سند می‌نشیند و سند تغییرناپذیر است. تغییرِ
    نگاشت فقط روی ثبت‌های آینده اثر دارد.
    """
    warehouse = _warehouse(db, code="W-MAP", name="انبار نگاشت")
    old_invoice, _ = _buy(db, user, warehouse)
    old_accounts = _entry_accounts(db, old_invoice.journal_entry_id)
    assert get_account(db, cc.INVENTORY).id in old_accounts

    account = _scrap_account(db)
    warehouse.gl_account_id = account.id
    db.flush()

    new_invoice, _ = _buy(db, user, warehouse)
    assert account.id in _entry_accounts(db, new_invoice.journal_entry_id)
    #: و سندِ قدیمی همان است که بود.
    assert _entry_accounts(db, old_invoice.journal_entry_id) == old_accounts


# ───────────────────────── فعال / غیرفعال (§۱۵ §۱۷) ───────────────────────────


def test_an_inactive_warehouse_is_refused_everywhere(db, user):
    """§۱۵ — «غیرفعال» یک قاعده است، نه برچسب.

    تا پیش از این فقط رسیدِ انبارِ خرید این پرچم را می‌سنجید؛ فاکتور فروش،
    فاکتور خرید، تعدیل و انتقال همگی انبارِ غیرفعال را می‌پذیرفتند.
    """
    warehouse = _warehouse(db, code="W-OFF", name="انبار بسته", is_active=False)
    item = make_item(db)

    with pytest.raises(HTTPException) as err:
        post_purchase_invoice(
            db,
            PurchaseInvoiceIn(
                invoice_date=TODAY,
                warehouse_id=warehouse.id,
                lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_cost=Decimal(1000))],
            ),
            user,
        )
    assert "غیرفعال است" in err.value.detail

    with pytest.raises(HTTPException):
        post_stock_adjustment(
            db,
            StockAdjustmentIn(
                item_id=item.id, warehouse_id=warehouse.id, qty_diff=Decimal(1),
                reason="آزمون", adjustment_date=TODAY,
            ),
            user,
        )


def test_history_still_knows_an_inactive_warehouse(db, user):
    """§۱۵ — غیرفعال‌کردن گذشته را پاک نمی‌کند؛ فقط جلوی ثبتِ تازه را می‌گیرد."""
    warehouse = _warehouse(db, code="W-HIST", name="انبار تاریخی")
    invoice, item = _buy(db, user, warehouse)

    #: کالا را خارج می‌کنیم تا غیرفعال‌سازی مجاز شود.
    post_stock_adjustment(
        db,
        StockAdjustmentIn(
            item_id=item.id, warehouse_id=warehouse.id, qty_diff=Decimal(-1),
            reason="تخلیه", adjustment_date=TODAY,
        ),
        user,
    )
    warehouse.is_active = False
    db.flush()

    moves = db.query(StockLedger).filter(StockLedger.warehouse_id == warehouse.id).all()
    assert len(moves) == 2
    assert db.get(JournalEntry, invoice.journal_entry_id) is not None


def test_a_warehouse_with_stock_cannot_be_deactivated(db, user):
    """**§۱۷ — موجودی نباید بی‌صدا سرگردان شود.**

    کالا در انبارِ غیرفعال گیر می‌افتد: نه از آن خارج می‌شود نه به آن وارد.
    پیام تعداد را می‌گوید و راهِ خروج را هم.
    """
    warehouse = _warehouse(db, code="W-FULL", name="انبار پر")
    _buy(db, user, warehouse)

    with pytest.raises(HTTPException) as err:
        svc.assert_can_deactivate(db, warehouse)
    assert err.value.status_code == 409
    assert "۱ قلم کالا" in err.value.detail
    assert "منتقل" in err.value.detail


def test_an_empty_warehouse_can_be_deactivated(db, user):
    """گارد نباید بن‌بست بسازد: انبارِ خالی بدونِ اعتراض غیرفعال می‌شود."""
    warehouse = _warehouse(db, code="W-EMPTY", name="انبار خالی")
    svc.assert_can_deactivate(db, warehouse)  # نباید چیزی پرتاب کند


def test_a_netted_out_warehouse_counts_as_empty(db, user):
    """موجودیِ صفر یعنی خالی، حتی اگر ده حرکت داشته باشد.

    شمارش از جمعِ حرکات می‌آید نه از تعدادِ ردیف‌ها — همان منبعی که موجودی از
    آن می‌آید، نه شمارشِ دومی که بتواند با آن اختلاف پیدا کند.
    """
    warehouse = _warehouse(db, code="W-NET", name="انبار خنثی")
    _, item = _buy(db, user, warehouse)
    post_stock_adjustment(
        db,
        StockAdjustmentIn(
            item_id=item.id, warehouse_id=warehouse.id, qty_diff=Decimal(-1),
            reason="تخلیه", adjustment_date=TODAY,
        ),
        user,
    )

    assert svc.stock_positions(db, warehouse.id) == []
    svc.assert_can_deactivate(db, warehouse)


# ───────────────────────── فهرست و اندپوینت (§۲۹) ─────────────────────────────


def test_the_row_shows_the_default_account_and_says_so(db):
    """§۲۹ — نشان‌ندادنِ حساب یعنی کاربر فکر کند این انبار به هیچ حسابی نمی‌نشیند."""
    row = svc.row(db, main_warehouse(db))
    assert row["gl_account_id"] is None
    assert row["gl_account_is_default"] is True
    assert row["gl_account_code"] == get_account(db, cc.INVENTORY).code


def test_the_endpoints_carry_the_new_fields(db, user, client):
    created = client.post(
        "/api/warehouses",
        json={
            "code": "W-API", "name": "انبار محصول نهایی", "name2": "Finished Goods",
            "responsible": "رضا کریمی", "phone": "021-1234", "address": "تهران",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name2"] == "Finished Goods"
    assert body["responsible"] == "رضا کریمی"
    assert body["gl_account_is_default"] is True

    listed = client.get("/api/warehouses").json()
    assert any(w["code"] == "W-API" and w["gl_account_code"] for w in listed)


def test_deactivating_a_full_warehouse_is_refused_by_the_endpoint(db, user, client):
    """همان گارد، از مسیرِ واقعیِ رابط."""
    warehouse = _warehouse(db, code="W-EP", name="انبار اندپوینت")
    _buy(db, user, warehouse)
    db.commit()

    positions = client.get(f"/api/warehouses/{warehouse.id}/stock-positions").json()
    assert positions["item_count"] == 1

    refused = client.patch(f"/api/warehouses/{warehouse.id}", json={"is_active": False})
    assert refused.status_code == 409
    #: و انبار همچنان فعال است — گارد قبل از نوشتن شلیک کرده.
    assert client.get("/api/warehouses").json()
    db.rollback()
