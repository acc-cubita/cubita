"""نمای چاپی فاکتور — HTML آماده‌ی چاپ که سرور می‌سازد.

**چرا HTML و نه PDF سمت سرور:** پلن اولیه WeasyPrint را پیشنهاد می‌کرد. سخت‌ترین
بخش چاپ فارسی، شکل‌دهی حروف چسبان و راست‌به‌چپ است — و مرورگر هر دو را بی‌عیب
انجام می‌دهد، در حالی که WeasyPrint به pango/cairo نیاز دارد که هم روی ویندوزِ
توسعه دردسر است هم یک وابستگی سنگین روی سرور.

و این کارِ دورریختنی نیست: WeasyPrint هم ورودی‌اش HTML است. همین قالب، بدون تغییر،
بعداً به PDF سمت سرور تبدیل می‌شود اگر لازم شد (مثلاً برای پیوست ایمیل). پس مسیر
ارزان امروز، پیش‌نیاز مسیر کامل فرداست، نه بدهی فنی.

سه چیزی که خودمان باید انجام دهیم چون مرورگر نمی‌داند:
  - تبدیل تاریخ میلادی به شمسی
  - رقم‌های فارسی و جداکننده‌ی هزارگان
  - حروفی کردن مبلغ کل (انتظار رایج روی فاکتور رسمی ایرانی)
"""
from datetime import date
from decimal import Decimal
from html import escape

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

JALALI_MONTHS = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)

_GREGORIAN_MONTH_DAYS = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)


def gregorian_to_jalali(g: date) -> tuple[int, int, int]:
    """تبدیل میلادی به شمسی.

    عمداً بدون کتابخانه‌ی بیرونی: افزودن وابستگی یعنی هر استقرار باید pip install
    هم بکند، و این الگوریتم بیست خط و کاملاً مشخص است. درستی‌اش با لنگرهای
    تاریخیِ مستقلاً راستی‌آزمایی‌پذیر تست می‌شود (پیروزی انقلاب، نوروزهای اخیر).

    **محدودیتی که باید بدانید:** این حساب ۳۳ساله است و نه نجومی. تقویم رسمی ایران
    بر مبنای لحظه‌ی اعتدال بهاری تعیین می‌شود و برای معدودی از سال‌های دور ممکن
    است یک روز اختلاف داشته باشد. همه‌ی نرم‌افزارهای رایج از همین حساب استفاده
    می‌کنند، ولی اگر روزی تاریخ رسمیِ سند مالی اهمیت قانونی پیدا کرد، باید با
    تقویم رسمی همان سال تطبیق داده شود.
    """
    gy, gm, gd = g.year, g.month, g.day
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621

    gy2 = gy + 1 if gm > 2 else gy
    days = (
        365 * gy
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
        - 80
        + gd
        + _GREGORIAN_MONTH_DAYS[gm - 1]
    )

    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365

    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def format_jalali(g: date | None) -> str:
    if g is None:
        return "—"
    jy, jm, jd = gregorian_to_jalali(g)
    return f"{jd} {JALALI_MONTHS[jm - 1]} {jy}".translate(PERSIAN_DIGITS)


def fa_number(value) -> str:
    """عدد با جداکننده‌ی هزارگان و رقم فارسی."""
    if value is None:
        return "—"
    number = Decimal(str(value))
    quantized = number.quantize(Decimal(1)) if number == number.to_integral_value() else number.normalize()
    return f"{quantized:,}".translate(PERSIAN_DIGITS)


