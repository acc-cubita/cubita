"""On-premise owner controls; the enterprise server initiates every cloud call."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from app.schemas.item_units import ObservedRatioIn
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.licensing import state as license_state
from app.models.enterprise_license import EnterpriseLicense
from app.models.enterprise_market_bridge import EnterpriseMarketItemMap, EnterpriseMarketListingMap, EnterpriseMarketLocalState, EnterpriseMarketLocalPosting
from app.models.inventory import Item
from app.models.marketplace import MarketplaceListing
from app.models.user import User
from app.schemas.marketplace import (
    CatalogAllocationIn, CatalogAllocationOut, CatalogAllocationToggleIn,
    ConnectionOut, ConnectionRequestIn, ConnectionStatusIn, ListingIn, ListingOut,
    MarketplaceSettingsIn, MarketplaceSettingsOut, OrderConfirmIn, OrderDeliverIn,
    MessageIn, MessageOut, MessagesPage, OrderOut, OrderPlaceIn, ReturnOut, ReturnRejectIn, ReturnRequestIn,
    ZoneIn, ZoneOut, ConnectionZoneIn,
)
from app.secrets_at_rest import decrypt, encrypt, is_configured
from app.services import enterprise_market_catalog as catalog
from app.services import marketplace as market
from app.schemas.enterprise_market_bridge import MarketViewSnapshot, MarketFinancialEvent
from app.services.enterprise_market_sync import cloud_get, cloud_post

router = APIRouter(prefix="/api/local-market", tags=["enterprise-market-local"])
marketplace_router = APIRouter(prefix="/api/marketplace", tags=["enterprise-market-local"])


def active_market(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> Principal:
    if not get_settings().is_enterprise or not get_settings().market_bridge_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    if license_state.current(db).mode not in ("active", "grace"):
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "برای بازار، مجوز معتبر سازمانی لازم است")
    row = db.query(EnterpriseMarketLocalState.id).filter(
        EnterpriseMarketLocalState.tenant_id == principal.tenant_id,
        EnterpriseMarketLocalState.status == "active",
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "ابتدا حساب بازار را پیوند دهید")
    return principal


@marketplace_router.get("/distributor/settings", response_model=MarketplaceSettingsOut)
def seller_settings(principal: Principal = Depends(active_market),
                    _: User = Depends(require_permission("market_distribute", "view")),
                    db: Session = Depends(get_db)):
    return MarketplaceSettingsOut.model_validate(market.get_settings(db, principal.tenant_id))


@marketplace_router.put("/distributor/settings", response_model=MarketplaceSettingsOut)
def save_seller_settings(data: MarketplaceSettingsIn, principal: Principal = Depends(active_market),
                         _: User = Depends(require_permission("market_distribute", "update")),
                         db: Session = Depends(get_db)):
    if data.settlement_mode != "credit":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "درگاه آنلاین برای پخش سازمانی پشتیبانی نمی‌شود")
    return MarketplaceSettingsOut.model_validate(market.update_settings(db, principal.tenant_id, data))


@marketplace_router.get("/distributor/listings", response_model=list[ListingOut])
def seller_listings(principal: Principal = Depends(active_market),
                    _: User = Depends(require_permission("market_distribute", "view")),
                    db: Session = Depends(get_db)):
    return [ListingOut(**market.listing_dict(row)) for row in market.list_listings(db, principal.tenant_id)]


@marketplace_router.post("/distributor/listings", response_model=ListingOut, status_code=201)
def create_seller_listing(data: ListingIn, principal: Principal = Depends(active_market),
                          _: User = Depends(require_permission("market_distribute", "create")),
                          db: Session = Depends(get_db)):
    return ListingOut(**market.listing_dict(market.create_listing(db, principal.tenant_id, data)))


@marketplace_router.put("/distributor/listings/{listing_id}", response_model=ListingOut)
def update_seller_listing(listing_id: UUID, data: ListingIn, principal: Principal = Depends(active_market),
                          _: User = Depends(require_permission("market_distribute", "update")),
                          db: Session = Depends(get_db)):
    return ListingOut(**market.listing_dict(market.update_listing(db, principal.tenant_id, listing_id, data)))


@marketplace_router.post("/distributor/listings/{listing_id}/publish", response_model=ListingOut)
def publish_seller_listing(listing_id: UUID, is_published: bool, principal: Principal = Depends(active_market),
                           _: User = Depends(require_permission("market_distribute", "update")),
                           db: Session = Depends(get_db)):
    return ListingOut(**market.listing_dict(market.set_published(db, principal.tenant_id, listing_id, is_published)))


@marketplace_router.delete("/distributor/listings/{listing_id}", status_code=204)
def delete_seller_listing(listing_id: UUID, principal: Principal = Depends(active_market),
                          _: User = Depends(require_permission("market_distribute", "delete")),
                          db: Session = Depends(get_db)):
    mapped = db.query(EnterpriseMarketListingMap.id).filter(
        EnterpriseMarketListingMap.tenant_id == principal.tenant_id,
        EnterpriseMarketListingMap.local_listing_id == listing_id,
    ).first()
    if mapped is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این قلم به بازار نگاشت شده است؛ ابتدا انتشار آن را متوقف و نگاشت را حذف کنید")
    market.delete_listing(db, principal.tenant_id, listing_id)


@marketplace_router.get("/distributor/listings/{listing_id}/allocations", response_model=list[CatalogAllocationOut])
def seller_allocations(listing_id: UUID, principal: Principal = Depends(active_market),
                       _: User = Depends(require_permission("market_distribute", "view")),
                       db: Session = Depends(get_db)):
    return [CatalogAllocationOut(**row) for row in market.catalog_allocation_rows(db, principal.tenant_id, listing_id)]


@marketplace_router.post("/distributor/listings/{listing_id}/allocations", status_code=201)
def add_seller_allocation(listing_id: UUID, data: CatalogAllocationIn, principal: Principal = Depends(active_market),
                          user: User = Depends(require_permission("market_distribute", "update")),
                          db: Session = Depends(get_db)):
    row = market.allocate_batch(db, principal.tenant_id, listing_id, data.batch_id, data.qty, user)
    return {"id": str(row["id"]), "batch_id": str(row["batch_id"]), "qty": str(row["qty"])}


@marketplace_router.post("/distributor/allocations/{allocation_id}/toggle", status_code=204)
def toggle_seller_allocation(allocation_id: UUID, data: CatalogAllocationToggleIn,
                             principal: Principal = Depends(active_market),
                             _: User = Depends(require_permission("market_distribute", "update")),
                             db: Session = Depends(get_db)):
    market.set_allocation_active(db, principal.tenant_id, allocation_id, is_active=data.is_active)


def _market_cache(db: Session, tenant_id: UUID) -> MarketViewSnapshot:
    state = db.query(EnterpriseMarketLocalState).filter(
        EnterpriseMarketLocalState.tenant_id == tenant_id,
        EnterpriseMarketLocalState.status == "active",
    ).first()
    if state is None or state.market_snapshot is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "دادهٔ بازار هنوز همگام نشده است؛ پس از اتصال اینترنت دوباره بررسی کنید")
    if state.last_error_code == "access_denied":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "اعتبار پیوند بازار رد شده است؛ مالک شرکت باید پیوند و مجوز را بررسی کند")
    return MarketViewSnapshot.model_validate(state.market_snapshot)


def _command(db: Session, tenant_id: UUID, user: User, request_id: UUID, operation: str, payload: dict) -> dict:
    state = db.query(EnterpriseMarketLocalState).filter(
        EnterpriseMarketLocalState.tenant_id == tenant_id,
        EnterpriseMarketLocalState.status == "active",
    ).first()
    if state is None or not state.credential_encrypted:
        raise HTTPException(status.HTTP_409_CONFLICT, "اتصال بازار هنوز آماده نیست")
    credential = decrypt(state.credential_encrypted)
    result = cloud_post(
        f"sync/{state.link_id}/command",
        {"request_id": str(request_id), "operation": operation, "actor_name": (user.name or "کاربر سازمانی")[:200], "payload": payload},
        credential=credential,
    )
    # The command is already durably committed by the broker. A failed view
    # refresh must not turn a successful mutation into a failed client reply.
    try:
        view = MarketViewSnapshot.model_validate(cloud_get(f"sync/{state.link_id}/snapshot", credential=credential))
        state.market_snapshot = view.model_dump(mode="json")
        state.market_snapshot_at = view.captured_at
        state.last_error_code = ""
        db.flush()
    except HTTPException as exc:
        state.last_error_code = "access_denied" if exc.status_code < 500 else "network_or_sync_error"
    except ValueError:
        state.last_error_code = "invalid_snapshot"
    return result


@marketplace_router.post("/retailer/connections", response_model=ConnectionOut, status_code=201)
def request_buyer_connection(
    data: ConnectionRequestIn, request_id: UUID = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(active_market),
    user: User = Depends(require_permission("market_buy", "create")),
    db: Session = Depends(get_db),
):
    return ConnectionOut.model_validate(_command(db, principal.tenant_id, user, request_id, "buyer.connect", data.model_dump(mode="json")))


@marketplace_router.post("/retailer/orders", response_model=OrderOut, status_code=201)
def place_buyer_order(
    data: OrderPlaceIn, request_id: UUID = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(active_market),
    user: User = Depends(require_permission("market_buy", "create")),
    db: Session = Depends(get_db),
):
    return OrderOut.model_validate(_command(db, principal.tenant_id, user, request_id, "buyer.place", data.model_dump(mode="json")))


@marketplace_router.post("/distributor/connections/{connection_id}/status", response_model=ConnectionOut)
def update_seller_connection(
    connection_id: UUID, data: ConnectionStatusIn, request_id: UUID = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(active_market),
    user: User = Depends(require_permission("market_distribute", "approve")),
    db: Session = Depends(get_db),
):
    return ConnectionOut.model_validate(_command(
        db, principal.tenant_id, user, request_id, "seller.connection",
        {"connection_id": str(connection_id), **data.model_dump(mode="json")},
    ))


def _seller_order_command(db: Session, principal: Principal, user: User, request_id: UUID,
                          order_id: UUID, operation: str, cash_percent=None) -> OrderOut:
    payload = {"order_id": str(order_id)}
    if cash_percent is not None:
        payload["cash_percent"] = str(cash_percent)
    return OrderOut.model_validate(_command(db, principal.tenant_id, user, request_id, operation, payload))


@marketplace_router.post("/distributor/orders/{order_id}/confirm", response_model=OrderOut)
def confirm_seller_order(
    order_id: UUID, body: OrderConfirmIn | None = None, request_id: UUID = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(active_market),
    user: User = Depends(require_permission("market_distribute", "approve")),
    db: Session = Depends(get_db),
):
    return _seller_order_command(db, principal, user, request_id, order_id, "seller.confirm", (body or OrderConfirmIn()).cash_percent)


@marketplace_router.post("/distributor/orders/{order_id}/deliver", response_model=OrderOut)
def deliver_seller_order(
    order_id: UUID, body: OrderDeliverIn | None = None, request_id: UUID = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(active_market),
    user: User = Depends(require_permission("market_distribute", ("deliver", "approve"))),
    db: Session = Depends(get_db),
):
    return _seller_order_command(db, principal, user, request_id, order_id, "seller.deliver", (body or OrderDeliverIn()).cash_percent)


@marketplace_router.post("/distributor/orders/{order_id}/reject", response_model=OrderOut)
def reject_seller_order(
    order_id: UUID, request_id: UUID = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(active_market),
    user: User = Depends(require_permission("market_distribute", "update")),
    db: Session = Depends(get_db),
):
    return _seller_order_command(db, principal, user, request_id, order_id, "seller.reject")


@marketplace_router.post("/retailer/returns", response_model=ReturnOut, status_code=201)
def request_buyer_return(
    data: ReturnRequestIn, request_id: UUID = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(active_market),
    user: User = Depends(require_permission("market_buy", "create")),
    db: Session = Depends(get_db),
):
    return ReturnOut.model_validate(_command(db, principal.tenant_id, user, request_id, "buyer.return", data.model_dump(mode="json")))


@marketplace_router.post("/distributor/returns/{return_id}/approve", response_model=ReturnOut)
def approve_seller_return(
    return_id: UUID, request_id: UUID = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(active_market),
    user: User = Depends(require_permission("market_distribute", "approve")),
    db: Session = Depends(get_db),
):
    return ReturnOut.model_validate(_command(db, principal.tenant_id, user, request_id, "seller.return.approve", {"return_id": str(return_id)}))


@marketplace_router.post("/distributor/returns/{return_id}/reject", response_model=ReturnOut)
def reject_seller_return(
    return_id: UUID, body: ReturnRejectIn | None = None,
    request_id: UUID = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(active_market),
    user: User = Depends(require_permission("market_distribute", "update")),
    db: Session = Depends(get_db),
):
    return ReturnOut.model_validate(_command(
        db, principal.tenant_id, user, request_id, "seller.return.reject",
        {"return_id": str(return_id), **(body or ReturnRejectIn()).model_dump(mode="json")},
    ))


def _thread_page(db: Session, principal: Principal, kind: str, thread_id: UUID,
                 *, fresh_required: bool = False) -> MessagesPage:
    state = db.query(EnterpriseMarketLocalState).filter(
        EnterpriseMarketLocalState.tenant_id == principal.tenant_id,
        EnterpriseMarketLocalState.status == "active",
    ).first()
    if state is None or not state.credential_encrypted:
        raise HTTPException(status.HTTP_409_CONFLICT, "اتصال بازار آماده نیست")
    key = f"{kind}:{thread_id}"
    cached = (state.message_threads or {}).get(key)
    try:
        raw = cloud_get(f"sync/{state.link_id}/messages/{kind}/{thread_id}", credential=decrypt(state.credential_encrypted))
        page = MessagesPage.model_validate(raw)
        threads = dict(state.message_threads or {})
        threads[key] = page.model_dump(mode="json")
        # Only previously viewed market conversations are cached. Bound the
        # local JSON document so one account cannot grow it without limit.
        while len(threads) > 100:
            threads.pop(next(iter(threads)))
        state.message_threads = threads
        db.flush()
    except HTTPException as exc:
        if fresh_required or exc.status_code != status.HTTP_503_SERVICE_UNAVAILABLE or cached is None:
            raise
        page = MessagesPage.model_validate(cached)
    permission = "market_buy" if page.my_role == "retailer" else "market_distribute"
    if not principal.has_permission(permission, "view"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این گفتگو ندارید")
    return page


def _send_thread_message(db: Session, principal: Principal, user: User, request_id: UUID,
                         kind: str, thread_id: UUID, data: MessageIn) -> MessageOut:
    page = _thread_page(db, principal, kind, thread_id, fresh_required=True)
    permission = "market_buy" if page.my_role == "retailer" else "market_distribute"
    if not principal.has_permission(permission, "create"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "اجازهٔ ارسال پیام ندارید")
    result = MessageOut.model_validate(_command(
        db, principal.tenant_id, user, request_id, f"{kind}.message",
        {"thread_id": str(thread_id), **data.model_dump(mode="json")},
    ))
    return result


@marketplace_router.get("/connections/{connection_id}/messages", response_model=MessagesPage)
def connection_messages(
    connection_id: UUID, after: datetime | None = None,
    principal: Principal = Depends(active_market), db: Session = Depends(get_db),
):
    page = _thread_page(db, principal, "connection", connection_id)
    return page.model_copy(update={"messages": [m for m in page.messages if after is None or m.created_at > after]})


@marketplace_router.post("/connections/{connection_id}/messages", response_model=MessageOut, status_code=201)
def send_connection_message(
    connection_id: UUID, data: MessageIn, request_id: UUID = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(active_market),
    db: Session = Depends(get_db),
):
    return _send_thread_message(db, principal, principal.user, request_id, "connection", connection_id, data)


@marketplace_router.get("/orders/{order_id}/messages", response_model=MessagesPage)
def order_messages(
    order_id: UUID, after: datetime | None = None,
    principal: Principal = Depends(active_market), db: Session = Depends(get_db),
):
    page = _thread_page(db, principal, "order", order_id)
    return page.model_copy(update={"messages": [m for m in page.messages if after is None or m.created_at > after]})


@marketplace_router.post("/orders/{order_id}/messages", response_model=MessageOut, status_code=201)
def send_order_message(
    order_id: UUID, data: MessageIn, request_id: UUID = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(active_market), db: Session = Depends(get_db),
):
    return _send_thread_message(db, principal, principal.user, request_id, "order", order_id, data)


@marketplace_router.get("/retailer/distributors")
def cached_distributors(principal: Principal = Depends(active_market),
                        _: User = Depends(require_permission("market_buy", "view")),
                        db: Session = Depends(get_db)):
    return _market_cache(db, principal.tenant_id).distributors


@marketplace_router.get("/retailer/connections")
def cached_buyer_connections(principal: Principal = Depends(active_market),
                             _: User = Depends(require_permission("market_buy", "view")),
                             db: Session = Depends(get_db)):
    return _market_cache(db, principal.tenant_id).retailer_connections


@marketplace_router.get("/retailer/catalog")
def cached_catalog(distributor_id: UUID | None = None, principal: Principal = Depends(active_market),
                   _: User = Depends(require_permission("market_buy", "view")),
                   db: Session = Depends(get_db)):
    rows = _market_cache(db, principal.tenant_id).catalog
    return [row for row in rows if distributor_id is None or row.distributor_tenant_id == distributor_id]


@marketplace_router.get("/retailer/orders")
def cached_buyer_orders(principal: Principal = Depends(active_market),
                        _: User = Depends(require_permission("market_buy", "view")),
                        db: Session = Depends(get_db)):
    return _market_cache(db, principal.tenant_id).retailer_orders


@marketplace_router.get("/retailer/returns")
def cached_buyer_returns(principal: Principal = Depends(active_market),
                         _: User = Depends(require_permission("market_buy", "view")),
                         db: Session = Depends(get_db)):
    return _market_cache(db, principal.tenant_id).retailer_returns


@marketplace_router.get("/distributor/connections")
def cached_seller_connections(principal: Principal = Depends(active_market),
                              _: User = Depends(require_permission("market_distribute", "view")),
                              db: Session = Depends(get_db)):
    return _market_cache(db, principal.tenant_id).distributor_connections


@marketplace_router.get("/distributor/orders")
def cached_seller_orders(principal: Principal = Depends(active_market),
                         _: User = Depends(require_permission("market_distribute", "view")),
                         db: Session = Depends(get_db)):
    return _market_cache(db, principal.tenant_id).distributor_orders


@marketplace_router.get("/distributor/returns")
def cached_seller_returns(principal: Principal = Depends(active_market),
                          _: User = Depends(require_permission("market_distribute", "view")),
                          db: Session = Depends(get_db)):
    return _market_cache(db, principal.tenant_id).distributor_returns


@marketplace_router.get("/distributor/zones")
def cached_seller_zones(principal: Principal = Depends(active_market),
                        _: User = Depends(require_permission("market_distribute", "view")),
                        db: Session = Depends(get_db)):
    return _market_cache(db, principal.tenant_id).zones


@marketplace_router.post("/distributor/zones", response_model=ZoneOut, status_code=201)
def create_seller_zone(data: ZoneIn, request_id: UUID = Header(alias="Idempotency-Key"),
                       principal: Principal = Depends(active_market),
                       user: User = Depends(require_permission("market_distribute", "create")),
                       db: Session = Depends(get_db)):
    return _command(db, principal.tenant_id, user, request_id, "seller.zone.create", data.model_dump(mode="json"))


@marketplace_router.put("/distributor/zones/{zone_id}", response_model=ZoneOut)
def update_seller_zone(zone_id: UUID, data: ZoneIn, request_id: UUID = Header(alias="Idempotency-Key"),
                       principal: Principal = Depends(active_market),
                       user: User = Depends(require_permission("market_distribute", "update")),
                       db: Session = Depends(get_db)):
    return _command(db, principal.tenant_id, user, request_id, "seller.zone.update", {"zone_id": str(zone_id), **data.model_dump(mode="json")})


@marketplace_router.delete("/distributor/zones/{zone_id}", status_code=204)
def delete_seller_zone(zone_id: UUID, request_id: UUID = Header(alias="Idempotency-Key"),
                       principal: Principal = Depends(active_market),
                       user: User = Depends(require_permission("market_distribute", "delete")),
                       db: Session = Depends(get_db)):
    _command(db, principal.tenant_id, user, request_id, "seller.zone.delete", {"zone_id": str(zone_id)})


@marketplace_router.post("/distributor/connections/{connection_id}/zone", response_model=ConnectionOut)
def assign_seller_zone(connection_id: UUID, data: ConnectionZoneIn, request_id: UUID = Header(alias="Idempotency-Key"),
                       principal: Principal = Depends(active_market),
                       user: User = Depends(require_permission("market_distribute", "update")),
                       db: Session = Depends(get_db)):
    return _command(db, principal.tenant_id, user, request_id, "seller.connection.zone", {"connection_id": str(connection_id), **data.model_dump(mode="json")})


@marketplace_router.get("/distributor/commissions")
def cached_seller_commissions(principal: Principal = Depends(active_market),
                              _: User = Depends(require_permission("market_distribute", "view")),
                              db: Session = Depends(get_db)):
    return _market_cache(db, principal.tenant_id).commissions


@marketplace_router.get("/unread")
def cached_unread(principal: Principal = Depends(active_market), db: Session = Depends(get_db)):
    buy = principal.has_permission("market_buy", "view")
    sell = principal.has_permission("market_distribute", "view")
    if not buy and not sell:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی بازار ندارید")
    view = _market_cache(db, principal.tenant_id)
    return (view.buyer_unread if buy else 0) + (view.seller_unread if sell else 0)


@router.get("/snapshot")
def cached_market_snapshot(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    """Last synced cloud market data; never offers offline mutation."""
    if not get_settings().is_enterprise or not get_settings().market_bridge_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    if license_state.current(db).mode not in ("active", "grace"):
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "برای بازار، مجوز معتبر سازمانی لازم است")
    buy = principal.has_permission("market_buy", "view")
    sell = principal.has_permission("market_distribute", "view")
    if not buy and not sell:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی بازار ندارید")
    state = db.query(EnterpriseMarketLocalState).filter(
        EnterpriseMarketLocalState.tenant_id == principal.tenant_id,
        EnterpriseMarketLocalState.status == "active",
    ).first()
    if state is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "ابتدا بازار را به حساب ابری پیوند دهید")
    if state.last_error_code == "access_denied":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "اعتبار پیوند بازار رد شده است؛ مالک شرکت باید پیوند و مجوز را بررسی کند")
    if state.market_snapshot is None:
        return {"last_sync_at": None, "offline": True, "snapshot": None}
    view = MarketViewSnapshot.model_validate(state.market_snapshot).model_dump(mode="json")
    if not buy:
        for key in ("distributors", "retailer_connections", "catalog", "retailer_orders", "retailer_returns"):
            view[key] = []
        view["buyer_unread"] = 0
    if not sell:
        for key in ("distributor_connections", "distributor_orders", "distributor_returns", "zones", "commissions"):
            view[key] = []
        view["seller_unread"] = 0
    recent = state.market_snapshot_at is not None and (
        datetime.now(timezone.utc) - state.market_snapshot_at
    ).total_seconds() <= 180
    return {"last_sync_at": state.market_snapshot_at, "offline": not recent, "snapshot": view}


@router.get("/sync-status")
def sync_status(principal: Principal = Depends(active_market), db: Session = Depends(get_db)):
    if not any(principal.has_permission(module, "view") for module in ("market_buy", "market_distribute")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی بازار ندارید")
    state = db.query(EnterpriseMarketLocalState).filter(EnterpriseMarketLocalState.tenant_id == principal.tenant_id).one()
    recent = state.market_snapshot_at is not None and (datetime.now(timezone.utc) - state.market_snapshot_at).total_seconds() <= 180
    return {"last_sync_at": state.market_snapshot_at, "offline": not recent or bool(state.last_error_code),
            "access_denied": state.last_error_code == "access_denied"}


def owner(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> Principal:
    if not get_settings().is_enterprise or not get_settings().market_bridge_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    if principal.role.key != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "فقط مالک شرکت می‌تواند بازار را پیوند دهد")
    if license_state.current(db).mode not in ("active", "grace"):
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "برای بازار، مجوز معتبر سازمانی لازم است")
    if not is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "SECRETS_KEY برای نگهداری امن پیوند تنظیم نشده است")
    return principal


def _license_token(db: Session) -> str:
    row = db.get(EnterpriseLicense, 1)
    if row is None or not row.token:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "مجوز سازمانی نصب نشده است")
    return row.token


@router.get("/state")
def market_state(principal: Principal = Depends(owner), db: Session = Depends(get_db)):
    state = db.query(EnterpriseMarketLocalState).filter(
        EnterpriseMarketLocalState.tenant_id == principal.tenant_id,
    ).first()
    if state is None:
        return {"status": "unlinked", "last_sync_at": None, "last_error_code": "", "catalog_approved": False}
    return {
        "status": state.status,
        "cloud_tenant_id": state.cloud_tenant_id,
        "last_sync_at": state.last_sync_at,
        "last_error_code": state.last_error_code,
        "catalog_approved": state.catalog_approved,
    }


@router.post("/pair/start")
def pair_start(principal: Principal = Depends(owner), db: Session = Depends(get_db)):
    state = db.query(EnterpriseMarketLocalState).filter(EnterpriseMarketLocalState.tenant_id == principal.tenant_id).first()
    if state is not None and state.status == "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "این سرور قبلاً به بازار پیوند خورده است")
    result = cloud_post("pair/start", {"token": _license_token(db)})
    try:
        link_id = UUID(result["link_id"])
        pair_code = str(result["pair_code"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "پاسخ پیوند بازار ناقص است") from exc
    if state is None:
        state = EnterpriseMarketLocalState(tenant_id=principal.tenant_id, link_id=link_id, status="pending")
        db.add(state)
    else:
        state.link_id = link_id
        state.cloud_tenant_id = None
        state.credential_encrypted = None
        state.status = "pending"
    # A different cloud owner/account may approve this new link. Neither the
    # previous account's cached conversations nor its publication approval
    # may become visible/active before a fresh sync and owner review.
    state.catalog_approved = False
    state.pending_generation = None
    state.pending_started_at = None
    state.market_snapshot = None
    state.market_snapshot_at = None
    state.message_threads = None
    state.last_sync_at = None
    state.last_error_code = ""
    db.flush()
    return {"link_id": link_id, "pair_code": pair_code, "expires_at": result.get("expires_at")}


@router.post("/pair/complete")
def pair_complete(principal: Principal = Depends(owner), db: Session = Depends(get_db)):
    state = db.query(EnterpriseMarketLocalState).filter(EnterpriseMarketLocalState.tenant_id == principal.tenant_id).with_for_update().first()
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ابتدا درخواست پیوند را بسازید")
    if state.status == "active":
        return {"status": "active", "cloud_tenant_id": state.cloud_tenant_id}
    result = cloud_post("pair/poll", {"token": _license_token(db), "link_id": str(state.link_id)})
    if result.get("status") == "revoked":
        state.status = "revoked"
        state.credential_encrypted = None
        db.flush()
        return {"status": "revoked"}
    if result.get("status") == "pending":
        return {"status": "pending"}
    if result.get("status") != "active":
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "وضعیت پیوند بازار نامعتبر است")
    try:
        cloud_tenant_id = UUID(result["cloud_tenant_id"])
        credential = result["credential"]
        if not isinstance(credential, str) or len(credential) < 32:
            raise ValueError("invalid credential")
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "پاسخ پیوند بازار ناقص است") from exc
    state.cloud_tenant_id = cloud_tenant_id
    state.credential_encrypted = encrypt(credential)
    state.status = "active"
    db.flush()
    return {"status": "active", "cloud_tenant_id": cloud_tenant_id}


class LocalItemMapIn(BaseModel):
    local_item_id: UUID
    market_item_ref: UUID | None = None


class LocalQuantityInputIn(BaseModel):
    line_index: int = Field(ge=0, le=99)
    unit_id: UUID
    observations: list[ObservedRatioIn] = Field(default_factory=list, max_length=100)


def _posting_permission(principal: Principal, side: str, action: str) -> None:
    if not principal.has_permission("market_buy" if side == "buyer" else "market_distribute", action):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به ثبت مالی این سمت بازار ندارید")


@router.get("/posting-errors")
def posting_errors(principal: Principal = Depends(active_market), db: Session = Depends(get_db)):
    sides = [side for side, module in (("buyer", "market_buy"), ("seller", "market_distribute"))
             if principal.has_permission(module, "view")]
    if not sides:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی بازار ندارید")
    rows = db.query(EnterpriseMarketLocalPosting).filter(
        EnterpriseMarketLocalPosting.tenant_id == principal.tenant_id,
        EnterpriseMarketLocalPosting.side.in_(sides),
        EnterpriseMarketLocalPosting.status.in_(("blocked", "retryable_error", "pending")),
    ).order_by(EnterpriseMarketLocalPosting.created_at, EnterpriseMarketLocalPosting.id).limit(200).all()
    refs = {UUID(line["market_item_ref"]) for row in rows for line in row.payload.get("lines", [])}
    mapped = dict(db.query(EnterpriseMarketItemMap.market_item_ref, EnterpriseMarketItemMap.local_item_id).filter(
        EnterpriseMarketItemMap.tenant_id == principal.tenant_id,
        EnterpriseMarketItemMap.market_item_ref.in_(refs)).all())
    return [{"event_id": row.event_id, "order_number": row.payload.get("order_number"),
             "side": row.side, "kind": row.kind, "status": row.status,
             "attempts": row.attempts, "error_code": row.error_code,
             "error_detail": row.error_detail, "lines": [{**line,
                 "local_item_id":mapped.get(UUID(line["market_item_ref"]))}
                 for line in row.payload.get("lines", [])]} for row in rows]


def _error_posting(db: Session, principal: Principal, event_id: UUID) -> EnterpriseMarketLocalPosting:
    from app.services.enterprise_market_posting import lock_local_finance

    lock_local_finance(db, principal.tenant_id)
    row = db.query(EnterpriseMarketLocalPosting).filter(
        EnterpriseMarketLocalPosting.tenant_id == principal.tenant_id,
        EnterpriseMarketLocalPosting.event_id == event_id,
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "رویداد ثبت مالی پیدا نشد")
    _posting_permission(principal, row.side, "update")
    return row


@router.post("/posting-errors/{event_id}/retry")
def retry_posting(event_id: UUID, principal: Principal = Depends(active_market), db: Session = Depends(get_db)):
    from app.services.enterprise_market_posting import consume

    row = _error_posting(db, principal, event_id)
    # Unique event receipt remains the same; the worker sends the resulting
    # acknowledgement after this request commits, including after a lost reply.
    return consume(db, principal.tenant_id, MarketFinancialEvent.model_validate(row.payload))


@router.post("/posting-errors/{event_id}/mapping")
def repair_posting_mapping(event_id: UUID, data: LocalItemMapIn,
                           principal: Principal = Depends(active_market), db: Session = Depends(get_db)):
    row = _error_posting(db, principal, event_id)
    from app.services.enterprise_market_recovery import repair_mapping

    return repair_mapping(db, principal.tenant_id, principal.user.id, row, data.market_item_ref, data.local_item_id)


@router.post("/posting-errors/{event_id}/quantity-input")
def approve_posting_quantity(event_id: UUID, data: LocalQuantityInputIn,
                             principal: Principal = Depends(active_market), db: Session = Depends(get_db)):
    row = _error_posting(db, principal, event_id)
    if row.status == "posted" or row.kind != "order":
        raise HTTPException(409, "مقدار سند ثبت‌شده یا مرجوعی تغییر نمی‌کند؛ از واحد تاریخی فاکتور اصلی استفاده کنید")
    event = MarketFinancialEvent.model_validate(row.payload)
    if data.line_index >= len(event.lines):
        raise HTTPException(422, "ردیف انتخاب‌شده در رویداد وجود ندارد")
    from app.services.enterprise_market_posting import _local_items, MappingMissing
    from app.services import units
    line = event.lines[data.line_index]
    try:
        item = _local_items(db, principal.tenant_id, event)[line.market_item_ref]
    except MappingMissing as exc:
        raise HTTPException(409, "ابتدا نگاشت کالای همین رویداد را تکمیل کنید") from exc
    conversion = units.convert_transaction(db, item, line.qty, data.unit_id,
        context="sale" if event.side == "seller" else "purchase", observations=data.observations)
    row.quantity_inputs = {**(row.quantity_inputs or {}), str(data.line_index): {
        "schema_version":1, "item_id":str(item.id), "market_item_ref":str(line.market_item_ref),
        "conversion":conversion.snapshot(), "approved_by":str(principal.user.id),
        "approved_at":datetime.now(timezone.utc).isoformat()}}
    db.flush()
    return {"approved":True, "conversion":conversion.snapshot()}


class LocalListingMapIn(BaseModel):
    local_listing_id: UUID
    market_listing_ref: UUID | None = None
    items: list[LocalItemMapIn] = Field(min_length=1, max_length=100)


def _local_state(db: Session, tenant_id: UUID) -> EnterpriseMarketLocalState:
    state = db.query(EnterpriseMarketLocalState).filter(EnterpriseMarketLocalState.tenant_id == tenant_id).with_for_update().first()
    if state is None or state.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "ابتدا حساب ابری را به سرور پیوند دهید")
    return state


@router.get("/catalog/mappings")
def catalog_mappings(principal: Principal = Depends(owner), db: Session = Depends(get_db)):
    state = _local_state(db, principal.tenant_id)
    listings = db.query(EnterpriseMarketListingMap).filter(EnterpriseMarketListingMap.tenant_id == principal.tenant_id).all()
    items = db.query(EnterpriseMarketItemMap).filter(EnterpriseMarketItemMap.tenant_id == principal.tenant_id).all()
    return {
        "approved": state.catalog_approved,
        "last_sync_at": state.last_sync_at,
        "last_error_code": state.last_error_code,
        "listings": [{"local_listing_id": r.local_listing_id, "market_listing_ref": r.market_listing_ref} for r in listings],
        "items": [{"local_item_id": r.local_item_id, "market_item_ref": r.market_item_ref} for r in items],
    }


@router.post("/catalog/mappings")
def map_listing(data: LocalListingMapIn, principal: Principal = Depends(owner), db: Session = Depends(get_db)):
    state = _local_state(db, principal.tenant_id)
    if state.catalog_approved:
        raise HTTPException(status.HTTP_409_CONFLICT, "برای تغییر نگاشت، ابتدا انتشار کاتالوگ را متوقف کنید")
    listing = db.query(MarketplaceListing).filter(
        MarketplaceListing.id == data.local_listing_id,
        MarketplaceListing.distributor_tenant_id == principal.tenant_id,
    ).first()
    if listing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کاتالوگ محلی پیدا نشد")
    required = {comp.distributor_item_id for comp in listing.components}
    supplied = {entry.local_item_id for entry in data.items}
    if required != supplied or len(data.items) != len(supplied):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "همهٔ اجزای همین کاتالوگ باید دقیقاً یک‌بار نگاشت شوند")
    own_items = db.query(Item.id).filter(Item.id.in_(supplied), Item.tenant_id == principal.tenant_id).all()
    if {row.id for row in own_items} != required:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "یک کالای نگاشت‌شده به این شرکت تعلق ندارد")
    now = datetime.now(timezone.utc)
    existing = db.query(EnterpriseMarketListingMap).filter(
        EnterpriseMarketListingMap.tenant_id == principal.tenant_id,
        EnterpriseMarketListingMap.local_listing_id == listing.id,
    ).first()
    if existing is None:
        existing = EnterpriseMarketListingMap(
            tenant_id=principal.tenant_id, local_listing_id=listing.id,
            market_listing_ref=data.market_listing_ref or uuid4(),
            approved_by_id=principal.user.id, approved_at=now,
        )
        db.add(existing)
    elif data.market_listing_ref is not None and existing.market_listing_ref != data.market_listing_ref:
        raise HTTPException(status.HTTP_409_CONFLICT, "شناسهٔ کاتالوگ نگاشت‌شده ثابت است؛ برای کالای جدید کاتالوگ جدید بسازید")
    for entry in data.items:
        item_map = db.query(EnterpriseMarketItemMap).filter(
            EnterpriseMarketItemMap.tenant_id == principal.tenant_id,
            EnterpriseMarketItemMap.local_item_id == entry.local_item_id,
        ).first()
        if item_map is None:
            item_map = EnterpriseMarketItemMap(
                tenant_id=principal.tenant_id, local_item_id=entry.local_item_id,
                market_item_ref=entry.market_item_ref or uuid4(),
                approved_by_id=principal.user.id, approved_at=now,
            )
            db.add(item_map)
        elif entry.market_item_ref is not None and item_map.market_item_ref != entry.market_item_ref:
            raise HTTPException(status.HTTP_409_CONFLICT, "شناسهٔ کالای نگاشت‌شده ثابت است؛ تغییر آن مسیر سفارش و مرجوعی‌های گذشته را قطع می‌کند")
    db.flush()
    # Validation includes every selected listing, not just this one.  One
    # missing component must block publication of the entire generation.
    catalog.selected_snapshots(db, principal.tenant_id)
    return {"market_listing_ref": existing.market_listing_ref}


@router.delete("/catalog/mappings/{listing_id}", status_code=204)
def remove_listing_mapping(listing_id: UUID, principal: Principal = Depends(owner), db: Session = Depends(get_db)):
    state = _local_state(db, principal.tenant_id)
    if state.catalog_approved:
        raise HTTPException(status.HTTP_409_CONFLICT, "برای حذف نگاشت، ابتدا انتشار کاتالوگ را متوقف کنید")
    mapping = db.query(EnterpriseMarketListingMap).filter(
        EnterpriseMarketListingMap.tenant_id == principal.tenant_id,
        EnterpriseMarketListingMap.local_listing_id == listing_id,
    ).with_for_update().first()
    if mapping is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "نگاشت کاتالوگ پیدا نشد")
    # Keep item mappings: already accepted orders and returns may still need
    # them for exact-once local posting after the listing is unpublished.
    db.delete(mapping)
    db.flush()


@router.post("/catalog/approve")
def approve_catalog(principal: Principal = Depends(owner), db: Session = Depends(get_db)):
    state = _local_state(db, principal.tenant_id)
    catalog.selected_snapshots(db, principal.tenant_id)
    state.catalog_approved = True
    db.flush()
    return {"approved": True, "message": "کاتالوگ انتخابی در اتصال بعدی همگام می‌شود"}


@router.post("/catalog/pause")
def pause_catalog(principal: Principal = Depends(owner), db: Session = Depends(get_db)):
    state = _local_state(db, principal.tenant_id)
    state.catalog_approved = False
    db.flush()
    return {"approved": False, "message": "انتشار در اتصال بعدی متوقف می‌شود"}
