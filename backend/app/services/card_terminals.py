"""دستگاهِ کارت‌خوانِ بانکی — موجودیتی خزانه‌ای، نه صندوقِ فروش.

**این دو یکی نیستند و در کوبیتا هم قاطی نشده‌اند.** «صندوق فروشگاهی»
(`PosPage.tsx`) جایی است که فروش زده می‌شود و اصلاً جدول ندارد — از مسیرِ فاکتورِ
فروش می‌رود. `PosTerminal` دستگاهی است که کارتِ مشتری را می‌گیرد: `transport`،
`host`، `port`، `psp`، و حسابِ بانکیِ تسویه. رابطه‌شان یک‌طرفه است: صفحه‌ی فروش
دستگاه را صدا می‌زند.

**موجودیِ دستگاه هیچ ستونی ندارد و مشتق می‌ماند:**

    موجودیِ دستگاه = جمعِ رسیدهای کارتیِ تسویه‌نشده‌ی همین دستگاه

**و از مهاجرتِ ۰۱۰۹ همین عدد در دفتر هم هست.** تا پیش از آن نبود: رسیدِ کارتی از
همان لحظه معینِ *بانک* را بدهکار می‌کرد، پس پولِ نرسیده در دفتر روی بانک نشسته
بود و این عدد فقط یک شمارشِ عملیاتیِ کنارِ دفتر می‌ماند. حالا رسیدِ کارتی روی
«وجوهِ در راهِ کارت‌خوان» با تفصیلیِ همین دستگاه می‌نشیند و تسویه آن را به بانک
می‌برد — یعنی این تابع و مانده‌ی آن جفتِ `(معین، تفصیلی)` **باید یک عدد بدهند**.
دوبار شمردن در کار نیست، چون دو مرحله دو حسابِ متفاوت‌اند.

نگه‌داشتنِ این تابع روی خودِ خزانه عمدی است: پاسخ به «کدام رسیدها؟» را هم می‌دهد،
که مانده‌ی دفتری نمی‌دهد.
"""
from __future__ import annotations

from datetime import date as date_
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.banking import BankAccount
from app.models.pos_terminal import PosTerminal
from app.models.treasury import TreasuryTransaction

#: علامتِ اینکه رسید از کارت‌خوان آمده. `method` مقدارِ «card» ندارد — رسیدِ کارتی
#: از نظرِ روش «بانکی» است و این ستونِ جدا کانالش را می‌گوید.
PAID_VIA_TERMINAL = "pos_terminal"


def resolve(db: Session, terminal_id: UUID | None) -> PosTerminal:
    if terminal_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "دستگاه کارتخوان انتخاب نشده است")
    term = db.get(PosTerminal, terminal_id)
    if term is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دستگاهِ کارتخوان یافت نشد")
    return term


def assert_usable(db: Session, term: PosTerminal, on: date_ | None = None) -> None:
    """§۲۰ — دستگاهِ جمع‌آوری‌شده برای پرداختِ تازه انتخاب نمی‌شود.

    سابقه دست نمی‌خورد: تراکنش‌ها، تسویه‌ها و اسنادِ گذشته همه سرِ جایشان می‌مانند.
    """
    if not term.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"دستگاه «{term.label or term.terminal_no or 'کارتخوان'}» غیرفعال است "
            "و برای پرداختِ تازه انتخاب نمی‌شود",
        )


def settlement_account(db: Session, term: PosTerminal) -> BankAccount:
    """حسابِ بانکیِ تسویه‌ی دستگاه — **از خودِ دستگاه**، نه از کاربر (§۴).

    وقتی دستگاه حسابش را می‌داند، پرسیدنِ دوباره‌اش در هر تراکنش هم کارِ اضافه است
    هم راهی برای ناسازگاری: کارمزد می‌توانست به حسابی بخورد که ناخالص آنجا نرفته.
    """
    if term.bank_account_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"دستگاه «{term.label or 'کارتخوان'}» حسابِ بانکیِ تسویه ندارد؛ اول آن را تعیین کنید",
        )
    bank = db.get(BankAccount, term.bank_account_id)
    if bank is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب بانکیِ تسویه یافت نشد")
    return bank


def assert_currency_match(db: Session, currency_code: str, bank_account_id: UUID | None) -> None:
    """§۹ — ارزِ دستگاه باید با ارزِ حسابِ تسویه بخواند.

    **رد می‌شود، نه هشدار.** سیاستِ کوبیتا از قبل «یک موجودیت، یک ارز» است و هیچ
    گزارشی بینِ ارزها جمع نمی‌زند؛ کارت‌خوانِ ریالی که به حسابِ دلاری تسویه شود
    ترکیبی است که هیچ‌جای این سیستم نمی‌تواند درست حسابش کند. چون هر دو فیلد در
    مهاجرت پیش‌فرضِ `IRR` گرفته‌اند، هیچ جفتِ موجودی با این قید نمی‌شکند.
    """
    if bank_account_id is None:
        return
    bank = db.get(BankAccount, bank_account_id)
    if bank is None or bank.currency_code == currency_code:
        return
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        f"ارزِ دستگاه ({currency_code}) با ارزِ حساب «{bank.name}» ({bank.currency_code}) "
        "نمی‌خواند؛ تسویه‌ی بینِ دو ارز از این مسیر ممکن نیست",
    )


