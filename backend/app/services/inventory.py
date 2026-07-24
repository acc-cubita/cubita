from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.counters import DOC_JOURNAL_ENTRY, DOC_PURCHASE_INVOICE, DOC_SALES_INVOICE
from app.services.numbering import next_document_number
from app.models.accounting import JournalEntry, JournalLine
from app.models.inventory import Item, StockAdjustment, StockLedger
from app.models.invoices import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
)
from app.models.user import User
from app.schemas.inventory import StockAdjustmentIn
from app.schemas.invoices import PurchaseInvoiceIn, SalesInvoiceIn
from app.services import chart_codes as cc
from app.services.common import get_account as _get_account
from app.services.common import get_or_create_account
from app.services.cost_centers import resolve_cost_center_id
from app.services.period_close import assert_period_open


def vat_payable_account(db: Session):
    return get_or_create_account(
        db,
        cc.VAT_PAYABLE,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.VAT_PAYABLE],
        name="مالیات بر ارزش افزوده پرداختنی",
        acc_type="liability",
        parent_code="21",
    )


def vat_receivable_account(db: Session):
    return get_or_create_account(
        db,
        cc.VAT_RECEIVABLE,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.VAT_RECEIVABLE],
        name="مالیات بر ارزش افزوده / اعتبار مالیاتی",
        acc_type="asset",
        parent_code="11",
    )


def compute_tax(net: Decimal, rate: Decimal) -> Decimal:
    """مبلغ مالیات = خالص × نرخ٪، گردشده به عددِ صحیحِ ریال/تومان (ROUND_HALF_UP)."""
    if rate is None or rate <= 0:
        return Decimal(0)
    return (net * rate / Decimal(100)).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def get_stock_qty(db: Session, item_id: UUID, warehouse_id: UUID) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(StockLedger.qty), 0))
        .filter(StockLedger.item_id == item_id, StockLedger.warehouse_id == warehouse_id)
        .scalar()
    )
    return Decimal(total)


def get_total_stock_qty(db: Session, item_id: UUID) -> Decimal:
    total = db.query(func.coalesce(func.sum(StockLedger.qty), 0)).filter(StockLedger.item_id == item_id).scalar()
    return Decimal(total)


def lock_items(db: Session, item_ids) -> None:
    """ردیف کالاها را تا پایان تراکنش قفل می‌کند.

    قفل روی «کالا» است و نه روی دفتر موجودی، چون دفتر append-only است: قفل کردن
    ردیف‌های موجود جلوی INSERT ردیف جدید توسط تراکنش دیگر را نمی‌گیرد. ردیف کالا
    تنها نقطه‌ی مشترکی است که همه‌ی عملیات آن کالا از آن رد می‌شوند، و همین قفل
    هم‌زمان read-modify-write روی average_cost را هم امن می‌کند.

    ORDER BY لازم است نه تزئینی: بدون ترتیب قطعی، دو فاکتور هم‌زمان روی کالاهای
    مشترک می‌توانند آن‌ها را به ترتیب معکوس قفل کنند و deadlock بدهند.

    این فقط وقتی معنا دارد که تراکنش تا لحظه‌ی نوشتن باز بماند — که مرز تراکنشِ
    سطح درخواست در get_db آن را تضمین می‌کند.
    """
    ids = sorted(set(item_ids))
    if not ids:
        return
    db.query(Item.id).filter(Item.id.in_(ids)).order_by(Item.id).with_for_update().all()


