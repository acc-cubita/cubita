from datetime import date
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
from pydantic import BaseModel

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.accounting import Account, JournalEntry
from app.models.inventory import Contact, Item, StockLedger
from app.models.payment import Payment, PaymentRelatedDocument
from app.models.receipt import Receipt, ReceiptRelatedDocument
from app.models.sales_ops import SaleType
from app.models.invoices import (
    PurchaseInvoice, PurchaseInvoiceLine, SalesInvoice, WarehouseIssue, WarehouseReceipt,
)
from app.models.tenant import Membership, Tenant
from app.models.user import Role, User
from app.pagination import Page, PageParams, paginate
from app.schemas.invoices import (
    ApplyProductionPricesIn,
    ApplyProductionPricesOut,
    PurchaseInvoiceIn,
    PurchaseInvoiceOut,
    PurchaseSummaryOut,
    ReceiptPaymentContextOut,
    WarehouseReceiptIn,
    WarehouseReceiptOut,
    WarehouseIssueIn,
    WarehouseIssueOut,
    SalesInvoiceIn,
    SalesInvoiceOut,
    SalesSummaryOut,
    UnpricedOutputOut,
)
from app.schemas.voiding import VoidIn, VoidOut
from app.services import production_pricing, sales_posting
from app.services.idempotency import idempotent
from app.services.open_items import settled_amounts
from app.services.purchase_deductions import totals_by_nature
from app.services.inventory import duplicate_purchase_invoice_draft, post_purchase_invoice, post_sales_invoice
from app.services.reports import get_purchase_summary, get_sales_summary
from app.services.sales_invoices import (
    attach_sales_state,
    cancel_unposted_sales_invoice,
    finalize_immediate_sale,
    issue_sales_invoice_journal,
)
from decimal import Decimal

from app.services.pdf_invoice import render_invoice_pdf
from app.services.printing import fa_number, render_invoice, render_warehouse_document
from app.services.voiding import void_purchase_invoice, void_sales_invoice
from app.services.warehouse_receipts import (
    create_warehouse_receipt,
    receipt_payment_context,
    receipt_print_projection,
    received_by_line,
    void_warehouse_receipt,
)
from app.services.warehouse_issues import (
    attach_issue_accounts,
    create_warehouse_issue,
    post_sales_invoice_from_issue,
    void_warehouse_issue,
)

router = APIRouter(tags=["invoices"])


