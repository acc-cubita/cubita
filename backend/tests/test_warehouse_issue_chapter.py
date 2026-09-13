"""فصلِ «خروج انبار» — خروجِ مستقل، انتقال از موتورِ خودش، و خروج ← فاکتور فروش.

ادعاهای اصلی، هرکدام با عددِ خودش:

* **خروج موجودی را واقعاً کم می‌کند (§۱ §۱۲):** ۱۴۰ − ۱۰ = ۱۳۰، از دفترِ انبار.
* **مصرف درآمد نمی‌سازد (§۲۴ §۲۵):** طرفِ بدهکار حسابِ انتخابیِ کاربر است و هیچ
  ردیفی روی فروش یا طلبِ مشتری نمی‌نشیند.
* **فاکتوری که از خروج ساخته شود موجودی را دوباره کم نمی‌کند (§۱۵ §۳۹).**
* **ابطالِ آن فاکتور کالا را به قفسه برنمی‌گرداند** — خروج جدا می‌شود، باطل نه.
* **انتقال اتمی است و قفل دارد (§۲۸ §۲۹).**
"""
import itertools
import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account, JournalLine
from app.models.inventory import StockLedger, UnitOfMeasure
from app.models.invoices import SalesInvoice, WarehouseIssue
from app.schemas.invoices import (
    DirectWarehouseIssueIn,
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
    WarehouseIssueIn,
    WarehouseIssueLineIn,
)
from app.schemas.returns import SalesReturnIn, SalesReturnLineIn
from app.schemas.transfers import StockTransferIn, StockTransferLineIn
from app.services import chart_codes as cc
from app.services import warehouses as warehouses_svc
from app.services.common import get_account
from app.services.inventory import get_stock_qty, post_purchase_invoice, post_sales_invoice
from app.services.printing import fa_number
from app.services.returns import post_sales_return
from app.services.transfers import post_stock_transfer, void_stock_transfer
from app.services.warehouse_issues import (
    create_direct_warehouse_issue,
    create_warehouse_issue,
    void_warehouse_issue,
)
from tests.factories import main_warehouse, make_contact, make_item, other_warehouse

TODAY = date.today()
_SEQ = itertools.count(1)


def _buy(db, user, item, qty, cost, warehouse=None):
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=(warehouse or main_warehouse(db)).id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(cost))],
        ),
        user,
    )


def _expense(db, name="هزینه‌ی مصرفِ داخلی") -> Account:
    row = Account(
        code=f"E{next(_SEQ):04d}",
        name=name,
        type="expense",
        is_group=False,
        parent_id=get_account(db, cc.INVENTORY_ADJUSTMENT).parent_id,
    )
    db.add(row)
    db.flush()
    return row


def _entry_lines(db, entry_id):
    return db.query(JournalLine).filter(JournalLine.entry_id == entry_id).all()


def _direct(db, user, item, qty, *, issue_type="sale", receiver=None, account=None, warehouse=None, **line):
    return create_direct_warehouse_issue(
        db,
        DirectWarehouseIssueIn(
            issue_date=TODAY,
            issue_type=issue_type,
            warehouse_id=(warehouse or main_warehouse(db)).id,
            receiver_id=(receiver or make_contact(db, name="تحویل‌گیرنده‌ی آزمون")).id if issue_type == "sale" else None,
            account_id=account.id if account is not None else None,
            lines=[WarehouseIssueLineIn(item_id=item.id, qty=Decimal(qty), **line)],
        ),
        user,
    )


# ─────────────────────────── خروجِ مستقل ───────────────────────────


def test_a_direct_sale_issue_takes_stock_from_140_to_130(db, user):
    """§۱ §۱۲ — نمونه‌ی خودِ فصل، از دفترِ انبار نه از ستونِ قابلِ ویرایش."""
    item = make_item(db, name="کالای فصل")
    _buy(db, user, item, 140, 1_000)

    issue = _direct(db, user, item, 10)

    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(130)
    assert issue.origin == "direct" and issue.sales_invoice_id is None
    move = db.query(StockLedger).filter(StockLedger.source_id == issue.id).one()
    assert move.source_type == "warehouse_issue" and Decimal(move.qty) == Decimal(-10)
    lines = _entry_lines(db, issue.journal_entry_id)
    cogs = get_account(db, cc.COGS).id
    assert {(l.account_id, Decimal(l.debit), Decimal(l.credit)) for l in lines} == {
        (cogs, Decimal(10_000), Decimal(0)),
        (warehouses_svc.inventory_account_id(db, main_warehouse(db).id), Decimal(0), Decimal(10_000)),
    }


