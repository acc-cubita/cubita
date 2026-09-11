"""چرخه‌ی عمرِ چک — یک موجودیت، چند عملیات، یک تاریخچه.

## اصلِ دامنه

**یک برگِ کاغذ = یک رکورد.** واگذاری به بانک چکِ دوم نمی‌سازد، برگشت از خرج چکِ
سوم نمی‌سازد. همان `Check` وضعیت عوض می‌کند و هر گذر یک ردیف در `check_events`
می‌گذارد.

## چرا این فایل از `banking.py` جدا شد

منطقِ چک آنجا بینِ صورت‌حسابِ بانک و تنخواه پخش بود و به ۲۵۰ خط رسیده بود. حالا
که هر گذر رویدادِ تاریخچه هم می‌نویسد و عملیاتِ گروهی هم دارد، موتورِ خودش را
می‌خواهد — قرینه‌ی `pos_settlements.py`.

## سه چیزی که این پاس درست کرد

**۱. واگذاری در دفتر دیده می‌شود (§۹ §۱۳).** تا امروز `in_hand → deposited` هیچ
سندی نمی‌زد و فقط `bank_account_id` را می‌نشاند. یعنی مبلغِ چک تا لحظه‌ی وصول روی
«چک‌های دریافتنی» می‌ماند و دفتر نمی‌توانست بگوید چقدرش نزدِ ماست و چقدرش دستِ
بانک. حالا طبقه‌بندیِ دوباره است:

    چک‌های واگذارشده به بانک   بدهکار
        چک‌های دریافتنی            بستانکار

و وصول/واخواست از همان حسابِ واسط بستانکار می‌شوند، نه از «چک‌های دریافتنی».

**۲. نقد کردن (§۱۸-۲۰).** چکِ دریافتنی می‌تواند مستقیم نقد شود و پولش به صندوق
برود. تا امروز چنین راهی نبود و تنها گزینه «وصول» بود — که پول را به بانکی
می‌برد که هرگز چیزی نگرفته بود.

**۳. استردادِ چکِ پرداختنی (§۳۱).** `PAYABLE_TRANSITIONS` فقط `cleared` و
`bounced` داشت. بدتر: ردیف‌های `returned` سمتِ *دریافتنی* hard-code شده بودند، پس
اگر کسی این گذر را باز می‌کرد، سندِ غلط می‌خورد بی‌آنکه چیزی خطا بدهد.

## آنچه عمداً اینجا نیست

**جدولِ جداگانه‌ی «عملیاتِ چک».** فهرستِ عملیات از `check_events` ساخته می‌شود و
گروه‌بندیِ `batch_id` همان چیزی را می‌دهد که یک موجودیتِ جدا می‌داد — بدونِ
دومین جای ذخیره‌ی همان رابطه. اگر روزی عملیات فیلدِ خودش لازم داشت (پیوست،
وضعیتِ تأیید)، آن‌وقت جدول می‌گیرد.
"""
from __future__ import annotations

import uuid
from datetime import date as date_
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import JournalLine
from app.models.banking import BankAccount, BankTransaction, Check, Checkbook
from app.models.cashbox import Cashbox
from app.models.check_event import CheckEvent
from app.models.counters import DOC_CHECK_OPERATION
from app.models.inventory import Contact
from app.models.user import User
from app.schemas.banking import CheckIn
from app.services import cashboxes, checkbooks
from app.services import chart_codes as cc
from app.services.common import get_account, get_or_create_account, make_journal_entry
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open

#: گرافِ وضعیتِ چکِ دریافتنی. **هیچ حالتی نباید بن‌بست باشد** مگر واقعاً پایانِ راه
#: باشد (`cleared`، `bounced`، `returned`، `cashed`).
#:
#: تا پیش از این `endorsed` کلید نداشت، یعنی چکی که خرج شده بود برای همیشه قفل
#: می‌شد و «برگشت از خرج کردن» ناممکن بود. `deposited` هم راهِ بازگشت نداشت، با
#: آن‌که کامنتِ همین‌جا و متنِ صفحه‌ی «استرداد چک» هر دو وعده‌اش را می‌دادند.
RECEIVABLE_TRANSITIONS = {
    # `returned` = استرداد: چک را بدونِ وصول به صاحبش پس می‌دهیم. فقط از «نزدِ ما»
    # ممکن است؛ چکی که به بانک سپرده شده اول باید برگردد.
    # `cashed` = نقد کردن، که با وصولِ بانکی یکی نیست (§۱۹).
    "in_hand": {"deposited", "endorsed", "returned", "cashed"},
    # بازگشت از بانک بدونِ واخواست — بانک برگ را پس داده ولی برگشت نزده.
    "deposited": {"cleared", "bounced", "in_hand"},
    # برگشت از خرج کردن: گیرنده برگ را به ما پس داده.
    "endorsed": {"in_hand"},
}
PAYABLE_TRANSITIONS = {
    # `returned` = چکِ صادرشده پیش از وصول به ما برگشت (§۳۱).
    "issued": {"cleared", "bounced", "returned"},
}

