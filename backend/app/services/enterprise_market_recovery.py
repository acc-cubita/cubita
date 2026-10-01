"""Local repair of failed market posting; historical mappings stay immutable."""
from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.enterprise_market_bridge import EnterpriseMarketItemMap, EnterpriseMarketLocalPosting
from app.models.inventory import Item
from app.schemas.enterprise_market_bridge import MarketFinancialEvent


def repair_mapping(db: Session, tenant_id: UUID, actor_id: UUID, row: EnterpriseMarketLocalPosting,
                   market_item_ref: UUID | None, local_item_id: UUID) -> dict:
    if row.status == "posted" or market_item_ref is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "رویداد ثبت‌شده قابل تغییر نیست؛ شناسهٔ کالای رویداد ناموفق را انتخاب کنید")
    event = MarketFinancialEvent.model_validate(row.payload)
    if market_item_ref not in {line.market_item_ref for line in event.lines}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "این شناسهٔ کالا در رویداد وجود ندارد")
    item = db.query(Item).filter(Item.id == local_item_id, Item.tenant_id == tenant_id, Item.is_active.is_(True)).first()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کالای فعال متعلق به این شرکت پیدا نشد")
    used = db.query(EnterpriseMarketLocalPosting.id).filter(
        EnterpriseMarketLocalPosting.tenant_id == tenant_id,
        EnterpriseMarketLocalPosting.status == "posted",
        EnterpriseMarketLocalPosting.payload["lines"].contains([{"market_item_ref": str(market_item_ref)}]),
    ).first()
    if used is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این نگاشت در فاکتور ثبت‌شده استفاده شده است؛ برای حفظ مرجوعی آن را تغییر ندهید")
    mapping = db.query(EnterpriseMarketItemMap).filter(
        EnterpriseMarketItemMap.tenant_id == tenant_id,
        EnterpriseMarketItemMap.market_item_ref == market_item_ref,
    ).with_for_update().first()
    duplicate = db.query(EnterpriseMarketItemMap.id).filter(
        EnterpriseMarketItemMap.tenant_id == tenant_id,
        EnterpriseMarketItemMap.local_item_id == item.id,
        EnterpriseMarketItemMap.market_item_ref != market_item_ref,
    ).first()
    if duplicate:
        raise HTTPException(status.HTTP_409_CONFLICT, "این کالا به شناسهٔ دیگری نگاشت شده است؛ کالای دیگری انتخاب کنید")
    if mapping is None:
        mapping = EnterpriseMarketItemMap(tenant_id=tenant_id, market_item_ref=market_item_ref, local_item_id=item.id)
        db.add(mapping)
    mapping.local_item_id = item.id
    mapping.approved_by_id = actor_id
    mapping.approved_at = datetime.now(timezone.utc)
    db.flush()
    return {"mapped": True}