def test_a_sale_issue_needs_a_receiver(db):
    """§۳ — «تحویل‌گیرنده *» در خروجِ فروش اجباری است."""
    with pytest.raises(ValueError):
        DirectWarehouseIssueIn(
            issue_date=TODAY, issue_type="sale", warehouse_id=uuid.uuid4(),
            lines=[WarehouseIssueLineIn(item_id=uuid.uuid4(), qty=Decimal(1))],
        )


def test_transfer_is_not_a_direct_issue_type(db):
    with pytest.raises(ValueError, match="انتقال"):
        DirectWarehouseIssueIn(
            issue_date=TODAY, issue_type="transfer", warehouse_id=uuid.uuid4(),
            lines=[WarehouseIssueLineIn(item_id=uuid.uuid4(), qty=Decimal(1))],
        )


def test_consumption_debits_the_chosen_account_and_never_revenue(db, user):
    """§۲۴ §۲۵ — مصرف فاکتور، درآمد یا طلبِ مشتری نمی‌سازد."""
    item = make_item(db, name="کاغذِ اداری")
    _buy(db, user, item, 20, 500)
    expense = _expense(db)
    invoices_before = db.query(SalesInvoice).count()

    issue = _direct(db, user, item, 10, issue_type="consumption", account=expense)

    lines = _entry_lines(db, issue.journal_entry_id)
    debits = {l.account_id: Decimal(l.debit) for l in lines if l.debit}
    assert debits == {expense.id: Decimal(5_000)}
    forbidden = {get_account(db, cc.SALES_REVENUE).id, get_account(db, cc.ACCOUNTS_RECEIVABLE).id}
    assert not forbidden & {l.account_id for l in lines}
    assert db.query(SalesInvoice).count() == invoices_before
    assert issue.lines[0].account_id == expense.id


@pytest.mark.parametrize("role", [cc.ACCOUNTS_RECEIVABLE, cc.INVENTORY, cc.CASH, cc.SALES_REVENUE])
def test_consumption_refuses_an_account_another_engine_owns(db, user, role):
    """نشستنِ خروج روی طلب، موجودی، نقد یا درآمد سند را متوازن ولی مانده را خراب می‌کند."""
    item = make_item(db, name="قطعه")
    _buy(db, user, item, 5, 100)
    with pytest.raises(HTTPException) as err:
        _direct(db, user, item, 1, issue_type="other", account=get_account(db, role))
    assert err.value.status_code == 400
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(5)


def test_consumption_refuses_a_group_account(db, user):
    item = make_item(db, name="قطعه‌ی دیگر")
    _buy(db, user, item, 5, 100)
    group = db.get(Account, _expense(db).parent_id)
    assert group.is_group
    with pytest.raises(HTTPException) as err:
        _direct(db, user, item, 1, issue_type="consumption", account=group)
    assert "گروه" in err.value.detail


def test_consumption_without_an_account_is_refused_before_touching_stock(db):
    with pytest.raises(ValueError, match="معین"):
        DirectWarehouseIssueIn(
            issue_date=TODAY, issue_type="consumption", warehouse_id=uuid.uuid4(),
            lines=[WarehouseIssueLineIn(item_id=uuid.uuid4(), qty=Decimal(1))],
        )


def test_an_issue_cannot_take_more_than_the_warehouse_has(db, user):
    """§۱۴ — ۸ موجود، ۱۰ درخواستی: نه موجودیِ منفی، نه کسرِ ناقص."""
    item = make_item(db, name="کمیاب")
    _buy(db, user, item, 8, 1_000)
    with pytest.raises(HTTPException) as err:
        _direct(db, user, item, 10)
    assert err.value.status_code == 400 and "کافی نیست" in err.value.detail
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(8)


def test_two_lines_of_one_item_are_checked_together(db, user):
    item = make_item(db, name="تکراری")
    _buy(db, user, item, 10, 1_000)
    receiver = make_contact(db)
    with pytest.raises(HTTPException) as err:
        create_direct_warehouse_issue(
            db,
            DirectWarehouseIssueIn(
                issue_date=TODAY, issue_type="sale", warehouse_id=main_warehouse(db).id,
                receiver_id=receiver.id,
                lines=[
                    WarehouseIssueLineIn(item_id=item.id, qty=Decimal(6)),
                    WarehouseIssueLineIn(item_id=item.id, qty=Decimal(6)),
                ],
            ),
            user,
        )
    assert err.value.status_code == 400


