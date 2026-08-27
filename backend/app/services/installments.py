"""فروشِ اقساطی — قرارداد، زمان‌بندیِ وصول، و پرداخت.

سه قاعده‌ای که این ماژول را از یک «جدولِ سررسید» جدا می‌کند:

1. **قرارداد بدهی نمی‌سازد.** بدهی از فاکتورِ فروشِ نسیه می‌آید؛ قرارداد فقط
   زمان‌بندیِ وصولِ همان بدهی است و هر پرداخت یک دریافتِ خزانه‌ی واقعی می‌سازد.
   پس حسابداری هرگز دوباره‌کاری نمی‌شود و ماندهٔ دریافتنی همیشه مرجع است.
2. **وضعیت و جریمه محاسبه می‌شوند، ذخیره نمی‌شوند.** «معوق» و «جریمه‌ی دیرکرد»
   تابعِ تاریخِ امروزند؛ ذخیره‌شان یعنی نیاز به زمان‌بندِ پس‌زمینه و عددِ کهنه.
3. **جمعِ اقساط همیشه برابرِ مبلغِ تسهیم‌شده است.** هر تغییرِ زمان‌بندی این تساوی را
   دوباره می‌سنجد، وگرنه قرارداد بی‌صدا از فاکتورش واگرا می‌شود.
"""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.jalali import add_jalali_months
from app.models.counters import DOC_INSTALLMENT_PLAN
from app.models.installments import Installment, InstallmentPayment, InstallmentPlan
from app.models.inventory import Contact
from app.models.user import User
from app.schemas.installments import InstallmentPayIn, InstallmentPlanIn, RescheduleIn
from app.schemas.treasury import TreasuryTransactionIn
from app.services import treasury as treasury_service
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open
from app.services.reports import contact_balance

#: سطل‌های سنّیِ معوق (روز) — همان تقسیم‌بندیِ گزارشِ سنیِ مطالبات، تا دو گزارش یک زبان بگویند.
AGING_BUCKETS = (
    ("upcoming", "سررسیدنشده", None, 0),
    ("d1_30", "۱ تا ۳۰ روز", 1, 30),
    ("d31_60", "۳۱ تا ۶۰ روز", 31, 60),
    ("d61_90", "۶۱ تا ۹۰ روز", 61, 90),
    ("over_90", "بیش از ۹۰ روز", 91, None),
)


def _installment_status(inst: Installment, today: date) -> str:
    paid = Decimal(inst.paid_amount)
    amount = Decimal(inst.amount)
    if paid >= amount:
        return "paid"
    if paid > 0:
        return "partial"
    if inst.due_date < today:
        return "overdue"
    return "pending"


