"""منطقِ باشگاه مشتریان/CRM — سرنخ، امتیاز، و ابزارهای پیشرفته‌ی بازاریابی.

ابزارهای پیشرفته:
  - بخش‌بندیِ RFM (تازگی/تعداد/مبلغ) از رویِ فاکتورهای فروش.
  - سطوحِ باشگاه (تعیینِ سطحِ هر مشتری بر پایه‌ی امتیاز یا خریدِ سالانه).
  - بازخریدِ جایزه با امتیاز.
  - تولدهای پیشِ‌رو.
"""
import bisect
import math
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.crm import (
    Lead,
    LoyaltyReward,
    LoyaltySettings,
    LoyaltyTier,
    LoyaltyTransaction,
)
from app.models.invoices import SalesInvoice
from app.models.inventory import Contact
from app.models.user import User


def convert_lead_to_contact(db: Session, lead_id: UUID, user: User) -> Contact:
    """سرنخ را به یک «شخص» (مشتری) تبدیل می‌کند و از تبدیلِ دوباره جلوگیری می‌کند.

    وضعیتِ سرنخ به «won» می‌رود و به همان مشتریِ ساخته‌شده گره می‌خورد تا سابقه‌اش گم
    نشود.
    """
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سرنخ یافت نشد")
    if lead.converted_contact_id is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این سرنخ قبلاً به مشتری تبدیل شده است")

    phone = lead.phone.strip()[:20] if lead.phone and lead.phone.strip() else None
    contact = Contact(
        name=lead.name,
        type="customer",
        phone=phone,
        email=lead.email or None,
        address="",
    )
    db.add(contact)
    db.flush()

    lead.converted_contact_id = contact.id
    lead.status = "won"
    db.flush()
    return contact


def loyalty_balances(db: Session) -> list[dict]:
    """مانده‌ی امتیازِ هر مشتری = جمعِ تراکنش‌هایش (فقط مشتری‌هایی که تراکنش دارند)."""
    rows = (
        db.query(
            LoyaltyTransaction.contact_id,
            Contact.name.label("contact_name"),
            func.coalesce(func.sum(LoyaltyTransaction.points), 0).label("balance"),
        )
        .join(Contact, Contact.id == LoyaltyTransaction.contact_id)
        .group_by(LoyaltyTransaction.contact_id, Contact.name)
        .order_by(func.sum(LoyaltyTransaction.points).desc())
        .all()
    )
    return [
        {"contact_id": r.contact_id, "contact_name": r.contact_name, "balance": int(r.balance)}
        for r in rows
    ]


# ── تنظیماتِ کسبِ خودکارِ امتیاز ────────────────────────
def get_loyalty_settings(db: Session) -> LoyaltySettings | None:
    return db.query(LoyaltySettings).first()


def set_loyalty_settings(
    db: Session,
    is_enabled: bool,
    amount_per_point: Decimal,
    *,
    tier_basis: str = "points",
    tier_discount_auto: bool = False,
    birthday_gift_points: int = 0,
) -> LoyaltySettings:
    s = db.query(LoyaltySettings).first()
    if s is None:
        s = LoyaltySettings()
        db.add(s)
    s.is_enabled = is_enabled
    s.amount_per_point = amount_per_point
    s.tier_basis = tier_basis
    s.tier_discount_auto = tier_discount_auto
    s.birthday_gift_points = birthday_gift_points
    db.flush()
    return s


