"""سند ← عملیاتِ منبع: نیمه‌ی دومِ ردیابی.

جهتِ **عملیات ← سند** از قبل محکم است: شانزده مدل ستونِ `journal_entry_id` دارند و
`voiding._apply_void` رویش زندگی می‌کند. جهتِ معکوس نبود — حسابرسی که سندِ ۸۵۰ را
در دفتر می‌دید می‌فهمید «فاکتور فروش» بوده، ولی **کدام** فاکتور را نه.

**چرا مشتق و نه ذخیره.** `JournalEntry.source_id` برای همین ساخته شده بود و
هیچ‌وقت پر نشد؛ سی‌وهفت نقطه‌ی ساختِ سند باید یادشان می‌ماند و نماند. ولی مسئله
فقط انضباط نیست: آن ستون **دومین جای ذخیره‌ی همان رابطه** است و می‌تواند با
`journal_entry_id` نخواند — همان «دو نمای یک داده» که پروژه منعش می‌کند.

راهِ درست از خودِ داده درمی‌آید: `source_type` می‌گوید سراغِ کدام جدول برویم، و
`journal_entry_id` آن‌جا جواب را دارد. یک کوئری، بدونِ ستونِ تازه، بدونِ امکانِ
دریفت. اگر چیزی به سند اشاره نکند، جواب `None` است — که همان حقیقت است.

**رابطه لزوماً یک‌به‌یک نیست.** حقوق و دستمزد یک سند برای کلِ دوره می‌زند و همه‌ی
فیش‌ها به همان اشاره می‌کنند. پس شناسه و شماره فقط وقتی برمی‌گردند که منبع
*یکتا* باشد؛ وگرنه فقط شمارش. نشان‌دادنِ «فیش حقوقی ۱» برای سندی که بیست‌وسه فیش
دارد، غلط توصیف می‌کند.
"""
from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry
from app.models.assets import DepreciationEntry
from app.models.banking import BankTransaction, PettyCashTransaction
from app.models.inventory import StockAdjustment
from app.models.invoices import PurchaseInvoice, SalesInvoice
from app.models.manufacturing import ProductionOrder
from app.models.payroll import BenefitRun, Payslip
from app.models.period_close import FiscalPeriodClose
from app.models.returns import PurchaseReturn, SalesReturn
from app.models.sales_ops import CreditDebitNote
from app.models.stock_count import StockCountSession
from app.models.treasury import TreasuryTransaction

#: `source_type`ِ سند → مدلی که با `journal_entry_id` به آن برمی‌گردد.
#:
#: نگاشتِ نادقیق خطرناک نیست: کوئری همیشه `journal_entry_id == entry.id` است، پس
#: اگر ردیفی به این سند اشاره نکند جواب `None` می‌شود — هرگز جوابِ *غلط*.
SOURCE_MODELS: dict[str, type] = {
    "sales_invoice": SalesInvoice,
    "purchase_invoice": PurchaseInvoice,
    "sales_return": SalesReturn,
    "purchase_return": PurchaseReturn,
    "treasury_receipt": TreasuryTransaction,
    "treasury_payment": TreasuryTransaction,
    #: چک و بانک هر دو به گردشِ بانکی می‌نشینند؛ صدورِ چک هنوز گردشی نساخته و
    #: آن‌جا جواب به‌درستی خالی می‌ماند تا وصول شود.
    "check": BankTransaction,
    "bank": BankTransaction,
    "petty_cash": PettyCashTransaction,
    "payroll": Payslip,
    "payroll_benefit": BenefitRun,
    "depreciation": DepreciationEntry,
    "production_order": ProductionOrder,
    "stock_adjustment": StockAdjustment,
    "stock_count": StockCountSession,
    "credit_debit_note": CreditDebitNote,
    "period_close": FiscalPeriodClose,
}

#: مدل‌هایی که ستونِ `journal_entry_id` دارند ولی هیچ سندی به آن‌ها نمی‌رسد، پس در
#: نگاشت نیستند. صریح نوشته می‌شوند تا تستِ کامل‌بودنِ رجیستری بتواند بینِ
#: «عمداً نیست» و «یادمان رفت» فرق بگذارد.
#:
#: `PayrollSettlement` تسویه‌حسابِ پایانِ کار را *حساب* می‌کند و سندی نمی‌زند؛
#: پرداختش از مسیرِ خزانه می‌رود. ستونش امروز همیشه NULL است.
MODELS_WITHOUT_ENTRIES: frozenset[str] = frozenset({"PayrollSettlement"})

