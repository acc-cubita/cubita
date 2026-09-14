"""انبارگردانی — عکس‌برداری، مغایرت کسری/اضافی، سند تجمیعی، و چرخه‌ی وضعیت."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.accounting import JournalEntry, JournalLine
from app.models.inventory import StockLedger
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.schemas.stock_count import CountLineUpdateIn
from app.services import chart_codes as cc
from app.services.common import get_account
from app.services.inventory import get_stock_qty, post_purchase_invoice
from app.services.stock_taking import (
    cancel_session,
    create_session,
    post_session,
    serialize_session,
    set_counts,
)
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 3, 15)


def _stock_in(db, user, item, wh, qty, unit_cost):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 1, 1),
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost))],
        ),
        user,
    )


def _upd(line_id, qty):
    return CountLineUpdateIn(line_id=line_id, counted_qty=Decimal(qty))


def _line_for(session, item_id):
    return next(l for l in session.lines if l.item_id == item_id)


def test_create_snapshots_system_qty_and_excludes_services(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    service = make_item(db, name="نصب", is_service=True)
    _stock_in(db, user, item, wh, 10, 1000)

    session = create_session(db, wh.id, TODAY, user)
    line = _line_for(session, item.id)
    assert line.system_qty == Decimal(10)
    #: **شمارشِ کور:** عدد از شمارنده می‌آید، نه از سیستم. پیش‌فرضِ قدیمی
    #: (`counted_qty = system_qty`) شمارنده را با عددِ سیستم سوگیر می‌کرد و
    #: «نشمرده» را از «شمردم و برابر بود» غیرقابلِ تشخیص می‌ساخت.
    assert line.counted_qty is None
    assert line.unit_cost == Decimal(1000)
    assert all(l.item_id != service.id for l in session.lines)  # خدمت نمی‌آید


def test_shortage_books_debit_adjustment_credit_inventory(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 10, 1000)

    session = create_session(db, wh.id, TODAY, user)
    set_counts(db, session.id, [_upd(_line_for(session, item.id).id, 7)], user)  # کسری ۳
    posted = post_session(db, session.id, user)

    assert posted.status == "posted"
    assert posted.journal_entry_id is not None
    assert posted.posted_at is not None
    assert get_stock_qty(db, item.id, wh.id) == Decimal(7)

    moves = db.query(StockLedger).filter(StockLedger.source_type == "stock_count").all()
    assert len(moves) == 1
    assert moves[0].qty == Decimal(-3)
    assert moves[0].source_id == session.id

    entry = db.get(JournalEntry, posted.journal_entry_id)
    inv = get_account(db, cc.INVENTORY)
    adj = get_account(db, cc.INVENTORY_ADJUSTMENT)
    lines = {l.account_id: l for l in entry.lines}
    assert lines[adj.id].debit == Decimal(3000)  # کسری = هزینه‌ی مغایرت
    assert lines[inv.id].credit == Decimal(3000)


def test_overage_books_reverse(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 10, 1000)

    session = create_session(db, wh.id, TODAY, user)
    set_counts(db, session.id, [_upd(_line_for(session, item.id).id, 13)], user)  # اضافی ۳
    posted = post_session(db, session.id, user)

    assert get_stock_qty(db, item.id, wh.id) == Decimal(13)
    entry = db.get(JournalEntry, posted.journal_entry_id)
    inv = get_account(db, cc.INVENTORY)
    adj = get_account(db, cc.INVENTORY_ADJUSTMENT)
    lines = {l.account_id: l for l in entry.lines}
    assert lines[inv.id].debit == Decimal(3000)
    assert lines[adj.id].credit == Decimal(3000)


def test_no_variance_posts_without_journal(db, user):
    """شمارشی که با سیستم می‌خواند سند نمی‌سازد — ولی باید *شمرده* شده باشد."""
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 10, 1000)

    session = create_session(db, wh.id, TODAY, user)
    set_counts(db, session.id, [_upd(_line_for(session, item.id).id, 10)], user)
    posted = post_session(db, session.id, user)

    assert posted.status == "posted"
    assert posted.journal_entry_id is None
    assert db.query(StockLedger).filter(StockLedger.source_type == "stock_count").count() == 0


def test_posting_without_any_count_is_refused(db, user):
    """جلسه‌ای که هیچ ردیفش شمرده نشده چیزی برای تطبیق ندارد.

    پیش از این چنین جلسه‌ای «بدونِ مغایرت» ثبت می‌شد — چون شمارش از پیش با
    عددِ سیستم پر بود و هیچ‌کس نمی‌فهمید اصلاً کسی سراغِ انبار نرفته.
    """
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 10, 1000)
    session = create_session(db, wh.id, TODAY, user)

    with pytest.raises(HTTPException) as exc:
        post_session(db, session.id, user)
    assert exc.value.status_code == 400


def test_net_zero_value_still_moves_each_item(db, user):
    """اگر ارزشِ خالص صفر شود سندی صادر نمی‌شود، ولی مقدارِ هر کالا باید تعدیل شود."""
    wh = main_warehouse(db)
    a = make_item(db, name="الف")
    b = make_item(db, name="ب")
    _stock_in(db, user, a, wh, 10, 1000)
    _stock_in(db, user, b, wh, 10, 1000)

    session = create_session(db, wh.id, TODAY, user)
    set_counts(
        db,
        session.id,
        [_upd(_line_for(session, a.id).id, 12), _upd(_line_for(session, b.id).id, 8)],  # +۲ و -۲، ارزش خالص صفر
        user,
    )
    posted = post_session(db, session.id, user)

    assert posted.journal_entry_id is None  # ارزش خالص صفر
    assert get_stock_qty(db, a.id, wh.id) == Decimal(12)
    assert get_stock_qty(db, b.id, wh.id) == Decimal(8)
    assert db.query(StockLedger).filter(StockLedger.source_type == "stock_count").count() == 2


def test_serialize_totals(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 10, 1000)
    session = create_session(db, wh.id, TODAY, user)
    set_counts(db, session.id, [_upd(_line_for(session, item.id).id, 7)], user)

    data = serialize_session(session)
    assert data["variance_line_count"] == 1
    assert data["total_variance_value"] == Decimal(-3000)
    line = next(l for l in data["lines"] if l["item_id"] == item.id)
    assert line["variance"] == Decimal(-3)
    assert line["variance_value"] == Decimal(-3000)


def test_second_open_session_rejected(db, user):
    wh = main_warehouse(db)
    make_item(db)
    create_session(db, wh.id, TODAY, user)
    with pytest.raises(HTTPException) as exc:
        create_session(db, wh.id, TODAY, user)
    assert exc.value.status_code == 400


def test_edit_and_post_after_post_rejected(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 10, 1000)
    session = create_session(db, wh.id, TODAY, user)
    set_counts(db, session.id, [_upd(_line_for(session, item.id).id, 10)], user)
    post_session(db, session.id, user)

    with pytest.raises(HTTPException) as exc1:
        post_session(db, session.id, user)
    assert exc1.value.status_code == 400
    with pytest.raises(HTTPException) as exc2:
        set_counts(db, session.id, [_upd(_line_for(session, item.id).id, 5)], user)
    assert exc2.value.status_code == 400


def test_cancel_blocks_further_edits(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 10, 1000)
    session = create_session(db, wh.id, TODAY, user)
    cancelled = cancel_session(db, session.id)
    assert cancelled.status == "cancelled"
    with pytest.raises(HTTPException):
        set_counts(db, session.id, [_upd(_line_for(session, item.id).id, 5)], user)


def test_unknown_session_404(db, user):
    with pytest.raises(HTTPException) as exc:
        post_session(db, uuid4(), user)
    assert exc.value.status_code == 404


def test_negative_count_rejected_by_schema(db):
    with pytest.raises(ValueError):
        CountLineUpdateIn(line_id=uuid4(), counted_qty=Decimal(-1))