def award_purchase_points(db: Session, contact_id: UUID | None, amount: Decimal, txn_date: date, user: User) -> None:
    """اگر کسبِ خودکار فعال باشد، بابتِ این خرید امتیاز ثبت می‌کند.

    بی‌صدا برمی‌گردد اگر فروش مشتری ندارد، تنظیمات غیرفعال است یا نرخ صفر است — تا
    هوکِ داخلِ فاکتورِ فروش هرگز خودِ فروش را نشکند.
    """
    if contact_id is None:
        return
    settings = db.query(LoyaltySettings).first()
    if settings is None or not settings.is_enabled:
        return
    per = Decimal(settings.amount_per_point or 0)
    if per <= 0:
        return
    points = int(Decimal(amount) // per)
    if points <= 0:
        return
    db.add(
        LoyaltyTransaction(
            contact_id=contact_id,
            points=points,
            reason="کسبِ امتیاز بابتِ خرید",
            txn_date=txn_date,
            created_by_id=user.id,
        )
    )


# ── بخش‌بندیِ مشتریان (RFM) ─────────────────────────────
# امتیازِ ۱..۵ برای تازگی و تعداد، با آستانه‌های ثابتِ قابلِ‌فهم؛ «مبلغ» نسبی است
# (چارک‌بندیِ جامعه‌ی مشتریان) چون مقیاسِ ریالی از کسب‌وکاری به کسب‌وکارِ دیگر فرق دارد.
def _recency_score(days: int) -> int:
    if days <= 30:
        return 5
    if days <= 60:
        return 4
    if days <= 120:
        return 3
    if days <= 240:
        return 2
    return 1


def _frequency_score(count: int) -> int:
    if count >= 10:
        return 5
    if count >= 5:
        return 4
    if count >= 3:
        return 3
    if count >= 2:
        return 2
    return 1


def _quintile_score(value: float, sorted_vals: list[float]) -> int:
    """امتیازِ ۱..۵ بر اساسِ جای «مبلغ» در توزیعِ مشتریان (رتبه ÷ کل → پنجک)."""
    n = len(sorted_vals)
    if n == 0:
        return 1
    rank = bisect.bisect_right(sorted_vals, value)  # 1..n
    return min(5, max(1, math.ceil(rank / n * 5)))


def _segment(r: int, f: int, recency_days: int) -> str:
    """نگاشتِ امتیازها به یک بخشِ اقدام‌پذیر — ترتیبِ شرط‌ها مهم است."""
    if recency_days > 240:
        return "dormant"          # خفته / از‌دست‌رفته
    if r >= 4 and f >= 4:
        return "champion"         # قهرمانان
    if f >= 3 and r <= 2:
        return "at_risk"          # در معرضِ ریزش (پرتکرارِ سردشده)
    if f >= 3 and r >= 3:
        return "loyal"            # وفادار
    if f <= 1 and r >= 4:
        return "new"              # تازه‌وارد
    return "regular"              # عادی


def rfm_segments(db: Session, today: date | None = None) -> dict:
    """تحلیلِ RFM همه‌ی مشتریانِ دارای فاکتورِ فروش (باطل‌نشده) و دسته‌بندی‌شان."""
    today = today or date.today()
    rows = (
        db.query(
            SalesInvoice.contact_id.label("cid"),
            Contact.name.label("name"),
            func.count(SalesInvoice.id).label("freq"),
            func.max(SalesInvoice.invoice_date).label("last"),
            func.coalesce(func.sum(
                SalesInvoice.total_amount + SalesInvoice.tax_amount + SalesInvoice.total_additions
                + SalesInvoice.total_duties + SalesInvoice.rounding
            ), 0).label("monetary"),
        )
        .join(Contact, Contact.id == SalesInvoice.contact_id)
        .filter(SalesInvoice.contact_id.isnot(None))
        .filter(SalesInvoice.voided_at.is_(None))
        .group_by(SalesInvoice.contact_id, Contact.name)
        .all()
    )

    sorted_monetary = sorted(float(r.monetary) for r in rows)
    customers = []
    for r in rows:
        recency_days = (today - r.last).days if r.last else 9999
        freq = int(r.freq)
        monetary = float(r.monetary)
        r_s = _recency_score(recency_days)
        f_s = _frequency_score(freq)
        m_s = _quintile_score(monetary, sorted_monetary)
        customers.append(
            {
                "contact_id": r.cid,
                "contact_name": r.name,
                "recency_days": recency_days,
                "frequency": freq,
                "monetary": monetary,
                "last_purchase": r.last,
                "r": r_s,
                "f": f_s,
                "m": m_s,
                "segment": _segment(r_s, f_s, recency_days),
            }
        )
    # پرارزش‌ترین‌ها بالا
    customers.sort(key=lambda c: c["monetary"], reverse=True)

    summary: dict[str, dict] = {}
    for c in customers:
        s = summary.setdefault(c["segment"], {"segment": c["segment"], "count": 0, "monetary": 0.0})
        s["count"] += 1
        s["monetary"] += c["monetary"]

    return {
        "customers": customers,
        "summary": list(summary.values()),
        "total_customers": len(customers),
    }


# ── سطوحِ باشگاه ────────────────────────────────────────
def _annual_spend(db: Session, contact_id: UUID, today: date) -> Decimal:
    since = today - timedelta(days=365)
    total = (
        db.query(func.coalesce(func.sum(
            SalesInvoice.total_amount + SalesInvoice.tax_amount + SalesInvoice.total_additions
            + SalesInvoice.total_duties + SalesInvoice.rounding
        ), 0))
        .filter(SalesInvoice.contact_id == contact_id)
        .filter(SalesInvoice.voided_at.is_(None))
        .filter(SalesInvoice.invoice_date >= since)
        .scalar()
    )
    return Decimal(total or 0)


def _points_balance(db: Session, contact_id: UUID) -> int:
    total = (
        db.query(func.coalesce(func.sum(LoyaltyTransaction.points), 0))
        .filter(LoyaltyTransaction.contact_id == contact_id)
        .scalar()
    )
    return int(total or 0)


def tier_for_value(tiers_desc: list[LoyaltyTier], value: Decimal) -> LoyaltyTier | None:
    """بالاترین سطحی که آستانه‌اش را پوشانده (tiers از بزرگ به کوچک مرتب شده)."""
    for t in tiers_desc:
        if Decimal(value) >= Decimal(t.threshold):
            return t
    return None


def customer_tier(db: Session, contact_id: UUID, today: date | None = None) -> dict:
    """سطحِ فعلیِ یک مشتری + مقدارِ مبنا + درصدِ تخفیفِ سطح."""
    today = today or date.today()
    settings = db.query(LoyaltySettings).first()
    basis = settings.tier_basis if settings else "points"
    value = _points_balance(db, contact_id) if basis == "points" else _annual_spend(db, contact_id, today)
    tiers = db.query(LoyaltyTier).order_by(LoyaltyTier.threshold.desc()).all()
    tier = tier_for_value(tiers, Decimal(value))
    return {
        "basis": basis,
        "value": Decimal(value),
        "tier_id": tier.id if tier else None,
        "tier_name": tier.name if tier else None,
        "discount_percent": Decimal(tier.discount_percent) if tier else Decimal(0),
    }


def tier_members(db: Session, today: date | None = None) -> list[dict]:
    """همه‌ی مشتریان با مقدارِ مبنا و سطحِ فعلی‌شان — برای جدولِ «اعضای سطوح»."""
    today = today or date.today()
    settings = db.query(LoyaltySettings).first()
    basis = settings.tier_basis if settings else "points"
    tiers = db.query(LoyaltyTier).order_by(LoyaltyTier.threshold.desc()).all()

    if basis == "points":
        pairs = (
            db.query(
                LoyaltyTransaction.contact_id,
                Contact.name,
                func.coalesce(func.sum(LoyaltyTransaction.points), 0),
            )
            .join(Contact, Contact.id == LoyaltyTransaction.contact_id)
            .group_by(LoyaltyTransaction.contact_id, Contact.name)
            .all()
        )
    else:
        since = today - timedelta(days=365)
        pairs = (
            db.query(
                SalesInvoice.contact_id,
                Contact.name,
                func.coalesce(func.sum(
                    SalesInvoice.total_amount + SalesInvoice.tax_amount + SalesInvoice.total_additions
                    + SalesInvoice.total_duties + SalesInvoice.rounding
                ), 0),
            )
            .join(Contact, Contact.id == SalesInvoice.contact_id)
            .filter(SalesInvoice.contact_id.isnot(None))
            .filter(SalesInvoice.voided_at.is_(None))
            .filter(SalesInvoice.invoice_date >= since)
            .group_by(SalesInvoice.contact_id, Contact.name)
            .all()
        )

    out = []
    for cid, name, value in pairs:
        tier = tier_for_value(tiers, Decimal(value or 0))
        if tier is None:
            continue  # زیرِ پایین‌ترین سطح — عضوِ باشگاه محسوب نمی‌شود
        out.append(
            {
                "contact_id": cid,
                "contact_name": name,
                "value": Decimal(value or 0),
                "tier_id": tier.id,
                "tier_name": tier.name,
                "discount_percent": Decimal(tier.discount_percent),
            }
        )
    out.sort(key=lambda x: x["value"], reverse=True)
    return out


# ── بازخریدِ جایزه ─────────────────────────────────────
def redeem_reward(db: Session, contact_id: UUID, reward_id: UUID, user: User, txn_date: date | None = None) -> LoyaltyTransaction:
    """امتیازِ مشتری را در برابرِ یک جایزه خرج می‌کند (تراکنشِ منفیِ گره‌خورده به جایزه)."""
    reward = db.get(LoyaltyReward, reward_id)
    if reward is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "جایزه یافت نشد")
    if not reward.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این جایزه غیرفعال است")
    balance = _points_balance(db, contact_id)
    if balance < reward.points_cost:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"امتیازِ کافی نیست (مانده {balance}، لازم {reward.points_cost})",
        )
    txn = LoyaltyTransaction(
        contact_id=contact_id,
        points=-int(reward.points_cost),
        reason=f"بازخریدِ جایزه: {reward.name}",
        txn_date=txn_date or date.today(),
        reward_id=reward.id,
        created_by_id=user.id,
    )
    db.add(txn)
    db.flush()
    db.refresh(txn)
    return txn


