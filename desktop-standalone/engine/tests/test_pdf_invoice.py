"""فاکتور PDF واقعی — ساختِ سالمِ PDF فارسیِ RTL با فونتِ embed و متنِ انتخاب‌شدنی.

رندرِ بصری را نمی‌شود در تست خودکار سنجید، ولی این‌ها گاردهایی هستند که اگر
وابستگی (fpdf2/uharfbuzz)، فونت، یا منطقِ ساخت بشکند، سریع می‌گیرند: خروجی باید
یک PDF معتبر باشد، فونت داخلش embed شده باشد (تا روی هر دستگاه یکسان دیده شود) و
نگاشتِ ToUnicode داشته باشد (تا متن انتخاب/جست‌وجو شود).
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from app.services.pdf_invoice import render_invoice_pdf


def _pdf(**overrides) -> bytes:
    defaults = dict(
        kind="فاکتور فروش",
        business_name="فروشگاه نمونه",
        number=42,
        invoice_date=date(2026, 3, 21),
        party_name="مشتری تست",
        party_detail="۰۹۱۲۰۰۰۰۰۰۰ — تهران",
        description="بابت فروش",
        lines=[
            {"name": "کالای الف", "description": "", "qty": 3, "unit": "عدد", "unit_price": 50_000, "discount": 0},
        ],
        total=Decimal(150_000),
    )
    defaults.update(overrides)
    return render_invoice_pdf(**defaults)


def test_output_is_a_valid_pdf():
    data = _pdf()
    assert data[:5] == b"%PDF-"
    assert data[-6:].rstrip() == b"%%EOF"
    assert len(data) > 3000


def test_font_is_embedded_and_text_is_selectable():
    data = _pdf()
    assert b"FontFile2" in data   # فونت داخلِ فایل embed شده
    assert b"ToUnicode" in data   # متن انتخاب/جست‌وجو می‌شود


def test_tax_and_discount_variants_do_not_crash():
    # بدون مالیات و بدون تخفیف (مسیر «جمع کل»)
    assert _pdf(tax_amount=Decimal(0), total_discount=Decimal(0))[:5] == b"%PDF-"
    # با مالیات و تخفیف (مسیر تفکیک‌شده)
    data = _pdf(
        tax_amount=Decimal(15_000),
        total_discount=Decimal(5_000),
        lines=[{"name": "کالای ب", "qty": 2, "unit": "عدد", "unit_price": 80_000, "discount": 5_000}],
        total=Decimal(155_000),
    )
    assert data[:5] == b"%PDF-"


def test_voided_invoice_renders():
    data = _pdf(voided_at=datetime.now(timezone.utc), void_reason="ثبت اشتباه")
    assert data[:5] == b"%PDF-"


def test_long_names_and_missing_unit_do_not_crash():
    data = _pdf(
        lines=[
            {"name": "کالایی با نامِ خیلی خیلی طولانی که باید کوتاه شود " * 3, "qty": 1, "unit": "", "unit_price": 1_000, "discount": 0},
            {"name": "خدمت", "qty": 1, "unit": None, "unit_price": 500, "discount": 0},
        ],
        total=Decimal(1_500),
    )
    assert data[:5] == b"%PDF-"


def test_many_lines_paginate():
    lines = [{"name": f"کالای {i}", "qty": i, "unit": "عدد", "unit_price": 1000, "discount": 0} for i in range(1, 60)]
    data = render_invoice_pdf(
        kind="فاکتور فروش",
        business_name="نمونه",
        number=1,
        invoice_date=date(2026, 3, 21),
        party_name="مشتری",
        party_detail="",
        description="",
        lines=lines,
        total=Decimal(100_000),
    )
    assert data[:5] == b"%PDF-"
    assert b"/Count 2" in data or b"/Count 3" in data  # بیش از یک صفحه شد
