"""مسیرهای رسید دریافت.

**چرا فایلِ جدا ولی مسیرِ `/api/treasury/...`؟** رسید یک سندِ خزانه است و URLش
باید کنارِ بقیه‌ی خزانه بماند؛ ولی فایلِ جدا یعنی این فصل و فصلِ «اعلامیه پرداخت»
هم‌زمان نوشته می‌شوند بی‌آنکه یکی کارِ دیگری را بازنویسی کند. مسیر و فایل دو چیزِ
مستقل‌اند.

`POST /api/treasury/receipts`ِ قدیمی سرِ جای خودش در `routers/treasury.py` مانده
و فقط سرویسِ پشتش عوض شده، تا همان بدنه و همان پاسخ از حالا سربرگ هم بسازد —
رسیدِ ثبت‌شده با موبایل هم شماره بگیرد و در دفتر دیده شود.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.inventory import Contact
from app.models.receipt import Receipt
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.receipts import RasIn, RasOut, ReceiptIn, ReceiptOut, ReceiptVoidIn
from app.services import receipts as receipt_service
from app.services.printing import render_receipt
from app.services.idempotency import idempotent

router = APIRouter(tags=["receipts"])


@router.get("/api/receipts", response_model=Page[ReceiptOut])
def list_receipts(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    #: فیلتر **سمتِ سرور**. کشیدنِ کلِ دفتر برای فیلترکردنش در مرورگر، با اولین
    #: کسب‌وکارِ چندساله از کار می‌افتد.
    receipt_type: str | None = Query(None),
    contact_id: UUID | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    search: str | None = Query(None),
    _=Depends(require_permission("checks_bank", "view")),
):
    query = receipt_service.receipts_query(db)
    if receipt_type:
        query = query.filter(Receipt.receipt_type == receipt_type)
    if contact_id:
        query = query.filter(Receipt.contact_id == contact_id)
    if date_from:
        query = query.filter(Receipt.receipt_date >= date_from)
    if date_to:
        query = query.filter(Receipt.receipt_date <= date_to)
    if search:
        needle = f"%{search.strip()}%"
        query = query.filter(Receipt.description.ilike(needle) | Receipt.description2.ilike(needle))
    items, next_cursor = paginate(query, [Receipt.receipt_date, Receipt.id], params)
    return Page(
        items=[receipt_service.to_out(db, item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/api/receipts/{receipt_id}", response_model=ReceiptOut)
def get_receipt(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    return receipt_service.to_out(db, receipt_service.resolve(db, receipt_id))


@router.post("/api/receipts", response_model=ReceiptOut, status_code=201)
def create_receipt(
    data: ReceiptIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    """§۴۰ — همان کلید، همان رسید. تلاشِ دوباره‌ی شبکه سندِ دوم نمی‌سازد."""
    receipt = idempotent(
        db,
        request,
        user,
        operation="create_receipt",
        payload=data,
        run=lambda: receipt_service.create_receipt(db, data, user),
        replay=lambda rid: receipt_service.resolve(db, rid),
    )
    return receipt_service.to_out(db, receipt)


@router.post("/api/receipts/{receipt_id}/void", response_model=ReceiptOut)
def void_receipt(
    receipt_id: UUID,
    data: ReceiptVoidIn,
    db: Session = Depends(get_db),
    #: همان مجوزِ ابطالِ فاکتور. `checks_bank` اصلاً اکشنِ `delete` ندارد و
    #: افزودنش یعنی همه جز مالک از ابطال بیرون بمانند؛ و ابطالِ یک سندِ مالی
    #: واقعاً همان وزنِ ابطالِ فاکتور را دارد.
    user: User = Depends(require_permission("accounting", "delete")),
):
    receipt_service.void_receipt(db, receipt_id, reason=data.reason, user=user, void_date=data.void_date)
    return receipt_service.to_out(db, receipt_service.resolve(db, receipt_id))


@router.get("/api/receipts/{receipt_id}/duplicate")
def duplicate_receipt(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "create")),
):
    """پیش‌نویسِ رسیدِ تازه — **هیچ ردیفی نوشته نمی‌شود** (§۳۷)."""
    return receipt_service.duplicate_draft(db, receipt_id)


@router.post("/api/receipts/ras-preview", response_model=RasOut)
def ras_preview(
    data: RasIn,
    _=Depends(require_permission("checks_bank", "view")),
):
    """§۲۸ — راس یک محاسبه است، نه تراکنش. هیچ چیزی ذخیره نمی‌شود."""
    return receipt_service.weighted_maturity(
        [(row.amount, row.due_date) for row in data.rows],
        data.base_date,
        include_same_day=data.include_same_day,
    )


@router.get("/api/receipts/{receipt_id}/print", response_class=HTMLResponse)
def print_receipt(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("checks_bank", "view")),
):
    """§۲۵ — برگه از **همان رکورد** ساخته می‌شود، نه از نسخه‌ی دومِ داده.

    همان موتورِ چاپی که فاکتور و سند استفاده می‌کنند؛ زیرساختِ دومِ چاپ ساخته
    نشد چون فصل صریحاً منعش می‌کند.
    """
    receipt = receipt_service.resolve(db, receipt_id)
    contact = db.get(Contact, receipt.contact_id)
    detail = " — ".join(filter(None, [getattr(contact, "phone", ""), getattr(contact, "address", "")]))
    currency_line = ""
    if receipt.currency_code and receipt.currency_code != "IRR":
        currency_line = (
            f"ارز رسید: {receipt.currency_code} — نرخ تسعیر: {receipt.exchange_rate}؛ "
            "مبالغ زیر به ریال است"
        )
    html = render_receipt(
        business_name=principal.membership.tenant.name,
        number=int(receipt.number),
        receipt_date=receipt.receipt_date,
        type_label=receipt_service.type_label(receipt.receipt_type),
        party_name=contact.name if contact else "—",
        party_detail=detail,
        description=receipt.description,
        description2=receipt.description2,
        components=receipt_service.components(db, receipt),
        receipt_amount=receipt.base_currency_amount,
        discount_amount=receipt.discount_amount,
        settlement_total=receipt.base_currency_amount + receipt.discount_amount,
        voided_at=receipt.voided_at,
        void_reason=receipt.void_reason,
        currency_line=currency_line,
    )
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})
