"""صندوق — موجودیتِ عملیاتی، و مانده‌ای که از دفتر می‌آید.

**چرا مانده ذخیره نمی‌شود.** وسوسه‌ی طبیعی یک ستونِ `balance` روی `Cashbox` است که
هر دریافت و پرداخت به‌روزش کند. ولی آن‌وقت دو منبعِ حقیقت داریم برای یک پول، و
اولین مسیری که یادش برود ستون را به‌روز کند، صندوق را با تراز واگرا می‌کند —
بی‌آنکه کسی بفهمد.

پس مانده از **دفتر** می‌آید: مانده‌ی `(حسابِ صندوق، تفصیلیِ آن صندوق)`. دو سود
دارد که هیچ‌کدام تصادفی نیستند:

* **هر مسیری که به نقد دست بزند شمرده می‌شود** — نه فقط رسید و پرداخت، بلکه سندِ
  دستی، افتتاحیه، اصلاح، هر چیزِ دیگری که فردا اضافه شود.
* **صندوق نمی‌تواند با تراز واگرا شود.** همان قیدی که گزارش‌ها رویش بنا شده‌اند:
  اگر تراز و صندوق دو عدد بدهند، اشکالِ جدیِ حسابداری داریم. این‌جا از اساس ممکن
  نیست، چون یک عددند.

**موجودیِ اولیه هم همین است، فقط با تاریخِ دیگر.** موجودیِ اولِ سالِ N یعنی همان
مانده در ابتدای آن سال. جدولِ «سال مالی | موجودی» ساخته نشد چون کوبیتا از قبل
مانده‌ی اول دوره را با سند می‌زند و افتتاحیه‌ی هر سال تفصیلی را منتقل می‌کند.
"""
from __future__ import annotations

from datetime import date as date_
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.cashbox import Cashbox
from app.models.treasury import TreasuryTransaction
from app.services import chart_codes as cc
from app.services.common import get_account

#: نامِ صندوقی که وقتی هیچ صندوقی تعریف نشده خودکار ساخته می‌شود.
DEFAULT_CASHBOX_NAME = "صندوق اصلی"


def get_or_create_default(db: Session) -> Cashbox:
    """صندوقِ پیش‌فرض — ساخته می‌شود اگر هیچ صندوقی نباشد.

    `analytic_id` عمداً `NULL` می‌ماند: این صندوق یعنی «نقدی که به صندوقِ مشخصی
    نسبت داده نشده»، و ردیف‌های امروزِ دفتر دقیقاً همین‌اند. پس کسب‌وکارهای موجود
    بدونِ هیچ مهاجرتِ داده‌ای درست کار می‌کنند.

    مثلِ `get_or_create_account` این‌جا ساخته می‌شود نه در مهاجرت، چون نوشتن روی
    جدولِ RLS داخلِ مهاجرت یا صفر ردیف می‌گذارد یا روی مستأجرِ اشتباه.
    """
    existing = db.query(Cashbox).order_by(Cashbox.created_at).first()
    if existing is not None:
        return existing
    box = Cashbox(name=DEFAULT_CASHBOX_NAME, analytic_id=None, gl_account_id=None)
    db.add(box)
    db.flush()
    return box


def resolve_cashbox(db: Session, cashbox_id: UUID | None) -> Cashbox:
    """صندوقِ خواسته‌شده، یا پیش‌فرض اگر چیزی نیامده باشد.

    رسیدِ نقدیِ بدونِ صندوق باید مثلِ قبل کار کند — کدِ قدیمی و APIهای موجود
    `cashbox_id` نمی‌فرستند.
    """
    if cashbox_id is None:
        return get_or_create_default(db)
    box = db.get(Cashbox, cashbox_id)
    if box is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "صندوق یافت نشد")
    return box


def assert_usable(db: Session, box: Cashbox, on: date_) -> None:
    """صندوق برای عملیاتِ تازه در این تاریخ قابلِ استفاده است؟

    دو گارد که هر دو خطای ورودِ داده‌اند، نه سلیقه:
    غیرفعال یعنی دیگر انتخاب نمی‌شود (ولی سوابقش می‌ماند)، و تاریخِ پیش از افتتاح
    یعنی صندوق آن روز اصلاً وجود نداشته.
    """
    if not box.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"صندوق «{box.name}» غیرفعال است و برای عملیات تازه انتخاب نمی‌شود",
        )
    if box.opening_date is not None and on < box.opening_date:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"صندوق «{box.name}» از {box.opening_date} افتتاح شده؛ عملیات با تاریخ {on} پیش از آن است",
        )


def gl_account_id(db: Session, box: Cashbox) -> UUID:
    """حسابِ معینِ صندوق — پیش‌فرض همان حسابِ نقشِ `cash`."""
    if box.gl_account_id is not None:
        return box.gl_account_id
    return get_account(db, cc.CASH).id


