from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.inventory import Contact, StockLedger
from app.models.payment import Payment, PaymentRelatedDocument
from app.models.sales_ops import SaleType
from app.models.invoices import PurchaseInvoice, PurchaseInvoiceLine, SalesInvoice, WarehouseReceipt
from app.models.tenant import Membership
from app.models.user import Role, User
from app.pagination import Page, PageParams, paginate
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceOut,
    PurchaseSummaryOut,
    WarehouseReceiptIn,
    WarehouseReceiptOut,
    SalesInvoiceIn,
    SalesInvoiceOut,
    SalesSummaryOut,
)
from app.schemas.voiding import VoidIn, VoidOut
from app.services.idempotency import idempotent
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.reports import get_purchase_summary, get_sales_summary
from decimal import Decimal

from app.services.pdf_invoice import render_invoice_pdf
from app.services.printing import fa_number, render_invoice
from app.services.voiding import void_purchase_invoice, void_sales_invoice
from app.services.warehouse_receipts import (
    create_warehouse_receipt,
    received_by_line,
    void_warehouse_receipt,
)

router = APIRouter(tags=["invoices"])


def _attach_purchase_state(db: Session, invoices: list[PurchaseInvoice]) -> None:
    """تحویل را مشتق می‌کند؛ تسویه تا ساخته‌شدن موتور Allocation باز می‌ماند."""
    if not invoices:
        return
    ids = [invoice.id for invoice in invoices]
    related_payment_counts = dict(
        db.query(PaymentRelatedDocument.document_id, func.count(func.distinct(Payment.id)))
        .join(Payment, Payment.id == PaymentRelatedDocument.payment_id)
        .filter(
            PaymentRelatedDocument.document_type == "purchase_invoice",
            PaymentRelatedDocument.document_id.in_(ids),
            Payment.voided_at.is_(None),
        )
        .group_by(PaymentRelatedDocument.document_id)
        .all()
    )
    legacy_ids = {
        source_id
        for (source_id,) in db.query(StockLedger.source_id)
        .filter(StockLedger.source_type == "purchase_invoice", StockLedger.source_id.in_(ids))
        .distinct()
        .all()
    }
    for invoice in invoices:
        received = received_by_line(db, invoice.id)
        received_total = Decimal(0)
        ordered_total = Decimal(0)
        for line in invoice.lines:
            ordered = Decimal(line.qty)
            got = received.get(line.id, ordered if invoice.id in legacy_ids else Decimal(0))
            line.received_qty = got
            line.remaining_qty = max(ordered - got, Decimal(0))
            received_total += got
            ordered_total += ordered
        invoice.received_total_qty = received_total
        invoice.inventory_status = (
            "not_received" if received_total <= 0 else "fully_received" if received_total >= ordered_total else "partially_received"
        )
        final = Decimal(invoice.total_amount) + Decimal(invoice.tax_amount)
        invoice.final_amount = final
        # PaymentRelatedDocument فقط Reference است. وضعیت مالی وقتی قابل محاسبه
        # می‌شود که موتور Settlement/Allocation با سیاست‌های بازِ §۲۰ ساخته شود.
        invoice.settled_amount = Decimal(0)
        invoice.remaining_amount = final
        invoice.financial_status = "unsettled"
        # شمارش برای Trace است، نه مبنای تسویه؛ مبلغ همچنان فقط کارِ موتور Allocation است.
        invoice.related_payment_count = related_payment_counts.get(invoice.id, 0)
        rate = Decimal(invoice.exchange_rate or 1)
        invoice.transaction_total_amount = (Decimal(invoice.total_amount) / rate).quantize(Decimal("0.01"))
        invoice.transaction_tax_amount = (Decimal(invoice.tax_amount) / rate).quantize(Decimal("0.01"))
        invoice.transaction_final_amount = (final / rate).quantize(Decimal("0.01"))