def _penalty(remaining: Decimal, days_late: int, rate: Decimal) -> Decimal:
    """جریمه = مانده × نرخِ ماهانه × ماه‌های تأخیر (کسرِ ماه هم نسبی حساب می‌شود).

    نسبی‌بودن عمدی است: پنج روز تأخیر نباید جریمه‌ی یک ماهِ کامل بگیرد، و پرشِ
    پله‌ایِ جریمه سرِ روزِ سی‌ویکم برای مشتری غیرقابلِ توضیح است.
    """
    if rate <= 0 or days_late <= 0 or remaining <= 0:
        return Decimal(0)
    months = Decimal(days_late) / Decimal(30)
    return (remaining * rate / Decimal(100) * months).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def _pct(part: Decimal, whole: Decimal) -> Decimal:
    if whole <= 0:
        return Decimal(0)
    return (part / whole * Decimal(100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _serialize(plan: InstallmentPlan) -> dict:
    today = date.today()
    rate = Decimal(plan.penalty_rate or 0)
    total_paid = Decimal(0)
    overdue_amount = Decimal(0)
    overdue_count = 0
    penalty_total = Decimal(0)
    worst_days_late = 0
    next_due: date | None = None
    next_due_amount = Decimal(0)
    lines = []
    for inst in plan.installments:
        paid = Decimal(inst.paid_amount)
        amount = Decimal(inst.amount)
        remaining = amount - paid
        st = _installment_status(inst, today)
        days_late = (today - inst.due_date).days if (st in ("overdue", "partial") and inst.due_date < today) else 0
        penalty = _penalty(remaining, days_late, rate)
        total_paid += paid
        penalty_total += penalty
        worst_days_late = max(worst_days_late, days_late)
        if remaining > 0 and next_due is None:
            next_due, next_due_amount = inst.due_date, remaining
        if st == "overdue":
            overdue_amount += remaining
            overdue_count += 1
        lines.append(
            {
                "id": inst.id,
                "seq": inst.seq,
                "due_date": inst.due_date,
                "amount": amount,
                "paid_amount": paid,
                "remaining": remaining,
                "paid_date": inst.paid_date,
                "status": st,
                "days_late": days_late,
                "penalty": penalty,
            }
        )

    seq_of = {i.id: i.seq for i in plan.installments}
    payments = [
        {
            "id": p.id,
            "installment_id": p.installment_id,
            "installment_seq": seq_of.get(p.installment_id, 0),
            "amount": Decimal(p.amount),
            "paid_on": p.paid_on,
            "method": p.method,
            "treasury_transaction_id": p.treasury_transaction_id,
            "notes": p.notes,
        }
        for p in sorted(plan.payments, key=lambda x: (x.paid_on, seq_of.get(x.installment_id, 0)))
    ]

    total = Decimal(plan.total_amount)
    cash = Decimal(plan.cash_price or 0) or total
    profit = Decimal(plan.profit_amount or 0)
    financed = total - Decimal(plan.down_payment)
    scheduled = sum((Decimal(i.amount) for i in plan.installments), Decimal(0))
    return {
        "id": plan.id,
        "number": plan.number,
        "contact_id": plan.contact_id,
        "contact_name": plan.contact.name if plan.contact else "—",
        "sales_invoice_id": plan.sales_invoice_id,
        "title": plan.title,
        "total_amount": total,
        "cash_price": cash,
        "profit_amount": profit,
        "profit_pct": _pct(profit, cash),
        "down_payment": Decimal(plan.down_payment),
        "financed": financed,
        "num_installments": plan.num_installments,
        "interval_months": plan.interval_months,
        "start_date": plan.start_date,
        "status": plan.status,
        "penalty_rate": rate,
        "guarantor_name": plan.guarantor_name or "",
        "guarantor_phone": plan.guarantor_phone or "",
        "guarantor_national_id": plan.guarantor_national_id or "",
        "notes": plan.notes,
        "installments": lines,
        "payments": payments,
        "total_paid": total_paid,
        "total_remaining": scheduled - total_paid,
        "next_due_date": next_due,
        "next_due_amount": next_due_amount,
        "overdue_amount": overdue_amount,
        "overdue_count": overdue_count,
        "penalty_total": penalty_total,
        "collected_pct": _pct(total_paid, scheduled),
        "worst_days_late": worst_days_late,
    }


def _plans_query(db: Session):
    return db.query(InstallmentPlan).options(
        selectinload(InstallmentPlan.installments),
        selectinload(InstallmentPlan.payments),
        selectinload(InstallmentPlan.contact),
    )


def list_plans(db: Session) -> list[dict]:
    plans = _plans_query(db).order_by(InstallmentPlan.created_at.desc()).all()
    return [_serialize(p) for p in plans]


def _load(db: Session, plan_id: UUID) -> InstallmentPlan:
    plan = _plans_query(db).filter(InstallmentPlan.id == plan_id).first()
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قرارداد اقساط یافت نشد")
    return plan


def get_plan(db: Session, plan_id: UUID) -> dict:
    return _serialize(_load(db, plan_id))


def create_plan(db: Session, data: InstallmentPlanIn, user: User) -> dict:
    contact = db.get(Contact, data.contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مشتری یافت نشد")

    financed = Decimal(data.total_amount) - Decimal(data.down_payment)

    # قرارداد فقط زمان‌بندیِ وصولِ یک بدهیِ موجود است (از فاکتورِ فروشِ نسیه). بدونِ
    # این محافظ می‌شد قراردادِ بی‌پشتوانه ساخت و با هر قسط، دریافتنیِ مشتری را منفی
    # کرد. پس مشتری باید دستِ‌کم به‌اندازهٔ مبلغِ اقساطی به ما بدهکار باشد.
    bal = contact_balance(db, data.contact_id)
    if bal < financed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"ماندهٔ دریافتنیِ این مشتری ({int(bal):,} تومان) کمتر از مبلغِ اقساطی "
            f"({int(financed):,} تومان) است؛ اول فاکتورِ فروشِ نسیه ثبت کنید.",
        )

    n = data.num_installments
    base = financed // n  # تومانِ کامل
    remainder = financed - base * n  # به آخرین قسط اضافه می‌شود

    plan = InstallmentPlan(
        number=next_document_number(db, DOC_INSTALLMENT_PLAN),
        contact_id=data.contact_id,
        sales_invoice_id=data.sales_invoice_id,
        title=data.title or "فروش اقساطی",
        total_amount=data.total_amount,
        cash_price=data.cash_price,
        profit_amount=data.profit_amount,
        down_payment=data.down_payment,
        num_installments=n,
        interval_months=data.interval_months,
        start_date=data.start_date,
        status="active",
        penalty_rate=data.penalty_rate,
        guarantor_name=data.guarantor_name.strip(),
        guarantor_phone=data.guarantor_phone.strip(),
        guarantor_national_id=data.guarantor_national_id.strip(),
        notes=data.notes,
        created_by_id=user.id,
    )
    for k in range(1, n + 1):
        amount = base + (remainder if k == n else Decimal(0))
        plan.installments.append(
            Installment(
                seq=k,
                due_date=add_jalali_months(data.start_date, (k - 1) * data.interval_months),
                amount=amount,
            )
        )
    db.add(plan)
    db.flush()
    db.refresh(plan)
    return _serialize(plan)


# ── وصول ─────────────────────────────────────────────────────────────────────


def _assert_payable(plan: InstallmentPlan) -> None:
    if plan.status != "active":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این قرارداد فعال نیست")


def _receive(db: Session, plan: InstallmentPlan, data: InstallmentPayIn, label: str, user: User):
    """یک دریافتِ خزانه‌ی واقعی می‌سازد و شیءِ تراکنش را برمی‌گرداند.

    محافظِ اضافه‌دریافت اینجاست چون هر مسیرِ وصول (تک‌قسط، تسهیمِ فیش، تسویه‌ی
    زودهنگام) از همین‌جا رد می‌شود؛ گذاشتنش در هر مسیر یعنی دیر یا زود یکی جا می‌ماند.
    """
    assert_period_open(db, data.transaction_date)
    bal = contact_balance(db, plan.contact_id)
    if Decimal(data.amount) > bal:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"این دریافت ({int(data.amount):,} تومان) بیش از ماندهٔ دریافتنیِ مشتری "
            f"({int(bal):,} تومان) است و آن را منفی می‌کند.",
        )
    return treasury_service.create_receipt(
        db,
        TreasuryTransactionIn(
            transaction_date=data.transaction_date,
            contact_id=plan.contact_id,
            amount=data.amount,
            method=data.method,
            bank_account_id=data.bank_account_id,
            description=label,
        ),
        user,
    )


def _apply(
    plan: InstallmentPlan,
    inst: Installment,
    amount: Decimal,
    data: InstallmentPayIn,
    txn_id: UUID | None,
    user: User,
) -> None:
    inst.paid_amount = Decimal(inst.paid_amount) + amount
    if Decimal(inst.paid_amount) >= Decimal(inst.amount):
        inst.paid_date = data.transaction_date
    plan.payments.append(
        InstallmentPayment(
            plan_id=plan.id,
            installment_id=inst.id,
            amount=amount,
            paid_on=data.transaction_date,
            method=data.method,
            treasury_transaction_id=txn_id,
            notes=data.notes,
            created_by_id=user.id,
        )
    )


def _close_if_settled(plan: InstallmentPlan) -> None:
    if all(Decimal(i.paid_amount) >= Decimal(i.amount) for i in plan.installments):
        plan.status = "completed"


def pay_installment(
    db: Session, plan_id: UUID, installment_id: UUID, data: InstallmentPayIn, user: User
) -> dict:
    plan = _load(db, plan_id)
    _assert_payable(plan)

    inst = next((i for i in plan.installments if i.id == installment_id), None)
    if inst is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قسط یافت نشد")

    remaining = Decimal(inst.amount) - Decimal(inst.paid_amount)
    if data.amount > remaining:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"مبلغ بیشتر از باقیمانده‌ی قسط ({remaining}) است"
        )

    name = plan.contact.name if plan.contact else ""
    txn = _receive(db, plan, data, f"قسط {inst.seq} قرارداد {plan.number} — {name}".strip(), user)
    _apply(plan, inst, Decimal(data.amount), data, getattr(txn, "id", None), user)
    _close_if_settled(plan)

    db.flush()
    db.refresh(plan)
    return _serialize(plan)


