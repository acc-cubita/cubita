"""تسهیمِ هزینه‌ی حمل روی ردیف‌های یک رسید — سرویسِ دامنه، نه کدِ داخلِ فرم.

**§۲۳ صریح است:** «الگوریتم تسهیم را داخل UI ننویسیم.»

    Receipt Freight  →  Allocation Policy  →  Allocated Freight per Line

دلیلش فقط تمیزی نیست. اگر تسهیم در فرم حساب شود، رسیدی که از API یا از یک
گردشِ دیگر ساخته شود سهمِ حمل نمی‌گیرد و بی‌صدا موجودی را ارزان‌تر ثبت می‌کند —
بدونِ اینکه هیچ ترازی به‌هم بخورد.

**§۲۳ همچنین می‌گوید انواعِ دیگر را فرض نکنیم:** «این ویدیو فقط "به نسبت
مساوی" را به‌صورت واضح نشان می‌دهد.» پس همان یکی ساخته می‌شود. `POLICIES` یک
رجیستری است تا مبنای بعدی (به نسبتِ مبلغ، به نسبتِ وزن، …) وقتی فصلِ مربوطش
تعریفش کرد، یک تابع باشد نه یک بازنویسی.
"""

from decimal import Decimal
from typing import Callable

from fastapi import HTTPException, status

#: مبنای پیش‌فرض — همان که فصل نشان می‌دهد.
EQUAL = "equal"

BASIS_LABELS = {EQUAL: "به نسبت مساوی"}


def _equal(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """به نسبتِ مساوی بینِ ردیف‌ها — بی‌اعتنا به مقدار و مبلغ (§۲۲).

    نمونه‌ی فصل: حملِ ۵۰٬۰۰۰ روی دو ردیف (یکی ۵۰۰٬۰۰۰ و دیگری ۹۰۰٬۰۰۰) به
    ۲۵٬۰۰۰ و ۲۵٬۰۰۰ تقسیم می‌شود — یعنی وزنِ ردیف در این مبنا نقشی ندارد.
    """
    return [Decimal(1)] * len(weights)


#: هر مبنا وزنِ نسبیِ ردیف‌ها را می‌دهد؛ خودِ تقسیم و ته‌مانده یک‌جا و مشترک
#: انجام می‌شود تا دو مبنا دو جور گِرد نکنند.
POLICIES: dict[str, Callable[[Decimal, list[Decimal]], list[Decimal]]] = {EQUAL: _equal}


def allocate(total: Decimal, line_values: list[Decimal], basis: str = EQUAL) -> list[Decimal]:
    """سهمِ حملِ هر ردیف — جمعشان **دقیقاً** برابرِ `total` است.

    ته‌مانده‌ی گِردکردن به ردیفِ آخر می‌رود. بدونِ این، جمعِ سهم‌ها با مبلغِ
    حمل چند ریال فرق می‌کرد و سندِ حسابداری تراز نمی‌شد — خطایی که فقط روی
    اعدادِ بخش‌ناپذیر خودش را نشان می‌دهد و تا آن لحظه بی‌صداست.
    """
    if basis not in POLICIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مبنای تسهیم حمل پشتیبانی نمی‌شود")
    if not line_values:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "هزینه‌ی حمل روی رسیدی که هیچ ردیفِ کالایی ندارد تسهیم‌شدنی نیست",
        )
    total = Decimal(total)
    if total == 0:
        return [Decimal(0)] * len(line_values)

    weights = POLICIES[basis](total, [Decimal(v) for v in line_values])
    weight_sum = sum(weights, Decimal(0))
    if weight_sum <= 0:
        #: مبنایی که همه‌ی وزن‌هایش صفر شد (مثلاً تسهیم به نسبتِ مبلغ روی رسیدی
        #: که همه‌ی ردیف‌هایش رایگان‌اند) به «مساوی» برمی‌گردد، نه به خطا: حمل
        #: واقعاً پرداخت شده و باید جایی بنشیند.
        weights = [Decimal(1)] * len(line_values)
        weight_sum = Decimal(len(line_values))

    shares = [
        (total * weight / weight_sum).quantize(Decimal(1)) for weight in weights
    ]
    shares[-1] += total - sum(shares, Decimal(0))
    return shares
