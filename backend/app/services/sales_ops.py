"""منطقِ عملیاتِ ماژولِ فروش.

سه‌جای این فایل تصمیمِ واقعی دارد و بقیه CRUDِ ساده است:

* `suggest_pricing` — قیمت و تخفیف را *پیشنهاد* می‌دهد، اعمال نمی‌کند.
* `run_commission` — نتیجه را ذخیره می‌کند، نه اینکه هر بار از نو بسازد.
* `post_note` — تنها چیزی در این ماژول که سند حسابداری می‌زند.
"""
from datetime import date as date_
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.accounting import JournalLine
from app.models.advanced_inventory import PriceList, PriceListItem
from app.models.counters import DOC_CREDIT_DEBIT_NOTE
from app.models.invoices import SalesInvoice
from app.models.sales_ops import (
    CommissionRule,
    CommissionRun,
    CommissionRunLine,
    CreditDebitNote,
    DiscountItemGroupMember,
    PricingFactor,
)
from app.models.user import User
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open


# ───────────────────────── ۱) پیشنهادِ قیمت‌گذاری ─────────────────────────


def _active_factors(db: Session, on: date_) -> list[PricingFactor]:
    """عامل‌های فعالِ همان تاریخ. بازه‌ی NULL یعنی بی‌کران از آن سمت."""
    return (
        db.query(PricingFactor)
        .filter(
            PricingFactor.is_active.is_(True),
            or_(PricingFactor.valid_from.is_(None), PricingFactor.valid_from <= on),
            or_(PricingFactor.valid_to.is_(None), PricingFactor.valid_to >= on),
        )
        .all()
    )


def suggest_pricing(db: Session, item_id: UUID, qty: Decimal, on: date_ | None = None) -> dict:
    """قیمت و تخفیفِ پیشنهادی برای یک ردیفِ فاکتور.

    **پیشنهاد است نه حکم.** فرم عدد را می‌گذارد و کاربر می‌تواند عوضش کند، و
    `applied` می‌گوید این عدد از کجا آمده تا کاربر بداند چرا. اجباری‌کردنش یعنی
    گره‌زدنِ مسیرِ ثبتِ حسابداری به موتوری که خطایش سند را وارونه می‌کند.

    ترتیبِ اعمال: قیمتِ پایه از آخرین اعلامیه‌ی قیمتِ اجراشده → عامل‌های افزاینده →
    تخفیف‌ها. افزاینده پیش از تخفیف می‌آید چون تخفیف روی قیمتِ نهایی معنی می‌دهد،
    نه روی قیمتِ پیش از حمل و بسته‌بندی.
    """
    on = on or date_.today()
    qty = Decimal(qty or 0)

    # آخرین اعلامیه‌ای که تا این تاریخ اجرا شده — نه هر اعلامیه‌ی فعالی.
    row = (
        db.query(PriceListItem.price, PriceList.name, PriceList.effective_from)
        .join(PriceList, PriceList.id == PriceListItem.price_list_id)
        .filter(
            PriceListItem.item_id == item_id,
            PriceList.is_active.is_(True),
            PriceList.effective_from <= on,
        )
        .order_by(PriceList.effective_from.desc())
        .first()
    )
    applied: list[dict] = []
    unit_price = Decimal(row[0]) if row else Decimal(0)
    if row:
        applied.append({"kind": "price_list", "name": row[1], "value": Decimal(row[0])})

    group_ids = {
        g for (g,) in db.query(DiscountItemGroupMember.group_id).filter(
            DiscountItemGroupMember.item_id == item_id
        )
    }

    def matches(f: PricingFactor) -> bool:
        if f.scope == "all":
            return True
        if f.scope == "item":
            return f.item_id == item_id
        return f.group_id in group_ids

    base = unit_price * qty
    markup = Decimal(0)
    for f in (x for x in _active_factors(db, on) if x.kind == "markup" and matches(x)):
        add = (base * Decimal(f.value) / 100) if f.mode == "percent" else (Decimal(f.value) * qty)
        markup += add
        applied.append({"kind": "markup", "name": f.name, "value": add})

    discount = Decimal(0)
    for f in (x for x in _active_factors(db, on) if x.kind == "discount" and matches(x)):
        cut = ((base + markup) * Decimal(f.value) / 100) if f.mode == "percent" else (Decimal(f.value) * qty)
        discount += cut
        applied.append({"kind": "discount", "name": f.name, "value": cut})

    # تخفیف هرگز از مبلغ بیشتر نشود — وگرنه ردیفِ منفی می‌سازد.
    discount = min(discount, base + markup)
    return {
        "unit_price": unit_price,
        "gross": base + markup,
        "discount": discount,
        "net": base + markup - discount,
        "applied": applied,
    }


