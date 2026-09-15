"""شمارنده‌ی اسناد، به‌ازای هر مستأجر.

جایگزین هشت SEQUENCE سراسری. دو دلیل دارد و دومی مهم‌تر است:

۱. سراسری بودن با چند‌مستأجری ناسازگار است — مستأجر دوم فاکتورش از شماره‌ی ۹۰۰
   شروع می‌شد چون مستأجر اول ۸۹۹ سند زده بود.

۲. **SEQUENCE روی rollback شکاف می‌سازد.** nextval بیرون از تراکنش عمل می‌کند، پس
   فاکتوری که ثبتش نیمه‌کاره لغو شود شماره‌اش را می‌سوزاند. سامانه‌ی مؤدیان
   شماره‌گذاری بدون شکاف انتظار دارد. افزایشِ این جدول داخل همان تراکنش است، پس
   اگر سند برنگردد شماره هم برمی‌گردد — ذاتاً بدون شکاف.

هزینه‌اش این است که همزمانی روی یک نوع سندِ یک مستأجر سریالی می‌شود. برای دفترداری
که چند سند در ثانیه می‌زند بی‌اهمیت است، و در ازایش درستی می‌گیریم.
"""
from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

#: انواع سندی که شماره‌ی رسمی می‌گیرند
DOC_JOURNAL_ENTRY = "journal_entry"
#: شمارنده‌ی «شماره عطف» سند حسابداری — جدا از شماره‌ی سند، و عمداً.
#:
#: شماره‌ی سند با عملیاتِ «شماره‌گذاری مجدد» به‌ترتیبِ تاریخ جابه‌جا می‌شود؛ عطف
#: هرگز. عطف به‌ترتیبِ *ثبت* داده می‌شود و روی سند قفل می‌ماند، پس ارجاعِ بیرونی
#: (چاپ، پیوست، نامه) به آن نمی‌شکند. دو ترتیبِ متفاوت یعنی دو شمارنده‌ی متفاوت —
#: یکی‌کردنشان یعنی یا عطف با بازشماره‌گذاری بشکند یا شماره‌ی سند از تاریخ عقب بماند.
DOC_JOURNAL_ATF = "journal_atf"
DOC_SALES_INVOICE = "sales_invoice"
DOC_PURCHASE_INVOICE = "purchase_invoice"
DOC_PAYSLIP = "payslip"
DOC_SALES_QUOTATION = "sales_quotation"
DOC_SALES_RETURN = "sales_return"
DOC_PURCHASE_RETURN = "purchase_return"
DOC_STOCK_TRANSFER = "stock_transfer"
DOC_PRODUCTION_ORDER = "production_order"
DOC_INSTALLMENT_PLAN = "installment_plan"
#: اعلامیه‌ی بدهکار/بستانکار — شماره‌ی رسمی می‌گیرد چون سند حسابداری می‌زند.
DOC_CREDIT_DEBIT_NOTE = "credit_debit_note"
#: تسویه‌ی کارت‌خوان — شماره‌ی رسمی می‌گیرد چون سندِ حسابداری می‌زند و در فهرست
#: و مغایرت‌گیریِ بانکی به آن ارجاع داده می‌شود (§۵).
DOC_POS_SETTLEMENT = "pos_settlement"
#: عملیاتِ چک (واگذاری، وصول، واخواست، نقد کردن، …). شماره‌ی مستقل دارد چون یک
#: عملیات می‌تواند چند چک را با هم ببرد (§۱۱ §۴۴) و با شماره‌ی چک و شماره‌ی سند
#: هیچ‌کدام یکی نیست.
DOC_CHECK_OPERATION = "check_operation"
#: رسید دریافت — شماره‌ی عملیاتیِ خودِ رسید، جدا از شماره‌ی سندِ حسابداری و شماره‌ی
#: چک. §۴ همین تفکیک را می‌خواهد، و بی‌شکاف‌بودن اینجا هم مثلِ فاکتور لازم است.
DOC_RECEIPT = "receipt"
DOC_PAYMENT = "payment"
DOC_WAREHOUSE_RECEIPT = "warehouse_receipt"
#: تسویه‌ی حسابِ طرف مقابل — تخصیصِ اقلامِ باز به هم. شماره‌ی مستقل دارد چون
#: خودش سند است و به شماره‌ی فاکتور و رسیدی که تخصیص می‌دهد گره نمی‌خورد (§۴۹).
DOC_SETTLEMENT = "settlement"
DOC_WAREHOUSE_ISSUE = "warehouse_issue"
DOC_WAREHOUSE_ISSUE_RETURN = "warehouse_issue_return"
#: فاکتور خرید خدمات — سریِ شماره‌ی خودش را دارد، جدا از فاکتور خرید کالا. هر دو
#: در یک جدول‌اند و ستونِ `kind` جدایشان می‌کند.
DOC_SERVICE_PURCHASE_INVOICE = "service_purchase_invoice"
#: اجرای «قیمت‌گذاری اسناد انبار» — سندِ اصلاحیِ بها، با شماره‌ی خودش (مهاجرتِ ۰۱۴۹).
DOC_INVENTORY_VALUATION = "inventory_valuation"
#: انبارگردانی سریِ شماره‌ی خودش را دارد — سندِ کسری/اضافی سندِ دیگری است (§۹۰).
DOC_STOCK_COUNT = "stock_count"
#: پیمان — سریِ شماره‌ی داخلیِ خودش، جدا از شماره‌ی قراردادِ خودِ کارفرما
#: (`Contract.external_reference`، متنِ آزاد).
DOC_CONTRACT = "contract"
#: متممِ پیمان — سریِ شماره‌ی مستقل، جدا از شماره‌ی پیمانِ مبنا.
DOC_CONTRACT_AMENDMENT = "contract_amendment"
#: صورت‌وضعیتِ دریافتی — سریِ شماره‌ی مستقل خودش.
DOC_CONTRACT_STATEMENT = "contract_statement"
#: تسویه‌حسابِ نهاییِ پیمان — سریِ شماره‌ی مستقل خودش؛ تنها سندِ این ماژول که
#: حسابداری واقعی دارد.
DOC_CONTRACT_SETTLEMENT = "contract_settlement"

