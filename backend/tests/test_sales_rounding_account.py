"""حسابِ «تعدیلِ گِرد کردن فروش» باید حسابِ خودش باشد، نه یک کانالِ فروشِ واقعی.

تا پیش از مهاجرتِ ۰۱۴۳، `DEFAULT_CODE_BY_ROLE[SALES_ROUNDING]` کدِ `4102` بود و
`4102` در `seed.CHART_OF_ACCOUNTS` «فروش کالا - آنلاین» است. چون
`provision_tenant` نقش را از روی همین نگاشت مهر می‌زند، رندِ هر فاکتور مستقیم
داخلِ درآمدِ فروشِ آنلاین می‌نشست و آن عدد دیگر «فروشِ آنلاین» نبود.

این دقیقاً همان چیزی است که `SALES_RETURN` را از «فروش» جدا کرد؛ این‌جا نقض شده
بود و هیچ تستی نمی‌دیدش — چون همه‌ی تست‌های موجود حساب را **با نقشش** پیدا
می‌کنند و نقش همیشه یک حسابی برمی‌گرداند، درست یا غلط.
"""
from datetime import date
from decimal import Decimal

from app.models.accounting import Account, JournalEntry
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.seed import CHART_OF_ACCOUNTS
from app.services import chart_codes as cc
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 3, 15)

#: کانال‌های فروشِ واقعی در چارتِ پایه — درآمدی که کسب‌وکار از آن گزارش می‌گیرد.
SALES_CHANNEL_CODES = ("4101", "4102")


def _stock_in(db, user, item, wh):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(100), unit_cost=Decimal(500_000))],
        ),
        user,
    )


# --- ساختارِ نگاشت -----------------------------------------------------------


def test_default_role_codes_are_unique():
    """دو نقش نمی‌توانند یک کدِ پیش‌فرض داشته باشند.

    `ROLE_BY_DEFAULT_CODE` وارونه‌ی `DEFAULT_CODE_BY_ROLE` است؛ اگر دو نقش یک کد
    بگیرند، یکی‌شان **بی‌صدا** از وارونه می‌افتد و در `provision_tenant` هرگز مهر
    نمی‌خورد. این‌جا شمارش می‌شود تا آن سکوت ممکن نباشد.
    """
    assert len(cc.ROLE_BY_DEFAULT_CODE) == len(cc.DEFAULT_CODE_BY_ROLE)


def test_rounding_default_code_is_not_a_sales_channel():
    """کدِ پیش‌فرضِ نقشِ رند نباید کدِ یکی از کانال‌های فروش باشد."""
    assert cc.DEFAULT_CODE_BY_ROLE[cc.SALES_ROUNDING] not in SALES_CHANNEL_CODES


def test_rounding_default_code_exists_in_the_seed_chart():
    """حساب باید در چارتِ پایه باشد، وگرنه هر مشتریِ تازه با `get_or_create` یک
    حسابِ خارج از چارتِ نشانده‌شده می‌گیرد و دو جا دو نام پیدا می‌کند."""
    seeded = {code: name for code, name, *_ in CHART_OF_ACCOUNTS}
    code = cc.DEFAULT_CODE_BY_ROLE[cc.SALES_ROUNDING]
    assert code in seeded
    assert "فروش کالا" not in seeded[code]


# --- رفتارِ واقعیِ ثبت --------------------------------------------------------


def test_rounding_role_sits_on_its_own_account(db):
    """نقشِ رند و نقشِ درآمدِ فروش دو حسابِ متفاوت‌اند."""
    rounding = db.query(Account).filter(Account.system_role == cc.SALES_ROUNDING).first()
    revenue = db.query(Account).filter(Account.system_role == cc.SALES_REVENUE).first()
    assert rounding is not None and revenue is not None
    assert rounding.id != revenue.id


def test_rounding_does_not_land_in_online_sales_revenue(db, user):
    """سندِ فاکتورِ رندشده هیچ ردیفی روی حسابِ «فروش کالا - آنلاین» نمی‌گذارد.

    گاردِ همان باگ: پیش از ۰۱۴۳ ردیفِ رند دقیقاً روی همین حساب می‌نشست.
    """
    online = db.query(Account).filter(Account.code == "4102").first()
    assert online is not None, "چارتِ پایه دیگر ۴۱۰۲ ندارد — این تست باید به‌روز شود"
    assert online.system_role is None

    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh)
    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            rounding=Decimal(-400),
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(1_000_000))],
        ),
        user,
    )
    entry = db.get(JournalEntry, inv.journal_entry_id)
    assert sum(line.debit for line in entry.lines) == sum(line.credit for line in entry.lines)

    rounding_acc = db.query(Account).filter(Account.system_role == cc.SALES_ROUNDING).first()
    rline = next(line for line in entry.lines if line.account_id == rounding_acc.id)
    assert rline.debit == Decimal(400)

    assert not [line for line in entry.lines if line.account_id == online.id]