def test_a_carton_issue_lands_as_pieces_and_shows_cartons(db, user):
    """§۱۱ — همان تبدیلِ مرکزی؛ دفترِ انبار عدد می‌بیند، برگه کارتن هم نشان می‌دهد."""
    piece = db.query(UnitOfMeasure).filter(UnitOfMeasure.name == "عدد").one()
    carton = db.query(UnitOfMeasure).filter(UnitOfMeasure.name == "کارتن").one()
    item = make_item(
        db, name="نوشابه", primary_unit_id=piece.id, secondary_unit_id=carton.id,
        conversion_mode="fixed", conversion_factor=Decimal(24),
    )
    _buy(db, user, item, 100, 1_000)

    issue = _direct(db, user, item, 2, unit_id=carton.id)

    line = issue.lines[0]
    assert Decimal(line.qty) == Decimal(48)
    assert Decimal(line.secondary_qty) == Decimal(2) and line.secondary_unit_snapshot == "کارتن"
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(52)


def test_a_service_has_no_warehouse_issue(db, user):
    service = make_item(db, name="نصب", is_service=True)
    with pytest.raises(HTTPException) as err:
        _direct(db, user, service, 1)
    assert "خدمت" in err.value.detail


def test_the_direct_issue_endpoint_is_idempotent(db, user, client):
    """§۴۶ — پاسخِ گم‌شده و تکرار نباید دو خروج و دو کسرِ موجودی بسازد."""
    item = make_item(db, name="تکرارِ شبکه")
    _buy(db, user, item, 30, 1_000)
    body = {
        "issue_date": TODAY.isoformat(), "issue_type": "sale", "warehouse_id": str(main_warehouse(db).id),
        "receiver_id": str(make_contact(db).id), "lines": [{"item_id": str(item.id), "qty": 5}],
    }
    headers = {"Idempotency-Key": f"issue-{uuid.uuid4()}"}

    first = client.post("/api/warehouse-issues", json=body, headers=headers)
    second = client.post("/api/warehouse-issues", json=body, headers=headers)

    assert first.status_code == 201, first.text
    assert second.json()["id"] == first.json()["id"]
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(25)


def test_issue_detail_names_the_debit_account(db, user, client):
    """ستونِ «کد حساب معین» (§۹) — حسابی که واقعاً سند خورده."""
    item = make_item(db, name="مصرفی")
    _buy(db, user, item, 5, 200)
    expense = _expense(db, name="هزینه‌ی کارگاه")
    issue = _direct(db, user, item, 2, issue_type="consumption", account=expense)

    body = client.get(f"/api/warehouse-issues/{issue.id}").json()

    assert body["issue_type"] == "consumption"
    assert body["lines"][0]["account_code"] == expense.code
    assert body["lines"][0]["account_name"] == "هزینه‌ی کارگاه"


# ─────────────────────────── فهرست ───────────────────────────


def test_the_ledger_lists_issues_and_transfers_with_type_aware_columns(db, user, client):
    """§۳۶ §۳۷ — یک فهرست، نه چهار؛ فروش تحویل‌گیرنده دارد، انتقال انبارِ مقصد."""
    item = make_item(db, name="فهرستی")
    _buy(db, user, item, 50, 1_000)
    receiver = make_contact(db, name="مشتریِ فهرست")
    _direct(db, user, item, 3, receiver=receiver)
    _direct(db, user, item, 2, issue_type="consumption", account=_expense(db))
    post_stock_transfer(
        db,
        StockTransferIn(
            transfer_date=TODAY, from_warehouse_id=main_warehouse(db).id, to_warehouse_id=other_warehouse(db).id,
            lines=[StockTransferLineIn(item_id=item.id, qty=Decimal(4))],
        ),
        user,
    )

    rows = client.get("/api/warehouse-issues").json()["items"]
    assert {r["issue_type"] for r in rows} >= {"sale", "consumption", "transfer"}
    sale = next(r for r in rows if r["issue_type"] == "sale")
    assert sale["receiver_name"] == "مشتریِ فهرست" and sale["kind"] == "issue"

    transfers = client.get("/api/warehouse-issues", params={"issue_type": "transfer"}).json()["items"]
    assert [r["kind"] for r in transfers] == ["transfer"]
    assert transfers[0]["destination_warehouse_name"] == other_warehouse(db).name
    assert transfers[0]["total_cost"] == "4000" or Decimal(transfers[0]["total_cost"]) == Decimal(4_000)

    consumption = client.get("/api/warehouse-issues", params={"issue_type": "consumption"}).json()["items"]
    assert [r["issue_type"] for r in consumption] == ["consumption"]


