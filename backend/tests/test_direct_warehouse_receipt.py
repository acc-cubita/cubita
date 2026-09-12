"""رسیدِ انبار: دو مسیرِ معتبر، و **یک** نقطه‌ی ثبتِ بدهی.

مهم‌ترین ادعای این فایل همان هشدارِ مرکزیِ فصل است: فاکتور و رسید نباید یک بدهی
را دو بار ثبت کنند. پس هر دو مسیر سنجیده می‌شوند:

  فاکتور → رسید   :  بدهی یک‌بار (سرِ فاکتور)، رسید سند نمی‌زند
  رسیدِ مستقیم     :  بدهی یک‌بار (سرِ رسید)، چون فاکتوری در کار نیست
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import JournalEntry, JournalLine
from app.models.invoices import RECEIPT_TYPES, WarehouseReceipt
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    WarehouseReceiptIn,
    WarehouseReceiptLineIn,
)
from app.services import chart_codes as cc
from app.services.common import get_account
from app.services.inventory import get_stock_qty, post_purchase_invoice
from app.services.reports import get_inventory_report
from app.services.warehouse_receipts import create_warehouse_receipt, void_warehouse_receipt
from tests.factories import main_warehouse, make_contact, make_item

TODAY = date(2026, 3, 15)


class Ledger:
    """دلتای ماندهٔ حساب‌ها — پایگاهِ آزمون در اجرای کامل صفر نیست."""

    def __init__(self, db):
        self.db = db
        self.before = {}

    def snap(self, role):
        self.before[role] = self._balance(role)
        return self

    def delta(self, role):
        return self._balance(role) - self.before[role]

    def _balance(self, role):
        account_id = get_account(self.db, role).id
        rows = (
            self.db.query(JournalLine.debit, JournalLine.credit)
            .filter(JournalLine.account_id == account_id)
            .all()
        )
        return sum((Decimal(d) - Decimal(c) for d, c in rows), Decimal(0))


def direct_receipt(db, user, *, item, qty=10, unit_cost=5_000_000, contact=None, **kwargs):
    return create_warehouse_receipt(
        db,
        None,
        WarehouseReceiptIn(
            receipt_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            contact_id=contact.id if contact else None,
            lines=[
                WarehouseReceiptLineIn(
                    item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost)
                )
            ],
            **kwargs,
        ),
        user,
    )


# ─────────────────── مسیرِ دوم: رسیدِ مستقیم (§۸ §۹ §۱۰) ───────────────────


def test_a_receipt_can_be_created_without_any_invoice(db, user):
    """اصلاحِ مرکزیِ فصل.

    تا امروز `purchase_invoice_id` اجباری بود و تنها راهِ ساخت از دلِ فاکتور —
    یعنی خریدی که فاکتورش بعداً می‌آید هیچ راهی برای ورودِ کالا نداشت.
    """
    item = make_item(db, name="لیوان")
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")

    receipt = direct_receipt(db, user, item=item, contact=supplier)

    assert receipt.purchase_invoice_id is None
    assert receipt.lines[0].purchase_invoice_line_id is None
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(10)


def test_a_direct_receipt_posts_its_own_journal(db, user):
    """§۳۴ — رسیدِ مستقیم خودش منشأِ مالی است.

    نزدنِ سند یعنی کالا بی‌هیچ اثرِ حسابداری وارد انبار شود و دفتر با گزارشِ
    انبار برای همیشه واگرا بماند.
    """
    item = make_item(db, name="لیوان")
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    ledger = Ledger(db).snap(cc.INVENTORY).snap(cc.ACCOUNTS_PAYABLE)

    receipt = direct_receipt(db, user, item=item, qty=10, unit_cost=5_000_000, contact=supplier)

    assert receipt.journal_entry_id is not None
    assert ledger.delta(cc.INVENTORY) == Decimal(50_000_000)
    assert ledger.delta(cc.ACCOUNTS_PAYABLE) == Decimal(-50_000_000)


def test_a_direct_receipt_keeps_ledger_and_stock_report_together(db, user):
    """دفتر و گزارشِ انبار باید یک عدد بگویند."""
    item = make_item(db, name="لیوان")
    ledger = Ledger(db).snap(cc.INVENTORY)
    before = Decimal(get_inventory_report(db, None, as_of=TODAY)["total_value"])

    direct_receipt(db, user, item=item, qty=4, unit_cost=1_000_000)

    moved_report = Decimal(get_inventory_report(db, None, as_of=TODAY)["total_value"]) - before
    assert ledger.delta(cc.INVENTORY) == moved_report == Decimal(4_000_000)


def test_a_direct_receipt_without_a_deliverer_is_a_cash_purchase(db, user):
    """قاعده همان است که فاکتورِ خرید دارد — دو موتور یک تصمیم را دو جور نمی‌گیرند."""
    item = make_item(db, name="لیوان")
    ledger = Ledger(db).snap(cc.CASH).snap(cc.ACCOUNTS_PAYABLE)

    direct_receipt(db, user, item=item, qty=2, unit_cost=1_000_000)

    assert ledger.delta(cc.CASH) == Decimal(-2_000_000)
    assert ledger.delta(cc.ACCOUNTS_PAYABLE) == Decimal(0)


def test_a_service_on_a_direct_receipt_goes_to_expense(db, user):
    """§۳۵ — یک رسید چند ردیفِ سند می‌سازد؛ خدمت به هزینه می‌نشیند نه به موجودی."""
    service = make_item(db, name="حمل", is_service=True)
    ledger = Ledger(db).snap(cc.INVENTORY).snap(cc.SERVICE_EXPENSE)

    direct_receipt(db, user, item=service, qty=1, unit_cost=3_000_000)

    assert ledger.delta(cc.SERVICE_EXPENSE) == Decimal(3_000_000)
    assert ledger.delta(cc.INVENTORY) == Decimal(0)


def test_a_zero_value_direct_receipt_posts_nothing(db, user):
    """سندِ صفر چیزی توضیح نمی‌دهد و فقط دفتر را شلوغ می‌کند."""
    item = make_item(db, name="نمونه رایگان")
    receipt = direct_receipt(db, user, item=item, qty=5, unit_cost=0)

    assert receipt.journal_entry_id is None
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(5)


# ─────────────── مسیرِ اول: از دلِ فاکتور — بدون ثبتِ دوباره (§۳۷) ───────────────


def test_an_invoice_backed_receipt_posts_no_journal(db, user):
    """**مهم‌ترین ادعای فصل.**

    اگر فاکتور و رسید هر دو بدهی را ثبت کنند، حسابِ تأمین‌کننده دقیقاً دو برابر
    می‌شود — و چون هر دو سند متوازن‌اند، هیچ ترازی به‌هم نمی‌خورد که خبر بدهد.
    """
    item = make_item(db, name="لیوان")
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    ledger = Ledger(db).snap(cc.ACCOUNTS_PAYABLE)

    invoice = post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=None,
            contact_id=supplier.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(5_000_000))],
        ),
        user,
    )
    after_invoice = ledger.delta(cc.ACCOUNTS_PAYABLE)

    receipt = create_warehouse_receipt(
        db,
        invoice.id,
        WarehouseReceiptIn(
            receipt_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[
                WarehouseReceiptLineIn(
                    purchase_invoice_line_id=invoice.lines[0].id, qty=Decimal(10)
                )
            ],
        ),
        user,
    )

    assert receipt.journal_entry_id is None, "رسیدِ گره‌خورده به فاکتور نباید سند بزند"
    assert ledger.delta(cc.ACCOUNTS_PAYABLE) == after_invoice == Decimal(-50_000_000)


def test_the_deliverer_falls_back_to_the_invoice_counterparty(db, user):
    """§۶ — در خریدِ داخلی تحویل‌دهنده همان طرفِ معامله است، اگر چیزِ دیگری گفته نشود."""
    item = make_item(db, name="لیوان")
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    invoice = post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=None,
            contact_id=supplier.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(3), unit_cost=Decimal(1_000_000))],
        ),
        user,
    )
    receipt = create_warehouse_receipt(
        db,
        invoice.id,
        WarehouseReceiptIn(
            receipt_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[WarehouseReceiptLineIn(purchase_invoice_line_id=invoice.lines[0].id, qty=Decimal(3))],
        ),
        user,
    )
    assert receipt.contact_id == supplier.id


# ─────────────────── نوعِ رسید و سه نقشِ جدا (§۲ §۶ §۷) ───────────────────


def test_five_receipt_types_exist(db, user):
    """§۲ §۳ — یک موتور، پنج منشأ. نه پنج جدول."""
    assert set(RECEIPT_TYPES) == {
        "purchase_domestic",
        "purchase_import",
        "production",
        "other",
        "opening",
    }


def test_the_type_is_stored_on_the_receipt(db, user):
    item = make_item(db, name="محصول")
    receipt = direct_receipt(db, user, item=item, receipt_type="production")
    assert receipt.receipt_type == "production"


def test_an_unknown_type_is_refused(db, user):
    item = make_item(db, name="لیوان")
    with pytest.raises(Exception):
        direct_receipt(db, user, item=item, receipt_type="teleportation")


def test_deliverer_carrier_and_freight_agent_stay_separate(db, user):
    """§۷ — «این سه مفهوم را از همان اول در یک فیلد supplier قاطی نکنیم»."""
    item = make_item(db, name="لیوان")
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    carrier = make_contact(db, name="باربری", type_="supplier")
    agent = make_contact(db, name="واسط حمل", type_="supplier")

    receipt = create_warehouse_receipt(
        db,
        None,
        WarehouseReceiptIn(
            receipt_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            contact_id=supplier.id,
            carrier_id=carrier.id,
            freight_agent_id=agent.id,
            lines=[WarehouseReceiptLineIn(item_id=item.id, qty=Decimal(1), unit_cost=Decimal(1))],
        ),
        user,
    )
    assert (receipt.contact_id, receipt.carrier_id, receipt.freight_agent_id) == (
        supplier.id,
        carrier.id,
        agent.id,
    )


# ─────────────────── گاردها و ابطال ───────────────────


def test_an_inactive_warehouse_refuses_a_receipt(db, user):
    """گاردِ مشترکِ فصلِ انبار، نه یک بررسیِ محلیِ دوباره."""
    item = make_item(db, name="لیوان")
    warehouse = main_warehouse(db)
    warehouse.is_active = False
    db.flush()

    with pytest.raises(HTTPException) as err:
        direct_receipt(db, user, item=item)
    assert err.value.status_code == 400


def test_a_warehouse_the_item_is_not_allowed_in_is_refused(db, user):
    """§۲۹ از فصلِ کالا — رسید هم همان قاعده را می‌بیند."""
    from app.services import items as items_svc
    from tests.factories import other_warehouse

    item = make_item(db, name="مواد اولیه")
    items_svc.set_warehouses(db, item, [{"warehouse_id": other_warehouse(db).id}])

    with pytest.raises(HTTPException) as err:
        direct_receipt(db, user, item=item)
    assert err.value.status_code == 400


def test_an_unknown_item_on_a_direct_receipt_is_refused(db, user):
    from uuid import uuid4

    with pytest.raises(HTTPException) as err:
        create_warehouse_receipt(
            db,
            None,
            WarehouseReceiptIn(
                receipt_date=TODAY,
                warehouse_id=main_warehouse(db).id,
                lines=[WarehouseReceiptLineIn(item_id=uuid4(), qty=Decimal(1), unit_cost=Decimal(1))],
            ),
            user,
        )
    assert err.value.status_code == 400


def test_voiding_a_direct_receipt_removes_the_stock(db, user):
    """§۴۶ — ابطالِ کنترل‌شده، نه حذفِ فیزیکی."""
    item = make_item(db, name="لیوان")
    receipt = direct_receipt(db, user, item=item, qty=6, unit_cost=1_000_000)
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(6)

    void_warehouse_receipt(db, receipt.id, reason="اشتباه بود", user=user)
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(0)
    assert receipt.is_voided


def test_the_journal_points_back_to_the_receipt(db, user):
    """§۳۴ — شرحِ سند صریحاً به رسید ارجاع می‌دهد و منشأ قابلِ پیمایش است."""
    item = make_item(db, name="لیوان")
    receipt = direct_receipt(db, user, item=item, qty=1, unit_cost=1_000_000)

    entry = db.get(JournalEntry, receipt.journal_entry_id)
    assert entry.source_type == "warehouse_receipt"
    assert f"رسید انبار شماره {receipt.number}" in entry.description


def test_the_source_registry_knows_the_receipt(db, user):
    """رجیستریِ منشأ باید رسید را بشناسد، وگرنه سند از دفتر قابلِ پیمایش نیست."""
    from app.services.entry_source import SOURCE_MODELS

    assert SOURCE_MODELS["warehouse_receipt"] is WarehouseReceipt
