"""فصلِ «برگشت خروج انبار» — ادعاهای اصلی، هرکدام با عددِ خودش.

* **برگشتِ فیزیکی ≠ برگشتِ تجاری (§۱۶ §۱۷):** فاکتور برگشتی دیگر خودش موجودی را زیاد
  نمی‌کند؛ برای هر برگشتِ فیزیکی دقیقاً یک حرکتِ مثبت هست.
* **برگشتِ جزئی (§۱۸–§۲۲):** فاکتور برگشتیِ ۱۰ ← برگشتِ انبارِ ۵ و ۵؛ ششمی رد می‌شود.
* **حساب از خروجِ مبدأ (§۲۸ §۳۸ §۳۹):** برگشتِ مصرف همان هزینه‌ای را بستانکار می‌کند
  که خروج بدهکار کرده بود — نه بهای تمام‌شده، نه درآمد.
* **بها = بهای خروج (§۲۹ §۳۰):** نه قیمتِ فروش و نه میانگینِ امروز.
* **ابطال تاریخچه را خراب نمی‌کند (§۴۰–§۴۲).**
"""
import itertools
import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account, JournalLine
from app.models.inventory import StockLedger
from app.models.invoices import WarehouseIssue
from app.models.issue_returns import WarehouseIssueReturn
from app.models.returns import SalesReturn
from app.schemas.invoices import (
    DirectWarehouseIssueIn,
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
    WarehouseIssueIn,
    WarehouseIssueLineIn,
)
from app.schemas.issue_returns import IssueReturnIn, IssueReturnLineIn
from app.schemas.returns import SalesReturnIn, SalesReturnLineIn
from app.services import chart_codes as cc
from app.services import warehouses as warehouses_svc
from app.services.common import get_account
from app.services.inventory import get_stock_qty, post_purchase_invoice, post_sales_invoice
from app.services.issue_returns import attach_physical_state, create_issue_return, void_issue_return
from app.services.printing import fa_number
from app.services.returns import post_sales_return
from app.services.voiding import void_sales_return
from app.services.warehouse_issues import (
    create_direct_warehouse_issue,
    create_warehouse_issue,
    post_sales_invoice_from_issue,
    void_warehouse_issue,
)
from tests.factories import main_warehouse, make_contact, make_item, other_warehouse

TODAY = date.today()
_SEQ = itertools.count(1)


# ─────────────────────────── سازنده‌ها ───────────────────────────


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


def _expense(db, name="هزینه‌ی مصرفِ کارگاه") -> Account:
    row = Account(
        code=f"R{next(_SEQ):04d}", name=name, type="expense", is_group=False,
        parent_id=get_account(db, cc.INVENTORY_ADJUSTMENT).parent_id,
    )
    db.add(row)
    db.flush()
    return row


def _inventory_account(db, name="موجودیِ انبارِ دوم") -> Account:
    row = Account(
        code=f"J{next(_SEQ):04d}", name=name, type="asset", is_group=False,
        parent_id=get_account(db, cc.INVENTORY).parent_id,
    )
    db.add(row)
    db.flush()
    return row


def _entry(db, entry_id) -> set[tuple]:
    return {
        (line.account_id, Decimal(line.debit), Decimal(line.credit))
        for line in db.query(JournalLine).filter(JournalLine.entry_id == entry_id).all()
    }


def _stock(db, item, warehouse=None) -> Decimal:
    return get_stock_qty(db, item.id, (warehouse or main_warehouse(db)).id)


def _moves(db, source_type, source_id):
    return db.query(StockLedger).filter(
        StockLedger.source_type == source_type, StockLedger.source_id == source_id
    ).all()


def _sell(db, user, item, qty, *, price=3_000, contact=None, warehouse=None):
    """فروشِ خودکار — فاکتور، سند و خروج با هم."""
    return post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY, warehouse_id=(warehouse or main_warehouse(db)).id,
            contact_id=(contact or make_contact(db)).id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_price=Decimal(price))],
        ),
        user,
    )


def _sell_staged(db, user, item, qty, *, price=3_000, contact=None):
    return post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY, contact_id=(contact or make_contact(db)).id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_price=Decimal(price))],
        ),
        user,
        move_inventory=False,
        issue_accounting=False,
    )


