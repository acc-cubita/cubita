from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import require_permission
from app.models.quotations import SalesQuotation
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.invoices import SalesInvoiceOut
from app.schemas.quotations import SalesQuotationIn, SalesQuotationOut, SalesQuotationStatusUpdateIn
from app.services.quotations import convert_quotation_to_invoice, create_quotation, update_quotation_status

router = APIRouter(tags=["quotations"])


@router.get("/api/sales-quotations", response_model=Page[SalesQuotationOut])
def list_quotations(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("invoices", "view")),
):
    items, next_cursor = paginate(
        db.query(SalesQuotation).options(selectinload(SalesQuotation.lines)),
        [SalesQuotation.quotation_date, SalesQuotation.number],
        params,
    )
    return Page(items=items, next_cursor=next_cursor)


@router.post("/api/sales-quotations", response_model=SalesQuotationOut, status_code=201)
def create_sales_quotation(
    data: SalesQuotationIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return create_quotation(db, data, user)


@router.patch("/api/sales-quotations/{quotation_id}/status", response_model=SalesQuotationOut)
def patch_quotation_status(
    quotation_id: UUID,
    data: SalesQuotationStatusUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "update")),
):
    return update_quotation_status(db, quotation_id, data.status, user)


@router.post("/api/sales-quotations/{quotation_id}/convert", response_model=SalesInvoiceOut, status_code=201)
def convert_quotation(
    quotation_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return convert_quotation_to_invoice(db, quotation_id, user)
