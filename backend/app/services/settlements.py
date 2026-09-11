"""موتورِ تسویه‌ی حسابِ طرف مقابل.

**این سرویس سندِ حسابداری نمی‌زند — و این عمدی‌ترین تصمیمِ این فصل است (§۲۲ §۲۳).**
فاکتور دریافتنی را بدهکار کرده، رسید همان را بستانکار کرده، و ماندهٔ مشتری همین
حالا درست است. تسویه فقط می‌گوید آن دو گردش به هم مربوط‌اند. سندِ دوم چیزی را
درست‌تر نمی‌کند؛ فقط ۱۰۰ بدهکار و ۱۰۰ بستانکارِ خنثی به دفتر اضافه می‌کند و
گزارش‌های گردش را شلوغ‌تر می‌کند (§۲۴).

پس اثرِ تسویه جایی جز `settlement_allocations` دیده نمی‌شود، و همان‌جا کافی است:
«تسویه‌شده» و «مانده‌ی قابلِ تسویه»ی هر سند از همین ردیف‌ها مشتق می‌شوند
(`services/open_items.py`).

**نسبتش با `receipt_related_documents`.** سندِ رسید (مهاجرتِ ۰۱۱۱) جدولی دارد که
پیوندِ رسید به فاکتور را با یک `allocated_amount` نگه می‌دارد، و داکِ خودش صریح
می‌گوید موتورِ تسویه نیست و «منطقِ دقیقِ Allocation را فصلِ تسویه نهایی می‌کند».
همین‌جاست. آن جدول یک **پیوندِ ردگیری در لحظه‌ی ثبتِ رسید** است با یک گاردِ محلی
(جمعِ تخصیص از مبلغِ همان رسید بیشتر نشود)؛ منبعِ حقیقتِ «چقدرِ این فاکتور تسویه
شده» این‌جاست، نه آن‌جا. تا وقتی رقمِ آن جدول در هیچ مانده‌ای خوانده نمی‌شود،
دو نمای یک داده نیستند؛ اگر روزی قرار شد خوانده شود، باید از همین تخصیص‌ها مشتق
شود نه کنارشان.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import Account
from app.models.counters import DOC_SETTLEMENT
from app.models.inventory import Contact
from app.models.settlement import Settlement, SettlementAllocation
from app.models.user import User
from app.services import open_items as oi
from app.services.numbering import next_document_number
from app.services.printing import fa_number

#: ارزِ پایه‌ی دفتر. تخصیص همیشه با همین عدد انجام می‌شود، چون همان چیزی است که در
#: `journal_lines.debit/credit` نشسته.
BASE_CURRENCY = "IRR"


def _resolve_lines(db: Session, data, *, exclude_settlement_id: UUID | None = None) -> list[dict]:
    """هر قلمِ ورودی را به سندِ واقعی‌اش گره می‌زند و اعتبارش را می‌سنجد.

    سه چیز اینجا کنترل می‌شود که هیچ‌کدام در کلاینت قابلِ اعتماد نیستند: سمتِ
    واقعیِ سند (§۸)، مانده‌ی قابلِ تسویه (§۱۴)، و ارز (§۳۲).
    """
    account = oi.assert_counterparty_account(db, data.account_id)
    if db.get(Contact, data.contact_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "طرف حساب یافت نشد")

    own = oi._own_allocations(db, exclude_settlement_id) if exclude_settlement_id else {}
    seen: set[tuple[str, UUID]] = set()
    resolved: list[dict] = []

    for seq, line in enumerate(data.items, start=1):
        key = (line.source_type, line.source_id)
        if key in seen:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "یک سند دوبار در یک تسویه آمده است؛ مبلغش را در یک ردیف جمع کنید.",
            )
        seen.add(key)

        item = oi.resolve_item(
            db,
            account_id=account.id,
            contact_id=data.contact_id,
            source_type=line.source_type,
            source_id=line.source_id,
        )
        amount = Decimal(line.amount)
        if amount <= 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "مبلغِ تسویه باید بزرگ‌تر از صفر باشد")

        #: **سمت را سند تعیین می‌کند، نه کاربر.** اگر رسیدی در ستونِ بدهکار بنشیند،
        #: جمع‌ها ممکن است تراز شوند و تسویه‌ای ثبت شود که معنایش وارونه است.
        if line.side != item["side"]:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"«{item['label']}» اثرِ {'بدهکار' if item['side'] == 'debit' else 'بستانکار'}ِ "
                "این طرف حساب است و در ستونِ دیگر نمی‌نشیند.",
            )

        settled = oi.settled_amounts(db, [key]).get(key, Decimal(0)) - own.get(key, Decimal(0))
        remaining = item["document_amount"] - settled
        if amount > remaining:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"مبلغِ تسویه‌ی «{item['label']}» بیشتر از مانده‌ی قابلِ تسویه است. "
                f"مانده: {fa_number(remaining)} ریال، مبلغِ واردشده: {fa_number(amount)} ریال.",
            )

        item = {**item, "seq": seq, "amount": amount, "remaining_before": remaining}
        resolved.append(item)

    return resolved


def _assert_single_currency(lines: list[dict]) -> str:
    """تسویه‌ی چندارزی قاعده ندارد، پس فرض هم نمی‌شود (§۳۲).

    ردِ صریح بهتر از تخصیصِ خاموش با نرخی است که کسی تعیینش نکرده.
    """
    currencies = {line["currency_code"] or BASE_CURRENCY for line in lines}
    if len(currencies) > 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "اقلامِ این تسویه ارزهای متفاوت دارند. تسویه‌ی بینِ دو ارز قاعده‌ی مشخصی "
            "ندارد و خودکار انجام نمی‌شود؛ برای هر ارز یک تسویه‌ی جدا ثبت کنید.",
        )
    return currencies.pop() if currencies else BASE_CURRENCY


def _assert_balanced(lines: list[dict]) -> Decimal:
    """جمعِ بدهکار باید با جمعِ بستانکار برابر باشد (§۱۹).

    پیامِ خطا هر سه عدد را می‌گوید (§۲۱). «خطایی رخ داد» کاربر را با فرمی پر از
    ردیف تنها می‌گذارد تا خودش دنبالِ اختلاف بگردد.
    """
    debit = sum((line["amount"] for line in lines if line["side"] == "debit"), Decimal(0))
    credit = sum((line["amount"] for line in lines if line["side"] == "credit"), Decimal(0))
    if debit <= 0 or credit <= 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "تسویه به هر دو سمت نیاز دارد: دستِ‌کم یک قلمِ بدهکار و یک قلمِ بستانکار.",
        )
    if debit != credit:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "تسویه قابلِ ثبت نیست؛ دو سمت برابر نیستند.\n"
            f"جمعِ اقلامِ بدهکار: {fa_number(debit)} ریال\n"
            f"جمعِ اقلامِ بستانکار: {fa_number(credit)} ریال\n"
            f"اختلاف: {fa_number(abs(debit - credit))} ریال",
        )
    return debit


def create_settlement(db: Session, data, user: User) -> Settlement:
    lines = _resolve_lines(db, data)
    currency = _assert_single_currency(lines)
    total = _assert_balanced(lines)

    settlement = Settlement(
        number=next_document_number(db, DOC_SETTLEMENT),
        settlement_date=data.settlement_date,
        contact_id=data.contact_id,
        account_id=data.account_id,
        currency_code=currency,
        description=(data.description or "").strip(),
        description2=(data.description2 or "").strip(),
        total_amount=total,
        created_by_id=user.id,
        allocations=[
            SettlementAllocation(
                seq=line["seq"],
                side=line["side"],
                source_type=line["source_type"],
                source_id=line["source_id"],
                amount=line["amount"],
            )
            for line in lines
        ],
    )
    db.add(settlement)
    db.flush()
    return settlement


def void_settlement(db: Session, settlement_id: UUID, *, reason: str, user: User) -> Settlement:
    """برگشتِ تسویه — فقط رابطه آزاد می‌شود (§۳۷ §۳۸).

    نه فاکتوری حذف می‌شود نه رسیدی؛ تسویه مالکشان نیست. ردیف‌های تخصیص هم پاک
    نمی‌شوند: «چه چیزی آزاد شد و کِی» بخشی از سابقه است (§۴۹).
    """
    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تسویه یافت نشد")
    if settlement.is_voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "این تسویه قبلاً برگشت خورده است")

    settlement.voided_at = datetime.now(timezone.utc)
    settlement.voided_by_id = user.id
    settlement.void_reason = (reason or "").strip()
    db.flush()
    return settlement


def verify_totals(db: Session, settlement: Settlement) -> None:
    """عکسِ ذخیره‌شده‌ی جمع را مقابلِ ردیف‌ها می‌گذارد.

    `total_amount` برای خواندنِ سریعِ فهرست است نه منبعِ حقیقت؛ اگر روزی از ردیف‌ها
    جدا بیفتد باید دیده شود، نه اینکه بی‌صدا در فهرست بنشیند.
    """
    debit = (
        db.query(func.coalesce(func.sum(SettlementAllocation.amount), 0))
        .filter(
            SettlementAllocation.settlement_id == settlement.id,
            SettlementAllocation.side == "debit",
        )
        .scalar()
    )
    if Decimal(debit) != Decimal(settlement.total_amount):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"جمعِ تسویه‌ی شماره {settlement.number} با ردیف‌هایش نمی‌خواند",
        )


def get(db: Session, settlement_id: UUID) -> Settlement:
    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تسویه یافت نشد")
    return settlement


def row(db: Session, settlement: Settlement) -> dict:
    account = db.get(Account, settlement.account_id)
    return {
        "id": settlement.id,
        "number": settlement.number,
        "settlement_date": settlement.settlement_date,
        "contact_id": settlement.contact_id,
        "contact_name": oi.contact_name(db, settlement.contact_id),
        "account_id": settlement.account_id,
        "account_name": account.name if account is not None else "",
        "currency_code": settlement.currency_code,
        "description": settlement.description,
        "description2": settlement.description2,
        "total_amount": Decimal(settlement.total_amount),
        "item_count": len(settlement.allocations),
        "voided_at": settlement.voided_at,
        "void_reason": settlement.void_reason,
        "created_at": settlement.created_at,
    }


def open_items_summary(
    db: Session,
    *,
    account_id: UUID,
    contact_id: UUID | None = None,
    as_of=None,
    only_open: bool = True,
    exclude_settlement_id: UUID | None = None,
) -> dict:
    """اقلامِ باز به‌علاوه‌ی جمع‌ها (§۴۵).

    `net` باید با ماندهٔ همان معین در دفتر بخواند؛ برای همین با `only_open=False`
    حساب می‌شود حتی وقتی فهرست فیلتر شده — وگرنه عددِ خلاصه با گزارشِ مانده
    اختلاف پیدا می‌کرد و این دقیقاً همان دو‌نماییِ ممنوع است.
    """
    account = oi.assert_counterparty_account(db, account_id)
    everything = oi.open_items(
        db,
        account_id=account_id,
        contact_id=contact_id,
        as_of=as_of,
        only_open=False,
        exclude_settlement_id=exclude_settlement_id,
    )
    debit_total = sum((i["document_amount"] for i in everything if i["side"] == "debit"), Decimal(0))
    credit_total = sum((i["document_amount"] for i in everything if i["side"] == "credit"), Decimal(0))
    open_debit = sum(
        (i["remaining_amount"] for i in everything if i["side"] == "debit" and i["remaining_amount"] > 0),
        Decimal(0),
    )
    open_credit = sum(
        (i["remaining_amount"] for i in everything if i["side"] == "credit" and i["remaining_amount"] > 0),
        Decimal(0),
    )
    items = [i for i in everything if not only_open or i["remaining_amount"] > 0]
    #: گردشی که سندِ قابلِ تسویه‌ای پشتش نیست — سندِ دستی، ماندهٔ اول دوره، و چکِ
    #: پیش از ۰۱۱۰. **همیشه در سطحِ کلِ معین** حساب می‌شود حتی وقتی یک طرف حساب
    #: انتخاب شده، چون ردیفِ دفترِ بی‌سند به هیچ طرف حسابی قابلِ نسبت‌دادن نیست —
    #: و همین دلیلِ وجودش است.
    residual = oi.unattributed(db, account_id, as_of)
    return {
        "account_id": account.id,
        "account_name": account.name,
        "account_ledger_net": oi.ledger_balance(db, account_id, as_of),
        "unattributed": residual,
        "contact_id": contact_id,
        "contact_name": oi.contact_name(db, contact_id) if contact_id else "",
        "debit_total": debit_total,
        "credit_total": credit_total,
        "net": debit_total - credit_total,
        "open_debit": open_debit,
        "open_credit": open_credit,
        "items": [{**item, "status_label": oi.STATUS_LABELS[item["status"]]} for item in items],
    }


def settlements_query(db: Session):
    return db.query(Settlement).order_by(Settlement.settlement_date.desc(), Settlement.number.desc())


def describe_allocations(db: Session, settlement: Settlement) -> list[dict]:
    """ردیف‌های یک تسویه با اطلاعاتِ زنده‌ی سندِ منبع.

    مبلغ و تاریخ و شماره از خودِ سند خوانده می‌شوند نه از کپیِ لحظه‌ی ثبت — پس اگر
    سندِ منبع بعداً تغییر کرده باشد، همان‌جا دیده می‌شود (§۳۹).
    """
    live = {
        (item["source_type"], item["source_id"]): item
        for item in oi.open_items(
            db,
            account_id=settlement.account_id,
            contact_id=settlement.contact_id,
            only_open=False,
        )
    }
    rows = []
    for allocation in settlement.allocations:
        key = (allocation.source_type, allocation.source_id)
        item = live.get(key)
        kind = oi.SETTLEABLE.get(allocation.source_type)
        rows.append(
            {
                "side": allocation.side,
                "source_type": allocation.source_type,
                "source_id": allocation.source_id,
                "label": kind.label if kind else allocation.source_type,
                "amount": Decimal(allocation.amount),
                "number": item["number"] if item else None,
                "entry_number": item["entry_number"] if item else None,
                "document_date": item["document_date"] if item else None,
                "document_amount": item["document_amount"] if item else None,
                "settled_amount": item["settled_amount"] if item else None,
                "remaining_amount": item["remaining_amount"] if item else None,
                "status": item["status"] if item else None,
                #: سندِ منبع دیگر روی این معین گردشی ندارد — باطل یا ویرایش شده.
                "source_missing": item is None,
            }
        )
    return rows