def test_the_ledger_pages_through_every_row_exactly_once(db, user, client):
    item = make_item(db, name="صفحه‌بندی")
    _buy(db, user, item, 100, 1_000)
    created = {str(_direct(db, user, item, 1).id) for _ in range(3)}
    for _ in range(2):
        created.add(str(post_stock_transfer(
            db,
            StockTransferIn(
                transfer_date=TODAY, from_warehouse_id=main_warehouse(db).id,
                to_warehouse_id=other_warehouse(db).id,
                lines=[StockTransferLineIn(item_id=item.id, qty=Decimal(1))],
            ),
            user,
        ).id))

    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = client.get("/api/warehouse-issues", params=params).json()
        seen += [r["id"] for r in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert created <= set(seen)
    assert len(seen) == len(set(seen))


def test_an_unknown_ledger_type_is_a_400(client):
    assert client.get("/api/warehouse-issues", params={"issue_type": "gift"}).status_code == 400


# ─────────────────────────── خروج ← فاکتور فروش ───────────────────────────


def _invoice_body(context, *, receiver_id, qty=None, price=1_000, **extra):
    return {
        "invoice_date": TODAY.isoformat(),
        "contact_id": str(receiver_id),
        "tax_rate": 0,
        "source_warehouse_issue_id": context["issue_id"],
        "lines": [
            {
                "item_id": line["item_id"],
                "qty": float(qty if qty is not None else Decimal(line["qty"])),
                "unit_price": price,
                "source_issue_line_id": line["issue_line_id"],
            }
            for line in context["lines"]
        ],
        **extra,
    }


def _issued_sale(db, user, client, qty=10):
    item = make_item(db, name="فروشِ پیش از فاکتور", sales_price=1_000)
    _buy(db, user, item, 50, 400)
    receiver = make_contact(db, name="مشتریِ تحویل‌گرفته")
    issue = _direct(db, user, item, qty, receiver=receiver)
    context = client.get(f"/api/warehouse-issues/{issue.id}/invoice-context").json()
    return item, receiver, issue, context


def test_an_invoice_made_from_an_issue_moves_no_stock(db, user, client):
    """§۱۵ §۱۶ — کالا از قبل رفته؛ فاکتور فقط سندِ تجاری است."""
    item, receiver, issue, context = _issued_sale(db, user, client)
    assert context["receiver_id"] == str(receiver.id)
    assert Decimal(context["lines"][0]["suggested_unit_price"]) == Decimal(1_000)
    moves_before = db.query(StockLedger).filter(StockLedger.item_id == item.id).count()

    r = client.post(
        "/api/sales-invoices", json=_invoice_body(context, receiver_id=receiver.id),
        headers={"Idempotency-Key": f"inv-{uuid.uuid4()}"},
    )

    assert r.status_code == 201, r.text
    invoice = r.json()
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(40)
    assert db.query(StockLedger).filter(StockLedger.item_id == item.id).count() == moves_before
    db.expire_all()
    assert str(db.get(WarehouseIssue, issue.id).sales_invoice_id) == invoice["id"]
    assert invoice["fulfillment_status"] == "fully_issued"
    #: §۳۹ — مسیرِ برعکس: از فاکتور به همان خروج.
    back = client.get(f"/api/sales-invoices/{invoice['id']}/warehouse-issues").json()
    assert [row["id"] for row in back] == [str(issue.id)]
    #: COGS را خروج زده؛ سندِ فاکتور هرگز دوباره نمی‌زند.
    entry = db.get(SalesInvoice, uuid.UUID(invoice["id"])).journal_entry_id
    assert entry is not None
    assert get_account(db, cc.COGS).id not in {l.account_id for l in _entry_lines(db, entry)}


def test_the_same_issue_cannot_be_invoiced_twice(db, user, client):
    """§۳۹ — دو کلیک با دو کلید هم فقط یک فاکتور."""
    item, receiver, issue, context = _issued_sale(db, user, client)
    body = _invoice_body(context, receiver_id=receiver.id)
    assert client.post("/api/sales-invoices", json=body, headers={"Idempotency-Key": f"a-{uuid.uuid4()}"}).status_code == 201

    again = client.post("/api/sales-invoices", json=body, headers={"Idempotency-Key": f"b-{uuid.uuid4()}"})

    assert again.status_code == 409
    assert "قبلاً" in again.json()["detail"]
    assert client.get(f"/api/warehouse-issues/{issue.id}/invoice-context").status_code == 409


def test_an_invoice_from_an_issue_keeps_the_issued_quantity(db, user, client):
    item, receiver, issue, context = _issued_sale(db, user, client)
    r = client.post("/api/sales-invoices", json=_invoice_body(context, receiver_id=receiver.id, qty=9))
    assert r.status_code == 400
    db.expire_all()
    assert db.get(WarehouseIssue, issue.id).sales_invoice_id is None


def test_an_invoice_from_an_issue_cannot_add_other_goods(db, user, client):
    item, receiver, issue, context = _issued_sale(db, user, client)
    stranger = make_item(db, name="کالای بیرونی")
    body = _invoice_body(context, receiver_id=receiver.id)
    body["lines"].append({"item_id": str(stranger.id), "qty": 1, "unit_price": 100})
    r = client.post("/api/sales-invoices", json=body)
    assert r.status_code == 400 and "در این خروج نیست" in r.json()["detail"]


def test_a_consumption_issue_never_becomes_a_sales_invoice(db, user, client):
    """§۲۵ — مصرف درآمد نمی‌سازد، حتی اگر کسی بخواهد."""
    item = make_item(db, name="مصرفِ کارگاه")
    _buy(db, user, item, 5, 100)
    issue = _direct(db, user, item, 1, issue_type="consumption", account=_expense(db))
    assert client.get(f"/api/warehouse-issues/{issue.id}/invoice-context").status_code == 400


@pytest.mark.parametrize("mode", ["immediate", "staged"])
def test_voiding_an_invoice_made_from_a_direct_issue_keeps_the_goods_out(db, user, client, mode):
    """کالا واقعاً رفته؛ ابطالِ سندِ تجاری آن را به قفسه برنمی‌گرداند — در هر دو سیاست."""
    assert client.patch("/api/sales-invoice-posting", json={"mode": mode}).status_code == 200
    item, receiver, issue, context = _issued_sale(db, user, client)
    invoice = client.post("/api/sales-invoices", json=_invoice_body(context, receiver_id=receiver.id)).json()

    r = client.post(f"/api/sales-invoices/{invoice['id']}/void", json={"reason": "مبلغ اشتباه بود"})

    assert r.status_code == 200, r.text
    db.expire_all()
    kept = db.get(WarehouseIssue, issue.id)
    assert kept.voided_at is None and kept.sales_invoice_id is None
    assert all(line.sales_invoice_line_id is None for line in kept.lines)
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(40)
    fresh = client.get(f"/api/warehouse-issues/{issue.id}/invoice-context").json()
    assert client.post("/api/sales-invoices", json=_invoice_body(fresh, receiver_id=receiver.id)).status_code == 201


def test_voiding_an_issue_whose_invoice_has_a_return_is_refused(db, user):
    """وگرنه کالای برگشتی دو بار به انبار برمی‌گردد."""
    item = make_item(db, name="برگشتی")
    _buy(db, user, item, 10, 1_000)
    invoice = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY, warehouse_id=main_warehouse(db).id, contact_id=make_contact(db).id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(5), unit_price=Decimal(3_000))],
        ),
        user,
    )
    post_sales_return(
        db,
        SalesReturnIn(
            return_date=TODAY, sales_invoice_id=invoice.id,
            lines=[SalesReturnLineIn(sales_invoice_line_id=invoice.lines[0].id, qty=Decimal(1))],
        ),
        user,
    )
    issue = db.query(WarehouseIssue).filter(WarehouseIssue.sales_invoice_id == invoice.id).one()

    with pytest.raises(HTTPException) as err:
        void_warehouse_issue(db, issue.id, reason="آزمون", user=user)
    assert err.value.status_code == 409


