"""جستجو و ردیابیِ چک — یک موتور، چند نما.

**این دامنه‌ی دومِ چک نیست.** هرچه اینجاست از `checks` و `check_events` خوانده
می‌شود؛ نه کپیِ جستجویی ساخته می‌شود، نه وضعیتِ موازی. اگر این فایل و صفحه‌ی
عملیاتِ چک روزی دو جواب بدهند، یکی‌شان باگ است — نه «دو دیدگاه».

سه چیز اینجا اضافه می‌شود که در فهرستِ ساده نبود:

۱. **فیلترِ واقعیِ سمتِ سرور.** تا امروز `/api/checks` هیچ فیلتری نداشت و کلاینت
   همه‌ی چک‌ها را می‌گرفت و در مرورگر غربال می‌کرد. برای دفترِ کوچک کار می‌کرد و
   برای دفترِ بزرگ یعنی مگابایت‌ها داده برای پیدا‌کردنِ یک برگ.

۲. **«الان کجاست؟» (§۲۰ §۲۱).** خزانه‌دار وضعیتِ فنی را نمی‌خواهد، جایش را
   می‌خواهد: «دستِ بانک ملت»، «خرج‌شده به شرکت الف». این از وضعیت و پیوندهای
   واقعی **مشتق** می‌شود — هیچ‌جا به‌صورتِ متنِ آزاد ذخیره نمی‌شود، چون آن‌وقت
   می‌توانست با وضعیت نخواند.

۳. **شمارش و مبلغِ هر وضعیت (§۳۴)** — از همان داده، نه از جدولِ گزارشیِ جدا.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.models.banking import BankAccount, Check
from app.models.cashbox import Cashbox
from app.models.check_event import CheckEvent
from app.models.inventory import Contact
from app.services.check_ops import STATUS_LABEL

#: وضعیت‌هایی که «چک هنوز در جریان است» یعنی. حالت‌های پایانی (وصول، نقد،
#: واخواست، استرداد) بیرونند.
OPEN_STATUSES = ("in_hand", "deposited", "endorsed", "issued")


@dataclass(frozen=True)
class Holder:
    """جایی که چک الان هست — نوع، شناسه و برچسبِ خواندنی.

    `kind` می‌گوید به کدام موجودیت اشاره می‌کند تا رابط بتواند لینک بدهد؛
    `label` برای خواندن است، نه برای ذخیره‌کردن.
    """

    kind: str
    label: str
    id: UUID | None = None


def current_holder(db: Session, check: Check) -> Holder:
    """«الان کجاست؟» — مشتق از وضعیت و پیوندهای واقعی (§۲۰ §۲۱).

    هیچ ستونی برای این نگه نمی‌داریم. ستونِ جدا یعنی یک عددِ دومِ قابلِ دریفت:
    چکی که وضعیتش عوض شده ولی «محل»ش نه، دقیقاً همان دروغی است که این فصل
    می‌خواهد نباشد.
    """
    status = check.status
    if status == "deposited":
        bank = db.get(BankAccount, check.bank_account_id) if check.bank_account_id else None
        return Holder("bank_account", f"دستِ بانک — {bank.name}" if bank else "دستِ بانک", bank.id if bank else None)
    if status == "cashed":
        box = db.get(Cashbox, check.cashbox_id) if check.cashbox_id else None
        return Holder("cashbox", f"نقد شده به {box.name}" if box else "نقد شده", box.id if box else None)
    if status == "endorsed":
        #: گیرنده روی **رویدادِ خرج** نشسته، نه روی خودِ چک: `check.contact_id`
        #: هنوز کسی است که چک را به ما داده.
        event = (
            db.query(CheckEvent)
            .filter(CheckEvent.check_id == check.id, CheckEvent.operation == "endorse")
            .order_by(CheckEvent.at.desc())
            .first()
        )
        holder = db.get(Contact, event.contact_id) if event and event.contact_id else None
        return Holder(
            "contact",
            f"خرج‌شده به {holder.name}" if holder else "خرج‌شده",
            holder.id if holder else None,
        )
    if status == "in_hand":
        return Holder("company", "نزدِ ما")
    if status == "issued":
        holder = db.get(Contact, check.contact_id) if check.contact_id else None
        return Holder(
            "contact",
            f"دستِ {holder.name}" if holder else "دستِ گیرنده",
            holder.id if holder else None,
        )
    if status == "returned":
        holder = db.get(Contact, check.contact_id) if check.contact_id else None
        return Holder(
            "contact",
            f"مسترد شده به {holder.name}" if holder else "مسترد شده",
            holder.id if holder else None,
        )
    #: `cleared` و `bounced` — چک دیگر «جایی» ندارد؛ وضعیت خودش جواب است.
    return Holder("none", STATUS_LABEL.get(status, status))


def search(
    db: Session,
    *,
    q: str | None = None,
    type_: str | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    bank_account_id: UUID | None = None,
    cashbox_id: UUID | None = None,
    contact_id: UUID | None = None,
):
    """کوئریِ پایه‌ی جستجو — فیلترها روی سرور، نه در مرورگر.

    `q` عمداً روی **شماره، صیادی، پشت‌نمره، صاحبِ چک، نامِ بانک و شرح** می‌گردد
    (§۲۲: فیلترِ سریع). نامِ طرف حساب هم با `join` می‌آید، چون کاربر معمولاً همان
    را می‌داند نه شناسه‌اش.
    """
    query = db.query(Check).options(selectinload(Check.contact))

    if type_ in ("receivable", "payable"):
        query = query.filter(Check.type == type_)
    if status:
        query = query.filter(Check.status == status)
    if statuses:
        query = query.filter(Check.status.in_(statuses))
    if due_from is not None:
        query = query.filter(Check.due_date >= due_from)
    if due_to is not None:
        query = query.filter(Check.due_date <= due_to)
    if amount_min is not None:
        query = query.filter(Check.amount >= amount_min)
    if amount_max is not None:
        query = query.filter(Check.amount <= amount_max)
    if bank_account_id is not None:
        query = query.filter(Check.bank_account_id == bank_account_id)
    if cashbox_id is not None:
        query = query.filter(Check.cashbox_id == cashbox_id)
    if contact_id is not None:
        query = query.filter(Check.contact_id == contact_id)

    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        query = query.outerjoin(Contact, Check.contact_id == Contact.id).filter(
            or_(
                Check.number.ilike(like),
                Check.sayad_id.ilike(like),
                Check.back_number.ilike(like),
                Check.owner_name.ilike(like),
                Check.bank_name.ilike(like),
                Check.description.ilike(like),
                Contact.name.ilike(like),
            )
        )
    return query


def summary(db: Session, *, type_: str | None = None) -> list[dict]:
    """شمارش و جمعِ مبلغِ هر وضعیت (§۳۴).

    از همان کوئریِ جستجو می‌آید، نه از جدولِ گزارشیِ جدا — پس هیچ‌وقت با فهرست
    اختلاف پیدا نمی‌کند. ترتیب همان `STATUS_LABEL` است تا KPIها جای ثابت داشته
    باشند و کاربر هر بار دنبالِ ستون نگردد.
    """
    rows = search(db, type_=type_).all()
    buckets: dict[str, dict] = {}
    for check in rows:
        bucket = buckets.setdefault(
            check.status,
            {"status": check.status, "label": STATUS_LABEL.get(check.status, check.status),
             "count": 0, "amount": Decimal(0)},
        )
        bucket["count"] += 1
        bucket["amount"] += Decimal(check.amount)
    return [buckets[s] for s in STATUS_LABEL if s in buckets]
