"""روشِ تسویه‌ی صورتحسابِ مؤدیان باید از خودِ فاکتور بیاید.

**باگی که بسته شد.** `setm` در سربرگِ بسته ثابتِ `1` بود، یعنی **هر فروشِ
نسیه‌ای هم به سازمان امور مالیاتی «نقدی» اظهار می‌شد** — ادعای دریافتِ وجهی که
نشده بود.

داده‌اش از روزِ اول موجود بود و هیچ‌چیزِ تازه‌ای لازم نداشت:
`SalesInvoice.settlement_terms` با قیدِ `IN ('cash','credit','mixed')`، انتخابگرش
در فرمِ فاکتور و ویزارد، نمایشش در `InvoiceList`. فقط همین یک نقطه نادیده‌اش
می‌گرفت.

**آنچه عمداً دست نخورد:** `inp` (الگوی صورتحساب) همچنان ثابتِ `1` است. هیچ
نشانه‌ی ساختاریِ صادرات یا ارزی در مسیرِ مؤدیان نیست — «صادراتی» فقط می‌تواند
نامِ یک نوعِ فروش باشد، نه یک پرچم — و حدس‌زدنِ کدِ الگو از `1=فروش`ِ صادقانه‌ی
فعلی بدتر است.
"""
import re
from datetime import date
from decimal import Decimal

import pytest

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
TAX_ID = "AB12CD00000000000000A1"


def _settings(db):
    s = svc.get_settings(db)
    s.memory_id = "AB12CD"
    s.national_id = "10101010101"
    s.economic_code = "411111111111"
    s.default_stuff_id = "1111111111111"
    s.is_sandbox = True
    s.is_active = True
    db.flush()
    return s


def _invoice(db, user, *, settlement_terms=None):
    """یک فاکتورِ فروشِ ساده. `None` یعنی فیلد اصلاً فرستاده نمی‌شود."""
    wh = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(50), unit_cost=Decimal(400_000))],
        ),
        user,
    )
    payload = {
        "invoice_date": TODAY,
        "warehouse_id": wh.id,
        "tax_rate": Decimal(10),
        "lines": [SalesInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_price=Decimal(1_000_000))],
    }
    if settlement_terms is not None:
        payload["settlement_terms"] = settlement_terms
    return post_sales_invoice(db, SalesInvoiceIn(**payload), user)


# ─────────── هر سه حالت ───────────


@pytest.mark.parametrize(
    "terms,expected",
    [("cash", 1), ("credit", 2), ("mixed", 3)],
)
def test_the_settlement_method_follows_the_invoice(db, user, terms, expected):
    settings = _settings(db)
    inv = _invoice(db, user, settlement_terms=terms)
    packet = svc.build_invoice_packet(inv, settings, TAX_ID)
    assert packet["header"]["setm"] == expected


def test_a_credit_sale_is_no_longer_declared_as_cash(db, user):
    """**گاردِ همان باگ.** پیش از اصلاح این عدد `1` بود."""
    settings = _settings(db)
    inv = _invoice(db, user, settlement_terms="credit")
    packet = svc.build_invoice_packet(inv, settings, TAX_ID)
    assert packet["header"]["setm"] != 1, "*** فروشِ نسیه «نقدی» اظهار شد ***"


def test_the_default_is_credit_not_cash(db, user):
    """فاکتوری که روشِ تسویه‌اش تصریح نشده.

    پیش‌فرضِ ستون `credit` است، و محافظه‌کارانه‌تر هم هست: اظهارِ نادرستِ «نقدی»
    یعنی ادعای دریافتِ وجهی که نشده.
    """
    settings = _settings(db)
    inv = _invoice(db, user)
    packet = svc.build_invoice_packet(inv, settings, TAX_ID)
    assert packet["header"]["setm"] == svc.SETTLEMENT_METHOD_CODES["credit"]


# ─────────── گاردهای ساختاری ───────────


def test_the_mapping_covers_every_value_the_column_allows(db):
    """اگر روزی مقدارِ چهارمی به قید اضافه شود، اینجا باید بشکند.

    وگرنه آن مقدار **بی‌صدا** به پیش‌فرض می‌افتد و باز هم یک اظهارِ نادرست
    می‌سازد — همان شکلِ خاموشِ باگِ اصلی، فقط با یک لایه فاصله.
    """
    from sqlalchemy import inspect as sa_inspect

    from app.database import engine
    from app.models.invoices import SalesInvoice

    constraints = sa_inspect(engine).get_check_constraints(SalesInvoice.__tablename__)
    settlement = next(
        (c for c in constraints if c["name"] == "ck_sales_invoices_settlement_terms"), None
    )
    assert settlement is not None, "قیدِ روشِ تسویه پیدا نشد"

    #: Postgres قید را بازنویسی می‌کند — `IN (...)` به
    #: `= ANY (ARRAY['cash'::character varying, …])` تبدیل می‌شود. پس به‌جای
    #: تکه‌کردنِ پرانتزها، خودِ رشته‌های نقل‌قولی برداشته می‌شوند.
    allowed = set(re.findall(r"'([a-z_]+)'", settlement["sqltext"]))
    assert allowed == set(svc.SETTLEMENT_METHOD_CODES), (
        f"قید {allowed} را می‌پذیرد ولی نگاشت {set(svc.SETTLEMENT_METHOD_CODES)} را می‌شناسد"
    )


def test_the_codes_are_distinct(db):
    """سه روشِ متفاوت نباید به یک کد برسند."""
    codes = list(svc.SETTLEMENT_METHOD_CODES.values())
    assert len(set(codes)) == len(codes), f"کدِ تکراری: {codes}"


def test_the_invoice_pattern_is_deliberately_unchanged(db, user):
    """`inp` هنوز ثابت است — و این یک تصمیم است، نه فراموشی.

    اگر روزی صادرات یا فاکتورِ ارزی ساختار پیدا کرد، این تست همان‌جاست که
    یادآوری می‌کند الگو هم باید مشتق شود.
    """
    settings = _settings(db)
    inv = _invoice(db, user, settlement_terms="cash")
    packet = svc.build_invoice_packet(inv, settings, TAX_ID)
    assert packet["header"]["inp"] == 1
