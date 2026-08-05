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


# رنگِ برند (آبیِ کوبیتا). در HTML و PDF یکسان استفاده می‌شود تا هر دو خروجی هم‌ظاهر باشند.
_ACCENT = "#2563eb"

_STYLE = """
@page { size: A4; margin: 12mm; }
* { box-sizing: border-box; }
body {
  font-family: Vazirmatn, Tahoma, "Segoe UI", sans-serif;
  direction: rtl; color: #1e293b; margin: 0; font-size: 12px; line-height: 1.75; background: #fff;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.sheet { max-width: 190mm; margin: 0 auto; padding: 6mm 8mm; }

.head { display: flex; justify-content: space-between; align-items: flex-start;
        border-bottom: 3px solid #2563eb; padding-bottom: 14px; margin-bottom: 18px; }
.brand-block { display: flex; align-items: center; gap: 12px; }
.logo { width: 48px; height: 48px; border-radius: 13px; background: #2563eb; color: #fff;
        display: grid; place-items: center; font-size: 23px; font-weight: 800; flex: 0 0 auto; }
.title { font-size: 22px; font-weight: 800; margin: 0; color: #2563eb; line-height: 1.2; }
.biz { color: #475569; font-size: 12.5px; margin-top: 3px; }
.meta { text-align: left; font-size: 12px; }
.meta .chip { display: block; background: #eef2fb; border: 1px solid #d7def5; border-radius: 9px;
              padding: 6px 13px; margin-bottom: 7px; white-space: nowrap; }
.meta .chip span { color: #64748b; }
.meta .chip strong { color: #0f172a; }

.parties { display: flex; gap: 14px; margin-bottom: 16px; }
.party { flex: 1; border: 1px solid #e2e8f0; border-radius: 12px; padding: 11px 14px; background: #f8fafc; }
.party h2 { font-size: 11px; margin: 0 0 5px; color: #2563eb; font-weight: 700; letter-spacing: .2px; }
.party .big { font-weight: 700; font-size: 13.5px; color: #0f172a; }
.party .sub { color: #64748b; }

table { width: 100%; border-collapse: collapse; margin-bottom: 14px;
        border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; }
thead th { background: #2563eb; color: #fff; font-weight: 600; padding: 9px 8px; text-align: right; font-size: 11.5px; }
tbody td { border-bottom: 1px solid #eef2f7; padding: 8px; text-align: right; }
tbody tr:nth-child(even) td { background: #f8fafc; }
td.num, th.num { text-align: center; font-variant-numeric: tabular-nums; }
tfoot td { padding: 7px 10px; font-weight: 700; background: #f1f5f9; border-bottom: 1px solid #e8edf5; }
tfoot tr.grand td { background: #eef4ff; color: #1d4ed8; font-size: 14px; border-top: 2px solid #2563eb; border-bottom: 0; }

.words { border: 1px dashed #c7d2fe; background: #f5f8ff; border-radius: 12px; padding: 10px 14px; margin-bottom: 16px; }
.words strong { color: #1d4ed8; }
.signs { display: flex; gap: 16px; margin-top: 34px; }
.sign { flex: 1; border-top: 1.5px solid #cbd5e1; padding-top: 8px; text-align: center; color: #64748b; }
.footer { margin-top: 22px; padding-top: 10px; border-top: 1px solid #eef2f7;
          text-align: center; color: #94a3b8; font-size: 10.5px; }
.voided { color: #dc2626; border: 2px solid #dc2626; background: #fef2f2; border-radius: 10px;
          padding: 8px 12px; margin-bottom: 14px; font-weight: 700; text-align: center; }
.currency-note { background: #f2f6ff; border: 1px solid #b8c8e8; border-radius: 10px;
          padding: 7px 12px; margin-bottom: 12px; font-weight: 600; }
.toolbar { text-align: center; margin: 14px 0 22px; }
.toolbar button { font: inherit; padding: 9px 26px; cursor: pointer; border: 0;
                  background: #2563eb; color: #fff; border-radius: 10px; font-weight: 700;
                  box-shadow: 0 4px 12px -4px rgba(37,99,235,.5); }
@media print { .toolbar { display: none; } body { font-size: 11px; } .sheet { padding: 0; } }
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
    rounding: Decimal = Decimal(0),
    voided_at=None,
    void_reason: str = "",
    currency_line: str = "",
) -> str:
    """HTML کامل و مستقل — بدون هیچ منبع بیرونی، تا آفلاین و در چاپ هم درست باشد."""
    banner = ""
    if voided_at is not None:
        reason = f" — {escape(void_reason)}" if void_reason else ""
        banner = f"<div class='voided'>این فاکتور باطل شده است{reason}</div>"

    currency_banner = f"<div class='currency-note'>{escape(currency_line)}</div>" if currency_line else ""

    # total همان جمعِ خالص (بدون مالیات) است؛ اگر مالیات یا گِردکردنی هست، تفکیک نشان داده می‌شود.
    subtotal = Decimal(str(total))
    tax = Decimal(str(tax_amount or 0))
    discount = Decimal(str(total_discount or 0))
    rnd = Decimal(str(rounding or 0))
    grand_total = subtotal + tax + rnd

    rows = []
    if discount > 0:
        # ناخالص و تخفیف فقط وقتی نشان داده می‌شوند که تخفیفی باشد، تا فاکتورهای
        # بدون تخفیف دقیقاً مثل قبل چاپ شوند.
        rows.append(f"<tr><td colspan='7'>جمع ناخالص (ریال)</td><td class='num'>{fa_number(subtotal + discount)}</td></tr>")
        rows.append(f"<tr><td colspan='7'>جمع تخفیف (ریال)</td><td class='num'>{fa_number(discount)}</td></tr>")
    if tax > 0 or rnd != 0:
        rows.append(f"<tr><td colspan='7'>جمع خالص (ریال)</td><td class='num'>{fa_number(subtotal)}</td></tr>")
        if tax > 0:
            rows.append(f"<tr><td colspan='7'>مالیات بر ارزش افزوده (ریال)</td><td class='num'>{fa_number(tax)}</td></tr>")
        if rnd != 0:
            rows.append(f"<tr><td colspan='7'>گِرد کردن (ریال)</td><td class='num'>{fa_number(rnd)}</td></tr>")
        rows.append(f"<tr class='grand'><td colspan='7'>مبلغ قابل پرداخت (ریال)</td><td class='num'>{fa_number(grand_total)}</td></tr>")
    else:
        rows.append(f"<tr class='grand'><td colspan='7'>جمع کل (ریال)</td><td class='num'>{fa_number(subtotal)}</td></tr>")
    totals_rows = "".join(rows)

    logo_letter = escape((business_name.strip()[:1] or "ک"))

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
  {currency_banner}
  <div class="head">
    <div class="brand-block">
      <div class="logo">{logo_letter}</div>
      <div>
        <h1 class="title">{escape(kind)}</h1>
        <div class="biz">{escape(business_name)}</div>
      </div>
    </div>
    <div class="meta">
      <div class="chip"><span>شماره</span> &nbsp;<strong>{fa_number(number)}</strong></div>
      <div class="chip"><span>تاریخ</span> &nbsp;<strong>{format_jalali(invoice_date)}</strong></div>
    </div>
  </div>

  <div class="parties">
    <div class="party">
      <h2>طرف حساب</h2>
      <div class="big">{escape(party_name)}</div>
      <div class="sub">{escape(party_detail)}</div>
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

  <div class="footer">قدرت‌گرفته از حسابداریِ کوبیتا · cubita.ir</div>
</div>
</body>
</html>"""
