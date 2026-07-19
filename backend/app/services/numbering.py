"""تخصیص شماره‌ی رسمی سند، به‌ازای هر مستأجر و بدون شکاف.

تنها نقطه‌ای که شماره‌ی سند ساخته می‌شود. هر دوازده فراخوانی پراکنده‌ی nextval از
اینجا رد می‌شوند تا این منطق یک جا بماند.

روش: UPDATE ... RETURNING روی ردیف شمارنده. خودِ UPDATE قفل سطری می‌گیرد، پس دو
تراکنش هم‌زمان نمی‌توانند یک شماره بگیرند — دومی پشت قفل صبر می‌کند تا اولی commit
یا rollback شود. چون افزایش داخل همان تراکنش سند است، سندِ برگشت‌خورده شماره‌اش را
هم برمی‌گرداند و دنباله بدون شکاف می‌ماند؛ SEQUENCE این خاصیت را ندارد.
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.counters import DOC_TYPES
from app.tenant_context import require_current_tenant


def next_document_number(db: Session, doc_type: str, tenant_id: UUID | None = None) -> int:
    """مستأجر را به‌صورت پیش‌فرض از زمینه‌ی تراکنش می‌گیرد.

    عمداً به امضای سرویس‌ها اضافه نشد: مستأجر همین حالا روی تراکنش نشسته (همان چیزی
    که RLS از آن می‌خواند)، پس خواندنش از همان‌جا یعنی یک منبع حقیقت به‌جای دوتا که
    می‌توانند از هم جدا بیفتند.
    """
    if doc_type not in DOC_TYPES:
        raise ValueError(f"نوع سند ناشناخته: {doc_type}")

    tenant_id = tenant_id or require_current_tenant()
    number = db.execute(
        text(
            """
            UPDATE document_counters
               SET last_number = last_number + 1
             WHERE tenant_id = :tenant_id AND doc_type = :doc_type
            RETURNING last_number
            """
        ),
        {"tenant_id": str(tenant_id), "doc_type": doc_type},
    ).scalar_one_or_none()

    if number is None:
        # ردیف شمارنده باید هنگام provisioning ساخته شده باشد. نبودنش یعنی مستأجر
        # ناقص ساخته شده — بهتر است بلند شکست بخورد تا اینکه بی‌صدا از ۱ شروع کند و
        # شماره‌ی تکراری بسازد.
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"شمارنده‌ی «{doc_type}» برای این مستأجر ساخته نشده؛ provisioning ناقص است",
        )
    return int(number)
