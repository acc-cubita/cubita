from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.inventory import Contact, Item
from app.models.invoices import PurchaseInvoice, SalesInvoice
from app.models.returns import PurchaseReturn, SalesReturn, SalesReturnReason
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.returns import (
    ReceiptReturnableLineOut,
    PurchaseReturnIn,
    PurchaseReturnOut,
    ReturnableLineOut,
    SalesReturnIn,
    SalesReturnOut,
    SalesReturnReasonIn,
    SalesReturnReasonOut,
    VoidIn,
)
from app.services import voiding
from app.services.idempotency import idempotent
from app.services.printing import render_invoice, render_warehouse_document
from app.services.returns import (
    attach_return_state,
    get_purchase_returnable_summary,
    get_receipt_returnable_summary,
    get_returnable_summary,
    post_purchase_return,
    post_sales_return,
    return_print_projection,
)

router = APIRouter(tags=["returns"])


@router.get("/api/sales-invoices/{invoice_id}/returnable", response_model=list[ReturnableLineOut])
def sales_invoice_returnable(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    """باقی‌ماندهٔ قابلِ برگشتِ هر کالای یک فاکتور فروش."""
    return [ReturnableLineOut(**row) for row in get_returnable_summary(db, invoice_id)]


@router.get(
    "/api/warehouse-receipts/{receipt_id}/returnable",
    response_model=list[ReceiptReturnableLineOut],
)
def warehouse_receipt_returnable(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    """پنجره‌ی «مبنا»: از این رسید چه مقدار هنوز قابلِ برگشت است.

    **چرا از رسید و نه از فاکتور:** فاکتورِ خرید از مهاجرتِ ۰۱۲۹ انبار ندارد —
    کالا با رسید وارد می‌شود. و اگر یک کالا چند بار با بهای متفاوت وارد شده
    باشد، فقط رسید می‌داند کدام ورود را داریم برمی‌گردانیم.
    """
    return [ReceiptReturnableLineOut(**row) for row in get_receipt_returnable_summary(db, receipt_id)]


@router.get("/api/purchase-invoices/{invoice_id}/returnable", response_model=list[ReturnableLineOut])
def purchase_invoice_returnable(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    """باقی‌ماندهٔ قابلِ برگشتِ هر کالای یک فاکتور خرید."""
    return [ReturnableLineOut(**row) for row in get_purchase_returnable_summary(db, invoice_id)]


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
    attach_return_state(db, items)
    return Page(items=items, next_cursor=next_cursor)


@router.post("/api/sales-returns", response_model=SalesReturnOut, status_code=201)
def create_sales_return(
    data: SalesReturnIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    """§۵۴ — همان کلید، همان برگشت. تلاشِ دوباره‌ی شبکه سندِ دوم نمی‌سازد."""
    sales_return = idempotent(
        db, request, user,
        operation="create_sales_return",
        payload=data,
        run=lambda: post_sales_return(db, data, user),
        replay=lambda rid: db.get(SalesReturn, rid),
    )
    attach_return_state(db, [sales_return])
    return sales_return


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
    attach_return_state(db, items)
    return Page(items=items, next_cursor=next_cursor)


@router.post("/api/purchase-returns", response_model=PurchaseReturnOut, status_code=201)
def create_purchase_return(
    data: PurchaseReturnIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    purchase_return = idempotent(
        db, request, user,
        operation="create_purchase_return",
        payload=data,
        run=lambda: post_purchase_return(db, data, user),
        replay=lambda rid: db.get(PurchaseReturn, rid),
    )
    attach_return_state(db, [purchase_return])
    return purchase_return


# ═══════════════════ ابطالِ برگشت (§۷۱–§۷۸) ═══════════════════
#
# تا امروز راهی نبود. و `voiding._guard_no_active_returns` هنگامِ ابطالِ فاکتور
# می‌گفت «اول سندِ برگشت را برگردانید» — کاری که هیچ مسیری نداشت، پس یک برگشتِ
# اشتباهی فاکتورش را برای همیشه قفل می‌کرد.
#
# مجوز `("accounting", "delete")` است نه `invoices` — همان مجوزی که ابطالِ خودِ
# فاکتور می‌خواهد. ابطال، ثبتِ تازه نیست.


@router.post("/api/sales-returns/{return_id}/void", response_model=SalesReturnOut)
def void_sales_return(
    return_id: UUID,
    data: VoidIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "delete")),
):
    voiding.void_sales_return(
        db, return_id, reason=data.reason, user=user, void_date=data.void_date
    )
    sales_return = db.get(SalesReturn, return_id)
    attach_return_state(db, [sales_return])
    return sales_return


@router.post("/api/purchase-returns/{return_id}/void", response_model=PurchaseReturnOut)
def void_purchase_return(
    return_id: UUID,
    data: VoidIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "delete")),
):
    voiding.void_purchase_return(
        db, return_id, reason=data.reason, user=user, void_date=data.void_date
    )
    purchase_return = db.get(PurchaseReturn, return_id)
    attach_return_state(db, [purchase_return])
    return purchase_return


# ═══════════════════ مِسترِ علتِ برگشتِ کالا (§۲۴ §۲۵) ═══════════════════


@router.get("/api/sales-return-reasons", response_model=list[SalesReturnReasonOut])
def list_sales_return_reasons(
    only_active: bool = False,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    """`only_active` برای فرمِ ثبت است؛ فهرستِ کامل برای صفحه‌ی مدیریت.

    سندِ تاریخی علتِ غیرفعالش را نگه می‌دارد (§۸۵)، پس فهرستِ کامل هم لازم است.
    """
    query = db.query(SalesReturnReason)
    if only_active:
        query = query.filter(SalesReturnReason.is_active.is_(True))
    return query.order_by(SalesReturnReason.title).all()


@router.post("/api/sales-return-reasons", response_model=SalesReturnReasonOut, status_code=201)
def create_sales_return_reason(
    data: SalesReturnReasonIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "create")),
):
    reason = SalesReturnReason(
        title=data.title.strip(), title2=data.title2.strip(), is_active=data.is_active
    )
    db.add(reason)
    db.flush()
    return reason


