from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.calendar import CalendarEvent
from app.models.user import User
from app.schemas.calendar import CalendarEventIn


def list_events(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    include_done: bool = True,
) -> list[CalendarEvent]:
    """رویدادهای بازه‌ی خواسته‌شده (یا همه) — مرتب بر اساس تاریخ و ساعت.

    بدون صفحه‌بندی: نمای ماهانه‌ی تقویم ذاتاً محدود است (چند ده رویداد در ماه)، پس
    کرسر فقط پیچیدگی بی‌فایده اضافه می‌کرد. RLS خودش خروجی را به مستأجر جاری محدود
    می‌کند.
    """
    q = db.query(CalendarEvent)
    if date_from is not None:
        q = q.filter(CalendarEvent.event_date >= date_from)
    if date_to is not None:
        q = q.filter(CalendarEvent.event_date <= date_to)
    if not include_done:
        q = q.filter(CalendarEvent.is_done.is_(False))
    return q.order_by(
        CalendarEvent.event_date.asc(),
        CalendarEvent.start_time.asc().nullsfirst(),
        CalendarEvent.created_at.asc(),
    ).all()


def get_event(db: Session, event_id: UUID) -> CalendarEvent:
    # db.get زیر RLS رویدادِ مستأجر دیگر را اصلاً نمی‌بیند، پس این هم گاردِ «پیدا
    # نشد» است و هم گاردِ جداسازیِ مستأجر — یک مسیر، نه دو تا که یکی فراموش شود.
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "رویداد پیدا نشد")
    return event


def _apply(event: CalendarEvent, data: CalendarEventIn) -> None:
    event.title = data.title
    event.description = data.description
    event.event_date = data.event_date
    event.start_time = data.start_time
    event.end_time = data.end_time
    event.category = data.category
    event.is_done = data.is_done


def create_event(db: Session, data: CalendarEventIn, user: User) -> CalendarEvent:
    event = CalendarEvent(created_by_id=user.id)
    _apply(event, data)
    # tenant_id توسط رویدادِ before_flush خودکار مهر می‌خورد.
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_event(db: Session, event_id: UUID, data: CalendarEventIn) -> CalendarEvent:
    event = get_event(db, event_id)
    _apply(event, data)
    db.commit()
    db.refresh(event)
    return event


def set_done(db: Session, event_id: UUID, done: bool) -> CalendarEvent:
    event = get_event(db, event_id)
    event.is_done = done
    db.commit()
    db.refresh(event)
    return event


def delete_event(db: Session, event_id: UUID) -> None:
    event = get_event(db, event_id)
    db.delete(event)
    db.commit()
