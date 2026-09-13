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
.logo { width: 48px; height: 48px; border-radius: 13px; background: #2563eb;
        display: grid; place-items: center; flex: 0 0 auto; }
.logo svg { display: block; }
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
.notes { border: 1px solid #e2e8f0; background: #f8fafc; border-radius: 12px; padding: 10px 14px; margin: 18px 0 4px; }
.notes .lbl { display: block; color: #2563eb; font-weight: 700; font-size: 11px; margin-bottom: 3px; letter-spacing: .2px; }
.notes .txt { color: #0f172a; }
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
    total_additions: Decimal = Decimal(0),
    total_duties: Decimal = Decimal(0),
    rounding: Decimal = Decimal(0),
    voided_at=None,
    void_reason: str = "",
    currency_line: str = "",
    business_detail: str = "",
    party_label: str = "طرف حساب",
    business_party_label: str = "",
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
    additions = Decimal(str(total_additions or 0))
    duties = Decimal(str(total_duties or 0))
    rnd = Decimal(str(rounding or 0))
    grand_total = subtotal + tax + rnd

    rows = []
    if discount > 0:
        # ناخالص و تخفیف فقط وقتی نشان داده می‌شوند که تخفیفی باشد، تا فاکتورهای
        # بدون تخفیف دقیقاً مثل قبل چاپ شوند.
        rows.append(f"<tr><td colspan='7'>جمع ناخالص (ریال)</td><td class='num'>{fa_number(subtotal + discount - additions - duties)}</td></tr>")
        rows.append(f"<tr><td colspan='7'>جمع تخفیف (ریال)</td><td class='num'>{fa_number(discount)}</td></tr>")
    if additions > 0:
        rows.append(f"<tr><td colspan='7'>جمع اضافات (ریال)</td><td class='num'>{fa_number(additions)}</td></tr>")
    if duties > 0:
        rows.append(f"<tr><td colspan='7'>جمع عوارض (ریال)</td><td class='num'>{fa_number(duties)}</td></tr>")
    if tax > 0 or rnd != 0 or additions > 0 or duties > 0:
        rows.append(f"<tr><td colspan='7'>جمع خالص (ریال)</td><td class='num'>{fa_number(subtotal)}</td></tr>")
        if tax > 0:
            rows.append(f"<tr><td colspan='7'>مالیات بر ارزش افزوده (ریال)</td><td class='num'>{fa_number(tax)}</td></tr>")
        if rnd != 0:
            rows.append(f"<tr><td colspan='7'>گِرد کردن (ریال)</td><td class='num'>{fa_number(rnd)}</td></tr>")
        rows.append(f"<tr class='grand'><td colspan='7'>مبلغ قابل پرداخت (ریال)</td><td class='num'>{fa_number(grand_total)}</td></tr>")
    else:
        rows.append(f"<tr class='grand'><td colspan='7'>جمع کل (ریال)</td><td class='num'>{fa_number(subtotal)}</td></tr>")
    totals_rows = "".join(rows)

    # نشانِ برندِ برداری (برگه/فاکتور) — جای‌گزینِ حرفِ اول، هم‌ظاهر با خروجیِ PDF.
    logo_svg = (
        '<svg viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">'
        '<path d="M9 4.5h9.6L23.5 9.4V26A1.5 1.5 0 0 1 22 27.5H9A1.5 1.5 0 0 1 7.5 26V6A1.5 1.5 0 0 1 9 4.5z" fill="#fff"/>'
        '<path d="M18.6 4.6v3.4A1.4 1.4 0 0 0 20 9.4h3.3z" fill="#bcd0f7"/>'
        '<rect x="11" y="14" width="10" height="1.8" rx="0.9" fill="#2563eb"/>'
        '<rect x="11" y="17.8" width="10" height="1.8" rx="0.9" fill="#2563eb"/>'
        '<rect x="11" y="21.6" width="6" height="1.8" rx="0.9" fill="#2563eb"/>'
        "</svg>"
    )

    # «شرح» به بالای امضاها منتقل می‌شود؛ فقط وقتی متنی باشد نمایش داده می‌شود.
    note = (description or "").strip()
    notes_block = (
        f"<div class='notes'><span class='lbl'>شرح</span>"
        f"<div class='txt'>{escape(note)}</div></div>"
        if note
        else ""
    )
    business_party = (
        f"<div class='party'><h2>{escape(business_party_label)}</h2>"
        f"<div class='big'>{escape(business_name)}</div>"
        f"<div class='sub'>{escape(business_detail)}</div></div>"
        if business_party_label
        else ""
    )

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
      <div class="logo">{logo_svg}</div>
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
    {business_party}
    <div class="party">
      <h2>{escape(party_label)}</h2>
      <div class="big">{escape(party_name)}</div>
      <div class="sub">{escape(party_detail)}</div>
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

  {notes_block}

  <div class="signs">
    <div class="sign">مهر و امضای فروشنده</div>
    <div class="sign">مهر و امضای خریدار</div>
  </div>

  <div class="footer">قدرت‌گرفته از حسابداریِ کوبیتا · cubita.ir</div>
</div>
</body>
</html>"""


def _journal_rows(lines: list[dict]) -> str:
    """ردیف‌های سند. شماره‌ی ردیف از `seq` می‌آید نه از شمارنده‌ی حلقه.

    اگر از حلقه می‌آمد، برگه‌ی چاپی همیشه ۱..n نشان می‌داد حتی وقتی ترتیبِ
    واقعیِ ذخیره‌شده چیزِ دیگری بود — یعنی مشکل را پنهان می‌کرد به‌جای نشان‌دادنش.
    سندهای پیش از مهاجرتِ ۰۱۰۰ که `seq = 0` دارند به ترتیبِ نمایش شماره می‌گیرند.
    """
    out = []
    for i, line in enumerate(lines, start=1):
        seq = line.get("seq") or i
        tracking = line.get("tracking_no") or ""
        if tracking and line.get("tracking_date"):
            tracking = f"{tracking} ({format_jalali(line['tracking_date'])})"
        out.append(
            "<tr>"
            f"<td class='num'>{fa_number(seq)}</td>"
            f"<td class='num'>{escape(line.get('account_code') or '')}</td>"
            f"<td>{escape(line.get('account_name') or '')}</td>"
            f"<td>{escape(line.get('analytic_name') or '')}</td>"
            f"<td>{escape(line.get('cost_center_name') or '')}</td>"
            f"<td>{escape(line.get('description') or '')}</td>"
            f"<td>{escape(tracking)}</td>"
            f"<td class='num'>{fa_number(line['debit']) if Decimal(str(line['debit'])) else ''}</td>"
            f"<td class='num'>{fa_number(line['credit']) if Decimal(str(line['credit'])) else ''}</td>"
            "</tr>"
        )
    return "\n".join(out)


def render_journal_entry(
    *,
    business_name: str,
    number,
    atf_number=None,
    sub_number: str = "",
    entry_date: date | None,
    status: str,
    description: str,
    lines: list[dict],
    source_label: str = "",
    voided_at=None,
    void_reason: str = "",
) -> str:
    """برگه‌ی چاپیِ سند حسابداری — HTML مستقل، بدونِ منبعِ بیرونی.

    **چرا جمعِ بدهکار و بستانکار هر دو چاپ می‌شوند و نه فقط یکی:** برگه‌ی سند سندِ
    رسمی است و خواننده — حسابرس یا مدیر — باید بتواند توازن را *روی همان کاغذ*
    ببیند، نه اینکه به درستیِ نرم‌افزار اعتماد کند.
    """
    total_debit = sum((Decimal(str(l["debit"])) for l in lines), Decimal(0))
    total_credit = sum((Decimal(str(l["credit"])) for l in lines), Decimal(0))

    banner = ""
    if voided_at is not None:
        reason = f" — {escape(void_reason)}" if void_reason else ""
        banner = f"<div class='voided'>این سند باطل شده است{reason}</div>"

    #: سندِ موقت هنوز قطعی نیست و برگه‌اش نباید با سندِ دائم اشتباه گرفته شود.
    status_fa = "دائم" if status == "permanent" else "موقت"

    meta = [
        f"<div class='chip'><span>شماره</span> &nbsp;<strong>{fa_number(number)}</strong></div>",
        f"<div class='chip'><span>تاریخ</span> &nbsp;<strong>{format_jalali(entry_date)}</strong></div>",
        f"<div class='chip'><span>وضعیت</span> &nbsp;<strong>{status_fa}</strong></div>",
    ]
    if atf_number:
        meta.insert(1, f"<div class='chip'><span>عطف</span> &nbsp;<strong>{fa_number(atf_number)}</strong></div>")
    if sub_number:
        meta.insert(2, f"<div class='chip'><span>فرعی</span> &nbsp;<strong>{escape(sub_number)}</strong></div>")
    #: منبع روی خودِ برگه می‌آید: برگه‌ی چاپ‌شده از سیستم جدا می‌شود و
    #: خواننده نمی‌تواند برگردد بپرسد این سند از کجا آمده.
    if source_label:
        meta.append(
            f"<div class='chip'><span>منبع</span> &nbsp;<strong>{escape(source_label)}</strong></div>"
        )

    note = (description or "").strip()
    notes_block = (
        f"<div class='notes'><span class='lbl'>شرح سند</span>"
        f"<div class='txt'>{escape(note)}</div></div>"
        if note
        else ""
    )

    logo_svg = (
        '<svg viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">'
        '<path d="M9 4.5h9.6L23.5 9.4V26A1.5 1.5 0 0 1 22 27.5H9A1.5 1.5 0 0 1 7.5 26V6A1.5 1.5 0 0 1 9 4.5z" fill="#fff"/>'
        '<path d="M18.6 4.6v3.4A1.4 1.4 0 0 0 20 9.4h3.3z" fill="#bcd0f7"/>'
        '<rect x="11" y="14" width="10" height="1.8" rx="0.9" fill="#2563eb"/>'
        '<rect x="11" y="17.8" width="10" height="1.8" rx="0.9" fill="#2563eb"/>'
        '<rect x="11" y="21.6" width="6" height="1.8" rx="0.9" fill="#2563eb"/>'
        "</svg>"
    )

    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>سند حسابداری شماره {fa_number(number)}</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="toolbar"><button onclick="window.print()">چاپ / ذخیره PDF</button></div>
<div class="sheet">
  {banner}
  <div class="head">
    <div class="brand-block">
      <div class="logo">{logo_svg}</div>
      <div>
        <h1 class="title">سند حسابداری</h1>
        <div class="biz">{escape(business_name)}</div>
      </div>
    </div>
    <div class="meta">
      {''.join(meta)}
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th class="num" style="width:5%">ردیف</th>
        <th class="num" style="width:9%">کد حساب</th>
        <th style="width:19%">نام حساب</th>
        <th style="width:12%">تفصیلی</th>
        <th style="width:11%">مرکز هزینه</th>
        <th style="width:18%">شرح</th>
        <th style="width:10%">پیگیری</th>
        <th class="num" style="width:8%">بدهکار</th>
        <th class="num" style="width:8%">بستانکار</th>
      </tr>
    </thead>
    <tbody>
{_journal_rows(lines)}
    </tbody>
    <tfoot>
      <tr class="grand">
        <td colspan="7">جمع (ریال)</td>
        <td class="num">{fa_number(total_debit)}</td>
        <td class="num">{fa_number(total_credit)}</td>
      </tr>
    </tfoot>
  </table>

  {notes_block}

  <div class="signs">
    <div class="sign">تنظیم‌کننده</div>
    <div class="sign">تأییدکننده</div>
    <div class="sign">مدیر مالی</div>
  </div>

  <div class="footer">قدرت‌گرفته از حسابداریِ کوبیتا · cubita.ir</div>
</div>
</body>
</html>"""


#: برچسبِ فارسیِ هر ابزار در برگه‌ی چاپی. چاپ **از همان رکوردِ رسید** ساخته
#: می‌شود (§۲۵) — نسخه‌ی دومی از داده‌ی مالی وجود ندارد که بتواند واگرا شود.
_RECEIPT_KIND_LABELS = {
    "cash": "وجه نقد",
    "transfer": "حواله",
    "cheque": "چک",
    "card": "کارت‌خوان",
}


def _receipt_rows(components: list[dict]) -> str:
    """هر جزء یک ردیف، با ستون‌هایی که برای همان ابزار معنا دارند.

    ستونِ «شماره/مرجع» برای چک شماره‌ی برگ است، برای حواله شماره‌ی حواله، و برای
    کارت‌خوان کد پیگیری؛ «سررسید» فقط چک دارد. خالی‌گذاشتنشان بهتر از ساختنِ سه
    جدولِ جدا است، چون کاربر یک فهرست می‌خواهد که جمعش بخواند.
    """
    out = []
    for i, row in enumerate(components, start=1):
        label = _RECEIPT_KIND_LABELS.get(row.get("kind", ""), row.get("kind", ""))
        due = format_jalali(row.get("due_date")) if row.get("due_date") else "—"
        out.append(
            "      <tr>"
            f"<td class='num'>{fa_number(i)}</td>"
            f"<td>{escape(label)}</td>"
            f"<td>{escape(str(row.get('label') or ''))}</td>"
            f"<td>{escape(str(row.get('reference_no') or '—'))}</td>"
            f"<td class='num'>{due}</td>"
            f"<td>{escape(str(row.get('description') or ''))}</td>"
            f"<td class='num'>{fa_number(row.get('amount') or 0)}</td>"
            "</tr>"
        )
    return "\n".join(out)


def render_receipt(
    *,
    business_name: str,
    number,
    receipt_date: date | None,
    type_label: str,
    party_name: str,
    party_detail: str,
    description: str,
    description2: str = "",
    components: list[dict],
    receipt_amount: Decimal,
    discount_amount: Decimal = Decimal(0),
    settlement_total: Decimal = Decimal(0),
    voided_at=None,
    void_reason: str = "",
    currency_line: str = "",
) -> str:
    """برگه‌ی چاپیِ رسید دریافت — از همان رکورد، نه از یک نسخه‌ی جدا (§۲۵).

    **مبلغ به حروف مشتق است** (§۲۶): از `settlement_total` حساب می‌شود و هیچ‌جا
    ذخیره نمی‌شود. ذخیره‌کردنش یعنی یک منبعِ حقیقتِ دوم که می‌تواند با عدد نخواند.

    امضاها «پرداخت‌کننده / دریافت‌کننده»اند نه «فروشنده / خریدار» — رسید سندِ
    خزانه است، نه فاکتور.
    """
    banner = ""
    if voided_at is not None:
        reason = f" — {escape(void_reason)}" if void_reason else ""
        banner = f"<div class='voided'>این رسید باطل شده است{reason}</div>"

    currency_banner = f"<div class='currency-note'>{escape(currency_line)}</div>" if currency_line else ""

    received = Decimal(str(receipt_amount or 0))
    discount = Decimal(str(discount_amount or 0))
    total = Decimal(str(settlement_total or 0)) or (received + discount)

    totals = [
        f"<tr><td colspan='6'>مبلغ دریافت (ریال)</td><td class='num'>{fa_number(received)}</td></tr>"
    ]
    if discount > 0:
        #: تخفیف فقط وقتی نشان داده می‌شود که باشد، تا رسیدهای بی‌تخفیف شلوغ نشوند.
        totals.append(
            f"<tr><td colspan='6'>تخفیف تسویه (ریال)</td><td class='num'>{fa_number(discount)}</td></tr>"
        )
    totals.append(
        f"<tr class='grand'><td colspan='6'>جمع کل (ریال)</td><td class='num'>{fa_number(total)}</td></tr>"
    )

    notes = []
    if description:
        notes.append(f"<span class='lbl'>بابت</span><span class='txt'>{escape(description)}</span>")
    if description2:
        notes.append(f"<span class='lbl'>توضیحات</span><span class='txt'>{escape(description2)}</span>")
    notes_block = f"<div class='notes'>{''.join(notes)}</div>" if notes else ""

    logo_svg = (
        "<svg width='26' height='26' viewBox='0 0 24 24' fill='none' stroke='#fff' "
        "stroke-width='2' stroke-linecap='round'><path d='M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6'/></svg>"
    )

    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>رسید دریافت شماره {fa_number(number)}</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="toolbar"><button onclick="window.print()">چاپ / ذخیره PDF</button></div>
<div class="sheet">
  {banner}
  {currency_banner}
  <div class="head">
    <div class="brand-block">
      <div class="logo">{logo_svg}</div>
      <div>
        <h1 class="title">رسید دریافت</h1>
        <div class="biz">{escape(business_name)}</div>
      </div>
    </div>
    <div class="meta">
      <div class="chip"><span>شماره</span> &nbsp;<strong>{fa_number(number)}</strong></div>
      <div class="chip"><span>تاریخ</span> &nbsp;<strong>{format_jalali(receipt_date)}</strong></div>
    </div>
  </div>

  <div class="parties">
    <div class="party">
      <h2>دریافت از</h2>
      <div class="big">{escape(party_name)}</div>
      <div class="sub">{escape(party_detail)}</div>
    </div>
    <div class="party">
      <h2>نوع دریافت</h2>
      <div class="big">{escape(type_label)}</div>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th class="num" style="width:6%">ردیف</th>
        <th style="width:13%">ابزار</th>
        <th style="width:22%">صندوق / بانک / دستگاه</th>
        <th style="width:16%">شماره / مرجع</th>
        <th class="num" style="width:13%">سررسید</th>
        <th style="width:16%">شرح</th>
        <th class="num" style="width:14%">مبلغ</th>
      </tr>
    </thead>
    <tbody>
{_receipt_rows(components)}
    </tbody>
    <tfoot>
      {''.join(totals)}
    </tfoot>
  </table>

  <div class="words">مبلغ به حروف: <strong>{amount_in_words(total)}</strong> ریال</div>

  {notes_block}

  <div class="signs">
    <div class="sign">امضای پرداخت‌کننده</div>
    <div class="sign">امضای دریافت‌کننده</div>
  </div>

  <div class="footer">قدرت‌گرفته از حسابداریِ کوبیتا · cubita.ir</div>
</div>
</body>
</html>"""


_PAYMENT_KIND_LABELS = {
    "cash": "وجه نقد",
    "bank_withdrawal": "برداشت بانکی",
    "payable_cheque": "چک پرداختنی",
    "endorsed_cheque": "چک واگذاری",
}


def _payment_rows(components: list[dict]) -> str:
    """قرینه‌ی `_receipt_rows`، با یک ستونِ اضافه: کارمزد.

    کارمزد فقط سمتِ پرداخت وجود دارد — معادلِ سمتِ دریافت، کارمزدِ وصولِ چکِ
    واگذاری است که مفهومِ دیگری است و به‌زور در تقارن جا نمی‌شود.
    """
    out = []
    for i, row in enumerate(components, start=1):
        label = _PAYMENT_KIND_LABELS.get(row.get("kind", ""), row.get("kind", ""))
        due = format_jalali(row.get("due_date")) if row.get("due_date") else "—"
        fee = Decimal(str(row.get("bank_fee") or 0))
        out.append(
            "      <tr>"
            f"<td class='num'>{fa_number(i)}</td>"
            f"<td>{escape(label)}</td>"
            f"<td>{escape(str(row.get('label') or ''))}</td>"
            f"<td>{escape(str(row.get('reference_no') or '—'))}</td>"
            f"<td class='num'>{due}</td>"
            f"<td class='num'>{fa_number(fee) if fee else '—'}</td>"
            f"<td class='num'>{fa_number(row.get('amount') or 0)}</td>"
            "</tr>"
        )
    return "\n".join(out)


def render_payment(
    *,
    business_name: str,
    number,
    payment_date: date | None,
    type_label: str,
    party_name: str,
    party_detail: str,
    description: str,
    description2: str = "",
    components: list[dict],
    payment_amount: Decimal,
    discount_amount: Decimal = Decimal(0),
    bank_fee_amount: Decimal = Decimal(0),
    settlement_total: Decimal = Decimal(0),
    voided_at=None,
    void_reason: str = "",
    currency_line: str = "",
) -> str:
    """برگه‌ی چاپیِ اعلامیه پرداخت — قرینه‌ی `render_receipt`.

    **چرا قرینه و نه یک تابعِ مشترکِ پارامتری:** دو سند ستون‌های متفاوت دارند
    (کارمزد فقط این‌جا) و امضاهایشان هم فرق می‌کند. یکی‌کردنشان یعنی یک تابع با
    چند پرچمِ «اگر رسید بود…» که هر دو را سخت‌خوان می‌کند.
    """
    banner = ""
    if voided_at is not None:
        reason = f" — {escape(void_reason)}" if void_reason else ""
        banner = f"<div class='voided'>این اعلامیه باطل شده است{reason}</div>"

    currency_banner = f"<div class='currency-note'>{escape(currency_line)}</div>" if currency_line else ""

    paid = Decimal(str(payment_amount or 0))
    discount = Decimal(str(discount_amount or 0))
    fee = Decimal(str(bank_fee_amount or 0))
    total = Decimal(str(settlement_total or 0)) or (paid + discount)

    totals = [f"<tr><td colspan='6'>مبلغ پرداخت (ریال)</td><td class='num'>{fa_number(paid)}</td></tr>"]
    if fee > 0:
        totals.append(f"<tr><td colspan='6'>کارمزد بانکی (ریال)</td><td class='num'>{fa_number(fee)}</td></tr>")
    if discount > 0:
        totals.append(f"<tr><td colspan='6'>تخفیف تسویه (ریال)</td><td class='num'>{fa_number(discount)}</td></tr>")
    totals.append(
        f"<tr class='grand'><td colspan='6'>جمع کل (ریال)</td><td class='num'>{fa_number(total)}</td></tr>"
    )

    notes = []
    if description:
        notes.append(f"<span class='lbl'>بابت</span><span class='txt'>{escape(description)}</span>")
    if description2:
        notes.append(f"<span class='lbl'>توضیحات</span><span class='txt'>{escape(description2)}</span>")
    notes_block = f"<div class='notes'>{''.join(notes)}</div>" if notes else ""

    logo_svg = (
        "<svg width='26' height='26' viewBox='0 0 24 24' fill='none' stroke='#fff' "
        "stroke-width='2' stroke-linecap='round'><path d='M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6'/></svg>"
    )

    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>اعلامیه پرداخت شماره {fa_number(number)}</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="toolbar"><button onclick="window.print()">چاپ / ذخیره PDF</button></div>
<div class="sheet">
  {banner}
  {currency_banner}
  <div class="head">
    <div class="brand-block">
      <div class="logo">{logo_svg}</div>
      <div>
        <h1 class="title">اعلامیه پرداخت</h1>
        <div class="biz">{escape(business_name)}</div>
      </div>
    </div>
    <div class="meta">
      <div class="chip"><span>شماره</span> &nbsp;<strong>{fa_number(number)}</strong></div>
      <div class="chip"><span>تاریخ</span> &nbsp;<strong>{format_jalali(payment_date)}</strong></div>
    </div>
  </div>

  <div class="parties">
    <div class="party">
      <h2>پرداخت به</h2>
      <div class="big">{escape(party_name)}</div>
      <div class="sub">{escape(party_detail)}</div>
    </div>
    <div class="party">
      <h2>نوع پرداخت</h2>
      <div class="big">{escape(type_label)}</div>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th class="num" style="width:6%">ردیف</th>
        <th style="width:14%">ابزار</th>
        <th style="width:21%">صندوق / بانک / چک</th>
        <th style="width:15%">شماره / مرجع</th>
        <th class="num" style="width:12%">تاریخ</th>
        <th class="num" style="width:12%">کارمزد</th>
        <th class="num" style="width:14%">مبلغ</th>
      </tr>
    </thead>
    <tbody>
{_payment_rows(components)}
    </tbody>
    <tfoot>
      {''.join(totals)}
    </tfoot>
  </table>

  <div class="words">مبلغ به حروف: <strong>{amount_in_words(total)}</strong> ریال</div>

  {notes_block}

  <div class="signs">
    <div class="sign">امضای پرداخت‌کننده</div>
    <div class="sign">امضای دریافت‌کننده</div>
  </div>

  <div class="footer">قدرت‌گرفته از حسابداریِ کوبیتا · cubita.ir</div>
</div>
</body>
</html>"""


def _warehouse_rows(lines: list[dict]) -> str:
    """ردیف‌های برگه‌ی رسید/برگشتِ انبار — ستون‌هایی که §۴۱ نام می‌برد.

    «مالیات» و «حمل» هر ردیف جدا می‌آیند و «خالص» جمعِ همان سه است، تا کاغذ
    همان تفکیکی را نشان دهد که سندِ حسابداری و فرم دارند (§۲۵ §۴۲).
    """
    out = []
    for i, line in enumerate(lines, start=1):
        seq = line.get("seq") or i
        out.append(
            "<tr>"
            f"<td class='num'>{fa_number(seq)}</td>"
            f"<td class='num'>{escape(line.get('code') or '')}</td>"
            f"<td>{escape(line.get('name') or '')}</td>"
            f"<td class='num'>{escape(line.get('unit') or '')}</td>"
            f"<td class='num'>{fa_number(line['qty'])}</td>"
            f"<td class='num'>{fa_number(line['unit_cost'])}</td>"
            f"<td class='num'>{fa_number(line['amount'])}</td>"
            f"<td class='num'>{fa_number(line['tax'])}</td>"
            f"<td class='num'>{fa_number(line['freight'])}</td>"
            f"<td class='num'>{fa_number(line['net'])}</td>"
            "</tr>"
        )
    return "\n".join(out)


#: قالبِ A5 (§۳۵) — همان برگه در کاغذِ کوچک‌تر، نه سندِ دیگری. فقط اندازه و
#: فشردگی عوض می‌شود؛ داده همان Projection است.
_A5_STYLE = """
@page { size: A5; margin: 8mm; }
.sheet { max-width: 132mm; padding: 3mm 4mm; }
body { font-size: 10.5px; }
.title { font-size: 17px; }
.parties { flex-direction: column; gap: 8px; }
thead th, tbody td { padding: 5px 4px; font-size: 10px; }
.signs { margin-top: 22px; }
"""

PRINT_TEMPLATES = ("standard", "a5")


def render_issue_permit(
    *,
    title: str,
    business_name: str,
    number,
    doc_date: date | None,
    type_label: str,
    warehouse_code: str,
    warehouse_name: str,
    party_label: str,
    party_name: str,
    party_detail: str,
    lines: list[dict],
    total_qty: Decimal,
    references: list[tuple[str, str]] | tuple = (),
    description: str = "",
    sign_labels: tuple[str, str] = ("صادرکننده", "تحویل‌گیرنده"),
    voided_at=None,
    void_reason: str = "",
    template: str = "standard",
) -> str:
    """«مجوز خروج انبار» — برگه‌ی فیزیکیِ بیرون‌رفتنِ کالا (§۳۳ §۳۴).

    **بی‌مبلغ، عمداً.** مجوزِ خروج فاکتور نیست؛ نگهبانِ درِ انبار باید بداند چه
    کالایی و چند تا بیرون می‌رود، نه به چه قیمتی فروخته شده. ستون‌ها همان‌هایی‌اند
    که فصل نام می‌برد: مقدار و واحدِ اصلی، مقدار و واحدِ فرعی، توضیحات، و جمع.
    """
    banner = ""
    if voided_at is not None:
        reason = f" — {escape(void_reason)}" if void_reason else ""
        banner = f"<div class='voided'>این سند باطل شده است{reason}</div>"

    rows = []
    for i, line in enumerate(lines, start=1):
        secondary = line.get("secondary_qty")
        rows.append(
            "<tr>"
            f"<td class='num'>{fa_number(line.get('seq') or i)}</td>"
            f"<td class='num'>{escape(line.get('code') or '')}</td>"
            f"<td>{escape(line.get('name') or '')}</td>"
            f"<td class='num'>{fa_number(line['qty'])}</td>"
            f"<td class='num'>{escape(line.get('unit') or '')}</td>"
            f"<td class='num'>{fa_number(secondary) if secondary is not None else '—'}</td>"
            f"<td class='num'>{escape(line.get('secondary_unit') or '') or '—'}</td>"
            f"<td>{escape(line.get('description') or '')}</td>"
            "</tr>"
        )
    reference_chips = "".join(
        f"<div class='chip'><span>{escape(label)}</span> &nbsp;<strong>{fa_number(value)}</strong></div>"
        for label, value in references
    )
    note = (description or "").strip()
    notes_block = (
        f"<div class='notes'><span class='lbl'>توضیحات</span><div class='txt'>{escape(note)}</div></div>"
        if note
        else ""
    )
    warehouse_line = " — ".join(filter(None, [warehouse_code, warehouse_name]))
    style = _STYLE + (_A5_STYLE if template == "a5" else "")

    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} شماره {fa_number(number)}</title>
<style>{style}</style>
</head>
<body>
<div class="toolbar"><button onclick="window.print()">چاپ / ذخیره PDF</button></div>
<div class="sheet">
  {banner}
  <div class="head">
    <div class="brand-block">
      <div>
        <h1 class="title">{escape(title)}</h1>
        <div class="biz">{escape(business_name)}</div>
      </div>
    </div>
    <div class="meta">
      <div class="chip"><span>شماره</span> &nbsp;<strong>{fa_number(number)}</strong></div>
      <div class="chip"><span>تاریخ</span> &nbsp;<strong>{format_jalali(doc_date)}</strong></div>
      {reference_chips}
    </div>
  </div>

  <div class="parties">
    <div class="party">
      <h2>انبار</h2>
      <div class="big">{escape(warehouse_line)}</div>
      <div class="sub">نوع: {escape(type_label)}</div>
    </div>
    <div class="party">
      <h2>{escape(party_label)}</h2>
      <div class="big">{escape(party_name)}</div>
      <div class="sub">{escape(party_detail)}</div>
    </div>
  </div>

  <table class="table-plain">
    <thead>
      <tr>
        <th class="num" style="width:6%">ردیف</th>
        <th class="num" style="width:11%">کد کالا</th>
        <th style="width:25%">عنوان کالا</th>
        <th class="num" style="width:10%">مقدار اصلی</th>
        <th class="num" style="width:9%">واحد اصلی</th>
        <th class="num" style="width:10%">مقدار فرعی</th>
        <th class="num" style="width:9%">واحد فرعی</th>
        <th style="width:20%">توضیحات</th>
      </tr>
    </thead>
    <tbody>
{"".join(rows)}
    </tbody>
    <tfoot>
      <tr class="grand"><td colspan="3">جمع</td><td class="num">{fa_number(total_qty)}</td><td colspan="4"></td></tr>
    </tfoot>
  </table>

  {notes_block}

  <div class="signs">
    <div class="sign">{escape(sign_labels[0])}</div>
    <div class="sign">{escape(sign_labels[1])}</div>
  </div>

  <div class="footer">قدرت‌گرفته از حسابداریِ کوبیتا · cubita.ir</div>
</div>
</body>
</html>"""


def render_warehouse_document(
    *,
    title: str,
    business_name: str,
    number,
    doc_date: date | None,
    type_label: str,
    warehouse_code: str,
    warehouse_name: str,
    party_label: str,
    party_name: str,
    party_detail: str,
    lines: list[dict],
    goods_amount: Decimal,
    freight_amount: Decimal,
    duty_amount: Decimal,
    tax_amount: Decimal,
    net_amount: Decimal,
    description: str = "",
    sign_labels: tuple[str, str] = ("صادرکننده", "تحویل‌دهنده"),
    extra_totals: list[tuple[str, Decimal]] | tuple = (),
    voided_at=None,
    void_reason: str = "",
    currency_line: str = "",
) -> str:
    """برگه‌ی چاپیِ رسیدِ انبار و برگشتِ رسید — **Projectionِ همان سند** (§۴۲).

    فصل: «Print نباید مدل مالی دیگری باشد.» پس هیچ عددی این‌جا حساب نمی‌شود؛
    اجزا (کالا، حمل، عوارض، مالیات، خالص) همان‌هایی‌اند که مدل مشتق می‌کند و
    سندِ حسابداری از آن‌ها ساخته شده. `render_invoice` به کار نمی‌آمد چون ستونِ
    «تخفیف» دارد و «حمل» و «کد کالا» ندارد — برگه‌ی انبار زبانِ دیگری است.
    """
    banner = ""
    if voided_at is not None:
        reason = f" — {escape(void_reason)}" if void_reason else ""
        banner = f"<div class='voided'>این سند باطل شده است{reason}</div>"
    currency_banner = f"<div class='currency-note'>{escape(currency_line)}</div>" if currency_line else ""

    net = Decimal(str(net_amount or 0))
    duty = Decimal(str(duty_amount or 0))
    rows = [
        f"<tr><td colspan='9'>جمع کالا (ریال)</td><td class='num'>{fa_number(goods_amount)}</td></tr>",
        f"<tr><td colspan='9'>حمل (ریال)</td><td class='num'>{fa_number(freight_amount)}</td></tr>",
    ]
    if duty > 0:
        rows.append(f"<tr><td colspan='9'>عوارض (ریال)</td><td class='num'>{fa_number(duty)}</td></tr>")
    rows.append(f"<tr><td colspan='9'>مالیات (ریال)</td><td class='num'>{fa_number(tax_amount)}</td></tr>")
    rows.append(f"<tr class='grand'><td colspan='9'>خالص (ریال)</td><td class='num'>{fa_number(net)}</td></tr>")
    for label, value in extra_totals:
        rows.append(f"<tr><td colspan='9'>{escape(label)}</td><td class='num'>{fa_number(value)}</td></tr>")

    note = (description or "").strip()
    notes_block = (
        f"<div class='notes'><span class='lbl'>توضیحات</span><div class='txt'>{escape(note)}</div></div>"
        if note
        else ""
    )
    warehouse_line = " — ".join(filter(None, [warehouse_code, warehouse_name]))

    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} شماره {fa_number(number)}</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="toolbar"><button onclick="window.print()">چاپ / ذخیره PDF</button></div>
<div class="sheet">
  {banner}
  {currency_banner}
  <div class="head">
    <div class="brand-block">
      <div>
        <h1 class="title">{escape(title)}</h1>
        <div class="biz">{escape(business_name)}</div>
      </div>
    </div>
    <div class="meta">
      <div class="chip"><span>شماره</span> &nbsp;<strong>{fa_number(number)}</strong></div>
      <div class="chip"><span>تاریخ</span> &nbsp;<strong>{format_jalali(doc_date)}</strong></div>
      <div class="chip"><span>نوع</span> &nbsp;<strong>{escape(type_label)}</strong></div>
    </div>
  </div>

  <div class="parties">
    <div class="party">
      <h2>انبار</h2>
      <div class="big">{escape(warehouse_line)}</div>
    </div>
    <div class="party">
      <h2>{escape(party_label)}</h2>
      <div class="big">{escape(party_name)}</div>
      <div class="sub">{escape(party_detail)}</div>
    </div>
  </div>

  <table class="table-plain">
    <thead>
      <tr>
        <th class="num" style="width:5%">ردیف</th>
        <th class="num" style="width:9%">کد کالا</th>
        <th style="width:20%">عنوان کالا</th>
        <th class="num" style="width:6%">واحد</th>
        <th class="num" style="width:8%">مقدار</th>
        <th class="num" style="width:10%">فی</th>
        <th class="num" style="width:11%">مبلغ</th>
        <th class="num" style="width:10%">مالیات و عوارض</th>
        <th class="num" style="width:9%">حمل</th>
        <th class="num" style="width:12%">خالص</th>
      </tr>
    </thead>
    <tbody>
{_warehouse_rows(lines)}
    </tbody>
    <tfoot>
      {"".join(rows)}
    </tfoot>
  </table>

  <div class="words">خالص به حروف: <strong>{amount_in_words(net)}</strong> ریال</div>

  {notes_block}

  <div class="signs">
    <div class="sign">{escape(sign_labels[0])}</div>
    <div class="sign">{escape(sign_labels[1])}</div>
  </div>

  <div class="footer">قدرت‌گرفته از حسابداریِ کوبیتا · cubita.ir</div>
</div>
</body>
</html>"""
