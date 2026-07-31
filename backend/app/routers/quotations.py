from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.inventory import Contact
from app.models.quotations import SalesQuotation
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.invoices import SalesInvoiceOut
from app.schemas.quotations import SalesQuotationIn, SalesQuotationOut, SalesQuotationStatusUpdateIn
from app.services.printing import render_invoice
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


def _quotation_party(db: Session, quotation: SalesQuotation) -> tuple[str, str]:
    """نامِ مشتریِ پیش‌فاکتور: طرف‌حسابِ انتخاب‌شده، وگرنه نامِ دستی، وگرنه «مشتری»."""
    if quotation.contact_id:
        contact = db.get(Contact, quotation.contact_id)
        if contact is not None:
            return contact.name, " — ".join(filter(None, [contact.phone, contact.address]))
    return (quotation.customer_name or "مشتری"), ""


@router.get("/api/sales-quotations/{quotation_id}/print", response_class=HTMLResponse)
def print_quotation(
    quotation_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("invoices", "view")),
):
    quotation = db.get(SalesQuotation, quotation_id)
    if quotation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیش‌فاکتور یافت نشد")
    name, detail = _quotation_party(db, quotation)
    html = render_invoice(
        kind="پیش‌فاکتور",
        business_name=principal.membership.tenant.name,
        number=quotation.number,
        invoice_date=quotation.quotation_date,
        party_name=name,
        party_detail=detail,
        # توضیحاتِ کاربر؛ اگر خالی بود فقط «پیش‌فاکتور» — بدونِ جمله‌ی پیش‌فرض.
        description=quotation.description or "پیش‌فاکتور",
        lines=[
            {
                "name": line.item.name,
                "description": line.description,
                "qty": line.qty,
                "unit": line.item.unit,
                "unit_price": line.unit_price,
                "discount": 0,
            }
            for line in quotation.lines
        ],
        total=quotation.total_amount,
    )
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})