#: گذر → نامِ عملیات. **از وضعیتِ مقصد استنتاج نمی‌شود** و نباید بشود:
#: `deposited → in_hand` و `endorsed → in_hand` هر دو به یک وضعیت می‌رسند ولی دو
#: رویدادِ کاملاً متفاوت‌اند.
OPERATION_BY_TRANSITION: dict[tuple[str, str], str] = {
    ("in_hand", "deposited"): "deposit",
    ("in_hand", "endorsed"): "endorse",
    ("in_hand", "returned"): "refund",
    ("in_hand", "cashed"): "cash",
    ("deposited", "cleared"): "collect",
    ("deposited", "bounced"): "dishonor",
    ("deposited", "in_hand"): "undeposit",
    ("endorsed", "in_hand"): "return_endorsed",
    ("issued", "cleared"): "collect",
    ("issued", "bounced"): "dishonor",
    ("issued", "returned"): "refund",
}

#: برچسبِ فارسیِ وضعیت — برای پیامِ خطا. کاربر نباید `in_hand` بخواند (§۴۳).
STATUS_LABEL = {
    "in_hand": "نزدِ ما",
    "deposited": "واگذارشده به بانک",
    "cleared": "وصول‌شده",
    "bounced": "برگشتی (واخواست)",
    "endorsed": "خرج‌شده",
    "issued": "صادرشده",
    "returned": "مسترد شده",
    "cashed": "نقد شده",
}

OPERATION_LABEL = {
    "receive": "دریافت",
    "issue": "صدور",
    "deposit": "واگذاری به بانک",
    "undeposit": "بازگشت از بانک",
    "collect": "وصول",
    "dishonor": "واخواست",
    "cash": "نقد کردن",
    "endorse": "خرج کردن",
    "return_endorsed": "برگشت از خرج",
    "refund": "استرداد",
}


def in_collection_account(db: Session):
    """حسابِ «چک‌های واگذارشده به بانک» — و اگر نبود، ساختنش.

    `get_or_create` است نه `get`، چون این نقش بعد از استقرارِ کسب‌وکارهای موجود
    اضافه شده و چارتِ آن‌ها آن را ندارد.
    """
    return get_or_create_account(
        db,
        cc.CHECKS_IN_COLLECTION,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.CHECKS_IN_COLLECTION],
        name="چک‌های واگذارشده به بانک",
        acc_type="asset",
        parent_code="1",
    )


# ─────────────────────────────── ثبتِ رویداد ───────────────────────────────


def record_event(
    db: Session,
    check: Check,
    *,
    operation: str,
    from_status: str | None,
    to_status: str,
    event_date: date_,
    user: User,
    bank_account_id: UUID | None = None,
    cashbox_id: UUID | None = None,
    contact_id: UUID | None = None,
    journal_entry_id: UUID | None = None,
    operation_no: int | None = None,
    batch_id: UUID | None = None,
    note: str = "",
) -> CheckEvent:
    """یک گذر را در تاریخچه می‌نویسد.

    **تنها جایی که `check_events` نوشته می‌شود.** جدول فقط‌افزودنی است، پس اشتباهِ
    اینجا با UPDATE قابلِ جبران نیست — به‌جایش رویدادِ تازه اضافه می‌شود.
    """
    event = CheckEvent(
        check_id=check.id,
        operation=operation,
        from_status=from_status,
        to_status=to_status,
        event_date=event_date,
        bank_account_id=bank_account_id,
        cashbox_id=cashbox_id,
        contact_id=contact_id,
        journal_entry_id=journal_entry_id,
        operation_no=operation_no,
        batch_id=batch_id,
        note=note or "",
        created_by_id=user.id if user else None,
    )
    db.add(event)
    db.flush()
    return event


def timeline(db: Session, check_id: UUID) -> list[dict]:
    """تاریخچه‌ی یک چک، از قدیم به جدید (§۳۶)."""
    rows = (
        db.query(CheckEvent)
        .filter(CheckEvent.check_id == check_id)
        .order_by(CheckEvent.at, CheckEvent.event_date)
        .all()
    )
    return [_event_row(db, e) for e in rows]


