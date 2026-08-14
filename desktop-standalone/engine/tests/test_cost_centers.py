"""مراکز هزینه/پروژه — برچسبِ سند، انتقال به سندِ فاکتور، گزارشِ سود، و گاردِ حذف."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import JournalEntry, JournalLine
from app.schemas.cost_center import CostCenterIn
from app.schemas.invoices import SalesInvoiceIn, SalesInvoiceLineIn, PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.services import chart_codes as cc
from app.services import cost_centers as svc
from app.services.common import get_account, make_journal_entry
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.reports import get_cost_center_report
from app.models.cost_center import CostCenter
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 3, 15)


def _center(db, user, name="پروژه الف", code="P1"):
    return svc.create_cost_center(db, CostCenterIn(name=name, code=code), user)


def _tagged(db, user, account, *, debit=0, credit=0, center=None):
    other = get_account(db, cc.CASH)
    make_journal_entry(
        db,
        TODAY,
        "تست مرکز",
        "manual",
        user,
        [
            JournalLine(account_id=account.id, debit=Decimal(debit), credit=Decimal(credit),
                        cost_center_id=center.id if center else None),
            JournalLine(account_id=other.id, debit=Decimal(credit), credit=Decimal(debit),
                        cost_center_id=center.id if center else None),
        ],
    )
    db.flush()


def _row(report, cost_center_id):
    return next((r for r in report["rows"] if r["cost_center_id"] == cost_center_id), None)


def test_create_and_list(db, user):
    c = _center(db, user)
    centers = svc.list_cost_centers(db)
    assert any(x.id == c.id for x in centers)


def test_report_groups_income_and_expense_by_center(db, user):
    center = _center(db, user)
    rev = get_account(db, cc.SALES_REVENUE)
    exp = get_account(db, cc.PAYROLL_EXPENSE)
    _tagged(db, user, rev, credit=1_000_000, center=center)
    _tagged(db, user, exp, debit=400_000, center=center)

    report = get_cost_center_report(db, None, None)
    row = _row(report, center.id)
    assert row is not None
    assert row["income"] == Decimal(1_000_000)
    assert row["expense"] == Decimal(400_000)
    assert row["profit"] == Decimal(600_000)


def test_untagged_activity_falls_into_none_bucket(db, user):
    rev = get_account(db, cc.SALES_REVENUE)
    _tagged(db, user, rev, credit=500_000, center=None)

    report = get_cost_center_report(db, None, None)
    none_row = _row(report, None)
    assert none_row is not None
    assert none_row["cost_center_name"] == "بدون مرکز هزینه"
    assert none_row["income"] >= Decimal(500_000)


def test_sales_invoice_propagates_center_to_journal_lines(db, user):
    center = _center(db, user)
    wh = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(1_000_000))],
        ),
        user,
    )

    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            cost_center_id=center.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_price=Decimal(5_000_000))],
        ),
        user,
    )

    assert inv.cost_center_id == center.id
    entry = db.get(JournalEntry, inv.journal_entry_id)
    # همه‌ی ردیف‌های سندِ فاکتور باید برچسبِ مرکز را گرفته باشند
    assert entry.lines and all(l.cost_center_id == center.id for l in entry.lines)

    # و در گزارش، سود این پروژه = درآمد ۱۰م − COGS ۲م = ۸م
    report = get_cost_center_report(db, None, None)
    row = _row(report, center.id)
    assert row["income"] == Decimal(10_000_000)
    assert row["expense"] == Decimal(2_000_000)
    assert row["profit"] == Decimal(8_000_000)


def test_invalid_cost_center_on_invoice_is_rejected(db, user):
    from uuid import uuid4

    wh = main_warehouse(db)
    item = make_item(db)
    with pytest.raises(HTTPException) as exc:
        post_sales_invoice(
            db,
            SalesInvoiceIn(
                invoice_date=TODAY,
                warehouse_id=wh.id,
                cost_center_id=uuid4(),  # وجود ندارد
                lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(1_000))],
            ),
            user,
        )
    assert exc.value.status_code == 400


def test_delete_blocked_when_referenced(db, user):
    center = _center(db, user)
    rev = get_account(db, cc.SALES_REVENUE)
    _tagged(db, user, rev, credit=100_000, center=center)
    with pytest.raises(HTTPException) as exc:
        svc.delete_cost_center(db, center.id)
    assert exc.value.status_code == 400


def test_delete_ok_when_unreferenced(db, user):
    center = _center(db, user)
    svc.delete_cost_center(db, center.id)
    assert db.get(CostCenter, center.id) is None
