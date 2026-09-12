"""قیمتِ کالا به‌صورتِ **قاعده**، نه یک عدد (§۳۷–§۴۳).

§۳۸ صریح است که `product.sale_price = 100` مدلِ کافی‌ای نیست: یک کالا می‌تواند
هم‌زمان قیمتِ عمده به ریال، خرده به ریال و صادراتی به دلار داشته باشد — و قیمتِ
کارتن با قیمتِ عدد یکی نیست (§۴۱).

---

**دو چیز که این‌جا ساخته نمی‌شود.**

نوعِ فروش، ارز و گروهِ مشتری از داده‌ی موجودِ کوبیتا می‌آیند (§۳۹ §۴۰): فصل منع
می‌کند که زیرسیستمِ قیمت تعریفِ موازیِ خودش را بسازد.

و **قیمتِ فاکتور از این‌جا نمی‌آید** (§۴۳). این *سیاست* است؛ قیمتی که روی ردیفِ
فاکتور نشسته یک مقدارِ تاریخی است و با عوض‌شدنِ این جدول تغییر نمی‌کند.
"""
from __future__ import annotations

from datetime import date as date_
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.advanced_inventory import PriceList, PriceListItem
from app.models.inventory import Contact


def _specificity(row: PriceListItem) -> int:
    """چند بُعدِ این ردیف صریح است.

    ردیفی که نوعِ فروش و واحد و گروهِ مشتری را نام برده، از ردیفِ «هر زمینه‌ای»
    مشخص‌تر است و باید برنده شود — وگرنه قیمتِ عمومی، قیمتِ ویژه را می‌پوشاند.
    """
    return sum(
        1
        for value in (row.sale_type_id, row.unit_id, row.contact_group_id)
        if value is not None
    )


def _matches(row: PriceListItem, *, sale_type_id, unit_id, contact_group_id, currency_code) -> bool:
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
    مشخص‌ترین می‌برد.
    """
    on = on or date_.today()
    contact_group_id = None
    if contact_id is not None:
        contact = db.get(Contact, contact_id)
        contact_group_id = contact.group_id if contact else None

    rows = (
        db.query(PriceListItem, PriceList.effective_from)
        .join(PriceList, PriceList.id == PriceListItem.price_list_id)
        .filter(
            PriceListItem.item_id == item_id,
            PriceList.is_active.is_(True),
            PriceList.effective_from <= on,
        )
        .order_by(PriceList.effective_from.desc())
        .all()
    )
    if not rows:
        return None

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
        return None
    return max(candidates, key=_specificity)


def assert_within_policy(
    db: Session,
    item,
    unit_price: Decimal,
    *,
    on: date_ | None = None,
    sale_type_id: UUID | None = None,
    unit_id: UUID | None = None,
    contact_id: UUID | None = None,
    currency_code: str = "IRR",
) -> None:
    """§۴۲ — کاربر چقدر اجازه‌ی تغییرِ نرخ دارد.

    **پیش‌فرض بی‌حد است.** ردیف‌های موجود `allow_rate_change = true` و هر دو حد
    صفر دارند، که یعنی «بدونِ کنترل» — پس هیچ فروشی با این قابلیت یک‌شبه مسدود
    نمی‌شود. فقط کسی که صریحاً حد بگذارد کنترل می‌گیرد.

    و اگر هیچ قاعده‌ای با این زمینه نخواند، سیاستی وجود ندارد که نقض شود.
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
        return
    base = Decimal(rule.price or 0)
    if base <= 0:
        return
    price = Decimal(unit_price or 0)
    if price == base:
        return

    if not rule.allow_rate_change:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"نرخِ «{item.name}» در اعلامیه‌ی قیمت قفل است و تغییر نمی‌کند "
            f"(نرخِ مصوب: {base:,}).",
        )

    deviation = (price - base) / base * Decimal(100)
    limit_up = Decimal(rule.max_increase_percent or 0)
    limit_down = Decimal(rule.max_decrease_percent or 0)

    if deviation > 0 and limit_up > 0 and deviation > limit_up:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"نرخِ «{item.name}» بیش از حدِ مجاز بالا رفته: "
            f"سقفِ افزایش {limit_up}٪ است و این ردیف {deviation.quantize(Decimal('0.01'))}٪ بالاتر از "
            f"نرخِ مصوب ({base:,}) است.",
        )
    if deviation < 0 and limit_down > 0 and -deviation > limit_down:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"تخفیفِ «{item.name}» بیش از حدِ مجاز است: "
            f"سقفِ کاهش {limit_down}٪ است و این ردیف {(-deviation).quantize(Decimal('0.01'))}٪ پایین‌تر از "
            f"نرخِ مصوب ({base:,}) است.",
        )