DOC_TYPES = (
    DOC_JOURNAL_ENTRY,
    DOC_JOURNAL_ATF,
    DOC_SALES_INVOICE,
    DOC_PURCHASE_INVOICE,
    DOC_PAYSLIP,
    DOC_SALES_QUOTATION,
    DOC_SALES_RETURN,
    DOC_PURCHASE_RETURN,
    DOC_STOCK_TRANSFER,
    DOC_PRODUCTION_ORDER,
    DOC_INSTALLMENT_PLAN,
    DOC_CREDIT_DEBIT_NOTE,
    DOC_POS_SETTLEMENT,
    DOC_CHECK_OPERATION,
    DOC_RECEIPT,
    DOC_PAYMENT,
    DOC_WAREHOUSE_RECEIPT,
    DOC_SETTLEMENT,
    DOC_WAREHOUSE_ISSUE,
    DOC_WAREHOUSE_ISSUE_RETURN,
    DOC_SERVICE_PURCHASE_INVOICE,
    DOC_INVENTORY_VALUATION,
    DOC_STOCK_COUNT,
    DOC_CONTRACT,
    DOC_CONTRACT_AMENDMENT,
    DOC_CONTRACT_STATEMENT,
    DOC_CONTRACT_SETTLEMENT,
)


class DocumentCounter(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "document_counters"
    __table_args__ = (UniqueConstraint("tenant_id", "doc_type", name="uq_document_counters_tenant_doc"),)

    doc_type: Mapped[str] = mapped_column(String(40))
    last_number: Mapped[int] = mapped_column(BigInteger, default=0)
