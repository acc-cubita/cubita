"""قیمتِ کالا به‌صورتِ **قاعده**، نه یک عدد (§۳۷–§۴۳ِ فصلِ کالا، و کلِ فصلِ اعلامیه قیمت).

§۳۸ صریح است که `product.sale_price = 100` مدلِ کافی‌ای نیست: یک کالا می‌تواند
هم‌زمان قیمتِ عمده به ریال، خرده به ریال و صادراتی به دلار داشته باشد — و قیمتِ
کارتن با قیمتِ عدد یکی نیست (§۴۱).

---

**این فایل تنها موتورِ قیمتِ فروش است (§۵۴).**

تا پیش از فصلِ «اعلامیه قیمت» سه موتور وجود داشت: همین، و یک نگاشتِ
`item_id → price` در فرمِ فاکتور، و سومی در صندوق. هر سه جوابِ متفاوت می‌دادند،
چون آن دوتا `effective_from` و `is_active` و هر چهار بُعدِ زمینه را نمی‌دیدند.
نتیجه این بود که فرم یک قیمت پر می‌کرد و سرور با قاعده‌ی **دیگری** اعتبارش را
می‌سنجید. حالا هر دو مصرف‌کننده از `resolve_detail` می‌آیند.

**دو چیز که این‌جا ساخته نمی‌شود.**

نوعِ فروش، ارز، گروهِ مشتری و گروهِ فروشِ کالا از داده‌ی موجودِ کوبیتا می‌آیند
(§۳۹ §۴۰): فصل منع می‌کند که زیرسیستمِ قیمت تعریفِ موازیِ خودش را بسازد.

و **قیمتِ فاکتور از این‌جا نمی‌آید** (§۴۳ §۱۰ §۹۳). این *سیاست* است؛ قیمتی که روی
ردیفِ فاکتور نشسته یک مقدارِ تاریخی است و با عوض‌شدنِ این جدول تغییر نمی‌کند.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.audit import record_change
from app.models.advanced_inventory import PriceList, PriceListItem
from app.models.inventory import Contact
from app.models.sales_ops import BULK_PRICE_MODES, DiscountItemGroupMember



# ────────────────────────── حلِ قیمت ──────────────────────────


@dataclass(frozen=True)
class ResolvedPrice:
    """جوابِ §۲۱: «چرا فیِ این ردیف این عدد است؟»

    فصل صریح می‌گوید حل‌کننده نباید فقط یک عدد برگرداند. بدونِ `rule_id` و
    `announcement_name` هیچ‌کس نمی‌تواند بگوید این نرخ از کجا آمد، و بدونِ
    `min_price`/`max_price` رابط مجبور می‌شود حدها را خودش دوباره حساب کند —
    یعنی همان دو-موتور-شدنی که این فایل برای رفعش نوشته شده.
    """

    rule_id: UUID
    announcement_id: UUID
    announcement_name: str
    effective_from: date_
    unit_price: Decimal
    currency_code: str
    addition_percent: Decimal
    allow_rate_change: bool
    allow_discount_change: bool
    max_increase_percent: Decimal
    max_decrease_percent: Decimal
    #: `None` یعنی از آن سمت حدی نیست (§۲۸ — حدها نامتقارن‌اند و صفر یعنی بی‌حد).
    min_price: Decimal | None
    max_price: Decimal | None
    #: §۳۵ §۳۷ — بیش از یک قاعده با همین درجه‌ی مشخص‌بودن خواند. برنده قطعی و
    #: پایدار است، ولی پیکربندی مبهم است و کاربر باید بداند.
    ambiguous: bool


def _item_group_ids(db: Session, item_id: UUID) -> set[UUID]:
    """گروه‌های فروشی که این کالا عضوشان است (§۱۴)."""
    return {
        g
        for (g,) in db.query(DiscountItemGroupMember.group_id).filter(
            DiscountItemGroupMember.item_id == item_id
        )
    }


def _rank(row: PriceListItem) -> tuple:
    """کلیدِ **کاملاً مرتب** برای انتخابِ برنده — نه `max()` روی ترتیبِ دیتابیس.

    §۳۷ می‌گوید تطابقِ مبهم یا باید ممنوع باشد یا قابلِ توضیح، و «ردیفی که
    دیتابیس اول برگرداند» خطرناک است — چون دو کوئری می‌توانند دو قیمت بدهند.

    * **هدف مقدم بر شمارشِ ابعاد است.** قاعده‌ای که خودِ کالا را نام برده بر
      قاعده‌ی گروه می‌چربد، و این حدس نیست: مجموعه‌ی کالاهای اولی زیرمجموعه‌ی
      دومی است.
    * بینِ هم‌رتبه‌ها، هر بُعدِ صریحِ بیشتر (نوع فروش، واحد، گروه مشتری) جلوتر
      است — همان معیارِ قبلی.
    * و در پایان `id` می‌آید تا انتخاب **پایدار** بماند حتی وقتی پیکربندی مبهم
      است. مبهم‌بودن با `ambiguous` به بیرون گزارش می‌شود، نه با یک قیمتِ تصادفی.
    """
    target = 2 if row.item_id is not None else 1
    dims = sum(
        1
        for value in (row.sale_type_id, row.unit_id, row.contact_group_id)
        if value is not None
    )
    return (target, dims, str(row.id))


def _matches(
    row: PriceListItem, *, sale_type_id, unit_id, contact_group_id, currency_code
) -> bool:
    """`NULL` در هر بُعد یعنی «هر مقداری».

    پس ردیف‌های موجود — که هر سه بُعدشان خالی است — دقیقاً مثلِ امروز روی همه‌ی
    زمینه‌ها می‌نشینند و هیچ قیمتی با این تغییر گم نمی‌شود.
    """
    if row.currency_code != currency_code:
        return False
    for row_value, wanted in (
        (row.sale_type_id, sale_type_id),
        (row.unit_id, unit_id),
        (row.contact_group_id, contact_group_id),
    ):
        if row_value is not None and row_value != wanted:
            return False
    return True


def _resolve_with_flag(
    db: Session,
    item_id: UUID,
    *,
    on: date_ | None = None,
    sale_type_id: UUID | None = None,
    unit_id: UUID | None = None,
    contact_id: UUID | None = None,
    currency_code: str = "IRR",
) -> tuple[PriceListItem | None, bool]:
    on = on or date_.today()
    contact_group_id = None
    if contact_id is not None:
        contact = db.get(Contact, contact_id)
        contact_group_id = contact.group_id if contact else None

    group_ids = _item_group_ids(db, item_id)
    #: قاعده یا این کالا را نام می‌برد، یا یکی از گروه‌های فروشی که عضوش است (§۱۴).
    target = PriceListItem.item_id == item_id
    if group_ids:
        target = or_(
            target,
            and_(PriceListItem.item_id.is_(None), PriceListItem.item_group_id.in_(group_ids)),
        )

    rows = (
        db.query(PriceListItem, PriceList.effective_from)
        .join(PriceList, PriceList.id == PriceListItem.price_list_id)
        .filter(
            target,
            PriceList.is_active.is_(True),
            PriceList.effective_from <= on,
        )
        .order_by(PriceList.effective_from.desc())
        .all()
    )
    if not rows:
        return None, False

    newest = rows[0][1]
    candidates = [
        row
        for row, effective_from in rows
        if effective_from == newest
        and _matches(
            row,
            sale_type_id=sale_type_id,
            unit_id=unit_id,
            contact_group_id=contact_group_id,
            currency_code=currency_code,
        )
    ]
    if not candidates:
        return None, False

    ordered = sorted(candidates, key=_rank, reverse=True)
    winner = ordered[0]
    ambiguous = len(ordered) > 1 and _rank(ordered[1])[:2] == _rank(winner)[:2]
    return winner, ambiguous


def resolve(
    db: Session,
    item_id: UUID,
    *,
    on: date_ | None = None,
    sale_type_id: UUID | None = None,
    unit_id: UUID | None = None,
    contact_id: UUID | None = None,
    currency_code: str = "IRR",
) -> PriceListItem | None:
    """مشخص‌ترین قاعده‌ی قیمتی که با این زمینه می‌خواند.

    از آخرین اعلامیه‌ی **اجراشده تا این تاریخ** می‌آید، نه از هر اعلامیه‌ی فعالی
    — همان قاعده‌ای که `quote_line` از قبل داشت. بینِ ردیف‌های همان اعلامیه،
    مشخص‌ترین می‌برد (`_rank`).
    """
    winner, _ = _resolve_with_flag(
        db,
        item_id,
        on=on,
        sale_type_id=sale_type_id,
        unit_id=unit_id,
        contact_id=contact_id,
        currency_code=currency_code,
    )
    return winner


def _bounds(rule: PriceListItem) -> tuple[Decimal | None, Decimal | None]:
    """کفِ و سقفِ مجازِ نرخ (§۲۹).

    **یک‌جا حساب می‌شود و هم گارد و هم رابط همین را می‌خوانند** — وگرنه رابط یک
    حد نشان می‌دهد و سرور حدِ دیگری را اعمال می‌کند، که دقیقاً همان شکافی است که
    این فصل برای بستنش نوشته شده (§۹۶).

    کف به پایین و سقف به بالا رند می‌شود تا عددی که روی صفحه نوشته شده هرگز
    خودش رد نشود. قیمت `Numeric(18, 0)` است، پس رند به ریالِ صحیح.
    """
    base = Decimal(rule.price or 0)
    if base <= 0:
        return None, None
    if not rule.allow_rate_change:
        return base, base

    one = Decimal(1)
    down = Decimal(rule.max_decrease_percent or 0)
    up = Decimal(rule.max_increase_percent or 0)
    #: صفر یعنی **بی‌حد** — یعنی رفتارِ امروز، پس هیچ فروشی یک‌شبه مسدود نمی‌شود.
    low = (base * (one - down / 100)).quantize(one, rounding=ROUND_FLOOR) if down > 0 else None
    high = (base * (one + up / 100)).quantize(one, rounding=ROUND_CEILING) if up > 0 else None
    return low, high


def resolve_detail(
    db: Session,
    item_id: UUID,
    *,
    on: date_ | None = None,
    sale_type_id: UUID | None = None,
    unit_id: UUID | None = None,
    contact_id: UUID | None = None,
    currency_code: str = "IRR",
) -> ResolvedPrice | None:
    """همان `resolve`، ولی با تمامِ چیزی که برای *توضیحِ* نرخ لازم است (§۲۱ §۹۱)."""
    rule, ambiguous = _resolve_with_flag(
        db,
        item_id,
        on=on,
        sale_type_id=sale_type_id,
        unit_id=unit_id,
        contact_id=contact_id,
        currency_code=currency_code,
    )
    if rule is None:
        return None
    announcement = db.get(PriceList, rule.price_list_id)
    low, high = _bounds(rule)
    return ResolvedPrice(
        rule_id=rule.id,
        announcement_id=rule.price_list_id,
        announcement_name=announcement.name if announcement else "",
        effective_from=announcement.effective_from if announcement else (on or date_.today()),
        unit_price=Decimal(rule.price or 0),
        currency_code=rule.currency_code,
        addition_percent=Decimal(rule.addition_percent or 0),
        allow_rate_change=rule.allow_rate_change,
        allow_discount_change=rule.allow_discount_change,
        max_increase_percent=Decimal(rule.max_increase_percent or 0),
        max_decrease_percent=Decimal(rule.max_decrease_percent or 0),
        min_price=low,
        max_price=high,
        ambiguous=ambiguous,
    )


# ────────────────────── گاردِ سیاستِ قیمت ──────────────────────


def assert_within_policy(
    db: Session,
    item,
    unit_price: Decimal,
    *,
    discount: Decimal | None = None,
    on: date_ | None = None,
    sale_type_id: UUID | None = None,
    unit_id: UUID | None = None,
    contact_id: UUID | None = None,
    currency_code: str = "IRR",
) -> PriceListItem | None:
    """§۲۴ §۲۵ §۲۷ §۲۸ — کاربر چقدر اجازه‌ی تغییرِ نرخ و تخفیف دارد.

    **پیش‌فرض بی‌حد است.** ردیف‌های موجود `allow_rate_change = true`،
    `allow_discount_change = true` و هر دو حد صفر دارند، که یعنی «بدونِ کنترل» —
    پس هیچ فروشی با این قابلیت یک‌شبه مسدود نمی‌شود. فقط کسی که صریحاً حد
    بگذارد کنترل می‌گیرد.

    و اگر هیچ قاعده‌ای با این زمینه نخواند، سیاستی وجود ندارد که نقض شود (§۵۸ —
    این رفتارِ امروز است و فصل منع می‌کند که جایش چیزِ تازه‌ای حدس زده شود).

    قاعده‌ی برنده برگردانده می‌شود تا ثبتِ فاکتور بتواند ردِ قیمت را روی ردیف
    بنشاند بی‌آنکه حل را دو بار انجام دهد.
    """
    rule = resolve(
        db,
        item.id,
        on=on,
        sale_type_id=sale_type_id,
        unit_id=unit_id,
        contact_id=contact_id,
        currency_code=currency_code,
    )
    if rule is None:
        return None

    #: §۲۵ — تخفیف سیاستِ خودش را دارد. عمداً پیش از گاردِ نرخ می‌آید تا پیامِ
    #: «تخفیف قفل است» با پیامِ «نرخ قفل است» قاطی نشود.
    if discount is not None and Decimal(discount) > 0 and not rule.allow_discount_change:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"تخفیفِ «{item.name}» در اعلامیه‌ی قیمت قفل است و روی فاکتور تغییر نمی‌کند.",
        )

    base = Decimal(rule.price or 0)
    if base <= 0:
        return rule
    price = Decimal(unit_price or 0)
    if price == base:
        return rule

    if not rule.allow_rate_change:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"نرخِ «{item.name}» در اعلامیه‌ی قیمت قفل است و تغییر نمی‌کند "
            f"(نرخِ مصوب: {base:,}).",
        )

    low, high = _bounds(rule)
    if high is not None and price > high:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"نرخِ «{item.name}» بیش از حدِ مجاز بالا رفته: سقفِ افزایش "
            f"{Decimal(rule.max_increase_percent)}٪ است، یعنی حداکثر {high:,} "
            f"(نرخِ مصوب: {base:,}).",
        )
    if low is not None and price < low:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"تخفیفِ «{item.name}» بیش از حدِ مجاز است: سقفِ کاهش "
            f"{Decimal(rule.max_decrease_percent)}٪ است، یعنی حداقل {low:,} "
            f"(نرخِ مصوب: {base:,}).",
        )
    return rule


# ────────────────────── تغییرِ گروهیِ فی ──────────────────────


def round_price(value: Decimal, step: int) -> Decimal:
    """رند به نزدیک‌ترین مضربِ `step` — **یک بار، در دامنه** (§۴۹ §۵۱).

    فصل «رقمِ اعشار» را در دیالوگ نشان می‌دهد، ولی `price` این‌جا
    `Numeric(18, 0)` است — ریالِ صحیح. پس اعشار روی آن جایی ندارد و تطبیقِ
    صادقانه‌اش **دقتِ رند** است: به ریال، ده‌ریال، صد، هزار…

    و یک‌جا انجام می‌شود، نه در بک‌اند و رابط و چاپ جداگانه — سه رندِ مستقل
    یعنی سه عدد.
    """
    value = max(value, Decimal(0))
    one = Decimal(1)
    if step <= 1:
        return value.quantize(one, rounding=ROUND_HALF_UP)
    unit = Decimal(step)
    return (value / unit).quantize(one, rounding=ROUND_HALF_UP) * unit


def apply_bulk_mode(price: Decimal, mode: str, value: Decimal) -> Decimal:
    """ریاضیِ یک ردیف. جدا نگه داشته شده تا تست بتواند مستقیم بسنجدش."""
    hundred = Decimal(100)
    if mode == "increase_percent":
        return price * (1 + value / hundred)
    if mode == "decrease_percent":
        return price * (1 - value / hundred)
    if mode == "increase_amount":
        return price + value
    if mode == "decrease_amount":
        return price - value
    if mode == "fixed":
        return value
    #: "none" — قیمت دست نمی‌خورد؛ فقط رندِ پایین‌دستی اعمال می‌شود (§۵۲).
    return price


@dataclass
class BulkResult:
    """نتیجه‌ی یک فرمانِ تغییرِ گروهی.

    `id` شناسه‌ی اعلامیه است چون `idempotent(...)` منبعِ عملیات را با آن پی
    می‌گیرد. `replayed` صریح است تا کلاینتی که دوباره فرستاده بداند **هیچ‌چیز
    دوباره اعمال نشد** — نه اینکه خیال کند صفر ردیف واجد شرایط بوده.
    """

    id: UUID
    changed: int
    replayed: bool = False
    rows: list[dict] | None = None


#: سقفِ ردیف‌هایی که قبل/بعدشان در رکوردِ حسابرسی می‌نشیند. فراتر از این فقط
#: شمارش ثبت می‌شود — یک فرمانِ ده‌هزارردیفی رکوردی می‌سازد که دیگر کسی
#: نمی‌خواندش، و ردِ حسابرسی که خوانده نشود ردِ حسابرسی نیست.
_AUDIT_ROW_CAP = 500

_BULK_LABEL = {
    "increase_percent": "افزایشِ درصدی",
    "increase_amount": "افزایشِ مبلغی",
    "decrease_percent": "کاهشِ درصدی",
    "decrease_amount": "کاهشِ مبلغی",
    "fixed": "مبلغِ ثابت",
    "none": "بدونِ تغییر (فقط رند)",
}


def bulk_change(
    db: Session,
    price_list_id: UUID,
    *,
    mode: str,
    value: Decimal,
    rounding: int = 1,
    rule_ids: list[UUID] | None = None,
    item_ids: list[UUID] | None = None,
    sale_type_id: UUID | None = None,
    currency_code: str | None = None,
) -> BulkResult:
    """تغییرِ گروهیِ فیِ یک اعلامیه (§۴۲–§۴۸).

    **چرا این تابع از یک حلقه‌ی ساده خطرناک‌تر است.** `for row: row.price *= 1.2`
    درست به‌نظر می‌رسد و سه شکستِ بی‌صدا دارد که فصل هر سه را نام می‌برد:

    * **تکرارِ درخواست (§۴۵ §۴۶ §۹۴).** پاسخ گم می‌شود، کلاینت دوباره می‌فرستد،
      و ۱۰۰ به‌جای ۱۲۰ می‌شود ۱۴۴. دفاعش این‌جا نیست — در `idempotent(...)`ِ
      مسیر است — ولی این تابع باید در یک تراکنش بماند تا آن دفاع معنا بدهد.
    * **دو مدیرِ هم‌زمان (§۴۷ §۸۹).** بدونِ قفل، «آخری می‌برد» بی‌هشدار اتفاق
      می‌افتد. `with_for_update()` روی ردیف‌های هدف همان الگوی `lock_items` است.
    * **دامنه‌ی لغزان (§۴۸).** ردیف‌ها **داخلِ** همان قفل انتخاب می‌شوند، پس
      «آیا قاعده‌ای که وسطِ کار اضافه شد جزوِ این فرمان بود؟» جوابِ قطعی دارد.

    و رند **یک بار** در پایان می‌خورد (§۵۱)، نه جدا در هر لایه.
    """
    if mode not in BULK_PRICE_MODES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "حالتِ تغییرِ گروهی نامعتبر است")
    if rounding < 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "دقتِ رند باید دستِ‌کم ۱ باشد")

    announcement = db.get(PriceList, price_list_id)
    if announcement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اعلامیه‌ی قیمت یافت نشد")

    query = db.query(PriceListItem).filter(PriceListItem.price_list_id == price_list_id)
    if rule_ids:
        query = query.filter(PriceListItem.id.in_(rule_ids))
    if item_ids:
        query = query.filter(PriceListItem.item_id.in_(item_ids))
    if sale_type_id is not None:
        query = query.filter(PriceListItem.sale_type_id == sale_type_id)
    if currency_code:
        query = query.filter(PriceListItem.currency_code == currency_code)

    # ترتیب لازم است نه تزئینی: دو فرمانِ هم‌زمان روی ردیف‌های مشترک بدونِ ترتیبِ
    # قطعی می‌توانند آن‌ها را معکوس قفل کنند و deadlock بدهند.
    rows = query.order_by(PriceListItem.id).with_for_update().all()
    if not rows:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "هیچ ردیفی از این اعلامیه با این شرایط پیدا نشد"
        )

    changed: list[dict] = []
    for row in rows:
        before = Decimal(row.price or 0)
        after = round_price(apply_bulk_mode(before, mode, Decimal(value)), rounding)
        if after == before:
            continue
        row.price = after
        changed.append({"rule_id": str(row.id), "item_id": str(row.item_id or ""),
                        "from": before, "to": after})

    summary = (
        f"تغییرِ گروهیِ فیِ اعلامیه‌ی «{announcement.name}» — "
        f"{_BULK_LABEL[mode]}"
        + (f" {Decimal(value):,}" if mode != "none" else "")
        + f"، رند به {rounding:,} ریال، {len(changed)} ردیف"
    )
    #: §۸۵ — قبل/بعد ثبت می‌شود. ثبتِ خودکارِ `before_flush` این را نمی‌گیرد چون
    #: خودِ `PriceList` تغییر نمی‌کند و ردیف‌ها عمداً مدلِ تحتِ حسابرسی نیستند
    #: (یک فاکتورِ ده‌ردیفه نباید یازده رکوردِ حسابرسی بسازد).
    record_change(
        db,
        announcement,
        {
            "فرمان": {"from": None, "to": summary},
            "ردیف‌ها": {
                "from": None,
                "to": changed[:_AUDIT_ROW_CAP]
                if len(changed) <= _AUDIT_ROW_CAP
                else f"{len(changed)} ردیف (بیش از سقفِ ثبتِ جزئیات)",
            },
        },
        summary,
    )
    db.flush()
    return BulkResult(id=price_list_id, changed=len(changed), rows=changed)
