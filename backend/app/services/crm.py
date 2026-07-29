"""منطقِ باشگاه مشتریان/CRM — تبدیلِ سرنخ به مشتری و مانده‌ی امتیازِ وفاداری."""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.crm import Lead, LoyaltyTransaction
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
