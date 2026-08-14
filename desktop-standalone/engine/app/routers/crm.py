from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.crm import CrmActivity, Lead, LoyaltyReward, LoyaltyTier, LoyaltyTransaction
from app.models.user import User
from app.schemas.crm import (
    ActivityIn,
    ActivityOut,
    ActivityUpdateIn,
    BirthdayOut,
    ContactTierOut,
    ConvertLeadOut,
    LeadIn,
    LeadOut,
    LeadUpdateIn,
    LoyaltyBalanceOut,
    LoyaltySettingsIn,
    LoyaltySettingsOut,
    LoyaltyTxnIn,
    LoyaltyTxnOut,
    RedeemIn,
    RewardIn,
    RewardOut,
    RfmOut,
    TierIn,
    TierMemberOut,
    TierOut,
)
from app.services import crm as service

router = APIRouter(prefix="/api/crm", tags=["crm"])


# ── سرنخ‌ها ─────────────────────────────────────────────
@router.get("/leads", response_model=list[LeadOut])
def list_leads(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "view")),
):
    q = db.query(Lead)
    if status_filter:
        q = q.filter(Lead.status == status_filter)
    return q.order_by(Lead.created_at.desc()).all()


@router.post("/leads", response_model=LeadOut, status_code=201)
def create_lead(
    data: LeadIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("crm", "create")),
):
    lead = Lead(**data.model_dump(), created_by_id=user.id)
    db.add(lead)
    db.flush()
    db.refresh(lead)
    return lead


@router.patch("/leads/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: UUID,
    data: LeadUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "update")),
):
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سرنخ یافت نشد")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(lead, key, value)
    db.flush()
    db.refresh(lead)
    return lead


@router.delete("/leads/{lead_id}", status_code=204)
def delete_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "delete")),
):
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سرنخ یافت نشد")
    db.delete(lead)


@router.post("/leads/{lead_id}/convert", response_model=ConvertLeadOut)
def convert_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("crm", "update")),
):
    contact = service.convert_lead_to_contact(db, lead_id, user)
    return ConvertLeadOut(contact_id=contact.id)


# ── فعالیت/پیگیری ───────────────────────────────────────
@router.get("/activities", response_model=list[ActivityOut])
def list_activities(
    lead_id: UUID | None = Query(None),
    contact_id: UUID | None = Query(None),
    done: bool | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "view")),
):
    q = db.query(CrmActivity)
    if lead_id:
        q = q.filter(CrmActivity.lead_id == lead_id)
    if contact_id:
        q = q.filter(CrmActivity.contact_id == contact_id)
    if done is not None:
        q = q.filter(CrmActivity.done == done)
    return q.order_by(CrmActivity.activity_date.desc()).all()


@router.post("/activities", response_model=ActivityOut, status_code=201)
def create_activity(
    data: ActivityIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("crm", "create")),
):
    if data.lead_id is None and data.contact_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فعالیت باید به یک سرنخ یا مشتری وصل باشد")
    activity = CrmActivity(**data.model_dump(), created_by_id=user.id)
    db.add(activity)
    db.flush()
    db.refresh(activity)
    return activity


@router.patch("/activities/{activity_id}", response_model=ActivityOut)
def update_activity(
    activity_id: UUID,
    data: ActivityUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "update")),
):
    activity = db.get(CrmActivity, activity_id)
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فعالیت یافت نشد")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(activity, key, value)
    db.flush()
    db.refresh(activity)
    return activity


@router.delete("/activities/{activity_id}", status_code=204)
def delete_activity(
    activity_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "delete")),
):
    activity = db.get(CrmActivity, activity_id)
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فعالیت یافت نشد")
    db.delete(activity)


# ── امتیازِ وفاداری (باشگاه مشتریان) ───────────────────
@router.get("/loyalty", response_model=list[LoyaltyBalanceOut])
def loyalty_balances(
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "view")),
):
    return service.loyalty_balances(db)


@router.get("/loyalty/transactions", response_model=list[LoyaltyTxnOut])
def loyalty_transactions(
    contact_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "view")),
):
    q = db.query(LoyaltyTransaction)
    if contact_id:
        q = q.filter(LoyaltyTransaction.contact_id == contact_id)
    return q.order_by(LoyaltyTransaction.txn_date.desc()).all()


