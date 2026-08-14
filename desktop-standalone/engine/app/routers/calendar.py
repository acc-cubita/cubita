from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.calendar import CalendarEventDone, CalendarEventIn, CalendarEventOut
from app.services import calendar as calendar_service

router = APIRouter(prefix="/api/calendar-events", tags=["calendar"])


@router.get("", response_model=list[CalendarEventOut])
def list_events(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    include_done: bool = Query(True),
    db: Session = Depends(get_db),
    _=Depends(require_permission("calendar", "view")),
):
    return calendar_service.list_events(db, date_from=date_from, date_to=date_to, include_done=include_done)


@router.post("", response_model=CalendarEventOut, status_code=201)
def create_event(
    data: CalendarEventIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("calendar", "create")),
):
    return calendar_service.create_event(db, data, user)


@router.put("/{event_id}", response_model=CalendarEventOut)
def update_event(
    event_id: UUID,
    data: CalendarEventIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("calendar", "update")),
):
    return calendar_service.update_event(db, event_id, data)


@router.patch("/{event_id}/done", response_model=CalendarEventOut)
def toggle_done(
    event_id: UUID,
    data: CalendarEventDone,
    db: Session = Depends(get_db),
    _=Depends(require_permission("calendar", "update")),
):
    return calendar_service.set_done(db, event_id, data.is_done)


@router.delete("/{event_id}", status_code=204)
def delete_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("calendar", "delete")),
):
    calendar_service.delete_event(db, event_id)
