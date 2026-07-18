from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import require_permission
from app.models.invoices import PurchaseInvoice, SalesInvoice
from app.models.user import User
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceOut,
    SalesInvoiceIn,
    SalesInvoiceOut,
)
from app.services.inventory import post_purchase_invoice, post_sales_invoice

router = APIRouter(tags=["invoices"])


@router.get("/api/sales-invoices", response_model=list[SalesInvoiceOut])
def list_sales_invoices(db: Session = Depends(get_db), _=Depends(require_permission("invoices", "view"))):
    return (
        db.query(SalesInvoice)
        .options(selectinload(SalesInvoice.lines))
        .order_by(SalesInvoice.invoice_date.desc(), SalesInvoice.number.desc())
        .all()
    )


@router.post("/api/sales-invoices", response_model=SalesInvoiceOut, status_code=201)
def create_sales_invoice(
    data: SalesInvoiceIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return post_sales_invoice(db, data, user)


@router.get("/api/purchase-invoices", response_model=list[PurchaseInvoiceOut])
def list_purchase_invoices(db: Session = Depends(get_db), _=Depends(require_permission("invoices", "view"))):
    return (
        db.query(PurchaseInvoice)
        .options(selectinload(PurchaseInvoice.lines))
        .order_by(PurchaseInvoice.invoice_date.desc(), PurchaseInvoice.number.desc())
        .all()
    )


@router.post("/api/purchase-invoices", response_model=PurchaseInvoiceOut, status_code=201)
def create_purchase_invoice(
    data: PurchaseInvoiceIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return post_purchase_invoice(db, data, user)
