"""آیا این عاملِ حقوق در این مبنا شرکت می‌کند — و با چه ضریبی.

**یک قاعده، پنج مصرف‌کننده.** فیشِ حقوق (مبنای بیمه و مالیات)، عیدی، سنوات و
بازخریدِ مرخصی همه از همین‌جا می‌پرسند. فصلِ مرجع صریح است که نباید چهار موتورِ
مستقل با چهار `switch` ساخته شود؛ این ماژول همان یک‌جا است.

## پیش‌فرض = رفتارِ امروز

جدولِ `payroll_factor_participations` فقط **استثنا** نگه می‌دارد. نبودنِ ردیف
یعنی پیش‌فرض، و پیش‌فرض عمداً همان فرمولی است که کوبیتا پیش از مهاجرتِ ۰۱۳۹
داشت:

    مبنای بیمه / مالیات     →  همه‌ی عوامل، ضریبِ ۱   (مبنا کلِ ناخالص بود)
    مبنای عیدی/سنوات/مرخصی  →  فقط «حقوق پایه»        (مبنا `base_salary` بود)

پس جدولِ خالی یعنی هیچ عددی عوض نشده. این عدمِ‌تقارن یک رمزگذاریِ دقیق است، نه
یک سلیقه — و تستی همین را قفل می‌کند.
"""
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.payroll import BENEFIT_BASE_PURPOSES, PayrollFactorParticipation

#: نگاشتِ `(شناسه‌ی عامل، هدف) → ضریب`. همان چیزی که `resolve` مصرف می‌کند.
ParticipationMap = dict[tuple[UUID, str], Decimal]


def participation_map(db: Session) -> ParticipationMap:
    """همه‌ی استثناهای مستأجرِ جاری، در یک پرس‌وجو.

    یک‌بار خوانده می‌شود و برای کلِ اجرا همان می‌ماند: یک دوره‌ی حقوق باید با یک
    نسخه‌ی منسجم از قاعده‌ها حساب شود، نه اینکه نیمی از کارکنان قاعده‌ی قدیم
    بگیرند و نیمی قاعده‌ی تازه.
    """
    return {
        (row.factor_id, row.purpose): (Decimal(str(row.coefficient)) if row.included else Decimal(0))
        for row in db.query(PayrollFactorParticipation).all()
    }


def coefficient(factor, purpose: str, rules: ParticipationMap | None = None) -> Decimal:
    """ضریبِ شرکتِ یک عامل در یک مبنا. صفر یعنی اصلاً شرکت نمی‌کند.

    `factor` می‌تواند `None` باشد (ردیفِ بی‌عامل روی قراردادهای قدیمی)؛ آن‌وقت
    مثلِ عاملِ بی‌کلید رفتار می‌شود.
    """
    if rules:
        explicit = rules.get((getattr(factor, "id", None), purpose))
        if explicit is not None:
            return explicit
    if purpose in BENEFIT_BASE_PURPOSES:
        #: پیش‌فرضِ سه مبنای مزایا: فقط حقوق پایه — دقیقاً همان `contract.base_salary`
        #: که تا امروز تنها ورودیِ عیدی، سنوات و بازخریدِ مرخصی بود.
        return Decimal(1) if getattr(factor, "system_key", "") == "base" else Decimal(0)
    #: پیش‌فرضِ بیمه و مالیات: همه شریک‌اند — همان «مبنا = کلِ ناخالص».
    return Decimal(1)


def _benefit_lines(contract):
    for line in getattr(contract, "lines", []) or []:
        factor = getattr(line, "factor", None)
        if factor is not None and factor.category != "benefit":
            continue
        yield line, factor


def benefit_base(contract, purpose: str, rules: ParticipationMap | None = None) -> Decimal:
    """مبنای پولیِ یک هدف، از ردیف‌های **مزایای** قرارداد.

    **این همان جایی است که فصلِ مرجع «اشتباهِ خطرناک» می‌نامد.** نوشتنِ
    `ذخیره‌ی مرخصی = مانده × حقوقِ پایه` فرض می‌کند مبنا فقط پایه است؛ ولی فرم
    نشان می‌دهد چند عامل (حقِ سرپرستی، حقِ مسئولیت، حقِ سنوات، پایه) مبنا را
    می‌سازند.

    قراردادِ بی‌ردیف (پیش از مدلِ عامل‌محور) `base_salary` را می‌گیرد — وگرنه
    مبنایش صفر می‌شد و عیدیِ آن کارمند ناگهان صفر.
    """
    total = Decimal(0)
    seen_any = False
    for line, factor in _benefit_lines(contract):
        seen_any = True
        total += Decimal(str(line.amount)) * coefficient(factor, purpose, rules)
    if not seen_any:
        return Decimal(str(contract.base_salary))
    return total


def excluded_from_wage_base(contract, purpose: str, proration: Decimal, rules: ParticipationMap | None = None) -> Decimal:
    """چقدر از ناخالص **به این مبنا نمی‌آید** — برای بیمه و مالیات.

    مبنا از ناخالص کم می‌شود نه از صفر ساخته می‌شود، چون ناخالص اجزایی دارد که
    عامل ندارند (اضافه‌کار، و مزایای قراردادهای قدیمی روی ستون‌ها). ساختنِ مبنا
    از صفر آن‌ها را جا می‌انداخت؛ کم‌کردنِ استثناها جا نمی‌اندازد.
    """
    total = Decimal(0)
    for line, factor in _benefit_lines(contract):
        share = Decimal(1) - coefficient(factor, purpose, rules)
        if share > 0:
            total += Decimal(str(line.amount)) * proration * share
    return total
