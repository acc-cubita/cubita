from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.inventory import Contact
from app.models.invoices import PurchaseInvoice, SalesInvoice
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceOut,
    SalesInvoiceIn,
    SalesInvoiceOut,
)
from app.schemas.voiding import VoidIn, VoidOut
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.printing import render_invoice
from app.services.voiding import void_purchase_invoice, void_sales_invoice

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


@router.post("/api/sales-invoices/{invoice_id}/void", response_model=VoidOut)
def void_sales(
    invoice_id: UUID,
    data: VoidIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "delete")),
):
    """ابطال فاکتور فروش با ثبت سند معکوس.

    مجوز عمداً «delete» است و نه «update»: ابطال سند مالی اثر برگشت‌ناپذیرِ حسابداری
    دارد و نباید در اختیار نقشی باشد که فقط اجازه‌ی ویرایش دارد. با نقش‌های پیش‌فرض
    یعنی فقط مالک — فروشنده که «create» دارد نمی‌تواند فاکتور خودش را پاک کند.
    """
    reversal = void_sales_invoice(db, invoice_id, reason=data.reason, user=user, void_date=data.void_date)
    return VoidOut(reversal_entry_id=reversal.id, reversal_entry_number=reversal.number)


@router.post("/api/purchase-invoices/{invoice_id}/void", response_model=VoidOut)
def void_purchase(
    invoice_id: UUID,
    data: VoidIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "delete")),
):
    reversal = void_purchase_invoice(db, invoice_id, reason=data.reason, user=user, void_date=data.void_date)
    return VoidOut(reversal_entry_id=reversal.id, reversal_entry_number=reversal.number)


def _print_response(html: str) -> HTMLResponse:
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})


def _party(db: Session, contact_id, fallback: str) -> tuple[str, str]:
    contact = db.get(Contact, contact_id) if contact_id else None
    if contact is None:
        return fallback, ""
    return contact.name, " — ".join(filter(None, [contact.phone, contact.address]))


@router.get("/api/sales-invoices/{invoice_id}/print", response_class=HTMLResponse)
def print_sales_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("invoices", "view")),
):
    invoice = db.get(SalesInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور یافت نشد")

    name, detail = _party(db, invoice.contact_id, "مشتری نقدی")
    return _print_response(
        render_invoice(
            kind="فاکتور فروش",
            business_name=principal.membership.tenant.name,
            number=invoice.number,
            invoice_date=invoice.invoice_date,
            party_name=name,
            party_detail=detail,
            description=invoice.description,
            lines=[
                {
                    "name": line.item.name,
                    "description": line.description,
                    "qty": line.qty,
                    "unit": line.item.unit,
                    "unit_price": line.unit_price,
                }
                for line in invoice.lines
            ],
            total=invoice.total_amount,
            voided_at=invoice.voided_at,
            void_reason=invoice.void_reason,
        )
    )


@router.get("/api/purchase-invoices/{invoice_id}/print", response_class=HTMLResponse)
def print_purchase_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("invoices", "view")),
):
    invoice = db.get(PurchaseInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور یافت نشد")

    name, detail = _party(db, invoice.contact_id, "تأمین‌کننده نقدی")
    return _print_response(
        render_invoice(
            kind="فاکتور خرید",
            business_name=principal.membership.tenant.name,
            number=invoice.number,
            invoice_date=invoice.invoice_date,
            party_name=name,
            party_detail=detail,
            description=invoice.description,
            lines=[
                {
                    "name": line.item.name,
                    "description": line.description,
                    "qty": line.qty,
                    "unit": line.item.unit,
                    "unit_price": line.unit_cost,
                }
                for line in invoice.lines
            ],
            total=invoice.total_amount,
            voided_at=invoice.voided_at,
            void_reason=invoice.void_reason,
        )
    )
