"""Cloud-side durable event delivery and receipt reconciliation."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enterprise_market_bridge import EnterpriseMarketEvent
from app.models.marketplace import MarketplaceOrder, MarketplaceReturn
from app.schemas.enterprise_market_bridge import MarketPostingReceipt


def pending_for_link(db: Session, link_id: UUID) -> list[EnterpriseMarketEvent]:
    return db.query(EnterpriseMarketEvent).filter(
        EnterpriseMarketEvent.link_id == link_id,
        EnterpriseMarketEvent.status.in_(("pending", "retryable_error", "blocked")),
    ).order_by(EnterpriseMarketEvent.created_at, EnterpriseMarketEvent.id).limit(50).all()


def record_receipt(
    db: Session, link_id: UUID, event_id: UUID, receipt: MarketPostingReceipt,
) -> dict:
    initial = db.query(EnterpriseMarketEvent).filter(
        EnterpriseMarketEvent.id == event_id,
        EnterpriseMarketEvent.link_id == link_id,
    ).first()
    if initial is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "رویداد بازار پیدا نشد")
    # Every side of an order takes the same order lock first. Locking the two
    # event rows independently can otherwise leave both receipts committed but
    # neither transaction seeing its peer, so commission never settles.
    order = db.query(MarketplaceOrder).filter(MarketplaceOrder.id == initial.order_id).with_for_update().one()
    row = db.query(EnterpriseMarketEvent).filter(
        EnterpriseMarketEvent.id == event_id,
        EnterpriseMarketEvent.link_id == link_id,
    ).with_for_update().one()
    if receipt.event_id != row.id or receipt.order_id != row.order_id or receipt.side != row.side:
        raise HTTPException(status.HTTP_409_CONFLICT, "رسید با رویداد بازار تطبیق ندارد")
    if row.status != "posted":
        row.attempts += 1
        row.status = receipt.outcome
        row.error_code = receipt.error_code if receipt.outcome != "posted" else ""
        if receipt.outcome == "posted":
            row.posted_at = datetime.now(timezone.utc)
    if row.status == "posted":
        peers = db.query(EnterpriseMarketEvent).filter(
            EnterpriseMarketEvent.operation_ref == row.operation_ref,
            EnterpriseMarketEvent.kind == row.kind,
        ).all()
        if len(peers) == 2 and all(peer.status == "posted" for peer in peers):
            if row.kind == "return":
                ret = db.query(MarketplaceReturn).filter(
                    MarketplaceReturn.id == row.operation_ref,
                    MarketplaceReturn.order_id == order.id,
                ).with_for_update().first()
                if ret is None:
                    raise HTTPException(status.HTTP_409_CONFLICT, "مرجوعی رویداد یافت نشد")
                if ret.status == "sync_pending":
                    ret.status = "approved"
            elif order.status == "sync_pending":
                from app.services import marketplace as market

                order.status = "delivered" if order.delivered_at is not None else "confirmed"
                market._record_commission(db, order)
    db.flush()
    return {"status": row.status, "event_id": row.id}
