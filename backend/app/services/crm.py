"""منطقِ باشگاه مشتریان/CRM — تبدیلِ سرنخ به مشتری، مانده‌ی امتیاز و کسبِ خودکارِ امتیاز."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.crm import Lead, LoyaltySettings, LoyaltyTransaction
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


def set_loyalty_settings(db: Session, is_enabled: bool, amount_per_point: Decimal) -> LoyaltySettings:
    s = db.query(LoyaltySettings).first()
    if s is None:
        s = LoyaltySettings(is_enabled=is_enabled, amount_per_point=amount_per_point)
        db.add(s)
    else:
        s.is_enabled = is_enabled
        s.amount_per_point = amount_per_point
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
