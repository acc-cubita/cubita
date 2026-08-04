"""مدیریتِ فروشگاهِ بومی از داخلِ برنامه — `/api/storefront/*`.

سطحِ احرازشده‌ی مالکِ کسب‌وکار (جدا از `/api/shop/*`ِ عمومی و `/api/integration/*`ِ
اتصالِ بیرونی). گیتِ فقط-پلن مثلِ مؤدیان/اتصال: حسابِ آزمایشی باکسِ «خرید پلن» می‌بیند.
مجوز مثلِ اتصالِ فروشگاه روی «inventory» می‌نشیند.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import require_feature, require_permission
from app.models.user import User
from app.services.site_build import build_site_bundle
from app.schemas.storefront_native import (
    FulfillmentIn,
    GatewayIn,
    GatewayOut,
    ItemListingIn,
    ItemListingOut,
    OrderOut,
    StorefrontSettingsIn,
    StorefrontSettingsOut,
)
from app.services import storefront_manage as service

router = APIRouter(
    prefix="/api/storefront",
    tags=["storefront"],
    dependencies=[Depends(require_feature("storefront"))],
)


@router.get("", response_model=StorefrontSettingsOut)
def read_storefront_settings(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "view"))):
    return service.to_settings_out(db, service.get_or_create_storefront(db))


@router.put("", response_model=StorefrontSettingsOut)
def update_settings(
    data: StorefrontSettingsIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    return service.to_settings_out(db, service.update_settings(db, data))


@router.post("/key/rotate", response_model=StorefrontSettingsOut)
def rotate_key(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "update"))):
    return service.to_settings_out(db, service.rotate_key(db))


@router.get("/site-bundle")
def site_bundle(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "view"))):
    """بسته‌ی ZIPِ سایتِ فروشگاه با config.jsِ مخصوصِ این کسب‌وکار (apiBase/slug/key)."""
    sf = service.get_or_create_storefront(db)
    slug = service.tenant_slug(db)
    settings = get_settings()
    api_base = (settings.storefront_api_base or settings.backend_url).rstrip("/")
    seo = service.build_seo_context(db, sf)
    try:
        data = build_site_bundle(api_base=api_base, slug=slug, key=sf.publishable_key, seo=seo)
    except FileNotFoundError as err:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(err))
    service.mark_built(db, sf)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="cubita-storefront-{slug}.zip"'},
    )


@router.post("/publish", response_model=StorefrontSettingsOut)
def publish(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "update"))):
    return service.to_settings_out(db, service.set_published(db, True))


@router.post("/unpublish", response_model=StorefrontSettingsOut)
def unpublish(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "update"))):
    return service.to_settings_out(db, service.set_published(db, False))


@router.get("/items", response_model=list[ItemListingOut])
def list_items(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "view"))):
    return service.list_item_listings(db)


@router.put("/items/{item_id}", response_model=ItemListingOut)
def upsert_item(
    item_id: uuid.UUID,
    data: ItemListingIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    isf, item = service.upsert_item_listing(db, item_id, data)
    return ItemListingOut(
        item_id=str(item.id),
        name=item.name,
        sku=item.sku,
        sales_price=int(item.sales_price or 0),
        is_listed=isf.is_listed,
        images=list(isf.images or []),
        long_description=isf.long_description,
        slug=isf.slug,
        sort=isf.sort,
        badge=isf.badge,
    )


@router.get("/gateways", response_model=list[GatewayOut])
def list_gateways(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "view"))):
    return service.list_gateways(db)


@router.put("/gateways/{provider}", response_model=GatewayOut)
def upsert_gateway(
    provider: str,
    data: GatewayIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    g = service.upsert_gateway(db, provider, data)
    return GatewayOut(provider=g.provider, has_merchant=bool(g.merchant_id), is_active=g.is_active)


# ── فیدِ سفارش ───────────────────────────────────────────────────────────────────


@router.get("/orders", response_model=list[OrderOut])
def list_orders(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "view"))):
    return service.list_orders(db)


@router.post("/orders/{order_id}/confirm-payment", response_model=OrderOut)
def confirm_payment(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    return service.to_order_out(service.confirm_payment(db, order_id, user))


@router.put("/orders/{order_id}/fulfillment", response_model=OrderOut)
def update_fulfillment(
    order_id: uuid.UUID,
    data: FulfillmentIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    return service.to_order_out(service.update_fulfillment(db, order_id, data.fulfillment_status))
