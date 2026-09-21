"""حسابرسی — مسیرهای سمتِ مشتری.

**دو روتر، یک فایل.** `router` باز است (فرمِ درخواست) و `work_router` پشتِ
`require_module("assurance_work")` نشسته — همان الگوی `routers/manufacturing.py`.
هر اندپوینتی که فردا به `work_router` اضافه شود، خودکار گیت می‌خورد؛ این تنها
شکلی از گیت است که با فراموشی باز نمی‌شود.

پنهان‌بودنِ منو هیچ چیزی را تضمین نمی‌کند — کلاینت کد است و کدِ کلاینت را کاربر
دارد. گیتِ واقعی همین دو خط است.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal, require_module, require_permission
from app.models.assurance import AssuranceFinding, AssuranceRun
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.assurance import (
    AssuranceRequestIn,
    EngagementOut,
    FindingOut,
    RefreshIn,
    RunOut,
)
from app.services import assurance as service
from app.services.assurance_access import WORK_MODULE
from app.services.idempotency import idempotent

router = APIRouter(prefix="/api/assurance", tags=["assurance"])
work_router = APIRouter(
    prefix="/api/assurance",
    tags=["assurance"],
    dependencies=[Depends(require_module(WORK_MODULE))],
)


def _out(db: Session, engagement) -> EngagementOut:
    """قرارداد + نامِ حسابرس. مشتری باید بداند چه کسی دفترش را می‌بیند."""
    data = EngagementOut.model_validate(engagement)
    if engagement.auditor_user_id is not None:
        auditor = db.get(User, engagement.auditor_user_id)
        if auditor is not None:
            data.auditor_name = auditor.name
            data.auditor_email = auditor.email
    return data


def _own(db: Session, principal: Principal):
    engagement = service.own_engagement(db, principal.tenant_id)
    if engagement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قراردادِ حسابرسی ندارید")
    return engagement


@router.get("/engagement", response_model=EngagementOut | None)
def get_engagement(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
    _=Depends(require_permission("assurance", "view")),
):
    """قراردادِ این کسب‌وکار، یا `null`.

    نبودنِ قرارداد حالتِ **عادی** است (هر حسابِ تازه)، نه خطا — پس ۲۰۰ با بدنه‌ی
    خالی می‌دهد تا صفحه‌ی درخواست فرمش را نشان دهد، نه یک پیامِ قرمز.
    """
    engagement = service.own_engagement(db, principal.tenant_id)
    return _out(db, engagement) if engagement is not None else None


@router.post("/request", response_model=EngagementOut, status_code=status.HTTP_201_CREATED)
def submit_request(
    data: AssuranceRequestIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    user: User = Depends(require_permission("assurance", "create")),
):
    """**idempotent** — دوکلیک نباید دو درخواست بسازد."""
    return idempotent(
        db,
        request,
        user,
        operation="assurance_request",
        payload=data,
        run=lambda: _out(
            db,
            service.request_engagement(
                db,
                principal.tenant_id,
                user,
                period_from=data.period_from,
                period_to=data.period_to,
                contact_phone=data.contact_phone,
                note=data.note,
            ),
        ),
        replay=lambda _id: _out(db, _own(db, principal)),
    )


# ── پشتِ گیت ─────────────────────────────────────────────────────────────────


@work_router.get("/runs", response_model=Page[RunOut])
def list_runs(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("assurance", "view")),
):
    query = db.query(AssuranceRun)
    rows, next_cursor = paginate(query, [AssuranceRun.ran_at, AssuranceRun.number], params)
    return Page(items=rows, next_cursor=next_cursor)


@work_router.get("/runs/latest", response_model=RunOut | None)
def latest_run(
    db: Session = Depends(get_db),
    _=Depends(require_permission("assurance", "view")),
):
    return (
        db.query(AssuranceRun)
        .order_by(AssuranceRun.ran_at.desc(), AssuranceRun.number.desc())
        .first()
    )


@work_router.get("/runs/{run_id}", response_model=RunOut)
def get_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("assurance", "view")),
):
    run = db.get(AssuranceRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بررسی یافت نشد")
    return run


@work_router.get("/runs/{run_id}/findings", response_model=Page[FindingOut])
def list_findings(
    run_id: UUID,
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    check_key: str | None = None,
    severity: str | None = None,
    _=Depends(require_permission("assurance", "view")),
):
    query = db.query(AssuranceFinding).filter(AssuranceFinding.run_id == run_id)
    if check_key:
        query = query.filter(AssuranceFinding.check_key == check_key)
    if severity:
        query = query.filter(AssuranceFinding.severity == severity)
    rows, next_cursor = paginate(
        query,
        [AssuranceFinding.check_key, AssuranceFinding.seq],
        params,
        descending=False,
    )
    return Page(items=rows, next_cursor=next_cursor)


@work_router.post("/runs", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def refresh_run(
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    user: User = Depends(require_permission("assurance", ("refresh", "approve"))),
):
    """اجرای دوباره‌ی بررسی‌ها — **idempotent** و با خنک‌کننده‌ی پنج‌دقیقه‌ای.

    دو کنشِ جایگزین، چون `refresh` کنشِ تازه‌ای است: wildcardِ نقشِ مالک فهرستِ
    **صریحی** از کنش‌هاست (`view/create/update/delete/approve`) و کنشِ تازه را
    نمی‌پوشاند — یعنی بدونِ این، مالکِ خودِ کسب‌وکار نمی‌توانست دکمه‌ی «بررسی
    دوباره» را بزند و برای رفعش مهاجرتی روی مجوزِ هر مستأجر لازم می‌شد. همان
    الگوی اندپوینتِ «تحویل» که `deliver` یا `approve` را می‌پذیرد.
    """
    engagement = _own(db, principal)
    service.assert_can_refresh(db, engagement)
    return idempotent(
        db,
        request,
        user,
        operation="assurance_run",
        payload=RefreshIn(),
        run=lambda: service.run_snapshot(db, engagement, user, trigger="manual"),
        replay=lambda run_id: db.get(AssuranceRun, run_id),
    )
