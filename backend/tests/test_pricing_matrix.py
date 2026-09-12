"""اعلامیه‌ی قیمت به‌عنوان ماتریس — ورودپذیر، تک‌موتور، و غیرقابلِ پاک‌شدن.

پنج ادعا:

  ۱. یک کالا در سه نوعِ فروش سه قیمت دارد و حل‌کننده هر سه را می‌دهد — و
     انتخابِ برنده **قطعی** است، نه ترتیبِ دیتابیس.
  ۲. سیاستِ نرخ و سیاستِ تخفیف دو چیزند و جدا اعمال می‌شوند.
  ۳. ذخیره‌ی یک ردیف، ردیف‌های دیگرِ اعلامیه را **پاک نمی‌کند** — و این
     مهم‌ترین تستِ این فایل است، چون دقیقاً همان مسیری بود که ماتریس را نابود
     می‌کرد.
  ۴. «تغییر فی»ِ گروهی روی تکرارِ درخواست دوباره اعمال نمی‌شود.
  ۵. عوض‌شدنِ اعلامیه فاکتورِ دیروز را بازنویسی نمی‌کند.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.advanced_inventory import PriceList, PriceListItem
from app.models.audit import AuditLog
from app.models.company import ContactGroup
from app.models.sales_ops import DiscountItemGroup, DiscountItemGroupMember, SaleType
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
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


def sell(db, user, item, *, unit_price, discount=0, sale_type_id=None, qty=1):
    return post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            contact_id=make_contact(db).id,
            sale_type_id=sale_type_id,
            lines=[
                SalesInvoiceLineIn(
                    item_id=item.id,
                    qty=Decimal(qty),
                    unit_price=Decimal(unit_price),
                    discount=Decimal(discount),
                )
            ],
        ),
        user,
    )


# ───────────── ۱) نوعِ فروش، بُعدِ اصلیِ قیمت (§۴ §۵۳) ─────────────


def test_one_item_three_sale_types_three_prices(db, user):
    """شاهدِ مرکزیِ فصل: عادی ۱۰٬۰۰۰ / خرده ۱۲٬۰۰۰ / عمده ۸٬۰۰۰."""
    item = make_item(db, name="لیوان آبی")
    normal, retail, wholesale = SaleType(name="عادی"), SaleType(name="فروش خرده"), SaleType(name="فروش عمده")
    db.add_all([normal, retail, wholesale])
    db.flush()
    announcement(
        db,
        user,
        [
            {"item_id": item.id, "price": Decimal(10_000), "sale_type_id": normal.id},
            {"item_id": item.id, "price": Decimal(12_000), "sale_type_id": retail.id},
            {"item_id": item.id, "price": Decimal(8_000), "sale_type_id": wholesale.id},
        ],
    )

    for sale_type, expected in ((normal, 10_000), (retail, 12_000), (wholesale, 8_000)):
        got = pricing.resolve_detail(db, item.id, on=TODAY, sale_type_id=sale_type.id)
        assert got.unit_price == expected
        assert got.announcement_name == "اعلامیه"
        assert got.ambiguous is False


def test_an_item_rule_beats_a_group_rule(db, user):
    """§۱۴ — قاعده‌ای که خودِ کالا را نام برده مشخص‌تر است از قاعده‌ی گروهش.

    این حدس نیست: مجموعه‌ی کالاهای قاعده‌ی اول زیرمجموعه‌ی دومی است.
    """
    item = make_item(db, name="لیوان")
    group = DiscountItemGroup(name="ظروف")
    db.add(group)
    db.flush()
    db.add(DiscountItemGroupMember(group_id=group.id, item_id=item.id))
    db.flush()

    announcement(
        db,
        user,
        [
            {"item_group_id": group.id, "price": Decimal(500)},
            {"item_id": item.id, "price": Decimal(300)},
        ],
    )
    assert pricing.resolve(db, item.id, on=TODAY).price == 300

    # کالایی که فقط از راهِ گروه می‌آید، قیمتِ گروه را می‌گیرد
    other = make_item(db, sku="G-2", name="بشقاب")
    db.add(DiscountItemGroupMember(group_id=group.id, item_id=other.id))
    db.flush()
    assert pricing.resolve(db, other.id, on=TODAY).price == 500


def test_a_group_rule_does_not_leak_to_outsiders(db, user):
    """کالایی که عضوِ گروه نیست نباید قیمتِ گروه را بگیرد."""
    inside = make_item(db, sku="IN", name="داخل")
    outside = make_item(db, sku="OUT", name="بیرون")
    group = DiscountItemGroup(name="ظروف")
    db.add(group)
    db.flush()
    db.add(DiscountItemGroupMember(group_id=group.id, item_id=inside.id))
    db.flush()
    announcement(db, user, [{"item_group_id": group.id, "price": Decimal(500)}])

    assert pricing.resolve(db, inside.id, on=TODAY).price == 500
    assert pricing.resolve(db, outside.id, on=TODAY) is None


def test_an_ambiguous_configuration_is_stable_and_reported(db, user):
    """§۳۵ §۳۷ — دو قاعده‌ی هم‌رتبه: برنده باید **همیشه یکی** باشد، و گفته شود.

    «ردیفی که دیتابیس اول برگرداند» یعنی دو کوئری می‌توانند دو قیمت بدهند — که
    برای یک تراکنشِ مالی پذیرفتنی نیست.
    """
    item = make_item(db, name="لیوان")
    sale_type = SaleType(name="عادی")
    group = ContactGroup(name="ویژه", created_by_id=user.id)
    db.add_all([sale_type, group])
    db.flush()
    contact = make_contact(db)
    contact.group_id = group.id
    db.flush()

    announcement(
        db,
        user,
        [
            {"item_id": item.id, "price": Decimal(100), "sale_type_id": sale_type.id},
            {"item_id": item.id, "price": Decimal(200), "contact_group_id": group.id},
        ],
    )
    picks = {
        pricing.resolve(db, item.id, on=TODAY, sale_type_id=sale_type.id, contact_id=contact.id).price
        for _ in range(5)
    }
    assert len(picks) == 1, "انتخابِ برنده باید پایدار باشد"

    got = pricing.resolve_detail(
        db, item.id, on=TODAY, sale_type_id=sale_type.id, contact_id=contact.id
    )
    assert got.ambiguous is True


# ───────── ۲) دو سیاستِ مستقل: نرخ و تخفیف (§۲۴ §۲۵ §۲۹) ─────────


def test_locking_the_discount_does_not_lock_the_rate(db, user):
    """§۲۵ — این دو یک پرچم نیستند."""
    item = make_item(db, name="لیوان")
    stock(db, user, item)
    announcement(
        db,
        user,
        [
            {
                "item_id": item.id,
                "price": Decimal(100),
                "allow_discount_change": False,
                "allow_rate_change": True,
                "max_increase_percent": Decimal(50),
                "max_decrease_percent": Decimal(50),
            }
        ],
    )

    with pytest.raises(HTTPException) as err:
        sell(db, user, item, unit_price=100, discount=5)
    assert err.value.status_code == 400
    assert "تخفیف" in err.value.detail

    # ولی نرخ همچنان در حدِ مجاز آزاد است
    invoice = sell(db, user, item, unit_price=120)
    assert invoice.lines[0].unit_price == 120


def test_locking_the_rate_does_not_lock_the_discount(db, user):
    item = make_item(db, name="لیوان")
    stock(db, user, item)
    announcement(
        db,
        user,
        [
            {
                "item_id": item.id,
                "price": Decimal(100),
                "allow_rate_change": False,
                "allow_discount_change": True,
            }
        ],
    )
    invoice = sell(db, user, item, unit_price=100, discount=5)
    assert invoice.lines[0].discount == 5

    with pytest.raises(HTTPException) as err:
        sell(db, user, item, unit_price=99)
    assert "نرخ" in err.value.detail


def test_the_bounds_are_asymmetric_and_come_from_the_domain(db, user):
    """§۲۸ §۲۹ — یک `allowed_variance_percent` کافی نیست.

    و حدها همان‌جایی حساب می‌شوند که گارد اعمالشان می‌کند، وگرنه رابط یک عدد
    نشان می‌دهد و سرور عددِ دیگری را می‌سنجد.
    """
    item = make_item(db, name="لیوان")
    announcement(
        db,
        user,
        [
            {
                "item_id": item.id,
                "price": Decimal(100_000),
                "max_decrease_percent": Decimal(5),
                "max_increase_percent": Decimal(10),
            }
        ],
    )
    got = pricing.resolve_detail(db, item.id, on=TODAY)
    assert got.min_price == 95_000
    assert got.max_price == 110_000


def test_a_locked_rate_reports_a_single_point_bound(db, user):
    item = make_item(db, name="لیوان")
    announcement(
        db,
        user,
        [{"item_id": item.id, "price": Decimal(100), "allow_rate_change": False}],
    )
    got = pricing.resolve_detail(db, item.id, on=TODAY)
    assert (got.min_price, got.max_price) == (100, 100)


def test_zero_limits_still_mean_no_limit(db, user):
    """رفتارِ امروزِ ردیف‌های موجود نباید با این فصل عوض شود."""
    item = make_item(db, name="لیوان")
    stock(db, user, item)
    announcement(db, user, [{"item_id": item.id, "price": Decimal(100)}])
    got = pricing.resolve_detail(db, item.id, on=TODAY)
    assert got.min_price is None and got.max_price is None
    assert sell(db, user, item, unit_price=10).lines[0].unit_price == 10


# ──────── ۳) ذخیره دیگر ماتریس را پاک نمی‌کند (§۴۷ §۸۳ §۹۳) ────────


def test_saving_one_context_free_row_no_longer_wipes_the_matrix(client):
    """**گاردِ همان باگ.**

    فرمِ «لیست قیمت»ِ انبار ردیف‌ها را در نگاشتِ `item_id → price` می‌ریخت و با
    زمینه‌ی خالی پس می‌فرستاد، و اندپوینت اول `items.clear()` می‌زد. نتیجه:
    یک بار «ذخیره» هر قیمتِ عمده/خرده و هر حدِ تغییرِ نرخ را برای همیشه می‌برد.
    """
    item = client.post("/api/items", json={"sku": "MX-1", "name": "لیوان"}).json()["id"]
    retail = client.post("/api/sales-ops/sale-types", json={"name": "خرده"}).json()["id"]
    pl = client.post("/api/price-lists", json={"name": "اعلامیه"}).json()["id"]

    client.put(
        f"/api/price-lists/{pl}/items",
        json={
            "items": [
                {"item_id": item, "price": 12_000, "sale_type_id": retail, "max_increase_percent": 5},
                {"item_id": item, "price": 10_000},
            ]
        },
    )
    # همان چیزی که فرمِ قدیمی می‌فرستاد: یک ردیف، بی‌زمینه
    r = client.put(f"/api/price-lists/{pl}/items", json={"items": [{"item_id": item, "price": 9_000}]})
    assert r.status_code == 200, r.text

    rows = client.get(f"/api/price-lists/{pl}/items").json()
    by_type = {x["sale_type_id"]: x for x in rows}
    assert len(rows) == 2, "ردیفِ نوع‌فروش‌دار باید زنده مانده باشد"
    assert float(by_type[retail]["price"]) == 12_000
    assert float(by_type[retail]["max_increase_percent"]) == 5
    assert float(by_type[None]["price"]) == 9_000


def test_a_rule_must_name_an_item_or_a_group(client):
    """قاعده‌ی بی‌هدف روی *همه‌ی* کالاها می‌نشیند — یک قیمتِ سراسریِ ناخواسته."""
    pl = client.post("/api/price-lists", json={"name": "اعلامیه"}).json()["id"]
    r = client.put(f"/api/price-lists/{pl}/items", json={"items": [{"price": 100}]})
    assert r.status_code == 422


def test_deleting_an_announcement_with_rules_deactivates_it(client):
    """§۸۳ §۸۴ — فاکتورِ پارسال باید بتواند بگوید نرخش از کدام قاعده آمد."""
    item = client.post("/api/items", json={"sku": "DL-1", "name": "لیوان"}).json()["id"]
    pl = client.post("/api/price-lists", json={"name": "اعلامیه"}).json()["id"]
    client.put(f"/api/price-lists/{pl}/items", json={"items": [{"item_id": item, "price": 100}]})

    assert client.delete(f"/api/price-lists/{pl}").status_code == 204
    still = next(x for x in client.get("/api/price-lists").json() if x["id"] == pl)
    assert still["is_active"] is False
    assert len(client.get(f"/api/price-lists/{pl}/items").json()) == 1


def test_a_price_announcement_leaves_an_audit_trail(db, user):
    """§۴۰ §۸۵ — تنها تصمیمِ مالیِ شرکت که تغییرش هیچ ردی نمی‌گذاشت."""
    item = make_item(db, name="لیوان")
    price_list = announcement(db, user, [{"item_id": item.id, "price": Decimal(100)}])
    db.flush()

    rows = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "PriceList", AuditLog.entity_id == price_list.id)
        .all()
    )
    assert [r.action for r in rows] == ["create"]
    assert rows[0].summary and "اعلامیه قیمت" in rows[0].summary


# ─────────── ۴) تغییرِ گروهیِ فی (§۴۲–§۴۸ §۵۱ §۹۴) ───────────


@pytest.mark.parametrize(
    "mode,value,expected",
    [
        ("increase_percent", 20, 120),
        ("decrease_percent", 20, 80),
        ("increase_amount", 25, 125),
        ("decrease_amount", 25, 75),
        ("fixed", 777, 777),
        ("none", 0, 100),
    ],
)
def test_every_bulk_mode(mode, value, expected):
    """§۴۳ — شش حالتِ دیالوگِ «تغییر فی»."""
    assert pricing.apply_bulk_mode(Decimal(100), mode, Decimal(value)) == expected


def test_rounding_is_applied_once_to_a_multiple_of_rials():
    """§۴۹ §۵۱ — قیمت `Numeric(18, 0)` است، پس «رقمِ اعشار» به دقتِ رند ترجمه می‌شود."""
    assert pricing.round_price(Decimal("10450"), 1) == 10_450
    assert pricing.round_price(Decimal("10450"), 100) == 10_500
    assert pricing.round_price(Decimal("10449"), 100) == 10_400
    assert pricing.round_price(Decimal("10450"), 1000) == 10_000
    # قیمتِ منفی ساخته نمی‌شود، حتی با کاهشِ مبلغیِ بزرگ
    assert pricing.round_price(Decimal(-5), 1) == 0


def test_bulk_change_is_not_reapplied_on_retry(client):
    """§۴۵ §۴۶ §۹۴ — خطرناک‌ترین شکستِ این قابلیت.

    «۲۰٪ اضافه کن» جابه‌جاکننده است نه نشاننده: تکرارِ درخواست ۱۰۰ را به ۱۴۴
    می‌برد و هر دو اجرا «موفق» به‌نظر می‌رسند.
    """
    item = client.post("/api/items", json={"sku": "BK-1", "name": "لیوان"}).json()["id"]
    created = client.post(
        "/api/sales-ops/price-announcements",
        json={
            "name": "اعلامیه",
            "effective_from": str(date.today()),
            "lines": [{"item_id": item, "price": 10_000}],
        },
    )
    assert created.status_code == 201, created.text
    pl = created.json()["id"]

    headers = {"Idempotency-Key": "bulk-once"}
    body = {"mode": "increase_percent", "value": 20}
    first = client.post(f"/api/sales-ops/price-announcements/{pl}/bulk-price", json=body, headers=headers)
    second = client.post(f"/api/sales-ops/price-announcements/{pl}/bulk-price", json=body, headers=headers)

    assert first.status_code == 200, first.text
    assert first.json()["changed"] == 1
    assert second.json()["replayed"] is True

    rows = client.get(f"/api/price-lists/{pl}/items").json()
    assert float(rows[0]["price"]) == 12_000, "اجرای دوم نباید دوباره ۲۰٪ اضافه کرده باشد"


def test_bulk_change_scope_and_audit(db, user):
    """§۴۸ §۸۵ — دامنه‌ی فرمان قطعی است و قبل/بعد ثبت می‌شود."""
    cheap = make_item(db, sku="B-1", name="ارزان")
    dear = make_item(db, sku="B-2", name="گران")
    price_list = announcement(
        db,
        user,
        [
            {"item_id": cheap.id, "price": Decimal(100)},
            {"item_id": dear.id, "price": Decimal(200)},
        ],
    )

    result = pricing.bulk_change(
        db, price_list.id, mode="increase_percent", value=Decimal(10), item_ids=[cheap.id]
    )
    assert result.changed == 1

    prices = {
        row.item_id: row.price
        for row in db.query(PriceListItem).filter(PriceListItem.price_list_id == price_list.id)
    }
    assert prices[cheap.id] == 110
    assert prices[dear.id] == 200, "ردیفِ بیرونِ دامنه نباید دست بخورد"

    entry = (
        db.query(AuditLog)
        .filter(AuditLog.entity_id == price_list.id, AuditLog.action == "update")
        .order_by(AuditLog.at.desc())
        .first()
    )
    assert entry is not None and "تغییرِ گروهیِ فی" in entry.summary
    assert entry.changes["ردیف‌ها"]["to"][0]["from"] == "100"
    assert entry.changes["ردیف‌ها"]["to"][0]["to"] == "110"


def test_bulk_change_needs_a_matching_row(db, user):
    item = make_item(db, name="لیوان")
    price_list = announcement(db, user, [{"item_id": item.id, "price": Decimal(100)}])
    other = make_item(db, sku="Z-9", name="دیگری")
    with pytest.raises(HTTPException) as err:
        pricing.bulk_change(
            db, price_list.id, mode="fixed", value=Decimal(1), item_ids=[other.id]
        )
    assert err.value.status_code == 400


# ──────── ۵) پیکربندی تاریخ را بازنویسی نمی‌کند (§۱۰ §۷۵ §۹۳) ────────


def test_changing_the_announcement_leaves_yesterdays_invoice_alone(db, user):
    item = make_item(db, name="لیوان")
    stock(db, user, item)
    price_list = announcement(db, user, [{"item_id": item.id, "price": Decimal(12_000)}])
    invoice = sell(db, user, item, unit_price=12_000)

    pricing.bulk_change(db, price_list.id, mode="fixed", value=Decimal(20_000))

    db.refresh(invoice)
    assert invoice.lines[0].unit_price == 12_000
    assert invoice.lines[0].declared_unit_price == 12_000


def test_the_line_remembers_what_the_announcement_said(db, user):
    """§۹ §۵۹ §۶۱ §۹۱ — «چرا فیِ این ردیف این عدد است؟»

    و دست‌کاریِ دستی از همین دو ستون **مشتق** می‌شود؛ پرچمِ `price_changed`ِ
    مبهمی ساخته نمی‌شود.
    """
    item = make_item(db, name="لیوان")
    stock(db, user, item)
    price_list = announcement(
        db,
        user,
        [{"item_id": item.id, "price": Decimal(100), "max_decrease_percent": Decimal(20)}],
    )
    rule = db.query(PriceListItem).filter(PriceListItem.price_list_id == price_list.id).one()

    same = sell(db, user, item, unit_price=100)
    assert same.lines[0].declared_unit_price == 100
    assert same.lines[0].price_rule_id == rule.id
    assert same.lines[0].unit_price == same.lines[0].declared_unit_price  # دست‌نخورده

    lowered = sell(db, user, item, unit_price=90)
    assert lowered.lines[0].declared_unit_price == 100
    assert lowered.lines[0].unit_price != lowered.lines[0].declared_unit_price  # دست‌کاری‌شده


def test_a_line_without_a_matching_rule_has_no_lineage(db, user):
    """§۵۸ — نبودِ قاعده یک حقیقت است، نه یک عددِ حدسی."""
    item = make_item(db, name="لیوان")
    stock(db, user, item)
    invoice = sell(db, user, item, unit_price=555)
    assert invoice.lines[0].declared_unit_price is None
    assert invoice.lines[0].price_rule_id is None


def test_the_resolve_endpoint_answers_the_form(client):
    """مسیری که فرمِ فاکتور و صندوق از آن می‌خوانند — تنها موتورِ قیمت (§۵۴).

    تستِ سطحِ سرویس کافی نیست: اگر شکلِ پاسخ سرِ راه بشکند، هر دو مصرف‌کننده بی‌صدا
    به قیمتِ پایه برمی‌گردند و کسی خبردار نمی‌شود.
    """
    item = client.post("/api/items", json={"sku": "RS-1", "name": "لیوان"}).json()["id"]
    retail = client.post("/api/sales-ops/sale-types", json={"name": "خرده"}).json()["id"]
    client.post(
        "/api/sales-ops/price-announcements",
        json={
            "name": "اعلامیه",
            "effective_from": str(date.today()),
            "lines": [
                {
                    "item_id": item,
                    "price": 12_000,
                    "sale_type_id": retail,
                    "max_decrease_percent": 5,
                    "max_increase_percent": 10,
                    "allow_discount_change": False,
                    "addition_percent": 3,
                }
            ],
        },
    )

    r = client.get(f"/api/sales-ops/pricing/resolve?item_id={item}&sale_type_id={retail}")
    assert r.status_code == 200, r.text
    got = r.json()
    assert float(got["unit_price"]) == 12_000
    assert float(got["min_price"]) == 11_400 and float(got["max_price"]) == 13_200
    assert got["allow_discount_change"] is False
    assert float(got["addition_percent"]) == 3
    assert got["announcement_name"] == "اعلامیه"
    assert got["ambiguous"] is False

    # زمینه‌ای که قاعده ندارد: `null`، نه یک قیمتِ حدسی (§۵۸)
    assert client.get(f"/api/sales-ops/pricing/resolve?item_id={item}").json() is None


def test_a_future_announcement_does_not_price_today(db, user):
    item = make_item(db, name="لیوان")
    announcement(db, user, [{"item_id": item.id, "price": Decimal(100)}])
    announcement(
        db,
        user,
        [{"item_id": item.id, "price": Decimal(999)}],
        on=TODAY + timedelta(days=30),
        name="اعلامیه‌ی آینده",
    )
    assert pricing.resolve(db, item.id, on=TODAY).price == 100