def _owned_transactions(term: PosTerminal):
    """شرطِ «این تراکنش مالِ این دستگاه است».

    دو حالت، چون داده‌ی مستقر کلیدِ خارجی ندارد:

    1. `pos_terminal_id` برابرِ این دستگاه — رسیدهای پس از مهاجرتِ ۰۱۰۷.
    2. رسیدی که کلیدِ خارجی ندارد ولی `terminal_no`اش با شماره‌ی دستگاه یکی است.

    شرطِ دوم **دقیقاً همان تطبیقی است که صفحه‌ی تسویه امروز انجام می‌دهد**، پس
    رفتار عوض نمی‌شود؛ فقط حالا جایی دیده می‌شود. برای دستگاهِ بی‌شماره خاموش
    است، وگرنه رسیدهای بی‌شماره را به آن نسبت می‌داد.
    """
    same_id = TreasuryTransaction.pos_terminal_id == term.id
    if not term.terminal_no:
        return same_id
    return or_(
        same_id,
        (TreasuryTransaction.pos_terminal_id.is_(None))
        & (TreasuryTransaction.terminal_no == term.terminal_no),
    )


def unsettled_balance(db: Session, term: PosTerminal) -> Decimal:
    """§۱۳ §۱۵ — «موجودیِ عملیاتیِ دستگاه»: کشیده‌شده ولی هنوز واریزنشده.

    **مشتق است.** هیچ‌جا ذخیره نمی‌شود و هیچ کدی آن را دستی کم و زیاد نمی‌کند؛
    تسویه فقط `settled_at` را پر می‌کند و این عدد خودش پایین می‌آید.
    """
    total = (
        db.query(func.coalesce(func.sum(TreasuryTransaction.amount), 0))
        .filter(
            TreasuryTransaction.paid_via == PAID_VIA_TERMINAL,
            TreasuryTransaction.settled_at.is_(None),
            TreasuryTransaction.voided_at.is_(None),
            _owned_transactions(term),
        )
        .scalar()
    )
    return Decimal(total or 0)


def _in_use(db: Session, term: PosTerminal) -> bool:
    return (
        db.query(TreasuryTransaction.id).filter(_owned_transactions(term)).first() is not None
    )


def _assert_terminal_no_free(db: Session, terminal_no: str, exclude_id: UUID | None = None) -> None:
    """شماره‌ی پایانه یکتاست — ولی فقط وقتی پر شده.

    خالی‌بودن مجاز است چون دستگاه‌های تعریف‌شده‌ی پیش از مهاجرتِ ۰۱۰۷ شماره
    ندارند و اجباری‌کردنش یا مقدارِ ساختگی می‌ساخت یا ویرایششان را قفل می‌کرد.
    """
    if not terminal_no:
        return
    query = db.query(PosTerminal).filter(PosTerminal.terminal_no == terminal_no)
    if exclude_id is not None:
        query = query.filter(PosTerminal.id != exclude_id)
    other = query.first()
    if other is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"شماره پایانه {terminal_no} از قبل به دستگاه «{other.label or 'بی‌نام'}» تعلق دارد",
        )


def _assert_analytic_free(db: Session, analytic_id: UUID | None, exclude_id: UUID | None = None) -> None:
    """یک تفصیلی نمی‌تواند مالِ دو دستگاه باشد — وگرنه وجوهِ در راهشان یکی می‌شود.

    `NULL` استثناست: چند دستگاه می‌توانند بی‌تفصیلی بمانند، ولی آن‌وقت همه‌شان یک
    مانده‌ی دفتری می‌خوانند. همان قاعده‌ای که صندوق و حسابِ بانکی دارند.
    """
    if analytic_id is None:
        return
    query = db.query(PosTerminal).filter(PosTerminal.analytic_id == analytic_id)
    if exclude_id is not None:
        query = query.filter(PosTerminal.id != exclude_id)
    other = query.first()
    if other is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"این تفصیلی از قبل به دستگاه «{other.label or other.terminal_no or 'بی‌نام'}» تعلق دارد",
        )


def _assert_analytic_change_allowed(db: Session, term: PosTerminal, new_analytic_id) -> None:
    """تفصیلیِ دستگاهی که سابقه دارد عوض نمی‌شود.

    عوض‌کردنش هیچ سندی را بازنویسی نمی‌کند — ولی مانده‌ی وجوهِ در راه را **بی‌صدا**
    به مجموعه‌ی دیگری از ردیف‌ها می‌برد: پولِ قبلی از فهرست ناپدید می‌شود و صفر
    جایش می‌نشیند. راهِ درست «انتقال مانده به حساب دیگر» است.
    """
    if new_analytic_id == term.analytic_id or not _in_use(db, term):
        return
    raise HTTPException(
        status.HTTP_409_CONFLICT,
        f"دستگاه «{_label(term)}» سابقه دارد و تفصیلی‌اش عوض نمی‌شود؛ مانده‌اش با "
        "«انتقال مانده به حساب دیگر» منتقل می‌شود تا اسنادِ گذشته دست‌نخورده بمانند",
    )


