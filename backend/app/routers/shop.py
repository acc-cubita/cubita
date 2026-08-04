"""API عمومیِ فروشگاه — `/api/shop/*`.

**سطحِ عمومیِ بدونِ احرازِ کاربر.** هویت با هدرهای `X-Shop-Slug` + `X-Shop-Key`
است (کلیدِ publishable که در سایتِ استاتیک بیک می‌شود). این روتر عمداً از
get_principal/require_permission استفاده *نمی‌کند* — آن‌ها برای کاربرانِ احرازشده‌ی
برنامه‌ی حسابداری‌اند، نه خریدارانِ سایت.

TODO(delivery-phase): CORS باید per-storefront بازتاب داده شود (originِ مجازِ هر
مستأجر از `storefronts.allowed_origin`)، چون سایت روی دامنه‌ی خودِ مستأجر است و
CORالسراسریِ main.py آن را نمی‌شناسد. برای فاز پایه (+تست‌ها که مرورگر نیستند) کافی است.
"""
from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.shop import ShopCategoryOut, ShopInfoOut, ShopProductOut
from app.services import shop as service
from app.services.shop import ShopContext

router = APIRouter(prefix="/api/shop", tags=["shop"])


def get_shop_context(
    x_shop_slug: str | None = Header(default=None, alias="X-Shop-Slug"),
    x_shop_key: str | None = Header(default=None, alias="X-Shop-Key"),
    db: Session = Depends(get_db),
) -> ShopContext:
    # resolve_storefront زمینه‌ی مستأجر را روی همین session ست می‌کند؛ چون FastAPI
    # وابستگیِ get_db را در هر درخواست یک‌بار می‌سازد، اندپوینت همان session را می‌گیرد.
    return service.resolve_storefront(db, x_shop_slug or "", x_shop_key or "")


@router.get("/info", response_model=ShopInfoOut)
def shop_info(ctx: ShopContext = Depends(get_shop_context)):
    sf = ctx.storefront
    return ShopInfoOut(
        theme_id=sf.theme_id,
        theme_config=sf.theme_config or {},
        seo_title=sf.seo_title,
        seo_description=sf.seo_description,
        contact_block=sf.contact_block or {},
    )


@router.get("/catalog", response_model=list[ShopProductOut])
def catalog(ctx: ShopContext = Depends(get_shop_context), db: Session = Depends(get_db)):
    return service.list_catalog(db)


@router.get("/categories", response_model=list[ShopCategoryOut])
def categories(ctx: ShopContext = Depends(get_shop_context), db: Session = Depends(get_db)):
    return service.list_categories(db)


@router.get("/product/{slug}", response_model=ShopProductOut)
def product(slug: str, ctx: ShopContext = Depends(get_shop_context), db: Session = Depends(get_db)):
    return service.get_product(db, slug)
