"""چندارزی — ارز و نرخ، آخرین نرخ، و ذخیره‌ی ارز روی فاکتور (بدون اثر بر دفترِ پایه)."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.schemas.currency import CurrencyIn, ExchangeRateIn
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.services import chart_codes as cc
from app.services.common import get_account
from app.services.currencies import (
    create_currency,
    delete_currency,
    get_latest,
    latest_rate,
    list_currencies,
    upsert_rate,
)
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.reports import get_trial_balance
from tests.factories import main_warehouse, make_contact, make_item


def _usd(db, user):
    return create_currency(db, CurrencyIn(code="usd", name="دلار آمریکا", symbol="$"), user)


def test_currency_code_is_uppercased(db, user):
    c = _usd(db, user)
    assert c.code == "USD"
    assert [x.code for x in list_currencies(db)] == ["USD"]


def test_duplicate_currency_rejected(db, user):
    _usd(db, user)
    with pytest.raises(HTTPException) as exc:
        _usd(db, user)
    assert exc.value.status_code == 400


def test_rate_requires_defined_currency(db, user):
    with pytest.raises(HTTPException) as exc:
        upsert_rate(db, ExchangeRateIn(currency_code="EUR", rate_date=date(2026, 3, 1), rate=Decimal(900_000)), user)
    assert exc.value.status_code == 400


def test_upsert_rate_updates_same_day(db, user):
    _usd(db, user)
    upsert_rate(db, ExchangeRateIn(currency_code="USD", rate_date=date(2026, 3, 1), rate=Decimal(800_000)), user)
    upsert_rate(db, ExchangeRateIn(currency_code="USD", rate_date=date(2026, 3, 1), rate=Decimal(820_000)), user)
    r = latest_rate(db, "USD", date(2026, 3, 1))
    assert r.rate == Decimal(820_000)  # همان روز به‌روزرسانی شد، نه ردیف تازه


def test_latest_rate_picks_most_recent_on_or_before(db, user):
    _usd(db, user)
    upsert_rate(db, ExchangeRateIn(currency_code="USD", rate_date=date(2026, 1, 1), rate=Decimal(700_000)), user)
    upsert_rate(db, ExchangeRateIn(currency_code="USD", rate_date=date(2026, 3, 1), rate=Decimal(800_000)), user)
    upsert_rate(db, ExchangeRateIn(currency_code="USD", rate_date=date(2026, 6, 1), rate=Decimal(900_000)), user)

    assert latest_rate(db, "USD", date(2026, 4, 1)).rate == Decimal(800_000)
    assert get_latest(db, "USD")["rate"] == Decimal(900_000)  # پیش‌فرض امروز → آخرین


def test_delete_currency_removes_its_rates(db, user):
    c = _usd(db, user)
    upsert_rate(db, ExchangeRateIn(currency_code="USD", rate_date=date(2026, 3, 1), rate=Decimal(800_000)), user)
    delete_currency(db, c.id)
    assert list_currencies(db) == []
    assert latest_rate(db, "USD") is None


def test_sales_invoice_stores_currency_without_touching_ledger(db, user):
    """ارزِ فاکتور فقط متادیتای نمایشی است؛ سند حسابداری همان مبلغِ پایه را ثبت می‌کند."""
    wh = main_warehouse(db)
    item = make_item(db)
    contact = make_contact(db)
    # موجودی
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 1, 1),
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(500_000))],
        ),
        user,
    )
    _usd(db, user)
    # کلاینت مبلغ را به پایه تبدیل کرده: ۱۰۰ دلار × ۸۰۰٬۰۰۰ = ۸۰٬۰۰۰٬۰۰۰ ریال
    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=date(2026, 3, 1),
            warehouse_id=wh.id,
            contact_id=contact.id,
            currency_code="USD",
            exchange_rate=Decimal(800_000),
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(80_000_000))],
        ),
        user,
    )
    assert inv.currency_code == "USD"
    assert inv.exchange_rate == Decimal(800_000)
    assert inv.total_amount == Decimal(80_000_000)  # پایه، بدون تغییر

    # فروش در تریال‌بالانس به مبلغِ پایه نشسته (درآمد ۸۰م)
    income = next(
        r for r in get_trial_balance(db, None, None) if r["account_code"] == cc.DEFAULT_CODE_BY_ROLE[cc.SALES_REVENUE]
    )
    assert Decimal(income["balance"]) == Decimal(80_000_000)


def test_base_invoice_defaults(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 1, 1),
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(5), unit_cost=Decimal(100_000))],
        ),
        user,
    )
    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=date(2026, 3, 1),
            warehouse_id=wh.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(200_000))],
        ),
        user,
    )
    assert inv.currency_code is None  # پیش‌فرض = پایه
    assert inv.exchange_rate == Decimal(1)


def test_negative_rate_rejected_by_schema(db):
    with pytest.raises(ValueError):
        ExchangeRateIn(currency_code="USD", rate_date=date(2026, 3, 1), rate=Decimal(0))


def test_invoice_currency_requires_positive_rate(db):
    with pytest.raises(ValueError):
        SalesInvoiceIn(
            invoice_date=date(2026, 3, 1),
            warehouse_id="00000000-0000-0000-0000-000000000000",
            currency_code="USD",
            exchange_rate=Decimal(0),
            lines=[SalesInvoiceLineIn(item_id="00000000-0000-0000-0000-000000000000", qty=Decimal(1), unit_price=Decimal(1))],
        )
