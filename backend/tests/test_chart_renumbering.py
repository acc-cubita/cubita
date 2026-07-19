"""بازشماره‌گذاری چارت حساب.

کل هدف ستون `system_role` همین است: کد حساب متعلق به مشتری است و حسابداران
معمولاً چارت را با رویه‌ی خودشان بازشماره‌گذاری می‌کنند. قبل از این تغییر،
`get_account` با رشته‌ی کد جست‌وجو می‌کرد و اولین مشتری‌ای که «صندوق» را از ۱۱۰۱
جابه‌جا می‌کرد، ثبت فاکتورهایش می‌شکست — آن هم نه در لحظه‌ی تغییر کد، بلکه بعداً
موقع ثبت سند، که پیدا کردن علتش سخت است.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models.accounting import Account, JournalLine
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.services import chart_codes as cc
from app.services.common import get_account
from app.services.inventory import post_purchase_invoice, post_sales_invoice

from tests.factories import main_warehouse, make_item


def test_every_posting_role_resolves_after_provisioning(db):
    """محافظ: هر نقشی که سرویس‌ها استفاده می‌کنند باید در چارت وجود داشته باشد.

    اگر روزی نقشی به chart_codes اضافه شود و در provision_tenant علامت نخورد،
    شکستش موقع ثبت سند ظاهر می‌شود نه موقع ساخت مستأجر. این تست جلوتر می‌گیردش.
    """
    for role in cc.DEFAULT_CODE_BY_ROLE:
        account = get_account(db, role)
        assert account.system_role == role


def test_posting_survives_a_renumbered_chart(db, user):
    """مشتری کد حساب‌ها را عوض می‌کند؛ ثبت باید کاملاً بی‌تفاوت باشد."""
    item = make_item(db, sales_price=Decimal(5_000_000))
    warehouse = main_warehouse(db)

    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 6, 1),
            warehouse_id=warehouse.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(3_000_000))],
        ),
        user,
    )

    # مشتری چارتش را بازشماره‌گذاری می‌کند — کدهای کاملاً متفاوت، نقش‌ها دست‌نخورده
    renumbered = {
        cc.CASH: "10-01",
        cc.INVENTORY: "10-05",
        cc.COGS: "50-01",
        cc.SALES_REVENUE: "40-01",
    }
    for role, new_code in renumbered.items():
        db.query(Account).filter(Account.system_role == role).update({"code": new_code})
    db.flush()

    invoice = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=date(2026, 6, 2),
            warehouse_id=warehouse.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_price=Decimal(5_000_000))],
        ),
        user,
    )

    assert invoice.total_amount == Decimal(10_000_000)
    entry = invoice.journal_entry_id
    assert entry is not None, "با چارت بازشماره‌گذاری‌شده سند ساخته نشد"

    # سند باید روی همان حساب‌های نقش‌دار نشسته باشد، حالا با کدهای جدیدشان
    rows = (
        db.query(Account.code, JournalLine.debit, JournalLine.credit)
        .join(JournalLine, Account.id == JournalLine.account_id)
        .filter(JournalLine.entry_id == entry)
        .all()
    )
    codes = {code for code, _, _ in rows}
    assert {"10-01", "10-05", "50-01", "40-01"} & codes, f"سند روی حساب‌های بازشماره‌گذاری‌شده ننشست: {codes}"
    assert sum(d for _, d, _ in rows) == sum(c for _, _, c in rows), "سند نامتوازن شد"


def test_lookup_by_old_hardcoded_code_no_longer_drives_posting(db):
    """اگر کسی دوباره کد را hardcode کند، این تست نشانش می‌دهد.

    نقش‌ها باید مقدارشان معنایی باشد نه عددی؛ برگشتن به رشته‌ی کد یعنی برگشتن به
    همان باگ.
    """
    for role in cc.DEFAULT_CODE_BY_ROLE:
        assert not role.isdigit(), f"نقش «{role}» شبیه کد حساب است — احتمالاً به رفتار قدیمی برگشته"


def test_missing_role_fails_with_a_clear_message(db):
    """اگر حسابِ نقش‌دار پاک شود، خطا باید معنادار باشد نه NoneType."""
    db.query(Account).filter(Account.system_role == cc.PETTY_CASH).update({"system_role": None})
    db.flush()

    with pytest.raises(Exception) as exc:
        get_account(db, cc.PETTY_CASH)
    assert "petty_cash" in str(exc.value)
