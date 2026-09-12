"""چاپِ رسید و برگشتِ رسید، و میان‌برِ اعلامیه پرداخت (§۳۸–§۴۲).

دو ادعای اصلی:

* **چاپ Projection است، نه مدلِ مالیِ دوم (§۴۲).** عددی که روی کاغذ می‌آید همان
  است که سند و فرم دارند — تست با اعدادِ §۲۵ فصل: ۱٬۴۰۰٬۰۰۰ کالا + ۵۰٬۰۰۰ حمل +
  ۴۵٬۰۰۰ مالیات = ۱٬۴۹۵٬۰۰۰.
* **میان‌برِ پرداخت فقط زمینه منتقل می‌کند (§۳۹ §۴۰).** و مبلغِ پیشنهادی عمداً
  «خالصِ رسید» نیست: حمل بدهیِ حمل‌کننده است، نه تأمین‌کننده.
"""
import uuid
from datetime import date
from decimal import Decimal

from app.schemas.invoices import WarehouseReceiptIn, WarehouseReceiptLineIn
from app.schemas.returns import PurchaseReturnIn, PurchaseReturnLineIn
from app.services.printing import fa_number
from app.services.returns import post_purchase_return
from app.services.warehouse_receipts import create_warehouse_receipt, void_warehouse_receipt
from tests.factories import main_warehouse, make_contact, make_item

TODAY = date(2026, 3, 15)


def chapter_receipt(db, user, **header):
    """نمونه‌ی §۲۵: کالای مشمولِ ۹٪ و کالای معاف، با حملِ ۵۰٬۰۰۰."""
    taxed = make_item(db, name="کالای اول", tax_rate=Decimal(9))
    exempt = make_item(db, name="کالای دوم", purchase_vat_status="exempt")
    return create_warehouse_receipt(
        db,
        None,
        WarehouseReceiptIn(
            receipt_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            freight_amount=Decimal(50_000),
            lines=[
                WarehouseReceiptLineIn(item_id=taxed.id, qty=Decimal(100), unit_cost=Decimal(5_000)),
                WarehouseReceiptLineIn(item_id=exempt.id, qty=Decimal(150), unit_cost=Decimal(6_000)),
            ],
            **header,
        ),
        user,
    )


# ─────────────────── چاپِ رسید ───────────────────


def test_the_printed_receipt_carries_the_chapters_net(db, user, client):
    supplier = make_contact(db, name="تأمین‌کننده چاپ", type_="supplier")
    receipt = chapter_receipt(db, user, contact_id=supplier.id)
    assert receipt.net_amount == Decimal(1_495_000)

    res = client.get(f"/api/warehouse-receipts/{receipt.id}/print")

    assert res.status_code == 200, res.text
    body = res.text
    assert "رسید انبار" in body
    assert "تأمین‌کننده چاپ" in body
    #: هر پنج جزء همان عددِ مدل‌اند — چاپ هیچ‌چیز را خودش حساب نمی‌کند.
    for value in (1_400_000, 50_000, 45_000, 1_495_000):
        assert fa_number(Decimal(value)) in body, value


def test_the_printed_receipt_shows_freight_per_line(db, user, client):
    """§۲۲ — سهمِ حملِ هر ردیف روی کاغذ هم دیده می‌شود (۲۵٬۰۰۰ و ۲۵٬۰۰۰)."""
    receipt = chapter_receipt(db, user)

    body = client.get(f"/api/warehouse-receipts/{receipt.id}/print").text

    assert "حمل" in body
    assert body.count(fa_number(Decimal(25_000))) >= 2


def test_a_voided_receipt_is_marked_on_the_printout(db, user, client):
    receipt = chapter_receipt(db, user)
    void_warehouse_receipt(db, receipt.id, reason="آزمونِ ابطال", user=user)
    db.flush()

    body = client.get(f"/api/warehouse-receipts/{receipt.id}/print").text

    assert "این سند باطل شده است" in body
    assert "آزمونِ ابطال" in body


def test_printing_a_missing_receipt_is_a_404(client):
    assert client.get(f"/api/warehouse-receipts/{uuid.uuid4()}/print").status_code == 404


# ─────────────────── چاپِ برگشتِ رسید ───────────────────


def test_a_receipt_return_prints_as_a_warehouse_document(db, user, client):
    """برگشتی که به رسید لنگر زده برگه‌ی انبار می‌گیرد — با تحویل‌گیرنده و خالص توافقی.

    پیش از این، مسیرِ چاپ فاکتورِ مبدأ را فرض می‌کرد؛ برگشتِ رسیدِ مستقیم فاکتوری
    ندارد.
    """
    supplier = make_contact(db, name="تحویل‌گیرنده چاپ", type_="supplier")
    receipt = chapter_receipt(db, user, contact_id=supplier.id)
    ret = post_purchase_return(
        db,
        PurchaseReturnIn(
            return_date=TODAY,
            warehouse_receipt_id=receipt.id,
            receiver_id=supplier.id,
            lines=[PurchaseReturnLineIn(warehouse_receipt_line_id=receipt.lines[0].id, qty=Decimal(20))],
        ),
        user,
    )

    res = client.get(f"/api/purchase-returns/{ret.id}/print")

    assert res.status_code == 200, res.text
    body = res.text
    assert "برگشت رسید انبار" in body
    assert "تحویل‌گیرنده" in body
    assert "تحویل‌گیرنده چاپ" in body
    assert "خالص توافقی" in body


