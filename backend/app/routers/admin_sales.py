"""درخواست‌های خرید و مشاوره — کارتابلِ فروش در ستاد.

ثبتِ عمومی در `sales_inquiries.py` است. این‌جا کارشناسِ فروش صف را می‌بیند و وضعیت و یادداشتِ هر
درخواست را عوض می‌کند؛ هر تغییر در ردِ کارهای ستاد ثبت می‌شود (`tests/test_staff_audit_coverage.py`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import StaffPrincipal, require_staff
from app.models.sales_inquiry import SALES_STATUSES, SalesInquiry
from app.rate_limit import limit_admin_write
from app.services import staff_audit

router = APIRouter(prefix="/api/admin/sales-inquiries", tags=["admin-sales"])


class SalesInquiryOut(BaseModel):
    id: UUID
    created_at: datetime
    name: str
    company: str
    phone: str
    email: str
    product: str
    seats: int | None
    message: str
    status: str
    staff_note: str
    handled_at: datetime | None
    handled_by: str | None

    model_config = {"from_attributes": True}


class SalesInquiryListOut(BaseModel):
    items: list[SalesInquiryOut]
    #: شمارِ «تازه»ها در کلِ صف — نشانِ منوی ستاد.
    new_count: int


class SalesInquiryUpdateIn(BaseModel):
    status: str | None = None
    staff_note: str | None = Field(default=None, max_length=4000)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None and v not in SALES_STATUSES:
            raise ValueError("وضعیتِ ناشناخته")
        return v


@router.get("", response_model=SalesInquiryListOut)
def list_inquiries(
    db: Session = Depends(get_db),
    _: StaffPrincipal = Depends(require_staff("sales", "view")),
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Field(ge=1, le=200)] = 200,
) -> SalesInquiryListOut:
    """تازه‌ترین اول. `status` صف را به یک وضعیت محدود می‌کند."""
    q = select(SalesInquiry).order_by(SalesInquiry.created_at.desc()).limit(limit)
    if status_filter:
        q = q.where(SalesInquiry.status == status_filter)
    new_count = db.scalar(select(func.count()).select_from(SalesInquiry).where(SalesInquiry.status == "new")) or 0
    return SalesInquiryListOut(
        items=[SalesInquiryOut.model_validate(r) for r in db.execute(q).scalars().all()],
        new_count=new_count,
    )


@router.patch("/{inquiry_id}", response_model=SalesInquiryOut, dependencies=[Depends(limit_admin_write)])
def update_inquiry(
    inquiry_id: UUID,
    data: SalesInquiryUpdateIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("sales", "edit")),
) -> SalesInquiryOut:
    row = db.get(SalesInquiry, inquiry_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درخواست پیدا نشد")
    changes: dict = {}
    if data.status is not None and data.status != row.status:
        changes["status"] = [row.status, data.status]
        row.status = data.status
    if data.staff_note is not None and data.staff_note.strip() != row.staff_note:
        row.staff_note = data.staff_note.strip()
        changes["staff_note"] = row.staff_note
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "تغییری فرستاده نشد")
    row.handled_at = datetime.now(timezone.utc)
    row.handled_by = staff.email
    db.flush()
    staff_audit.record(
        db,
        staff,
        "sales_inquiry_update",
        summary=f"پیگیریِ درخواستِ خریدِ «{row.name}»",
        target_type="sales_inquiry",
        target_id=row.id,
        target_label=row.company or row.name,
        details=changes,
    )
    return SalesInquiryOut.model_validate(row)