def _attach_purchase_state(db: Session, invoices: list[PurchaseInvoice]) -> None:
    """تحویل، تسویه، کسورات و سندِ هر فاکتورِ خرید — همه مشتق، هیچ‌کدام ذخیره‌شده نه.

    **مانده از بدهیِ واقعی به تأمین‌کننده است، نه از جمعِ فاکتور.** در فاکتور خرید
    خدمات بخشی از مبلغ کسرِ مالیات تکلیفی و بیمه است و به تأمین‌کننده داده نمی‌شود.
    تا امروز مانده همیشه «جمعِ فاکتور» بود و میان‌برِ «اعلامیه پرداخت» همان را
    پیشنهاد می‌داد — یعنی پرداختِ کسورات به فروشنده.

    **تسویه‌شده** جمعِ تخصیص‌های باطل‌نشده‌ی موتورِ تسویه است (از ۰۱۱۴). اعلامیه‌ی
    پرداخت فقط مرجع است و مبلغی را «تسویه‌شده» اعلام نمی‌کند.

    **تحویل فقط کالا را می‌شمارد.** ردیفِ خدمت رسید انبار ندارد؛ شمردنش فاکتوری را
    که فقط خدمت دارد برای همیشه «تحویل‌نشده» نشان می‌داد.
    """
    if not invoices:
        return
    ids = [invoice.id for invoice in invoices]
    item_ids = {line.item_id for invoice in invoices for line in invoice.lines}
    service_items = {
        item_id
        for (item_id,) in db.query(Item.id).filter(Item.id.in_(item_ids), Item.is_service.is_(True)).all()
    } if item_ids else set()
    account_ids = {
        line.expense_account_id for invoice in invoices for line in invoice.lines if line.expense_account_id
    } | {row.account_id for invoice in invoices for row in invoice.deductions}
    accounts = (
        {account.id: account for account in db.query(Account).filter(Account.id.in_(account_ids)).all()}
        if account_ids
        else {}
    )
    journal_ids = {invoice.journal_entry_id for invoice in invoices if invoice.journal_entry_id}
    entries = (
        {
            entry_id: (number, entry_date)
            for entry_id, number, entry_date in db.query(
                JournalEntry.id, JournalEntry.number, JournalEntry.entry_date
            ).filter(JournalEntry.id.in_(journal_ids))
        }
        if journal_ids
        else {}
    )
    settled_by_invoice = settled_amounts(db, [("purchase_invoice", invoice_id) for invoice_id in ids])
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
            account = accounts.get(line.expense_account_id) if line.expense_account_id else None
            line.expense_account_code = account.code if account else ""
            line.expense_account_name = account.name if account else ""
            if line.item_id in service_items:
                line.received_qty = Decimal(0)
                line.remaining_qty = Decimal(0)
                continue
            ordered = Decimal(line.qty)
            got = received.get(line.id, ordered if invoice.id in legacy_ids else Decimal(0))
            line.received_qty = got
            line.remaining_qty = max(ordered - got, Decimal(0))
            received_total += got
            ordered_total += ordered
        invoice.received_total_qty = received_total
        invoice.inventory_status = (
            "not_applicable" if ordered_total <= 0
            else "not_received" if received_total <= 0
            else "fully_received" if received_total >= ordered_total
            else "partially_received"
        )
        final = Decimal(invoice.total_amount) + Decimal(invoice.tax_amount)
        invoice.final_amount = final
        payable = invoice.payable_amount
        settled = settled_by_invoice.get(("purchase_invoice", invoice.id), Decimal(0))
        invoice.settled_amount = settled
        invoice.remaining_amount = max(payable - settled, Decimal(0))
        invoice.financial_status = (
            "unsettled" if settled <= 0 else "fully_settled" if settled >= payable else "partially_settled"
        )
        totals = totals_by_nature(invoice.deductions)
        invoice.withholding_total = totals["withholding_tax"]
        invoice.insurance_total = totals["insurance"]
        for row in invoice.deductions:
            account = accounts.get(row.account_id)
            row.account_code = account.code if account else ""
            row.account_name = account.name if account else ""
        invoice.journal_entry_number, invoice.journal_entry_date = entries.get(
            invoice.journal_entry_id, (None, None)
        )
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
    contact_id: UUID | None = Query(None, description="فقط فاکتورهای این طرف حساب"),
    date_from: date | None = Query(None, description="از این تاریخ (شامل خودش)"),
    date_to: date | None = Query(None, description="تا این تاریخ (شامل خودش)"),
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("invoices", "view")),
):
    """دفترِ فاکتورهای فروش، با فیلترِ **سمتِ سرور**.

    تا امروز این اندپوینت فقط `limit` و `cursor` می‌گرفت، پس هر صفحه‌ای که
    می‌خواست فاکتورهای یک مشتری یا یک بازه را نشان دهد **کلِ دفتر را دانلود
    می‌کرد** و در مرورگر فیلتر می‌کرد — همان چیزی که قراردادِ صفحه‌های کوبیتا
    صریحاً منع می‌کند، و با اولین کسب‌وکارِ چندساله از کار می‌افتد.

    هر سه پارامتر اختیاری‌اند و **نبودشان یعنی رفتارِ دیروز**: پاسخِ بی‌فیلتر
    دقیقاً همان است که بود، پس هیچ فراخوانِ موجودی نمی‌شکند.
    """
    query = db.query(SalesInvoice).options(selectinload(SalesInvoice.lines))
    if contact_id is not None:
        query = query.filter(SalesInvoice.contact_id == contact_id)
    if date_from is not None:
        query = query.filter(SalesInvoice.invoice_date >= date_from)
    if date_to is not None:
        query = query.filter(SalesInvoice.invoice_date <= date_to)
    items, next_cursor = paginate(
        query,
        [SalesInvoice.invoice_date, SalesInvoice.number],
        params,
    )
    _attach_creators(db, items)
    _attach_brokers(db, items)
    _attach_sales_meta(db, items)
    attach_sales_state(db, items)
    return Page(items=items, next_cursor=next_cursor)