def test_a_sales_return_credits_the_cost_the_issue_actually_booked(db, user):
    """دومرحله‌ای: فاکتور با میانگینِ ۱٬۰۰۰، خریدِ بعدی میانگین را ۲٬۵۰۰ کرد، خروج با ۲٬۵۰۰.

    برگشتِ کامل باید همان ۱۲٬۵۰۰ را برگرداند که خروج سند زد — نه ۵٬۰۰۰ِ روزِ فاکتور.
    """
    item = make_item(db, name="گرانی")
    _buy(db, user, item, 10, 1_000)
    invoice = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY, warehouse_id=main_warehouse(db).id, contact_id=make_contact(db).id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(5), unit_price=Decimal(9_000))],
        ),
        user,
        move_inventory=False,
    )
    _buy(db, user, item, 10, 4_000)
    issue = create_warehouse_issue(
        db,
        invoice.id,
        WarehouseIssueIn(
            issue_date=TODAY, warehouse_id=main_warehouse(db).id,
            lines=[WarehouseIssueLineIn(sales_invoice_line_id=invoice.lines[0].id, qty=Decimal(5))],
        ),
        user,
    )
    assert issue.total_cost == Decimal(12_500)

    sales_return = post_sales_return(
        db,
        SalesReturnIn(
            return_date=TODAY, sales_invoice_id=invoice.id,
            lines=[SalesReturnLineIn(sales_invoice_line_id=invoice.lines[0].id, qty=Decimal(5))],
        ),
        user,
    )

    assert Decimal(sales_return.total_cost) == Decimal(12_500)