def _event_row(db: Session, event: CheckEvent) -> dict:
    bank = db.get(BankAccount, event.bank_account_id) if event.bank_account_id else None
    box = db.get(Cashbox, event.cashbox_id) if event.cashbox_id else None
    contact = db.get(Contact, event.contact_id) if event.contact_id else None
    return {
        "id": event.id,
        "check_id": event.check_id,
        "operation": event.operation,
        "operation_label": OPERATION_LABEL.get(event.operation, event.operation),
        "from_status": event.from_status,
        "to_status": event.to_status,
        "to_status_label": STATUS_LABEL.get(event.to_status, event.to_status),
        "event_date": event.event_date,
        "at": event.at,
        "operation_no": event.operation_no,
        "batch_id": event.batch_id,
        "bank_account_id": event.bank_account_id,
        "bank_account_name": bank.name if bank else None,
        "cashbox_id": event.cashbox_id,
        "cashbox_name": box.name if box else None,
        "contact_id": event.contact_id,
        "contact_name": contact.name if contact else None,
        "journal_entry_id": event.journal_entry_id,
        "note": event.note,
    }


# ──────────────────────────────── ساختِ چک ────────────────────────────────


def _resolve_leaf(db: Session, data: CheckIn) -> Checkbook | None:
    """دسته‌ی این چک را پیدا و برگش را می‌سنجد.

    دو چیزِ جدا که قاطی‌شان نکنیم:

    * **یکپارچگی** — اگر دسته‌ای انتخاب شده، شماره باید از همان دسته و خرج‌نشده
      باشد. این همیشه سنجیده می‌شود، در هر سیاستی؛ بدونش «برگِ مانده» عددِ دروغ
      می‌دهد و همان کاغذ دو بار خرج می‌شود.
    * **سیاست** — اینکه چکِ پرداختنی *اجازه دارد* بی‌دسته باشد یا نه، انتخابِ
      کسب‌وکار است و پیش‌فرضش «دارد» (رفتارِ امروز).

    چکِ دریافتنی دسته ندارد: کاغذش مالِ ما نیست و شماره‌اش را طرفِ مقابل نوشته.
    """
    if data.type == "receivable":
        return None

    if data.checkbook_id is None:
        if checkbooks.get_control_mode(db) == "book":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "طبقِ تنظیماتِ این کسب‌وکار، چکِ پرداختنی باید از یک دسته‌چک صادر "
                "شود. از صفحه‌ی «دسته چک» دسته را انتخاب و برگ را صادر کنید.",
            )
        return None

    book = checkbooks.resolve(db, data.checkbook_id)
    checkbooks.assert_leaf_available(db, book, data.number.strip())
    return book


def create_check(db: Session, data: CheckIn, user: User) -> Check:
    assert_period_open(db, data.issue_date)

    initial_status = "in_hand" if data.type == "receivable" else "issued"
    book = _resolve_leaf(db, data)

    if data.type == "receivable":
        # چک دریافتنی بابت مطالبات مشتری: از حساب دریافتنی به چک‌های دریافتنی منتقل می‌شود
        lines = [
            JournalLine(account_id=get_account(db, cc.CHECKS_RECEIVABLE).id, debit=data.amount, credit=0),
            JournalLine(account_id=get_account(db, cc.ACCOUNTS_RECEIVABLE).id, debit=0, credit=data.amount),
        ]
        description = f"دریافت چک شماره {data.number} بابت مطالبات"
    else:
        # چک پرداختنی بابت بدهی به تأمین‌کننده: از حساب پرداختنی به چک‌های پرداختنی منتقل می‌شود
        lines = [
            JournalLine(account_id=get_account(db, cc.ACCOUNTS_PAYABLE).id, debit=data.amount, credit=0),
            JournalLine(account_id=get_account(db, cc.CHECKS_PAYABLE).id, debit=0, credit=data.amount),
        ]
        description = f"صدور چک شماره {data.number} بابت بدهی"

    journal_entry = make_journal_entry(db, data.issue_date, description, "check", user, lines)

    check = Check(
        type=data.type,
        number=data.number,
        back_number=(data.back_number or "").strip(),
        sayad_id=(data.sayad_id or "").strip(),
        bank_name=data.bank_name,
        amount=data.amount,
        issue_date=data.issue_date,
        due_date=data.due_date,
        status=initial_status,
        description=data.description,
        contact_id=data.contact_id,
        checkbook_id=book.id if book else None,
        #: حسابِ بانکی از خودِ دسته می‌آید. تا امروز چکِ پرداختنی تا لحظه‌ی وصول
        #: هیچ حسابی نداشت و آن‌وقت **دوباره** از کاربر پرسیده می‌شد — با آنکه
        #: دسته از روزِ اول می‌دانستش.
        bank_account_id=book.bank_account_id if book else None,
        created_by_id=user.id,
    )
    db.add(check)
    db.flush()

    #: رویدادِ اولِ تایم‌لاین. بدونش تاریخچه از وسط شروع می‌شد.
    record_event(
        db,
        check,
        operation="receive" if data.type == "receivable" else "issue",
        from_status=None,
        to_status=initial_status,
        event_date=data.issue_date,
        user=user,
        contact_id=data.contact_id,
        bank_account_id=check.bank_account_id,
        journal_entry_id=journal_entry.id,
    )
    db.refresh(check)
    return check