def _label(term: PosTerminal) -> str:
    return term.label or term.terminal_no or "کارتخوان"


def row(db: Session, term: PosTerminal) -> dict:
    """یک دستگاه به شکلِ خروجی — تنها جایی که این شکل ساخته می‌شود."""
    bank = db.get(BankAccount, term.bank_account_id) if term.bank_account_id else None
    return {
        "id": term.id,
        "label": term.label,
        "name2": term.name2,
        "terminal_no": term.terminal_no,
        "psp": term.psp,
        "transport": term.transport,
        "host": term.host,
        "port": term.port,
        "com_port": term.com_port,
        "bank_account_id": term.bank_account_id,
        "bank_account_name": bank.name if bank else None,
        "bank_account_name2": bank.name2 if bank else None,
        "analytic_id": term.analytic_id,
        "analytic_code": term.analytic.code if term.analytic else None,
        "analytic_name": term.analytic.name if term.analytic else None,
        "currency_code": term.currency_code,
        "is_active": term.is_active,
        "is_default": term.is_default,
        #: مشتق — ستون نیست.
        "unsettled_balance": unsettled_balance(db, term),
    }


def list_terminals(
    db: Session,
    *,
    search: str | None = None,
    bank_account_id: UUID | None = None,
    currency_code: str | None = None,
    active_only: bool = False,
) -> list[dict]:
    """فهرست با جست‌وجو و صافی (§۲۲ §۲۳) — بدونِ موتورِ فیلترِ تازه."""
    query = db.query(PosTerminal)
    if search:
        needle = f"%{search.strip()}%"
        query = query.filter(
            or_(PosTerminal.terminal_no.ilike(needle), PosTerminal.label.ilike(needle))
        )
    if bank_account_id is not None:
        query = query.filter(PosTerminal.bank_account_id == bank_account_id)
    if currency_code:
        query = query.filter(PosTerminal.currency_code == currency_code)
    if active_only:
        query = query.filter(PosTerminal.is_active.is_(True))
    return [row(db, t) for t in query.order_by(PosTerminal.label).all()]


def clear_default(db: Session, exclude_id: UUID | None = None) -> None:
    query = db.query(PosTerminal).filter(PosTerminal.is_default.is_(True))
    if exclude_id is not None:
        query = query.filter(PosTerminal.id != exclude_id)
    for other in query.all():
        other.is_default = False


def create_terminal(db: Session, data: dict) -> PosTerminal:
    _assert_terminal_no_free(db, data.get("terminal_no") or "")
    _assert_analytic_free(db, data.get("analytic_id"))
    assert_currency_match(db, data.get("currency_code") or "IRR", data.get("bank_account_id"))
    term = PosTerminal(**data)
    db.add(term)
    db.flush()
    if term.is_default:
        clear_default(db, exclude_id=term.id)
    db.flush()
    db.refresh(term)
    return term


def update_terminal(db: Session, terminal_id: UUID, data: dict) -> PosTerminal:
    term = resolve(db, terminal_id)
    if "terminal_no" in data:
        _assert_terminal_no_free(db, data["terminal_no"] or "", exclude_id=term.id)
    if "analytic_id" in data:
        _assert_analytic_free(db, data["analytic_id"], exclude_id=term.id)
        _assert_analytic_change_allowed(db, term, data["analytic_id"])
    #: ارز و حساب هرکدام ممکن است تنها عوض شوند، پس قید روی *نتیجه* سنجیده
    #: می‌شود نه روی چیزی که فرستاده شده.
    assert_currency_match(
        db,
        data.get("currency_code", term.currency_code) or "IRR",
        data.get("bank_account_id", term.bank_account_id),
    )
    for key, value in data.items():
        setattr(term, key, value)
    db.flush()
    if term.is_default:
        clear_default(db, exclude_id=term.id)
    db.flush()
    db.refresh(term)
    return term


def delete_terminal(db: Session, terminal_id: UUID) -> None:
    """§۲۱ — دستگاهی که ده‌هزار تراکنش دارد حذف نمی‌شود، غیرفعال می‌شود.

    تا امروز `DELETE` هیچ سنجشی نداشت: چون کلیدِ خارجی وجود نداشت، پایگاه‌داده هم
    جلویش را نمی‌گرفت و رکورد بی‌صدا می‌رفت، در حالی که رسیدهایش می‌ماندند.
    """
    term = resolve(db, terminal_id)
    if _in_use(db, term):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"دستگاه «{term.label or term.terminal_no or 'کارتخوان'}» در تراکنش‌ها "
            "استفاده شده و حذف نمی‌شود؛ به‌جایش غیرفعالش کنید",
        )
    db.delete(term)
    db.flush()
