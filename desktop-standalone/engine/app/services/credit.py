"""وضعیت اعتبارِ یک مشتری — مانده‌ی مطالبات در برابرِ سقفِ اعتبار.

مانده‌ی مطالبات دقیقاً با همان تعریفِ گزارشِ سنیِ مطالبات حساب می‌شود تا دو جا یک عدد
بدهند: مجموعِ فاکتورهای فروشِ باطل‌نشده منهای دریافت‌ها و برگشت‌ها. این محاسبه در سطحِ
شخص است (نه فاکتور‌به‌فاکتور)، چون تسویه هم در همین سیستم در سطحِ شخص ثبت می‌شود.

خروجی فقط پایه‌ی یک هشدارِ زنده هنگام صدور فاکتور است؛ هیچ سندی نمی‌سازد و چیزی را
بلاک نمی‌کند — تصمیمِ فروش با کاربر است، و فاکتورهای آفلاین هم نباید سمت سرور رد شوند.
"""
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.inventory import Contact
from app.models.invoices import SalesInvoice
from app.models.returns import SalesReturn
from app.models.treasury import TreasuryTransaction


def customer_outstanding(db: Session, contact_id: UUID, as_of: date | None = None) -> Decimal:
    """مانده‌ی خالصِ مطالبات از یک مشتری تا تاریخِ `as_of` (پیش‌فرض: امروز).

    مثبت یعنی مشتری به ما بدهکار است؛ منفی یعنی از او پیش‌دریافت داریم.
    """
    as_of = as_of or date.today()

    invoices = db.query(
        func.coalesce(func.sum(SalesInvoice.total_amount + SalesInvoice.tax_amount), 0)
    ).filter(
        SalesInvoice.contact_id == contact_id,
        SalesInvoice.voided_at.is_(None),
        SalesInvoice.invoice_date <= as_of,
    ).scalar()

    receipts = db.query(
        func.coalesce(func.sum(TreasuryTransaction.amount), 0)
    ).filter(
        TreasuryTransaction.contact_id == contact_id,
        TreasuryTransaction.type == "receipt",
        TreasuryTransaction.transaction_date <= as_of,
    ).scalar()

    returns = db.query(
        func.coalesce(func.sum(SalesReturn.total_amount + SalesReturn.tax_amount), 0)
    ).join(SalesInvoice, SalesReturn.sales_invoice_id == SalesInvoice.id).filter(
        SalesInvoice.contact_id == contact_id,
        SalesInvoice.voided_at.is_(None),
        SalesReturn.return_date <= as_of,
    ).scalar()

    return Decimal(invoices) - Decimal(receipts) - Decimal(returns)


def get_credit_status(db: Session, contact_id: UUID) -> dict:
    """سقفِ اعتبار، مانده‌ی جاری، مانده‌ی قابلِ استفاده و آیا از سقف گذشته است."""
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "طرف حساب یافت نشد")

    limit = Decimal(contact.credit_limit or 0)
    outstanding = customer_outstanding(db, contact_id)
    # سقفِ صفر یعنی «بدون سقف» — هیچ‌وقت over_limit نمی‌شود.
    over_limit = limit > 0 and outstanding > limit
    return {
        "contact_id": contact.id,
        "name": contact.name,
        "credit_limit": limit,
        "outstanding": outstanding,
        "available": limit - outstanding,
        "over_limit": over_limit,
    }