# ───────────────────────────── گذرِ وضعیت ─────────────────────────────


def _clearing_account(db: Session, check: Check, sent_id: UUID | None) -> BankAccount:
    """حسابی که پول از آن کم/به آن اضافه می‌شود هنگامِ وصول.

    چکِ پرداختنیِ صادرشده از یک دسته‌چک، حسابش را از همان دسته دارد؛ پرسیدنِ
    دوباره‌اش هم اضافه است هم راهی برای ناسازگاری — تعهد روی یک حساب ثبت شده بود
    و پول از حسابِ دیگری کم می‌شد. پس حسابِ ناهمخوانِ ارسالی **رد** می‌شود،
    نه اینکه بی‌صدا یکی ترجیح داده شود.
    """
    own = db.get(BankAccount, check.bank_account_id) if check.bank_account_id else None
    if check.type == "receivable":
        #: چکِ دریافتنی حسابش را در «واگذاری به بانک» گرفته، نه از دسته‌چک.
        if own is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "حساب بانکی مشخص نیست")
        return own

    sent = db.get(BankAccount, sent_id) if sent_id else None
    if own is not None and sent is not None and sent.id != own.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"این چک از حسابِ «{own.name}» صادر شده است؛ وصولش از حسابِ دیگری ثبت نمی‌شود",
        )
    account = own or sent
    if account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "حساب بانکی مشخص نیست")
    return account



def assert_not_pledged_to_payment(db: Session, check: Check, new_status: str) -> None:
    """چکی که با اعلامیه‌ی پرداخت خرج شده، از مسیرِ دیگری برنگردد.

    **این گارد جلوی از‌دست‌رفتنِ پول را می‌گیرد، نه یک ناسازگاریِ ظاهری را.** بدونش:

    ۱. چک با اعلامیه خرج می‌شود → ردیفِ `PaymentChequeTransfer` با `reversed_at` خالی
    ۲. کسی عملیاتِ «برگشت از خرج کردن» را از صفحه‌ی چک می‌زند → وضعیت `in_hand`
       می‌شود ولی آن ردیف دست‌نخورده می‌ماند
    ۳. ابطالِ اعلامیه حالا ۴۰۹ می‌گیرد (گاردش وضعیتِ `endorsed` می‌خواهد) — پس
       سندِ اعلامیه می‌ماند و بدهی تسویه‌شده حساب می‌شود
    ۴. و همان چک دوباره قابلِ خرج‌کردن است

    یعنی بدهی با چکی تسویه شده که برگشته، بی‌هیچ سندِ معکوس و بی‌راهی برای ابطال.
    """
    if new_status != "in_hand" or check.status != "endorsed":
        return
    from app.models.payment import Payment, PaymentChequeTransfer

    pledged = (
        db.query(PaymentChequeTransfer.id)
        .join(Payment, Payment.id == PaymentChequeTransfer.payment_id)
        .filter(
            PaymentChequeTransfer.check_id == check.id,
            PaymentChequeTransfer.reversed_at.is_(None),
            Payment.voided_at.is_(None),
        )
        .first()
    )
    if pledged is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"چکِ شماره‌ی {check.number} با یک اعلامیه‌ی پرداخت خرج شده است؛ "
            "برای برگرداندنش همان اعلامیه را باطل کنید، نه این عملیات را.",
        )


def assert_can_transition(check: Check, new_status: str) -> None:
    """§۴۳ — خطا باید بگوید *چرا* نمی‌شود، نه فقط «مجاز نیست».

    پیامِ قبلی وضعیت‌ها را با نامِ داخلیِ انگلیسی می‌گفت (`in_hand`، `deposited`)
    که برای کاربرِ فارسی‌زبان تقریباً بی‌معنی بود.
    """
    transitions = RECEIVABLE_TRANSITIONS if check.type == "receivable" else PAYABLE_TRANSITIONS
    allowed = transitions.get(check.status, set())
    if new_status in allowed:
        return
    now = STATUS_LABEL.get(check.status, check.status)
    want = STATUS_LABEL.get(new_status, new_status)
    if not allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"چک شماره {check.number} در وضعیتِ «{now}» است و دیگر عملیاتی نمی‌پذیرد.",
        )
    options = "، ".join(STATUS_LABEL.get(s, s) for s in sorted(allowed))
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        f"چک شماره {check.number} در وضعیتِ «{now}» است و «{want}» از آن ممکن نیست. "
        f"از این وضعیت فقط این‌ها ممکن‌اند: {options}.",
    )