_ONES = ("", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه")
_TEENS = ("ده", "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده", "هفده", "هجده", "نوزده")
_TENS = ("", "", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود")
_HUNDREDS = ("", "صد", "دویست", "سیصد", "چهارصد", "پانصد", "ششصد", "هفتصد", "هشتصد", "نهصد")
_SCALES = ((10**9, "میلیارد"), (10**6, "میلیون"), (10**3, "هزار"), (1, ""))


def _three_digits_to_words(n: int) -> str:
    parts = []
    if n >= 100:
        parts.append(_HUNDREDS[n // 100])
        n %= 100
    if 10 <= n < 20:
        parts.append(_TEENS[n - 10])
    else:
        if n >= 20:
            parts.append(_TENS[n // 10])
            n %= 10
        if n > 0:
            parts.append(_ONES[n])
    return " و ".join(parts)


def amount_in_words(value) -> str:
    """مبلغ به حروف — انتظار رایج روی فاکتور رسمی ایرانی."""
    n = int(Decimal(str(value or 0)))
    if n == 0:
        return "صفر"
    parts = []
    for scale, name in _SCALES:
        chunk, n = divmod(n, scale)
        if chunk:
            words = _three_digits_to_words(chunk)
            parts.append(f"{words} {name}".strip())
    return " و ".join(parts)


_STYLE = """
@page { size: A4; margin: 14mm; }
* { box-sizing: border-box; }
body {
  font-family: Vazirmatn, Tahoma, "Segoe UI", sans-serif;
  direction: rtl; color: #111; margin: 0; font-size: 12px; line-height: 1.7;
}
.sheet { max-width: 190mm; margin: 0 auto; padding: 8mm; }
.head { display: flex; justify-content: space-between; align-items: flex-start;
        border-bottom: 2px solid #111; padding-bottom: 10px; margin-bottom: 14px; }
.title { font-size: 20px; font-weight: 700; margin: 0 0 4px; }
.meta { text-align: left; font-size: 12px; }
.meta div { margin-bottom: 2px; }
.parties { display: flex; gap: 16px; margin-bottom: 14px; }
.party { flex: 1; border: 1px solid #bbb; border-radius: 4px; padding: 8px 10px; }
.party h2 { font-size: 12px; margin: 0 0 4px; color: #555; font-weight: 600; }
table { width: 100%; border-collapse: collapse; margin-bottom: 12px; }
th, td { border: 1px solid #bbb; padding: 6px 8px; text-align: right; }
th { background: #f2f2f2; font-weight: 600; }
td.num, th.num { text-align: center; font-variant-numeric: tabular-nums; }
tfoot td { font-weight: 700; background: #fafafa; }
.words { border: 1px solid #bbb; border-radius: 4px; padding: 8px 10px; margin-bottom: 14px; }
.signs { display: flex; gap: 16px; margin-top: 28px; }
.sign { flex: 1; border-top: 1px solid #888; padding-top: 6px; text-align: center; color: #555; }
.voided { color: #b00; border: 2px solid #b00; border-radius: 4px;
          padding: 6px 10px; margin-bottom: 12px; font-weight: 700; }
.toolbar { text-align: center; margin: 12px 0 20px; }
.toolbar button { font: inherit; padding: 8px 22px; cursor: pointer;
                  border: 1px solid #111; background: #111; color: #fff; border-radius: 6px; }
@media print { .toolbar { display: none; } body { font-size: 11px; } }
"""


def _rows(lines) -> str:
    out = []
    for i, line in enumerate(lines, start=1):
        gross = Decimal(str(line["qty"])) * Decimal(str(line["unit_price"]))
        discount = Decimal(str(line.get("discount") or 0))
        # مبلغِ ستونِ آخر خالصِ پس از تخفیف است تا جمعِ ستون با «جمع کل» بخواند؛
        # وگرنه خریدار روی کاغذ دو عددِ ناسازگار می‌بیند.
        out.append(
            f"<tr>"
            f"<td class='num'>{fa_number(i)}</td>"
            f"<td>{escape(line['name'])}</td>"
            f"<td>{escape(line.get('description') or '')}</td>"
            f"<td class='num'>{fa_number(line['qty'])}</td>"
            f"<td class='num'>{escape(line.get('unit') or '')}</td>"
            f"<td class='num'>{fa_number(line['unit_price'])}</td>"
            f"<td class='num'>{fa_number(discount)}</td>"
            f"<td class='num'>{fa_number(gross - discount)}</td>"
            f"</tr>"
        )
    return "\n".join(out)


def render_invoice(
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
    voided_at=None,
    void_reason: str = "",
) -> str:
    """HTML کامل و مستقل — بدون هیچ منبع بیرونی، تا آفلاین و در چاپ هم درست باشد."""
    banner = ""
    if voided_at is not None:
        reason = f" — {escape(void_reason)}" if void_reason else ""
        banner = f"<div class='voided'>این فاکتور باطل شده است{reason}</div>"

    # total همان جمعِ خالص (بدون مالیات) است؛ اگر مالیاتی هست، تفکیک نشان داده می‌شود.
    subtotal = Decimal(str(total))
    tax = Decimal(str(tax_amount or 0))
    discount = Decimal(str(total_discount or 0))
    grand_total = subtotal + tax

    rows = []
    if discount > 0:
        # ناخالص و تخفیف فقط وقتی نشان داده می‌شوند که تخفیفی باشد، تا فاکتورهای
        # بدون تخفیف دقیقاً مثل قبل چاپ شوند.
        rows.append(f"<tr><td colspan='7'>جمع ناخالص (ریال)</td><td class='num'>{fa_number(subtotal + discount)}</td></tr>")
        rows.append(f"<tr><td colspan='7'>جمع تخفیف (ریال)</td><td class='num'>{fa_number(discount)}</td></tr>")
    if tax > 0:
        rows.append(f"<tr><td colspan='7'>جمع خالص (ریال)</td><td class='num'>{fa_number(subtotal)}</td></tr>")
        rows.append(f"<tr><td colspan='7'>مالیات بر ارزش افزوده (ریال)</td><td class='num'>{fa_number(tax)}</td></tr>")
        rows.append(f"<tr><td colspan='7'>مبلغ قابل پرداخت (ریال)</td><td class='num'>{fa_number(grand_total)}</td></tr>")
    else:
        rows.append(f"<tr><td colspan='7'>جمع کل (ریال)</td><td class='num'>{fa_number(subtotal)}</td></tr>")
    totals_rows = "".join(rows)

    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(kind)} شماره {fa_number(number)}</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="toolbar"><button onclick="window.print()">چاپ / ذخیره PDF</button></div>
<div class="sheet">
  {banner}
  <div class="head">
    <div>
      <h1 class="title">{escape(kind)}</h1>
      <div>{escape(business_name)}</div>
    </div>
    <div class="meta">
      <div>شماره: <strong>{fa_number(number)}</strong></div>
      <div>تاریخ: <strong>{format_jalali(invoice_date)}</strong></div>
    </div>
  </div>

  <div class="parties">
    <div class="party">
      <h2>طرف حساب</h2>
      <div><strong>{escape(party_name)}</strong></div>
      <div>{escape(party_detail)}</div>
    </div>
    <div class="party">
      <h2>شرح</h2>
      <div>{escape(description) or "—"}</div>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th class="num" style="width:6%">ردیف</th>
        <th style="width:26%">شرح کالا/خدمت</th>
        <th style="width:20%">توضیح</th>
        <th class="num" style="width:10%">تعداد</th>
        <th class="num" style="width:8%">واحد</th>
        <th class="num" style="width:13%">مبلغ واحد</th>
        <th class="num" style="width:9%">تخفیف</th>
        <th class="num" style="width:13%">مبلغ کل</th>
      </tr>
    </thead>
    <tbody>
{_rows(lines)}
    </tbody>
    <tfoot>
      {totals_rows}
    </tfoot>
  </table>

  <div class="words">مبلغ به حروف: <strong>{amount_in_words(grand_total)}</strong> ریال</div>

  <div class="signs">
    <div class="sign">مهر و امضای فروشنده</div>
    <div class="sign">مهر و امضای خریدار</div>
  </div>
</div>
</body>
</html>"""
