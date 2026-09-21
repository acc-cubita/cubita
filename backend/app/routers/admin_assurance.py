"""کارتابلِ حسابرسیِ ستاد — فقط سوپرادمین.

**قاعده‌ی این فایل:** هر تغییری روی قرارداد، درونِ زمینه‌ی مستأجرِ *مشتری* اجرا
می‌شود (`tenant_scope`)، نه زمینه‌ی خودِ ادمین. دو دلیل، هر دو سخت:

۱. `assurance_runs`/`assurance_findings` زیرِ RLS هستند؛ بدونِ زمینه، درج با
   سیاستِ `WITH CHECK` رد می‌شود.
۲. ردِ حسابرسی (`app/audit.py`) ردیف را با `tenant_id`ِ خودِ شیء می‌نویسد و
   `audit_log` هم `WITH CHECK` دارد — یعنی تأییدِ قراردادِ مستأجرِ B در زمینه‌ی
   مستأجرِ A، ردِ تغییر را بی‌صدا از دست می‌داد.

همان الگویی که `auth.my_tenants` برای خواندنِ نامِ نقش‌ها به کار می‌برد: وارد
زمینه شو، کار را بکن، زمینه را برگردان.
"""
from contextlib import contextmanager
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal, require_super_admin
from app.models.assurance import AssuranceEngagement
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.assurance import (
    ApproveIn,
    AssignIn,
    CloseIn,
    ExtendIn,
    RejectIn,
    RunOut,
    StaffEngagementOut,
)
from app.services import assurance as service
from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant, tenant_scope

router = APIRouter(prefix="/api/admin/assurance", tags=["assurance-admin"])


@contextmanager
def _client_scope(db: Session, principal: Principal, tenant_id: UUID):
    """زمینه‌ی مستأجرِ مشتری، با بازگرداندنِ تضمین‌شده‌ی زمینه‌ی ادمین."""
    try:
        with tenant_scope(db, tenant_id):
            yield
    finally:
        bind_session_tenant(db, principal.tenant_id)
        apply_tenant_to_transaction(db, principal.tenant_id)


def _row(db: Session, engagement: AssuranceEngagement) -> StaffEngagementOut:
    data = StaffEngagementOut.model_validate(engagement)
    tenant = db.get(Tenant, engagement.tenant_id)
    if tenant is not None:
        data.tenant_name = tenant.name
    if engagement.auditor_user_id is not None:
        auditor = db.get(User, engagement.auditor_user_id)
        if auditor is not None:
            data.auditor_name = auditor.name
            data.auditor_email = auditor.email
    requester = db.get(User, engagement.requested_by_id)
    if requester is not None:
        data.owner_email = requester.email
    return data


def _load(db: Session, engagement_id: UUID) -> AssuranceEngagement:
    engagement = db.get(AssuranceEngagement, engagement_id)
    if engagement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قرارداد یافت نشد")
    return engagement


@router.get("", response_model=list[StaffEngagementOut])
def list_engagements(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    """صفِ درخواست‌ها در همه‌ی کسب‌وکارها، تازه‌ترین اول."""
    query = db.query(AssuranceEngagement)
    if status_filter:
        query = query.filter(AssuranceEngagement.status == status_filter)
    rows = query.order_by(AssuranceEngagement.requested_at.desc()).limit(200).all()
    return [_row(db, row) for row in rows]


@router.post("/{engagement_id}/approve", response_model=StaffEngagementOut)
def approve(
    engagement_id: UUID,
    data: ApproveIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    actor: User = Depends(require_super_admin),
):
    engagement = _load(db, engagement_id)
    with _client_scope(db, principal, engagement.tenant_id):
        service.approve(
            db,
            engagement,
            actor,
            auditor_email=data.auditor_email,
            days=data.days,
            period_from=data.period_from,
            period_to=data.period_to,
        )
    return _row(db, engagement)


@router.post("/{engagement_id}/reject", response_model=StaffEngagementOut)
def reject(
    engagement_id: UUID,
    data: RejectIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    actor: User = Depends(require_super_admin),
):
    engagement = _load(db, engagement_id)
    with _client_scope(db, principal, engagement.tenant_id):
        service.reject(db, engagement, actor, reason=data.reason)
    return _row(db, engagement)


@router.post("/{engagement_id}/assign", response_model=StaffEngagementOut)
def assign(
    engagement_id: UUID,
    data: AssignIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    actor: User = Depends(require_super_admin),
):
    engagement = _load(db, engagement_id)
    with _client_scope(db, principal, engagement.tenant_id):
        service.assign(db, engagement, actor, auditor_email=data.auditor_email, days=data.days)
    return _row(db, engagement)


@router.post("/{engagement_id}/extend", response_model=StaffEngagementOut)
def extend(
    engagement_id: UUID,
    data: ExtendIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _: User = Depends(require_super_admin),
):
    engagement = _load(db, engagement_id)
    with _client_scope(db, principal, engagement.tenant_id):
        service.extend(db, engagement, days=data.days)
    return _row(db, engagement)


@router.post("/{engagement_id}/run", response_model=RunOut)
def run_now(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    actor: User = Depends(require_super_admin),
):
    """اجرای بررسی از سمتِ ستاد — برای وقتی اجرای هنگامِ تأیید شکست خورده."""
    engagement = _load(db, engagement_id)
    if engagement.status not in ("approved", "active"):
        raise HTTPException(status.HTTP_409_CONFLICT, "این قرارداد باز نیست")
    with _client_scope(db, principal, engagement.tenant_id):
        run = service.run_snapshot(db, engagement, actor, trigger="staff")
        return RunOut.model_validate(run)


@router.post("/{engagement_id}/close", response_model=StaffEngagementOut)
def close(
    engagement_id: UUID,
    data: CloseIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _: User = Depends(require_super_admin),
):
    engagement = _load(db, engagement_id)
    with _client_scope(db, principal, engagement.tenant_id):
        service.close(db, engagement, note=data.note)
    return _row(db, engagement)