@router.get("/api/sales-invoices/summary", response_model=SalesSummaryOut)
def sales_summary(
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    """شاخص‌های فروش، محاسبه‌شده سمت سرور (تا کلاینت کلِ فاکتورها را دانلود نکند)."""
    return SalesSummaryOut(**get_sales_summary(db))


# ─────────────────── سیاستِ صدورِ فاکتور فروش ───────────────────


class SalesPostingOut(BaseModel):
    mode: str
    options: list[dict]
    #: True یعنی کاربر خودش انتخاب کرده؛ False یعنی هنوز روی پیش‌فرضِ سرویس است.
    is_explicit: bool


class SalesPostingIn(BaseModel):
    mode: str


def _sales_posting_out(tenant: Tenant) -> SalesPostingOut:
    return SalesPostingOut(
        mode=tenant.sales_invoice_posting or sales_posting.DEFAULT_POSTING_MODE,
        is_explicit=tenant.sales_invoice_posting is not None,
        options=[
            {
                "key": key,
                "label": sales_posting.POSTING_MODE_LABELS[key],
                "hint": sales_posting.POSTING_MODE_HINTS[key],
                "effects": sales_posting.POSTING_MODE_EFFECTS[key],
                "is_default": key == sales_posting.DEFAULT_POSTING_MODE,
            }
            for key in sales_posting.POSTING_MODES
        ],
    )


def _posting_tenant(db: Session, principal: Principal) -> Tenant:
    tenant = db.get(Tenant, principal.tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کسب‌وکار یافت نشد")
    return tenant


@router.get("/api/sales-invoice-posting", response_model=SalesPostingOut)
def get_sales_invoice_posting(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("invoices", "view")),
):
    """«ثبت فاکتور» سند و خروجِ انبار را هم بزند یا نه؟"""
    return _sales_posting_out(_posting_tenant(db, principal))


@router.patch("/api/sales-invoice-posting", response_model=SalesPostingOut)
def set_sales_invoice_posting(
    data: SalesPostingIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    #: تصمیمی در سطحِ کلِ کسب‌وکار است، نه ویرایشِ یک فاکتور — پس مالک و حسابدار،
    #: نه هر کسی که مجوزِ ثبتِ فاکتور دارد. (همان تاپلی که کنترلِ شماره‌ی چک دارد:
    #: `approve` از «*»ِ مالک می‌آید و `update` دستِ حسابدار است.)
    _=Depends(require_permission("invoices", ("approve", "update"))),
):
    """تغییرِ سیاست.

    **روی فاکتورهای گذشته اثری ندارد.** فاکتوری که دیروز بدونِ سند ثبت شده، با
    عوض‌کردنِ این گزینه سند نمی‌گیرد؛ سندش را از فهرست صادر می‌کنید. و برعکس،
    رفتنِ به «دومرحله‌ای» سندِ فاکتورهای دیروز را پس نمی‌گیرد — تاریخ بازنویسی
    نمی‌شود.
    """
    tenant = _posting_tenant(db, principal)
    try:
        sales_posting.set_posting_mode(tenant, data.mode)
    except ValueError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err)) from err
    db.flush()
    return _sales_posting_out(tenant)


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
    #: **«ثبت فاکتور» چه‌قدر کار انجام دهد، انتخابِ خودِ کسب‌وکار است.**
    #:
    #: `immediate` (پیش‌فرض) سند و خروج را همان لحظه می‌زند — رفتاری که کاربران
    #: سال‌ها داشته‌اند. `staged` فقط سندِ تجاری را ثبت می‌کند و آن دو گام را به
    #: فهرستِ فاکتورها می‌سپارد، برای فروشی که تحویلش روزِ دیگری است.
    #:
    #: مسیر یکی است در هر دو حالت؛ فقط خودکار بودنِ دو گام عوض می‌شود.
    immediate = sales_posting.posts_immediately(db)
    if x_cubita_offline_replay:
        from app.services import valuation

        #: همان استدلالِ سقفِ اعتبار برای گاردِ خطِ زمانِ موجودی: فروشِ آفلاینِ دیروز
        #: وقتی همگام می‌شود که خریدِ امروز پیش از آن ثبت شده. گاردِ موجودیِ امروز
        #: سر جایش است؛ اثرِ ترتیب در «ارزش‌گذاریِ منقضی» دیده می‌شود.
        db.info[valuation.LENIENT_TIMELINE] = True
    invoice = idempotent(
        db,
        request,
        user,
        operation="create_sales_invoice",
        payload=data,
        #: فاکتوری که از خروجِ ثبت‌شده ساخته می‌شود هیچ‌وقت خودش موجودی کم نمی‌کند —
        #: حتی در سیاستِ «خودکار» (§۱۵). سندِ درآمد و طلب اما همان سیاست را دارد.
        run=lambda: (
            post_sales_invoice_from_issue(
                db, data, user, enforce_credit=not x_cubita_offline_replay, issue_accounting=immediate,
            )
            if data.source_warehouse_issue_id
            else post_sales_invoice(
                db, data, user, enforce_credit=not x_cubita_offline_replay,
                move_inventory=immediate, issue_accounting=immediate,
            )
        ),
        replay=lambda rid: db.get(SalesInvoice, rid),
    )
    _attach_creators(db, [invoice])
    _attach_brokers(db, [invoice])
    _attach_sales_meta(db, [invoice])
    attach_sales_state(db, [invoice])
    return invoice