def update_check_status(
    db: Session,
    check_id: UUID,
    new_status: str,
    bank_account_id: UUID | None,
    user: User,
    *,
    cashbox_id: UUID | None = None,
    contact_id: UUID | None = None,
    event_date: date_ | None = None,
    note: str = "",
    operation_no: int | None = None,
    batch_id: UUID | None = None,
    external_journal_entry_id: UUID | None = None,
) -> Check:
    """تنها جایی که `checks.status` نوشته می‌شود — و همیشه با یک رویداد.

    `external_journal_entry_id` یعنی **حسابداری را فراخواننده زده است**؛ سندی
    این‌جا ساخته نمی‌شود و همان شناسه روی رویداد می‌نشیند. لازمش داریم چون
    اعلامیه‌ی پرداخت و رسید دریافت هر کدام *یک* سند دارند (§۳۰) و ردیف‌های چک
    داخلِ همان سند جمع می‌شوند؛ بدونِ این پارامتر، یا سند دوبار می‌خورد یا
    وضعیت بی‌رویداد عوض می‌شود. هر دو غلط‌اند.
    """
    check = db.get(Check, check_id)
    if check is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "چک یافت نشد")

    assert_can_transition(check, new_status)
    assert_not_pledged_to_payment(db, check, new_status)
    from_status = check.status
    operation = OPERATION_BY_TRANSITION[(from_status, new_status)]
    when = event_date or check.due_date

    # گاردِ دوره فقط برای انتقال‌هایی که واقعاً سند می‌زنند. تنها گذرِ بی‌سند
    # «بازگشت از بانک» است — و آن هم سندِ قرینه‌ی واگذاری را می‌زند، پس در عمل
    # همه‌ی گذرها سند دارند و دوره سنجیده می‌شود.
    assert_period_open(db, when)

    journal_entry = None
    #: سندِ فراخواننده — شاخه‌های پایین رد می‌شوند تا اثرِ مالی دوبار نخورد.
    caller_posted = external_journal_entry_id is not None
    event_bank_id = None
    event_cashbox_id = None

    if caller_posted:
        pass

    elif new_status == "deposited":
        if bank_account_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای واگذاری چک، انتخاب حساب بانکی لازم است")
        bank = db.get(BankAccount, bank_account_id)
        if bank is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "حساب بانکی یافت نشد")
        check.bank_account_id = bank.id
        event_bank_id = bank.id
        #: §۱۳ — طبقه‌بندیِ دوباره، نه ایجادِ وجه. دارایی از بین نرفته؛ محلش عوض
        #: شده. تا امروز اینجا هیچ سندی زده نمی‌شد و دفتر این تفاوت را نمی‌دید.
        lines = [
            JournalLine(account_id=in_collection_account(db).id, debit=check.amount, credit=0),
            JournalLine(account_id=get_account(db, cc.CHECKS_RECEIVABLE).id, debit=0, credit=check.amount),
        ]
        journal_entry = make_journal_entry(
            db, when, f"واگذاری چک شماره {check.number} به بانک {bank.name}", "check", user, lines
        )

    elif new_status == "in_hand" and from_status == "deposited":
        #: بازگشت از بانک — معکوسِ دقیقِ سندِ واگذاری.
        lines = [
            JournalLine(account_id=get_account(db, cc.CHECKS_RECEIVABLE).id, debit=check.amount, credit=0),
            JournalLine(account_id=in_collection_account(db).id, debit=0, credit=check.amount),
        ]
        journal_entry = make_journal_entry(
            db, when, f"بازگشت چک شماره {check.number} از بانک بدونِ واخواست", "check", user, lines
        )
        check.bank_account_id = None

    elif new_status == "cleared":
        bank = _clearing_account(db, check, bank_account_id)
        event_bank_id = bank.id
        if check.type == "receivable":
            #: بستانکارْ حسابِ واسط است نه «چک‌های دریافتنی» — همان‌جا که واگذاری
            #: بدهکارش کرده بود. وگرنه حسابِ واسط تا ابد باز می‌ماند.
            lines = [
                JournalLine(
                    account_id=bank.gl_account_id,
                    analytic_id=bank.analytic_id,
                    debit=check.amount,
                    credit=0,
                ),
                JournalLine(account_id=in_collection_account(db).id, debit=0, credit=check.amount),
            ]
        else:
            lines = [
                JournalLine(account_id=get_account(db, cc.CHECKS_PAYABLE).id, debit=check.amount, credit=0),
                JournalLine(
                    account_id=bank.gl_account_id,
                    analytic_id=bank.analytic_id,
                    debit=0,
                    credit=check.amount,
                ),
            ]
        journal_entry = make_journal_entry(
            db, when, f"وصول/کسر چک شماره {check.number}", "check", user, lines
        )
        db.add(
            BankTransaction(
                bank_account_id=bank.id,
                transaction_date=when,
                amount=check.amount if check.type == "receivable" else -Decimal(check.amount),
                description=f"چک شماره {check.number}",
                source_type="check_clear",
                source_id=check.id,
                journal_entry_id=journal_entry.id,
                created_by_id=user.id,
            )
        )
        check.bank_account_id = bank.id

    elif new_status == "cashed":
        #: §۱۸-۲۰ — نقد کردن، که با وصولِ بانکی یکی نیست. پول به صندوق می‌رود.
        box = cashboxes.resolve_cashbox(db, cashbox_id)
        cashboxes.assert_usable(db, box, when)
        check.cashbox_id = box.id
        event_cashbox_id = box.id
        lines = [
            JournalLine(
                account_id=cashboxes.gl_account_id(db, box),
                #: تفصیلیِ صندوق — همان چیزی که مانده‌ی هر صندوق را جدا می‌کند.
                analytic_id=box.analytic_id,
                debit=check.amount,
                credit=0,
            ),
            JournalLine(account_id=get_account(db, cc.CHECKS_RECEIVABLE).id, debit=0, credit=check.amount),
        ]
        journal_entry = make_journal_entry(
            db, when, f"نقد کردن چک شماره {check.number} به صندوق {box.name}", "check", user, lines
        )

    elif new_status == "bounced":
        source = (
            in_collection_account(db).id
            if check.type == "receivable"
            else get_account(db, cc.CHECKS_PAYABLE).id
        )
        if check.type == "receivable":
            #: طلب به حسابِ مشتری برمی‌گردد؛ حسابِ واسط بسته می‌شود.
            lines = [
                JournalLine(account_id=get_account(db, cc.ACCOUNTS_RECEIVABLE).id, debit=check.amount, credit=0),
                JournalLine(account_id=source, debit=0, credit=check.amount),
            ]
        else:
            lines = [
                JournalLine(account_id=source, debit=check.amount, credit=0),
                JournalLine(account_id=get_account(db, cc.ACCOUNTS_PAYABLE).id, debit=0, credit=check.amount),
            ]
        journal_entry = make_journal_entry(
            db, when, f"واخواست چک شماره {check.number}", "check", user, lines
        )

    elif new_status == "returned":
        #: استرداد اثرِ ثبتِ اولیه را برمی‌گرداند — دقیقاً معکوسِ لحظه‌ی دریافت/صدور.
        #: با `bounced` یکی نیست؛ آن‌جا بانک برگشت زده و اینجا برگ سالم پس داده شده.
        #:
        #: **سمتِ پرداختنی تازه است.** تا امروز این شاخه ردیف‌های دریافتنی را
        #: بی‌قیدوشرط می‌نشاند، پس بازکردنِ `issued → returned` سندِ غلط می‌زد.
        if check.type == "receivable":
            lines = [
                JournalLine(account_id=get_account(db, cc.ACCOUNTS_RECEIVABLE).id, debit=check.amount, credit=0),
                JournalLine(account_id=get_account(db, cc.CHECKS_RECEIVABLE).id, debit=0, credit=check.amount),
            ]
            text = f"استرداد چک شماره {check.number} به صاحبش"
        else:
            lines = [
                JournalLine(account_id=get_account(db, cc.CHECKS_PAYABLE).id, debit=check.amount, credit=0),
                JournalLine(account_id=get_account(db, cc.ACCOUNTS_PAYABLE).id, debit=0, credit=check.amount),
            ]
            text = f"استردادِ چکِ پرداختنیِ شماره {check.number} به ما"
        journal_entry = make_journal_entry(db, when, text, "check", user, lines)

    elif new_status == "in_hand" and from_status == "endorsed":
        #: **برگشت از خرج کردن** — دقیقاً معکوسِ سندِ خرج: برگ دوباره نزدِ ماست و
        #: بدهیِ ما به کسی که به او داده بودیم هم برمی‌گردد.
        lines = [
            JournalLine(account_id=get_account(db, cc.CHECKS_RECEIVABLE).id, debit=check.amount, credit=0),
            JournalLine(account_id=get_account(db, cc.ACCOUNTS_PAYABLE).id, debit=0, credit=check.amount),
        ]
        journal_entry = make_journal_entry(
            db, when, f"برگشت از خرج کردن چک شماره {check.number}", "check", user, lines
        )

    elif new_status == "endorsed":
        lines = [
            JournalLine(account_id=get_account(db, cc.ACCOUNTS_PAYABLE).id, debit=check.amount, credit=0),
            JournalLine(account_id=get_account(db, cc.CHECKS_RECEIVABLE).id, debit=0, credit=check.amount),
        ]
        journal_entry = make_journal_entry(
            db, when, f"خرج کردن چک شماره {check.number} بابت پرداخت", "check", user, lines
        )

    check.status = new_status
    db.flush()

    record_event(
        db,
        check,
        operation=operation,
        from_status=from_status,
        to_status=new_status,
        event_date=when,
        user=user,
        bank_account_id=event_bank_id,
        cashbox_id=event_cashbox_id,
        contact_id=contact_id,
        journal_entry_id=journal_entry.id if journal_entry else external_journal_entry_id,
        operation_no=operation_no,
        batch_id=batch_id,
        note=note,
    )
    db.refresh(check)
    return check


