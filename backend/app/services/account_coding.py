"""قاعده‌ی کدینگِ حساب‌ها — چند رقم در هر سطحِ درخت.

چارتِ حساب در ایران چهار سطح دارد (گروه ← کل ← معین ← تفصیلی) و هر مؤسسه‌ی حسابداری
رویه‌ی خودش را برای طولِ کد دارد. تا امروز این طول هیچ‌جا تعریف نشده بود: کاربر باید
خودش حدس می‌زد و هیچ‌چیز جلوی کدِ نامنظم را نمی‌گرفت.

**رقمِ افزوده در هر سطح، نه طولِ کل.** کدِ هر حساب = کدِ پدرش + N رقم. با پیش‌فرضِ
`(۱، ۱، ۲، ۲)` همان چارتِ فعلی بازتولید می‌شود: ۱ ← ۱۱ ← ۱۱۰۱ ← ۱۱۰۱۰۱.

**حساب‌های موجود دست نمی‌خورند.** کدِ حساب روی اسناد و گزارش‌های چاپ‌شده نشسته؛
بازشماره‌گذاریِ خودکار یعنی شکستنِ چیزی که مالِ ماست نیست. قاعده فقط روی حسابِ *تازه*
اعمال می‌شود — هم در پیشنهادِ کد و هم در اعتبارسنجیِ سرور.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.accounting import Account
from app.models.tenant import Tenant

#: نامِ سطح‌ها، به ترتیبِ عمق.
LEVEL_NAMES = ("گروه", "کل", "معین", "تفصیلی")

#: رقمِ افزوده در هر سطح. عمداً برابرِ ساختارِ چارتِ فعلی است تا حساب‌های موجود با
#: قاعده جور باشند و ارتقا هیچ‌کس را با چارتِ «نامعتبر» رها نکند.
DEFAULT_WIDTHS: tuple[int, ...] = (1, 1, 2, 2)

#: سطحِ عمیق‌تر از تفصیلی هم ممکن است ساخته شود؛ از آخرین رقمِ تعریف‌شده پیروی می‌کند.
MIN_WIDTH, MAX_WIDTH = 1, 6


def get_widths(tenant: Tenant | None) -> list[int]:
    raw = getattr(tenant, "account_code_widths", None) if tenant else None
    if not isinstance(raw, list) or len(raw) != len(DEFAULT_WIDTHS):
        return list(DEFAULT_WIDTHS)
    return [_clamp(n, DEFAULT_WIDTHS[i]) for i, n in enumerate(raw)]


def _clamp(value, fallback: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(MIN_WIDTH, min(MAX_WIDTH, n))


def set_widths(tenant: Tenant, widths: list[int]) -> list[int]:
    clean = [_clamp(n, DEFAULT_WIDTHS[i]) for i, n in enumerate(widths[: len(DEFAULT_WIDTHS)])]
    while len(clean) < len(DEFAULT_WIDTHS):
        clean.append(DEFAULT_WIDTHS[len(clean)])
    tenant.account_code_widths = clean
    return clean


def depth_of(db: Session, parent: Account | None) -> int:
    """عمقِ حسابی که زیرِ `parent` ساخته می‌شود — ریشه = ۰."""
    depth = 0
    node = parent
    seen: set = set()
    while node is not None and node.id not in seen:
        seen.add(node.id)
        depth += 1
        node = db.get(Account, node.parent_id) if node.parent_id else None
    return depth


def width_for(widths: list[int], depth: int) -> int:
    return widths[depth] if depth < len(widths) else widths[-1]


def expected_code_length(widths: list[int], depth: int) -> int:
    """طولِ کلِ کد در این عمق — جمعِ رقم‌های همه‌ی سطح‌ها تا این‌جا."""
    return sum(width_for(widths, d) for d in range(depth + 1))


def sibling_width(db: Session, parent: Account | None) -> int | None:
    """رقمِ افزوده‌ی فرزندانِ موجودِ همین سرفصل — قراردادِ *واقعیِ* این شاخه.

    چارتِ پیش‌فرض یکدست نیست و نباید هم باشد: دارایی‌ها سه سطح دارند (۱ ← ۱۱ ← ۱۱۰۱)
    ولی هزینه‌ها دو سطح (۵ ← ۵۱۰۱). اگر فقط قاعده‌ی عمق را اعمال کنیم، ساختنِ
    هم‌ردیفِ ۵۱۰۱ رد می‌شود — یعنی قاعده‌ای که قرار بود نظم بیاورد، چارتِ موجود را
    نامعتبر می‌کند.

    پس قرارداد بر قاعده مقدم است: اگر همه‌ی فرزندانِ یک سرفصل طولِ یکسان دارند، همان
    طول ادامه پیدا می‌کند. فقط جایی که سابقه‌ای نیست (یا سابقه ناهمگون است) قاعده
    تصمیم می‌گیرد.
    """
    prefix = parent.code if parent is not None else ""
    query = db.query(Account.code)
    query = query.filter(Account.parent_id == parent.id) if parent is not None else query.filter(
        Account.parent_id.is_(None)
    )
    widths = {
        len(code) - len(prefix)
        for (code,) in query.all()
        if code.startswith(prefix) and len(code) > len(prefix) and code.isdigit()
    }
    return widths.pop() if len(widths) == 1 else None


def effective_width(db: Session, parent: Account | None, widths: list[int], depth: int) -> int:
    return sibling_width(db, parent) or width_for(widths, depth)


def level_name(depth: int) -> str:
    return LEVEL_NAMES[depth] if depth < len(LEVEL_NAMES) else LEVEL_NAMES[-1]


def preview(widths: list[int]) -> list[str]:
    """نمونه‌ی کد در هر سطح — «۱ ← ۱۱ ← ۱۱۰۱ ← ۱۱۰۱۰۱»."""
    out: list[str] = []
    code = ""
    for depth in range(len(widths)):
        code += "1".rjust(width_for(widths, depth), "0")
        out.append(code)
    return out


def validate_new_code(db: Session, *, code: str, parent: Account | None, widths: list[int]) -> None:
    """کدِ حسابِ تازه باید با قاعده جور باشد. خطا را به‌صورتِ ValueError می‌دهد.

    دو شرط: طولِ درست برای این عمق، و شروع‌شدن با کدِ پدر. شرطِ دوم همان چیزی است که
    درخت را واقعاً درخت نگه می‌دارد — بدونِ آن، کدِ ۹۹۹۹ می‌توانست زیرِ سرفصلِ ۱۱ بنشیند
    و هر گزارشِ مبتنی‌بر‌کد بی‌معنا شود.
    """
    depth = depth_of(db, parent)
    prefix_len = len(parent.code) if parent is not None else 0
    expected = prefix_len + effective_width(db, parent, widths, depth)
    name = level_name(depth)

    if not code.isdigit():
        raise ValueError(f"کد حساب باید فقط رقم باشد (سطحِ {name}: {expected} رقم)")
    if len(code) != expected:
        raise ValueError(
            f"کد حسابِ سطحِ «{name}» باید {expected} رقم باشد؛ «{code}» {len(code)} رقم است"
        )
    if parent is not None and not code.startswith(parent.code):
        raise ValueError(f"کد حساب باید با کدِ سرفصلِ والد ({parent.code}) شروع شود")


def suggest_code(db: Session, *, parent: Account | None, widths: list[int]) -> str:
    """کدِ آزادِ بعدی زیرِ یک سرفصل، طبقِ قاعده."""
    depth = depth_of(db, parent)
    width = effective_width(db, parent, widths, depth)
    prefix = parent.code if parent is not None else ""

    used = {
        code
        for (code,) in db.query(Account.code).all()
        if code.startswith(prefix) and len(code) == len(prefix) + width
    }
    for n in range(1, 10**width):
        candidate = prefix + str(n).rjust(width, "0")
        if candidate not in used:
            return candidate
    # همه‌ی کدهای این سطح پر شده — نادر، ولی نباید بی‌صدا کدِ تکراری بدهیم.
    raise ValueError(f"همه‌ی کدهای {width}رقمی زیرِ این سرفصل استفاده شده‌اند")