# ─────────────────────────── ۲) بستنِ فاکتور ────────────────────────────


def close_invoices(
    db: Session,
    user: User,
    *,
    invoice_ids: list[UUID] | None = None,
    date_from: date_ | None = None,
    date_to: date_ | None = None,
) -> dict:
    """فاکتورها را می‌بندد — دسته‌ای یا موردی.

    بستن هیچ اثرِ مالی ندارد؛ فقط فاکتور را از دسترسِ ویرایش و ابطال بیرون می‌برد.
    یک‌طرفه است، به همان دلیلی که «دائم‌کردنِ سند» یک‌طرفه است: «بسته» یعنی
    امضاشده، و برگرداندنش همان چیزی است که این وضعیت باید جلویش را بگیرد.
    """
    query = db.query(SalesInvoice).filter(
        SalesInvoice.closed_at.is_(None), SalesInvoice.voided_at.is_(None)
    )
    if invoice_ids:
        query = query.filter(SalesInvoice.id.in_(invoice_ids))
    if date_from:
        query = query.filter(SalesInvoice.invoice_date >= date_from)
    if date_to:
        query = query.filter(SalesInvoice.invoice_date <= date_to)

    invoices = query.all()
    if not invoices:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فاکتورِ بازی با این شرایط پیدا نشد")

    now = datetime.now(timezone.utc)
    for inv in invoices:
        inv.closed_at = now
        inv.closed_by_id = user.id
    db.flush()
    return {
        "count": len(invoices),
        "first_date": min(i.invoice_date for i in invoices),
        "last_date": max(i.invoice_date for i in invoices),
        "total": sum((Decimal(i.total_amount) for i in invoices), Decimal(0)),
    }


def assert_invoice_open(db: Session, invoice_id: UUID) -> SalesInvoice:
    """گاردِ مشترک: فاکتورِ بسته ویرایش و ابطال نمی‌شود."""
    inv = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id).first()
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور پیدا نشد")
    if inv.closed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "فاکتورِ بسته‌شده تغییر نمی‌کند")
    return inv


# ─────────────────────── ۳) محاسبه و ذخیره‌ی پورسانت ──────────────────────


def preview_commission(db: Session, date_from: date_, date_to: date_) -> dict:
    """پورسانتِ هر فروشنده در بازه — بدونِ ذخیره.

    فاکتورِ باطل حساب نمی‌شود؛ فاکتورِ بی‌فروشنده هم همین‌طور (پورسانت‌بگیری ندارد).
    """
    if date_from > date_to:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تاریخِ شروع بعد از پایان است")

    rules = {r.salesperson_id: r for r in db.query(CommissionRule).filter(CommissionRule.is_active.is_(True))}
    if not rules:
        return {"date_from": date_from, "date_to": date_to, "total_amount": Decimal(0), "rows": []}

    agg = (
        db.query(
            SalesInvoice.salesperson_id,
            func.count(SalesInvoice.id),
            func.coalesce(func.sum(SalesInvoice.total_amount), 0),
            func.coalesce(func.sum(SalesInvoice.total_amount - SalesInvoice.total_cost), 0),
        )
        .filter(
            SalesInvoice.voided_at.is_(None),
            SalesInvoice.salesperson_id.isnot(None),
            SalesInvoice.invoice_date >= date_from,
            SalesInvoice.invoice_date <= date_to,
        )
        .group_by(SalesInvoice.salesperson_id)
        .all()
    )

    names = {u.id: u.name or u.email for u in db.query(User).all()}
    rows = []
    for person_id, count, net, profit in agg:
        rule = rules.get(person_id)
        if rule is None:
            continue  # فروشنده‌ای که قاعده‌ی پورسانت ندارد
        base = Decimal(profit if rule.basis == "profit" else net)
        # سودِ منفی پورسانتِ منفی نمی‌سازد؛ صفر می‌شود.
        base = max(base, Decimal(0))
        amount = (base * Decimal(rule.rate) / 100).quantize(Decimal(1))
        rows.append(
            {
                "salesperson_id": person_id,
                "salesperson_name": names.get(person_id, "—"),
                "invoice_count": int(count),
                "base_amount": base,
                "rate": Decimal(rule.rate),
                "basis": rule.basis,
                "amount": amount,
            }
        )
    rows.sort(key=lambda r: -r["amount"])
    return {
        "date_from": date_from,
        "date_to": date_to,
        "total_amount": sum((r["amount"] for r in rows), Decimal(0)),
        "rows": rows,
    }