def _issue_invoice(db, user, invoice, qty, warehouse=None):
    return create_warehouse_issue(
        db, invoice.id,
        WarehouseIssueIn(
            issue_date=TODAY, warehouse_id=(warehouse or main_warehouse(db)).id,
            lines=[WarehouseIssueLineIn(sales_invoice_line_id=invoice.lines[0].id, qty=Decimal(qty))],
        ),
        user,
    )


def _direct(db, user, item, qty, *, issue_type="consumption", account=None, receiver=None, warehouse=None):
    return create_direct_warehouse_issue(
        db,
        DirectWarehouseIssueIn(
            issue_date=TODAY, issue_type=issue_type, warehouse_id=(warehouse or main_warehouse(db)).id,
            receiver_id=(receiver or make_contact(db)).id if issue_type == "sale" else None,
            account_id=account.id if account is not None else None,
            lines=[WarehouseIssueLineIn(item_id=item.id, qty=Decimal(qty))],
        ),
        user,
    )


def _commercial(db, user, invoice, qty, *, physical):
    return post_sales_return(
        db,
        SalesReturnIn(
            return_date=TODAY, sales_invoice_id=invoice.id,
            lines=[SalesReturnLineIn(sales_invoice_line_id=invoice.lines[0].id, qty=Decimal(qty))],
        ),
        user,
        physical=physical,
    )


def _back_from_sales_return(db, user, sales_return, qty, warehouse=None):
    return create_issue_return(
        db,
        IssueReturnIn(
            return_date=TODAY, return_type="sale", warehouse_id=(warehouse or main_warehouse(db)).id,
            lines=[IssueReturnLineIn(sales_return_line_id=sales_return.lines[0].id, qty=Decimal(qty))],
        ),
        user,
    )


def _back_from_issue(db, user, issue, qty, *, return_type="consumption", deliverer=None, warehouse=None):
    return create_issue_return(
        db,
        IssueReturnIn(
            return_date=TODAY, return_type=return_type, warehouse_id=(warehouse or main_warehouse(db)).id,
            deliverer_id=deliverer.id if deliverer is not None else None,
            lines=[IssueReturnLineIn(warehouse_issue_line_id=issue.lines[0].id, qty=Decimal(qty))],
        ),
        user,
    )


def _state(db, sales_return):
    db.refresh(sales_return)
    attach_physical_state(db, [sales_return])
    return sales_return.physical_status, sales_return.physical_remaining_qty


# ─────────────────────────── مالکیت: یک حرکتِ مثبت ───────────────────────────


def test_an_immediate_sales_return_brings_the_goods_back_through_its_own_issue_return(db, user):
    """§۱۷ §۴۶ — خودکار برای کاربر همان است؛ ولی حرکت و بها مالِ برگشتِ خروج‌اند."""
    item = make_item(db, name="برگشتِ خودکار")
    _buy(db, user, item, 20, 1_000)
    invoice = _sell(db, user, item, 10)
    assert _stock(db, item) == Decimal(10)

    sales_return = _commercial(db, user, invoice, 4, physical=True)

    assert _stock(db, item) == Decimal(14)
    assert sales_return.stock_mode == "issue_return"
    assert _moves(db, "sales_return", sales_return.id) == []
    back = db.query(WarehouseIssueReturn).filter(WarehouseIssueReturn.sales_return_id == sales_return.id).one()
    assert back.origin == "sales_return" and back.return_type == "sale"
    [move] = _moves(db, "warehouse_issue_return", back.id)
    assert Decimal(move.qty) == Decimal(4)

    cogs = get_account(db, cc.COGS).id
    inventory = warehouses_svc.inventory_account_id(db, main_warehouse(db).id)
    commercial_accounts = {account for account, _, _ in _entry(db, sales_return.journal_entry_id)}
    assert cogs not in commercial_accounts and inventory not in commercial_accounts
    assert _entry(db, back.journal_entry_id) == {
        (inventory, Decimal(4_000), Decimal(0)),
        (cogs, Decimal(0), Decimal(4_000)),
    }
    assert _state(db, sales_return) == ("fully_returned", Decimal(0))


