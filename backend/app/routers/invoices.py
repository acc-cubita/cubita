from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
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
from app.services.idempotency import idempotent
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from decimal import Decimal

from app.services.pdf_invoice import render_invoice_pdf
from app.services.printing import fa_number, render_invoice
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
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return idempotent(
        db,
        request,
        user,
        operation="create_sales_invoice",
        payload=data,
        run=lambda: post_sales_invoice(db, data, user),
        replay=lambda rid: db.get(SalesInvoice, rid),
    )


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
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return idempotent(
        db,
        request,
        user,
        operation="create_purchase_invoice",
        payload=data,
        run=lambda: post_purchase_invoice(db, data, user),
        replay=lambda rid: db.get(PurchaseInvoice, rid),
    )


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


def _currency_line(invoice) -> str:
    """اگر فاکتور ارزی باشد، رشته‌ی «ارز/نرخ/معادل» را برای چاپ و PDF می‌سازد.

    مبالغِ فاکتور پایه (ریال) اند؛ معادلِ ارزی = مبلغِ قابل‌پرداختِ ریالی ÷ نرخ.
    """
    if not invoice.currency_code:
        return ""
    rate = Decimal(str(invoice.exchange_rate or 1))
    grand = Decimal(str(invoice.total_amount)) + Decimal(str(invoice.tax_amount))
    foreign = (grand / rate).quantize(Decimal("0.01")) if rate else Decimal(0)
    return (
        f"ارز فاکتور: {invoice.currency_code} — نرخ برابری: {fa_number(rate)} ریال — "
        f"معادل: {fa_number(foreign)} {invoice.currency_code}"
    )


def _sales_render_kwargs(db: Session, principal: Principal, invoice: SalesInvoice) -> dict:
    name, detail = _party(db, invoice.contact_id, "مشتری نقدی")
    return dict(
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
                "discount": line.discount,
            }
            for line in invoice.lines
        ],
        total=invoice.total_amount,
        tax_amount=invoice.tax_amount,
        total_discount=invoice.total_discount,
        voided_at=invoice.voided_at,
        void_reason=invoice.void_reason,
        currency_line=_currency_line(invoice),
    )


def _purchase_render_kwargs(db: Session, principal: Principal, invoice: PurchaseInvoice) -> dict:
    name, detail = _party(db, invoice.contact_id, "تأمین‌کننده نقدی")
    return dict(
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
                "discount": line.discount,
            }
            for line in invoice.lines
        ],
        total=invoice.total_amount,
        tax_amount=invoice.tax_amount,
        total_discount=invoice.total_discount,
        voided_at=invoice.voided_at,
        void_reason=invoice.void_reason,
        currency_line=_currency_line(invoice),
    )


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


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
    return _print_response(render_invoice(**_sales_render_kwargs(db, principal, invoice)))


@router.get("/api/sales-invoices/{invoice_id}/pdf")
def pdf_sales_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("invoices", "view")),
):
    invoice = db.get(SalesInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور یافت نشد")
    pdf_bytes = render_invoice_pdf(**_sales_render_kwargs(db, principal, invoice))
    return _pdf_response(pdf_bytes, f"sales-invoice-{invoice.number}.pdf")


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
    return _print_response(render_invoice(**_purchase_render_kwargs(db, principal, invoice)))


@router.get("/api/purchase-invoices/{invoice_id}/pdf")
def pdf_purchase_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("invoices", "view")),
):
    invoice = db.get(PurchaseInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور یافت نشد")
    pdf_bytes = render_invoice_pdf(**_purchase_render_kwargs(db, principal, invoice))
    return _pdf_response(pdf_bytes, f"purchase-invoice-{invoice.number}.pdf")