@router.patch("/api/sales-return-reasons/{reason_id}", response_model=SalesReturnReasonOut)
def update_sales_return_reason(
    reason_id: UUID,
    data: SalesReturnReasonIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "create")),
):
    """غیرفعال می‌کند، حذف نمی‌کند — سندهای تاریخی علتشان را از دست نمی‌دهند."""
    reason = db.get(SalesReturnReason, reason_id)
    if reason is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "علتِ برگشت یافت نشد")
    reason.title = data.title.strip()
    reason.title2 = data.title2.strip()
    reason.is_active = data.is_active
    db.flush()
    return reason


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


@router.get("/api/purchase-returns/{return_id}/print", response_class=HTMLResponse)
def print_purchase_return(
    return_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("invoices", "view")),
):
    """نمای چاپیِ سندِ برگشت از خرید — همان قالب با عنوانِ «برگشت از خرید»."""
    pret = db.get(PurchaseReturn, return_id)
    if pret is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سند برگشت یافت نشد")

    #: برگشتی که به رسید لنگر زده، برگه‌ی **انبار** می‌گیرد (انبار، تحویل‌گیرنده،
    #: حمل، خالص و خالص توافقی) — نه قالبِ فاکتور که هیچ‌کدام را ندارد.
    if pret.warehouse_receipt_id is not None:
        html = render_warehouse_document(
            business_name=principal.membership.tenant.name, **return_print_projection(db, pret)
        )
        return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})

    invoice = db.get(PurchaseInvoice, pret.purchase_invoice_id) if pret.purchase_invoice_id else None
    contact = db.get(Contact, invoice.contact_id) if invoice and invoice.contact_id else None
    party_name = contact.name if contact else "تأمین‌کننده نقدی"
    party_detail = " — ".join(filter(None, [contact.phone, contact.address])) if contact else ""
    items = {i.id: i for i in db.query(Item).filter(Item.id.in_([l.item_id for l in pret.lines])).all()}

    html = render_invoice(
        kind="برگشت از خرید",
        business_name=principal.membership.tenant.name,
        number=pret.number,
        invoice_date=pret.return_date,
        party_name=party_name,
        party_detail=party_detail,
        description=pret.description or (f"بابت فاکتور خرید شماره {invoice.number}" if invoice else ""),
        lines=[
            {
                "name": items[l.item_id].name if l.item_id in items else "",
                "description": l.description,
                "qty": l.qty,
                "unit": items[l.item_id].unit if l.item_id in items else "",
                "unit_price": l.unit_cost,
                "discount": 0,
            }
            for l in pret.lines
        ],
        total=pret.total_amount,
        tax_amount=pret.tax_amount,
    )
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})