#: منبع‌هایی که واقعاً عملیاتِ بیرونی ندارند — سند خودش رویداد است. این‌ها شکاف
#: نیستند و `None` گرفتنشان درست است.
ACCOUNTING_NATIVE: frozenset[str] = frozenset(
    {
        "manual",
        "fx_revaluation",
        "closing_entry",
        "opening_entry",
        "opening",
        "opening_balance",
        "recurring",
        #: اصلاحِ طبقه‌بندیِ مانده هم عملیاتِ منبعِ بیرونی ندارد — خودِ سند رویداد است.
        "reclassification",
    }
)


#: نامِ فارسیِ هر منبع، برای برگه‌ی چاپی. رابط نسخه‌ی خودش را در `kit.tsx` دارد
#: (`SOURCE_LABELS`) و آن‌جا منبع‌های حسابداری‌زاد را هم پوشش می‌دهد؛ این‌جا فقط
#: چیزهایی لازم است که واقعاً عملیاتِ منبع دارند.
SOURCE_LABELS: dict[str, str] = {
    "sales_invoice": "فاکتور فروش",
    "purchase_invoice": "فاکتور خرید",
    "sales_return": "برگشت از فروش",
    "purchase_return": "برگشت از خرید",
    "treasury_receipt": "رسید دریافت",
    "treasury_payment": "اعلامیه پرداخت",
    "check": "چک",
    "bank": "عملیات بانکی",
    "petty_cash": "تنخواه‌گردان",
    "payroll": "حقوق و دستمزد",
    "payroll_benefit": "مزایا",
    "depreciation": "استهلاک",
    "production_order": "سفارش تولید",
    "stock_adjustment": "تعدیل انبار",
    "stock_count": "انبارگردانی",
    "credit_debit_note": "اعلامیه بدهکار/بستانکار",
    "period_close": "بستن دوره",
}


def describe(source: dict | None) -> str:
    """برچسبِ خواندنیِ منبع — «فاکتور فروش ۱۲۵» یا «حقوق و دستمزد — ۲۳ مورد».

    وقتی منبع یکتا نیست شماره نمی‌آید، چون شماره‌ی *یکی* از بیست‌وسه فیش، سند را
    غلط توصیف می‌کند.
    """
    if source is None:
        return ""
    #: واردکردنِ درون‌تابعی تا این ماژول به لایه‌ی چاپ گره نخورد؛ تنها چیزی که از
    #: آن‌جا لازم است تبدیلِ رقم است.
    from app.services.printing import fa_number

    label = SOURCE_LABELS.get(source["source_type"], source["source_type"])
    if source.get("number"):
        return f"{label} {fa_number(source['number'])}"
    if source.get("count", 0) > 1:
        return f"{label} — {fa_number(source['count'])} مورد"
    return label


def _ref(model: type, rows: list) -> dict:
    """شکلِ خروجی برای یک سند. شناسه فقط وقتی می‌آید که منبع یکتا باشد."""
    single = rows[0] if len(rows) == 1 else None
    return {
        "model": model.__name__,
        "count": len(rows),
        "id": single.id if single is not None else None,
        #: بعضی از این مدل‌ها شماره ندارند (گردشِ بانکی، اجرای مزایا)؛ `getattr`
        #: به‌جای شرطِ جدا برای هرکدام.
        "number": str(getattr(single, "number", "") or "") or None if single is not None else None,
    }


def resolve_sources(db: Session, entries: list[JournalEntry]) -> dict[UUID, dict]:
    """منبعِ چند سند، **دسته‌ای**.

    کلیدِ کارایی همین است: سندها بر `source_type` گروه می‌شوند و برای هر نوع *یک*
    کوئریِ `IN` می‌رود. صفحه‌ی دویست‌تایی حداکثر به تعدادِ *نوع‌ها* کوئری می‌خورد،
    نه به تعدادِ سندها.
    """
    by_type: dict[str, list[UUID]] = defaultdict(list)
    for entry in entries:
        model = SOURCE_MODELS.get(entry.source_type or "")
        if model is not None:
            by_type[entry.source_type].append(entry.id)

    out: dict[UUID, dict] = {}
    for source_type, entry_ids in by_type.items():
        model = SOURCE_MODELS[source_type]
        grouped: dict[UUID, list] = defaultdict(list)
        for row in db.query(model).filter(model.journal_entry_id.in_(entry_ids)).all():
            grouped[row.journal_entry_id].append(row)
        for entry_id, rows in grouped.items():
            out[entry_id] = {"source_type": source_type, **_ref(model, rows)}
    return out


def resolve_source(db: Session, entry: JournalEntry) -> dict | None:
    """منبعِ یک سند. `None` یعنی سند عملیاتِ منبع ندارد — سندِ دستی، تسعیر، اختتامیه."""
    return resolve_sources(db, [entry]).get(entry.id)
