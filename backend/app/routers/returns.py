from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.inventory import Contact, Item
from app.models.invoices import SalesInvoice
from app.models.returns import PurchaseReturn, SalesReturn
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.returns import (
    PurchaseReturnIn,
    PurchaseReturnOut,
    ReturnableLineOut,
    SalesReturnIn,
    SalesReturnOut,
)
from app.services.printing import render_invoice
from app.services.returns import get_returnable_summary, post_purchase_return, post_sales_return

router = APIRouter(tags=["returns"])


@router.get("/api/sales-invoices/{invoice_id}/returnable", response_model=list[ReturnableLineOut])
def sales_invoice_returnable(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    """باقی‌ماندهٔ قابلِ برگشتِ هر کالای یک فاکتور فروش."""
    return [ReturnableLineOut(**row) for row in get_returnable_summary(db, invoice_id)]


@router.get("/api/sales-returns", response_model=Page[SalesReturnOut])
def list_sales_returns(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("invoices", "view")),
):
    items, next_cursor = paginate(
        db.query(SalesReturn).options(selectinload(SalesReturn.lines)),
        [SalesReturn.return_date, SalesReturn.number],
        params,
    )
    return Page(items=items, next_cursor=next_cursor)


@router.post("/api/sales-returns", response_model=SalesReturnOut, status_code=201)
def create_sales_return(
    data: SalesReturnIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return post_sales_return(db, data, user)


@router.get("/api/purchase-returns", response_model=Page[PurchaseReturnOut])
def list_purchase_returns(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("invoices", "view")),
):
    items, next_cursor = paginate(
        db.query(PurchaseReturn).options(selectinload(PurchaseReturn.lines)),
        [PurchaseReturn.return_date, PurchaseReturn.number],
        params,
    )
    return Page(items=items, next_cursor=next_cursor)


@router.post("/api/purchase-returns", response_model=PurchaseReturnOut, status_code=201)
def create_purchase_return(
    data: PurchaseReturnIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return post_purchase_return(db, data, user)


@router.get("/api/sales-returns/{return_id}/print", response_class=HTMLResponse)
def print_sales_return(
    return_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("invoices", "view")),
):
    """نمای چاپیِ سندِ برگشت از فروش — همان قالبِ فاکتور با عنوانِ «برگشت از فروش»."""
    sret = db.get(SalesReturn, return_id)
    if sret is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سند برگشت یافت نشد")

    invoice = db.get(SalesInvoice, sret.sales_invoice_id)
    contact = db.get(Contact, invoice.contact_id) if invoice and invoice.contact_id else None
    party_name = contact.name if contact else "مشتری نقدی"
    party_detail = " — ".join(filter(None, [contact.phone, contact.address])) if contact else ""
    items = {i.id: i for i in db.query(Item).filter(Item.id.in_([l.item_id for l in sret.lines])).all()}

    html = render_invoice(
        kind="برگشت از فروش",
        business_name=principal.membership.tenant.name,
        number=sret.number,
        invoice_date=sret.return_date,
        party_name=party_name,
        party_detail=party_detail,
        description=sret.description or (f"بابت فاکتور فروش شماره {invoice.number}" if invoice else ""),
        lines=[
            {
                "name": items[l.item_id].name if l.item_id in items else "",
                "description": l.description,
                "qty": l.qty,
                "unit": items[l.item_id].unit if l.item_id in items else "",
                "unit_price": l.unit_price,
                "discount": 0,
            }
            for l in sret.lines
        ],
        total=sret.total_amount,
        tax_amount=sret.tax_amount,
    )
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})
