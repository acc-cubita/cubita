"""انبارهای مرتبط، انبارِ پیش‌فرض و کنترلِ موجودی (§۲۴–§۳۳).

سه ادعا که هر سه راحت می‌شد اشتباه پیاده کرد:

  ۱. فهرستِ خالی یعنی «همه‌ی انبارها»، نه «هیچ انباری» — وگرنه هر کالای موجودی
     یک‌شبه غیرقابل‌استفاده می‌شد.
  ۲. انبارِ پیش‌فرض **مالکیت نیست**؛ کالا به آن قفل نمی‌شود.
  ۳. حداکثرِ موجودی **سدِ تراکنش نیست**، سیگنالِ برنامه‌ریزی است.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.inventory import ItemWarehouse
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.services import items as items_svc
from app.services.inventory import post_purchase_invoice
from tests.factories import main_warehouse, make_item, other_warehouse

TODAY = date(2026, 3, 15)


def buy(db, user, item, warehouse, *, qty=10, unit_cost=1_000_000):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=warehouse.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost))],
        ),
        user,
    )


# ─────────────────── فهرستِ خالی = همه‌ی انبارها (§۲۹) ───────────────────


def test_an_item_with_no_list_may_use_any_warehouse(db, user):
    """رفتارِ امروزِ کوبیتا؛ تفسیرِ دیگر هر کالای موجودی را می‌شکست."""
    item = make_item(db, name="لیوان")
    assert items_svc.allowed_warehouse_ids(db, item.id) == set()
    buy(db, user, item, main_warehouse(db))
    buy(db, user, item, other_warehouse(db))


def test_a_listed_item_is_refused_elsewhere(db, user):
    item = make_item(db, name="مواد اولیه")
    items_svc.set_warehouses(db, item, [{"warehouse_id": main_warehouse(db).id}])

    buy(db, user, item, main_warehouse(db))
    with pytest.raises(HTTPException) as err:
        buy(db, user, item, other_warehouse(db))
    assert err.value.status_code == 400
    assert "مواد اولیه" in err.value.detail


def test_a_service_is_never_restricted(db, user):
    """§۱۶ — خدمت اصلاً وارد انبار نمی‌شود؛ محدودکردنش بی‌معناست."""
    service = make_item(db, name="حمل", is_service=True)
    items_svc.set_warehouses(db, service, [{"warehouse_id": main_warehouse(db).id}])
    buy(db, user, service, other_warehouse(db))  # بدون خطا


def test_stock_already_there_is_never_stranded(db, user):
    """§۳۳ — حذفِ رابطه گذشته را پاک نمی‌کند، و نباید موجودی را هم زندانی کند.

    اگر خروج را هم ببندیم، کالا در انباری گیر می‌افتد که نه واردش می‌شود نه
    خارج — همان «سرگردانیِ موجودی» که فصلِ انبار منعش می‌کند.
    """
    item = make_item(db, name="لیوان")
    buy(db, user, item, other_warehouse(db), qty=5)

    items_svc.set_warehouses(db, item, [{"warehouse_id": main_warehouse(db).id}])
    # هنوز در انبارِ دوم موجودی دارد، پس عملیات روی همان انبار مجاز می‌ماند
    items_svc.assert_warehouse_allowed(db, item, other_warehouse(db).id)


def test_removing_a_link_leaves_the_ledger_alone(db, user):
    """§۳۳ — تاریخچه جای دیگری زندگی می‌کند."""
    from app.services.inventory import get_stock_qty

    item = make_item(db, name="لیوان")
    buy(db, user, item, other_warehouse(db), qty=7)
    before = get_stock_qty(db, item.id, other_warehouse(db).id)

    items_svc.set_warehouses(db, item, [{"warehouse_id": main_warehouse(db).id}])
    assert get_stock_qty(db, item.id, other_warehouse(db).id) == before == Decimal(7)


# ───────────────────── انبارِ پیش‌فرض (§۳۱ §۳۲) ─────────────────────


def test_the_default_is_a_suggestion_not_a_lock(db, user):
    """§۳۲ — «Default Warehouse ≠ Only Warehouse»."""
    item = make_item(db, name="لیوان")
    items_svc.set_warehouses(
        db,
        item,
        [
            {"warehouse_id": main_warehouse(db).id, "is_default": True},
            {"warehouse_id": other_warehouse(db).id},
        ],
    )
    assert items_svc.default_warehouse_id(db, item.id) == main_warehouse(db).id
    buy(db, user, item, other_warehouse(db))  # انبارِ غیرپیش‌فرض هم مجاز است


def test_only_one_warehouse_can_be_default(db, user):
    item = make_item(db, name="لیوان")
    with pytest.raises(HTTPException) as err:
        items_svc.set_warehouses(
            db,
            item,
            [
                {"warehouse_id": main_warehouse(db).id, "is_default": True},
                {"warehouse_id": other_warehouse(db).id, "is_default": True},
            ],
        )
    assert err.value.status_code == 400


def test_moving_the_default_does_not_trip_the_unique_index(db, user):
    """جابه‌جایی باید یک عملیات باشد، نه دو نوشتنِ متعارض."""
    item = make_item(db, name="لیوان")
    links = [
        {"warehouse_id": main_warehouse(db).id, "is_default": True},
        {"warehouse_id": other_warehouse(db).id},
    ]
    items_svc.set_warehouses(db, item, links)
    items_svc.set_warehouses(
        db,
        item,
        [
            {"warehouse_id": main_warehouse(db).id},
            {"warehouse_id": other_warehouse(db).id, "is_default": True},
        ],
    )
    assert items_svc.default_warehouse_id(db, item.id) == other_warehouse(db).id


def test_having_no_default_is_allowed(db, user):
    """§۳۲ — نبودِ پیش‌فرض یعنی «انتخاب نشده»، نه «کالا جایی ندارد»."""
    item = make_item(db, name="لیوان")
    items_svc.set_warehouses(db, item, [{"warehouse_id": main_warehouse(db).id}])
    assert items_svc.default_warehouse_id(db, item.id) is None


def test_an_unknown_warehouse_is_refused(db, user):
    from uuid import uuid4

    item = make_item(db, name="لیوان")
    with pytest.raises(HTTPException) as err:
        items_svc.set_warehouses(db, item, [{"warehouse_id": uuid4()}])
    assert err.value.status_code == 404


def test_the_link_is_many_to_many(db, user):
    """§۳۰ — یک کالا در چند انبار، و یک انبار پرِ چند کالا."""
    a = make_item(db, name="الف")
    b = make_item(db, name="ب")
    main, other = main_warehouse(db), other_warehouse(db)
    items_svc.set_warehouses(db, a, [{"warehouse_id": main.id}, {"warehouse_id": other.id}])
    items_svc.set_warehouses(db, b, [{"warehouse_id": main.id}])

    assert items_svc.allowed_warehouse_ids(db, a.id) == {main.id, other.id}
    in_main = db.query(ItemWarehouse).filter(ItemWarehouse.warehouse_id == main.id).count()
    assert in_main == 2


# ───────────────────── کنترلِ موجودی (§۲۴–§۲۸) ─────────────────────


def test_the_maximum_never_blocks_a_purchase(db, user):
    """§۲۶ — «نباید مانع قطعی ورود کالا شود»."""
    item = make_item(db, name="لیوان", max_stock=Decimal(5))
    buy(db, user, item, main_warehouse(db), qty=100)  # بدون خطا


def test_the_minimum_never_blocks_a_sale(db, user):
    """§۲۵ — حداقلِ موجودی سیگنال است، نه سد."""
    item = make_item(db, name="لیوان", min_stock=Decimal(20))
    buy(db, user, item, main_warehouse(db), qty=1)  # بدون خطا


def test_limits_fall_back_to_the_item(db, user):
    """§۲۸ — عددِ سراسری همان رفتارِ امروزِ نقطه‌ی سفارش است."""
    item = make_item(db, name="لیوان", min_stock=Decimal(10), max_stock=Decimal(50))
    items_svc.set_warehouses(db, item, [{"warehouse_id": main_warehouse(db).id}])
    assert items_svc.stock_limits(db, item, main_warehouse(db).id) == (Decimal(10), Decimal(50))


def test_a_warehouse_row_can_override_the_limits(db, user):
    """§۲۸ — ساختار هر دو تفسیر را می‌پذیرد و هیچ‌کدام را تحمیل نمی‌کند."""
    item = make_item(db, name="لیوان", min_stock=Decimal(10), max_stock=Decimal(50))
    items_svc.set_warehouses(
        db,
        item,
        [{"warehouse_id": main_warehouse(db).id, "min_stock": Decimal(2), "max_stock": Decimal(8)}],
    )
    assert items_svc.stock_limits(db, item, main_warehouse(db).id) == (Decimal(2), Decimal(8))
    # انباری که override ندارد همان عددِ کالا را می‌گیرد
    assert items_svc.stock_limits(db, item, other_warehouse(db).id) == (Decimal(10), Decimal(50))


def test_a_partial_override_only_replaces_what_it_sets(db, user):
    item = make_item(db, name="لیوان", min_stock=Decimal(10), max_stock=Decimal(50))
    items_svc.set_warehouses(
        db, item, [{"warehouse_id": main_warehouse(db).id, "max_stock": Decimal(8)}]
    )
    assert items_svc.stock_limits(db, item, main_warehouse(db).id) == (Decimal(10), Decimal(8))


def test_low_stock_separates_the_two_thresholds(db, user, client, grant_module):
    """§۲۵ — نقطه‌ی سفارش و حداقلِ موجودی دو مفهومِ جدا هستند.

    یکی‌کردنشان یعنی کاربر نفهمد چرا هشدار گرفته.
    """
    grant_module("inventory")
    item = make_item(db, name="لیوان", min_stock=Decimal(20))
    buy(db, user, item, main_warehouse(db), qty=5)
    db.commit()

    rows = client.get("/api/stock/low").json()
    mine = [r for r in rows if r["item_id"] == str(item.id)]
    assert mine and mine[0]["trigger"] == "min"
    assert Decimal(mine[0]["shortfall"]) == Decimal(15)


def test_over_stock_reports_the_excess(db, user, client, grant_module):
    grant_module("inventory")
    item = make_item(db, name="لیوان", max_stock=Decimal(5))
    buy(db, user, item, main_warehouse(db), qty=12)
    db.commit()

    rows = client.get("/api/stock/over").json()
    mine = [r for r in rows if r["item_id"] == str(item.id)]
    assert mine and Decimal(mine[0]["excess"]) == Decimal(7)
