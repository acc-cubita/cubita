"""ورودِ واقعیِ کالا به انبار — و در گردشِ خرید، سندِ عملیاتیِ همان ورود.

**دو مسیرِ معتبر (§۹).** رسید یا به فاکتورِ خرید گره می‌خورد، یا مستقیم ثبت
می‌شود. تا امروز فقط مسیرِ اول ممکن بود؛ خریدی که فاکتورش بعداً می‌آید — یا
اصلاً نمی‌آید — هیچ راهی برای ورودِ کالا نداشت.

---

**نقطه‌ی ثبتِ حسابداری صریح است، و این مهم‌ترین قاعده‌ی این فایل است (§۳۷).**

فصل هشدار می‌دهد که فاکتور و رسید نباید یک بدهی را دو بار ثبت کنند. سیاستِ
موجودِ کوبیتا سنجیده شد و منسجم است: بدهی را **فاکتور** می‌شناسد و رسید هیچ
سندی نمی‌زند. آن دست نمی‌خورد.

ولی رسیدِ **مستقیم** فاکتوری ندارد که بدهی را شناخته باشد. نزدنِ سند برایش یعنی
کالا بی‌هیچ اثرِ حسابداری وارد انبار شود و دفتر با گزارشِ انبار برای همیشه
واگرا بماند — همان بیماری‌ای که این فصل می‌خواهد درمانش کند. پس:

    رسیدِ گره‌خورده به فاکتور  →  فقط حرکتِ فیزیکی
    رسیدِ مستقیم               →  حرکتِ فیزیکی + سندِ حسابداری

`receipt.journal_entry_id` می‌گوید کدام‌یک اتفاق افتاده. §۴۴ می‌خواهد «اثرِ
انباری» و «اثرِ حسابداری» دو چیزِ جدا باشند، نه یک بولینِ مبهم.

**و حساب‌ها با نقش حل می‌شوند، نه با کد یا نام (§۳۶).**
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalLine
from app.models.advanced_inventory import StockBatch
from app.models.counters import DOC_WAREHOUSE_RECEIPT
from app.models.inventory import Contact, Item, StockLedger, Warehouse
from app.models.invoices import (
    RECEIPT_TYPE_LABELS,
    RECEIPT_TYPES,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    WarehouseReceipt,
    WarehouseReceiptLine,
)
from app.models.user import User
from app.schemas.invoices import WarehouseReceiptIn
from app.services import chart_codes as cc
from app.services import items as items_svc
from app.services import warehouses as warehouses_svc
from app.services.common import get_account, make_journal_entry
from app.services.inventory import get_total_stock_qty, goods_in_transit_account, lock_items
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open
from app.services.voiding import recompute_average_cost, reverse_journal_entry


def received_by_line(db: Session, invoice_id: UUID) -> dict[UUID, Decimal]:
    rows = (
        db.query(WarehouseReceiptLine.purchase_invoice_line_id, func.sum(WarehouseReceiptLine.qty))
        .join(WarehouseReceipt, WarehouseReceipt.id == WarehouseReceiptLine.receipt_id)
        .filter(
            WarehouseReceipt.purchase_invoice_id == invoice_id,
            WarehouseReceipt.voided_at.is_(None),
            WarehouseReceipt.status == "posted",
        )
        .group_by(WarehouseReceiptLine.purchase_invoice_line_id)
        .all()
    )
    return {line_id: Decimal(qty) for line_id, qty in rows}


def _resolve_invoice(db: Session, invoice_id: UUID | None) -> PurchaseInvoice | None:
    """فاکتورِ مبدأ، اگر رسید به یکی گره خورده باشد (§۸).

    `None` یعنی رسیدِ مستقیم — یک سناریوی واقعی، نه یک حالتِ خطا.
    """
    if invoice_id is None:
        return None
    invoice = db.get(PurchaseInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور خرید یافت نشد")
    if invoice.is_voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "برای فاکتور باطل‌شده نمی‌توان رسید انبار ساخت")
    return invoice


def _invoice_backed_lines(
    db: Session, invoice: PurchaseInvoice, data: WarehouseReceiptIn
) -> list[dict]:
    """ردیف‌های رسید از روی ردیف‌های فاکتور، با گاردِ «بیش از مانده»."""
    requested = {row.purchase_invoice_line_id: Decimal(row.qty) for row in data.lines}
    if None in requested:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "وقتی رسید به فاکتور گره خورده، هر ردیف باید ردیفِ فاکتورش را نام ببرد.",
        )
    purchase_lines = (
        db.query(PurchaseInvoiceLine)
        .filter(PurchaseInvoiceLine.invoice_id == invoice.id, PurchaseInvoiceLine.id.in_(requested))
        .with_for_update()
        .all()
    )
    if len(purchase_lines) != len(requested):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "یکی از ردیف‌ها متعلق به این فاکتور نیست")

    already = received_by_line(db, invoice.id)
    rows = []
    for line in purchase_lines:
        remaining = Decimal(line.qty) - already.get(line.id, Decimal(0))
        if requested[line.id] > remaining:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"مقدار تحویل «{line.item_name_snapshot or line.item.name}» از مانده {remaining} بیشتر است",
            )
        #: بهای ورود از **خالصِ ردیفِ فاکتور** می‌آید (پس از تخفیف، با اضافات و
        #: عوارض) — نه از قیمتِ فهرستِ تأمین‌کننده. وگرنه انبار گران‌تر از چیزی
        #: که پول داده‌ایم ارزش‌گذاری می‌شود.
        line_value = (
            Decimal(line.qty) * Decimal(line.unit_cost)
            - Decimal(line.discount)
            + Decimal(line.addition)
            + Decimal(line.duty_amount)
        )
        rows.append(
            {
                "purchase_invoice_line_id": line.id,
                "item": line.item,
                "qty": requested[line.id],
                "unit_cost": line_value / Decimal(line.qty),
                "code": line.item_code_snapshot or line.item.sku,
                "name": line.item_name_snapshot or line.item.name,
                "unit": line.unit_snapshot or line.item.unit,
                "description": next(
                    row.description
                    for row in data.lines
                    if row.purchase_invoice_line_id == line.id
                ),
            }
        )
    return rows


def _direct_lines(db: Session, data: WarehouseReceiptIn) -> list[dict]:
    """ردیف‌های رسیدِ مستقیم — کالا و مقدار و بها مستقیم وارد می‌شوند (§۹).

    کالا از **Item Master** می‌آید و این‌جا هیچ کالای تازه‌ای ساخته نمی‌شود
    (§۱۵).
    """
    items = {
        item.id: item
        for item in db.query(Item).filter(Item.id.in_([row.item_id for row in data.lines])).all()
    }
    rows = []
    for row in data.lines:
        item = items.get(row.item_id)
        if item is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کالا با شناسه {row.item_id} یافت نشد")
        rows.append(
            {
                "purchase_invoice_line_id": None,
                "item": item,
                "qty": Decimal(row.qty),
                "unit_cost": Decimal(row.unit_cost or 0),
                "code": item.sku,
                "name": item.name,
                "unit": item.unit,
                "description": row.description,
            }
        )
    return rows


def _post_direct_journal(
    db: Session, receipt: WarehouseReceipt, rows: list[dict], user: User
) -> None:
    """سندِ حسابداریِ رسیدِ مستقیم (§۳۴ §۳۵ §۳۶).

    **فقط برای رسیدِ مستقیم.** رسیدی که به فاکتور گره خورده هیچ سندی نمی‌زند،
    چون فاکتور بدهی را از قبل شناخته و ثبتِ دوباره یعنی حسابِ تأمین‌کننده دو
    برابر شود (§۳۷).

    یک رسید می‌تواند **چند ردیفِ سند** بسازد (§۳۵): موجودیِ هر انبار حسابِ
    خودش را دارد و خدمت به حسابِ هزینه می‌نشیند — همان تفکیکی که فاکتورِ خرید
    هم دارد، از همان سرویس. حساب‌ها با `system_role` حل می‌شوند نه با کد یا نام
    (§۳۶).
    """
    total = sum((row["qty"] * row["unit_cost"] for row in rows), Decimal(0))
    if total <= 0:
        #: رسیدِ مستقیمِ بی‌بها (مثلاً ورودِ امانی) سندِ صفر نمی‌سازد — سندِ خالی
        #: چیزی توضیح نمی‌دهد و فقط دفتر را شلوغ می‌کند.
        return

    inventory_account_id = warehouses_svc.inventory_account_id(db, receipt.warehouse_id)
    debit_by_account: dict[UUID, Decimal] = {}
    for row in rows:
        account_id = items_svc.purchase_account_id(
            db, row["item"], inventory_account_id=inventory_account_id
        )
        debit_by_account[account_id] = debit_by_account.get(account_id, Decimal(0)) + (
            row["qty"] * row["unit_cost"]
        )

    #: طرفِ بستانکار: اگر تحویل‌دهنده‌ای نام برده شده، بدهی به اوست؛ وگرنه نقد.
    #: همان قاعده‌ای که `post_purchase_invoice` دارد — دو موتور یک تصمیم را دو
    #: جور نمی‌گیرند.
    credit_account = (
        get_account(db, cc.ACCOUNTS_PAYABLE) if receipt.contact_id else get_account(db, cc.CASH)
    )
    lines = [
        JournalLine(
            account_id=account_id,
            debit=amount,
            credit=0,
            description=(
                "بابت ورود کالا" if account_id == inventory_account_id else "بابت ورود خدمت"
            ),
        )
        for account_id, amount in debit_by_account.items()
    ]
    lines.append(
        JournalLine(
            account_id=credit_account.id,
            debit=0,
            credit=total,
            description=f"بابت رسید انبار شماره {receipt.number}",
        )
    )
    entry = make_journal_entry(
        db,
        receipt.receipt_date,
        f"رسید انبار شماره {receipt.number} ({RECEIPT_TYPE_LABELS[receipt.receipt_type]})",
        "warehouse_receipt",
        user,
        lines,
    )
    receipt.journal_entry_id = entry.id


def _reclassified_so_far(db: Session, invoice_line_id: UUID) -> Decimal:
    """چقدر از این ردیفِ فاکتور قبلاً از «کالای در راه» خارج شده.

    از خودِ ردیف‌های رسید مشتق می‌شود (مقدار × بهای واحد)، نه از یک ستونِ
    جداگانه — همان قاعده‌ی «مشتق بهتر از ذخیره».
    """
    rows = (
        db.query(WarehouseReceiptLine.qty, WarehouseReceiptLine.unit_cost)
        .join(WarehouseReceipt, WarehouseReceipt.id == WarehouseReceiptLine.receipt_id)
        .filter(
            WarehouseReceiptLine.purchase_invoice_line_id == invoice_line_id,
            WarehouseReceipt.voided_at.is_(None),
            WarehouseReceipt.status == "posted",
        )
        .all()
    )
    return sum((Decimal(qty) * Decimal(unit_cost) for qty, unit_cost in rows), Decimal(0))


def _post_reclassification(
    db: Session,
    receipt: WarehouseReceipt,
    invoice: PurchaseInvoice,
    rows: list[dict],
    user: User,
) -> None:
    """کالا از «در راه» به «موجودیِ انبار» منتقل می‌شود (§۳۴).

    **این شناساییِ تازه نیست، طبقه‌بندیِ دوباره است.** دارایی از بین نرفته؛ فقط
    محلش عوض شده. بدهیِ تأمین‌کننده دست نمی‌خورد، پس §۳۷ نقض نمی‌شود — همان
    الگویی که «چک‌های واگذارشده به بانک» دارد.

    **فاکتورهای پیش از این تغییر دست‌نخورده می‌مانند.** آن‌ها مستقیماً «موجودی
    کالا» را بدهکار کرده‌اند؛ اگر رسیدشان حالا دوباره موجودی را بدهکار کند،
    موجودیِ دفتری دو برابر می‌شود. `invoice.goods_in_transit` همین را می‌گوید.
    """
    if not invoice.goods_in_transit:
        return

    inventory_account_id = warehouses_svc.inventory_account_id(db, receipt.warehouse_id)
    transit_account = goods_in_transit_account(db)
    total = Decimal(0)
    for row in rows:
        if row["item"].is_service:
            #: خدمت هرگز در راه نبوده — همان لحظه‌ی فاکتور هزینه شده.
            continue
        line = db.get(PurchaseInvoiceLine, row["purchase_invoice_line_id"])
        line_net = (
            Decimal(line.qty) * Decimal(line.unit_cost)
            - Decimal(line.discount)
            + Decimal(line.addition)
            + Decimal(line.duty_amount)
        )
        moved = Decimal(row["qty"]) * Decimal(row["unit_cost"])
        #: **آخرین تحویلِ یک ردیف، ته‌مانده را هم می‌برد.** بهای واحد عددِ صحیحِ
        #: گردشده است، پس جمعِ «مقدار × بها» لزوماً با خالصِ ردیف برابر نمی‌شود
        #: و چند ریال در «کالای در راه» جا می‌ماند — حسابی که باید صفر شود و
        #: هرگز نمی‌شد.
        before = _reclassified_so_far(db, line.id) - moved
        if Decimal(row["qty"]) + _received_before(db, line.id, receipt.id) >= Decimal(line.qty):
            moved = line_net - before
        if moved <= 0:
            continue
        total += moved

    if total <= 0:
        return

    entry = make_journal_entry(
        db,
        receipt.receipt_date,
        f"رسید انبار شماره {receipt.number} — ورود کالای در راه به انبار",
        "warehouse_receipt",
        user,
        [
            JournalLine(
                account_id=inventory_account_id,
                debit=total,
                credit=0,
                description=f"ورود کالا با رسید انبار شماره {receipt.number}",
            ),
            JournalLine(
                account_id=transit_account.id,
                debit=0,
                credit=total,
                description=f"خروج از کالای در راه (فاکتور خرید {invoice.number})",
            ),
        ],
    )
    receipt.journal_entry_id = entry.id


def _received_before(db: Session, invoice_line_id: UUID, exclude_receipt_id: UUID) -> Decimal:
    rows = (
        db.query(func.coalesce(func.sum(WarehouseReceiptLine.qty), 0))
        .join(WarehouseReceipt, WarehouseReceipt.id == WarehouseReceiptLine.receipt_id)
        .filter(
            WarehouseReceiptLine.purchase_invoice_line_id == invoice_line_id,
            WarehouseReceipt.id != exclude_receipt_id,
            WarehouseReceipt.voided_at.is_(None),
            WarehouseReceipt.status == "posted",
        )
        .scalar()
    )
    return Decimal(rows or 0)


def create_warehouse_receipt(
    db: Session, invoice_id: UUID | None, data: WarehouseReceiptIn, user: User
) -> WarehouseReceipt:
    """رسیدِ انبار — گره‌خورده به فاکتور یا مستقیم (§۹).

    `invoice_id` می‌تواند از مسیرِ URL بیاید (گردشِ قدیمی) یا از خودِ بدنه.
    """
    assert_period_open(db, data.receipt_date)
    invoice_id = invoice_id if invoice_id is not None else data.purchase_invoice_id
    invoice = _resolve_invoice(db, invoice_id)

    #: انبارِ غیرفعال کالا نمی‌پذیرد — همان گاردِ مشترکِ فصلِ انبار، نه یک
    #: بررسیِ محلیِ دوباره.
    warehouses_svc.assert_usable(db, data.warehouse_id, action="رسید انبار")

    if data.receipt_type not in RECEIPT_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوعِ رسید نامعتبر است")
    if data.contact_id is not None and db.get(Contact, data.contact_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تحویل‌دهنده معتبر نیست")

    rows = (
        _invoice_backed_lines(db, invoice, data)
        if invoice is not None
        else _direct_lines(db, data)
    )

    #: §۲۹ — کالا فقط به انبارهای مرتبطش وارد می‌شود. فهرستِ خالی یعنی «همه».
    for row in rows:
        items_svc.assert_warehouse_allowed(db, row["item"], data.warehouse_id)

    lock_items(db, [row["item"].id for row in rows if not row["item"].is_service])

    receipt = WarehouseReceipt(
        number=next_document_number(db, DOC_WAREHOUSE_RECEIPT),
        receipt_date=data.receipt_date,
        purchase_invoice_id=invoice.id if invoice is not None else None,
        warehouse_id=data.warehouse_id,
        receipt_type=data.receipt_type,
        contact_id=data.contact_id if invoice is None else (data.contact_id or invoice.contact_id),
        carrier_id=data.carrier_id,
        freight_agent_id=data.freight_agent_id,
        currency_code=data.currency_code,
        exchange_rate=data.exchange_rate,
        description=data.description.strip(),
        description2=data.description2.strip(),
        created_by_id=user.id,
    )
    db.add(receipt)
    db.flush()

    for index, row in enumerate(rows, start=1):
        item = row["item"]
        receipt.lines.append(
            WarehouseReceiptLine(
                purchase_invoice_line_id=row["purchase_invoice_line_id"],
                item_id=item.id,
                qty=row["qty"],
                unit_cost=row["unit_cost"],
                item_code_snapshot=row["code"],
                item_name_snapshot=row["name"],
                unit_snapshot=row["unit"],
                description=row["description"],
            )
        )
        if item.is_service:
            continue
        old_qty = get_total_stock_qty(db, item.id)
        new_qty = old_qty + row["qty"]
        if new_qty > 0:
            item.average_cost = (
                (old_qty * Decimal(item.average_cost)) + row["qty"] * row["unit_cost"]
            ) / new_qty
        db.add(
            StockLedger(
                item_id=item.id,
                warehouse_id=data.warehouse_id,
                qty=row["qty"],
                unit_cost=row["unit_cost"],
                entry_date=data.receipt_date,
                source_type="warehouse_receipt",
                source_id=receipt.id,
            )
        )
        db.add(
            StockBatch(
                item_id=item.id,
                warehouse_id=data.warehouse_id,
                batch_number=f"WR{receipt.number}-{index}",
                qty=row["qty"],
                received_qty=row["qty"],
                unit_cost=row["unit_cost"],
                source_type="warehouse_receipt",
                source_id=receipt.id,
                received_date=data.receipt_date,
                notes=data.description.strip(),
                created_by_id=user.id,
            )
        )

    #: **این‌جا نقطه‌ی ثبت تصمیم می‌گیرد (§۳۷).** رسیدِ گره‌خورده به فاکتور سند
    #: نمی‌زند چون فاکتور بدهی را شناخته؛ رسیدِ مستقیم می‌زند چون هیچ سندِ
    #: دیگری این خرید را نمی‌شناسد.
    if invoice is None:
        _post_direct_journal(db, receipt, rows, user)
    else:
        _post_reclassification(db, receipt, invoice, rows, user)

    db.flush()
    db.refresh(receipt)
    return receipt


def void_warehouse_receipt(
    db: Session, receipt_id: UUID, *, reason: str, user: User, void_date: date | None = None
) -> WarehouseReceipt:
    receipt = db.get(WarehouseReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "رسید انبار یافت نشد")
    if receipt.is_voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "این رسید قبلاً باطل شده است")
    effective_date = void_date or receipt.receipt_date
    assert_period_open(db, effective_date)
    moves = db.query(StockLedger).filter(
        StockLedger.source_type == "warehouse_receipt", StockLedger.source_id == receipt.id
    ).all()
    lock_items(db, [move.item_id for move in moves])
    for move in moves:
        current = Decimal(
            db.query(func.coalesce(func.sum(StockLedger.qty), 0))
            .filter(StockLedger.item_id == move.item_id, StockLedger.warehouse_id == move.warehouse_id)
            .scalar()
        )
        if current - Decimal(move.qty) < 0:
            raise HTTPException(status.HTTP_409_CONFLICT, "ابطال رسید، موجودی انبار را منفی می‌کند")
        db.add(
            StockLedger(
                item_id=move.item_id,
                warehouse_id=move.warehouse_id,
                qty=-Decimal(move.qty),
                unit_cost=move.unit_cost,
                entry_date=effective_date,
                source_type="void",
                source_id=receipt.id,
            )
        )
    #: **سند هم باید برگردد، نه فقط موجودی.**
    #:
    #: تا وقتی رسید سند نمی‌زد، ابطالش فقط کارِ انبار بود. حالا که رسیدِ مستقیم
    #: بدهی می‌شناسد و رسیدِ فاکتوردار کالا را از «در راه» خارج می‌کند، ابطالِ
    #: بی‌برگشتِ سند یعنی دفتر و انبار از هم جدا بیفتند: کالا برمی‌گردد ولی
    #: مبلغش در دفتر می‌ماند.
    if receipt.journal_entry_id is not None:
        entry = db.get(JournalEntry, receipt.journal_entry_id)
        if entry is not None:
            reverse_journal_entry(
                db,
                entry,
                void_date=effective_date,
                user=user,
                description=f"ابطال رسید انبار شماره {receipt.number}",
            )

    receipt.voided_at = datetime.now(timezone.utc)
    receipt.voided_by_id = user.id
    receipt.void_reason = reason.strip()
    receipt.status = "voided"
    db.flush()
    for item_id in {move.item_id for move in moves}:
        item = db.get(Item, item_id)
        if item is not None:
            recompute_average_cost(db, item)
    return receipt
