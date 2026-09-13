"""برگشتِ خروجِ انبار — فهرست، مبنا، ثبت، جزئیات، ابطال، چاپ."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.issue_returns import ISSUE_RETURN_TYPES, WarehouseIssueReturn
from app.models.user import User
from app.pagination import Page, PageParams
from app.schemas.issue_returns import (
    IssueReturnBasisDocOut,
    IssueReturnBasisOut,
    IssueReturnIn,
    IssueReturnOut,
    IssueReturnRowOut,
)
from app.schemas.returns import VoidIn
from app.services import issue_returns as svc
from app.services.idempotency import idempotent
from app.services.printing import PRINT_TEMPLATES, render_issue_permit

router = APIRouter(tags=["warehouse-issue-returns"])


def _get(db: Session, return_id: UUID) -> WarehouseIssueReturn:
    ret = (
        db.query(WarehouseIssueReturn)
        .options(selectinload(WarehouseIssueReturn.lines))
        .filter(WarehouseIssueReturn.id == return_id)
        .one_or_none()
    )
    if ret is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "برگشت خروج انبار یافت نشد")
    return ret


def _out(db: Session, ret: WarehouseIssueReturn) -> WarehouseIssueReturn:
    svc.attach_line_details(db, [ret])
    return ret


@router.get("/api/warehouse-issue-returns", response_model=Page[IssueReturnRowOut])
def list_issue_returns(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    return_type: str | None = None,
    warehouse_id: UUID | None = None,
    deliverer_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    state: str | None = None,
    _=Depends(require_permission("inventory", "view")),
):
    if return_type and return_type not in ISSUE_RETURN_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوعِ برگشت نامعتبر است")
    if state and state not in ("active", "voided"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "وضعیت باید «معتبر» یا «باطل‌شده» باشد")
    rows, next_cursor = svc.ledger_page(
        db, params, return_type=return_type or None, warehouse_id=warehouse_id, deliverer_id=deliverer_id,
        date_from=date_from, date_to=date_to, state=state or None,
    )
    return Page(items=rows, next_cursor=next_cursor)


@router.get("/api/warehouse-issue-returns/basis", response_model=list[IssueReturnBasisDocOut])
def issue_return_basis_documents(
    return_type: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    """پنجره‌ی «مبنا» — سندهایی که هنوز کالایی برای برگشت دارند."""
    if return_type not in ISSUE_RETURN_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوعِ برگشت نامعتبر است")
    return svc.basis_documents(db, return_type)


@router.get("/api/warehouse-issue-returns/basis/{kind}/{doc_id}", response_model=IssueReturnBasisOut)
def issue_return_basis_detail(
    kind: str,
    doc_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    return svc.basis_detail(db, kind, doc_id)


@router.post("/api/warehouse-issue-returns", response_model=IssueReturnOut, status_code=201)
def create_issue_return(
    data: IssueReturnIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "create")),
):
    """**idempotent.** تکرارِ شبکه‌ای برگشتِ دوم، حرکتِ مثبتِ دوم و سندِ دوم نمی‌سازد."""
    ret = idempotent(
        db, request, user, operation="create_warehouse_issue_return", payload=data,
        run=lambda: svc.create_issue_return(db, data, user),
        replay=lambda rid: _get(db, rid),
    )
    return _out(db, ret)


@router.get("/api/warehouse-issue-returns/{return_id}", response_model=IssueReturnOut)
def get_issue_return(
    return_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    return _out(db, _get(db, return_id))


@router.post("/api/warehouse-issue-returns/{return_id}/void", response_model=IssueReturnOut)
def void_issue_return(
    return_id: UUID,
    data: VoidIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "delete")),
):
    """همان مجوزی که ابطالِ خروج و فاکتور می‌خواهد — ابطال ثبتِ تازه نیست."""
    svc.void_issue_return(db, return_id, reason=data.reason, user=user, void_date=data.void_date)
    return _out(db, _get(db, return_id))


@router.get("/api/warehouse-issue-returns/{return_id}/print", response_class=HTMLResponse)
def print_issue_return(
    return_id: UUID,
    template: str = "standard",
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("inventory", "view")),
):
    if template not in PRINT_TEMPLATES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "قالبِ چاپ نامعتبر است")
    html = render_issue_permit(
        business_name=principal.membership.tenant.name,
        template=template,
        **svc.print_projection(db, _get(db, return_id)),
    )
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})