def settle_amount(db: Session, plan_id: UUID, data: InstallmentPayIn, user: User) -> dict:
    """یک فیش، چند قسط — تسهیم از قدیمی‌ترین قسطِ باز به بعد.

    مشتری معمولاً «۵ میلیون» می‌ریزد، نه «قسطِ شماره‌ی سه». تقسیمِ دستیِ آن بین
    قسط‌ها کارِ کاربر نیست و هر بار جای اشتباه‌کردن دارد.
    """
    plan = _load(db, plan_id)
    _assert_payable(plan)

    open_lines = [i for i in sorted(plan.installments, key=lambda x: x.seq) if Decimal(i.amount) > Decimal(i.paid_amount)]
    if not open_lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "قسطِ بازی برای تسهیم نمانده")

    outstanding = sum((Decimal(i.amount) - Decimal(i.paid_amount) for i in open_lines), Decimal(0))
    if Decimal(data.amount) > outstanding:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"مبلغ ({int(data.amount):,}) بیش از کلِ ماندهٔ اقساط ({int(outstanding):,}) است",
        )

    name = plan.contact.name if plan.contact else ""
    txn = _receive(db, plan, data, f"وصول اقساط قرارداد {plan.number} — {name}".strip(), user)
    txn_id = getattr(txn, "id", None)

    left = Decimal(data.amount)
    for inst in open_lines:
        if left <= 0:
            break
        share = min(left, Decimal(inst.amount) - Decimal(inst.paid_amount))
        _apply(plan, inst, share, data, txn_id, user)
        left -= share

    _close_if_settled(plan)
    db.flush()
    db.refresh(plan)
    return _serialize(plan)