def test_a_staged_return_of_ten_comes_back_as_five_and_five(db, user):
    """§۱۸–§۲۲ — نمونه‌ی خودِ فصل: باقیمانده مشتق است و ششمی رد می‌شود."""
    item = make_item(db, name="مرجوعیِ جزئی")
    _buy(db, user, item, 30, 1_000)
    invoice = _sell_staged(db, user, item, 10)
    issue = _issue_invoice(db, user, invoice, 10)
    assert _stock(db, item) == Decimal(20)

    sales_return = _commercial(db, user, invoice, 10, physical=False)
    assert _stock(db, item) == Decimal(20), "برگشتِ تجاری موجودی را تکان نمی‌دهد"
    assert _state(db, sales_return) == ("not_returned", Decimal(10))

    first = _back_from_sales_return(db, user, sales_return, 5)
    assert _stock(db, item) == Decimal(25)
    assert _state(db, sales_return) == ("partially_returned", Decimal(5))

    second = _back_from_sales_return(db, user, sales_return, 5)
    assert _stock(db, item) == Decimal(30)
    assert _state(db, sales_return) == ("fully_returned", Decimal(0))

    with pytest.raises(HTTPException) as err:
        _back_from_sales_return(db, user, sales_return, 1)
    assert err.value.status_code == 400 and "باقیمانده" in err.value.detail

    for back in (first, second):
        [line] = back.lines
        assert line.sales_return_line_id == sales_return.lines[0].id
        assert line.warehouse_issue_line_id == issue.lines[0].id, "زنجیره تا خروجِ اصلی قابلِ ردیابی است"


def test_one_request_cannot_spend_the_same_remainder_twice(db, user):
    """§۴۴ — دو ردیف در یک درخواست همان‌قدر محدودند که دو کاربرِ هم‌زمان."""
    item = make_item(db, name="دو ردیف")
    _buy(db, user, item, 10, 1_000)
    invoice = _sell_staged(db, user, item, 5)
    _issue_invoice(db, user, invoice, 5)
    sales_return = _commercial(db, user, invoice, 5, physical=False)
    line = sales_return.lines[0].id

    with pytest.raises(HTTPException) as err:
        create_issue_return(
            db,
            IssueReturnIn(
                return_date=TODAY, return_type="sale", warehouse_id=main_warehouse(db).id,
                lines=[
                    IssueReturnLineIn(sales_return_line_id=line, qty=Decimal(3)),
                    IssueReturnLineIn(sales_return_line_id=line, qty=Decimal(3)),
                ],
            ),
            user,
        )
    assert err.value.status_code == 400


def test_a_legacy_invoice_keeps_its_inline_return_and_refuses_a_second_physical_one(db, user):
    """فاکتورِ پیش از ۰۱۲۵ خروج ندارد؛ برگشتش همان مسیرِ قدیمی را می‌رود — و فقط یک بار."""
    item = make_item(db, name="فاکتورِ قدیمی")
    _buy(db, user, item, 20, 1_000)
    warehouse = main_warehouse(db)
    invoice = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY, warehouse_id=warehouse.id, contact_id=make_contact(db).id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(5), unit_price=Decimal(3_000))],
        ),
        user, move_inventory=False, issue_accounting=False,
    )
    #: همان ردیفی که فاکتورهای پیش از جداسازی خودشان می‌نوشتند.
    db.add(StockLedger(
        item_id=item.id, warehouse_id=warehouse.id, qty=Decimal(-5), unit_cost=Decimal(1_000),
        entry_date=TODAY, source_type="sales_invoice", source_id=invoice.id,
    ))
    db.flush()

    sales_return = _commercial(db, user, invoice, 3, physical=True)

    assert sales_return.stock_mode == "inline"
    [move] = _moves(db, "sales_return", sales_return.id)
    assert Decimal(move.qty) == Decimal(3)
    assert db.query(WarehouseIssueReturn).filter(WarehouseIssueReturn.sales_return_id == sales_return.id).count() == 0
    with pytest.raises(HTTPException) as err:
        _back_from_sales_return(db, user, sales_return, 1)
    assert "دو بار" in err.value.detail


# ─────────────────────────── دو باگِ بسته‌شده ───────────────────────────


