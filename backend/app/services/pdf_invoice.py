"""فاکتور PDF واقعی — متنِ برداری و انتخاب‌شدنی، فارسیِ راست‌به‌چپ.

بر خلاف نمای HTML (که شکل‌دهی و RTL را به مرورگر می‌سپارد)، این‌جا PDF را خودِ سرور
می‌سازد تا خروجی یک **فایلِ قابلِ‌دانلود** باشد (برای پیوست ایمیل/بایگانی) — همان
مسیری که docstring نمای HTML از ابتدا پیش‌بینی کرده بود.

**چرا fpdf2 و نه WeasyPrint:** WeasyPrint به pango/cairo نیاز دارد — کتابخانه‌ی
سیستمیِ سنگین روی سرور. fpdf2 خالصِ پایتون است و شکل‌دهیِ حروفِ چسبان و RTL را با
`uharfbuzz` (چرخِ نصب، بدون libِ سیستمی) انجام می‌دهد. فونتِ Vazirmatn داخلِ مخزن
جاسازی شده و در خروجی هم embed می‌شود، پس PDF روی هر دستگاهی یکسان دیده می‌شود و
متنش انتخاب/جست‌وجو می‌شود.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF

from app.services.printing import amount_in_words, fa_number, format_jalali

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_REGULAR = str(_FONT_DIR / "Vazirmatn-Regular.ttf")
_BOLD = str(_FONT_DIR / "Vazirmatn-Bold.ttf")

_INK = (17, 17, 17)
_MUTED = (90, 90, 90)
_HEADER_BG = (242, 242, 242)
_FOOT_BG = (250, 250, 250)
_LINE = (180, 180, 180)
_RED = (176, 0, 0)

# عرض ستون‌ها به میلی‌متر، از راست به چپ. مجموع = عرضِ مفیدِ A4 با حاشیه‌ی ۱۴ (۱۸۲).
_COLS = [
    (12, "ردیف", "C"),
    (60, "شرح کالا / خدمت", "R"),
    (20, "تعداد", "C"),
    (16, "واحد", "C"),
    (28, "مبلغ واحد", "C"),
    (22, "تخفیف", "C"),
    (24, "مبلغ کل", "C"),
]
_ROW_H = 8


def _truncate(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


class _InvoicePDF(FPDF):
    def __init__(self):
        super().__init__(format="A4")
        self.set_auto_page_break(True, margin=15)
        self.set_margins(14, 14, 14)
        self.add_font("Vazir", "", _REGULAR)
        self.add_font("Vazir", "B", _BOLD)
        self.set_text_shaping(True)
        self.add_page()

    @property
    def right(self) -> float:
        return self.w - self.r_margin

    def line_full(self, y: float, width: float = 0.4) -> None:
        self.set_draw_color(*_INK)
        self.set_line_width(width)
        self.line(self.l_margin, y, self.right, y)

    def row(self, y: float, cells, *, h: float = _ROW_H, border: bool = True) -> float:
        """یک ردیفِ راست‌به‌چپ می‌کشد. cells = list از (width, text, align, fill_rgb|None)."""
        x = self.right
        self.set_draw_color(*_LINE)
        self.set_line_width(0.2)
        for w, text, align, fill in cells:
            x -= w
            self.set_xy(x, y)
            if fill is not None:
                self.set_fill_color(*fill)
            self.cell(w, h, text, border=1 if border else 0, align=align, fill=fill is not None)
        return y + h


def _usable(pdf: _InvoicePDF) -> float:
    return pdf.w - pdf.l_margin - pdf.r_margin


def render_invoice_pdf(
    *,
    kind: str,
    business_name: str,
    number,
    invoice_date: date | None,
    party_name: str,
    party_detail: str,
    description: str,
    lines: list[dict],
    total: Decimal,
    tax_amount: Decimal = Decimal(0),
    total_discount: Decimal = Decimal(0),
    rounding: Decimal = Decimal(0),
    voided_at=None,
    void_reason: str = "",
    currency_line: str = "",
) -> bytes:
    pdf = _InvoicePDF()
    usable = _usable(pdf)
    right = pdf.right

    subtotal = Decimal(str(total))
    tax = Decimal(str(tax_amount or 0))
    discount = Decimal(str(total_discount or 0))
    rnd = Decimal(str(rounding or 0))
    grand_total = subtotal + tax + rnd

    # --- سربرگ ---
    pdf.set_text_color(*_INK)
    pdf.set_font("Vazir", "B", 20)
    pdf.set_xy(pdf.l_margin, 14)
    pdf.cell(usable, 10, kind, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Vazir", "", 11)
    pdf.set_text_color(*_MUTED)
    pdf.cell(usable, 6, business_name, align="R", new_x="LMARGIN", new_y="NEXT")

    # شماره و تاریخ سمت چپِ سربرگ
    pdf.set_text_color(*_INK)
    pdf.set_font("Vazir", "", 11)
    pdf.set_xy(pdf.l_margin, 15)
    pdf.cell(usable, 6, f"شماره: {fa_number(number)}", align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(pdf.l_margin, 21)
    pdf.cell(usable, 6, f"تاریخ: {format_jalali(invoice_date)}", align="L", new_x="LMARGIN", new_y="NEXT")

    pdf.line_full(32)
    y = 36

    # --- بنر ابطال ---
    if voided_at is not None:
        reason = f" — {void_reason}" if void_reason else ""
        pdf.set_fill_color(255, 235, 235)
        pdf.set_draw_color(*_RED)
        pdf.set_line_width(0.5)
        pdf.set_text_color(*_RED)
        pdf.set_font("Vazir", "B", 12)
        pdf.set_xy(pdf.l_margin, y)
        pdf.cell(usable, 9, f"این فاکتور باطل شده است{reason}", border=1, align="C", fill=True)
        pdf.set_text_color(*_INK)
        y += 13

    # --- نوار ارز (اگر فاکتور ارزی باشد) ---
    if currency_line:
        pdf.set_fill_color(242, 246, 255)
        pdf.set_draw_color(184, 200, 232)
        pdf.set_line_width(0.2)
        pdf.set_text_color(*_INK)
        pdf.set_font("Vazir", "B", 10)
        pdf.set_xy(pdf.l_margin, y)
        pdf.cell(usable, 8, currency_line, border=1, align="R", fill=True)
        y += 12

    # --- طرف حساب و شرح (دو جعبه) ---
    box_w = (usable - 6) / 2
    box_h = 18
    for idx, (heading, body) in enumerate(
        [("طرف حساب", f"{party_name}\n{party_detail}".strip()), ("شرح", description or "—")]
    ):
        # جعبه‌ی راست اول (idx=0 راست، idx=1 چپ)
        bx = right - box_w if idx == 0 else pdf.l_margin
        pdf.set_draw_color(*_LINE)
        pdf.set_line_width(0.2)
        pdf.rect(bx, y, box_w, box_h)
        pdf.set_xy(bx + 2, y + 1.5)
        pdf.set_font("Vazir", "", 8.5)
        pdf.set_text_color(*_MUTED)
        pdf.cell(box_w - 4, 5, heading, align="R")
        pdf.set_xy(bx + 2, y + 6.5)
        pdf.set_font("Vazir", "B", 10)
        pdf.set_text_color(*_INK)
        pdf.multi_cell(box_w - 4, 5, _truncate(body.replace("\n", " — "), 90), align="R")
    y += box_h + 6

    # --- جدول اقلام ---
    pdf.set_font("Vazir", "B", 9)
    header = [(w, title, align, _HEADER_BG) for (w, title, align) in _COLS]
    y = pdf.row(y, header, h=9)

    pdf.set_font("Vazir", "", 9)
    for i, line in enumerate(lines, start=1):
        gross = Decimal(str(line["qty"])) * Decimal(str(line["unit_price"]))
        line_discount = Decimal(str(line.get("discount") or 0))
        cells = [
            (_COLS[0][0], fa_number(i), "C", None),
            (_COLS[1][0], _truncate(line["name"], 40), "R", None),
            (_COLS[2][0], fa_number(line["qty"]), "C", None),
            (_COLS[3][0], line.get("unit") or "", "C", None),
            (_COLS[4][0], fa_number(line["unit_price"]), "C", None),
            (_COLS[5][0], fa_number(line_discount), "C", None),
            (_COLS[6][0], fa_number(gross - line_discount), "C", None),
        ]
        y = pdf.row(y, cells)

    # --- ردیف‌های جمع ---
    label_w = usable - _COLS[6][0]  # همه‌ی ستون‌ها منهای «مبلغ کل»
    value_w = _COLS[6][0]

    def total_row(y, label, value, *, bold=True):
        pdf.set_font("Vazir", "B" if bold else "", 9)
        return pdf.row(
            y,
            [(label_w, label, "R", _FOOT_BG), (value_w, fa_number(value), "C", _FOOT_BG)],
        )

    if discount > 0:
        y = total_row(y, "جمع ناخالص (ریال)", subtotal + discount, bold=False)
        y = total_row(y, "جمع تخفیف (ریال)", discount, bold=False)
    if tax > 0 or rnd != 0:
        y = total_row(y, "جمع خالص (ریال)", subtotal, bold=False)
        if tax > 0:
            y = total_row(y, "مالیات بر ارزش افزوده (ریال)", tax, bold=False)
        if rnd != 0:
            y = total_row(y, "گِرد کردن (ریال)", rnd, bold=False)
        y = total_row(y, "مبلغ قابل پرداخت (ریال)", grand_total)
    else:
        y = total_row(y, "جمع کل (ریال)", subtotal)

    y += 6

    # --- مبلغ به حروف ---
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.rect(pdf.l_margin, y, usable, 10)
    pdf.set_xy(pdf.l_margin + 2, y + 2.5)
    pdf.set_font("Vazir", "", 10)
    pdf.cell(usable - 4, 5, f"مبلغ به حروف: {amount_in_words(grand_total)} ریال", align="R")
    y += 20

    # --- امضاها ---
    pdf.set_font("Vazir", "", 10)
    pdf.set_text_color(*_MUTED)
    pdf.set_xy(right - box_w, y)
    pdf.cell(box_w, 6, "مهر و امضای فروشنده", align="C")
    pdf.set_xy(pdf.l_margin, y)
    pdf.cell(box_w, 6, "مهر و امضای خریدار", align="C")

    out = pdf.output()
    return bytes(out)
