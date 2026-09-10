"""دسته‌چک — منبعِ برگ‌های چکِ پرداختنی، نه یک رویدادِ مالی.

تعریفِ دسته‌چک هیچ سندی نمی‌زند: نه پول می‌سازد نه بدهی. اثرِ مالی وقتی پیدا
می‌شود که برگی از آن در یک پرداخت خرج شود. پس این فایل هیچ‌جا `JournalLine`
نمی‌سازد.

**برگ‌ها materialize نمی‌شوند.** یک دسته‌ی پنجاه‌برگی پنجاه ردیف نمی‌سازد؛ وضعیتِ
هر برگ از چک‌های وصل‌شده *مشتق* می‌شود. دلیلش را همان کامنتِ قدیمیِ
`list_checkbooks` گفته بود: شمارنده‌ی جدا با هر ابطال/حذفِ چک از واقعیت فاصله
می‌گرفت. مشتق هیچ‌وقت دروغ نمی‌گوید.

ولی مشتق‌بودن یکتایی نمی‌آورد، و تا امروز **هیچ‌چیز جلوی خرج‌کردنِ دوباره‌ی یک برگ
را نمی‌گرفت** — `create_check` مقدارِ `checkbook_id` را می‌گرفت و بی‌هیچ سنجشی
می‌نشاند. حالا دو لایه دارد: سنجشِ سرویس (پیامِ فارسیِ روشن) و ایندکسِ جزئیِ
یکتای `uq_checks_tenant_book_number` (تضمینِ واقعی، حتی اگر مسیرِ تازه‌ای اضافه شود).

**مرزِ سیاست و یکپارچگی:** `cheque_number_control` فقط تعیین می‌کند آیا چکِ
پرداختنیِ **بی‌دسته** مجاز است. اگر کاربر دسته‌ای را انتخاب کرد، بازه و
تکراری‌نبودن در **هر دو** حالت سنجیده می‌شوند — آن یکپارچگیِ داده است نه سیاست،
چون بدونش «برگِ مانده» عددِ دروغ می‌دهد.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.banking import BankAccount, Check, Checkbook
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.banking import CheckbookIn, CheckbookUpdateIn
from app.tenant_context import session_tenant

#: سیاست‌های کنترلِ شماره‌ی چکِ پرداختنی.
CONTROL_MODES = ("off", "book")
DEFAULT_CONTROL_MODE = "off"
CONTROL_MODE_LABELS = {
    "off": "آزاد",
    "book": "فقط از دسته‌چک",
}
CONTROL_MODE_HINTS = {
    "off": "شماره‌ی چکِ پرداختنی را دستی می‌نویسید و دسته‌چک اختیاری است.",
    "book": "هر چکِ پرداختنی باید از یک دسته‌چکِ باز صادر شود.",
}
CONTROL_MODE_EFFECTS = {
    "off": [
        "چکِ پرداختنی بدونِ دسته‌چک هم ثبت می‌شود.",
        "اگر دسته‌ای انتخاب شود، شماره باز هم باید از همان دسته و خرج‌نشده باشد.",
    ],
    "book": [
        "چکِ پرداختنیِ بدونِ دسته‌چک رد می‌شود.",
        "شمارِ برگِ مانده‌ی هر دسته همیشه با واقعیت می‌خواند.",
        "چک‌های ثبت‌شده‌ی گذشته دست نمی‌خورند.",
    ],
}


# ---------------------------------------------------------------------------
# سیاست
# ---------------------------------------------------------------------------


def get_control_mode(db: Session) -> str:
    """سیاستِ این کسب‌وکار. بدونِ زمینه‌ی مستأجر، پیش‌فرض — تا seed و اسکریپت نشکنند."""
    tenant_id = session_tenant(db)
    if tenant_id is None:
        return DEFAULT_CONTROL_MODE
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        return DEFAULT_CONTROL_MODE
    return tenant.cheque_number_control or DEFAULT_CONTROL_MODE


def set_control_mode(tenant: Tenant, mode: str) -> str:
    if mode not in CONTROL_MODES:
        raise ValueError("سیاستِ کنترلِ شماره‌ی چک نامعتبر است")
    tenant.cheque_number_control = mode
    return mode


# ---------------------------------------------------------------------------
# دسترسی و وضعیت
# ---------------------------------------------------------------------------


def resolve(db: Session, checkbook_id: UUID | None) -> Checkbook:
    if checkbook_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "دسته‌چک انتخاب نشده است")
    book = db.get(Checkbook, checkbook_id)
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دسته‌چک یافت نشد")
    return book


def label(book: Checkbook) -> str:
    """نامِ خواندنیِ دسته برای پیام‌های خطا."""
    return book.serial or f"{book.first_number}–{book.last_number}"


def assert_usable(db: Session, book: Checkbook) -> None:
    """دسته‌ی بسته دیگر برگِ تازه نمی‌دهد؛ برگ‌های خرج‌شده‌اش دست نمی‌خورند."""
    if not book.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"دسته‌چکِ «{label(book)}» بسته است و از آن برگِ تازه صادر نمی‌شود",
        )


def used_count(db: Session, book: Checkbook) -> int:
    return db.query(func.count(Check.id)).filter(Check.checkbook_id == book.id).scalar() or 0


# ---------------------------------------------------------------------------
# برگ
# ---------------------------------------------------------------------------


def _numeric_range(book: Checkbook) -> tuple[int, int] | None:
    """بازه به‌صورتِ عدد، یا `None` اگر شماره‌ها عددی نباشند.

    شماره‌ها عمداً رشته‌اند (بانک صفرِ ابتدایی می‌گذارد و تبدیل به عدد آن را
    می‌خورد). ولی برای «داخلِ بازه هست یا نه» چاره‌ای جز مقایسه‌ی عددی نیست —
    مقایسه‌ی رشته‌ای «۹» را بزرگ‌تر از «۱۰» می‌داند.
    """
    if not (book.first_number.isdigit() and book.last_number.isdigit()):
        return None
    return int(book.first_number), int(book.last_number)


def assert_leaf_in_range(book: Checkbook, number: str) -> None:
    """شماره باید واقعاً برگی از همین دسته باشد.

    اگر شماره‌های دسته یا خودِ شماره عددی نباشند، سنجش رها می‌شود: ساختارِ شماره‌ی
    بانکی همیشه عددی نیست و مسدودکردنِ چیزی که نمی‌فهمیمش بدتر از نسنجیدنش است.
    """
    bounds = _numeric_range(book)
    if bounds is None or not number.isdigit():
        return
    first, last = bounds
    if not (first <= int(number) <= last):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"شماره‌ی {number} در دسته‌چکِ «{label(book)}» نیست "
            f"(بازه‌ی این دسته {book.first_number} تا {book.last_number} است)",
        )


def assert_leaf_free(db: Session, book: Checkbook, number: str, *, exclude_check_id: UUID | None = None) -> None:
    """یک برگِ فیزیکی فقط یک بار خرج می‌شود.

    عمداً وضعیتِ چک را نگاه نمی‌کند: چکِ باطل‌شده یا برگشتی هم برگ را آزاد نمی‌کند،
    چون آن کاغذ دیگر سابقه دارد و دوباره نوشتنش یعنی دو تعهد با یک شماره.
    """
    query = db.query(Check).filter(Check.checkbook_id == book.id, Check.number == number)
    if exclude_check_id is not None:
        query = query.filter(Check.id != exclude_check_id)
    existing = query.first()
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"برگِ {number} از دسته‌چکِ «{label(book)}» قبلاً خرج شده است "
            f"(چکِ {existing.issue_date} به مبلغِ {int(existing.amount):,})",
        )


def assert_leaf_available(db: Session, book: Checkbook, number: str) -> None:
    """هر سه سنجشِ لازم پیش از خرج‌کردنِ یک برگ."""
    assert_usable(db, book)
    assert_leaf_in_range(book, number)
    assert_leaf_free(db, book, number)


def used_leaves(db: Session, book: Checkbook) -> list[dict]:
    """هر برگِ خرج‌شده کجا رفت — ناوبریِ برعکسِ دسته ← برگ ← چک.

    بدونِ این، «۷ برگ خرج شده» عددی است که کاربر باید خودش دنبالِ معنایش بگردد.
    """
    rows = (
        db.query(Check)
        .filter(Check.checkbook_id == book.id)
        .order_by(Check.number)
        .all()
    )
    return [
        {
            "number": check.number,
            "check_id": check.id,
            "status": check.status,
            "amount": check.amount,
            "issue_date": check.issue_date,
            "due_date": check.due_date,
            "contact_name": check.contact_name,
        }
        for check in rows
    ]


def next_number(db: Session, checkbook_id: UUID) -> str:
    """شماره‌ی برگِ بعدیِ این دسته — پیشنهاد، نه قفل.

    از بزرگ‌ترین شماره‌ی مصرف‌شده جلو می‌رود، نه از شمارِ برگ‌ها: اگر کاربر برگی را
    از وسط خرج کرده باشد، شمارشِ ساده شماره‌ی تکراری پیشنهاد می‌داد.
    """
    book = resolve(db, checkbook_id)
    numbers = [
        c.number
        for c in db.query(Check).filter(Check.checkbook_id == book.id).all()
        if (c.number or "").isdigit()
    ]
    if not book.first_number.isdigit():
        return ""
    width = len(book.first_number)
    nxt = (max(int(n) for n in numbers) + 1) if numbers else int(book.first_number)
    if book.last_number.isdigit() and nxt > int(book.last_number):
        return ""
    return str(nxt).zfill(width)


# ---------------------------------------------------------------------------
# اعتبارسنجیِ خودِ دسته
# ---------------------------------------------------------------------------


def _assert_serial_free(db: Session, bank_account_id: UUID, serial: str, *, exclude_id: UUID | None = None) -> None:
    if not serial:
        return
    query = db.query(Checkbook).filter(
        Checkbook.bank_account_id == bank_account_id, Checkbook.serial == serial
    )
    if exclude_id is not None:
        query = query.filter(Checkbook.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "دسته‌چکی با این سری برای همین حساب ثبت شده است"
        )


def assert_no_range_overlap(
    db: Session,
    bank_account_id: UUID,
    first: str,
    last: str,
    *,
    exclude_id: UUID | None = None,
) -> None:
    """بازه‌ی دو دسته‌ی یک حساب نباید هم را بپوشاند.

    **رد می‌شود، نه هشدار.** بانک هرگز دو دسته‌ی هم‌پوشان برای یک حساب صادر
    نمی‌کند، پس هزینه‌ی مسدودکردن صفر است — و سودش این است که یک شماره از دو دسته
    قابلِ انتخاب نماند، وگرنه ایندکسِ یکتا (که به دسته کلید خورده) دور زده می‌شود
    و همان کاغذ دو بار خرج می‌شود.

    فقط دسته‌های موجودِ عددی سنجیده می‌شوند؛ دسته‌ی غیرعددی مقایسه‌پذیر نیست.
    """
    if not (first.isdigit() and last.isdigit()):
        return
    lo, hi = int(first), int(last)
    query = db.query(Checkbook).filter(Checkbook.bank_account_id == bank_account_id)
    if exclude_id is not None:
        query = query.filter(Checkbook.id != exclude_id)
    for other in query.all():
        bounds = _numeric_range(other)
        if bounds is None:
            continue
        o_lo, o_hi = bounds
        if lo <= o_hi and o_lo <= hi:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"بازه‌ی این دسته با دسته‌چکِ «{label(other)}» "
                f"({other.first_number} تا {other.last_number}) هم‌پوشانی دارد؛ "
                "یک شماره نباید از دو دسته قابلِ صدور باشد",
            )


def _resolve_bank(db: Session, bank_account_id: UUID) -> BankAccount:
    bank = db.get(BankAccount, bank_account_id)
    if bank is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب بانکی یافت نشد")
    return bank


def _leaf_count(first: str, last: str, given: int) -> int:
    """اگر هر دو عددی‌اند، شمارِ برگ را خودمان حساب می‌کنیم — کاربر نباید ریاضی کند."""
    count = given
    if count <= 0 and first.isdigit() and last.isdigit():
        count = int(last) - int(first) + 1
    if count <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تعداد برگ باید مثبت باشد")
    return count


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def row(db: Session, book: Checkbook, *, bank_name: str | None = None, used: int | None = None) -> dict:
    used = used_count(db, book) if used is None else used
    if bank_name is None:
        bank = db.get(BankAccount, book.bank_account_id)
        bank_name = bank.name if bank else ""
    return {
        "id": book.id,
        "bank_account_id": book.bank_account_id,
        "bank_account_name": bank_name or "",
        "serial": book.serial,
        "first_number": book.first_number,
        "last_number": book.last_number,
        "leaf_count": book.leaf_count,
        "used_count": used,
        "remaining_count": max(book.leaf_count - used, 0),
        "issue_date": book.issue_date,
        "description": book.description,
        "is_active": book.is_active,
        "cheque_print_format": book.cheque_print_format,
    }


def list_checkbooks(db: Session) -> list[dict]:
    """دسته‌چک‌ها با شمارِ برگِ خرج‌شده.

    «چند برگ مانده» از روی چک‌های وصل‌شده شمرده می‌شود نه از یک شمارنده‌ی جدا:
    شمارنده با هر ابطال/حذفِ چک از واقعیت فاصله می‌گرفت.
    """
    used = dict(
        db.query(Check.checkbook_id, func.count(Check.id))
        .filter(Check.checkbook_id.isnot(None))
        .group_by(Check.checkbook_id)
        .all()
    )
    rows = (
        db.query(Checkbook, BankAccount.name)
        .outerjoin(BankAccount, BankAccount.id == Checkbook.bank_account_id)
        .order_by(Checkbook.created_at.desc())
        .all()
    )
    return [row(db, book, bank_name=bank_name, used=used.get(book.id, 0)) for book, bank_name in rows]


def create_checkbook(db: Session, data: CheckbookIn, user: User) -> Checkbook:
    bank = _resolve_bank(db, data.bank_account_id)

    first = data.first_number.strip()
    last = data.last_number.strip()
    if not first or not last:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "شماره‌ی اولین و آخرین برگ لازم است")

    leaf_count = _leaf_count(first, last, data.leaf_count)
    serial = data.serial.strip()
    _assert_serial_free(db, bank.id, serial)
    assert_no_range_overlap(db, bank.id, first, last)

    book = Checkbook(
        bank_account_id=bank.id,
        serial=serial,
        first_number=first,
        last_number=last,
        leaf_count=leaf_count,
        issue_date=data.issue_date,
        description=data.description.strip(),
        cheque_print_format=data.cheque_print_format.strip(),
        is_active=True,
        created_by_id=user.id,
    )
    db.add(book)
    db.flush()
    db.refresh(book)
    return book


#: تغییرشان بعد از خرج‌شدنِ اولین برگ، سابقه‌ی چک‌های صادرشده را بی‌معنا می‌کند.
STRUCTURAL_FIELDS = ("bank_account_id", "first_number", "last_number", "leaf_count")


def update_checkbook(db: Session, checkbook_id: UUID, data: CheckbookUpdateIn) -> Checkbook:
    """ویرایشِ دسته — ساختاری فقط تا وقتی برگی خرج نشده.

    تا امروز هیچ راهی برای ویرایش نبود (فقط باز/بستن و حذف)، پس یک غلطِ تایپی در
    شماره‌ی آخرین برگ تا ابد می‌ماند. ولی تغییرِ حساب یا بازه پس از خرج‌شدنِ برگ،
    چکِ صادرشده را به دسته‌ای نسبت می‌دهد که هرگز از آن نیامده — پس مسدود است.
    """
    book = resolve(db, checkbook_id)
    fields = data.model_dump(exclude_unset=True)

    touched = [f for f in STRUCTURAL_FIELDS if f in fields]
    if touched:
        used = used_count(db, book)
        if used:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"از این دسته {used} برگ صادر شده است؛ حساب و بازه‌ی شماره دیگر "
                "عوض نمی‌شوند. سری، توضیحات و وضعیت را می‌توانید ویرایش کنید.",
            )

    bank_account_id = fields.get("bank_account_id", book.bank_account_id)
    if "bank_account_id" in fields:
        _resolve_bank(db, bank_account_id)

    first = fields.get("first_number", book.first_number).strip()
    last = fields.get("last_number", book.last_number).strip()
    if not first or not last:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "شماره‌ی اولین و آخرین برگ لازم است")

    serial = fields.get("serial", book.serial).strip()
    if serial != book.serial or bank_account_id != book.bank_account_id:
        _assert_serial_free(db, bank_account_id, serial, exclude_id=book.id)
    if touched:
        assert_no_range_overlap(db, bank_account_id, first, last, exclude_id=book.id)

    book.bank_account_id = bank_account_id
    book.serial = serial
    book.first_number = first
    book.last_number = last
    if touched:
        book.leaf_count = _leaf_count(first, last, fields.get("leaf_count", 0))
    if "issue_date" in fields:
        book.issue_date = fields["issue_date"]
    if "description" in fields:
        book.description = fields["description"].strip()
    if "cheque_print_format" in fields:
        book.cheque_print_format = fields["cheque_print_format"].strip()
    if "is_active" in fields:
        book.is_active = fields["is_active"]

    db.flush()
    db.refresh(book)
    return book


def delete_checkbook(db: Session, checkbook_id: UUID) -> None:
    """فقط دسته‌ی دست‌نخورده حذف می‌شود.

    دسته‌ای که برگ خورده سابقه‌ی چک‌های صادرشده است؛ حذفش آن چک‌ها را بی‌ریشه
    می‌کند. به‌جای حذف، «بستن» (is_active=false) کارِ درست است و پیام همین را می‌گوید.
    """
    book = resolve(db, checkbook_id)
    used = used_count(db, book)
    if used:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"از این دسته {used} برگ صادر شده است؛ به‌جای حذف آن را ببندید.",
        )
    db.delete(book)
    db.flush()


# ---------------------------------------------------------------------------
# قالبِ چاپ
# ---------------------------------------------------------------------------


def print_format(db: Session, book: Checkbook) -> str:
    """قالبِ چاپِ این دسته — خالی یعنی از حسابِ بانکی ارث می‌برد.

    یک زنجیره‌ی ساده به‌جای دو زیرساختِ موازیِ قالب. موتورِ چاپِ چک هنوز وجود
    ندارد؛ این فقط ترتیبِ خواندن را از حالا تثبیت می‌کند.
    """
    if book.cheque_print_format:
        return book.cheque_print_format
    bank = db.get(BankAccount, book.bank_account_id)
    return bank.cheque_print_format if bank else ""
