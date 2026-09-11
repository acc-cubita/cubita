"""تسویه‌ی حسابِ طرف مقابل — تخصیص، نه پرداخت.

قیدِ اصلیِ این فایل در یک جمله: **تسویه نباید هیچ اثری بر دفتر بگذارد.** فاکتور و
رسید اثرشان را قبلاً زده‌اند و تسویه فقط می‌گوید کدام با کدام. اگر روزی سندی بزند،
ماندهٔ مشتری از واقعیت جدا می‌افتد بی‌آنکه چیزی خطا بدهد — و `test_settlement_writes_nothing_to_the_ledger`
همان لحظه قرمز می‌شود.

قیدِ دوم: **«تسویه‌شده» ذخیره نمی‌شود.** هرجا عددش لازم است از تخصیص‌ها جمع زده
می‌شود، پس برگشتِ تسویه خودبه‌خود مانده را آزاد می‌کند و جایی برای «دو ستونِ
ناهماهنگ» نمی‌ماند.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import JournalEntry, JournalLine
from app.models.settlement import Settlement
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.schemas.settlement import SettlementIn, SettlementItemIn
from app.schemas.treasury import TreasuryTransactionIn
from app.services import chart_codes as cc
from app.services import open_items as oi
from app.services import settlements as svc
from app.services.common import get_account
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.treasury import create_payment, create_receipt
from app.services.voiding import void_sales_invoice
from tests.factories import main_warehouse, make_contact, make_item

TODAY = date(2026, 6, 1)


# ───────────────────────────────── ساخت‌وسازها ─────────────────────────────────


def _stock_in(db, user, item, wh, qty=100, unit_cost=400_000):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY - timedelta(days=60),
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost))],
        ),
        user,
    )


def _sell(db, user, contact, price, on=TODAY):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh)
    return post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=on,
            warehouse_id=wh.id,
            contact_id=contact.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(price))],
        ),
        user,
    )


def _receipt(db, user, contact, amount, on=TODAY):
    return create_receipt(
        db,
        TreasuryTransactionIn(
            transaction_date=on, contact_id=contact.id, amount=Decimal(amount), method="cash"
        ),
        user,
    )


def _ar(db):
    return get_account(db, cc.ACCOUNTS_RECEIVABLE)


def _ap(db):
    return get_account(db, cc.ACCOUNTS_PAYABLE)


def _item_in(item, amount):
    return SettlementItemIn(
        source_type=item["source_type"],
        source_id=item["source_id"],
        side=item["side"],
        amount=Decimal(amount),
    )


def _settle(db, user, contact, account, pairs, on=TODAY, description=""):
    return svc.create_settlement(
        db,
        SettlementIn(
            settlement_date=on,
            contact_id=contact.id,
            account_id=account.id,
            description=description,
            items=[_item_in(item, amount) for item, amount in pairs],
        ),
        user,
    )


def _items(db, contact, account, **kwargs):
    return oi.open_items(db, account_id=account.id, contact_id=contact.id, **kwargs)


def _by_type(items, source_type):
    return next(item for item in items if item["source_type"] == source_type)


def _ledger_snapshot(db) -> tuple[int, Decimal, Decimal]:
    entries = db.query(JournalEntry).count()
    debit = sum(
        (Decimal(line.debit) for line in db.query(JournalLine).all()), Decimal(0)
    )
    credit = sum(
        (Decimal(line.credit) for line in db.query(JournalLine).all()), Decimal(0)
    )
    return entries, debit, credit


# ───────────────────────────── قیدِ اصلی: دفتر دست‌نخورده ─────────────────────


def test_settlement_writes_nothing_to_the_ledger(db, user):
    """**مهم‌ترین تست (§۲۲ §۲۳ §۲۴).**

    اثرِ مالی قبلاً ثبت شده؛ تسویه فقط رابطه است. سندِ دوم مانده را درست‌تر
    نمی‌کند، فقط دفتر را شلوغ می‌کند — و اگر روزی رقمش با اصل نخواند، خرابی
    بی‌صداست.
    """
    contact = make_contact(db, name="مشتری الف")
    _sell(db, user, contact, 200_000)
    _receipt(db, user, contact, 200_000)
    before = _ledger_snapshot(db)

    items = _items(db, contact, _ar(db))
    invoice = _by_type(items, "sales_invoice")
    receipt = _by_type(items, "treasury_receipt")
    _settle(db, user, contact, _ar(db), [(invoice, 200_000), (receipt, 200_000)])

    assert _ledger_snapshot(db) == before


def test_open_items_reconcile_with_the_account_balance(db, user):
    """جمعِ جبریِ اقلامِ باز = ماندهٔ همان معین (§۲۶ §۴۴).

    هر دو از یک ردیف‌های دفتر مشتق می‌شوند، پس نمی‌توانند به‌خاطرِ دو محاسبه‌ی جدا
    از هم جدا بیفتند. اگر روزی این تست بشکند یعنی یکی از دو مسیر ردیفی را
    می‌بیند که دیگری نمی‌بیند.
    """
    contact = make_contact(db, name="مشتری ب")
    _sell(db, user, contact, 500_000)
    _receipt(db, user, contact, 300_000)

    summary = svc.open_items_summary(db, account_id=_ar(db).id, contact_id=contact.id, only_open=False)
    ledger = sum(
        (Decimal(line.debit) - Decimal(line.credit))
        for line in db.query(JournalLine).filter(JournalLine.account_id == _ar(db).id).all()
    )
    assert summary["net"] == ledger == Decimal(200_000)
    assert summary["unattributed"] == Decimal(0)


def test_a_manual_entry_on_receivable_is_reported_not_swallowed(db, user):
    """**کشفِ داده‌ی واقعی.** گردشی که سندِ قابلِ تسویه ندارد نباید ناپدید شود.

    ردیفِ دستی روی دریافتنی (و همین‌طور ماندهٔ اول دوره، و چکی که پیش از مهاجرتِ
    ۰۱۱۰ ثبت شده و رویدادی ندارد) در دفتر هست ولی لنگرِ سندی ندارد تا تخصیص
    بخورد. حذفِ خاموشش یعنی بخشی از ماندهٔ مشتری در «اقلامِ باز» گم شود و کاربر
    نفهمد چرا دو عدد نمی‌خوانند. `unattributed` دقیقاً همان تفاوت را می‌گوید.
    """
    contact = make_contact(db, name="مشتری ب۲")
    _sell(db, user, contact, 100_000)

    entry = JournalEntry(
        entry_date=TODAY,
        description="تعدیلِ دستیِ دریافتنی",
        source_type="manual",
        created_by_id=user.id,
        lines=[
            JournalLine(account_id=_ar(db).id, debit=Decimal(50_000), credit=0, seq=1),
            JournalLine(
                account_id=get_account(db, cc.CASH).id, debit=0, credit=Decimal(50_000), seq=2
            ),
        ],
    )
    db.add(entry)
    db.flush()

    summary = svc.open_items_summary(db, account_id=_ar(db).id, only_open=False)
    assert summary["unattributed"] == Decimal(50_000)
    assert summary["net"] + summary["unattributed"] == summary["account_ledger_net"]
    #: و در فهرستِ اقلام نمی‌آید — چون واقعاً سندی برای تخصیص ندارد.
    assert all(i["source_type"] != "manual" for i in summary["items"])


# ───────────────────────────── ساختارِ تخصیص ─────────────────────────────────


def test_one_invoice_settles_against_two_receipts(db, user):
    """مثالِ خودِ فصل (§۱۶ §۲۰): فاکتورِ ۲۰۰ با دو رسیدِ ۱۰۰."""
    contact = make_contact(db, name="مشتری پ")
    _sell(db, user, contact, 200_000)
    _receipt(db, user, contact, 100_000)
    _receipt(db, user, contact, 100_000, on=TODAY + timedelta(days=1))

    items = _items(db, contact, _ar(db))
    invoice = _by_type(items, "sales_invoice")
    receipts = [i for i in items if i["source_type"] == "treasury_receipt"]
    assert len(receipts) == 2

    settlement = _settle(
        db,
        user,
        contact,
        _ar(db),
        [(invoice, 200_000), (receipts[0], 100_000), (receipts[1], 100_000)],
    )

    assert settlement.total_amount == Decimal(200_000)
    assert len(settlement.allocations) == 3
    assert _items(db, contact, _ar(db)) == []


def test_one_receipt_settles_against_two_invoices(db, user):
    """جهتِ معکوس هم باید ممکن باشد (§۱۷) — رابطه چند‌به‌چند است."""
    contact = make_contact(db, name="مشتری ت")
    _sell(db, user, contact, 60_000)
    _sell(db, user, contact, 40_000, on=TODAY + timedelta(days=1))
    _receipt(db, user, contact, 100_000)

    items = _items(db, contact, _ar(db))
    invoices = [i for i in items if i["source_type"] == "sales_invoice"]
    receipt = _by_type(items, "treasury_receipt")

    _settle(db, user, contact, _ar(db), [(invoices[0], 60_000), (invoices[1], 40_000), (receipt, 100_000)])
    assert _items(db, contact, _ar(db)) == []


def test_partial_settlement_leaves_the_rest_open(db, user):
    """تسویه‌ی جزئی (§۱۵ §۲۷): فاکتورِ ۱۰۰ با دریافتِ ۴۰ → مانده‌ی ۶۰ باز می‌ماند."""
    contact = make_contact(db, name="مشتری ث")
    _sell(db, user, contact, 100_000)
    _receipt(db, user, contact, 40_000)

    items = _items(db, contact, _ar(db))
    _settle(
        db,
        user,
        contact,
        _ar(db),
        [(_by_type(items, "sales_invoice"), 40_000), (_by_type(items, "treasury_receipt"), 40_000)],
    )

    invoice = _by_type(_items(db, contact, _ar(db)), "sales_invoice")
    assert invoice["document_amount"] == Decimal(100_000)
    assert invoice["settled_amount"] == Decimal(40_000)
    assert invoice["remaining_amount"] == Decimal(60_000)
    assert invoice["status"] == oi.PARTIAL


def test_an_unallocated_receipt_stays_visible(db, user):
    """پیش‌دریافت گم نمی‌شود (§۲۸ §۲۹).

    دریافتِ ۱۵۰ که فقط ۱۰۰ از آن به فاکتور خورده، هنوز ۵۰ مانده‌ی قابلِ تخصیص
    دارد — و همان ۵۰ است که فردا به فاکتورِ بعدی می‌خورد.
    """
    contact = make_contact(db, name="مشتری ج")
    _sell(db, user, contact, 100_000)
    _receipt(db, user, contact, 150_000)

    items = _items(db, contact, _ar(db))
    _settle(
        db,
        user,
        contact,
        _ar(db),
        [(_by_type(items, "sales_invoice"), 100_000), (_by_type(items, "treasury_receipt"), 100_000)],
    )

    receipt = _by_type(_items(db, contact, _ar(db)), "treasury_receipt")
    assert receipt["remaining_amount"] == Decimal(50_000)
    assert receipt["status"] == oi.PARTIAL


def test_a_fully_settled_document_leaves_the_picker(db, user):
    """سندی با مانده‌ی صفر دوباره قابلِ تخصیص نیست (§۳۳)."""
    contact = make_contact(db, name="مشتری چ")
    _sell(db, user, contact, 100_000)
    _receipt(db, user, contact, 100_000)
    items = _items(db, contact, _ar(db))
    _settle(
        db,
        user,
        contact,
        _ar(db),
        [(_by_type(items, "sales_invoice"), 100_000), (_by_type(items, "treasury_receipt"), 100_000)],
    )

    assert _items(db, contact, _ar(db)) == []
    every = _items(db, contact, _ar(db), only_open=False)
    assert {item["status"] for item in every} == {oi.SETTLED}


# ───────────────────────────── کنترل‌ها ─────────────────────────────────────


def test_unbalanced_settlement_is_refused_with_the_three_numbers(db, user):
    """§۲۱ — پیام باید هر سه عدد را بگوید، نه «خطایی رخ داد»."""
    contact = make_contact(db, name="مشتری ح")
    _sell(db, user, contact, 200_000)
    _receipt(db, user, contact, 180_000)
    items = _items(db, contact, _ar(db))

    with pytest.raises(HTTPException) as err:
        _settle(
            db,
            user,
            contact,
            _ar(db),
            [(_by_type(items, "sales_invoice"), 200_000), (_by_type(items, "treasury_receipt"), 180_000)],
        )

    assert err.value.status_code == 400
    detail = err.value.detail
    assert "۲۰۰,۰۰۰" in detail and "۱۸۰,۰۰۰" in detail and "۲۰,۰۰۰" in detail


def test_settling_more_than_the_remaining_is_refused(db, user):
    """§۱۴ — مبلغِ تسویه نمی‌تواند از مانده‌ی قابلِ تسویه بیشتر باشد."""
    contact = make_contact(db, name="مشتری خ")
    _sell(db, user, contact, 100_000)
    _receipt(db, user, contact, 500_000)
    items = _items(db, contact, _ar(db))

    with pytest.raises(HTTPException) as err:
        _settle(
            db,
            user,
            contact,
            _ar(db),
            [(_by_type(items, "sales_invoice"), 200_000), (_by_type(items, "treasury_receipt"), 200_000)],
        )
    assert "مانده‌ی قابلِ تسویه" in err.value.detail


def test_a_receipt_cannot_be_put_on_the_debit_side(db, user):
    """§۸ — سمت را اثرِ واقعیِ سند تعیین می‌کند، نه ستونی که کاربر انتخاب کرده.

    بدونِ این کنترل، کاربر می‌توانست دو رسید را یکی در هر ستون بگذارد، جمع‌ها
    تراز می‌شد و تسویه‌ای ثبت می‌شد که معنایش وارونه بود.
    """
    contact = make_contact(db, name="مشتری د")
    _sell(db, user, contact, 100_000)
    _receipt(db, user, contact, 100_000)
    items = _items(db, contact, _ar(db))
    receipt = _by_type(items, "treasury_receipt")

    with pytest.raises(HTTPException) as err:
        svc.create_settlement(
            db,
            SettlementIn(
                settlement_date=TODAY,
                contact_id=contact.id,
                account_id=_ar(db).id,
                items=[
                    SettlementItemIn(
                        source_type=receipt["source_type"],
                        source_id=receipt["source_id"],
                        side="debit",
                        amount=Decimal(100_000),
                    ),
                    _item_in(_by_type(items, "sales_invoice"), 100_000),
                ],
            ),
            user,
        )
    assert "در ستونِ دیگر نمی‌نشیند" in err.value.detail


def test_one_sided_settlement_is_refused(db, user):
    contact = make_contact(db, name="مشتری ذ")
    _sell(db, user, contact, 100_000)
    items = _items(db, contact, _ar(db))

    with pytest.raises(HTTPException) as err:
        _settle(db, user, contact, _ar(db), [(_by_type(items, "sales_invoice"), 100_000)])
    assert "هر دو سمت" in err.value.detail


def test_a_document_of_another_counterparty_is_refused(db, user):
    """§۴ — فاکتورِ مشتری الف با رسیدِ مشتری ب تسویه نمی‌شود."""
    alef = make_contact(db, name="مشتری ر")
    be = make_contact(db, name="مشتری ز")
    _sell(db, user, alef, 100_000)
    _receipt(db, user, be, 100_000)

    invoice = _by_type(_items(db, alef, _ar(db)), "sales_invoice")
    receipt = _by_type(_items(db, be, _ar(db)), "treasury_receipt")

    with pytest.raises(HTTPException) as err:
        _settle(db, user, alef, _ar(db), [(invoice, 100_000), (receipt, 100_000)])
    assert err.value.status_code == 400


def test_settlement_only_runs_on_a_counterparty_account(db, user):
    """§۵ §۳۱ — معین باید دریافتنی/پرداختنی باشد؛ صندوق حسابِ طرف مقابل نیست."""
    contact = make_contact(db, name="مشتری ژ")
    with pytest.raises(HTTPException) as err:
        oi.assert_counterparty_account(db, get_account(db, cc.CASH).id)
    assert "معینِ طرف مقابل نیست" in err.value.detail
    assert contact is not None


def test_the_same_document_twice_in_one_settlement_is_refused(db, user):
    contact = make_contact(db, name="مشتری س")
    _sell(db, user, contact, 100_000)
    _receipt(db, user, contact, 100_000)
    items = _items(db, contact, _ar(db))
    invoice = _by_type(items, "sales_invoice")

    with pytest.raises(HTTPException) as err:
        _settle(
            db,
            user,
            contact,
            _ar(db),
            [(invoice, 50_000), (invoice, 50_000), (_by_type(items, "treasury_receipt"), 100_000)],
        )
    assert "دوبار" in err.value.detail


# ───────────────────────────── سمتِ پرداختنی ─────────────────────────────────


def test_a_purchase_invoice_is_a_credit_item(db, user):
    """§۸ دوباره، از سمتِ دیگر: «فاکتور» به‌خودیِ‌خود بدهکار نیست.

    فاکتورِ خرید پرداختنی را **بستانکار** می‌کند و پرداختِ ما بدهکارش — یعنی
    دقیقاً وارونه‌ی سناریوی مشتری. اگر جهت از نامِ فرم استنتاج می‌شد، این تسویه
    هرگز تراز نمی‌شد.
    """
    supplier = make_contact(db, name="تأمین‌کننده الف", type_="supplier")
    wh = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            contact_id=supplier.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_cost=Decimal(300_000))],
        ),
        user,
    )
    create_payment(
        db,
        TreasuryTransactionIn(
            transaction_date=TODAY, contact_id=supplier.id, amount=Decimal(300_000), method="cash"
        ),
        user,
    )

    items = _items(db, supplier, _ap(db))
    invoice = _by_type(items, "purchase_invoice")
    payment = _by_type(items, "treasury_payment")
    assert invoice["side"] == "credit"
    assert payment["side"] == "debit"

    settlement = _settle(db, user, supplier, _ap(db), [(invoice, 300_000), (payment, 300_000)])
    assert settlement.total_amount == Decimal(300_000)
    assert _items(db, supplier, _ap(db)) == []


def test_receivable_and_payable_of_one_company_stay_apart(db, user):
    """§۳۰ §۳۱ — یک شرکت هم مشتری است هم تأمین‌کننده؛ تهاتر خودکار نمی‌شود.

    فاکتورِ فروشِ او روی دریافتنی است و فاکتورِ خریدش روی پرداختنی. هیچ‌کدام در
    فهرستِ دیگری دیده نمی‌شود، پس امکانِ تهاترِ ناخواسته وجود ندارد.
    """
    both = make_contact(db, name="شرکت دوسویه")
    _sell(db, user, both, 100_000)
    wh = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            contact_id=both.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_cost=Decimal(100_000))],
        ),
        user,
    )

    receivable_side = {i["source_type"] for i in _items(db, both, _ar(db))}
    payable_side = {i["source_type"] for i in _items(db, both, _ap(db))}
    assert receivable_side == {"sales_invoice"}
    assert payable_side == {"purchase_invoice"}


# ───────────────────────────── برگشت و ردیابی ───────────────────────────────


def test_voiding_a_settlement_frees_the_documents(db, user):
    """§۳۷ §۳۸ — رابطه آزاد می‌شود، اسناد دست‌نخورده می‌مانند."""
    contact = make_contact(db, name="مشتری ش")
    invoice_doc = _sell(db, user, contact, 100_000)
    receipt_doc = _receipt(db, user, contact, 100_000)
    items = _items(db, contact, _ar(db))
    settlement = _settle(
        db,
        user,
        contact,
        _ar(db),
        [(_by_type(items, "sales_invoice"), 100_000), (_by_type(items, "treasury_receipt"), 100_000)],
    )
    assert _items(db, contact, _ar(db)) == []

    svc.void_settlement(db, settlement.id, reason="اشتباه ثبت شد", user=user)

    freed = _items(db, contact, _ar(db))
    assert {i["source_type"] for i in freed} == {"sales_invoice", "treasury_receipt"}
    assert all(i["remaining_amount"] == Decimal(100_000) for i in freed)
    #: اسنادِ منبع سرِ جایشان — تسویه مالکشان نبود.
    assert invoice_doc.voided_at is None
    assert receipt_doc.id is not None
    #: ردیف‌های تخصیص پاک نمی‌شوند؛ سابقه می‌ماند.
    assert len(db.get(Settlement, settlement.id).allocations) == 2


def test_a_partial_void_restores_only_what_it_took(db, user):
    """§۳۷ — از دو تسویه، برگشتِ یکی فقط سهمِ خودش را آزاد می‌کند."""
    contact = make_contact(db, name="مشتری ص")
    _sell(db, user, contact, 100_000)
    _receipt(db, user, contact, 60_000)
    _receipt(db, user, contact, 40_000, on=TODAY + timedelta(days=1))

    items = _items(db, contact, _ar(db))
    invoice = _by_type(items, "sales_invoice")
    receipts = [i for i in items if i["source_type"] == "treasury_receipt"]
    first = _settle(db, user, contact, _ar(db), [(invoice, 60_000), (receipts[0], 60_000)])

    items = _items(db, contact, _ar(db))
    _settle(
        db,
        user,
        contact,
        _ar(db),
        [(_by_type(items, "sales_invoice"), 40_000), (receipts[1], 40_000)],
    )
    assert _items(db, contact, _ar(db)) == []

    svc.void_settlement(db, first.id, reason="", user=user)
    invoice_now = _by_type(_items(db, contact, _ar(db)), "sales_invoice")
    assert invoice_now["settled_amount"] == Decimal(40_000)
    assert invoice_now["remaining_amount"] == Decimal(60_000)


def test_allocation_history_shows_each_step_and_its_counterpart(db, user):
    """§۳۵ §۳۶ — «تسویه‌شده: ۱۰۰» کافی نیست؛ باید گفت کِی و با چه چیزی."""
    contact = make_contact(db, name="مشتری ض")
    _sell(db, user, contact, 100_000)
    _receipt(db, user, contact, 30_000)
    _receipt(db, user, contact, 70_000, on=TODAY + timedelta(days=10))

    items = _items(db, contact, _ar(db))
    invoice = _by_type(items, "sales_invoice")
    receipts = [i for i in items if i["source_type"] == "treasury_receipt"]
    _settle(db, user, contact, _ar(db), [(invoice, 30_000), (receipts[0], 30_000)])
    _settle(
        db,
        user,
        contact,
        _ar(db),
        [(_by_type(_items(db, contact, _ar(db)), "sales_invoice"), 70_000), (receipts[1], 70_000)],
        on=TODAY + timedelta(days=10),
    )

    history = oi.allocation_history(db, invoice["source_type"], invoice["source_id"])
    assert [row["amount"] for row in history] == [Decimal(30_000), Decimal(70_000)]
    assert all(row["side"] == "debit" for row in history)
    #: سمتِ مقابل — همان چیزی که سؤالِ «بابتِ چه؟» را جواب می‌دهد.
    assert all(row["counter_items"][0]["source_type"] == "treasury_receipt" for row in history)


def test_a_voided_settlement_stays_in_the_history(db, user):
    """«چرا مانده برگشت؟» بدونِ دیدنِ تسویه‌ی برگشت‌خورده بی‌جواب می‌ماند."""
    contact = make_contact(db, name="مشتری ط")
    _sell(db, user, contact, 100_000)
    _receipt(db, user, contact, 100_000)
    items = _items(db, contact, _ar(db))
    invoice = _by_type(items, "sales_invoice")
    settlement = _settle(
        db, user, contact, _ar(db), [(invoice, 100_000), (_by_type(items, "treasury_receipt"), 100_000)]
    )
    svc.void_settlement(db, settlement.id, reason="اشتباه", user=user)

    history = oi.allocation_history(db, invoice["source_type"], invoice["source_id"])
    assert len(history) == 1
    assert history[0]["voided"] is True


# ───────────────────────────── سلامتِ سندِ منبع ───────────────────────────────


def test_voiding_an_allocated_invoice_is_refused(db, user):
    """§۴۱ — ابطالِ سندی که تخصیص خورده بی‌صدا تخصیص را یتیم می‌کرد.

    چون تسویه سندِ حسابداری نمی‌زند، هیچ ترازی هم به‌هم نمی‌خورد تا خطا را لو
    بدهد؛ پس گارد لازم است نه اختیاری.
    """
    contact = make_contact(db, name="مشتری ظ")
    invoice_doc = _sell(db, user, contact, 100_000)
    _receipt(db, user, contact, 100_000)
    items = _items(db, contact, _ar(db))
    _settle(
        db,
        user,
        contact,
        _ar(db),
        [(_by_type(items, "sales_invoice"), 100_000), (_by_type(items, "treasury_receipt"), 100_000)],
    )

    with pytest.raises(HTTPException) as err:
        void_sales_invoice(db, invoice_doc.id, reason="اشتباه", user=user)
    assert err.value.status_code == 409
    assert "تسویه" in err.value.detail


def test_after_the_settlement_is_reversed_the_invoice_can_be_voided(db, user):
    """همان گارد نباید بن‌بست بسازد: مسیرِ درست در پیامِ خطا گفته شده."""
    contact = make_contact(db, name="مشتری ع")
    invoice_doc = _sell(db, user, contact, 100_000)
    _receipt(db, user, contact, 100_000)
    items = _items(db, contact, _ar(db))
    settlement = _settle(
        db,
        user,
        contact,
        _ar(db),
        [(_by_type(items, "sales_invoice"), 100_000), (_by_type(items, "treasury_receipt"), 100_000)],
    )
    svc.void_settlement(db, settlement.id, reason="", user=user)

    void_sales_invoice(db, invoice_doc.id, reason="اشتباه", user=user)
    assert invoice_doc.voided_at is not None


# ───────────────────────────── شماره و تکرار ─────────────────────────────────


def test_settlements_get_gap_free_numbers(db, user):
    contact = make_contact(db, name="مشتری غ")
    _sell(db, user, contact, 100_000)
    _receipt(db, user, contact, 60_000)
    _receipt(db, user, contact, 40_000, on=TODAY + timedelta(days=1))
    items = _items(db, contact, _ar(db))
    invoice = _by_type(items, "sales_invoice")
    receipts = [i for i in items if i["source_type"] == "treasury_receipt"]

    first = _settle(db, user, contact, _ar(db), [(invoice, 60_000), (receipts[0], 60_000)])
    second = _settle(
        db,
        user,
        contact,
        _ar(db),
        [(_by_type(_items(db, contact, _ar(db)), "sales_invoice"), 40_000), (receipts[1], 40_000)],
    )
    assert second.number == first.number + 1


def test_the_stored_total_matches_the_allocations(db, user):
    contact = make_contact(db, name="مشتری ف")
    _sell(db, user, contact, 100_000)
    _receipt(db, user, contact, 100_000)
    items = _items(db, contact, _ar(db))
    settlement = _settle(
        db,
        user,
        contact,
        _ar(db),
        [(_by_type(items, "sales_invoice"), 100_000), (_by_type(items, "treasury_receipt"), 100_000)],
    )
    svc.verify_totals(db, settlement)  # نباید چیزی پرتاب کند


# ───────────────────────────── اندپوینت‌ها ───────────────────────────────────


def test_endpoints_exist_and_are_wired(client, db, user):
    contact = make_contact(db, name="مشتری ق")
    _sell(db, user, contact, 100_000)
    _receipt(db, user, contact, 100_000)
    db.commit()

    accounts = client.get("/api/settlements/accounts").json()
    assert len(accounts) == 2

    ar = next(a for a in accounts if a["code"])
    summary = client.get(
        "/api/settlements/open-items", params={"account_id": ar["id"], "contact_id": str(contact.id)}
    ).json()
    assert len(summary["items"]) == 2

    payload = {
        "settlement_date": str(TODAY),
        "contact_id": str(contact.id),
        "account_id": ar["id"],
        "description": "تسویه‌ی آزمایشی",
        "items": [
            {
                "source_type": item["source_type"],
                "source_id": item["source_id"],
                "side": item["side"],
                "amount": item["remaining_amount"],
            }
            for item in summary["items"]
        ],
    }
    created = client.post("/api/settlements", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["total_amount"] in ("100000", "100000.00", 100000)
    assert len(body["allocations"]) == 2

    listed = client.get("/api/settlements").json()
    assert [row["id"] for row in listed] == [body["id"]]

    voided = client.post(f"/api/settlements/{body['id']}/void", json={"reason": "آزمایش"})
    assert voided.status_code == 200
    assert voided.json()["voided_at"] is not None


def test_retrying_the_same_request_does_not_double_the_allocation(client, db, user):
    """§۵۰ — Retry نباید تخصیص‌ها را دو برابر کند.

    اینجا خطرش از تسویه‌ی کارت‌خوان بیشتر است: چون سندی زده نمی‌شود، دو برابر شدنِ
    تخصیص هیچ ترازی را به‌هم نمی‌زند و تنها نشانه‌اش «تسویه‌شده»ی غلط است.
    """
    contact = make_contact(db, name="مشتری ک")
    _sell(db, user, contact, 100_000)
    _receipt(db, user, contact, 100_000)
    db.commit()

    ar = next(a for a in client.get("/api/settlements/accounts").json() if a["code"])
    summary = client.get(
        "/api/settlements/open-items", params={"account_id": ar["id"], "contact_id": str(contact.id)}
    ).json()
    payload = {
        "settlement_date": str(TODAY),
        "contact_id": str(contact.id),
        "account_id": ar["id"],
        "items": [
            {
                "source_type": i["source_type"],
                "source_id": i["source_id"],
                "side": i["side"],
                "amount": i["remaining_amount"],
            }
            for i in summary["items"]
        ],
    }
    headers = {"Idempotency-Key": "settlement-retry-1"}
    first = client.post("/api/settlements", json=payload, headers=headers)
    second = client.post("/api/settlements", json=payload, headers=headers)

    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len(client.get("/api/settlements").json()) == 1
