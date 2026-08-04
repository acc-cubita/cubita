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
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.inventory import Item, Warehouse
from app.models.storefront_native import (
    ItemStorefront,
    Storefront,
    StorefrontCategory,
    StorefrontCustomer,
    StorefrontOrder,
    StorefrontOrderLine,
)
from app.models.tenant import Tenant
from app.schemas.shop import ShopCategoryOut, ShopOrderIn, ShopProductOut
from app.services.inventory import get_stock_qty
from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant

#: سفارش‌های سایت از این انبار فروخته می‌شوند (مثلِ مدلِ اتصالِ بیرونی). موجودیِ
#: کاتالوگ هم از همین انبار خوانده می‌شود تا «نمایش = قابلِ فروش» باشد.
ONLINE_WAREHOUSE_CODE = "ONLINE"


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


def _fulfillment_warehouse(db: Session) -> Warehouse | None:
    return db.query(Warehouse).filter(Warehouse.code == ONLINE_WAREHOUSE_CODE).first()


def _stock_for(db: Session, wh: Warehouse | None, item_id: UUID) -> int:
    if wh is None:
        return 0
    return int(get_stock_qty(db, item_id, wh.id))


def list_catalog(db: Session) -> list[ShopProductOut]:
    wh = _fulfillment_warehouse(db)
    rows = _listed_query(db).order_by(ItemStorefront.sort, Item.name).all()
    return [_to_product_out(isf, item, _stock_for(db, wh, item.id)) for isf, item in rows]


def get_product(db: Session, slug: str) -> ShopProductOut:
    row = _listed_query(db).filter(ItemStorefront.slug == slug).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کالا یافت نشد")
    isf, item = row
    return _to_product_out(isf, item, _stock_for(db, _fulfillment_warehouse(db), item.id))


def place_order(db: Session, data: ShopOrderIn) -> StorefrontOrder:
    """سفارشِ سایت را به‌صورت «در انتظارِ پرداخت» ثبت می‌کند — بدونِ سندِ حسابداری.

    **قیمت‌ها سمتِ سرور محاسبه می‌شوند** (`item.sales_price`)، نه از کلاینت — وگرنه
    خریدار می‌توانست قیمت را در درخواست دستکاری کند.
    """
    if not data.lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سبد خالی است")
    if not data.customer_name.strip() or not data.customer_phone.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نام و شماره‌ی تماس لازم است")

    wh = _fulfillment_warehouse(db)
    prepared: list[tuple[Item, int, int, int]] = []  # (item, qty, unit_price, line_total)
    subtotal = 0
    for line in data.lines:
        if line.qty <= 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "تعداد باید بزرگ‌تر از صفر باشد")
        row = _listed_query(db).filter(ItemStorefront.slug == line.slug).first()
        if row is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کالای «{line.slug}» روی سایت موجود نیست")
        _isf, item = row
        available = _stock_for(db, wh, item.id)
        if available < line.qty:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"موجودیِ «{item.name}» کافی نیست (موجود: {available})")
        unit_price = int(item.sales_price or 0)
        line_total = unit_price * line.qty
        subtotal += line_total
        prepared.append((item, line.qty, unit_price, line_total))

    phone = data.customer_phone.strip()
    customer = db.query(StorefrontCustomer).filter(StorefrontCustomer.phone == phone).first()
    if customer is None:
        customer = StorefrontCustomer(
            name=data.customer_name.strip(),
            phone=phone,
            email=data.customer_email or "",
            address=data.shipping_address or "",
        )
        db.add(customer)
        db.flush()

    next_number = (db.query(func.max(StorefrontOrder.order_number)).scalar() or 0) + 1
    order = StorefrontOrder(
        order_number=next_number,
        tracking_code=secrets.token_hex(4).upper(),
        customer_id=customer.id,
        customer_name=data.customer_name.strip(),
        customer_phone=phone,
        customer_email=data.customer_email or "",
        shipping_address=data.shipping_address or "",
        note=data.note or "",
        subtotal=subtotal,
        total=subtotal,
        payment_status="pending",
        fulfillment_status="new",
    )
    db.add(order)
    db.flush()
    for item, qty, unit_price, line_total in prepared:
        db.add(
            StorefrontOrderLine(
                order_id=order.id,
                item_id=item.id,
                item_name=item.name,
                qty=qty,
                unit_price=unit_price,
                line_total=line_total,
            )
        )
    db.flush()
    return order


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