def test_a_voided_issue_no_longer_lets_a_return_invent_stock(db, user):
    """پیش از این: ۲۰ خرید، ۱۰ فروش، ابطالِ خروج، برگشتِ ۵ → موجودیِ ۲۵."""
    item = make_item(db, name="موجودیِ شبح")
    _buy(db, user, item, 20, 1_000)
    invoice = _sell(db, user, item, 10)
    issue = db.query(WarehouseIssue).filter(WarehouseIssue.sales_invoice_id == invoice.id).one()
    void_warehouse_issue(db, issue.id, reason="آزمون", user=user)
    assert _stock(db, item) == Decimal(20)

    with pytest.raises(HTTPException) as err:
        _commercial(db, user, invoice, 5, physical=True)

    assert err.value.status_code == 400 and "خارج نشده" in err.value.detail
    assert _stock(db, item) == Decimal(20)


def test_a_staged_return_debits_the_account_of_the_warehouse_it_returns_to(db, user):
    """پیش از این: کالا به انبارِ آنلاین برمی‌گشت و سند موجودیِ پیش‌فرض را بدهکار می‌کرد."""
    online = other_warehouse(db)
    account = _inventory_account(db)
    online.gl_account_id = account.id
    db.flush()
    item = make_item(db, name="آنلاین")
    _buy(db, user, item, 10, 1_000, warehouse=online)
    invoice = _sell_staged(db, user, item, 4)
    _issue_invoice(db, user, invoice, 4, warehouse=online)
    sales_return = _commercial(db, user, invoice, 2, physical=False)
    cogs = get_account(db, cc.COGS).id

    to_online = _back_from_sales_return(db, user, sales_return, 1, warehouse=online)
    to_main = _back_from_sales_return(db, user, sales_return, 1)

    assert _entry(db, to_online.journal_entry_id) == {
        (account.id, Decimal(1_000), Decimal(0)), (cogs, Decimal(0), Decimal(1_000)),
    }
    default_inventory = warehouses_svc.inventory_account_id(db, main_warehouse(db).id)
    assert _entry(db, to_main.journal_entry_id) == {
        (default_inventory, Decimal(1_000), Decimal(0)), (cogs, Decimal(0), Decimal(1_000)),
    }
    assert _stock(db, item, online) == Decimal(7) and _stock(db, item) == Decimal(1)


# ─────────────────────────── مصرف و سایر ───────────────────────────


def test_a_consumption_return_credits_the_expense_the_issue_debited(db, user):
    """§۲۴ §۳۸ — نه بهای تمام‌شده، نه درآمد، نه طلبِ مشتری."""
    expense = _expense(db)
    item = make_item(db, name="قطعه‌ی مصرفی")
    _buy(db, user, item, 20, 500)
    issue = _direct(db, user, item, 10, account=expense)
    returns_before = db.query(SalesReturn).count()

    back = _back_from_issue(db, user, issue, 4)

    assert _stock(db, item) == Decimal(14)
    inventory = warehouses_svc.inventory_account_id(db, main_warehouse(db).id)
    assert _entry(db, back.journal_entry_id) == {
        (inventory, Decimal(2_000), Decimal(0)),
        (expense.id, Decimal(0), Decimal(2_000)),
    }
    assert back.lines[0].account_id == expense.id
    assert db.query(SalesReturn).count() == returns_before


def test_a_return_only_reverses_an_issue_of_its_own_type(db, user):
    """§۲۴ — «سایر» راهِ دور زدنِ حسابِ خروجِ «مصرف» نیست."""
    item = make_item(db, name="نوعِ نادرست")
    _buy(db, user, item, 10, 500)
    issue = _direct(db, user, item, 5, account=_expense(db))
    with pytest.raises(HTTPException) as err:
        _back_from_issue(db, user, issue, 1, return_type="other")
    assert err.value.status_code == 400 and "«مصرف»" in err.value.detail