# ─────────────────────────── چاپ ───────────────────────────


def test_the_exit_permit_is_not_an_invoice(db, user, client):
    """§۳۳ §۳۴ — مجوزِ خروج مقدار دارد، مبلغ ندارد."""
    item = make_item(db, name="کالای چاپی", sku="PRN-1")
    _buy(db, user, item, 20, 1_234)
    receiver = make_contact(db, name="گیرنده‌ی برگه")
    issue = _direct(db, user, item, 7, receiver=receiver)

    body = client.get(f"/api/warehouse-issues/{issue.id}/print").text

    assert "مجوز خروج انبار (فروش)" in body
    assert "گیرنده‌ی برگه" in body and "PRN-1" in body
    assert "مقدار فرعی" in body and fa_number(Decimal(7)) in body
    assert "فی" not in body.replace("فیش", "") and fa_number(Decimal(8_638)) not in body


def test_the_a5_template_is_the_same_document(db, user, client):
    """§۳۵ — قالبِ دیگر، نه سندِ دیگر."""
    item = make_item(db, name="A5")
    _buy(db, user, item, 5, 100)
    issue = _direct(db, user, item, 1)
    standard = client.get(f"/api/warehouse-issues/{issue.id}/print").text
    a5 = client.get(f"/api/warehouse-issues/{issue.id}/print", params={"template": "a5"}).text
    assert "size: A5" in a5 and "size: A5" not in standard
    assert client.get(f"/api/warehouse-issues/{issue.id}/print", params={"template": "a3"}).status_code == 400


def test_a_voided_issue_is_marked_on_the_permit(db, user, client):
    item = make_item(db, name="باطل")
    _buy(db, user, item, 5, 100)
    issue = _direct(db, user, item, 1)
    void_warehouse_issue(db, issue.id, reason="ثبتِ تکراری", user=user)
    body = client.get(f"/api/warehouse-issues/{issue.id}/print").text
    assert "این سند باطل شده است" in body and "ثبتِ تکراری" in body


# ─────────────────────────── انتقال بین انبار ───────────────────────────


def _transfer(db, user, item, qty, **header):
    return post_stock_transfer(
        db,
        StockTransferIn(
            transfer_date=TODAY, from_warehouse_id=main_warehouse(db).id,
            to_warehouse_id=other_warehouse(db).id,
            lines=[StockTransferLineIn(item_id=item.id, qty=Decimal(qty))],
            **header,
        ),
        user,
    )


def test_a_transfer_between_two_ledger_accounts_moves_the_value_too(db, user):
    """از وقتی هر انبار معینِ خودش را دارد، نزدنِ سند یعنی مانده‌ی دو معین نخواند."""
    online = other_warehouse(db)
    account = Account(
        code=f"I{next(_SEQ):04d}", name="موجودیِ انبارِ آنلاین", type="asset", is_group=False,
        parent_id=get_account(db, cc.INVENTORY).parent_id,
    )
    db.add(account)
    db.flush()
    online.gl_account_id = account.id
    db.flush()
    item = make_item(db, name="منتقل‌شونده")
    _buy(db, user, item, 10, 1_000)

    transfer = _transfer(db, user, item, 4)

    lines = _entry_lines(db, transfer.journal_entry_id)
    assert {(l.account_id, Decimal(l.debit), Decimal(l.credit)) for l in lines} == {
        (account.id, Decimal(4_000), Decimal(0)),
        (warehouses_svc.inventory_account_id(db, main_warehouse(db).id), Decimal(0), Decimal(4_000)),
    }
    assert get_stock_qty(db, item.id, online.id) == Decimal(4)


