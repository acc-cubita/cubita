from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import require_permission
from app.models.returns import PurchaseReturn, SalesReturn
from app.models.user import User
from app.schemas.returns import (
    PurchaseReturnIn,
    PurchaseReturnOut,
    SalesReturnIn,
    SalesReturnOut,
)
from app.services.returns import post_purchase_return, post_sales_return

router = APIRouter(tags=["returns"])


@router.get("/api/sales-returns", response_model=list[SalesReturnOut])
def list_sales_returns(db: Session = Depends(get_db), _=Depends(require_permission("invoices", "view"))):
    return (
        db.query(SalesReturn)
        .options(selectinload(SalesReturn.lines))
        .order_by(SalesReturn.return_date.desc(), SalesReturn.number.desc())
        .all()
    )


@router.post("/api/sales-returns", response_model=SalesReturnOut, status_code=201)
def create_sales_return(
    data: SalesReturnIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return post_sales_return(db, data, user)


@router.get("/api/purchase-returns", response_model=list[PurchaseReturnOut])
def list_purchase_returns(db: Session = Depends(get_db), _=Depends(require_permission("invoices", "view"))):
    return (
        db.query(PurchaseReturn)
        .options(selectinload(PurchaseReturn.lines))
        .order_by(PurchaseReturn.return_date.desc(), PurchaseReturn.number.desc())
        .all()
    )


@router.post("/api/purchase-returns", response_model=PurchaseReturnOut, status_code=201)
def create_purchase_return(
    data: PurchaseReturnIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return post_purchase_return(db, data, user)