def _attach_creators(db: Session, invoices: list) -> None:
    """نام و نقشِ ثبت‌کننده را روی هر فاکتور می‌نشاند (برای نمایشِ «چه کسی زد»).

    فیلدها روی خودِ نمونه‌ی ORM ست می‌شوند (mapped نیستند، پس persist نمی‌شوند) و
    Pydantic با from_attributes می‌خواندشان. نقش از memberships (سراسری/بی‌RLS، پس با
    فیلترِ صریحِ tenant_id) گرفته می‌شود؛ همه‌ی فاکتورهای پاسخ در یک مستأجرند.
    """
    ids = {inv.created_by_id for inv in invoices if getattr(inv, "created_by_id", None)}
    if not ids:
        return
    names = {uid: name for uid, name in db.query(User.id, User.name).filter(User.id.in_(ids)).all()}
    roles: dict = {}
    tenant_ids = {inv.tenant_id for inv in invoices}
    for tid in tenant_ids:
        rows = (
            db.query(Membership.user_id, Role.name)
            .join(Role, Role.id == Membership.role_id)
            .filter(Membership.user_id.in_(ids), Membership.tenant_id == tid)
            .all()
        )
        for uid, rname in rows:
            roles[uid] = rname
    for inv in invoices:
        inv.created_by_name = names.get(inv.created_by_id)
        inv.created_by_role = roles.get(inv.created_by_id)


def _attach_brokers(db: Session, invoices: list) -> None:
    """نامِ واسطه را برای نمایش روی فاکتورهای فروش می‌نشاند.

    مثلِ `_attach_creators` روی نمونه‌ی ORM ست می‌شود و persist نمی‌شود. یک کوئری
    برای همه‌ی فاکتورها، نه یکی به‌ازای هر فاکتور.
    """
    ids = {inv.broker_id for inv in invoices if getattr(inv, "broker_id", None)}
    if not ids:
        return
    names = {cid: name for cid, name in db.query(Contact.id, Contact.name).filter(Contact.id.in_(ids)).all()}
    for inv in invoices:
        inv.broker_name = names.get(inv.broker_id)


def _attach_sales_meta(db: Session, invoices: list) -> None:
    """نامِ فروشنده و نوعِ فروش را برای نمایش می‌نشاند.

    هر دو ستون از روزِ اول روی `sales_invoices` بودند و **هیچ‌وقت پر نمی‌شدند**، پس
    هیچ‌جا هم نمایش داده نمی‌شدند. حالا که پر می‌شوند، فهرست باید نشانشان بدهد —
    وگرنه کاربر نمی‌فهمد پورسانت به نامِ چه کسی رفته.
    """
    person_ids = {inv.salesperson_id for inv in invoices if getattr(inv, "salesperson_id", None)}
    if person_ids:
        names = {uid: (name or email) for uid, name, email in
                 db.query(User.id, User.name, User.email).filter(User.id.in_(person_ids)).all()}
        for inv in invoices:
            inv.salesperson_name = names.get(inv.salesperson_id)

    type_ids = {inv.sale_type_id for inv in invoices if getattr(inv, "sale_type_id", None)}
    if type_ids:
        types = {tid: name for tid, name in
                 db.query(SaleType.id, SaleType.name).filter(SaleType.id.in_(type_ids)).all()}
        for inv in invoices:
            inv.sale_type_name = types.get(inv.sale_type_id)


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
    _attach_creators(db, items)
    _attach_brokers(db, items)
    _attach_sales_meta(db, items)
    return Page(items=items, next_cursor=next_cursor)


