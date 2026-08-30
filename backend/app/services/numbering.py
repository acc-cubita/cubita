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
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.models.counters import DOC_JOURNAL_ATF, DOC_TYPES
from app.tenant_context import SESSION_KEY, get_current_tenant, require_session_tenant


def next_document_number(db: Session, doc_type: str, tenant_id: UUID | None = None) -> int:
    """مستأجر را به‌صورت پیش‌فرض از زمینه‌ی تراکنش می‌گیرد.

    عمداً به امضای سرویس‌ها اضافه نشد: مستأجر همین حالا روی تراکنش نشسته (همان چیزی
    که RLS از آن می‌خواند)، پس خواندنش از همان‌جا یعنی یک منبع حقیقت به‌جای دوتا که
    می‌توانند از هم جدا بیفتند.
    """
    if doc_type not in DOC_TYPES:
        raise ValueError(f"نوع سند ناشناخته: {doc_type}")

    tenant_id = tenant_id or require_session_tenant(db)
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


# ───────────────────────── شماره عطف سند حسابداری ─────────────────────────


@event.listens_for(Session, "before_flush")
def _assign_atf_number(session: Session, flush_context, instances) -> None:
    """به هر سندِ تازه، پیش از نشستن در دیتابیس، شماره عطف می‌دهد.

    **چرا رویداد و نه فراخوانی در هر سرویس:** سند از هشت جای مختلف ساخته می‌شود —
    فرمِ دستی، فاکتور فروش، فاکتور خرید، انبارگردانی، تولید، ابطال، ادغام، سندِ
    تکرارشونده — و قرار است هر سندِ آینده هم عطف داشته باشد. یک فراخوانیِ فراموش‌شده
    یعنی سندی با عطفِ خالی که تا وقتی کاربر دنبالش نگردد دیده نمی‌شود. همان الگویی
    که `tenant_id` با آن مهر می‌خورد: یک‌جا، برای همه، غیرِقابلِ‌فراموشی.

    **ترتیب با `number` نه ترتیبِ مجموعه.** `session.new` مجموعه است و ترتیبش
    تصادفی؛ وقتی یک فلاش چند سند دارد (مثلِ فاکتوری که سندِ فروش و سندِ بهای تمام‌شده
    را با هم می‌زند)، عطف باید به همان ترتیبی برود که شماره‌ی سند رفته.

    **`no_autoflush` لازم است:** این تابع خودش وسطِ فلاش است و `Session.execute`
    به‌صورتِ پیش‌فرض فلاشِ دیگری راه می‌اندازد — یعنی بازگشتِ بی‌پایان.
    """
    from app.models.accounting import JournalEntry

    if session.info.get(SESSION_KEY) is None and get_current_tenant() is None:
        # بدونِ زمینه‌ی مستأجر شمارنده‌ای هم نیست. خودِ درج با RLS رد می‌شود؛ اینجا
        # ساکت رد می‌شویم تا خطای واقعی را با خطای شمارنده نپوشانیم.
        return

    pending = [
        obj
        for obj in session.new
        if isinstance(obj, JournalEntry) and obj.atf_number is None
    ]
    if not pending:
        return

    with session.no_autoflush:
        for entry in sorted(pending, key=lambda e: (e.number is None, e.number or 0)):
            entry.atf_number = next_document_number(session, DOC_JOURNAL_ATF)
