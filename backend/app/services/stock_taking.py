"""انبارگردانی (شمارش فیزیکی موجودی).

یک لایه‌ی جلسه‌ای بالای تعدیلِ تک‌کالاییِ موجود: کاربر شمارشِ فیزیکی را وارد
می‌کند و در پایان همه‌ی مغایرت‌ها با یک سندِ تجمیعی اعمال می‌شوند. قرارداد
حسابداری همان تعدیلِ تک‌کالایی است: اضافیِ خالص → بدهکارِ موجودی/بستانکارِ مغایرت
انبار؛ کسریِ خالص → برعکس.

**انبارگردانی موجودی را بازنویسی نمی‌کند.** `stock = counted` نوشته نمی‌شود؛
مغایرت یک حرکتِ عادیِ دفترِ موجودی می‌سازد که از همان موتورِ ارزش‌گذاریِ مشترک رد
می‌شود. جلسه یک *مشاهده* است، نه یک حرکت.

## دو تصمیمی که این ماژول را از نسخه‌ی اولش جدا می‌کند

**۱) عکسِ سیستمی در لحظه‌ی *شمارش* گرفته می‌شود، نه لحظه‌ی بازکردنِ جلسه.**

نسخه‌ی اول سرِ ایجادِ جلسه عکس می‌گرفت و شمارش ساعت‌ها بعد انجام می‌شد. نتیجه‌اش
با پروب اثبات شد:

    موجودی ۱۰۰ → جلسه باز شد (عکس = ۱۰۰)
    ۱۰ عدد فروخته شد → موجودیِ واقعی ۹۰
    شمارنده می‌شمارد ۹۰   (درست؛ ده تا واقعاً رفته)
    ثبت → اختلاف = ۹۰ − ۱۰۰ = −۱۰  →  موجودیِ نهایی ۸۰

فروشِ ده‌تایی **دو بار** کم شد. حالا `set_counts` همان لحظه موجودی را از دفتر
بازمی‌خواند، پس مبنای مقایسه همان چیزی است که سیستم *وقتی شمارنده عدد را داد*
باور داشت. حرکتِ بعد از آن لحظه بیرونِ اختلاف می‌ماند — که درست است، چون خودش
در دفتر هست.

**۲) شمارشِ کور.** `counted_qty` دیگر با `system_qty` از پیش پر نمی‌شود.
`NULL` یعنی «هنوز شمرده نشده» و از اختلاف‌گیری کنار می‌ماند؛ صفرِ صریح یعنی
«شمردم، هیچ نبود» و کسریِ واقعی می‌سازد. یکی‌گرفتنِ این دو یعنی جلسه‌ای که
نیمه‌کاره ثبت شود موجودیِ صدها کالای دست‌نخورده را از انبار بیرون بریزد.
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalLine
from app.services import tafsili
from app.models.counters import DOC_JOURNAL_ENTRY, DOC_STOCK_COUNT
from app.models.inventory import Item, StockLedger, Warehouse
from app.models.stock_count import StockCountLine, StockCountSession
from app.models.user import User
from app.services import chart_codes as cc
from app.services import warehouses
from app.services.common import get_account as _get_account
from app.services.common import number_lines
from app.services import valuation
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open


def _live_qty(db: Session, warehouse_id: UUID, item_ids) -> dict:
    """موجودیِ *همین لحظه*ی چند کالا در یک انبار، مستقیم از دفتر.

    تنها تعریفِ «سیستم چه می‌گوید» در این ماژول. هم سرِ ساختِ جلسه صدا زده
    می‌شود و هم سرِ ورودِ شمارش — و دومی است که باگِ دوبارشماری را می‌بندد.
    """
    ids = list(item_ids)
    if not ids:
        return {}
    rows = (
        db.query(StockLedger.item_id, func.coalesce(func.sum(StockLedger.qty), 0))
        .filter(StockLedger.warehouse_id == warehouse_id, StockLedger.item_id.in_(ids))
        .group_by(StockLedger.item_id)
        .all()
    )
    return {item_id: Decimal(qty) for item_id, qty in rows}


def _get_session(db: Session, session_id: UUID) -> StockCountSession:
    session = db.get(StockCountSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "جلسه‌ی انبارگردانی یافت نشد")
    return session


def create_session(
    db: Session,
    warehouse_id: UUID,
    count_date,
    user: User,
    notes: str = "",
    item_ids: list[UUID] | None = None,
) -> StockCountSession:
    """جلسه‌ی تازه می‌سازد.

    **دامنه انتخابی است.** `item_ids` خالی یعنی «هر کالایی که در *همین انبار*
    سابقه‌ی حرکت دارد» — نه کلِ کاتالوگِ کسب‌وکار. کاتالوگِ پنج‌هزارقلمی هر بار
    پنج‌هزار ردیفِ بی‌ربط می‌ساخت و شمارشِ چرخه‌ای (چند قلمِ پرگردش) ممکن نبود.

    عددِ شمارش **پر نمی‌شود** — شمارشِ کور از همین‌جا شروع می‌شود.
    """
    warehouses.assert_usable(db, warehouse_id, action="انبارگردانی")
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "انبار یافت نشد")

    # اجازه‌ی بیش از یک جلسه‌ی بازِ همزمان روی یک انبار داده نمی‌شود — دو شمارشِ موازی
    # روی یک انبار یعنی دو عکسِ متناقض از یک واقعیت.
    existing = (
        db.query(StockCountSession)
        .filter(StockCountSession.warehouse_id == warehouse_id, StockCountSession.status == "open")
        .first()
    )
    if existing is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "یک جلسه‌ی انبارگردانیِ باز برای این انبار وجود دارد")

    query = db.query(Item).filter(Item.is_service.is_(False))
    if item_ids:
        items = query.filter(Item.id.in_(item_ids)).order_by(Item.sku).all()
        found = {item.id for item in items}
        missing = [str(i) for i in item_ids if i not in found]
        if missing:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "کالای انتخاب‌شده یافت نشد یا خدمات است")
    else:
        #: فقط کالاهایی که در همین انبار سابقه‌ی حرکت دارند. کالایی که هرگز به
        #: این انبار نیامده ردیفِ «۰ در برابر ۰» می‌ساخت و فقط فهرست را شلوغ می‌کرد.
        seen = {
            item_id
            for (item_id,) in db.query(StockLedger.item_id)
            .filter(StockLedger.warehouse_id == warehouse_id)
            .distinct()
        }
        items = [item for item in query.order_by(Item.sku).all() if item.id in seen]

    qty_map = _live_qty(db, warehouse_id, [item.id for item in items])

    session = StockCountSession(
        number=next_document_number(db, DOC_STOCK_COUNT),
        warehouse_id=warehouse_id,
        count_date=count_date,
        status="open",
        notes=notes or "",
        created_by_id=user.id,
    )
    for item in items:
        session.lines.append(
            StockCountLine(
                item_id=item.id,
                #: عکسِ اولیه فقط برای نمایش و گزارشِ «چه‌قدر انتظار داریم» است؛
                #: مبنای اختلاف، عکسی است که سرِ ورودِ شمارش گرفته می‌شود.
                system_qty=qty_map.get(item.id, Decimal(0)),
                counted_qty=None,  # شمارشِ کور — عدد از شمارنده می‌آید، نه از سیستم
                unit_cost=item.average_cost,
            )
        )
    db.add(session)
    db.flush()
    db.refresh(session)
    return session


def set_counts(db: Session, session_id: UUID, updates: list, user: User) -> StockCountSession:
    """شمارشِ فیزیکیِ چند ردیف را ثبت می‌کند. فقط روی جلسه‌ی باز مجاز است.

    **این‌جا عکسِ سیستمی هم تازه می‌شود — و همین باگِ دوبارشماری را می‌بندد.**
    مبنای اختلاف باید همان چیزی باشد که سیستم *در لحظه‌ی شمارش* باور داشت، نه
    ساعت‌ها پیش سرِ بازکردنِ جلسه. حرکتی که پس از این لحظه بیفتد بیرونِ اختلاف
    می‌ماند — که درست است، چون خودش در دفتر نشسته.

    `counted_qty = None` یعنی «شمارش را پس بگیر»: ردیف به حالتِ نشمرده برمی‌گردد
    و از اختلاف‌گیری کنار می‌رود.
    """
    session = _get_session(db, session_id)
    if session.status != "open":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فقط جلسه‌ی باز قابل ویرایش است")

    line_map = {line.id: line for line in session.lines}
    touched: list[StockCountLine] = []
    for upd in updates:
        line = line_map.get(upd.line_id)
        if line is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "ردیف انبارگردانی یافت نشد")
        touched.append(line)

    live = _live_qty(db, session.warehouse_id, [line.item_id for line in touched])
    now = datetime.now(timezone.utc)
    for upd, line in zip(updates, touched):
        line.counted_qty = upd.counted_qty
        if upd.counted_qty is None:
            line.counted_at = None
            line.counted_by_id = None
            continue
        line.system_qty = live.get(line.item_id, Decimal(0))
        line.counted_at = now
        line.counted_by_id = user.id

    db.flush()
    db.refresh(session)
    return session


def cancel_session(db: Session, session_id: UUID) -> StockCountSession:
    session = _get_session(db, session_id)
    if session.status != "open":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فقط جلسه‌ی باز قابل لغو است")
    session.status = "cancelled"
    db.flush()
    db.refresh(session)
    return session


def post_session(db: Session, session_id: UUID, user: User) -> StockCountSession:
    """مغایرت‌ها را به دفتر موجودی و یک سندِ تجمیعی اعمال می‌کند و جلسه را می‌بندد."""
    session = _get_session(db, session_id)
    if session.status != "open":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فقط جلسه‌ی باز قابل ثبت است")
    assert_period_open(db, session.count_date)

    counted = [line for line in session.lines if line.counted_qty is not None]
    if not counted:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "هیچ ردیفی شمرده نشده است — جلسه‌ای بی شمارش چیزی برای تطبیق ندارد.",
        )

    #: **ردیفِ نشمرده صفر نیست.** جلسه‌ای که نیمه‌کاره ثبت شود فقط همان چیزی را
    #: تطبیق می‌دهد که واقعاً شمرده شده؛ بقیه دست‌نخورده می‌مانند و در گزارشِ
    #: پوشش دیده می‌شوند.
    total_delta = Decimal(0)  # تغییرِ خالصِ ارزشِ موجودی (علامت‌دار)
    moves: list[StockLedger] = []
    for line in counted:
        variance = Decimal(line.counted_qty) - Decimal(line.system_qty)
        if variance == 0:
            continue
        move = StockLedger(
            item_id=line.item_id,
            warehouse_id=session.warehouse_id,
            qty=variance,
            unit_cost=line.unit_cost,
            entry_date=session.count_date,
            source_type="stock_count",
            source_id=session.id,
        )
        db.add(move)
        moves.append(move)
        total_delta += variance * Decimal(line.unit_cost)
    valuation.settle_posting(db, moves)

    if total_delta != 0:
        amount = abs(total_delta)
        #: سمتِ موجودی معینِ همان انباری است که شمرده شده (§۹).
        inventory_id = warehouses.inventory_account_id(db, session.warehouse_id)
        adjustment_id = _get_account(db, cc.INVENTORY_ADJUSTMENT).id
        if total_delta > 0:  # موجودی خالص زیاد شد (اضافی)
            debit_id, credit_id = inventory_id, adjustment_id
        else:  # موجودی خالص کم شد (کسری)
            debit_id, credit_id = adjustment_id, inventory_id
        entry = JournalEntry(
            number=next_document_number(db, DOC_JOURNAL_ENTRY),
            entry_date=session.count_date,
            description=f"انبارگردانی انبار «{session.warehouse.name}»",
            source_type="stock_count",
            created_by_id=user.id,
            lines=number_lines([
                JournalLine(account_id=debit_id, debit=amount, credit=0),
                JournalLine(account_id=credit_id, debit=0, credit=amount),
            ]),
        )
        tafsili.assert_entry_has_tafsili(db, entry)
        db.add(entry)
        db.flush()
        session.journal_entry_id = entry.id

    session.status = "posted"
    session.posted_at = datetime.now(timezone.utc)
    db.flush()
    db.refresh(session)
    return session


def moved_since_count(db: Session, session: StockCountSession) -> list[dict]:
    """کالاهایی که **پس از** ثبتِ شمارششان حرکت کرده‌اند.

    گزارش است، نه گارد. اختلافِ این ردیف‌ها همچنان درست حساب می‌شود (چون مبنای
    آن، عکسِ لحظه‌ی شمارش است و حرکتِ بعدی خودش در دفتر هست)؛ ولی کاربر باید
    بداند که بینِ شمارش و ثبت، انبار بی‌کار ننشسته — شاید بخواهد دوباره بشمارد.
    """
    counted = [line for line in session.lines if line.counted_qty is not None]
    if not counted:
        return []
    live = _live_qty(db, session.warehouse_id, [line.item_id for line in counted])
    out = []
    for line in counted:
        now_qty = live.get(line.item_id, Decimal(0))
        if now_qty == Decimal(line.system_qty):
            continue
        out.append(
            {
                "item_id": line.item_id,
                "item_name": line.item.name if line.item else "",
                "system_qty_at_count": Decimal(line.system_qty),
                "system_qty_now": now_qty,
                "counted_at": line.counted_at,
            }
        )
    return out


# --- سریال‌سازی -------------------------------------------------------------------


def _serialize_line(line: StockCountLine) -> dict:
    """ردیفِ نشمرده **اختلاف ندارد**، صفر هم ندارد — `None` است.

    اگر این‌جا صفر برگردانده شود، رابط «بدونِ اختلاف» نشان می‌دهد و کاربر
    نمی‌فهمد که اصلاً سراغِ آن کالا نرفته.
    """
    counted = None if line.counted_qty is None else Decimal(line.counted_qty)
    variance = None if counted is None else counted - Decimal(line.system_qty)
    return {
        "id": line.id,
        "item_id": line.item_id,
        "item_name": line.item.name,
        "item_sku": line.item.sku,
        "unit": line.item.unit,
        "system_qty": Decimal(line.system_qty),
        "counted_qty": counted,
        "unit_cost": Decimal(line.unit_cost),
        "counted_at": line.counted_at,
        "variance": variance,
        "variance_value": None if variance is None else variance * Decimal(line.unit_cost),
    }


def serialize_session(session: StockCountSession) -> dict:
    lines = [_serialize_line(line) for line in sorted(session.lines, key=lambda x: x.item.sku)]
    counted_lines = [l for l in lines if l["counted_qty"] is not None]
    variance_lines = [l for l in counted_lines if l["variance"] != 0]
    return {
        "id": session.id,
        "number": session.number,
        "warehouse_id": session.warehouse_id,
        "warehouse_name": session.warehouse.name,
        "count_date": session.count_date,
        "status": session.status,
        "notes": session.notes,
        "journal_entry_id": session.journal_entry_id,
        "posted_at": session.posted_at,
        "created_at": session.created_at,
        "line_count": len(lines),
        #: پوششِ شمارش — بی این عدد، «ثبت» یعنی امضا کردنِ چیزی که نمی‌دانیم
        #: چه‌قدرش را واقعاً دیده‌ایم.
        "counted_line_count": len(counted_lines),
        "variance_line_count": len(variance_lines),
        "total_variance_value": sum((l["variance_value"] for l in variance_lines), Decimal(0)),
        "lines": lines,
    }


def summarize_session(session: StockCountSession) -> dict:
    return {
        "id": session.id,
        "number": session.number,
        "warehouse_id": session.warehouse_id,
        "warehouse_name": session.warehouse.name,
        "count_date": session.count_date,
        "status": session.status,
        "notes": session.notes,
        "posted_at": session.posted_at,
        "created_at": session.created_at,
        "line_count": len(session.lines),
        "counted_line_count": len([l for l in session.lines if l.counted_qty is not None]),
    }


def list_sessions(db: Session) -> list[dict]:
    sessions = (
        db.query(StockCountSession)
        .order_by(StockCountSession.created_at.desc())
        .all()
    )
    return [summarize_session(s) for s in sessions]


def get_session_detail(db: Session, session_id: UUID) -> dict:
    return serialize_session(_get_session(db, session_id))


def count_tag_projection(db: Session, session: StockCountSession) -> dict:
    """داده‌ی برگه‌های شمارش — **بدونِ موجودیِ سیستمی**.

    شماره‌ی تگ از ترتیبِ ثابتِ ردیف‌ها (کدِ کالا) مشتق می‌شود، نه ذخیره: تا وقتی
    دامنه‌ی جلسه عوض نشود همان عدد است، و چاپِ دوباره **هویتِ تازه نمی‌سازد** —
    همان چیزی که فصل درباره‌ی Reprint هشدار می‌دهد.
    """
    creator = db.get(User, session.created_by_id)
    ordered = sorted(session.lines, key=lambda line: (line.item.sku or "", line.item.name))
    return {
        "session_number": session.number,
        "count_date": session.count_date,
        "warehouse_code": getattr(session.warehouse, "code", "") or "",
        "warehouse_name": session.warehouse.name,
        "responsible": (creator.email if creator else ""),
        "lines": [
            {
                "tag_no": index,
                "sku": line.item.sku,
                "name": line.item.name,
                "unit": line.item.unit,
            }
            for index, line in enumerate(ordered, start=1)
        ],
    }