def test_the_return_is_valued_at_the_issue_cost_and_voiding_restores_the_average(db, user):
    """§۲۹ §۳۰ — بها همان بهای خروج است؛ ابطال میانگین را به «انگار نبوده» برمی‌گرداند."""
    item = make_item(db, name="میانگین")
    _buy(db, user, item, 10, 1_000)
    issue = _direct(db, user, item, 10, account=_expense(db))
    _buy(db, user, item, 10, 2_000)
    db.refresh(item)
    assert Decimal(item.average_cost) == Decimal(2_000)

    back = _back_from_issue(db, user, issue, 5)
    db.refresh(item)
    assert Decimal(back.lines[0].unit_cost) == Decimal(1_000)
    assert Decimal(item.average_cost).quantize(Decimal("0.01")) == Decimal("1666.67")

    void_issue_return(db, back.id, reason="ثبتِ اشتباه", user=user)
    db.refresh(item)
    assert Decimal(item.average_cost) == Decimal(2_000)
    assert _stock(db, item) == Decimal(10)


# ─────────────────────────── فروشِ پیش از فاکتور ───────────────────────────


def test_goods_returned_before_the_invoice_shrink_the_invoice(db, user, client):
    """ده عدد تحویل، دو عدد پیش از فاکتور برگشت → فاکتور هشت عدد است، نه ده."""
    item = make_item(db, name="پیش از فاکتور", sales_price=1_000)
    _buy(db, user, item, 50, 400)
    receiver = make_contact(db, name="گیرنده‌ی مرجوعی")
    issue = _direct(db, user, item, 10, issue_type="sale", receiver=receiver)
    back = _back_from_issue(db, user, issue, 2, return_type="sale", deliverer=receiver)
    assert _stock(db, item) == Decimal(42)

    context = client.get(f"/api/warehouse-issues/{issue.id}/invoice-context").json()
    assert Decimal(context["lines"][0]["qty"]) == Decimal(8)

    def invoice_of(qty):
        return post_sales_invoice_from_issue(
            db,
            SalesInvoiceIn(
                invoice_date=TODAY, warehouse_id=issue.warehouse_id, contact_id=receiver.id,
                source_warehouse_issue_id=issue.id,
                lines=[SalesInvoiceLineIn(
                    item_id=item.id, qty=Decimal(qty), unit_price=Decimal(1_000),
                    source_issue_line_id=issue.lines[0].id,
                )],
            ),
            user,
        )

    with pytest.raises(HTTPException) as err:
        invoice_of(10)
    assert "خالص" in err.value.detail
    invoice = invoice_of(8)
    assert Decimal(invoice.total_cost) == Decimal(3_200)
    assert _stock(db, item) == Decimal(42), "فاکتور از خروج موجودی را دوباره کم نمی‌کند"

    with pytest.raises(HTTPException) as err:
        void_issue_return(db, back.id, reason="", user=user)
    assert err.value.status_code == 409 and "فاکتور فروش" in err.value.detail


def test_an_invoiced_issue_comes_back_only_through_the_sales_return(db, user):
    """کالای فاکتورشده بدونِ برگشتِ تجاری برنمی‌گردد — وگرنه طلبِ مشتری سرِ جایش می‌ماند."""
    item = make_item(db, name="فاکتورشده")
    _buy(db, user, item, 10, 1_000)
    invoice = _sell(db, user, item, 5)
    issue = db.query(WarehouseIssue).filter(WarehouseIssue.sales_invoice_id == invoice.id).one()
    with pytest.raises(HTTPException) as err:
        _back_from_issue(db, user, issue, 1, return_type="sale", deliverer=make_contact(db))
    assert err.value.status_code == 400 and "برگشت از فروش" in err.value.detail


# ─────────────────────────── ابطال ───────────────────────────


def test_an_issue_with_a_live_return_cannot_be_voided(db, user):
    """§۴۱ — ابطالِ خروج کالای برگشتی را دو بار به انبار برمی‌گرداند."""
    item = make_item(db, name="خروجِ برگشت‌خورده")
    _buy(db, user, item, 20, 1_000)
    issue = _direct(db, user, item, 10, account=_expense(db))
    back = _back_from_issue(db, user, issue, 3)

    with pytest.raises(HTTPException) as err:
        void_warehouse_issue(db, issue.id, reason="", user=user)
    assert err.value.status_code == 409 and str(back.number) in err.value.detail

    void_issue_return(db, back.id, reason="", user=user)
    assert _stock(db, item) == Decimal(10)
    void_warehouse_issue(db, issue.id, reason="", user=user)
    assert _stock(db, item) == Decimal(20)