def post_sales_invoice(db: Session, data: SalesInvoiceIn, user: User) -> SalesInvoice:
    assert_period_open(db, data.invoice_date)

    items_by_id = {item.id: item for item in db.query(Item).filter(Item.id.in_([l.item_id for l in data.lines])).all()}

    # مقدار درخواستی هر کالا باید بین ردیف‌ها جمع شود، نه ردیف‌به‌ردیف سنجیده شود:
    # وگرنه فاکتوری با دو ردیف ۶تایی از یک کالا در برابر موجودی ۱۰ پاس می‌شد، چون هر
    # ردیف جدا با همان ۱۰ مقایسه می‌شد. این تک‌نخی هم رخ می‌داد و نیازی به همزمانی نداشت.
    requested_by_item: dict[UUID, Decimal] = {}
    for line in data.lines:
        item = items_by_id.get(line.item_id)
        if item is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کالا با شناسه {line.item_id} یافت نشد")
        if not item.is_service:
            requested_by_item[line.item_id] = requested_by_item.get(line.item_id, Decimal(0)) + line.qty

    # قفل قبل از خواندن موجودی: وگرنه دو فاکتور موازی هر دو همان موجودی را می‌خوانند،
    # هر دو پاس می‌شوند و موجودی منفی می‌شود — یعنی کالایی فروخته می‌شود که وجود ندارد.
    lock_items(db, requested_by_item.keys())

    for item_id, requested in requested_by_item.items():
        available = get_stock_qty(db, item_id, data.warehouse_id)
        if available < requested:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"موجودی «{items_by_id[item_id].name}» کافی نیست (موجود: {available}, درخواستی: {requested})",
            )

    number = next_document_number(db, DOC_SALES_INVOICE)

    total_amount = Decimal(0)
    total_discount = Decimal(0)
    total_cost = Decimal(0)
    invoice_lines: list[SalesInvoiceLine] = []
    stock_moves: list[StockLedger] = []

    for line in data.lines:
        item = items_by_id[line.item_id]
        unit_cost = item.average_cost if not item.is_service else Decimal(0)
        line_discount = Decimal(line.discount or 0)
        # خالصِ ردیف = ناخالص − تخفیف. جمعِ همین‌ها می‌شود total_amount، یعنی درآمد و
        # پایه‌ی مالیات هر دو «پس از تخفیف»اند.
        total_amount += (line.qty * line.unit_price) - line_discount
        total_discount += line_discount
        total_cost += line.qty * unit_cost
        invoice_lines.append(
            SalesInvoiceLine(
                item_id=line.item_id,
                qty=line.qty,
                unit_price=line.unit_price,
                discount=line_discount,
                unit_cost=unit_cost,
                description=line.description,
            )
        )
        if not item.is_service:
            stock_moves.append(
                StockLedger(
                    item_id=line.item_id,
                    warehouse_id=data.warehouse_id,
                    qty=-line.qty,
                    unit_cost=unit_cost,
                    entry_date=data.invoice_date,
                    source_type="sales_invoice",
                )
            )

    tax_amount = compute_tax(total_amount, data.tax_rate)
    cost_center_id = resolve_cost_center_id(db, data.cost_center_id)
    receivable_or_cash = _get_account(db, cc.ACCOUNTS_RECEIVABLE) if data.contact_id else _get_account(db, cc.CASH)
    journal_lines = [
        JournalLine(
            account_id=receivable_or_cash.id,
            debit=total_amount + tax_amount,  # مشتری خالص + مالیات را می‌پردازد
            credit=0,
            description="بابت فروش کالا/خدمت",
        ),
        JournalLine(
            account_id=_get_account(db, cc.SALES_REVENUE).id,
            debit=0,
            credit=total_amount,
            description="بابت فروش کالا/خدمت",
        ),
    ]
    if tax_amount > 0:
        journal_lines.append(
            JournalLine(
                account_id=vat_payable_account(db).id,
                debit=0,
                credit=tax_amount,
                description="مالیات بر ارزش افزوده فروش",
            )
        )
    if total_cost > 0:
        journal_lines.append(
            JournalLine(
                account_id=_get_account(db, cc.COGS).id,
                debit=total_cost,
                credit=0,
                description="بهای تمام‌شده کالای فروش‌رفته",
            )
        )
        journal_lines.append(
            JournalLine(
                account_id=_get_account(db, cc.INVENTORY).id,
                debit=0,
                credit=total_cost,
                description="کسر از موجودی کالا بابت فروش",
            )
        )

    if cost_center_id is not None:
        for line in journal_lines:
            line.cost_center_id = cost_center_id

    entry_number = next_document_number(db, DOC_JOURNAL_ENTRY)
    journal_entry = JournalEntry(
        number=entry_number,
        entry_date=data.invoice_date,
        description=f"فاکتور فروش شماره {number}",
        source_type="sales_invoice",
        created_by_id=user.id,
        lines=journal_lines,
    )
    db.add(journal_entry)
    db.flush()

    invoice = SalesInvoice(
        number=number,
        invoice_date=data.invoice_date,
        contact_id=data.contact_id,
        cost_center_id=cost_center_id,
        warehouse_id=data.warehouse_id,
        description=data.description,
        total_amount=total_amount,
        total_discount=total_discount,
        total_cost=total_cost,
        tax_rate=data.tax_rate,
        tax_amount=tax_amount,
        journal_entry_id=journal_entry.id,
        source_order_id=data.source_order_id,
        created_by_id=user.id,
        lines=invoice_lines,
    )
    db.add(invoice)
    # flush اجباری است و تزئینی نیست: شناسه‌ی کلید اصلی با default=uuid4 در لحظه‌ی
    # INSERT ساخته می‌شود، نه موقع ساختن شیء. بدون این خط، مقدارِ خوانده‌شده None
    # است و حرکت انبار بی‌صدا بدون منشأ ذخیره می‌شود — کاردکس و ابطال هر دو می‌شکنند.
    db.flush()
    for move in stock_moves:
        move.source_id = invoice.id
        db.add(move)

    db.flush()
    db.refresh(invoice)
    return invoice


