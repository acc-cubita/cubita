"""API عمومیِ فروشگاه — حلِ مستأجر، اعتبارسنجیِ کلید، و خواندنِ کاتالوگ.

**بوت‌استرَپِ مستأجر:** چون `storefronts` هم RLS دارد، کلیدِ publishable را نمی‌شود
بدونِ زمینه‌ی مستأجر روی خودِ آن جدول پیدا کرد (صفر ردیف برمی‌گردد). پس:
  ۱) مستأجر از `tenants.slug` (جدولِ سراسری، بدونِ RLS) پیدا می‌شود.
  ۲) زمینه‌ی مستأجر ست می‌شود تا RLS بقیه‌ی خواندن‌ها را محدود کند.
  ۳) کلیدِ publishable *داخلِ* آن زمینه با ردیفِ `storefronts` سنجیده می‌شود.

این همان الگوی «محافظت خودِ راز است، نه صرفاً RLS» است (مثلِ auth_tokens): slug
عمومی است، ولی رازِ واقعی همان کلید است که فقط داخلِ زمینه اعتبارسنجی می‌شود.
"""
import secrets
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.inventory import Item
from app.models.storefront_native import ItemStorefront, Storefront, StorefrontCategory
from app.models.tenant import Tenant
from app.schemas.shop import ShopCategoryOut, ShopProductOut
from app.services.inventory import get_total_stock_qty
from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant


@dataclass
class ShopContext:
    tenant_id: UUID
    storefront: Storefront


def resolve_storefront(db: Session, slug: str, key: str) -> ShopContext:
    """مستأجر را از slug پیدا، زمینه را ست، و کلیدِ publishable را می‌سنجد.

    عمداً همه‌ی خطاها ۴۰۱ عمومی‌اند (نه ۴۰۴ افشاگر) تا وجود/عدمِ یک فروشگاه و
    درستی/نادرستیِ کلید از هم قابلِ تفکیک نباشند. مقایسه‌ی کلید ثابت‌زمان است.
    """
    if not slug or not key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "شناسه یا کلیدِ فروشگاه ارسال نشده است")

    tenant = db.query(Tenant).filter(Tenant.slug == slug).first()  # سراسری، بدونِ RLS
    if tenant is None or tenant.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "فروشگاه یافت نشد یا غیرفعال است")

    # از این‌جا زمینه‌ی مستأجر ست می‌شود؛ هر خواندنِ بعدی با RLS به همین مستأجر محدود است.
    bind_session_tenant(db, tenant.id)
    apply_tenant_to_transaction(db, tenant.id)

    storefront = db.query(Storefront).first()
    if (
        storefront is None
        or not storefront.publishable_key
        or not secrets.compare_digest(storefront.publishable_key, key)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "کلیدِ فروشگاه نامعتبر است")

    if storefront.status != "published":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "این فروشگاه هنوز منتشر نشده است")

    return ShopContext(tenant_id=tenant.id, storefront=storefront)


def _to_product_out(isf: ItemStorefront, item: Item, qty: int) -> ShopProductOut:
    """سریالایزرِ کاست‌پنهان — فقط فیلدهای عمومی. average_cost هرگز اینجا نمی‌آید."""
    return ShopProductOut(
        id=str(item.id),
        slug=isf.slug or str(item.id),
        title=item.name,
        category=item.category or "",
        price=int(item.sales_price or 0),
        images=list(isf.images or []),
        badge=isf.badge or "",
        description=isf.long_description or "",
        stock=max(0, int(qty)),
        out_of_stock=int(qty) <= 0,
    )


def _listed_query(db: Session):
    return (
        db.query(ItemStorefront, Item)
        .join(Item, Item.id == ItemStorefront.item_id)
        .filter(
            ItemStorefront.is_listed.is_(True),
            Item.is_active.is_(True),
            Item.is_service.is_(False),
        )
    )


def list_catalog(db: Session) -> list[ShopProductOut]:
    rows = _listed_query(db).order_by(ItemStorefront.sort, Item.name).all()
    return [_to_product_out(isf, item, int(get_total_stock_qty(db, item.id))) for isf, item in rows]


def get_product(db: Session, slug: str) -> ShopProductOut:
    row = _listed_query(db).filter(ItemStorefront.slug == slug).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کالا یافت نشد")
    isf, item = row
    return _to_product_out(isf, item, int(get_total_stock_qty(db, item.id)))


def list_categories(db: Session) -> list[ShopCategoryOut]:
    cats = db.query(StorefrontCategory).order_by(StorefrontCategory.sort, StorefrontCategory.name).all()
    return [
        ShopCategoryOut(
            id=str(c.id),
            name=c.name,
            slug=c.slug,
            parent_id=str(c.parent_id) if c.parent_id else None,
        )
        for c in cats
    ]