def test_voiding_a_physical_return_frees_the_remainder_but_keeps_the_sales_return(db, user):
    """§۴۲ — ابطالِ برگشتِ انبار ≠ ابطالِ فاکتور برگشتی."""
    item = make_item(db, name="آزادسازی")
    _buy(db, user, item, 20, 1_000)
    invoice = _sell_staged(db, user, item, 10)
    _issue_invoice(db, user, invoice, 10)
    sales_return = _commercial(db, user, invoice, 10, physical=False)
    back = _back_from_sales_return(db, user, sales_return, 5)

    void_issue_return(db, back.id, reason="شمارشِ اشتباه", user=user)

    assert _stock(db, item) == Decimal(10)
    assert _state(db, sales_return) == ("not_returned", Decimal(10))
    assert sales_return.voided_at is None


def test_voiding_the_sales_return_takes_its_automatic_physical_return_with_it(db, user):
    item = make_item(db, name="آبشار")
    _buy(db, user, item, 20, 1_000)
    invoice = _sell(db, user, item, 10)
    sales_return = _commercial(db, user, invoice, 4, physical=True)
    back = db.query(WarehouseIssueReturn).filter(WarehouseIssueReturn.sales_return_id == sales_return.id).one()

    with pytest.raises(HTTPException) as err:
        void_issue_return(db, back.id, reason="", user=user)
    assert err.value.status_code == 409 and "خودش ساخته" in err.value.detail

    void_sales_return(db, sales_return.id, reason="مشتری منصرف شد", user=user)
    db.refresh(back)
    assert back.voided_at is not None
    assert _stock(db, item) == Decimal(10)


def test_a_sales_return_whose_goods_were_received_by_hand_waits_for_that_return(db, user):
    item = make_item(db, name="دستی")
    _buy(db, user, item, 20, 1_000)
    invoice = _sell_staged(db, user, item, 6)
    _issue_invoice(db, user, invoice, 6)
    sales_return = _commercial(db, user, invoice, 6, physical=False)
    back = _back_from_sales_return(db, user, sales_return, 2)

    with pytest.raises(HTTPException) as err:
        void_sales_return(db, sales_return.id, reason="", user=user)

    assert err.value.status_code == 409 and str(back.number) in err.value.detail


# ─────────────────────────── مسیرِ HTTP، فهرست، مبنا، چاپ ───────────────────────────


def test_transfer_is_not_a_return_type():
    with pytest.raises(ValueError, match="انتقال"):
        IssueReturnIn(
            return_date=TODAY, return_type="transfer", warehouse_id=uuid.uuid4(),
            lines=[IssueReturnLineIn(warehouse_issue_line_id=uuid.uuid4(), qty=Decimal(1))],
        )


def test_the_endpoint_is_idempotent(db, user, client):
    """§۴۵ — پاسخِ گم‌شده و تکرار: یک برگشت، یک حرکتِ مثبت."""
    item = make_item(db, name="تکرارِ شبکه")
    _buy(db, user, item, 10, 1_000)
    issue = _direct(db, user, item, 6, account=_expense(db))
    body = {
        "return_date": TODAY.isoformat(), "return_type": "consumption",
        "warehouse_id": str(main_warehouse(db).id),
        "lines": [{"warehouse_issue_line_id": str(issue.lines[0].id), "qty": 2}],
    }
    headers = {"Idempotency-Key": f"ir-{uuid.uuid4()}"}

    first = client.post("/api/warehouse-issue-returns", json=body, headers=headers)
    second = client.post("/api/warehouse-issue-returns", json=body, headers=headers)

    assert first.status_code == 201, first.text
    assert second.json()["id"] == first.json()["id"]
    assert len(_moves(db, "warehouse_issue_return", uuid.UUID(first.json()["id"]))) == 1
    assert _stock(db, item) == Decimal(6)