@router.get("/api/sales-invoices/summary", response_model=SalesSummaryOut)
def sales_summary(
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    """شاخص‌های فروش، محاسبه‌شده سمت سرور (تا کلاینت کلِ فاکتورها را دانلود نکند)."""
    return SalesSummaryOut(**get_sales_summary(db))


@router.post("/api/sales-invoices", response_model=SalesInvoiceOut, status_code=201)
def create_sales_invoice(
    data: SalesInvoiceIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
    #: صفِ آفلاینِ دسکتاپ این سرآیند را می‌فرستد. سقفِ اعتبار سرِ *همگام‌سازی* گرفته
    #: نمی‌شود: آن فروش قبلاً انجام شده و کالایش رفته، و ردّش این‌جا یعنی نابودکردنِ
    #: کارِ فروشنده. تصمیمِ «نفروش» باید در لحظه‌ی فروش گرفته شود.
    #:
    #: این مرزِ امنیتی نیست و لازم هم نیست باشد — قاعده‌ی کسب‌وکار است و کاربر
    #: می‌تواند همان تنظیم را در فرمِ طرف حساب روی «هشدار بده» بگذارد.
    x_cubita_offline_replay: str | None = Header(default=None),
):
    invoice = idempotent(
        db,
        request,
        user,
        operation="create_sales_invoice",
        payload=data,
        run=lambda: post_sales_invoice(
            db, data, user, enforce_credit=not x_cubita_offline_replay
        ),
        replay=lambda rid: db.get(SalesInvoice, rid),
    )
    _attach_creators(db, [invoice])
    _attach_brokers(db, [invoice])
    _attach_sales_meta(db, [invoice])
    return invoice


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
    _attach_creators(db, items)
    _attach_purchase_state(db, items)
    return Page(items=items, next_cursor=next_cursor)


@router.get("/api/purchase-invoices/summary", response_model=PurchaseSummaryOut)
def purchase_summary(
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    """شاخص‌های خرید، محاسبه‌شده سمت سرور."""
    return PurchaseSummaryOut(**get_purchase_summary(db))


@router.get("/api/purchase-price-info/{item_id}")
def purchase_price_info(
    item_id: UUID,
    supplier_id: UUID | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    """آخرین بهای تاریخی کالا، در کل و نزد تأمین‌کننده انتخابی."""
    base = (
        db.query(PurchaseInvoiceLine, PurchaseInvoice)
        .join(PurchaseInvoice, PurchaseInvoice.id == PurchaseInvoiceLine.invoice_id)
        .filter(PurchaseInvoiceLine.item_id == item_id, PurchaseInvoice.voided_at.is_(None))
    )

    def serialize(row):
        if row is None:
            return None
        line, invoice = row
        rate = Decimal(invoice.exchange_rate or 1)
        return {
            "invoice_id": invoice.id,
            "invoice_number": invoice.number,
            "invoice_date": invoice.invoice_date,
            "supplier_id": invoice.contact_id,
            "base_unit_cost": Decimal(line.unit_cost),
            "transaction_unit_cost": (Decimal(line.unit_cost) / rate).quantize(Decimal("0.01")),
            "currency_code": invoice.currency_code or "IRR",
            "exchange_rate": rate,
        }

    latest = base.order_by(PurchaseInvoice.invoice_date.desc(), PurchaseInvoice.created_at.desc()).first()
    supplier_latest = None
    if supplier_id is not None:
        supplier_latest = (
            base.filter(PurchaseInvoice.contact_id == supplier_id)
            .order_by(PurchaseInvoice.invoice_date.desc(), PurchaseInvoice.created_at.desc())
            .first()
        )
    return {"latest": serialize(latest), "supplier_latest": serialize(supplier_latest)}


@router.post("/api/purchase-invoices", response_model=PurchaseInvoiceOut, status_code=201)
def create_purchase_invoice(
    data: PurchaseInvoiceIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    invoice = idempotent(
        db,
        request,
        user,
        operation="create_purchase_invoice",
        payload=data,
        run=lambda: post_purchase_invoice(db, data, user),
        replay=lambda rid: db.get(PurchaseInvoice, rid),
    )
    _attach_creators(db, [invoice])
    _attach_purchase_state(db, [invoice])
    return invoice


@router.get("/api/purchase-invoices/{invoice_id}/warehouse-receipts", response_model=list[WarehouseReceiptOut])
def list_warehouse_receipts(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    if db.get(PurchaseInvoice, invoice_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور خرید یافت نشد")
    return (
        db.query(WarehouseReceipt)
        .options(selectinload(WarehouseReceipt.lines))
        .filter(WarehouseReceipt.purchase_invoice_id == invoice_id)
        .order_by(WarehouseReceipt.receipt_date.desc(), WarehouseReceipt.number.desc())
        .all()
    )


@router.post(
    "/api/purchase-invoices/{invoice_id}/warehouse-receipts",
    response_model=WarehouseReceiptOut,
    status_code=201,
)
def issue_warehouse_receipt(
    invoice_id: UUID,
    data: WarehouseReceiptIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return idempotent(
        db,
        request,
        user,
        operation=f"create_warehouse_receipt:{invoice_id}",
        payload=data,
        run=lambda: create_warehouse_receipt(db, invoice_id, data, user),
        replay=lambda rid: db.get(WarehouseReceipt, rid),
    )


@router.post("/api/warehouse-receipts/{receipt_id}/void", response_model=WarehouseReceiptOut)
def void_receipt(
    receipt_id: UUID,
    data: VoidIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "delete")),
):
    return void_warehouse_receipt(db, receipt_id, reason=data.reason, user=user, void_date=data.void_date)


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
    if db.query(WarehouseReceipt.id).filter(
        WarehouseReceipt.purchase_invoice_id == invoice_id,
        WarehouseReceipt.voided_at.is_(None),
    ).first():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این فاکتور رسید انبار فعال دارد؛ ابتدا رسیدهای وابسته را باطل کنید",
        )
    if db.query(Payment.id).join(
        PaymentRelatedDocument, PaymentRelatedDocument.payment_id == Payment.id
    ).filter(
        PaymentRelatedDocument.document_type == "purchase_invoice",
        PaymentRelatedDocument.document_id == invoice_id,
        Payment.voided_at.is_(None),
    ).first():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این فاکتور اعلامیه پرداخت فعال دارد؛ ابتدا اعلامیه‌های مرتبط را باطل کنید",
        )
    reversal = void_purchase_invoice(db, invoice_id, reason=data.reason, user=user, void_date=data.void_date)
    return VoidOut(reversal_entry_id=reversal.id, reversal_entry_number=reversal.number)


def _print_response(html: str) -> HTMLResponse:
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})


def _party(db: Session, contact_id, fallback: str) -> tuple[str, str]:
    contact = db.get(Contact, contact_id) if contact_id else None
    if contact is None:
        return fallback, ""
    return contact.name, " — ".join(filter(None, [contact.phone, contact.address]))


def _snapshot_party(snapshot: dict, fallback: tuple[str, str]) -> tuple[str, str]:
    """Snapshot خالی یعنی سند قدیمی؛ فقط در آن حالت Master فعلی fallback است."""
    if not snapshot:
        return fallback
    labels = (
        ("شماره ثبت", "registration_no"),
        ("شناسه ملی", "national_id"),
        ("کد اقتصادی", "economic_code"),
        ("شناسه مالیاتی", "tax_id"),
        ("کد پستی", "postal_code"),
        ("تلفن", "phone"),
        ("نشانی", "address"),
    )
    detail = " — ".join(f"{label}: {snapshot[key]}" for label, key in labels if snapshot.get(key))
    return snapshot.get("name") or fallback[0], detail


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
        rounding=invoice.rounding,
        voided_at=invoice.voided_at,
        void_reason=invoice.void_reason,
        currency_line=_currency_line(invoice),
    )


