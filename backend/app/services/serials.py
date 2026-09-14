"""ردیابیِ سریال — «SN-1 کجاست، و از کجا آمده؟»

پیش از این، سریال یک بن‌بست بود: به بچِ ورودش وصل بود و بس. فروش هیچ‌وقت لمسش
نمی‌کرد، پس جوابِ «به چه کسی فروخته شد؟» وجود نداشت و جوابِ «کجاست؟» تا ابد
«در همان بچِ اول» می‌ماند.

## چرا دفترِ رویداد، و نه یک ستونِ موقعیت

ساده‌ترین راه یک `current_document_id` روی سریال بود. غلط است: با هر حرکت
بازنویسی می‌شود و تاریخچه را می‌بلعد — همان اشتباهی که کوبیتا در موجودی نکرده
(مانده از دفتر مشتق می‌شود، در ستون ذخیره نمی‌شود). پس:

    موقعیتِ فعلی = مشتق از آخرین رویداد

## چرا رویدادِ خروج صریح ثبت می‌شود، نه خودکار وسطِ ثبتِ فاکتور

سریال چیزی است که **انسان می‌خوانَد** — از روی جعبه، با اسکنر. فاکتور مقدار
می‌داند و نمی‌داند کدام سه تا از پنج تا رفت. بافتنِ سریال داخلِ
`post_sales_invoice` یعنی هر مسیرِ فروش (فروشگاه، صندوق، بازارگاه، همگام‌سازیِ
آفلاین، برگشت) باید سریال بگیرد، وگرنه ثبت نشود — و هیچ‌کدام از آن مسیرها امروز
سریال ندارند.

پس تخصیص یک **گامِ جدا** است، با اعتبارسنجی در برابر مقدارِ سند. این یک سازشِ
آگاهانه است و حدّش صریح: تا وقتی کسی تخصیص ندهد، سند سریال ندارد. گزارشِ
«سریالِ تخصیص‌نیافته» همین شکاف را دیدنی می‌کند به‌جای اینکه پنهانش کند.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.models.advanced_inventory import (
    SERIAL_EVENT_TYPES,
    SERIAL_EVENT_LABELS,
    SERIAL_OUTBOUND_EVENTS,
    SerialEvent,
    StockBatch,
    StockBatchSerial,
)
from app.models.inventory import Contact, Item
from app.models.user import User
from app.services import valuation


def record(
    db: Session,
    serial_row: StockBatchSerial,
    *,
    event_type: str,
    source_type: str,
    source_id: UUID | None,
    entry_date: date,
    user: User | None = None,
    notes: str = "",
) -> SerialEvent | None:
    """یک رویداد ثبت می‌کند — و اگر همین سریال روی همین سند رویداد دارد، هیچ.

    یکتاسازی از **شکلِ داده** می‌آید (ایندکسِ یکتای `serial+source`)، نه از یک
    جدولِ کلید: تلاشِ دوباره‌ی شبکه نباید دو رویدادِ اقتصادی بسازد.
    """
    if event_type not in SERIAL_EVENT_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوعِ رویدادِ سریال نامعتبر است")
    if source_id is not None:
        existing = (
            db.query(SerialEvent)
            .filter(
                SerialEvent.serial_id == serial_row.id,
                SerialEvent.source_type == source_type,
                SerialEvent.source_id == source_id,
            )
            .first()
        )
        if existing is not None:
            return existing
    event = SerialEvent(
        serial_id=serial_row.id,
        event_type=event_type,
        source_type=source_type,
        source_id=source_id,
        entry_date=entry_date,
        notes=notes,
        created_by_id=user.id if user is not None else None,
    )
    db.add(event)
    db.flush()
    return event


def current_state(serial_row: StockBatchSerial) -> dict:
    """«الان کجاست؟» — **مشتق** از آخرین رویداد، نه ذخیره‌شده."""
    events = sorted(serial_row.events, key=lambda e: (e.entry_date, e.created_at or e.entry_date))
    last = events[-1] if events else None
    in_stock = last is None or last.event_type not in SERIAL_OUTBOUND_EVENTS
    return {
        "in_stock": in_stock,
        "last_event_type": last.event_type if last else None,
        "last_event_label": SERIAL_EVENT_LABELS.get(last.event_type, "") if last else "",
        "last_source_type": last.source_type if last else None,
        "last_source_id": last.source_id if last else None,
        "last_entry_date": last.entry_date if last else None,
    }


def assign(
    db: Session,
    *,
    serials: list[str],
    item_id: UUID,
    source_type: str,
    source_id: UUID,
    entry_date: date,
    event_type: str,
    user: User,
) -> dict:
    """سریال‌های نام‌برده را به یک سند می‌چسباند.

    سریال با **نامش** داده می‌شود چون کاربر همان را از روی جعبه می‌خوانَد؛
    این‌جا به ردیفِ واقعی حل می‌شود و اگر نبود، خطا — نه ساختنِ خاموشِ سریالِ
    تازه، که یعنی هر تایپی یک قلمِ جعلی بسازد.
    """
    if event_type not in SERIAL_EVENT_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوعِ رویدادِ سریال نامعتبر است")
    wanted = [s.strip() for s in serials if s and s.strip()]
    if not wanted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "هیچ سریالی داده نشده است")

    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کالا یافت نشد")

    rows = (
        db.query(StockBatchSerial)
        .join(StockBatch, StockBatch.id == StockBatchSerial.batch_id)
        .options(selectinload(StockBatchSerial.events))
        .filter(StockBatch.item_id == item_id, StockBatchSerial.serial.in_(wanted))
        .all()
    )
    found = {row.serial: row for row in rows}
    missing = [s for s in wanted if s not in found]
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"این سریال‌ها برای «{item.name}» ثبت نشده‌اند: {'، '.join(missing[:10])}",
        )

    #: **خروجِ چیزی که از قبل بیرون رفته**، خطاست. بی این گارد یک سریال می‌توانست
    #: دو بار فروخته شود و «کجاست؟» دو جواب پیدا کند.
    if event_type in SERIAL_OUTBOUND_EVENTS:
        #: **تلاشِ دوباره‌ی همین سند «قبلاً خارج شده» نیست.** بی این استثنا، یک
        #: قطعیِ شبکه به ۴۰۰ می‌خورد به‌جای اینکه بی‌اثر replay شود.
        gone = [
            s
            for s in wanted
            if not current_state(found[s])["in_stock"]
            and not any(
                e.source_type == source_type and e.source_id == source_id
                for e in found[s].events
            )
        ]
        if gone:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"این سریال‌ها از قبل از انبار خارج شده‌اند: {'، '.join(gone[:10])}",
            )

    created = 0
    for name in wanted:
        before = len(found[name].events)
        record(
            db,
            found[name],
            event_type=event_type,
            source_type=source_type,
            source_id=source_id,
            entry_date=entry_date,
            user=user,
        )
        db.refresh(found[name])
        created += 1 if len(found[name].events) > before else 0

    return {"assigned": len(wanted), "created": created, "replayed": len(wanted) - created}


def search(
    db: Session,
    *,
    serial: str | None = None,
    item_id: UUID | None = None,
    source_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 200,
) -> list[dict]:
    """جست‌وجوی سریال — هر سریال با **کلِ تاریخچه‌اش**، نه فقط موقعیتِ فعلی.

    فیلترها روی رویداد اعمال می‌شوند ولی تاریخچه‌ی برگردانده‌شده کامل است: اگر
    بپرسی «کدام سریال‌ها در فروردین خارج شدند»، پاسخ باید بگوید هرکدام از کجا
    آمده بودند — وگرنه باز یک بن‌بستِ تازه ساخته‌ایم.
    """
    query = (
        db.query(StockBatchSerial)
        .join(StockBatch, StockBatch.id == StockBatchSerial.batch_id)
        .options(selectinload(StockBatchSerial.events))
    )
    if serial:
        query = query.filter(StockBatchSerial.serial.ilike(f"%{serial.strip()}%"))
    if item_id is not None:
        query = query.filter(StockBatch.item_id == item_id)
    if source_type or date_from or date_to:
        event_q = db.query(SerialEvent.serial_id)
        if source_type:
            event_q = event_q.filter(SerialEvent.source_type == source_type)
        if date_from is not None:
            event_q = event_q.filter(SerialEvent.entry_date >= date_from)
        if date_to is not None:
            event_q = event_q.filter(SerialEvent.entry_date <= date_to)
        query = query.filter(StockBatchSerial.id.in_(event_q))

    rows = query.order_by(StockBatchSerial.serial).limit(limit).all()
    if not rows:
        return []

    batches = {
        b.id: b
        for b in db.query(StockBatch).filter(
            StockBatch.id.in_({row.batch_id for row in rows})
        )
    }
    items = {
        i.id: i
        for i in db.query(Item).filter(Item.id.in_({b.item_id for b in batches.values()}))
    }

    #: شماره‌ی سند و طرف حساب از همان موتورِ کاردکس می‌آیند — نه یک نگاشتِ دوم.
    keys = {
        (event.source_type, event.source_id)
        for row in rows
        for event in row.events
        if event.source_id is not None and event.source_type
    }
    numbers = valuation.document_numbers(db, keys)
    contacts = _contacts_for(db, keys)

    out = []
    for row in rows:
        batch = batches.get(row.batch_id)
        item = items.get(batch.item_id) if batch else None
        events = sorted(row.events, key=lambda e: (e.entry_date, e.created_at or e.entry_date))
        out.append(
            {
                "serial_id": row.id,
                "serial": row.serial,
                "status": row.status,
                "item_id": item.id if item else None,
                "item_sku": item.sku if item else "",
                "item_name": item.name if item else "",
                "batch_number": batch.batch_number if batch else "",
                **current_state(row),
                "events": [
                    {
                        "event_type": event.event_type,
                        "event_label": SERIAL_EVENT_LABELS.get(event.event_type, event.event_type),
                        "entry_date": event.entry_date,
                        "source_type": event.source_type,
                        "source_label": valuation.SOURCE_LABELS.get(
                            event.source_type, event.source_type
                        ),
                        "source_id": event.source_id,
                        "source_number": numbers.get((event.source_type, event.source_id)),
                        "counterparty": contacts.get((event.source_type, event.source_id), ""),
                        "notes": event.notes,
                    }
                    for event in events
                ],
            }
        )
    return out


def _contacts_for(db: Session, keys: set[tuple[str, UUID]]) -> dict[tuple[str, UUID], str]:
    """نامِ طرف حسابِ هر سندِ مبدأ — همان نگاشتی که گزارشِ ابعاد هم می‌سازد."""
    from app.services.inventory_analytics import _contact_by_source

    by_source = _contact_by_source(db, keys)
    if not by_source:
        return {}
    names = {
        cid: name
        for cid, name in db.query(Contact.id, Contact.name).filter(
            Contact.id.in_(set(by_source.values()))
        )
    }
    return {key: names.get(cid, "") for key, cid in by_source.items()}