@router.post("/api/sales-invoices/{invoice_id}/journal", response_model=SalesInvoiceOut)
def issue_sales_journal(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    issue_sales_invoice_journal(db, invoice_id, user)
    invoice = db.get(SalesInvoice, invoice_id)
    _attach_creators(db, [invoice])
    _attach_brokers(db, [invoice])
    _attach_sales_meta(db, [invoice])
    attach_sales_state(db, [invoice])
    return invoice


@router.post("/api/sales-invoices/immediate", response_model=SalesInvoiceOut, status_code=201)
def create_immediate_sales_invoice(
    data: SalesInvoiceIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    """فروش یک‌کلیکی POS؛ تراکنش واحد، اما با فاکتور/سند/خروج مستقل."""
    if data.warehouse_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "انبار فروش فوری الزامی است")
    if data.source_warehouse_issue_id:
        #: فروشِ فوری خودش خروج می‌سازد؛ فاکتور از روی خروجِ موجود مسیرِ عادی را دارد.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "فاکتورِ ساخته‌شده از خروج انبار از مسیرِ فروشِ فوری ثبت نمی‌شود"
        )

    def run() -> SalesInvoice:
        invoice = post_sales_invoice(
            db, data, user, move_inventory=False, issue_accounting=False,
        )
        finalize_immediate_sale(db, invoice, data.warehouse_id, user)
        return invoice

    invoice = idempotent(
        db,
        request,
        user,
        operation="create_immediate_sales_invoice",
        payload=data,
        run=run,
        replay=lambda rid: db.get(SalesInvoice, rid),
    )
    _attach_creators(db, [invoice])
    _attach_brokers(db, [invoice])
    _attach_sales_meta(db, [invoice])
    attach_sales_state(db, [invoice])
    return invoice


@router.get("/api/sales-invoices/{invoice_id}/warehouse-issues", response_model=list[WarehouseIssueOut])
def list_warehouse_issues(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    if db.get(SalesInvoice, invoice_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور فروش یافت نشد")
    issues = (
        db.query(WarehouseIssue).options(selectinload(WarehouseIssue.lines))
        .filter(WarehouseIssue.sales_invoice_id == invoice_id)
        .order_by(WarehouseIssue.issue_date.desc(), WarehouseIssue.number.desc()).all()
    )
    #: همان «حساب معین»ی که فهرستِ خروج‌ها نشان می‌دهد — دو مسیر، یک جواب.
    attach_issue_accounts(db, issues)
    return issues


@router.post(
    "/api/sales-invoices/{invoice_id}/warehouse-issues",
    response_model=WarehouseIssueOut, status_code=201,
)
def issue_sales_warehouse(
    invoice_id: UUID, data: WarehouseIssueIn, request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "create")),
):
    return idempotent(
        db, request, user, operation=f"create_warehouse_issue:{invoice_id}", payload=data,
        run=lambda: create_warehouse_issue(db, invoice_id, data, user),
        replay=lambda rid: db.get(WarehouseIssue, rid),
    )