def post_purchase_invoice(db: Session, data: PurchaseInvoiceIn, user: User) -> PurchaseInvoice:
    assert_period_open(db, data.invoice_date)

    items_by_id = {item.id: item for item in db.query(Item).filter(Item.id.in_([l.item_id for l in data.lines])).all()}
    for line in data.lines:
        if line.item_id not in items_by_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کالا با شناسه {line.item_id} یافت نشد")

    # average_cost پایین‌تر read-modify-write می‌شود؛ بدون قفل، دو خرید هم‌زمان یکی
    # محاسبه‌ی دیگری را بازنویسی می‌کند و بهای تمام‌شده برای همیشه غلط می‌ماند.
    lock_items(db, [line.item_id for line in data.lines])

    number = next_document_number(db, DOC_PURCHASE_INVOICE)

    total_amount = Decimal(0)
    total_discount = Decimal(0)
    invoice_lines: list[PurchaseInvoiceLine] = []
    stock_moves: list[StockLedger] = []

    for line in data.lines:
        item = items_by_id[line.item_id]
        line_discount = Decimal(line.discount or 0)
        line_net = (line.qty * line.unit_cost) - line_discount
        # بهای واقعیِ تمام‌شده‌ی هر واحد پس از تخفیف. موجودی باید به همین ارزش‌گذاری
        # شود، وگرنه انبار گران‌تر از چیزی که پول داده‌ایم در دفاتر می‌نشیند و سودِ
        # فروشِ بعدی کمتر از واقع گزارش می‌شود.
        effective_unit_cost = (line_net / line.qty) if line.qty else Decimal(0)
        total_amount += line_net
        total_discount += line_discount
        invoice_lines.append(
            PurchaseInvoiceLine(
                item_id=line.item_id,
                qty=line.qty,
                unit_cost=line.unit_cost,  # قیمتِ فهرستِ تأمین‌کننده، همان‌طور که در فاکتورش هست
                discount=line_discount,
                description=line.description,
            )
        )
        if not item.is_service:
            existing_qty = get_total_stock_qty(db, item.id)
            new_qty = existing_qty + line.qty
            if new_qty > 0:
                item.average_cost = ((existing_qty * item.average_cost) + line_net) / new_qty
            stock_moves.append(
                StockLedger(
                    item_id=line.item_id,
                    warehouse_id=data.warehouse_id,
                    qty=line.qty,
                    unit_cost=effective_unit_cost,
                    entry_date=data.invoice_date,
                    source_type="purchase_invoice",
                )
            )

    tax_amount = compute_tax(total_amount, data.tax_rate)
    cost_center_id = resolve_cost_center_id(db, data.cost_center_id)
    payable_or_cash = _get_account(db, cc.ACCOUNTS_PAYABLE) if data.contact_id else _get_account(db, cc.CASH)
    journal_lines = [
        JournalLine(
            account_id=_get_account(db, cc.INVENTORY).id,
            debit=total_amount,
            credit=0,
            description="بابت خرید کالا",
        ),
    ]
    if tax_amount > 0:
        journal_lines.append(
            JournalLine(
                account_id=vat_receivable_account(db).id,
                debit=tax_amount,
                credit=0,
                description="مالیات بر ارزش افزوده خرید (اعتبار مالیاتی)",
            )
        )
    journal_lines.append(
        JournalLine(
            account_id=payable_or_cash.id,
            debit=0,
            credit=total_amount + tax_amount,  # به تأمین‌کننده خالص + مالیات پرداخت می‌شود
            description="بابت خرید کالا",
        )
    )

    if cost_center_id is not None:
        for line in journal_lines:
            line.cost_center_id = cost_center_id

    entry_number = next_document_number(db, DOC_JOURNAL_ENTRY)
    journal_entry = JournalEntry(
        number=entry_number,
        entry_date=data.invoice_date,
        description=f"فاکتور خرید شماره {number}",
        source_type="purchase_invoice",
        created_by_id=user.id,
        lines=journal_lines,
    )
    db.add(journal_entry)
    db.flush()

    invoice = PurchaseInvoice(
        number=number,
        invoice_date=data.invoice_date,
        contact_id=data.contact_id,
        cost_center_id=cost_center_id,
        warehouse_id=data.warehouse_id,
        description=data.description,
        total_amount=total_amount,
        total_discount=total_discount,
        tax_rate=data.tax_rate,
        tax_amount=tax_amount,
        journal_entry_id=journal_entry.id,
        created_by_id=user.id,
        lines=invoice_lines,
    )
    db.add(invoice)
    # flush اجباری است و تزئینی نیست: شناسه‌ی کلید اصلی با default=uuid4 در لحظه‌ی
    # INSERT ساخته می‌شود، نه موقع ساختن شیء. بدون این خط، مقدارِ خوانده‌شده None
    # است و حرکت انبار بی‌صدا بدون منشأ ذخیره می‌شود — کاردکس و ابطال هر دو می‌شکنند.
    db.flush()
    for move in stock_moves:
        move.source_id = invoice.id
        db.add(move)

    db.flush()
    db.refresh(invoice)
    return invoice