# ──────────────────────────── عملیاتِ گروهی (§۴۴ §۴۵) ────────────────────────────


def run_operation(
    db: Session,
    user: User,
    *,
    check_ids: list[UUID],
    new_status: str,
    bank_account_id: UUID | None = None,
    cashbox_id: UUID | None = None,
    contact_id: UUID | None = None,
    event_date: date_ | None = None,
    note: str = "",
) -> dict:
    """یک عملیات روی چند چک — با نتیجه‌ی **جدا برای هر چک** (§۴۵).

    **چرا per-cheque و نه یک موفق/ناموفق:** کاربر ده چک را انتخاب می‌کند و یکی‌شان
    دیگر واجدِ شرایط نیست. «عملیات ناموفق» به او نمی‌گوید کدام و چرا، و او
    مجبور است یکی‌یکی امتحان کند.

    **کلِ عملیات در یک تراکنش است.** اگر یکی رد شود، بقیه هم برنمی‌گردند — چون
    هر چک `savepoint`ِ خودش را دارد. یعنی نُه چکِ سالم می‌روند و دهمی با دلیلش
    گزارش می‌شود.
    """
    if not check_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "هیچ چکی انتخاب نشده است")

    operation_no = next_document_number(db, DOC_CHECK_OPERATION)
    batch_id = uuid.uuid4()
    done: list[dict] = []
    failed: list[dict] = []
    operation = ""

    for check_id in check_ids:
        #: savepoint به‌ازای هر چک: خطای یکی نباید کارِ بقیه را برگرداند.
        try:
            with db.begin_nested():
                before = db.get(Check, check_id)
                if before is None:
                    raise HTTPException(status.HTTP_404_NOT_FOUND, "چک یافت نشد")
                #: نامِ عملیات را باید **پیش از** گذر برداشت؛ بعدش `from_status`
                #: دیگر روی رکورد نیست و `deposited → in_hand` از
                #: `endorsed → in_hand` قابلِ تفکیک نمی‌ماند.
                from_status = before.status
                check = update_check_status(
                    db,
                    check_id,
                    new_status,
                    bank_account_id,
                    user,
                    cashbox_id=cashbox_id,
                    contact_id=contact_id,
                    event_date=event_date,
                    note=note,
                    operation_no=operation_no,
                    batch_id=batch_id,
                )
            operation = operation or OPERATION_BY_TRANSITION.get((from_status, new_status), "")
            done.append({"check_id": check.id, "number": check.number, "amount": Decimal(check.amount)})
        except HTTPException as err:
            failed.append({"check_id": check_id, "reason": err.detail})

    if not done:
        #: هیچ‌کدام نرفت — شماره‌ی عملیات نباید بسوزد و کاربر باید دلیلِ اولی را
        #: ببیند. چون شمارنده داخلِ همین تراکنش بالا رفته، rollback برش می‌گرداند.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            failed[0]["reason"] if failed else "هیچ چکی واجدِ شرایط نبود",
        )

    return {
        "operation_no": operation_no,
        "batch_id": batch_id,
        "operation": operation,
        "operation_label": OPERATION_LABEL.get(operation, operation),
        "done": done,
        "failed": failed,
        "total_amount": sum((r["amount"] for r in done), Decimal(0)),
    }