def run_commission(db: Session, user: User, date_from: date_, date_to: date_, note: str = "") -> CommissionRun:
    """همان محاسبه، ولی ذخیره‌شده.

    چرا ذخیره و نه محاسبه‌ی هر بار: پورسانت مبنای پرداخت است. اگر زنده محاسبه شود،
    ابطالِ یک فاکتورِ قدیمی عددی را که ماهِ پیش پرداخت شده بی‌خبر عوض می‌کند و دیگر
    معلوم نیست چه چیزی پرداخت شده بود.
    """
    preview = preview_commission(db, date_from, date_to)
    if not preview["rows"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "در این بازه پورسانتی محاسبه نشد")

    run = CommissionRun(
        date_from=date_from,
        date_to=date_to,
        total_amount=preview["total_amount"],
        note=note,
        created_by_id=user.id,
        lines=[
            CommissionRunLine(
                salesperson_id=r["salesperson_id"],
                invoice_count=r["invoice_count"],
                base_amount=r["base_amount"],
                rate=r["rate"],
                basis=r["basis"],
                amount=r["amount"],
            )
            for r in preview["rows"]
        ],
    )
    db.add(run)
    db.flush()
    db.refresh(run)
    return run


# ─────────────────── ۴) اعلامیه‌ی بدهکار/بستانکار (سنددار) ────────────────


def post_note(
    db: Session,
    user: User,
    *,
    kind: str,
    note_date: date_,
    contact_id: UUID,
    amount: Decimal,
    reason: str = "",
    invoice_id: UUID | None = None,
) -> CreditDebitNote:
    """اعلامیه را ثبت و سندش را می‌زند.

    اعلامیه چیزی جز یک تعدیلِ واقعیِ مانده نیست؛ اگر در دفتر ننشیند، صورت‌حسابِ طرف
    مقابل با دفتر نمی‌خواند و همان اختلافی می‌شود که کسی بعداً باید دستی توضیحش دهد.

    * **بدهکار** — طرف به ما بدهکارتر می‌شود: بدهکارِ دریافتنی / بستانکارِ درآمد.
    * **بستانکار** — طلبِ ما کم می‌شود: بدهکارِ درآمد / بستانکارِ دریافتنی.
    """
    if kind not in ("debit", "credit"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوعِ اعلامیه نامعتبر است")
    amount = Decimal(amount)
    if amount <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مبلغِ اعلامیه باید بزرگ‌تر از صفر باشد")
    assert_period_open(db, note_date)

    receivable = get_account(db, cc.ACCOUNTS_RECEIVABLE)
    revenue = get_account(db, cc.SALES_REVENUE)
    label = "بدهکار" if kind == "debit" else "بستانکار"
    text = f"اعلامیه‌ی {label}" + (f" — {reason}" if reason else "")

    if kind == "debit":
        lines = [
            JournalLine(account_id=receivable.id, debit=amount, credit=0, description=text),
            JournalLine(account_id=revenue.id, debit=0, credit=amount, description=text),
        ]
    else:
        lines = [
            JournalLine(account_id=revenue.id, debit=amount, credit=0, description=text),
            JournalLine(account_id=receivable.id, debit=0, credit=amount, description=text),
        ]

    entry = make_journal_entry(db, note_date, text, "credit_debit_note", user, lines)
    note = CreditDebitNote(
        number=next_document_number(db, DOC_CREDIT_DEBIT_NOTE),
        kind=kind,
        note_date=note_date,
        contact_id=contact_id,
        amount=amount,
        reason=reason,
        invoice_id=invoice_id,
        journal_entry_id=entry.id,
        created_by_id=user.id,
    )
    db.add(note)
    db.flush()
    db.refresh(note)
    return note


def void_note(db: Session, user: User, note_id: UUID, reason: str) -> CreditDebitNote:
    """ابطالِ اعلامیه با سندِ معکوس — اصل سرِ جایش می‌ماند."""
    note = db.query(CreditDebitNote).filter(CreditDebitNote.id == note_id).first()
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اعلامیه پیدا نشد")
    if note.voided_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این اعلامیه قبلاً باطل شده")
    assert_period_open(db, date_.today())

    receivable = get_account(db, cc.ACCOUNTS_RECEIVABLE)
    revenue = get_account(db, cc.SALES_REVENUE)
    amount = Decimal(note.amount)
    text = f"ابطالِ اعلامیه‌ی شماره {note.number} — {reason}"
    # معکوسِ دقیقِ همان چیزی که ثبت شده بود.
    if note.kind == "debit":
        lines = [
            JournalLine(account_id=revenue.id, debit=amount, credit=0, description=text),
            JournalLine(account_id=receivable.id, debit=0, credit=amount, description=text),
        ]
    else:
        lines = [
            JournalLine(account_id=receivable.id, debit=amount, credit=0, description=text),
            JournalLine(account_id=revenue.id, debit=0, credit=amount, description=text),
        ]
    make_journal_entry(db, date_.today(), text, "credit_debit_note", user, lines)
    note.voided_at = datetime.now(timezone.utc)
    db.flush()
    return note