@router.post("/loyalty/transactions", response_model=LoyaltyTxnOut, status_code=201)
def add_loyalty_txn(
    data: LoyaltyTxnIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("crm", "create")),
):
    txn = LoyaltyTransaction(**data.model_dump(), created_by_id=user.id)
    db.add(txn)
    db.flush()
    db.refresh(txn)
    return txn


@router.get("/loyalty/settings", response_model=LoyaltySettingsOut)
def get_loyalty_settings(
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "view")),
):
    s = service.get_loyalty_settings(db)
    if s is None:
        from decimal import Decimal

        return LoyaltySettingsOut(is_enabled=False, amount_per_point=Decimal(0))
    return s


@router.put("/loyalty/settings", response_model=LoyaltySettingsOut)
def set_loyalty_settings(
    data: LoyaltySettingsIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "update")),
):
    return service.set_loyalty_settings(
        db,
        data.is_enabled,
        data.amount_per_point,
        tier_basis=data.tier_basis,
        tier_discount_auto=data.tier_discount_auto,
        birthday_gift_points=data.birthday_gift_points,
    )


# ── بخش‌بندیِ مشتریان (RFM) ─────────────────────────────
@router.get("/segments", response_model=RfmOut)
def customer_segments(
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "view")),
):
    return service.rfm_segments(db)


# ── سطوحِ باشگاه ────────────────────────────────────────
@router.get("/loyalty/tiers", response_model=list[TierOut])
def list_tiers(
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "view")),
):
    return db.query(LoyaltyTier).order_by(LoyaltyTier.threshold.asc()).all()


@router.post("/loyalty/tiers", response_model=TierOut, status_code=201)
def create_tier(
    data: TierIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "create")),
):
    tier = LoyaltyTier(**data.model_dump())
    db.add(tier)
    db.flush()
    db.refresh(tier)
    return tier


@router.put("/loyalty/tiers/{tier_id}", response_model=TierOut)
def update_tier(
    tier_id: UUID,
    data: TierIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "update")),
):
    tier = db.get(LoyaltyTier, tier_id)
    if tier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سطح یافت نشد")
    for key, value in data.model_dump().items():
        setattr(tier, key, value)
    db.flush()
    db.refresh(tier)
    return tier


@router.delete("/loyalty/tiers/{tier_id}", status_code=204)
def delete_tier(
    tier_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "delete")),
):
    tier = db.get(LoyaltyTier, tier_id)
    if tier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سطح یافت نشد")
    db.delete(tier)


@router.get("/loyalty/tier-members", response_model=list[TierMemberOut])
def tier_members(
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "view")),
):
    return service.tier_members(db)


@router.get("/loyalty/tier/{contact_id}", response_model=ContactTierOut)
def contact_tier(
    contact_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "view")),
):
    return service.customer_tier(db, contact_id)


# ── کاتالوگِ جوایز و بازخرید ──────────────────────────
@router.get("/loyalty/rewards", response_model=list[RewardOut])
def list_rewards(
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "view")),
):
    return db.query(LoyaltyReward).order_by(LoyaltyReward.points_cost.asc()).all()


@router.post("/loyalty/rewards", response_model=RewardOut, status_code=201)
def create_reward(
    data: RewardIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "create")),
):
    reward = LoyaltyReward(**data.model_dump())
    db.add(reward)
    db.flush()
    db.refresh(reward)
    return reward


@router.put("/loyalty/rewards/{reward_id}", response_model=RewardOut)
def update_reward(
    reward_id: UUID,
    data: RewardIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "update")),
):
    reward = db.get(LoyaltyReward, reward_id)
    if reward is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "جایزه یافت نشد")
    for key, value in data.model_dump().items():
        setattr(reward, key, value)
    db.flush()
    db.refresh(reward)
    return reward


@router.delete("/loyalty/rewards/{reward_id}", status_code=204)
def delete_reward(
    reward_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "delete")),
):
    reward = db.get(LoyaltyReward, reward_id)
    if reward is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "جایزه یافت نشد")
    db.delete(reward)


@router.post("/loyalty/redeem", response_model=LoyaltyTxnOut, status_code=201)
def redeem_reward(
    data: RedeemIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("crm", "create")),
):
    return service.redeem_reward(db, data.contact_id, data.reward_id, user, data.txn_date)


# ── تولدهای پیشِ‌رو ────────────────────────────────────
@router.get("/birthdays", response_model=list[BirthdayOut])
def birthdays(
    days: int = Query(30, ge=1, le=366),
    db: Session = Depends(get_db),
    _=Depends(require_permission("crm", "view")),
):
    return service.upcoming_birthdays(db, days)