def balance(db: Session, box: Cashbox, *, as_of: date_ | None = None) -> Decimal:
    """مانده‌ی صندوق تا یک تاریخ — از دفتر، نه از تراکنش‌های خزانه.

    `IS NOT DISTINCT FROM` عمدی است: تفصیلیِ `NULL` (صندوقِ پیش‌فرض) باید مثلِ هر
    مقدارِ دیگری مقایسه شود، و `= NULL` هرگز درست نمی‌شود.
    """
    query = (
        db.query(
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .filter(
            JournalLine.account_id == gl_account_id(db, box),
            JournalLine.analytic_id.is_not_distinct_from(box.analytic_id),
        )
    )
    if as_of is not None:
        query = query.filter(JournalEntry.entry_date <= as_of)
    debit, credit = query.one()
    return Decimal(debit) - Decimal(credit)


def opening_balance(db: Session, box: Cashbox) -> Decimal:
    """موجودیِ اولیه‌ی سالِ مالیِ جاری — همان مانده در آستانه‌ی شروعِ سال.

    **با مانده‌ی جاری قاطی نمی‌شود:** این عدد ابتدای دوره است و آن یکی نتیجه‌ی هر
    چیزی که بعدش افتاده. تفکیکشان همان چیزی است که جلوی مغایرت را می‌گیرد.

    اگر سالِ مالی تعریف نشده باشد، دوره‌ای در کار نیست و صفر برمی‌گردد.
    """
    from app.models.fiscal_year import FiscalYear

    year = db.query(FiscalYear).filter(FiscalYear.is_active.is_(True)).first()
    if year is None:
        return Decimal(0)
    #: «آستانه‌ی شروع» یعنی روزِ پیش از اولین روزِ سال — وگرنه سندهای خودِ روزِ اول
    #: هم موجودیِ اولیه شمرده می‌شدند.
    from datetime import timedelta

    return balance(db, box, as_of=year.start_date - timedelta(days=1))


def list_cashboxes(db: Session, *, include_inactive: bool = True) -> list[dict]:
    """فهرستِ صندوق‌ها با موجودیِ اولیه و مانده‌ی جاری — هر دو مشتق.

    **جمعِ کلِ صندوق‌ها برنمی‌گردد.** صندوقِ ریالی و دلاری بدونِ نرخ و تاریخ
    جمع‌شدنی نیستند؛ تجمیعِ ارزها کارِ موتورِ ارزی است، نه این فهرست.
    """
    query = db.query(Cashbox).order_by(Cashbox.name)
    if not include_inactive:
        query = query.filter(Cashbox.is_active.is_(True))
    out = []
    for box in query.all():
        out.append(
            {
                "id": box.id,
                "name": box.name,
                "name2": box.name2,
                "analytic_id": box.analytic_id,
                "analytic_code": box.analytic.code if box.analytic else None,
                "analytic_name": box.analytic.name if box.analytic else None,
                "gl_account_id": box.gl_account_id,
                "currency_code": box.currency_code,
                "opening_date": box.opening_date,
                "is_active": box.is_active,
                "opening_balance": opening_balance(db, box),
                "balance": balance(db, box),
            }
        )
    return out


def _in_use(db: Session, box: Cashbox) -> bool:
    """آیا جایی به این صندوق ارجاع داده شده؟

    ارجاعِ خزانه و ردیفِ دفتر هر دو حساب می‌شوند: صندوقی که تفصیلی‌اش در سندی
    نشسته، حذفش تاریخچه‌ی مالی را بی‌صاحب می‌کند.
    """
    if db.query(TreasuryTransaction).filter(TreasuryTransaction.cashbox_id == box.id).first():
        return True
    if box.analytic_id is None:
        return False
    return (
        db.query(JournalLine)
        .filter(
            JournalLine.account_id == gl_account_id(db, box),
            JournalLine.analytic_id == box.analytic_id,
        )
        .first()
        is not None
    )


def delete_cashbox(db: Session, cashbox_id: UUID) -> None:
    """حذف فقط برای صندوقی که هرگز استفاده نشده.

    صندوقِ استفاده‌شده «غیرفعال» می‌شود، حذف نمی‌شود — همان فلسفه‌ی همیشگی: سابقه‌ی
    مالی بی‌صدا از بین نمی‌رود. الگویش `delete_checkbook` است.
    """
    box = db.get(Cashbox, cashbox_id)
    if box is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "صندوق یافت نشد")
    if _in_use(db, box):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"صندوق «{box.name}» در عملیات استفاده شده و حذف نمی‌شود؛ به‌جایش غیرفعالش کنید",
        )
    db.delete(box)
    db.flush()


def _assert_analytic_free(db: Session, analytic_id: UUID | None, exclude_id: UUID | None = None) -> None:
    """یک تفصیلی نمی‌تواند مالِ دو صندوق باشد — وگرنه مانده‌هایشان یکی می‌شود.

    `NULL` استثناست: چند صندوق می‌توانند بی‌تفصیلی بمانند، ولی آن‌وقت همه‌شان
    «صندوقِ پیش‌فرض» را می‌خوانند. گاردش در `create_cashbox` است.
    """
    if analytic_id is None:
        return
    query = db.query(Cashbox).filter(Cashbox.analytic_id == analytic_id)
    if exclude_id is not None:
        query = query.filter(Cashbox.id != exclude_id)
    other = query.first()
    if other is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"این تفصیلی از قبل به صندوق «{other.name}» تعلق دارد",
        )


def create_cashbox(db: Session, data: dict) -> Cashbox:
    _assert_analytic_free(db, data.get("analytic_id"))
    #: صندوقِ دوم بدونِ تفصیلی یعنی دو صندوق با یک مانده — که بی‌معنی است.
    if data.get("analytic_id") is None and db.query(Cashbox).first() is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "برای صندوقِ دوم باید تفصیلی انتخاب شود، وگرنه مانده‌اش از صندوقِ اول جدا نمی‌شود",
        )
    box = Cashbox(**data)
    db.add(box)
    db.flush()
    db.refresh(box)
    return box


def update_cashbox(db: Session, cashbox_id: UUID, data: dict) -> Cashbox:
    box = db.get(Cashbox, cashbox_id)
    if box is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "صندوق یافت نشد")
    if "analytic_id" in data:
        _assert_analytic_free(db, data["analytic_id"], exclude_id=box.id)
    for key, value in data.items():
        setattr(box, key, value)
    db.flush()
    db.refresh(box)
    return box
