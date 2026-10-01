"""Cloud market-only projection for the enterprise server's offline read cache."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.enterprise_market_bridge import MarketViewSnapshot
from app.schemas.marketplace import (
    CatalogListingOut, CommissionPeriodOut, ConnectionOut, DistributorCardOut,
    OrderOut, ReturnOut, ZoneOut,
)
from app.services import marketplace as market


def snapshot(db: Session, cloud_tenant_id: UUID) -> MarketViewSnapshot:
    """Explicit market projection; never serialize a Tenant, Item or ledger row."""
    buyer_connections = market.list_connections(db, retailer_tenant_id=cloud_tenant_id)
    seller_connections = market.list_connections(db, distributor_tenant_id=cloud_tenant_id)

    def order_out(order):
        data = market.order_dict(db, order, cloud_tenant_id)
        # These refer to cloud financial documents for native parties. They
        # are neither needed by the market UI nor local document references.
        data["distributor_sales_invoice_id"] = None
        data["retailer_purchase_invoice_id"] = None
        return OrderOut(**data)

    return MarketViewSnapshot(
        captured_at=datetime.now(timezone.utc),
        distributors=[DistributorCardOut(**row) for row in market.list_distributors_for_retailer(db, cloud_tenant_id)],
        retailer_connections=[
            ConnectionOut(**market.connection_dict(db, row, cloud_tenant_id)) for row in buyer_connections
        ],
        distributor_connections=[
            ConnectionOut(**market.connection_dict(db, row, cloud_tenant_id)) for row in seller_connections
        ],
        catalog=[CatalogListingOut(**row) for row in market.list_catalog(db, cloud_tenant_id)],
        retailer_orders=[order_out(row) for row in market.list_orders(db, retailer_tenant_id=cloud_tenant_id)],
        distributor_orders=[order_out(row) for row in market.list_orders(db, distributor_tenant_id=cloud_tenant_id)],
        retailer_returns=[
            ReturnOut(**market.return_dict(db, row)) for row in market.list_returns(db, retailer_tenant_id=cloud_tenant_id)
        ],
        distributor_returns=[
            ReturnOut(**market.return_dict(db, row)) for row in market.list_returns(db, distributor_tenant_id=cloud_tenant_id)
        ],
        zones=[ZoneOut(**row) for row in market.list_zones(db, cloud_tenant_id)],
        commissions=[CommissionPeriodOut(**row) for row in market.commission_summary(db, cloud_tenant_id)],
        buyer_unread=market.total_unread(db, cloud_tenant_id, "retailer"),
        seller_unread=market.total_unread(db, cloud_tenant_id, "distributor"),
    )