# ── تولدهای پیشِ‌رو ────────────────────────────────────
def upcoming_birthdays(db: Session, days: int = 30, today: date | None = None) -> list[dict]:
    """مشتریانی که تولدشان تا `days` روزِ آینده است — مرتب بر اساسِ نزدیک‌ترین."""
    today = today or date.today()
    contacts = (
        db.query(Contact)
        .filter(Contact.birthday.isnot(None))
        .filter(Contact.type != "supplier")
        .all()
    )
    out = []
    for c in contacts:
        b = c.birthday
        # تولدِ امسال؛ اگر گذشته، سالِ بعد. (۲۹ اسفند/فوریه: به ۲۸ می‌افتد که همیشه هست.)
        month, day = b.month, min(b.day, 28) if (b.month == 2 and b.day == 29) else b.day
        try:
            nxt = date(today.year, month, day)
        except ValueError:
            nxt = date(today.year, month, 28)
        if nxt < today:
            nxt = date(today.year + 1, month, day)
        days_until = (nxt - today).days
        if days_until <= days:
            out.append(
                {
                    "contact_id": c.id,
                    "contact_name": c.name,
                    "birthday": b,
                    "next_birthday": nxt,
                    "days_until": days_until,
                    "turning_age": nxt.year - b.year,
                }
            )
    out.sort(key=lambda x: x["days_until"])
    return out
