"""واحدهای سنجش — داده‌ی پایه و **تنها** موتورِ تبدیل (§۱۷–§۲۳).

تا پیش از این واحد یک `String(20)`ِ آزاد روی کالا بود: «کیلوگرم» و «كيلوگرم»
دو واحدِ متفاوت بودند، و هیچ جایی نمی‌گفت یک کارتن چند عدد است.
"""
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.inventory import Item, UnitOfMeasure
from app.services import units as units_svc
from tests.factories import make_item


def unit(db, name: str) -> UnitOfMeasure:
    return db.query(UnitOfMeasure).filter(UnitOfMeasure.name == name).one()


# ───────────────────────── داده‌ی پایه، نه متنِ آزاد ─────────────────────────


def test_a_new_business_starts_with_standard_units(db, user):
    """§۱۹ — فرمِ کالای جدید باید واحدی برای انتخاب داشته باشد."""
    names = {u.name for u in db.query(UnitOfMeasure).all()}
    assert {"عدد", "کیلوگرم", "کارتن", "ساعت"} <= names


def test_free_text_still_lands_in_the_master(db, user):
    """مسیرهای قدیمی نوشتار می‌فرستند؛ نشتِ متنِ آزاد همان‌جا بسته می‌شود."""
    created = units_svc.get_or_create(db, "قواره")
    assert created.id is not None
    assert units_svc.get_or_create(db, "قواره").id == created.id


def test_a_blank_unit_is_refused(db, user):
    with pytest.raises(HTTPException) as err:
        units_svc.get_or_create(db, "   ")
    assert err.value.status_code == 400


def test_renaming_a_unit_reaches_the_items(db, user, client):
    """وگرنه `Item.unit` و واحدِ واقعی از هم جدا می‌افتند و بسته‌ی مؤدیان نامِ قدیمی را می‌فرستد."""
    piece = unit(db, "عدد")
    item = make_item(db, name="لیوان", primary_unit_id=piece.id)
    item.unit = "عدد"
    db.flush()

    piece.name = "عدد "
    units_svc.sync_item_unit(db, item)
    assert item.unit == "عدد "


def test_deactivating_a_unit_in_use_is_refused(db, user):
    """مثلِ انبار: پیام تعداد را می‌گوید، نه «عملیات ناموفق»."""
    piece = unit(db, "عدد")
    make_item(db, name="لیوان", primary_unit_id=piece.id)
    with pytest.raises(HTTPException) as err:
        units_svc.assert_can_deactivate(db, piece)
    assert err.value.status_code == 409
    assert "عدد" in err.value.detail


def test_an_unused_unit_can_be_deactivated(db, user):
    spare = units_svc.get_or_create(db, "قواره")
    units_svc.assert_can_deactivate(db, spare)  # بدون خطا


def test_an_inactive_unit_cannot_be_chosen(db, user):
    spare = units_svc.get_or_create(db, "قواره")
    spare.is_active = False
    db.flush()
    with pytest.raises(HTTPException) as err:
        units_svc.assert_usable(db, spare.id)
    assert err.value.status_code == 400


# ───────────────────────── نسبتِ تبدیل (§۲۰ §۲۱ §۲۲) ─────────────────────────


def carton_item(db, *, mode="fixed", factor=24):
    return make_item(
        db,
        name="لیوان",
        primary_unit_id=unit(db, "عدد").id,
        secondary_unit_id=unit(db, "کارتن").id,
        conversion_factor=Decimal(factor),
        conversion_mode=mode,
    )


def test_one_carton_is_twenty_four_pieces(db, user):
    """§۲۰ §۲۱ — خرید با کارتن، انبار با عدد."""
    item = carton_item(db)
    assert units_svc.to_primary(db, item, Decimal(2), item.secondary_unit_id) == Decimal(48)


def test_the_primary_unit_passes_through(db, user):
    item = carton_item(db)
    assert units_svc.to_primary(db, item, Decimal(5), item.primary_unit_id) == Decimal(5)
    assert units_svc.to_primary(db, item, Decimal(5), None) == Decimal(5)


def test_an_unrelated_unit_is_refused(db, user):
    """کوبیتا نسبتِ دو واحدِ بی‌ربط را نمی‌داند؛ حدس‌زدنش بدتر از خطاست."""
    item = carton_item(db)
    with pytest.raises(HTTPException) as err:
        units_svc.to_primary(db, item, Decimal(1), unit(db, "کیلوگرم").id)
    assert err.value.status_code == 400
    assert "کیلوگرم" in err.value.detail


def test_a_variable_ratio_refuses_to_guess(db, user):
    """§۲۲ — نسبتِ متغیر یعنی «این عدد را نمی‌شود از پیش دانست».

    عددی از خود درآوردن یعنی موجودی را با یک حدس پر کنیم.
    """
    item = carton_item(db, mode="variable", factor=0)
    with pytest.raises(HTTPException) as err:
        units_svc.to_primary(db, item, Decimal(1), item.secondary_unit_id)
    assert err.value.status_code == 400


def test_a_fixed_ratio_without_a_factor_is_refused(db, user):
    item = carton_item(db, factor=0)
    with pytest.raises(HTTPException) as err:
        units_svc.assert_conversion(item)
    assert err.value.status_code == 400


def test_the_secondary_unit_cannot_equal_the_primary(db, user):
    piece = unit(db, "عدد")
    item = make_item(
        db, name="لیوان", primary_unit_id=piece.id, secondary_unit_id=piece.id,
        conversion_factor=Decimal(1),
    )
    with pytest.raises(HTTPException) as err:
        units_svc.assert_conversion(item)
    assert err.value.status_code == 400


def test_a_variable_ratio_needs_no_factor(db, user):
    """نسبتِ متغیر عمداً بی‌عدد است — قیدِ «عدد لازم است» نباید رویش بیفتد."""
    units_svc.assert_conversion(carton_item(db, mode="variable", factor=0))


# ───────────────────── واحد موجودی نیست (§۱۶ §۲۳) ─────────────────────


def test_a_service_may_have_a_unit_without_stock(db, user):
    """§۴۴ — «۵ ساعت مشاوره» واحد دارد و موجودی ندارد."""
    hour = unit(db, "ساعت")
    service = make_item(db, name="مشاوره حقوقی", is_service=True, primary_unit_id=hour.id)
    assert service.is_service and service.primary_unit_id == hour.id


def test_weight_and_volume_are_metadata_not_balances(db, user):
    """§۲۳ — وزن و حجم متادیتای حمل‌ونقل‌اند؛ هیچ ماندهٔ‌ای از رویشان مشتق نمی‌شود."""
    item = make_item(db, name="بشکه", unit_weight=Decimal("12.5"), unit_volume=Decimal("0.2"))
    db.refresh(item)
    assert Decimal(item.unit_weight) == Decimal("12.5")
    assert not any(
        column.name in ("qty_on_hand", "stock", "quantity") for column in Item.__table__.columns
    )
