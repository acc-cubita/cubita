"""روش‌های شماره‌گذاریِ اسناد — دیدن و تنظیمِ شماره‌ی شروع.

`document_counters` از قبل وجود داشت و هر سند شماره‌اش را از همان می‌گرفت، ولی هیچ
راهی برای *دیدن* یا *تنظیمِ* آن نبود. نتیجه‌اش این بود که کسب‌وکاری که با شماره‌ی
فاکتور ۱۲۴۰ از سیستمِ قبلی می‌آمد، ناچار از ۱ شروع می‌کرد.

**فقط جلو، هرگز عقب.** شماره‌ی شمارنده را نمی‌شود کم کرد: شماره‌ی مصرف‌شده روی سندِ
ثبت‌شده نشسته و برگرداندنِ شمارنده یعنی شماره‌ی تکراری — دقیقاً همان چیزی که
شماره‌گذاریِ بدونِ شکافِ سامانه‌ی مؤدیان را می‌شکند.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.counters import DOC_TYPES, DocumentCounter

router = APIRouter(prefix="/api/numbering", tags=["numbering"])

#: برچسبِ فارسیِ هر نوعِ سند. کلیدها همان `DOC_TYPES` هستند و تست تضمین می‌کند جا نمانند.
DOC_LABELS: dict[str, str] = {
    "journal_entry": "سند حسابداری",
    "journal_atf": "شماره عطف سند",
    "sales_invoice": "فاکتور فروش",
    "purchase_invoice": "فاکتور خرید",
    "payslip": "فیش حقوقی",
    "sales_quotation": "پیش‌فاکتور",
    "sales_return": "برگشت از فروش",
    "purchase_return": "برگشت از خرید",
    "stock_transfer": "انتقال بین انبار",
    "production_order": "سفارش تولید",
    "installment_plan": "قرارداد اقساطی",
    "credit_debit_note": "اعلامیه بدهکار/بستانکار",
    "pos_settlement": "تسویه کارت‌خوان",
    "check_operation": "عملیات چک",
    "receipt": "رسید دریافت",
    "payment": "اعلامیه پرداخت",
    "warehouse_receipt": "رسید انبار خرید",
    "settlement": "تسویه حساب طرف مقابل",
    "warehouse_issue": "خروج انبار فروش",
    "warehouse_issue_return": "برگشت خروج انبار",
    "service_purchase_invoice": "فاکتور خرید خدمات",
    "inventory_valuation": "قیمت‌گذاری اسناد انبار",
    "stock_count": "انبارگردانی",
    "contract": "پیمان",
    "contract_amendment": "متمم پیمان",
}


class NumberingOut(BaseModel):
    doc_type: str
    label: str
    #: آخرین شماره‌ی مصرف‌شده. ۰ یعنی هنوز سندی از این نوع ثبت نشده.
    last_number: int
    #: شماره‌ای که به سندِ بعدیِ این نوع داده می‌شود.
    next_number: int


class NumberingIn(BaseModel):
    #: شماره‌ی سندِ بعدی. باید از شماره‌ی فعلی بزرگ‌تر باشد.
    next_number: int = Field(ge=1, le=9_999_999_999)


def _row(counter: DocumentCounter) -> NumberingOut:
    return NumberingOut(
        doc_type=counter.doc_type,
        label=DOC_LABELS.get(counter.doc_type, counter.doc_type),
        last_number=counter.last_number,
        next_number=counter.last_number + 1,
    )


@router.get("", response_model=list[NumberingOut])
def list_numbering(
    _perm=Depends(require_permission("accounting", "view")),
    db: Session = Depends(get_db),
):
    rows = db.query(DocumentCounter).all()
    by_type = {r.doc_type: r for r in rows}
    # ترتیبِ نمایش همان ترتیبِ تعریفِ نوعِ سند است، نه ترتیبِ تصادفیِ دیتابیس.
    return [_row(by_type[t]) for t in DOC_TYPES if t in by_type]


@router.patch("/{doc_type}", response_model=NumberingOut)
def set_numbering(
    doc_type: str,
    data: NumberingIn,
    _perm=Depends(require_permission("accounting", "approve")),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    if doc_type not in DOC_TYPES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "نوع سند ناشناخته است")

    counter = db.query(DocumentCounter).filter(DocumentCounter.doc_type == doc_type).first()
    if counter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "شمارنده‌ی این نوع سند وجود ندارد")

    target = data.next_number - 1
    if target < counter.last_number:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"شماره‌ی {data.next_number} قبلاً مصرف شده است؛ شماره‌ی بعدی باید بزرگ‌تر از "
            f"{counter.last_number} باشد",
        )

    counter.last_number = target
    db.flush()
    db.refresh(counter)
    return _row(counter)