def replay_operation(db: Session, batch_id: UUID) -> dict:
    """همان نتیجه، از روی رویدادهای ثبت‌شده — برای بازپخشِ idempotent.

    نتیجه ذخیره نمی‌شود و از `check_events` بازساخته می‌شود؛ به همان دلیلی که
    `services/idempotency.py` پاسخ را نگه نمی‌دارد: دو مسیرِ سریال‌سازی می‌توانند
    از هم جدا بیفتند، ولی رویدادها همان حقیقتِ واحدند.
    """
    rows = (
        db.query(CheckEvent)
        .filter(CheckEvent.batch_id == batch_id)
        .order_by(CheckEvent.at)
        .all()
    )
    if not rows:
        return None
    done = []
    for event in rows:
        check = db.get(Check, event.check_id)
        done.append(
            {
                "check_id": event.check_id,
                "number": check.number if check else "",
                "amount": Decimal(check.amount) if check else Decimal(0),
            }
        )
    first = rows[0]
    return {
        "operation_no": first.operation_no,
        "batch_id": batch_id,
        "operation": first.operation,
        "operation_label": OPERATION_LABEL.get(first.operation, first.operation),
        "done": done,
        #: ردنشده‌ها رویداد نساخته‌اند، پس بازپخش نمی‌تواند بازشان بسازد — و لازم
        #: هم نیست: کلاینتی که دوباره می‌فرستد دنبالِ «چه چیزی ثبت شد» است.
        "failed": [],
        "total_amount": sum((r["amount"] for r in done), Decimal(0)),
    }


