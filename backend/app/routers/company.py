"""موجودیت‌های «شرکت» — گروهِ طرف‌حساب، محلِ جغرافیایی، فردِ مرتبط.

مجوزها روی ماژولِ `crm` می‌نشیند: هر سه شناسنامه‌ی طرف‌حساب‌اند، و کسی که اجازه‌ی
دیدن/ویرایشِ طرف‌حساب دارد باید بتواند گروه و محل و افرادِ مرتبطش را هم ببیند و
بچیند. جدا کردنشان یعنی مجوزی که هیچ‌کس نمی‌فهمد چه چیزی را باز می‌کند.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.models.company import SavedReport
from app.schemas.company import (
    ContactGroupIn,
    ContactGroupOut,
    GeoLocationIn,
    GeoLocationOut,
    RelatedPersonIn,
    RelatedPersonOut,
    SavedReportIn,
    SavedReportOut,
)
from app.services import company as service

router = APIRouter(prefix="/api/company", tags=["company"])


# ── گروهِ طرف‌حساب ────────────────────────────────────────────────────────────


@router.get("/groups", response_model=list[ContactGroupOut])
def list_groups(
    include_inactive: bool = Query(True),
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "view")),
):
    return service.list_groups(db, include_inactive=include_inactive)


@router.post("/groups", response_model=ContactGroupOut, status_code=201)
def create_group(
    data: ContactGroupIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("crm", "create")),
):
    return service.create_group(db, data, user)


@router.put("/groups/{group_id}", response_model=ContactGroupOut)
def update_group(
    group_id: UUID,
    data: ContactGroupIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "update")),
):
    return service.update_group(db, group_id, data)


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(
    group_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "delete")),
):
    service.delete_group(db, group_id)


# ── محلِ جغرافیایی ───────────────────────────────────────────────────────────


@router.get("/locations", response_model=list[GeoLocationOut])
def list_locations(
    include_inactive: bool = Query(True),
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "view")),
):
    return service.list_geo(db, include_inactive=include_inactive)


@router.post("/locations", response_model=GeoLocationOut, status_code=201)
def create_location(
    data: GeoLocationIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("crm", "create")),
):
    return service.create_geo(db, data, user)


@router.put("/locations/{geo_id}", response_model=GeoLocationOut)
def update_location(
    geo_id: UUID,
    data: GeoLocationIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "update")),
):
    return service.update_geo(db, geo_id, data)


@router.delete("/locations/{geo_id}", status_code=204)
def delete_location(
    geo_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "delete")),
):
    service.delete_geo(db, geo_id)


# ── فردِ مرتبط ───────────────────────────────────────────────────────────────


@router.get("/persons", response_model=list[RelatedPersonOut])
def list_persons(
    contact_id: UUID | None = None,
    include_inactive: bool = Query(True),
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "view")),
):
    return service.list_persons(db, contact_id=contact_id, include_inactive=include_inactive)


@router.post("/persons", response_model=RelatedPersonOut, status_code=201)
def create_person(
    data: RelatedPersonIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("crm", "create")),
):
    return service.create_person(db, data, user)


@router.put("/persons/{person_id}", response_model=RelatedPersonOut)
def update_person(
    person_id: UUID,
    data: RelatedPersonIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "update")),
):
    return service.update_person(db, person_id, data)


@router.delete("/persons/{person_id}", status_code=204)
def delete_person(
    person_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "delete")),
):
    service.delete_person(db, person_id)


# ── گزارش‌ساز: تعریفِ گزارش‌های ذخیره‌شده ────────────────────────────────────
#
# مجوزها روی `reports` می‌نشیند: این‌ها گزارش‌اند، و کسی که اجازه‌ی دیدنِ گزارش دارد
# باید بتواند گزارشِ ذخیره‌شده را هم ببیند. *ساختن* اما مجوزِ نوشتن می‌خواهد، چون
# تعریفِ گزارش برای همه‌ی اعضای کسب‌وکار دیده می‌شود، نه فقط سازنده‌اش.


def _get_report(db: Session, report_id: UUID) -> SavedReport:
    row = db.get(SavedReport, report_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "گزارش پیدا نشد")
    return row


@router.get("/reports", response_model=list[SavedReportOut])
def list_reports(
    db: Session = Depends(get_db),
    _=Depends(require_permission("reports", "view")),
):
    return (
        db.query(SavedReport)
        .order_by(SavedReport.is_pinned.desc(), SavedReport.name)
        .all()
    )


@router.post("/reports", response_model=SavedReportOut, status_code=201)
def create_report(
    data: SavedReportIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports", "create")),
):
    row = SavedReport(
        name=data.name.strip(),
        description=data.description,
        source=data.source,
        config=data.config,
        is_pinned=data.is_pinned,
        created_by_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/reports/{report_id}", response_model=SavedReportOut)
def update_report(
    report_id: UUID,
    data: SavedReportIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("reports", "update")),
):
    row = _get_report(db, report_id)
    row.name = data.name.strip()
    row.description = data.description
    row.source = data.source
    row.config = data.config
    row.is_pinned = data.is_pinned
    db.commit()
    db.refresh(row)
    return row


@router.delete("/reports/{report_id}", status_code=204)
def delete_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("reports", "delete")),
):
    db.delete(_get_report(db, report_id))
    db.commit()
