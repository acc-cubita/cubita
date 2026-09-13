from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.transfers import StockTransfer
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.transfers import StockTransferIn, StockTransferOut
from app.schemas.voiding import VoidIn
from app.services.idempotency import idempotent
from app.services.printing import PRINT_TEMPLATES, render_issue_permit
from app.services.transfers import post_stock_transfer, transfer_print_projection, void_stock_transfer

router = APIRouter(tags=["transfers"])


def _get_transfer(db: Session, transfer_id: UUID) -> StockTransfer:
    transfer = (
        db.query(StockTransfer)
        .options(selectinload(StockTransfer.lines))
        .filter(StockTransfer.id == transfer_id)
        .one_or_none()
    )
    if transfer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "انتقال یافت نشد")
    return transfer


@router.get("/api/stock-transfers", response_model=Page[StockTransferOut])
def list_stock_transfers(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("inventory", "view")),
):
    items, next_cursor = paginate(
        db.query(StockTransfer).options(selectinload(StockTransfer.lines)),
        [StockTransfer.transfer_date, StockTransfer.number],
        params,
    )
    return Page(items=items, next_cursor=next_cursor)


@router.post("/api/stock-transfers", response_model=StockTransferOut, status_code=201)
def create_stock_transfer(
    data: StockTransferIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    """**idempotent.** تکرارِ شبکه‌ای نباید دو انتقال و دو بار جابه‌جاییِ کالا بسازد."""
    return idempotent(
        db, request, user, operation="create_stock_transfer", payload=data,
        run=lambda: post_stock_transfer(db, data, user),
        replay=lambda rid: _get_transfer(db, rid),
    )


@router.post("/api/stock-transfers/{transfer_id}/void", response_model=StockTransferOut)
def void_transfer(
    transfer_id: UUID,
    data: VoidIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "delete")),
):
    """ابطالِ کنترل‌شده، نه حذف (§۴۲) — هر دو حرکت و سندِ جابه‌جایی برمی‌گردند."""
    return void_stock_transfer(db, transfer_id, reason=data.reason, user=user, void_date=data.void_date)


@router.get("/api/stock-transfers/{transfer_id}/print", response_class=HTMLResponse)
def print_transfer(
    transfer_id: UUID,
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
        **transfer_print_projection(db, _get_transfer(db, transfer_id)),
    )
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})