# ─────────────────── زمینه‌ی اعلامیه پرداخت ───────────────────


def test_the_payment_context_carries_the_receipt_not_a_payment(db, user, client):
    """§۳۸ — نوع، طرف مقابل، شرح و «جمع مبلغ رسید انبار». هیچ پرداختی ساخته نمی‌شود."""
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    receipt = chapter_receipt(db, user, contact_id=supplier.id)

    res = client.get(f"/api/warehouse-receipts/{receipt.id}/payment-context")

    assert res.status_code == 200, res.text
    ctx = res.json()
    assert ctx["payment_type"] == "supplier"
    assert ctx["contact_id"] == str(supplier.id)
    assert ctx["document_type"] == "warehouse_receipt"
    assert ctx["description"] == f"بابت رسید انبار شماره {receipt.number}"
    assert Decimal(ctx["receipt_net_amount"]) == Decimal(1_495_000)


def test_the_suggested_amount_leaves_out_freight_owed_to_someone_else(db, user, client):
    """خالصِ رسید ۱٬۴۹۵٬۰۰۰ است، ولی تأمین‌کننده فقط کالا و مالیاتش را طلب دارد.

    حملِ بی‌حمل‌کننده نقد پرداخت شده؛ پیشنهادِ خالص یعنی کرایه دو بار پرداخت شود.
    """
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    receipt = chapter_receipt(db, user, contact_id=supplier.id)

    ctx = client.get(f"/api/warehouse-receipts/{receipt.id}/payment-context").json()

    assert Decimal(ctx["goods_due"]) == Decimal(1_445_000)
    assert Decimal(ctx["freight_due"]) == Decimal(0)
    assert Decimal(ctx["suggested_amount"]) == Decimal(1_445_000)


def test_freight_is_suggested_only_when_the_supplier_carried_it(db, user, client):
    supplier = make_contact(db, name="تأمین‌کننده و باربر", type_="supplier")
    receipt = chapter_receipt(db, user, contact_id=supplier.id, carrier_id=supplier.id)

    ctx = client.get(f"/api/warehouse-receipts/{receipt.id}/payment-context").json()

    assert Decimal(ctx["freight_due"]) == Decimal(50_000)
    assert Decimal(ctx["suggested_amount"]) == Decimal(1_495_000)


def test_a_cash_receipt_has_nothing_to_pay(db, user, client):
    """رسیدِ بی‌تحویل‌دهنده نقدی ثبت شده؛ اعلامیه پرداخت برایش بدهیِ ساختگی می‌سازد."""
    receipt = chapter_receipt(db, user)

    res = client.get(f"/api/warehouse-receipts/{receipt.id}/payment-context")

    assert res.status_code == 409


def test_a_voided_receipt_has_no_payment_context(db, user, client):
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    receipt = chapter_receipt(db, user, contact_id=supplier.id)
    void_warehouse_receipt(db, receipt.id, reason="اشتباه", user=user)
    db.flush()

    assert client.get(f"/api/warehouse-receipts/{receipt.id}/payment-context").status_code == 409


# ─────────────────── اعلامیه پرداخت با مرجعِ رسید ───────────────────


def _pay(client, contact, receipt, amount):
    return client.post(
        "/api/payments",
        json={
            "payment_type": "supplier",
            "contact_id": str(contact.id),
            "payment_date": TODAY.isoformat(),
            "description": "بابت رسید انبار",
            "description2": "تست",
            "cash": [{"amount": amount}],
            "related_documents": [
                {"document_type": "warehouse_receipt", "document_id": str(receipt.id)}
            ],
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )


def test_a_payment_can_reference_the_receipt_for_part_of_its_total(db, user, client):
    """§۳۹ §۴۰ — پرداخت سندِ مستقلِ خزانه است و مجبور به برابری با جمعِ رسید نیست."""
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    receipt = chapter_receipt(db, user, contact_id=supplier.id)

    res = _pay(client, supplier, receipt, 500_000)

    assert res.status_code == 201, res.text
    assert res.json()["related_documents"][0]["document_type"] == "warehouse_receipt"


def test_a_payment_to_someone_else_cannot_cite_the_receipt(db, user, client):
    """مرجعی که به تحویل‌دهنده‌ی دیگری اشاره کند، ردیابی را دروغ می‌کند."""
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    stranger = make_contact(db, name="دیگری", type_="supplier")
    receipt = chapter_receipt(db, user, contact_id=supplier.id)

    res = _pay(client, stranger, receipt, 100_000)

    assert res.status_code == 400