def early_settlement_quote(db: Session, plan_id: UUID, discount: Decimal = Decimal(0)) -> dict:
    """مبلغِ لازم برای تسویه‌ی یک‌جا، با تخفیفِ اختیاری روی سودِ وصول‌نشده.

    سقفِ تخفیف عمداً «سودِ وصول‌نشده» است نه کلِ مانده: تخفیفِ بیشتر یعنی زیرِ قیمتِ
    نقدی فروختن، که دیگر تخفیفِ تعجیل نیست و باید سندِ خودش را داشته باشد.
    """
    plan = _load(db, plan_id)
    data = _serialize(plan)
    remaining = data["total_remaining"]
    profit = Decimal(plan.profit_amount or 0)
    # سهمِ وصول‌نشده‌ی سود، به نسبتِ ماندهٔ اقساط.
    scheduled = data["total_paid"] + remaining
    unearned = (profit * remaining / scheduled).quantize(Decimal(1), rounding=ROUND_HALF_UP) if scheduled > 0 else Decimal(0)
    if discount < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تخفیف نمی‌تواند منفی باشد")
    if discount > unearned:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"تخفیف نمی‌تواند از سودِ وصول‌نشده ({int(unearned):,}) بیشتر باشد",
        )
    return {
        "remaining": remaining,
        "unearned_profit": unearned,
        "discount": discount,
        "payable": remaining - discount,
    }


# ── زمان‌بندی ────────────────────────────────────────────────────────────────


