"""واحدِ سنجش به‌عنوان داده‌ی پایه، و **تنها** موتورِ تبدیلِ واحد.

§۲۱ صریح است: «موتورِ تبدیل باید بینِ خرید، فروش، انبار و صندوق مشترک باشد؛ هر
فرم خودش تبدیل انجام ندهد.» پس تبدیل یک تابع دارد و فقط همین‌جا زندگی می‌کند.

---

**چه چیزی این‌جا ساخته نمی‌شود.** ورودِ نسبتِ متغیر در تراکنش. §۲۲ می‌گوید مدل
باید تفاوتِ نسبتِ ثابت و متغیر را *بشناسد*، ولی رفتارِ ورودش را «تا وقتی
workflowهای اختصاصی تثبیتش کنند» نهایی نکن. پس `to_primary` روی کالای
نسبت‌متغیر **خطا می‌دهد** به‌جای اینکه عددی از خودش دربیاورد — چون نسبتِ متغیر
اساساً یعنی «این عدد را نمی‌شود از پیش دانست».

**و واحد موجودی نیست (§۱۶).** داشتنِ واحد به هیچ قلمی رفتارِ انباری نمی‌دهد؛
«۵ ساعت مشاوره» واحد دارد و موجودی ندارد.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.inventory import CONVERSION_MODES, Item, UnitOfMeasure


def resolve(db: Session, unit_id: UUID) -> UnitOfMeasure:
    unit = db.get(UnitOfMeasure, unit_id)
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "واحد سنجش یافت نشد")
    return unit


def get_or_create(db: Session, name: str) -> UnitOfMeasure:
    """واحد را با نامش پیدا می‌کند و اگر نبود می‌سازد.

    برای مسیرهایی که واحد را هنوز به‌صورتِ نوشتار می‌دهند (ورودِ گروهیِ کالا،
    بازار، بازیابیِ پشتیبان). این **نشتِ متنِ آزاد را می‌بندد**: هر نوشتاری که از
    بیرون می‌آید یک ردیفِ واحد می‌شود، نه یک رشته‌ی سرگردان روی کالا.
    """
    name = (name or "").strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نامِ واحد نمی‌تواند خالی باشد")
    unit = db.query(UnitOfMeasure).filter(UnitOfMeasure.name == name).first()
    if unit is None:
        unit = UnitOfMeasure(name=name)
        db.add(unit)
        db.flush()
    return unit


def assert_usable(db: Session, unit_id: UUID | None) -> UnitOfMeasure | None:
    """واحدِ غیرفعال در تعریفِ تازه انتخاب نمی‌شود.

    کالاهایی که از قبل رویش نشسته‌اند دست نمی‌خورند — غیرفعال‌کردن گذشته را پاک
    نمی‌کند، فقط جلوی انتخابِ تازه را می‌گیرد.
    """
    if unit_id is None:
        return None
    unit = resolve(db, unit_id)
    if not unit.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"واحدِ «{unit.name}» غیرفعال است و انتخاب نمی‌شود.",
        )
    return unit


def assert_can_deactivate(db: Session, unit: UnitOfMeasure) -> None:
    """واحدی که هنوز روی کالایی نشسته بی‌صدا غیرفعال نمی‌شود.

    مثلِ انبار: پیام تعداد را می‌گوید، چون «عملیات ناموفق» کاربر را می‌فرستد
    دنبالِ چیزی که خودمان می‌دانیم.
    """
    used = (
        db.query(Item.id)
        .filter((Item.primary_unit_id == unit.id) | (Item.secondary_unit_id == unit.id))
        .count()
    )
    if used:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"واحدِ «{unit.name}» روی {used:,} قلم کالا نشسته و غیرفعال نمی‌شود. "
            "اول واحدِ آن کالاها را عوض کنید.",
        )


def sync_item_unit(db: Session, item: Item) -> None:
    """`Item.unit` را با نامِ واحدِ اصلی هم‌گام می‌کند.

    **این تنها جایی است که آن ستون نوشته می‌شود.** از این پس `unit` پرتوِ نامِ
    واحدِ اصلی است نه منبعِ حقیقت؛ نگه‌داشتنش عمدی است چون ردیفِ فاکتور، بسته‌ی
    مؤدیان، بازار و فروشگاه همه آن را می‌خوانند و شکستنشان چیزی درست‌تر نمی‌کرد.
    """
    if item.primary_unit_id is None:
        return
    unit = db.get(UnitOfMeasure, item.primary_unit_id)
    if unit is not None:
        item.unit = unit.name


def assert_conversion(item: Item) -> None:
    """نسبتِ تبدیل باید با واحدِ فرعی بخواند (§۲۰ §۲۱ §۲۲)."""
    if item.conversion_mode not in CONVERSION_MODES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نحوه‌ی تبدیلِ واحد نامعتبر است")
    if item.secondary_unit_id is None:
        return
    if item.secondary_unit_id == item.primary_unit_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "واحدِ فرعی نمی‌تواند همان واحدِ اصلی باشد"
        )
    if item.conversion_mode == "fixed" and Decimal(item.conversion_factor or 0) <= 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "برای نسبتِ ثابت باید بگویید هر واحدِ فرعی چند واحدِ اصلی است (مثلاً ۱ کارتن = ۲۴ عدد).",
        )


def to_primary(db: Session, item: Item, qty: Decimal, unit_id: UUID | None) -> Decimal:
    """مقدارِ واردشده را به **واحدِ اصلیِ** کالا برمی‌گرداند (§۲۱).

    تنها پیاده‌سازیِ تبدیل در کلِ کوبیتا. خرید با کارتن، فروش با عدد و انبار با
    عدد — هر سه باید یک عدد بگیرند، وگرنه موجودی بی‌صدا غلط می‌شود.

    `None` یا واحدِ اصلی یعنی «همان مقدار». واحدِ فرعی با نسبت ضرب می‌شود.
    هر واحدِ دیگری رد می‌شود: کوبیتا نسبتِ دو واحدِ بی‌ربط را نمی‌داند و
    حدس‌زدنش بدتر از خطاست.
    """
    if unit_id is None or unit_id == item.primary_unit_id:
        return qty
    if unit_id != item.secondary_unit_id:
        unit = resolve(db, unit_id)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"واحدِ «{unit.name}» برای «{item.name}» تعریف نشده؛ "
            "فقط واحدِ اصلی یا فرعیِ همان کالا پذیرفته می‌شود.",
        )
    if item.conversion_mode == "variable":
        #: §۲۲ — نسبتِ متغیر یعنی «این عدد را نمی‌شود از پیش دانست». عددی از خود
        #: درآوردن یعنی موجودی را با یک حدس پر کنیم.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"نسبتِ واحدِ «{item.name}» متغیر است و از پیش معلوم نیست؛ "
            "مقدار را به واحدِ اصلی وارد کنید.",
        )
    factor = Decimal(item.conversion_factor or 0)
    if factor <= 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"نسبتِ تبدیلِ واحدِ «{item.name}» تعریف نشده است.",
        )
    return qty * factor


def row(db: Session, item: Item) -> dict:
    """بخشِ واحدهای ردیفِ فهرستِ کالا (§۴۸)."""
    primary = db.get(UnitOfMeasure, item.primary_unit_id) if item.primary_unit_id else None
    secondary = db.get(UnitOfMeasure, item.secondary_unit_id) if item.secondary_unit_id else None
    return {
        "primary_unit_id": item.primary_unit_id,
        "primary_unit_name": primary.name if primary else item.unit,
        "secondary_unit_id": item.secondary_unit_id,
        "secondary_unit_name": secondary.name if secondary else "",
    }