@router.post("/api/warehouse-issues/{issue_id}/void", response_model=WarehouseIssueOut)
def void_sales_warehouse_issue(
    issue_id: UUID, data: VoidIn, db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "delete")),
):
    return void_warehouse_issue(db, issue_id, reason=data.reason, user=user, void_date=data.void_date)


@router.get("/api/purchase-invoices", response_model=Page[PurchaseInvoiceOut])
def list_purchase_invoices(
    kind: str | None = None,
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("invoices", "view")),
):
    """`kind`: `goods` (فاکتور خرید) یا `service` (فاکتور خرید خدمات)؛ خالی = هر دو."""
    query = db.query(PurchaseInvoice).options(
        selectinload(PurchaseInvoice.lines), selectinload(PurchaseInvoice.deductions)
    )
    if kind is not None:
        if kind not in ("goods", "service"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوعِ فاکتور خرید نامعتبر است")
        query = query.filter(PurchaseInvoice.kind == kind)
    #: `id` کلیدِ سوم است چون از ۰۱۴۱ هر نوع سریِ شماره‌ی خودش را دارد: «فاکتور ۵» کالا
    #: و «فاکتور ۵» خدمات در یک روز، با کرسرِ (تاریخ، شماره) یکی از دو صفحه گم می‌شد.
    items, next_cursor = paginate(
        query,
        [PurchaseInvoice.invoice_date, PurchaseInvoice.number, PurchaseInvoice.id],
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


@router.get("/api/purchase-invoices/{invoice_id}/duplicate")
def duplicate_purchase_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "create")),
):
    """پیش‌نویسِ امنِ فاکتور تازه؛ این درخواست هیچ رکوردی نمی‌نویسد."""
    return duplicate_purchase_invoice_draft(db, invoice_id)


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
    """رسید از دلِ یک فاکتورِ خرید — گردشِ قدیمی، دست‌نخورده."""
    return idempotent(
        db,
        request,
        user,
        operation=f"create_warehouse_receipt:{invoice_id}",
        payload=data,
        run=lambda: create_warehouse_receipt(db, invoice_id, data, user),
        replay=lambda rid: db.get(WarehouseReceipt, rid),
    )


@router.get("/api/warehouse-receipts", response_model=Page[WarehouseReceiptOut])
def list_all_warehouse_receipts(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    receipt_type: str | None = None,
    warehouse_id: UUID | None = None,
    contact_id: UUID | None = None,
    _=Depends(require_permission("invoices", "view")),
):
    """فهرستِ همه‌ی رسیدهای انبار (§۴۳).

    تا امروز رسید فقط از دلِ فاکتورش دیده می‌شد؛ رسیدِ مستقیم اصلاً فاکتوری
    ندارد که زیرش پیدا شود. پس رسید باید موجودیتِ قابلِ جست‌وجوی خودش باشد، نه
    یک حرکتِ ناشناس در دفترِ انبار.
    """
    query = db.query(WarehouseReceipt).options(selectinload(WarehouseReceipt.lines))
    if receipt_type:
        query = query.filter(WarehouseReceipt.receipt_type == receipt_type)
    if warehouse_id:
        query = query.filter(WarehouseReceipt.warehouse_id == warehouse_id)
    if contact_id:
        query = query.filter(WarehouseReceipt.contact_id == contact_id)
    items, next_cursor = paginate(
        query, [WarehouseReceipt.receipt_date, WarehouseReceipt.id], params
    )
    return Page(items=items, next_cursor=next_cursor)


