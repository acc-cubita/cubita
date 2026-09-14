"""اجرای «قیمت‌گذاری اسناد انبار» — محاسبه، پیش‌نمایش، ثبتِ سندِ اصلاحی و ابطال (نوبتِ دومِ فصل).

**محاسبه چیزی نمی‌نویسد.** بازپخشِ `valuation` برای کالاهای دامنه اجرا می‌شود و هر حرکتِ
منقضی (بهای ثبت‌شده‌اش با بازپخشِ زمانی نمی‌خواند) با بهای قبل و بعد، اثرِ ریالی و طرفِ
مقابلِ سندش در پیش‌نمایش می‌آید.

**پیش‌بررسیِ موجودیِ منفی.** میانگینِ موزون روی موجودیِ منفی تعریف ندارد؛ کالایی که در
یک انبار جایی از خطِ زمان منفی است، کلِ اجرا را متوقف می‌کند و پیش‌نمایش می‌گوید کجا.

**ثبت = یک سندِ اصلاحی.** هر اصلاح دو پا دارد: معینِ موجودیِ انبارِ حرکت، و همان حسابی که
حرکتِ اصلی خورده بود — حسابِ ردیفِ خروج (بهای تمام‌شده یا هزینه‌ی مصرف)، حسابِ ردیفِ برگشتِ
خروج، مغایرتِ انبار برای تعدیل و انبارگردانی. دو سرِ یک انتقال طرفِ مقابل ندارند و هم را
می‌پوشانند. پاها روی (حساب، مرکز هزینه) جمع می‌شوند، پس سند از ساختار متوازن است.

**ثبت روی داده‌ی کهنه رد می‌شود.** پیش‌نمایش توکنِ دفتر را برمی‌گرداند (بزرگ‌ترین `seq`ِ
کالاهای دامنه و شمارِ اجراها)؛ اگر از آن لحظه سندی ثبت یا باطل شده باشد، ثبت ۴۰۹ می‌گیرد.
کالاهای دامنه پیش از محاسبه‌ی دوباره قفل می‌شوند تا میانِ محاسبه و نوشتن چیزی عوض نشود.

**اجرای دوباره بی‌اثر است.** پس از ثبت، بهای فعالِ حرکات همان بازپخش است؛ محاسبه‌ی دوباره
هیچ حرکتِ منقضی‌ای نمی‌یابد و ثبت با «چیزی برای اصلاح نیست» رد می‌شود.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from itertools import groupby
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.counters import DOC_INVENTORY_VALUATION
from app.models.inventory import Item, StockLedger, Warehouse
from app.models.inventory_valuation import InventoryValuationAdjustment, InventoryValuationRun
from app.models.invoices import WarehouseIssue, WarehouseIssueLine
from app.models.issue_returns import WarehouseIssueReturnLine
from app.models.user import User
from app.services import chart_codes as cc
from app.services import valuation, warehouses
from app.services.common import get_account, make_journal_entry
from app.services.inventory import lock_items
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open
from app.services.voiding import reverse_journal_entry

#: پیش‌نمایش حداکثر این تعداد حرکت را فهرست می‌کند؛ جمع‌ها و سند همیشه از همه‌ی حرکات‌اند.
PREVIEW_MOVE_LIMIT = 300

#: حرکتِ منقضی‌ای که این نوبت اصلاح نمی‌کند — نشان داده می‌شود، نه بی‌صدا کنار گذاشته.
_SKIP_REASONS = {
    "production": (
        "مصرفِ تولید بهایش را به محصولِ نهایی داده؛ اصلاحش بهای محصول را هم جابه‌جا می‌کند، "
        "که این نوبت نمی‌سازد."
    ),
}
#: طرفِ مقابلِ سندِ اصلاحی برای حرکاتی که حسابِ ردیف ندارند.
_ROLE_COUNTERS = {
    "adjustment": cc.INVENTORY_ADJUSTMENT,
    "stock_count": cc.INVENTORY_ADJUSTMENT,
    "sales_invoice": cc.COGS,
}
_LINE_COUNTERS = ("warehouse_issue", "warehouse_issue_return")
_TRANSFERS = ("transfer_in", "transfer_out")


def _scope_items(db: Session, warehouse_id: UUID | None, item_id: UUID | None) -> list[UUID]:
    """کالاهای دامنه. انبار فقط کالا انتخاب می‌کند: میانگین مالِ کلِ شرکت است."""
    if item_id is not None:
        if db.get(Item, item_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "کالا یافت نشد")
        return [item_id]
    query = db.query(StockLedger.item_id).distinct()
    if warehouse_id is not None:
        if db.get(Warehouse, warehouse_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "انبار یافت نشد")
        query = query.filter(StockLedger.warehouse_id == warehouse_id)
    return sorted({row_item for (row_item,) in query.all()}, key=str)


def ledger_token(db: Session, item_ids: list[UUID]) -> str:
    """وضعیتِ دفتر برای کالاهای دامنه — هر چیزی که پیش‌نمایش را عوض می‌کند.

    `seq` ثبت و ابطالِ اسناد را می‌گیرد؛ **جمعِ ارزش** قیمت‌گذاریِ ورودی‌های بی‌فی را
    (`production_pricing` فیِ همان ردیفِ دفتر را پر می‌کند و ردیفِ تازه نمی‌سازد، پس `seq`
    تکان نمی‌خورد)؛ و شمارِ اجراها اجرای ثبت‌شده یا باطل‌شده‌ی دیگر را.
    """
    seq, value = 0, 0
    if item_ids:
        seq, value = (
            db.query(
                func.coalesce(func.max(StockLedger.seq), 0),
                func.coalesce(func.sum(StockLedger.qty * StockLedger.unit_cost), 0),
            )
            .filter(StockLedger.item_id.in_(item_ids))
            .one()
        )
    total, voided = db.query(
        func.count(InventoryValuationRun.id), func.count(InventoryValuationRun.voided_at)
    ).one()
    return f"{seq}.{Decimal(value).normalize():f}.{total}.{voided}"


def _line_counters(db: Session, item_ids: list[UUID]) -> dict[UUID, tuple[UUID | None, UUID | None]]:
    """حرکتِ خروج/برگشتِ خروج ← (حسابِ ردیف، مرکز هزینه) — همان حسابی که سندِ اصلی خورد."""
    out: dict[UUID, tuple[UUID | None, UUID | None]] = {}
    issue_moves = valuation.moves_by_line(
        db, source_type="warehouse_issue", line_model=WarehouseIssueLine,
        parent_column=WarehouseIssueLine.issue_id, item_ids=item_ids,
    )
    if issue_moves:
        for line_id, account_id, cost_center_id in (
            db.query(WarehouseIssueLine.id, WarehouseIssueLine.account_id, WarehouseIssue.cost_center_id)
            .join(WarehouseIssue, WarehouseIssue.id == WarehouseIssueLine.issue_id)
            .filter(WarehouseIssueLine.id.in_(list(issue_moves)))
            .all()
        ):
            out[issue_moves[line_id]] = (account_id, cost_center_id)
    return_moves = valuation.moves_by_line(
        db, source_type="warehouse_issue_return", line_model=WarehouseIssueReturnLine,
        parent_column=WarehouseIssueReturnLine.return_id, item_ids=item_ids,
    )
    if return_moves:
        for line_id, account_id, cost_center_id in (
            db.query(
                WarehouseIssueReturnLine.id, WarehouseIssueReturnLine.account_id,
                WarehouseIssueReturnLine.cost_center_id,
            )
            .filter(WarehouseIssueReturnLine.id.in_(list(return_moves)))
            .all()
        ):
            out[return_moves[line_id]] = (account_id, cost_center_id)
    return out


def calculate(
    db: Session,
    *,
    date_from: date | None,
    date_to: date,
    warehouse_id: UUID | None = None,
    item_id: UUID | None = None,
) -> dict:
    """پیش‌نمایشِ اجرا — هیچ‌چیز نمی‌نویسد. کلیدهای `_`دار فقط برای `commit_run`اند."""
    if date_from is not None and date_from > date_to:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "«از تاریخ» بعد از «تا تاریخ» است.")
    item_ids = _scope_items(db, warehouse_id, item_id)
    token = ledger_token(db, item_ids)
    voided, active, sources = valuation.context(db, item_ids) if item_ids else (set(), {}, {})
    rows = valuation.ledger_rows(db, item_ids=item_ids, until=date_to) if item_ids else []
    counters = _line_counters(db, item_ids) if item_ids else {}

    role_accounts: dict[str, UUID] = {}
    inventory_accounts: dict[UUID, UUID] = {}

    def role_account(role: str) -> UUID:
        if role not in role_accounts:
            role_accounts[role] = get_account(db, role).id
        return role_accounts[role]

    def inventory_account(warehouse: UUID) -> UUID:
        if warehouse not in inventory_accounts:
            inventory_accounts[warehouse] = warehouses.inventory_account_id(db, warehouse)
        return inventory_accounts[warehouse]

    negatives: list[dict] = []
    adjustments: list[dict] = []
    skipped: list[dict] = []
    for item, group in groupby(rows, key=lambda row: row.item_id):
        valued = valuation.replay(list(group), voided, active, sources)

        running: dict[UUID, Decimal] = defaultdict(Decimal)
        flagged: set[UUID] = set()
        for move in valued:
            if move.voided:
                continue
            row = move.row
            running[row.warehouse_id] += move.qty
            if running[row.warehouse_id] < 0 and row.warehouse_id not in flagged:
                flagged.add(row.warehouse_id)
                negatives.append({
                    "item_id": item, "warehouse_id": row.warehouse_id, "entry_date": row.entry_date,
                    "qty": running[row.warehouse_id], "source_type": row.source_type, "source_id": row.source_id,
                })

        for move in valued:
            if not move.stale:
                continue
            row = move.row
            if date_from is not None and row.entry_date < date_from:
                continue
            reason = _SKIP_REASONS.get(row.source_type)
            if reason is None and row.source_type not in (*_LINE_COUNTERS, *_TRANSFERS, *_ROLE_COUNTERS):
                reason = "برای این نوع حرکت قاعده‌ی سندِ اصلاحی تعریف نشده است."
            if reason is not None:
                skipped.append({
                    "item_id": item, "entry_date": row.entry_date, "source_type": row.source_type,
                    "source_id": row.source_id, "qty": move.qty, "reason": reason,
                })
                continue
            if row.source_type in _LINE_COUNTERS:
                counter_id, cost_center_id = counters.get(row.id, (None, None))
                #: ردیفِ خروجِ پیش از ۰۱۳۳ حساب ندارد و همیشه بهای تمام‌شده را بدهکار کرده بود.
                counter_id = counter_id or role_account(cc.COGS)
            elif row.source_type in _TRANSFERS:
                counter_id, cost_center_id = None, None
            else:
                counter_id, cost_center_id = role_account(_ROLE_COUNTERS[row.source_type]), None
            adjustments.append({
                "stock_ledger_id": row.id,
                "item_id": item,
                "warehouse_id": row.warehouse_id,
                "entry_date": row.entry_date,
                "source_type": row.source_type,
                "source_id": row.source_id,
                "qty": move.qty,
                "previous_cost": move.booked,
                "new_cost": move.cost,
                #: اختلافِ دو مبلغِ ریالی، نه ریالِ اختلافِ بها: سندِ اصلی هم «مقدار × بها» را
                #: به ریالِ صحیح زده بود. گِردکردنِ متقارن دو سرِ انتقال را دقیقاً قرینه می‌گذارد.
                "value_delta": valuation.rial(move.qty * move.cost) - valuation.rial(move.qty * move.booked),
                "inventory_account_id": inventory_account(row.warehouse_id),
                "counter_account_id": counter_id,
                "cost_center_id": cost_center_id,
            })

    net: dict[tuple[UUID, UUID | None], Decimal] = defaultdict(Decimal)
    for adjustment in adjustments:
        net[(adjustment["inventory_account_id"], None)] += adjustment["value_delta"]
        if adjustment["counter_account_id"] is not None:
            net[(adjustment["counter_account_id"], adjustment["cost_center_id"])] -= adjustment["value_delta"]
    lines = [(account_id, cost_center_id, amount) for (account_id, cost_center_id), amount in net.items() if amount != 0]
    if sum((amount for _, _, amount in lines), Decimal(0)) != 0:
        #: از ساختار ناممکن است؛ اگر روزی رخ دهد، ثبتِ سندِ نامتوازن بدتر از خطاست.
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "سندِ اصلاحی متوازن نشد؛ ثبت انجام نمی‌شود.")

    return _present(db, {
        "date_from": date_from,
        "date_to": date_to,
        "warehouse_id": warehouse_id,
        "item_id": item_id,
        "token": token,
        "blocked": bool(negatives),
        "_negatives": negatives,
        "_adjustments": adjustments,
        "_skipped": skipped,
        "_lines": lines,
    })


def _present(db: Session, plan: dict) -> dict:
    """نام‌ها و شماره‌ها برای نمایش — یک کوئری برای هر نوع، نه برای هر ردیف."""
    adjustments, negatives, skipped = plan["_adjustments"], plan["_negatives"], plan["_skipped"]
    item_ids = {entry["item_id"] for entry in (*adjustments, *negatives, *skipped)}
    items = (
        {item.id: item for item in db.query(Item).filter(Item.id.in_(item_ids)).all()} if item_ids else {}
    )
    warehouse_names = dict(db.query(Warehouse.id, Warehouse.name).all())
    account_ids = {account_id for account_id, _, _ in plan["_lines"]} | {
        entry["counter_account_id"] for entry in adjustments if entry["counter_account_id"]
    }
    accounts = (
        {account.id: account for account in db.query(Account).filter(Account.id.in_(account_ids)).all()}
        if account_ids
        else {}
    )
    numbers = valuation.document_numbers(
        db, {(entry["source_type"], entry["source_id"]) for entry in (*adjustments, *negatives, *skipped)}
    )

    def item_name(item_id: UUID) -> str:
        item = items.get(item_id)
        return item.name if item is not None else ""

    def source(entry: dict) -> dict:
        number = numbers.get((entry["source_type"], entry["source_id"]))
        return {
            "source_type": entry["source_type"],
            "source_label": valuation.SOURCE_LABELS.get(entry["source_type"], entry["source_type"]),
            "source_number": number,
        }

    by_item: dict[UUID, dict] = {}
    for entry in adjustments:
        summary = by_item.setdefault(entry["item_id"], {
            "item_id": entry["item_id"],
            "sku": items[entry["item_id"]].sku if entry["item_id"] in items else "",
            "name": item_name(entry["item_id"]),
            "move_count": 0,
            "value_delta": Decimal(0),
            "from_date": entry["entry_date"],
        })
        summary["move_count"] += 1
        summary["value_delta"] += entry["value_delta"]
        summary["from_date"] = min(summary["from_date"], entry["entry_date"])

    moves = [
        {
            "stock_ledger_id": entry["stock_ledger_id"],
            "item_id": entry["item_id"],
            "item_name": item_name(entry["item_id"]),
            "entry_date": entry["entry_date"],
            **source(entry),
            "warehouse_name": warehouse_names.get(entry["warehouse_id"], ""),
            "qty": entry["qty"],
            "previous_cost": entry["previous_cost"],
            "new_cost": entry["new_cost"],
            "value_delta": entry["value_delta"],
            "counter_account_name": (
                f"{accounts[entry['counter_account_id']].code} — {accounts[entry['counter_account_id']].name}"
                if entry["counter_account_id"] in accounts
                else ""
            ),
        }
        for entry in sorted(adjustments, key=lambda e: (e["entry_date"], item_name(e["item_id"])))
    ]
    plan.update({
        "negatives": [
            {
                "item_id": entry["item_id"],
                "item_name": item_name(entry["item_id"]),
                "warehouse_name": warehouse_names.get(entry["warehouse_id"], ""),
                "entry_date": entry["entry_date"],
                "qty": entry["qty"],
                **source(entry),
            }
            for entry in negatives
        ],
        "items": sorted(by_item.values(), key=lambda s: s["name"]),
        "moves": moves[:PREVIEW_MOVE_LIMIT],
        "moves_truncated": len(moves) > PREVIEW_MOVE_LIMIT,
        "accounts": sorted(
            (
                {
                    "account_id": account_id,
                    "code": accounts[account_id].code if account_id in accounts else "",
                    "name": accounts[account_id].name if account_id in accounts else "",
                    "debit": amount if amount > 0 else Decimal(0),
                    "credit": -amount if amount < 0 else Decimal(0),
                }
                for account_id, _cost_center_id, amount in plan["_lines"]
            ),
            key=lambda row: row["code"],
        ),
        "skipped": [
            {"item_name": item_name(entry["item_id"]), "entry_date": entry["entry_date"], "qty": entry["qty"],
             "reason": entry["reason"], **source(entry)}
            for entry in skipped
        ],
        "move_count": len(adjustments),
        "item_count": len(by_item),
        "total_delta": sum((entry["value_delta"] for entry in adjustments), Decimal(0)),
    })
    return plan


def commit_run(db: Session, data, user: User) -> InventoryValuationRun:
    assert_period_open(db, data.date_to)
    item_ids = _scope_items(db, data.warehouse_id, data.item_id)
    #: قفل پیش از محاسبه‌ی دوباره: میانِ محاسبه و نوشتن، سندی روی همین کالاها ثبت نشود.
    lock_items(db, item_ids)
    plan = calculate(
        db, date_from=data.date_from, date_to=data.date_to, warehouse_id=data.warehouse_id, item_id=data.item_id
    )
    if plan["token"] != data.token:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "از زمانِ محاسبه، سندی روی کالاهای این دامنه ثبت یا باطل شده یا اجرای دیگری ثبت شده است؛ "
            "دوباره «محاسبه» بزنید و پیش‌نمایشِ تازه را ببینید.",
        )
    if plan["blocked"]:
        first = plan["negatives"][0]
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"موجودیِ «{first['item_name']}» در «{first['warehouse_name']}» در تاریخِ "
            f"{valuation._jalali(first['entry_date'])} منفی است؛ میانگینِ موزون روی موجودیِ منفی تعریف ندارد. "
            "اول آن را اصلاح کنید یا این کالا را از دامنه بیرون بگذارید.",
        )
    adjustments = plan["_adjustments"]
    if not adjustments:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "در این دامنه حرکتِ منقضی‌ای نیست؛ سندِ اصلاحی لازم نیست."
        )

    number = next_document_number(db, DOC_INVENTORY_VALUATION)
    description = (data.description or "").strip()
    run = InventoryValuationRun(
        number=number,
        date_from=data.date_from,
        date_to=data.date_to,
        warehouse_id=data.warehouse_id,
        item_id=data.item_id,
        description=description,
        ledger_token=plan["token"],
        move_count=plan["move_count"],
        item_count=plan["item_count"],
        total_delta=plan["total_delta"],
        created_by_id=user.id,
    )
    db.add(run)
    db.flush()

    if plan["_lines"]:
        entry = make_journal_entry(
            db,
            data.date_to,
            f"قیمت‌گذاری اسناد انبار شماره {number}" + (f" — {description}" if description else ""),
            "inventory_valuation",
            user,
            [
                JournalLine(
                    account_id=account_id,
                    cost_center_id=cost_center_id,
                    debit=amount if amount > 0 else Decimal(0),
                    credit=-amount if amount < 0 else Decimal(0),
                    description="اصلاحِ بهای حرکاتِ انبار",
                )
                for account_id, cost_center_id, amount in plan["_lines"]
            ],
        )
        entry.source_id = run.id
        run.journal_entry_id = entry.id

    for adjustment in adjustments:
        db.add(InventoryValuationAdjustment(run_id=run.id, **adjustment))
    db.flush()
    #: برگشتِ خروج بهایش را از خروج می‌گیرد؛ اصلاحِ خروج میانگینِ کالا را هم جابه‌جا می‌کند.
    valuation.settle_void(db, {adjustment["item_id"] for adjustment in adjustments})
    db.refresh(run)
    return run


def void_run(
    db: Session, run_id: UUID, *, reason: str, user: User, void_date: date | None = None
) -> InventoryValuationRun:
    """ابطالِ اجرا: سندِ اصلاحی معکوس و اصلاح‌ها غیرفعال — بهای فعال به قبل از اجرا برمی‌گردد.

    **فقط آخرین اجرای باطل‌نشده.** اصلاحِ اجرای بعدی «بهای قبلی»اش را از همین اجرا گرفته؛
    ابطالِ این یکی سندش را برمی‌گرداند ولی بهای فعال همان اجرای بعدی می‌ماند، و دفتر و
    انبار دقیقاً به اندازه‌ی سندِ برگشته از هم جدا می‌افتادند.
    """
    run = (
        db.query(InventoryValuationRun)
        .filter(InventoryValuationRun.id == run_id)
        .with_for_update()
        .one_or_none()
    )
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اجرای قیمت‌گذاری یافت نشد")
    if run.voided_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این اجرا قبلاً باطل شده است")
    later = (
        db.query(InventoryValuationRun.number)
        .filter(InventoryValuationRun.voided_at.is_(None), InventoryValuationRun.number > run.number)
        .order_by(InventoryValuationRun.number.desc())
        .first()
    )
    if later is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"اجرای شماره {later.number} بعد از این ثبت شده است؛ ابطال فقط از آخرین اجرا ممکن است. "
            "اول اجراهای بعدی را باطل کنید.",
        )
    effective = void_date or run.date_to
    assert_period_open(db, effective)
    item_ids = sorted({adjustment.item_id for adjustment in run.adjustments}, key=str)
    lock_items(db, item_ids)
    if run.journal_entry_id is not None:
        entry = db.get(JournalEntry, run.journal_entry_id)
        if entry is not None:
            reversal = reverse_journal_entry(
                db, entry, void_date=effective, user=user,
                description=f"ابطال قیمت‌گذاری اسناد انبار شماره {run.number}"
                + (f" — {reason.strip()}" if reason.strip() else ""),
            )
            run.void_entry_id = reversal.id
    run.voided_at = datetime.now(timezone.utc)
    run.voided_by_id = user.id
    run.void_reason = reason.strip()
    db.flush()
    valuation.settle_void(db, item_ids)
    db.refresh(run)
    return run


def run_outs(db: Session, runs: list[InventoryValuationRun]) -> list[dict]:
    if not runs:
        return []
    latest = (
        db.query(func.max(InventoryValuationRun.number)).filter(InventoryValuationRun.voided_at.is_(None)).scalar()
    )
    entry_ids = {run.journal_entry_id for run in runs if run.journal_entry_id} | {
        run.void_entry_id for run in runs if run.void_entry_id
    }
    entries = dict(db.query(JournalEntry.id, JournalEntry.number).filter(JournalEntry.id.in_(entry_ids)).all()) if entry_ids else {}
    user_ids = {run.created_by_id for run in runs} | {run.voided_by_id for run in runs if run.voided_by_id}
    users = {user.id: user for user in db.query(User).filter(User.id.in_(user_ids)).all()}
    warehouse_names = dict(db.query(Warehouse.id, Warehouse.name).all())
    item_ids = {run.item_id for run in runs if run.item_id}
    item_names = dict(db.query(Item.id, Item.name).filter(Item.id.in_(item_ids)).all()) if item_ids else {}

    def user_name(user_id: UUID | None) -> str:
        user = users.get(user_id)
        if user is None:
            return ""
        return getattr(user, "full_name", None) or getattr(user, "name", None) or user.email

    return [
        {
            "id": run.id,
            "number": run.number,
            "date_from": run.date_from,
            "date_to": run.date_to,
            "warehouse_id": run.warehouse_id,
            "warehouse_name": warehouse_names.get(run.warehouse_id, "") if run.warehouse_id else "",
            "item_id": run.item_id,
            "item_name": item_names.get(run.item_id, "") if run.item_id else "",
            "description": run.description,
            "move_count": run.move_count,
            "item_count": run.item_count,
            "total_delta": run.total_delta,
            "journal_entry_id": run.journal_entry_id,
            "journal_entry_number": entries.get(run.journal_entry_id),
            "created_at": run.created_at,
            "created_by_name": user_name(run.created_by_id),
            "voided_at": run.voided_at,
            "voided_by_name": user_name(run.voided_by_id),
            "void_reason": run.void_reason,
            "void_entry_number": entries.get(run.void_entry_id),
            "voidable": run.voided_at is None and run.number == latest,
        }
        for run in runs
    ]


def run_detail(db: Session, run_id: UUID) -> dict:
    run = db.get(InventoryValuationRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اجرای قیمت‌گذاری یافت نشد")
    adjustments = [
        {
            "stock_ledger_id": adjustment.stock_ledger_id,
            "item_id": adjustment.item_id,
            "warehouse_id": adjustment.warehouse_id,
            "entry_date": adjustment.entry_date,
            "source_type": adjustment.source_type,
            "source_id": adjustment.source_id,
            "qty": Decimal(adjustment.qty),
            "previous_cost": Decimal(adjustment.previous_cost),
            "new_cost": Decimal(adjustment.new_cost),
            "value_delta": Decimal(adjustment.value_delta),
            "inventory_account_id": adjustment.inventory_account_id,
            "counter_account_id": adjustment.counter_account_id,
            "cost_center_id": adjustment.cost_center_id,
        }
        for adjustment in run.adjustments
    ]
    presented = _present(db, {"_adjustments": adjustments, "_negatives": [], "_skipped": [], "_lines": []})
    return {**run_outs(db, [run])[0], "adjustments": presented["moves"], "adjustments_truncated": presented["moves_truncated"]}