def test_a_transfer_between_same_account_warehouses_posts_nothing(db, user):
    """§۲۸ — جمعِ موجودیِ شرکت عوض نمی‌شود؛ حسابی هم عوض نمی‌شود."""
    item = make_item(db, name="هم‌حساب")
    _buy(db, user, item, 10, 1_000)
    assert _transfer(db, user, item, 3).journal_entry_id is None
    assert get_stock_qty(db, item.id, main_warehouse(db).id) + get_stock_qty(db, item.id, other_warehouse(db).id) == Decimal(10)


def test_transfer_lines_of_one_item_are_checked_together(db, user):
    item = make_item(db, name="دو ردیفی")
    _buy(db, user, item, 10, 1_000)
    with pytest.raises(HTTPException) as err:
        post_stock_transfer(
            db,
            StockTransferIn(
                transfer_date=TODAY, from_warehouse_id=main_warehouse(db).id,
                to_warehouse_id=other_warehouse(db).id,
                lines=[
                    StockTransferLineIn(item_id=item.id, qty=Decimal(6)),
                    StockTransferLineIn(item_id=item.id, qty=Decimal(6)),
                ],
            ),
            user,
        )
    assert err.value.status_code == 400
    assert get_stock_qty(db, item.id, other_warehouse(db).id) == Decimal(0)


def test_voiding_a_transfer_returns_both_sides(db, user):
    item = make_item(db, name="برگشتِ انتقال")
    _buy(db, user, item, 10, 1_000)
    transfer = _transfer(db, user, item, 4)

    void_stock_transfer(db, transfer.id, reason="انبارِ اشتباه", user=user)

    assert get_stock_qty(db, item.id, main_warehouse(db).id) == Decimal(10)
    assert get_stock_qty(db, item.id, other_warehouse(db).id) == Decimal(0)
    with pytest.raises(HTTPException) as err:
        void_stock_transfer(db, transfer.id, reason="دوباره", user=user)
    assert err.value.status_code == 409


def test_a_transfer_whose_goods_already_left_the_destination_cannot_be_voided(db, user):
    item = make_item(db, name="مصرف‌شده در مقصد")
    _buy(db, user, item, 10, 1_000)
    transfer = _transfer(db, user, item, 4)
    _direct(db, user, item, 3, issue_type="consumption", account=_expense(db), warehouse=other_warehouse(db))

    with pytest.raises(HTTPException) as err:
        void_stock_transfer(db, transfer.id, reason="دیر شده", user=user)

    assert err.value.status_code == 409
    assert get_stock_qty(db, item.id, other_warehouse(db).id) == Decimal(1)


def test_the_transfer_endpoint_is_idempotent(db, user, client):
    item = make_item(db, name="انتقالِ تکراری")
    _buy(db, user, item, 10, 1_000)
    body = {
        "transfer_date": TODAY.isoformat(), "from_warehouse_id": str(main_warehouse(db).id),
        "to_warehouse_id": str(other_warehouse(db).id), "lines": [{"item_id": str(item.id), "qty": 2}],
    }
    headers = {"Idempotency-Key": f"tr-{uuid.uuid4()}"}
    first = client.post("/api/stock-transfers", json=body, headers=headers)
    second = client.post("/api/stock-transfers", json=body, headers=headers)
    assert first.status_code == 201, first.text
    assert second.json()["id"] == first.json()["id"]
    assert get_stock_qty(db, item.id, other_warehouse(db).id) == Decimal(2)


def test_the_transfer_permit_names_the_destination(db, user, client):
    item = make_item(db, name="حواله‌ی چاپی")
    _buy(db, user, item, 10, 1_000)
    transfer = _transfer(db, user, item, 2)
    body = client.get(f"/api/stock-transfers/{transfer.id}/print").text
    assert "مجوز خروج انبار (انتقال بین انبار)" in body
    assert "انبار مقصد" in body and other_warehouse(db).name in body
