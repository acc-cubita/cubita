from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import require_permission
from app.models.invoices import PurchaseInvoice, SalesInvoice
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceOut,
    SalesInvoiceIn,
    SalesInvoiceOut,
)
from app.services.inventory import post_purchase_invoice, post_sales_invoice

router = APIRouter(tags=["invoices"])


@router.get("/api/sales-invoices", response_model=Page[SalesInvoiceOut])
def list_sales_invoices(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("invoices", "view")),
):
    items, next_cursor = paginate(
        db.query(SalesInvoice).options(selectinload(SalesInvoice.lines)),
        [SalesInvoice.invoice_date, SalesInvoice.number],
        params,
    )
    return Page(items=items, next_cursor=next_cursor)


@router.post("/api/sales-invoices", response_model=SalesInvoiceOut, status_code=201)
def create_sales_invoice(
    data: SalesInvoiceIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return post_sales_invoice(db, data, user)


@router.get("/api/purchase-invoices", response_model=Page[PurchaseInvoiceOut])
def list_purchase_invoices(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("invoices", "view")),
):
    items, next_cursor = paginate(
        db.query(PurchaseInvoice).options(selectinload(PurchaseInvoice.lines)),
        [PurchaseInvoice.invoice_date, PurchaseInvoice.number],
        params,
    )
    return Page(items=items, next_cursor=next_cursor)


@router.post("/api/purchase-invoices", response_model=PurchaseInvoiceOut, status_code=201)
def create_purchase_invoice(
    data: PurchaseInvoiceIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return post_purchase_invoice(db, data, user)