@router.post("/api/warehouse-receipts", response_model=WarehouseReceiptOut, status_code=201)
def create_direct_warehouse_receipt(
    data: WarehouseReceiptIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    """رسیدِ مستقل — با یا بدونِ فاکتورِ خرید (§۹).

    **بدونِ فاکتور یک سناریوی واقعی است، نه یک حالتِ خطا:** خریدی که فاکتورش
    بعداً می‌آید یا اصلاً نمی‌آید. چنین رسیدی خودش سندِ حسابداری می‌زند، چون
    هیچ سندِ دیگری این خرید را نمی‌شناسد.

    **idempotent، چون سند و حرکتِ انبار می‌سازد.** تکرارِ شبکه‌ای نباید رسیدِ دوم،
    ورودِ دوباره‌ی کالا و سندِ حسابداریِ دوم بسازد.
    """
    return idempotent(
        db,
        request,
        user,
        operation="create_direct_warehouse_receipt",
        payload=data,
        run=lambda: create_warehouse_receipt(db, None, data, user),
        replay=lambda rid: db.get(WarehouseReceipt, rid),
    )


@router.get("/api/warehouse-receipts/unpriced", response_model=list[UnpricedOutputOut])
def list_unpriced_outputs(
    warehouse_id: UUID,
    date_from: date,
    date_to: date,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    """ورودی‌های بی‌فیِ یک انبار در یک بازه.

    رسیدِ مستقیم می‌تواند بی فی ثبت شود — کالایی که خارج از سیستم تهیه شده و
    بهایش هنوز معلوم نیست. تا وقتی فی نخورَد، آن کالا در انبار هست و ارزشش صفر
    است؛ این فهرست همان‌ها را نشان می‌دهد.
    """
    return production_pricing.unpriced_outputs(
        db, warehouse_id=warehouse_id, date_from=date_from, date_to=date_to
    )


@router.post(
    "/api/warehouse-receipts/apply-prices", response_model=ApplyProductionPricesOut
)
def apply_unpriced_prices(
    data: ApplyProductionPricesIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    """فی را روی ردیف‌های بی‌فیِ دامنه می‌نشاند و سندِ نخورده را می‌زند.

    **حرکتِ انبارِ تازه‌ای ساخته نمی‌شود** — مقدار سرِ رسید وارد شده و این‌جا فقط
    بهای همان حرکت پر می‌شود.

    idempotent است، ولی محافظتِ اصلی از خودِ داده می‌آید: فقط ردیفِ **بی‌فی**
    قیمت می‌گیرد، پس اجرای دوباره چیزی برای انجام‌دادن پیدا نمی‌کند.
    """
    return idempotent(
        db,
        request,
        user,
        operation="apply_receipt_prices",
        payload=data,
        run=lambda: production_pricing.apply_prices(
            db,
            warehouse_id=data.warehouse_id,
            date_from=data.date_from,
            date_to=data.date_to,
            prices={row.item_id: row.unit_cost for row in data.prices},
            user=user,
        ),
        replay=lambda _rid: {"receipts": 0, "lines": 0, "value": Decimal(0)},
        resource_id=lambda _result: uuid4(),
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
    #: **گاردِ «اول خروج را باطل کنید» فقط وقتی معنی دارد که کاربر خودش خروج را
    #: ساخته باشد.**
    #:
    #: فلسفه‌اش این است که کسی ناخواسته حرکتِ انبارِ یک سندِ مستقل را برنگرداند.
    #: ولی در سیاستِ «خودکار»، خروج را *سیستم* به‌عنوان بخشی از همان «ثبت فاکتور»
    #: ساخته؛ کاربر سندی نمی‌بیند که بخواهد آگاهانه باطلش کند، و این گارد فقط
    #: یک بن‌بست می‌شود — همان بن‌بستی که فصلِ «فاکتور برگشتی» یکی‌اش را بست.
    #: `void_sales_invoice` خودش خروج‌های فعال را آبشاری باطل می‌کند.
    #: فقط خروجی که از خودِ فاکتور ساخته شده. خروجِ **مستقلی** که بعداً فاکتور
    #: گرفته با ابطالِ فاکتور جدا می‌شود، نه باطل — کالا واقعاً رفته است.
    if not sales_posting.posts_immediately(db) and db.query(WarehouseIssue.id).filter(
        WarehouseIssue.sales_invoice_id == invoice_id,
        WarehouseIssue.voided_at.is_(None),
        WarehouseIssue.origin == "invoice",
    ).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "این فاکتور خروج انبار فعال دارد؛ ابتدا خروج را باطل کنید")
    if db.query(Receipt.id).join(
        ReceiptRelatedDocument, ReceiptRelatedDocument.receipt_id == Receipt.id
    ).filter(
        ReceiptRelatedDocument.document_type == "sales_invoice",
        ReceiptRelatedDocument.document_id == invoice_id,
        Receipt.voided_at.is_(None),
    ).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "این فاکتور رسید دریافت فعال دارد؛ ابتدا رسید مرتبط را باطل کنید")
    invoice = db.get(SalesInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور فروش یافت نشد")
    if invoice.journal_entry_id is None:
        cancel_unposted_sales_invoice(db, invoice_id, reason=data.reason, user=user)
        return VoidOut(reversal_entry_id=None, reversal_entry_number=None)
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
    grand = (
        Decimal(str(invoice.total_amount)) + Decimal(str(invoice.tax_amount))
        + Decimal(str(getattr(invoice, "total_additions", 0)))
        + Decimal(str(getattr(invoice, "total_duties", 0)))
        + Decimal(str(getattr(invoice, "rounding", 0)))
    )
    foreign = (grand / rate).quantize(Decimal("0.01")) if rate else Decimal(0)
    return (
        f"ارز فاکتور: {invoice.currency_code} — نرخ برابری: {fa_number(rate)} ریال — "
        f"معادل: {fa_number(foreign)} {invoice.currency_code}"
    )


def _sales_render_kwargs(db: Session, principal: Principal, invoice: SalesInvoice) -> dict:
    name, detail = _snapshot_party(
        invoice.customer_snapshot or {}, _party(db, invoice.contact_id, "مشتری"),
    )
    seller_name, seller_detail = _snapshot_party(
        invoice.seller_snapshot or {}, (principal.membership.tenant.name, ""),
    )
    return dict(
        kind="فاکتور فروش",
        business_name=seller_name,
        business_detail=seller_detail,
        number=invoice.number,
        invoice_date=invoice.invoice_date,
        party_name=name,
        party_detail=detail,
        description=invoice.description,
        lines=[
            {
                "name": line.item_name_snapshot or line.item.name,
                "description": line.description,
                "qty": line.qty,
                "unit": line.unit_snapshot or line.item.unit,
                "unit_price": line.unit_price,
                "discount": line.discount,
            }
            for line in invoice.lines
        ],
        total=invoice.total_amount,
        tax_amount=invoice.tax_amount,
        total_discount=invoice.total_discount,
        total_additions=invoice.total_additions,
        total_duties=invoice.total_duties,
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
    service = invoice.kind == "service"
    return dict(
        kind="فاکتور خرید خدمات" if service else "فاکتور خرید",
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
        #: کسورات از همان Snapshotِ ذخیره‌شده می‌آیند، نه از نرخِ امروزِ نوعِ کسر —
        #: چاپ منبعِ مالیِ تازه‌ای نیست.
        deductions=[(row.name_snapshot, Decimal(row.amount)) for row in invoice.deductions],
        lines=[
            {
                #: برگه‌ی خدمات «کد خدمت» را هم نشان می‌دهد.
                "name": (
                    f"{line.item_code_snapshot} — {line.item_name_snapshot or line.item.name}"
                    if service and line.item_code_snapshot
                    else line.item_name_snapshot or line.item.name
                ),
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


@router.get("/api/warehouse-receipts/{receipt_id}/print", response_class=HTMLResponse)
def print_warehouse_receipt(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("invoices", "view")),
):
    """برگه‌ی چاپیِ رسید انبار — Projectionِ همان سند، نه مدلِ مالیِ دوم (§۴۲)."""
    receipt = db.get(WarehouseReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "رسید انبار یافت نشد")
    return _print_response(
        render_warehouse_document(
            business_name=principal.membership.tenant.name, **receipt_print_projection(db, receipt)
        )
    )


@router.get(
    "/api/warehouse-receipts/{receipt_id}/payment-context", response_model=ReceiptPaymentContextOut
)
def warehouse_receipt_payment_context(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    """زمینه‌ی «اعلامیه پرداخت» از روی رسید — فقط خواندنی؛ پرداخت همچنان سندِ خزانه است (§۳۹)."""
    receipt = db.get(WarehouseReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "رسید انبار یافت نشد")
    return receipt_payment_context(db, receipt)
