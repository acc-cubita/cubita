from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.recurring import RecurringEntryIn, RecurringEntryOut, RunResultOut
from app.services import recurring as service

router = APIRouter(prefix="/api/recurring-entries", tags=["recurring"])


@router.get("", response_model=list[RecurringEntryOut])
def list_recurring(
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return service.list_templates(db)


@router.post("", response_model=RecurringEntryOut, status_code=201)
def create_recurring(
    data: RecurringEntryIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    return service.serialize(service.create_template(db, data, user))


@router.get("/{template_id}", response_model=RecurringEntryOut)
def get_recurring(
    template_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return service.get_template_detail(db, template_id)


@router.put("/{template_id}", response_model=RecurringEntryOut)
def update_recurring(
    template_id: UUID,
    data: RecurringEntryIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "update")),
):
    return service.serialize(service.update_template(db, template_id, data))


@router.post("/{template_id}/set-active", response_model=RecurringEntryOut)
def set_recurring_active(
    template_id: UUID,
    is_active: bool = Query(...),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "update")),
):
    return service.serialize(service.set_active(db, template_id, is_active))


@router.delete("/{template_id}", status_code=204)
def delete_recurring(
    template_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "delete")),
):
    service.delete_template(db, template_id)


@router.post("/run", response_model=RunResultOut)
def run_recurring_due(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    return service.run_due(db, user)


@router.post("/{template_id}/run", response_model=RunResultOut)
def run_recurring_one(
    template_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    return service.run_one(db, template_id, user)