def post_stock_adjustment(db: Session, data: StockAdjustmentIn, user: User) -> StockAdjustment:
    assert_period_open(db, data.adjustment_date)

    item = db.get(Item, data.item_id)
    if item is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کالا یافت نشد")
    if item.is_service:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "خدمت موجودی ندارد که تعدیل شود")

    if data.qty_diff < 0:
        available = get_stock_qty(db, data.item_id, data.warehouse_id)
        if available < abs(data.qty_diff):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"موجودی «{item.name}» برای این میزان کسری کافی نیست (موجود: {available})",
            )

    unit_cost = item.average_cost
    amount = abs(data.qty_diff) * unit_cost

    # کسری: بدهکار حساب مغایرت انبار (هزینه)، بستانکار موجودی کالا. اضافی: برعکس (کاهش هزینه‌ی مغایرت).
    if data.qty_diff < 0:
        debit_account, credit_account = cc.INVENTORY_ADJUSTMENT, cc.INVENTORY
    else:
        debit_account, credit_account = cc.INVENTORY, cc.INVENTORY_ADJUSTMENT

    journal_entry = None
    if amount > 0:
        entry_number = next_document_number(db, DOC_JOURNAL_ENTRY)
        journal_entry = JournalEntry(
            number=entry_number,
            entry_date=data.adjustment_date,
            description=f"تعدیل موجودی «{item.name}»: {data.reason}".strip(),
            source_type="stock_adjustment",
            created_by_id=user.id,
            lines=[
                JournalLine(account_id=_get_account(db, debit_account).id, debit=amount, credit=0),
                JournalLine(account_id=_get_account(db, credit_account).id, debit=0, credit=amount),
            ],
        )
        db.add(journal_entry)
        db.flush()

    adjustment = StockAdjustment(
        item_id=data.item_id,
        warehouse_id=data.warehouse_id,
        qty_diff=data.qty_diff,
        unit_cost=unit_cost,
        reason=data.reason,
        adjustment_date=data.adjustment_date,
        journal_entry_id=journal_entry.id if journal_entry else None,
        created_by_id=user.id,
    )
    db.add(adjustment)
    db.add(
        StockLedger(
            item_id=data.item_id,
            warehouse_id=data.warehouse_id,
            qty=data.qty_diff,
            unit_cost=unit_cost,
            entry_date=data.adjustment_date,
            source_type="adjustment",
        )
    )
    db.flush()
    db.refresh(adjustment)
    return adjustment