def test_one_list_for_every_type_with_a_type_filter(db, user, client):
    """§۳۴ §۳۵ — فروش و مصرف کنارِ هم، با شماره‌ی سند حسابداری و مبنا."""
    item = make_item(db, name="فهرست")
    _buy(db, user, item, 40, 1_000)
    issue = _direct(db, user, item, 5, account=_expense(db))
    consumption = _back_from_issue(db, user, issue, 1)
    invoice = _sell_staged(db, user, item, 5)
    _issue_invoice(db, user, invoice, 5)
    sales_return = _commercial(db, user, invoice, 5, physical=False)
    sale = _back_from_sales_return(db, user, sales_return, 2)

    rows = {row["id"]: row for row in client.get("/api/warehouse-issue-returns", params={"limit": 200}).json()["items"]}
    assert {str(consumption.id), str(sale.id)} <= set(rows)
    assert rows[str(consumption.id)]["type_label"] == "مصرف"
    assert rows[str(consumption.id)]["issue_numbers"] == [issue.number]
    assert rows[str(consumption.id)]["journal_entry_number"] is not None
    assert rows[str(sale.id)]["sales_return_numbers"] == [sales_return.number]
    assert Decimal(rows[str(sale.id)]["total_cost"]) == Decimal(2_000)

    only = client.get("/api/warehouse-issue-returns", params={"return_type": "consumption", "limit": 200}).json()["items"]
    assert {row["return_type"] for row in only} == {"consumption"}
    assert client.get("/api/warehouse-issue-returns", params={"return_type": "transfer"}).status_code == 400

    listed = {row["id"]: row for row in client.get("/api/sales-returns", params={"limit": 200}).json()["items"]}
    assert listed[str(sales_return.id)]["physical_status"] == "partially_returned"
    assert Decimal(listed[str(sales_return.id)]["physical_remaining_qty"]) == Decimal(3)


def test_the_basis_window_shows_only_what_can_still_come_back(db, user, client):
    """§۱۴ — «مبنا» با باقیمانده؛ فاکتور برگشتی و خروجِ بی‌فاکتور برای فروش."""
    item = make_item(db, name="مبنا")
    _buy(db, user, item, 40, 1_000)
    invoice = _sell_staged(db, user, item, 10)
    _issue_invoice(db, user, invoice, 10)
    sales_return = _commercial(db, user, invoice, 10, physical=False)
    uninvoiced = _direct(db, user, item, 3, issue_type="sale")
    consumption = _direct(db, user, item, 2, account=_expense(db))

    sale_ids = {row["id"] for row in client.get("/api/warehouse-issue-returns/basis", params={"return_type": "sale"}).json()}
    assert {str(sales_return.id), str(uninvoiced.id)} <= sale_ids
    assert str(consumption.id) not in sale_ids

    _back_from_sales_return(db, user, sales_return, 4)
    detail = client.get(f"/api/warehouse-issue-returns/basis/sales_return/{sales_return.id}").json()
    [line] = detail["lines"]
    assert Decimal(line["returned"]) == Decimal(4) and Decimal(line["remaining"]) == Decimal(6)


def test_the_print_is_a_warehouse_document_with_cost_and_amount(db, user, client):
    """§۳۲ §۳۳ — برگه‌ی «برگشت خروج انبار»، با فی و مبلغِ **بها**، نه فاکتور برگشتی."""
    item = make_item(db, name="برگه‌ی برگشت")
    _buy(db, user, item, 10, 1_234)
    deliverer = make_contact(db, name="تحویل‌دهنده‌ی آزمون")
    issue = _direct(db, user, item, 7, account=_expense(db))
    back = create_issue_return(
        db,
        IssueReturnIn(
            return_date=TODAY, return_type="consumption", warehouse_id=main_warehouse(db).id,
            deliverer_id=deliverer.id,
            lines=[IssueReturnLineIn(warehouse_issue_line_id=issue.lines[0].id, qty=Decimal(3))],
        ),
        user,
    )

    body = client.get(f"/api/warehouse-issue-returns/{back.id}/print").text

    assert "برگشت خروج انبار (مصرف)" in body
    assert "تحویل‌دهنده‌ی آزمون" in body and "مبلغ" in body
    assert fa_number(Decimal(3_702)) in body
    permit = client.get(f"/api/warehouse-issues/{issue.id}/print").text
    assert "<th class=\"num\" style=\"width:10%\">مبلغ</th>" not in permit, "مجوزِ خروج همچنان بی‌مبلغ است"
