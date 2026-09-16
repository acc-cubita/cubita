"""خروجِ انبار به‌عنوانِ موجودیتِ مستقل — فهرست، خروجِ مستقیم، جزئیات، چاپ (§۳۳–§۳۸).

مسیرهای «خروج از روی فاکتور» و «ابطالِ خروج» همچنان در `routers/invoices.py`اند؛
این‌جا چیزهایی است که به فاکتور نیازی ندارند.
"""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.invoices import WarehouseIssue
from app.models.user import User
from app.pagination import Page, PageParams
from app.schemas.invoices import (
    DirectWarehouseIssueIn,
    IssueInvoiceContextOut,
    WarehouseIssueOut,
    WarehouseIssueRowOut,
)
from app.services import warehouse_issues as issues_svc
from app.services.idempotency import idempotent
from app.services.printing import PRINT_TEMPLATES, render_issue_permit

router = APIRouter(tags=["warehouse-issues"])

_LIST_TYPES = ("sale", "consumption", "production", "other", "transfer")


def _get_issue(db: Session, issue_id: UUID) -> WarehouseIssue:
    issue = (
        db.query(WarehouseIssue)
        .options(selectinload(WarehouseIssue.lines))
        .filter(WarehouseIssue.id == issue_id)
        .one_or_none()
    )
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "خروج انبار یافت نشد")
    return issue


@router.get("/api/warehouse-issues", response_model=Page[WarehouseIssueRowOut])
def list_warehouse_issue_ledger(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    issue_type: str | None = None,
    warehouse_id: UUID | None = None,
    receiver_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    state: str | None = None,
    _=Depends(require_permission("inventory", "view")),
):
    """فهرستِ خروج‌ها (§۳۶) — یک فهرست برای هر چهار نوع، نه چهار فهرست (§۳۷)."""
    if issue_type and issue_type not in _LIST_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوعِ خروج نامعتبر است")
    if state and state not in ("active", "voided"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "وضعیت باید «معتبر» یا «باطل‌شده» باشد")
    rows, next_cursor = issues_svc.ledger_page(
        db, params, issue_type=issue_type or None, warehouse_id=warehouse_id, receiver_id=receiver_id,
        date_from=date_from, date_to=date_to, state=state or None,
    )
    return Page(items=rows, next_cursor=next_cursor)


@router.post("/api/warehouse-issues", response_model=WarehouseIssueOut, status_code=201)
def create_direct_issue(
    data: DirectWarehouseIssueIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "create")),
):
    """خروجِ مستقل — فروش، مصرف یا سایر (§۱ §۳ §۲۴ §۲۶).

    **idempotent (§۴۶).** تکرارِ شبکه‌ای نباید خروجِ دوم، کسرِ دوباره‌ی موجودی و
    سندِ دوم بسازد.
    """
    issue = idempotent(
        db, request, user, operation="create_direct_warehouse_issue", payload=data,
        run=lambda: issues_svc.create_direct_warehouse_issue(db, data, user),
        replay=lambda rid: _get_issue(db, rid),
    )
    issues_svc.attach_issue_accounts(db, [issue])
    return issue


@router.get("/api/warehouse-issues/{issue_id}", response_model=WarehouseIssueOut)
def get_warehouse_issue(
    issue_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    issue = _get_issue(db, issue_id)
    issues_svc.attach_issue_accounts(db, [issue])
    return issue


@router.get("/api/warehouse-issues/{issue_id}/invoice-context", response_model=IssueInvoiceContextOut)
def warehouse_issue_invoice_context(
    issue_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "create")),
):
    """زمینه‌ی «صدور فاکتور فروش» از روی خروج (§۱۵ §۱۶) — چیزی ذخیره نمی‌کند."""
    return issues_svc.invoice_context(db, _get_issue(db, issue_id))


@router.get("/api/warehouse-issues/{issue_id}/print", response_class=HTMLResponse)
def print_warehouse_issue(
    issue_id: UUID,
    template: str = "standard",
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("inventory", "view")),
):
    """«مجوز خروج انبار» — قالبِ استاندارد یا A5 روی همان سند (§۳۵)."""
    if template not in PRINT_TEMPLATES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "قالبِ چاپ نامعتبر است")
    issue = _get_issue(db, issue_id)
    html = render_issue_permit(
        business_name=principal.membership.tenant.name,
        template=template,
        **issues_svc.issue_print_projection(db, issue),
    )
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})
