"""موتورِ رزرو — و جلوگیری از فروشِ بیش از موجودی (§۸ §۹ §۱۰).

## چه چیزی را حل می‌کند

تا مهاجرتِ ۰۱۷۳ موجودی فقط **لحظه‌ی ثبتِ خروج** سنجیده می‌شد. یعنی سفارشی که
امروز پذیرفته شده بود، هیچ ادعایی روی کالا نداشت و روزِ تحویل ممکن بود چیزی
نمانده باشد. رزرو همان ادعای گم‌شده است:

    رزرو   → `physical` **تکان نمی‌خورد**، فقط `available` کم می‌شود
    خروج   → هر دو کم می‌شوند (مصرفِ رزرو + حرکتِ دفتر)
    لغو    → ادعای آزادشده دوباره `available` می‌شود

## آنچه پایگاه‌داده می‌تواند تضمین کند و آنچه نمی‌تواند

§۹ «بلاک در سطحِ Database» خواسته. صادقانه: Postgres **ادعای تجمعیِ بین‌ردیفی**
به شکلِ اعلانی ندارد — «جمعِ رزروها ≤ جمعِ دفتر» را نه `CHECK` می‌گوید نه
`EXCLUDE`، و تریگر یعنی پنهان‌کردنِ منطقِ کسب‌وکار زیرِ ORM جایی که هیچ تستی
نگاهش نمی‌کند (این مخزن هیچ تریگری ندارد).

پس آنچه واقعاً تحویل می‌شود دو چیزِ مستقل است:

۱. **سریال‌سازیِ تراکنشی** — `SELECT … FOR UPDATE` روی ردیفِ *کالا*، که یک
   تضمینِ واقعیِ سطحِ پایگاه‌داده است. دو تراکنشِ هم‌زمان نمی‌توانند یک موجودی
   را دو بار ببینند.
۲. **تکرارناپذیریِ اعلانی** — ایندکسِ یکتای جزئی روی (سند، ردیف، رویداد).

قفل روی **کالا** است نه بار، به همان دلیلی که `lock_items` نوشته: ردیف‌های
موجود را قفل‌کردن جلوی `INSERT`ِ ردیفِ تازه را نمی‌گیرد، و بارها دقیقاً با هر
رسید `INSERT` می‌شوند. ردیفِ کالا تنها نقطه‌ی مشترکِ همه‌ی عملیاتِ آن کالاست.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.stock_reservations import StockReservation


def reserved_for_item(db: Session, item_id: UUID, warehouse_id: UUID) -> Decimal:
    """جمعِ ادعاهای جاری روی یک کالا در یک انبار — با بار و بی‌بار."""
    total = (
        db.query(func.coalesce(func.sum(StockReservation.qty), 0))
        .filter(
            StockReservation.item_id == item_id,
            StockReservation.warehouse_id == warehouse_id,
        )
        .scalar()
    )
    return Decimal(total)


def reserved_by_batch(db: Session, batch_ids: list[UUID]) -> dict[UUID, Decimal]:
    """ادعای جاری به تفکیکِ بار. بارِ بدونِ ادعا در خروجی نمی‌آید."""
    if not batch_ids:
        return {}
    rows = (
        db.query(StockReservation.batch_id, func.coalesce(func.sum(StockReservation.qty), 0))
        .filter(StockReservation.batch_id.in_(batch_ids))
        .group_by(StockReservation.batch_id)
        .all()
    )
    return {bid: Decimal(total) for bid, total in rows if bid is not None}


def _write(
    db: Session,
    *,
    item_id: UUID,
    warehouse_id: UUID,
    batch_id: UUID | None,
    qty: Decimal,
    kind: str,
    event: str,
    source_type: str,
    source_id: UUID | None,
    source_line_id: UUID | None,
    entry_date: date,
    notes: str,
    user,
) -> StockReservation | None:
    """یک ردیفِ دفترِ رزرو — **ایده‌آمپوتنت**.

    برخوردِ قیدِ یکتا یعنی همین رویداد از قبل برای همین سند ثبت شده (تلاشِ دوباره‌ی
    شبکه)، پس بی‌صدا رد می‌شود. `begin_nested` لازم است تا فقط همین `INSERT`
    برگردد نه کلِ تراکنش — همان الگوی `add_batch_serials`.
    """
    row = StockReservation(
        item_id=item_id,
        warehouse_id=warehouse_id,
        batch_id=batch_id,
        qty=qty,
        kind=kind,
        event=event,
        source_type=source_type,
        source_id=source_id,
        source_line_id=source_line_id,
        entry_date=entry_date,
        notes=notes,
        created_by_id=getattr(user, "id", None),
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        return None
    return row


def reserve(
    db: Session,
    *,
    item,
    warehouse_id: UUID,
    qty: Decimal,
    on: date,
    source_type: str,
    source_id: UUID | None = None,
    source_line_id: UUID | None = None,
    batch_id: UUID | None = None,
    kind: str = "order",
    notes: str = "",
    user=None,
) -> StockReservation | None:
    """ادعا روی موجودی — **پس از قفل و سنجش**.

    فراخوان باید `lock_items` را از قبل زده باشد؛ این‌جا دوباره زده می‌شود تا
    اگر مسیرِ تازه‌ای فراموشش کرد، باز هم امن بماند (قفلِ دوباره در همان تراکنش
    بی‌هزینه است).
    """
    from app.services.inventory import get_stock_qty, lock_items

    qty = Decimal(qty)
    if qty <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مقدارِ رزرو باید بزرگ‌تر از صفر باشد")

    lock_items(db, [item.id])
    on_hand = get_stock_qty(db, item.id, warehouse_id)
    claimed = reserved_for_item(db, item.id, warehouse_id)
    available = on_hand - claimed
    if qty > available:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"موجودیِ قابلِ تخصیصِ «{item.name}» کافی نیست "
            f"(موجود: {on_hand.normalize():f}، رزروشده: {claimed.normalize():f}، "
            f"درخواستی: {qty.normalize():f})",
        )
    return _write(
        db, item_id=item.id, warehouse_id=warehouse_id, batch_id=batch_id, qty=qty,
        kind=kind, event="reserve", source_type=source_type, source_id=source_id,
        source_line_id=source_line_id, entry_date=on, notes=notes, user=user,
    )


def release(
    db: Session,
    *,
    source_type: str,
    source_id: UUID,
    on: date,
    qty: Decimal | None = None,
    event: str = "release",
    notes: str = "",
    user=None,
) -> Decimal:
    """ادعای یک سند را آزاد می‌کند و مقدارِ آزادشده را برمی‌گرداند.

    `qty=None` یعنی **هرچه مانده** (لغوِ کامل). عددِ صریح یعنی لغوِ جزئی (§۱۰) —
    و چون دفتر علامت‌دار است، لغوِ جزئی فقط یک ردیفِ دیگر است، نه بازنویسی.

    آزادکردنِ بیش از مانده بی‌صدا به مانده محدود می‌شود: ادعای منفی یعنی سند
    بیشتر از چیزی که گرفته پس داده، که هیچ معنایی ندارد.
    """
    rows = (
        db.query(StockReservation)
        .filter(StockReservation.source_type == source_type, StockReservation.source_id == source_id)
        .all()
    )
    if not rows:
        return Decimal(0)

    outstanding: dict[tuple[UUID, UUID, UUID | None, UUID | None, str], Decimal] = {}
    for row in rows:
        key = (row.item_id, row.warehouse_id, row.batch_id, row.source_line_id, row.kind)
        outstanding[key] = outstanding.get(key, Decimal(0)) + Decimal(row.qty)

    remaining = None if qty is None else Decimal(qty)
    freed = Decimal(0)
    for (item_id, warehouse_id, batch_id, line_id, kind), open_qty in outstanding.items():
        if open_qty <= 0:
            continue
        take = open_qty if remaining is None else min(open_qty, remaining)
        if take <= 0:
            continue
        written = _write(
            db, item_id=item_id, warehouse_id=warehouse_id, batch_id=batch_id, qty=-take,
            kind=kind, event=event, source_type=source_type, source_id=source_id,
            source_line_id=line_id, entry_date=on, notes=notes, user=user,
        )
        #: اگر ردیف نوشته نشد، آزاد هم نشده. شمردنش یعنی گزارشِ دروغ به فراخوان —
        #: و این یک بار واقعاً اتفاق افتاد: قیدِ یکتا لغوِ دوم را رد کرد و تابع
        #: همچنان «۱۰۰ آزاد شد» برگرداند.
        if written is None:
            continue
        freed += take
        if remaining is not None:
            remaining -= take
            if remaining <= 0:
                break
    db.flush()
    return freed


def consume(db: Session, *, source_type: str, source_id: UUID, on: date, user=None) -> Decimal:
    """ادعای یک سند را **مصرف‌شده** علامت می‌زند — کالا واقعاً بیرون رفت.

    عددش مثلِ آزادسازی منفی است، ولی `event` فرق دارد: §۱۵ می‌خواهد «فروخته‌شده»
    از «لغوشده» تفکیک بماند، و اگر هر دو `release` بودند آن گزارش برای همیشه
    غیرممکن می‌شد.
    """
    return release(
        db, source_type=source_type, source_id=source_id, on=on, event="consume",
        notes="خروجِ قطعی", user=user,
    )


def open_reservations(db: Session, item_id: UUID, warehouse_id: UUID) -> list[dict]:
    """ادعاهای بازِ یک کالا، به تفکیکِ سند — برای نمایش و ردیابی (§۱۰)."""
    rows = (
        db.query(
            StockReservation.source_type,
            StockReservation.source_id,
            StockReservation.kind,
            func.coalesce(func.sum(StockReservation.qty), 0).label("qty"),
            func.min(StockReservation.entry_date).label("since"),
        )
        .filter(
            StockReservation.item_id == item_id,
            StockReservation.warehouse_id == warehouse_id,
        )
        .group_by(StockReservation.source_type, StockReservation.source_id, StockReservation.kind)
        .all()
    )
    return [
        {
            "source_type": r.source_type,
            "source_id": r.source_id,
            "kind": r.kind,
            "qty": Decimal(r.qty),
            "since": r.since,
        }
        for r in rows
        if Decimal(r.qty) > 0
    ]


def available_for(
    db: Session,
    item_id: UUID,
    warehouse_id: UUID,
    *,
    source_type: str | None = None,
    source_id: UUID | None = None,
) -> Decimal:
    """موجودیِ قابلِ استفاده **برای یک سندِ مشخص**.

        available = موجودی − (کلِ رزروها − رزروِ خودِ همین سند)

    سندی که از قبل ادعا داشته باید بتواند ادعای خودش را خرج کند؛ وگرنه رزرو
    به‌جای تضمینِ کالا تبدیل می‌شد به مانعِ تحویلِ همان کالا.

    وقتی هیچ رزروی وجود ندارد — یعنی حالتِ امروزِ همه‌ی مستأجرها — این دقیقاً
    همان `get_stock_qty` می‌شود. «پیش‌فرض = رفتارِ دیروز».
    """
    from app.services.inventory import get_stock_qty

    on_hand = get_stock_qty(db, item_id, warehouse_id)
    claimed = reserved_for_item(db, item_id, warehouse_id)
    own = Decimal(0)
    if source_id is not None:
        own = Decimal(
            db.query(func.coalesce(func.sum(StockReservation.qty), 0))
            .filter(
                StockReservation.item_id == item_id,
                StockReservation.warehouse_id == warehouse_id,
                StockReservation.source_type == source_type,
                StockReservation.source_id == source_id,
            )
            .scalar()
        )
    return on_hand - (claimed - own)
