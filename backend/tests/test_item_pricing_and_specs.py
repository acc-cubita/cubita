"""گروه‌بندی، مشخصات و قیمتِ چندبُعدی (§۳۴–§۴۳).

سه ادعا:

  ۱. گروه یک رکورد است نه یک متن، و `category` پرتوِ نامِ آن.
  ۲. مشخصه‌ها ستونِ ثابتِ کالا نیستند — تعریف ← مقدار.
  ۳. یک کالا می‌تواند چند قیمت داشته باشد، و مشخص‌ترین قاعده می‌برد. ولی
     قیمتِ فاکتورِ دیروز با عوض‌شدنِ اعلامیه تغییر نمی‌کند.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.advanced_inventory import PriceList, PriceListItem
from app.models.inventory import Contact, ItemAttribute, ItemGroup, Item
from app.models.sales_ops import SaleType
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.services import items as items_svc
from app.services import pricing
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from tests.factories import main_warehouse, make_contact, make_item

TODAY = date(2026, 3, 15)


def stock(db, user, item, qty=100):
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(1))],
        ),
        user,
    )


def announcement(db, user, rows, *, on=TODAY, name="اعلامیه"):
    price_list = PriceList(name=name, effective_from=on, created_by_id=user.id)
    db.add(price_list)
    db.flush()
    for row in rows:
        db.add(PriceListItem(price_list_id=price_list.id, **row))
    db.flush()
    return price_list


# ───────────────────────── گروه‌بندی (§۳۴) ─────────────────────────


def test_a_group_is_a_record_not_a_string(db, user):
    """متنِ آزاد گزارشِ گروهی را غیرقابل‌اعتماد می‌کرد."""
    group = items_svc.group_get_or_create(db, "لوازم خانگی")
    assert items_svc.group_get_or_create(db, "لوازم خانگی").id == group.id
    assert isinstance(group, ItemGroup)


def test_the_category_text_follows_the_group(db, user):
    """`category` از این پس پرتوِ نامِ گروه است، نه منبعِ حقیقت."""
    group = items_svc.group_get_or_create(db, "لوازم خانگی")
    item = make_item(db, name="یخچال", group_id=group.id)
    items_svc.sync_item_category(db, item)
    assert item.category == "لوازم خانگی"


def test_a_closed_group_is_not_offered(db, user):
    group = items_svc.group_get_or_create(db, "بایگانی")
    group.is_active = False
    db.flush()
    with pytest.raises(HTTPException) as err:
        items_svc.assert_group_usable(db, group.id)
    assert err.value.status_code == 400


def test_a_blank_group_name_is_refused(db, user):
    with pytest.raises(HTTPException):
        items_svc.group_get_or_create(db, "  ")


# ───────────────────────── مشخصات (§۳۵ §۳۶) ─────────────────────────


def test_specs_are_not_columns_on_the_item(db, user):
    """§۳۶ — «برای هر مشخصه ستون جدید در جدول Product نسازیم»."""
    columns = {c.name for c in Item.__table__.columns}
    assert not ({"color", "size", "brand", "material"} & columns)


def test_a_spec_value_is_stored_and_read_back(db, user):
    color = ItemAttribute(name="رنگ")
    size = ItemAttribute(name="سایز")
    db.add_all([color, size])
    db.flush()
    item = make_item(db, name="لیوان")

    items_svc.set_attributes(
        db,
        item,
        [
            {"attribute_id": color.id, "value": "قرمز"},
            {"attribute_id": size.id, "value": "بزرگ"},
        ],
    )
    rows = {row["attribute_name"]: row["value"] for row in items_svc.attribute_rows(db, item)}
    assert rows == {"رنگ": "قرمز", "سایز": "بزرگ"}


def test_an_empty_value_removes_the_row(db, user):
    """نگه‌داشتنِ ردیفِ تهی یعنی فهرستِ مشخصات پر از خطوطِ بی‌معنا شود."""
    color = ItemAttribute(name="رنگ")
    db.add(color)
    db.flush()
    item = make_item(db, name="لیوان")

    items_svc.set_attributes(db, item, [{"attribute_id": color.id, "value": "قرمز"}])
    items_svc.set_attributes(db, item, [{"attribute_id": color.id, "value": "  "}])
    assert items_svc.attribute_rows(db, item) == []


def test_an_unknown_attribute_is_refused(db, user):
    from uuid import uuid4

    item = make_item(db, name="لیوان")
    with pytest.raises(HTTPException) as err:
        items_svc.set_attributes(db, item, [{"attribute_id": uuid4(), "value": "x"}])
    assert err.value.status_code == 404


# ───────────────────── قیمتِ چندبُعدی (§۳۷–§۴۳) ─────────────────────


def test_one_item_can_hold_several_prices(db, user):
    """§۳۸ — عمده به ریال، خرده به ریال، صادراتی به دلار؛ هم‌زمان."""
    item = make_item(db, name="لیوان")
    wholesale = SaleType(name="عمده")
    retail = SaleType(name="خرده")
    db.add_all([wholesale, retail])
    db.flush()

    announcement(
        db,
        user,
        [
            {"item_id": item.id, "price": Decimal(90), "sale_type_id": wholesale.id},
            {"item_id": item.id, "price": Decimal(100), "sale_type_id": retail.id},
            {"item_id": item.id, "price": Decimal(2), "currency_code": "USD"},
        ],
    )

    assert pricing.resolve(db, item.id, on=TODAY, sale_type_id=wholesale.id).price == 90
    assert pricing.resolve(db, item.id, on=TODAY, sale_type_id=retail.id).price == 100
    assert pricing.resolve(db, item.id, on=TODAY, currency_code="USD").price == 2


def test_the_most_specific_rule_wins(db, user):
    """قیمتِ عمومی نباید قیمتِ ویژه را بپوشاند."""
    item = make_item(db, name="لیوان")
    special = SaleType(name="صادراتی")
    db.add(special)
    db.flush()
    announcement(
        db,
        user,
        [
            {"item_id": item.id, "price": Decimal(100)},
            {"item_id": item.id, "price": Decimal(80), "sale_type_id": special.id},
        ],
    )
    assert pricing.resolve(db, item.id, on=TODAY, sale_type_id=special.id).price == 80
    # زمینه‌ای که قاعده‌ی ویژه ندارد، همان عمومی را می‌گیرد
    assert pricing.resolve(db, item.id, on=TODAY).price == 100


def test_a_price_can_belong_to_a_unit(db, user):
    """§۴۱ — «۱ عدد = ۱۰۰، ۱ کارتن = ۲٬۲۰۰»."""
    from app.models.inventory import UnitOfMeasure

    piece = db.query(UnitOfMeasure).filter(UnitOfMeasure.name == "عدد").one()
    carton = db.query(UnitOfMeasure).filter(UnitOfMeasure.name == "کارتن").one()
    item = make_item(db, name="لیوان")
    announcement(
        db,
        user,
        [
            {"item_id": item.id, "price": Decimal(100), "unit_id": piece.id},
            {"item_id": item.id, "price": Decimal(2_200), "unit_id": carton.id},
        ],
    )
    assert pricing.resolve(db, item.id, on=TODAY, unit_id=carton.id).price == 2_200


def test_a_price_can_belong_to_a_customer_group(db, user):
    from app.models.company import ContactGroup

    group = ContactGroup(name="مشتریانِ طلایی", created_by_id=user.id)
    db.add(group)
    db.flush()
    customer = make_contact(db, name="مشتری طلایی")
    customer.group_id = group.id
    db.flush()

    item = make_item(db, name="لیوان")
    announcement(
        db,
        user,
        [
            {"item_id": item.id, "price": Decimal(100)},
            {"item_id": item.id, "price": Decimal(85), "contact_group_id": group.id},
        ],
    )
    assert pricing.resolve(db, item.id, on=TODAY, contact_id=customer.id).price == 85


def test_an_untouched_price_row_still_matches_everything(db, user):
    """ردیف‌های موجود هر سه بُعدشان خالی است و نباید هیچ قیمتی گم شود."""
    item = make_item(db, name="لیوان")
    sale_type = SaleType(name="نقدی")
    db.add(sale_type)
    db.flush()
    announcement(db, user, [{"item_id": item.id, "price": Decimal(100)}])
    assert pricing.resolve(db, item.id, on=TODAY, sale_type_id=sale_type.id).price == 100


def test_a_future_announcement_is_not_used_yet(db, user):
    item = make_item(db, name="لیوان")
    announcement(db, user, [{"item_id": item.id, "price": Decimal(100)}], on=TODAY)
    announcement(
        db, user, [{"item_id": item.id, "price": Decimal(130)}], on=date(2026, 6, 1), name="بعدی"
    )
    assert pricing.resolve(db, item.id, on=TODAY).price == 100


# ───────────────── کنترلِ تغییرِ نرخ (§۴۲) و تاریخ (§۴۳) ─────────────────


def test_no_limit_by_default(db, user):
    """ردیف‌های موجود حد ندارند؛ هیچ فروشی یک‌شبه مسدود نمی‌شود."""
    item = make_item(db, name="لیوان")
    stock(db, user, item)
    announcement(db, user, [{"item_id": item.id, "price": Decimal(100)}])
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(10))],
        ),
        user,
    )


def test_a_discount_beyond_the_limit_is_refused(db, user):
    """§۴۲ — «جلوی تخفیفِ خارج از سیاستِ شرکت را بگیرد»."""
    item = make_item(db, name="لیوان")
    stock(db, user, item)
    announcement(
        db,
        user,
        [{"item_id": item.id, "price": Decimal(1_000), "max_decrease_percent": Decimal(10)}],
    )
    with pytest.raises(HTTPException) as err:
        post_sales_invoice(
            db,
            SalesInvoiceIn(
                invoice_date=TODAY,
                warehouse_id=main_warehouse(db).id,
                lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(800))],
            ),
            user,
        )
    assert err.value.status_code == 400
    assert "لیوان" in err.value.detail


def test_a_discount_within_the_limit_passes(db, user):
    item = make_item(db, name="لیوان")
    stock(db, user, item)
    announcement(
        db,
        user,
        [{"item_id": item.id, "price": Decimal(1_000), "max_decrease_percent": Decimal(10)}],
    )
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(950))],
        ),
        user,
    )


def test_a_locked_rate_refuses_any_change(db, user):
    item = make_item(db, name="لیوان")
    stock(db, user, item)
    announcement(
        db, user, [{"item_id": item.id, "price": Decimal(1_000), "allow_rate_change": False}]
    )
    with pytest.raises(HTTPException) as err:
        post_sales_invoice(
            db,
            SalesInvoiceIn(
                invoice_date=TODAY,
                warehouse_id=main_warehouse(db).id,
                lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(1_001))],
            ),
            user,
        )
    assert err.value.status_code == 400


def test_the_exact_rate_always_passes(db, user):
    item = make_item(db, name="لیوان")
    stock(db, user, item)
    announcement(
        db, user, [{"item_id": item.id, "price": Decimal(1_000), "allow_rate_change": False}]
    )
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(1_000))],
        ),
        user,
    )


def test_changing_the_policy_leaves_yesterdays_invoice_alone(db, user):
    """§۴۳ — «قیمتِ فاکتورِ دیروز نباید تغییر کند»."""
    item = make_item(db, name="لیوان")
    stock(db, user, item)
    price_list = announcement(db, user, [{"item_id": item.id, "price": Decimal(1_000)}])
    invoice = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_price=Decimal(1_000))],
        ),
        user,
    )
    before = Decimal(invoice.lines[0].unit_price)

    price_list.items[0].price = Decimal(5_000)
    db.flush()
    db.refresh(invoice)
    assert Decimal(invoice.lines[0].unit_price) == before == Decimal(1_000)


def test_an_item_without_a_rule_has_no_policy_to_break(db, user):
    item = make_item(db, name="بی‌اعلامیه")
    stock(db, user, item)
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(7))],
        ),
        user,
    )


def test_the_price_context_is_not_a_parallel_definition(db, user):
    """§۳۹ §۴۰ — نوعِ فروش، ارز و گروهِ مشتری از داده‌ی موجود می‌آیند."""
    columns = {c.name for c in PriceListItem.__table__.columns}
    assert {"sale_type_id", "contact_group_id", "unit_id", "currency_code"} <= columns
    # هیچ ستونِ متنیِ «نوع فروش» یا «گروه مشتری» ساخته نشده
    assert "sale_type" not in columns and "customer_group" not in columns