def reschedule(db: Session, plan_id: UUID, data: RescheduleIn, user: User) -> dict:
    """ویرایشِ مبلغ/سررسیدِ اقساطِ باز — بدونِ دست‌زدن به جمعِ کل.

    دو گارد: قسطی که وصول شده کوچک‌تر از مبلغِ وصول‌شده‌اش نمی‌شود، و جمعِ اقساط
    باید همان مبلغِ تسهیم‌شده بماند. تنظیمِ مجددِ اقساط در عمل زیاد لازم می‌شود
    (تعویقِ یک قسط، تجمیعِ دو قسط) و بدونِ این دو گارد، قرارداد از فاکتورش واگرا می‌شود.
    """
    plan = _load(db, plan_id)
    _assert_payable(plan)

    by_id = {i.id: i for i in plan.installments}
    for line in data.lines:
        inst = by_id.get(line.installment_id)
        if inst is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "قسط یافت نشد")
        if line.amount < Decimal(inst.paid_amount):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"مبلغ قسط {inst.seq} نمی‌تواند کمتر از مبلغِ وصول‌شده‌اش ({int(inst.paid_amount):,}) باشد",
            )

    financed = Decimal(plan.total_amount) - Decimal(plan.down_payment)
    changed = {line.installment_id: line for line in data.lines}
    new_total = sum(
        (Decimal(changed[i.id].amount) if i.id in changed else Decimal(i.amount) for i in plan.installments),
        Decimal(0),
    )
    if new_total != financed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"جمعِ اقساط ({int(new_total):,}) باید برابرِ مبلغِ تسهیم‌شده ({int(financed):,}) باشد",
        )

    for line in data.lines:
        inst = by_id[line.installment_id]
        inst.amount = line.amount
        inst.due_date = line.due_date
        if Decimal(inst.paid_amount) < line.amount:
            inst.paid_date = None

    # ترتیبِ شماره‌ها باید با ترتیبِ سررسید بخواند، وگرنه «قسط بعدی» و تسهیمِ فیش
    # (که هر دو به ترتیبِ seq تکیه می‌کنند) عددِ اشتباه می‌دهند.
    for seq, inst in enumerate(sorted(plan.installments, key=lambda x: (x.due_date, x.seq)), start=1):
        inst.seq = seq

    _close_if_settled(plan)
    db.flush()
    db.refresh(plan)
    return _serialize(plan)


def cancel_plan(db: Session, plan_id: UUID) -> dict:
    plan = _load(db, plan_id)
    # پرداخت‌های انجام‌شده (دریافت‌های خزانه) سرِ جایشان می‌مانند؛ فقط قرارداد لغو می‌شود.
    plan.status = "cancelled"
    db.flush()
    db.refresh(plan)
    return _serialize(plan)


# ── نمای مدیریتی ─────────────────────────────────────────────────────────────


def get_summary(db: Session) -> dict:
    """سبدِ اقساط در یک نگاه: وصول، معوق به تفکیکِ سن، و بدهکارانِ بزرگ."""
    today = date.today()
    week_end = today + timedelta(days=7)
    month_end = today + timedelta(days=30)
    plans = [_serialize(p) for p in _plans_query(db).all()]
    active = [p for p in plans if p["status"] == "active"]

    buckets = {key: {"key": key, "label": label, "count": 0, "amount": Decimal(0)} for key, label, _, _ in AGING_BUCKETS}
    debtors: dict[UUID, dict] = {}
    financed = collected = remaining = overdue_amount = penalty_total = Decimal(0)
    overdue_count = 0
    due_week = due_month = Decimal(0)

    for plan in active:
        financed += plan["financed"]
        collected += plan["total_paid"]
        remaining += plan["total_remaining"]
        overdue_amount += plan["overdue_amount"]
        overdue_count += plan["overdue_count"]
        penalty_total += plan["penalty_total"]

        d = debtors.setdefault(
            plan["contact_id"],
            {
                "contact_id": plan["contact_id"],
                "contact_name": plan["contact_name"],
                "remaining": Decimal(0),
                "overdue": Decimal(0),
                "plans": 0,
            },
        )
        d["remaining"] += plan["total_remaining"]
        d["overdue"] += plan["overdue_amount"]
        d["plans"] += 1

        for inst in plan["installments"]:
            if inst["remaining"] <= 0:
                continue
            if inst["due_date"] <= week_end:
                due_week += inst["remaining"]
            if inst["due_date"] <= month_end:
                due_month += inst["remaining"]
            days = (today - inst["due_date"]).days
            for key, _label, lo, hi in AGING_BUCKETS:
                if lo is None:
                    hit = days <= 0
                elif hi is None:
                    hit = days >= lo
                else:
                    hit = lo <= days <= hi
                if hit:
                    buckets[key]["count"] += 1
                    buckets[key]["amount"] += inst["remaining"]
                    break

    top = sorted(debtors.values(), key=lambda r: r["remaining"], reverse=True)[:10]
    return {
        "active_plans": len(active),
        "total_financed": financed,
        "total_collected": collected,
        "total_remaining": remaining,
        "collected_pct": _pct(collected, collected + remaining),
        "overdue_amount": overdue_amount,
        "overdue_count": overdue_count,
        "penalty_total": penalty_total,
        "due_this_week": due_week,
        "due_this_month": due_month,
        "buckets": [buckets[key] for key, _l, _lo, _hi in AGING_BUCKETS],
        "top_debtors": top,
    }