def _purchase_render_kwargs(db: Session, principal: Principal, invoice: PurchaseInvoice) -> dict:
    name, detail = _snapshot_party(
        invoice.supplier_snapshot or {},
        _party(db, invoice.contact_id, "تأمین‌کننده نقدی"),
    )
    buyer_name, buyer_detail = _snapshot_party(
        invoice.buyer_snapshot or {},
        (principal.membership.tenant.name, ""),
    )
    return dict(
        kind="فاکتور خرید",
        business_name=buyer_name,
        business_detail=buyer_detail,
        business_party_label="خریدار",
        number=invoice.number,
        invoice_date=invoice.invoice_date,
        party_name=name,
        party_detail=detail,
        party_label="فروشنده",
        description=" — ".join(filter(None, [
            f"شماره فاکتور تأمین‌کننده: {invoice.supplier_invoice_number}" if invoice.supplier_invoice_number else "",
            invoice.description,
            invoice.description2,
        ])),
        lines=[
            {
                "name": line.item_name_snapshot or line.item.name,
                "description": line.description,
                "qty": line.qty,
                "unit": line.unit_snapshot or line.item.unit,
                "unit_price": line.unit_cost,
                "discount": line.discount,
            }
            for line in invoice.lines
        ],
        total=invoice.total_amount,
        tax_amount=invoice.tax_amount,
        total_discount=invoice.total_discount,
        total_additions=invoice.total_additions,
        total_duties=invoice.total_duties,
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
