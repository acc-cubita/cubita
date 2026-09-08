"""واحدِ سنجش در بسته‌ی مؤدیان — تا امروز هر چیزی «عدد» اظهار می‌شد.

`build_invoice_packet` کدِ واحد را ثابت `"164"` می‌فرستاد، چه کالا کیلوگرم بود چه
متر چه کارتن. یعنی فروشِ ۵۰ کیلوگرم به‌صورتِ ۵۰ «عدد» به سازمانِ امور مالیاتی
اظهار می‌شد — **دادهٔ نادرست، نه فقط قابلیتِ نداشته**.

کدهای بقیه‌ی واحدها **حدس زده نمی‌شوند**؛ کاربر از روی جدولِ رسمی واردشان می‌کند.
تنها پایه‌ی درون‌کد «عدد → ۱۶۴» است، همان چیزی که تا امروز برای همه می‌رفت.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.inventory import Item
from app.models.moadian import MoadianUnitMap
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.services import moadian as svc
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 3, 15)


def _sale(db, user, *, unit="عدد", qty=2):
    wh = main_warehouse(db)
    item = make_item(db)
    item.unit = unit
    db.flush()
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(50), unit_cost=Decimal(400_000))],
        ),
        user,
    )
    invoice = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(10),
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_price=Decimal(1_000_000))],
        ),
        user,
    )
    return invoice, item


def _map(db, user, unit, code):
    db.add(MoadianUnitMap(unit=unit, code=code, created_by_id=user.id))
    db.flush()


def _packet(db, invoice):
    settings = svc.get_settings(db)
    return svc.build_invoice_packet(invoice, settings, "X" * 22, None, svc.unit_codes(db))


# ── کدِ واحد ────────────────────────────────────────────────────────────────


def test_the_builtin_maps_piece_without_any_row(db, user):
    """**رگرسیون.** «عدد» باید بدونِ هیچ نگاشتی همان ۱۶۴ بماند — رفتارِ امروز."""
    invoice, _ = _sale(db, user, unit="عدد")
    assert _packet(db, invoice)["body"][0]["mu"] == "164"


def test_a_mapped_unit_uses_its_own_code(db, user):
    """**قیدِ اصلی.** کیلوگرم دیگر «عدد» اظهار نمی‌شود."""
    invoice, _ = _sale(db, user, unit="کیلوگرم")
    _map(db, user, "کیلوگرم", "166")

    assert _packet(db, invoice)["body"][0]["mu"] == "166"


def test_a_user_row_beats_the_builtin(db, user):
    """حرفِ کاربر بر پیش‌فرضِ ما مقدم است، حتی برای «عدد»."""
    invoice, _ = _sale(db, user, unit="عدد")
    _map(db, user, "عدد", "999")

    assert _packet(db, invoice)["body"][0]["mu"] == "999"


# ── گارد ────────────────────────────────────────────────────────────────────


def test_an_unmapped_unit_blocks_with_a_useful_message(db, user):
    """پیام باید بگوید کدام واحد، کدام کالا، و کجا درست می‌شود."""
    invoice, item = _sale(db, user, unit="کیلوگرم")

    with pytest.raises(HTTPException) as err:
        svc._assert_unit_codes(invoice, svc.unit_codes(db))

    detail = str(err.value.detail)
    assert "کیلوگرم" in detail
    assert item.name in detail
    assert "نگاشت" in detail


def test_the_serial_is_not_burned_when_validation_fails(db, user):
    """**قیدِ مهم.** سریالِ مالیاتی نباید بابتِ بسته‌ای که ساخته نمی‌شود هدر برود.

    همان دلیلی که `_assert_stuff_ids` هم پیش از `_next_serial` صدا زده می‌شود.
    """
    settings = svc.get_settings(db)
    settings.memory_id = "AB12CD"
    settings.default_stuff_id = "1111111111111"
    settings.is_active = True
    db.flush()
    before = settings.last_serial

    invoice, _ = _sale(db, user, unit="کیلوگرم")
    with pytest.raises(HTTPException):
        svc.submit_invoice(db, invoice.id, user)

    db.refresh(settings)
    assert settings.last_serial == before


def test_a_mapped_unit_clears_the_block(db, user):
    invoice, _ = _sale(db, user, unit="متر")
    _map(db, user, "متر", "170")

    svc._assert_unit_codes(invoice, svc.unit_codes(db))  # نباید خطا بدهد


# ── هویتِ خریدار ────────────────────────────────────────────────────────────


def test_an_economic_code_without_a_national_id_is_blocked(db, user):
    """خریدارِ نوعِ اول بدونِ شناسه‌ی ملی، `bid` را خالی می‌فرستاد."""
    from app.models.inventory import Contact

    contact = Contact(name="شرکت الف", type="customer", economic_code="411111111111")
    db.add(contact)
    db.flush()

    with pytest.raises(HTTPException) as err:
        svc._assert_buyer_identity(contact)
    assert "شرکت الف" in str(err.value.detail)


def test_a_complete_or_walkin_buyer_passes(db, user):
    from app.models.inventory import Contact

    complete = Contact(
        name="شرکت ب", type="customer", economic_code="411111111111", national_id="10101010101"
    )
    walkin = Contact(name="مشتریِ نقدی", type="customer")
    db.add_all([complete, walkin])
    db.flush()

    svc._assert_buyer_identity(complete)
    svc._assert_buyer_identity(walkin)
    svc._assert_buyer_identity(None)


# ── آمادگی ──────────────────────────────────────────────────────────────────


def test_readiness_lists_the_unmapped_units(db, user):
    """کاربر باید همه را یک‌جا ببیند، نه فاکتور به فاکتور کشفشان کند."""
    item = make_item(db)
    item.unit = "کارتن"
    db.flush()

    assert "کارتن" in svc.unmapped_units(db)

    _map(db, user, "کارتن", "171")
    assert "کارتن" not in svc.unmapped_units(db)