# ──────────────────────────── فهرستِ عملیات (§۴۰ §۴۱) ────────────────────────────


def list_operations(
    db: Session,
    *,
    operation: str | None = None,
    date_from: date_ | None = None,
    date_to: date_ | None = None,
    limit: int = 200,
) -> list[dict]:
    """چه عملیاتی، کِی، روی کدام چک — نمای دومِ همان دامنه.

    «فهرستِ چک‌ها» می‌گوید الان چه داریم؛ این می‌گوید چه اتفاقی افتاده.
    """
    query = db.query(CheckEvent)
    if operation:
        query = query.filter(CheckEvent.operation == operation)
    if date_from is not None:
        query = query.filter(CheckEvent.event_date >= date_from)
    if date_to is not None:
        query = query.filter(CheckEvent.event_date <= date_to)
    rows = query.order_by(CheckEvent.at.desc()).limit(min(limit, 500)).all()

    out = []
    for event in rows:
        check = db.get(Check, event.check_id)
        row = _event_row(db, event)
        row["check_number"] = check.number if check else ""
        row["check_amount"] = Decimal(check.amount) if check else Decimal(0)
        row["check_type"] = check.type if check else ""
        out.append(row)
    return out


def assert_sayad_free(db: Session, sayad_id: str, *, exclude_check_id: UUID | None = None) -> None:
    """کد صیادی روی چکِ دیگری ثبت نشده باشد.

    کد در سطحِ **کشور** یکتاست — یک برگ، یک کد. پس تکراری‌بودنش یعنی یا دو بار
    ثبت شده یا اشتباه تایپ شده؛ هیچ‌کدام حالتی نیست که بخواهیم نگه داریم.

    مهاجرتِ ۰۱۱۰ ستون را داد ولی قیدی رویش نگذاشت؛ ایندکسِ جزئیِ
    `uq_checks_tenant_sayad` (مهاجرتِ ۰۱۱۱) پشتیبانِ همین سنجش در سطحِ
    پایگاه‌داده است.
    """
    sayad = (sayad_id or "").strip()
    if not sayad:
        return
    query = db.query(Check).filter(Check.sayad_id == sayad)
    if exclude_check_id is not None:
        query = query.filter(Check.id != exclude_check_id)
    twin = query.first()
    if twin is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"کد صیادی {sayad} قبلاً روی چکِ شماره‌ی {twin.number} ثبت شده است",
        )


def new_check_row(
    db: Session,
    data: CheckIn,
    user: User,
    *,
    receipt_id: UUID | None = None,
    payment_id: UUID | None = None,
    journal_entry_id: UUID | None = None,
) -> Check:
    """ردیفِ چک — **بدونِ سندِ حسابداریِ خودش**.

    از `create_check` جدا شد چون رسیدِ دریافت و اعلامیه‌ی پرداخت چکشان را در سندِ
    *خودشان* ثبت می‌کنند: یک سند برای یک رویداد (§۳۰). اثرِ حسابداری یکی است —
    فقط آن دو ردیف در سندِ رسید/اعلامیه جمع می‌شوند به‌جای سندِ جدا.

    **ولی رویدادِ تایم‌لاین حذف نمی‌شود.** قاعده‌ی این ماژول این است که هر چک از
    همان لحظه‌ی اول رویداد داشته باشد؛ بدونش تاریخچه از وسط شروع می‌شود و
    «این برگ از کجا آمد؟» بی‌جواب می‌ماند.
    """
    book = _resolve_leaf(db, data)
    assert_sayad_free(db, data.sayad_id)
    initial_status = "in_hand" if data.type == "receivable" else "issued"
    check = Check(
        type=data.type,
        number=data.number,
        bank_name=data.bank_name,
        amount=data.amount,
        issue_date=data.issue_date,
        due_date=data.due_date,
        status=initial_status,
        description=data.description,
        description2=data.description2,
        contact_id=data.contact_id,
        checkbook_id=book.id if book else None,
        #: حسابِ بانکی از خودِ دسته می‌آید (مهاجرتِ ۰۱۰۸).
        bank_account_id=book.bank_account_id if book else None,
        receipt_id=receipt_id,
        payment_id=payment_id,
        sayad_id=(data.sayad_id or "").strip(),
        back_number=(data.back_number or "").strip(),
        branch_name=data.branch_name,
        branch_code=data.branch_code,
        account_number=data.account_number,
        owner_name=data.owner_name,
        created_by_id=user.id,
    )
    db.add(check)
    db.flush()
    record_event(
        db,
        check,
        operation="receive" if data.type == "receivable" else "issue",
        from_status=None,
        to_status=initial_status,
        event_date=data.issue_date,
        user=user,
        contact_id=data.contact_id,
        bank_account_id=check.bank_account_id,
        journal_entry_id=journal_entry_id,
    )
    return check
