"""«هدف حرکت» باید دلیلِ ثبت‌شده را بگوید، نه نوعِ سند را.

**چه کم بود.** docstringِ `inventory_analytics` هدف‌ها را چنین نام می‌برد: «فروش،
خرید، **مصرف، تولید**، انبارگردانی، انتقال…» — ولی برچسب را از `source_type`
می‌ساخت، و `source_type` این تفاوت‌ها را ندارد:

* رسیدِ انبار چه بابتِ خرید باشد چه تولید، `warehouse_receipt` نوشته می‌شود.
* خروجِ انبار چه فروش باشد چه مصرفِ داخلی، `warehouse_issue`.

پس رسیدِ تولیدی و رسیدِ خرید در گزارش **یک ردیف** بودند، و مصرفِ داخلی از فروش
جدا نبود. این دقیقاً قاعده‌ی ۷۷ پایگاه دانش است: دلیلِ حرکت باید داده باشد.

**و ستونِ تازه‌ای لازم نبود** — `WarehouseReceipt.receipt_type` و
`WarehouseIssue.issue_type` از قبل با قیدِ `CHECK` همین را نگه می‌دارند. کپی‌کردنشان
روی `stock_ledger` یعنی دو حقیقت، همان چیزی که این ماژول برای طرف حساب از آن
پرهیز کرده.
"""
from app.models.invoices import ISSUE_TYPE_LABELS, RECEIPT_TYPE_LABELS
from app.services.inventory_analytics import (
    PURPOSE_LABELS,
    _REASON_SOURCES,
    _purpose_of,
)
from uuid import uuid4

DOC = uuid4()


# ─────────── تفکیکی که تا امروز نبود ───────────


def test_a_production_receipt_is_not_a_purchase_receipt():
    """**هسته‌ی این اصلاح.** هر دو `warehouse_receipt` می‌نویسند."""
    reasons = {("warehouse_receipt", DOC): "production"}
    key, label = _purpose_of("warehouse_receipt", DOC, reasons)

    other = uuid4()
    buy_key, buy_label = _purpose_of(
        "warehouse_receipt", other, {("warehouse_receipt", other): "purchase_domestic"}
    )

    assert key != buy_key, "*** تولید و خرید دوباره یک ردیف شدند ***"
    assert "تولید" in label
    assert "خرید" in buy_label


def test_internal_consumption_is_not_a_sale():
    reasons = {("warehouse_issue", DOC): "consumption"}
    key, label = _purpose_of("warehouse_issue", DOC, reasons)

    other = uuid4()
    sale_key, _ = _purpose_of("warehouse_issue", other, {("warehouse_issue", other): "sale"})

    assert key != sale_key
    assert ISSUE_TYPE_LABELS["consumption"] in label


def test_the_label_keeps_the_document_name_too():
    """برچسب باید هر دو را بگوید: «رسید انبار — تولید».

    فقطِ «تولید» کاربر را گم می‌کند، چون سفارشِ تولید هم هدفِ «تولید» دارد و از
    مسیرِ دیگری می‌آید.
    """
    _, label = _purpose_of("warehouse_receipt", DOC, {("warehouse_receipt", DOC): "production"})
    assert PURPOSE_LABELS["warehouse_receipt"] in label
    assert RECEIPT_TYPE_LABELS["production"] in label


# ─────────── رفتارِ دیروز نباید عوض شود ───────────


def test_a_source_without_a_reason_is_untouched():
    """تعدیل، انبارگردانی، انتقال و اول‌دوره دلیلِ ثبت‌شده ندارند."""
    for kind in ("adjustment", "stock_count", "transfer_in", "opening", "purchase_invoice"):
        key, label = _purpose_of(kind, DOC, {})
        assert key == kind, f"*** «{kind}» کلیدش عوض شد ***"
        assert label == PURPOSE_LABELS.get(kind, kind)


def test_a_document_whose_reason_is_missing_falls_back():
    """سندی که پیدا نشد یا دلیلش خالی بود نباید ردیف را گم کند."""
    key, label = _purpose_of("warehouse_receipt", DOC, {})
    assert key == "warehouse_receipt"
    assert label == PURPOSE_LABELS["warehouse_receipt"]


def test_a_null_source_id_does_not_crash():
    """حرکتِ بی‌سند (ردیفِ میراثی) هنوز باید سطل بخورد."""
    key, _ = _purpose_of("warehouse_issue", None, {})
    assert key == "warehouse_issue"


# ─────────── قرارداد با مدل ───────────


def test_every_reason_source_has_labels_for_all_its_values():
    """اگر کسی نوعِ تازه‌ای به `RECEIPT_TYPES` اضافه کند و برچسبش را نه، گزارش
    کدِ خام نشان می‌داد."""
    from app.models.invoices import ISSUE_TYPES, RECEIPT_TYPES

    assert set(RECEIPT_TYPES) <= set(RECEIPT_TYPE_LABELS)
    assert set(ISSUE_TYPES) <= set(ISSUE_TYPE_LABELS)


def test_the_reason_sources_are_exactly_the_documents_that_carry_one():
    assert set(_REASON_SOURCES) == {"warehouse_receipt", "warehouse_issue"}
