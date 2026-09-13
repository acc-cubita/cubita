"""فصلِ «فاکتور خرید خدمات» — هزینه‌ی کامل، بدهی‌های تفکیک‌شده، مانده‌ی واقعی.

ادعای اصلیِ فصل و این فایل: **هزینه‌ی خدمت با بدهی به تأمین‌کننده یکی نیست.**
در مثالِ ویدیو ۱۰۰ میلیون مشاوره‌ی حقوقی هزینه است، ولی فقط ۸۰٫۳۳۳ میلیون به
فروشنده بدهکاریم؛ ۳ میلیون مالِ سازمانِ مالیاتی و ۱۶٫۶۶۷ میلیون مالِ بیمه است.

هر سه عدد باید در دفتر، در مانده‌ی طرف مقابل و در پیشنهادِ پرداخت درست بنشینند —
و هیچ‌کدام از خطاهایشان ترازی را به‌هم نمی‌زند. سندِ «۱۰۰ بدهکار هزینه، ۱۰۰
بستانکار تأمین‌کننده» هم متوازن است.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.accounting import Account, JournalLine
from app.models.advanced_inventory import StockBatch
from app.models.inventory import StockLedger
from app.schemas.invoices import (
    PurchaseDeductionIn,
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    WarehouseReceiptIn,
    WarehouseReceiptLineIn,
)
from app.schemas.purchase_deductions import PurchaseDeductionTypeIn
from app.schemas.returns import PurchaseReturnIn, PurchaseReturnLineIn
from app.services import chart_codes as cc
from app.services import purchase_deductions as deductions_svc
from app.services.common import get_account
from app.services.inventory import duplicate_purchase_invoice_draft, post_purchase_invoice
from app.services.open_items import open_items
from app.services.printing import fa_number
from app.services.returns import post_purchase_return
from app.services.voiding import void_purchase_invoice
from app.services.warehouse_receipts import create_warehouse_receipt
from tests.factories import main_warehouse, make_contact, make_item

TODAY = date(2026, 3, 15)


def balance(db, account_id) -> Decimal:
    rows = db.query(JournalLine.debit, JournalLine.credit).filter(JournalLine.account_id == account_id).all()
    return sum((Decimal(d) - Decimal(c) for d, c in rows), Decimal(0))


class Ledger:
    """دلتای مانده‌ی حساب‌ها، نه مانده‌ی مطلق — تست‌های هم‌زمانی بیرون از تراکنش commit می‌کنند."""

    def __init__(self, db, **accounts):
        self.db = db
        self.accounts = accounts
        self.before = {key: balance(db, account_id) for key, account_id in accounts.items()}

    def delta(self, key):
        return balance(self.db, self.accounts[key]) - self.before[key]


def deduction_type(db, name, nature, rate, *, basis="net_before_tax", account_id=None):
    return deductions_svc.create_type(
        db,
        PurchaseDeductionTypeIn(
            name=name, nature=nature, rate=Decimal(str(rate)), basis=basis, account_id=account_id
        ),
    )["id"]


def video_types(db):
    """نرخ‌های ویدیو — تعریفِ خودِ کسب‌وکار، نه قاعده‌ای که کوبیتا فرض کند."""
    return (
        deduction_type(db, "مالیات تکلیفی قرارداد", "withholding_tax", "3"),
        deduction_type(db, "حق بیمه قرارداد", "insurance", "16.667"),
    )


def buy_service(
    db, user, service, supplier, *, qty=2, unit_cost=50_000_000, deductions=(), tax_rate=0,
    discount=0, expense_account_id=None,
):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            kind="service",
            invoice_date=TODAY,
            contact_id=supplier.id,
            tax_rate=Decimal(tax_rate),
            lines=[
                PurchaseInvoiceLineIn(
                    item_id=service.id,
                    qty=Decimal(qty),
                    unit_cost=Decimal(unit_cost),
                    discount=Decimal(discount),
                    expense_account_id=expense_account_id,
                )
            ],
            deductions=[
                d if isinstance(d, PurchaseDeductionIn) else PurchaseDeductionIn(deduction_type_id=d)
                for d in deductions
            ],
        ),
        user,
    )


def buy_goods_invoice(db, user, item, supplier, *, warehouse=False, unit_cost=1_000_000):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id if warehouse else None,
            contact_id=supplier.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_cost=Decimal(unit_cost))],
        ),
        user,
    )


def return_service(db, user, invoice, service, qty):
    return post_purchase_return(
        db,
        PurchaseReturnIn(
            return_date=TODAY,
            purchase_invoice_id=invoice.id,
            lines=[PurchaseReturnLineIn(item_id=service.id, qty=Decimal(qty))],
        ),
        user,
    )


def rent_account(db):
    return db.query(Account).filter(Account.code == "5103").one()


@pytest.fixture
def legal(db):
    service = make_item(db, name="مشاوره حقوقی", is_service=True)
    supplier = make_contact(db, name="دفتر حقوقی", type_="supplier")
    return service, supplier


# ─────────────────── §۲۷–§۳۰ — هزینه یکی، بدهی سه‌تا ───────────────────


def test_the_video_invoice_splits_the_expense_into_three_liabilities(db, user, legal):
    service, supplier = legal
    withholding, insurance = video_types(db)

    invoice = buy_service(db, user, service, supplier, deductions=[withholding, insurance])

    lines = db.query(JournalLine).filter(JournalLine.entry_id == invoice.journal_entry_id).all()
    by_role = {
        db.get(Account, line.account_id).system_role: (Decimal(line.debit), Decimal(line.credit))
        for line in lines
    }
    assert len(lines) == 4
    assert by_role[cc.SERVICE_EXPENSE] == (Decimal(100_000_000), Decimal(0))
    assert by_role[cc.WITHHOLDING_TAX_PAYABLE] == (Decimal(0), Decimal(3_000_000))
    assert by_role[cc.CONTRACT_INSURANCE_PAYABLE] == (Decimal(0), Decimal(16_667_000))
    assert by_role[cc.ACCOUNTS_PAYABLE] == (Decimal(0), Decimal(80_333_000))
    assert sum(Decimal(l.debit) for l in lines) == sum(Decimal(l.credit) for l in lines)
    assert Decimal(invoice.total_deductions) == Decimal(19_667_000)
    assert invoice.payable_amount == Decimal(80_333_000)


def test_a_service_invoice_moves_no_stock(db, user, legal):
    service, supplier = legal
    invoice = buy_service(db, user, service, supplier)

    assert db.query(StockLedger).filter(StockLedger.source_id == invoice.id).count() == 0
    assert db.query(StockBatch).filter(StockBatch.source_id == invoice.id).count() == 0
    assert invoice.warehouse_id is None
    assert invoice.goods_in_transit is False


def test_vat_is_owed_to_the_supplier_and_never_deducted(db, user, legal):
    """ارزش افزوده مبلغِ فاکتور را زیاد می‌کند؛ کسورات بدهی را جابه‌جا. یک ستون نیستند (§۳۲)."""
    service, supplier = legal
    withholding, insurance = video_types(db)
    ledger = Ledger(db, ap=get_account(db, cc.ACCOUNTS_PAYABLE).id)

    invoice = buy_service(db, user, service, supplier, tax_rate=10, deductions=[withholding, insurance])

    assert Decimal(invoice.tax_amount) == Decimal(10_000_000)
    assert [Decimal(row.basis_amount) for row in invoice.deductions] == [Decimal(100_000_000)] * 2
    assert ledger.delta("ap") == Decimal(-90_333_000)


def test_the_basis_decides_whether_the_discount_counts(db, user, legal):
    service, supplier = legal
    on_net = deduction_type(db, "تکلیفی روی خالص", "withholding_tax", "3")
    on_gross = deduction_type(db, "بیمه روی ناخالص", "insurance", "5", basis="gross")

    invoice = buy_service(db, user, service, supplier, discount=10_000_000, deductions=[on_net, on_gross])

    amounts = {row.name_snapshot: Decimal(row.amount) for row in invoice.deductions}
    assert amounts["تکلیفی روی خالص"] == Decimal(2_700_000)
    assert amounts["بیمه روی ناخالص"] == Decimal(5_000_000)


def test_a_typed_amount_wins_and_later_rate_changes_do_not_rewrite_it(db, user, legal):
    """§۱۳ §۴۹ — تعریفِ امروز فاکتورِ دیروز را بازنویسی نمی‌کند."""
    service, supplier = legal
    withholding = deduction_type(db, "تکلیفی", "withholding_tax", "3")

    invoice = buy_service(
        db, user, service, supplier,
        deductions=[PurchaseDeductionIn(deduction_type_id=withholding, amount=Decimal(2_500_000))],
    )
    row = invoice.deductions[0]
    assert (Decimal(row.amount), Decimal(row.rate)) == (Decimal(2_500_000), Decimal(3))

    deductions_svc.update_type(
        db, withholding, PurchaseDeductionTypeIn(name="تکلیفی", nature="withholding_tax", rate=Decimal(5))
    )
    db.refresh(row)
    assert (Decimal(row.amount), Decimal(row.rate)) == (Decimal(2_500_000), Decimal(3))


# ─────────────────── §۱ §۴۷ — سندِ مستقل، نه فرمِ پر از if ───────────────────


def test_service_invoices_have_their_own_number_series(db, user, legal):
    service, supplier = legal
    product = make_item(db, name="کاغذ")

    first = buy_service(db, user, service, supplier)
    goods = buy_goods_invoice(db, user, product, supplier)
    second = buy_service(db, user, service, supplier)

    assert (first.kind, goods.kind) == ("service", "goods")
    assert second.number == first.number + 1


def test_a_product_cannot_be_bought_on_a_service_invoice(db, user, legal):
    _, supplier = legal
    product = make_item(db, name="لیوان")

    with pytest.raises(HTTPException) as err:
        buy_service(db, user, product, supplier)
    assert err.value.status_code == 400


def test_deductions_warehouses_and_account_overrides_belong_to_the_right_kind(db, legal):
    service, supplier = legal
    type_id = deduction_type(db, "تکلیفی", "withholding_tax", "3")
    line = PurchaseInvoiceLineIn(item_id=service.id, qty=Decimal(1), unit_cost=Decimal(1000))

    with pytest.raises(ValidationError):
        PurchaseInvoiceIn(
            invoice_date=TODAY, contact_id=supplier.id, lines=[line],
            deductions=[PurchaseDeductionIn(deduction_type_id=type_id)],
        )
    with pytest.raises(ValidationError):
        PurchaseInvoiceIn(kind="service", invoice_date=TODAY, warehouse_id=main_warehouse(db).id, lines=[line])
    with pytest.raises(ValidationError):
        PurchaseInvoiceIn(
            invoice_date=TODAY, contact_id=supplier.id,
            lines=[PurchaseInvoiceLineIn(
                item_id=service.id, qty=Decimal(1), unit_cost=Decimal(1000),
                expense_account_id=rent_account(db).id,
            )],
        )


def test_inactive_and_repeated_deduction_types_are_refused(db, user, legal):
    service, supplier = legal
    active = deduction_type(db, "تکلیفی", "withholding_tax", "3")
    with pytest.raises(HTTPException) as repeated:
        buy_service(db, user, service, supplier, deductions=[active, active])
    assert repeated.value.status_code == 400

    closed = deduction_type(db, "بیمه قدیمی", "insurance", "5")
    deductions_svc.update_type(
        db, closed, PurchaseDeductionTypeIn(name="بیمه قدیمی", nature="insurance", rate=Decimal(5), is_active=False)
    )
    with pytest.raises(HTTPException) as inactive:
        buy_service(db, user, service, supplier, deductions=[closed])
    assert inactive.value.status_code == 400


def test_deductions_can_never_make_the_supplier_owe_us(db, user, legal):
    service, supplier = legal
    first = deduction_type(db, "تکلیفی", "withholding_tax", "60")
    second = deduction_type(db, "بیمه", "insurance", "60")

    with pytest.raises(HTTPException) as err:
        buy_service(db, user, service, supplier, deductions=[first, second])
    assert err.value.status_code == 400


# ─────────────────── §۱۳ §۴۹ — حسابِ هزینه‌ی تاریخی ───────────────────


def test_a_line_can_choose_its_own_expense_account(db, user, legal):
    service, supplier = legal
    rent = rent_account(db)
    ledger = Ledger(db, rent=rent.id)

    invoice = buy_service(db, user, service, supplier, expense_account_id=rent.id)

    assert invoice.lines[0].expense_account_id == rent.id
    assert ledger.delta("rent") == Decimal(100_000_000)


def test_a_return_credits_the_account_the_invoice_actually_debited(db, user, legal):
    """باگِ پیش از این فصل: برگشت حساب را از نگاشتِ **امروزِ** خدمت می‌گرفت."""
    service, supplier = legal
    invoice = buy_service(db, user, service, supplier, qty=4, unit_cost=2_500_000)
    original = invoice.lines[0].expense_account_id
    assert original == get_account(db, cc.SERVICE_EXPENSE).id

    rent = rent_account(db)
    service.expense_account_id = rent.id
    db.flush()
    ledger = Ledger(db, original=original, rent=rent.id)

    return_service(db, user, invoice, service, 4)

    assert ledger.delta("original") == Decimal(-10_000_000)
    assert ledger.delta("rent") == Decimal(0)


def test_the_same_holds_for_a_service_line_on_a_goods_invoice(db, user, legal):
    service, supplier = legal
    invoice = buy_goods_invoice(db, user, service, supplier, warehouse=True, unit_cost=3_000_000)
    original = invoice.lines[0].expense_account_id
    assert original is not None

    rent = rent_account(db)
    service.expense_account_id = rent.id
    db.flush()
    ledger = Ledger(db, original=original, rent=rent.id)

    return_service(db, user, invoice, service, 1)

    assert ledger.delta("original") == Decimal(-3_000_000)
    assert ledger.delta("rent") == Decimal(0)


def test_returning_an_invoice_with_deductions_is_refused(db, user, legal):
    """قاعده‌ی تسهیمِ کسورات در برگشت تعریف نشده؛ حدسش بدهیِ مالیاتی را بی‌صدا غلط می‌کرد."""
    service, supplier = legal
    withholding, _ = video_types(db)
    invoice = buy_service(db, user, service, supplier, deductions=[withholding])

    with pytest.raises(HTTPException) as err:
        return_service(db, user, invoice, service, 1)
    assert err.value.status_code == 409


# ─────────────────── §۳۹–§۴۱ §۵۰ — مانده، پرداخت، ابطال ───────────────────


def test_the_supplier_open_item_is_the_net_payable(db, user, legal):
    service, supplier = legal
    withholding, insurance = video_types(db)
    invoice = buy_service(db, user, service, supplier, deductions=[withholding, insurance])

    items = open_items(db, account_id=get_account(db, cc.ACCOUNTS_PAYABLE).id, contact_id=supplier.id)
    row = next(item for item in items if item["source_id"] == invoice.id)

    assert row["document_amount"] == Decimal(80_333_000)
    assert row["side"] == "credit"


def test_voiding_reverses_every_liability(db, user, legal):
    service, supplier = legal
    withholding, insurance = video_types(db)
    buy_service(db, user, service, supplier, deductions=[withholding, insurance])  # حساب‌های نقش‌دار ساخته شوند
    ledger = Ledger(
        db,
        expense=get_account(db, cc.SERVICE_EXPENSE).id,
        withholding=get_account(db, cc.WITHHOLDING_TAX_PAYABLE).id,
        insurance=get_account(db, cc.CONTRACT_INSURANCE_PAYABLE).id,
        payable=get_account(db, cc.ACCOUNTS_PAYABLE).id,
    )

    invoice = buy_service(db, user, service, supplier, deductions=[withholding, insurance])
    void_purchase_invoice(db, invoice.id, reason="ثبتِ اشتباه", user=user)

    for key in ("expense", "withholding", "insurance", "payable"):
        assert ledger.delta(key) == Decimal(0), key


def test_no_warehouse_receipt_for_services(db, user, legal):
    service, supplier = legal
    receipt_line = lambda invoice: WarehouseReceiptIn(  # noqa: E731
        receipt_date=TODAY,
        warehouse_id=main_warehouse(db).id,
        lines=[WarehouseReceiptLineIn(purchase_invoice_line_id=invoice.lines[0].id, qty=Decimal(1))],
    )

    service_invoice = buy_service(db, user, service, supplier)
    with pytest.raises(HTTPException) as on_service_invoice:
        create_warehouse_receipt(db, service_invoice.id, receipt_line(service_invoice), user)
    assert on_service_invoice.value.status_code == 400

    goods_invoice = buy_goods_invoice(db, user, service, supplier)
    with pytest.raises(HTTPException) as on_goods_invoice:
        create_warehouse_receipt(db, goods_invoice.id, receipt_line(goods_invoice), user)
    assert on_goods_invoice.value.status_code == 400


def test_a_duplicate_keeps_the_kind_and_the_deduction_types(db, user, legal):
    service, supplier = legal
    withholding, insurance = video_types(db)
    invoice = buy_service(db, user, service, supplier, deductions=[withholding, insurance])

    draft = duplicate_purchase_invoice_draft(db, invoice.id)

    assert draft["kind"] == "service"
    assert [row["deduction_type_id"] for row in draft["deductions"]] == [withholding, insurance]
    assert draft["lines"][0]["expense_account_id"] == invoice.lines[0].expense_account_id


# ─────────────────── اندپوینت‌ها: فهرست، idempotency، چاپ ───────────────────


def test_the_api_reports_the_real_payable_and_filters_by_kind(client, db, legal):
    service, supplier = legal
    withholding, insurance = video_types(db)
    body = {
        "kind": "service",
        "invoice_date": TODAY.isoformat(),
        "contact_id": str(supplier.id),
        "supplier_invoice_number": "SUP-77",
        "lines": [{"item_id": str(service.id), "qty": 2, "unit_cost": 50_000_000}],
        "deductions": [{"deduction_type_id": str(withholding)}, {"deduction_type_id": str(insurance)}],
    }
    headers = {"Idempotency-Key": f"spi-{uuid.uuid4()}"}

    first = client.post("/api/purchase-invoices", json=body, headers=headers)
    second = client.post("/api/purchase-invoices", json=body, headers=headers)

    assert first.status_code == 201, first.text
    assert second.json()["id"] == first.json()["id"]
    created = first.json()
    assert Decimal(created["final_amount"]) == Decimal(100_000_000)
    assert Decimal(created["payable_amount"]) == Decimal(80_333_000)
    assert Decimal(created["remaining_amount"]) == Decimal(80_333_000)
    assert Decimal(created["withholding_total"]) == Decimal(3_000_000)
    assert Decimal(created["insurance_total"]) == Decimal(16_667_000)
    assert created["inventory_status"] == "not_applicable"
    assert created["journal_entry_number"] is not None
    assert created["lines"][0]["expense_account_name"]
    assert created["deductions"][0]["account_name"]

    services = client.get("/api/purchase-invoices", params={"kind": "service", "limit": 200}).json()["items"]
    goods = client.get("/api/purchase-invoices", params={"kind": "goods", "limit": 200}).json()["items"]
    assert created["id"] in {row["id"] for row in services}
    assert created["id"] not in {row["id"] for row in goods}
    assert client.get("/api/purchase-invoices", params={"kind": "other"}).status_code == 400


def test_the_print_shows_the_deductions_and_the_net(client, db, user, legal):
    service, supplier = legal
    withholding, insurance = video_types(db)
    invoice = buy_service(db, user, service, supplier, deductions=[withholding, insurance])

    html = client.get(f"/api/purchase-invoices/{invoice.id}/print").text

    assert "فاکتور خرید خدمات" in html
    assert "مالیات تکلیفی قرارداد" in html and "حق بیمه قرارداد" in html
    assert "خالص فاکتور" in html
    assert fa_number(80_333_000) in html
    pdf = client.get(f"/api/purchase-invoices/{invoice.id}/pdf")
    assert pdf.status_code == 200, pdf.text


def test_deduction_types_are_master_data_with_guarded_history(client, db, user, legal):
    service, supplier = legal
    created = client.post(
        "/api/purchase-deduction-types", json={"name": "تکلیفی ۳", "nature": "withholding_tax", "rate": 3}
    )
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["account_is_default"] is True and row["in_use"] is False

    duplicate = client.post("/api/purchase-deduction-types", json={"name": "تکلیفی ۳", "nature": "insurance"})
    assert duplicate.status_code == 409
    on_cash = client.post(
        "/api/purchase-deduction-types",
        json={"name": "روی صندوق", "nature": "insurance", "account_id": str(get_account(db, cc.CASH).id)},
    )
    assert on_cash.status_code == 400

    unused = client.post("/api/purchase-deduction-types", json={"name": "موقت", "nature": "insurance"}).json()
    assert client.delete(f"/api/purchase-deduction-types/{unused['id']}").status_code == 204

    buy_service(db, user, service, supplier, deductions=[uuid.UUID(row["id"])])
    assert client.delete(f"/api/purchase-deduction-types/{row['id']}").status_code == 409
    renatured = client.patch(
        f"/api/purchase-deduction-types/{row['id']}", json={"name": "تکلیفی ۳", "nature": "insurance", "rate": 3}
    )
    assert renatured.status_code == 409
    listed = {r["id"]: r for r in client.get("/api/purchase-deduction-types").json()}
    assert listed[row["id"]]["in_use"] is True
