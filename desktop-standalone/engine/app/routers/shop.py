"""API عمومیِ فروشگاه — `/api/shop/*`.

**سطحِ عمومیِ بدونِ احرازِ کاربر.** هویت با هدرهای `X-Shop-Slug` + `X-Shop-Key`
است (کلیدِ publishable که در سایتِ استاتیک بیک می‌شود). این روتر عمداً از
get_principal/require_permission استفاده *نمی‌کند* — آن‌ها برای کاربرانِ احرازشده‌ی
برنامه‌ی حسابداری‌اند، نه خریدارانِ سایت.

CORS این مسیرها در `main.py` (میدل‌ورِ `shop_public_cors`) با `*` باز است — چون سطحِ
عمومی روی دامنه‌ی خودِ مستأجر اجرا می‌شود و بدونِ کوکی است (احراز فقط با کلیدِ publishable).
"""
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.storefront_native import Storefront, StorefrontOrder
from app.models.tenant import Tenant
from app.schemas.shop import ShopCategoryOut, ShopInfoOut, ShopOrderIn, ShopOrderOut, ShopProductOut
from app.services import shop as service
from app.services import shop_payment
from app.services.payment_providers import get_provider
from app.services.shop import ShopContext
from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant

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
def shop_info(ctx: ShopContext = Depends(get_shop_context), db: Session = Depends(get_db)):
    sf = ctx.storefront
    return ShopInfoOut(
        theme_id=sf.theme_id,
        theme_config=sf.theme_config or {},
        seo_title=sf.seo_title,
        seo_description=sf.seo_description,
        contact_block=sf.contact_block or {},
        has_online_payment=shop_payment.has_online_payment(db),
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


@router.post("/orders", response_model=ShopOrderOut, status_code=201)
def create_order(
    data: ShopOrderIn, ctx: ShopContext = Depends(get_shop_context), db: Session = Depends(get_db)
):
    order = service.place_order(db, data)
    return ShopOrderOut(
        id=str(order.id),
        order_number=order.order_number,
        tracking_code=order.tracking_code,
        total=int(order.total),
        payment_status=order.payment_status,
    )


@router.post("/orders/{order_id}/pay")
def start_payment(
    order_id: uuid.UUID, ctx: ShopContext = Depends(get_shop_context), db: Session = Depends(get_db)
):
    """شروعِ پرداختِ آنلاین با درگاهِ مستأجر؛ لینکِ درگاه را برمی‌گرداند تا سایت به آن ببرد."""
    order = db.query(StorefrontOrder).filter(StorefrontOrder.id == order_id).first()
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش یافت نشد")
    if order.payment_status != "pending":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این سفارش قابلِ پرداخت نیست")
    gateway = shop_payment.active_gateway(db)
    if gateway is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "درگاهِ پرداختِ آنلاینِ فعالی تنظیم نشده است")

    settings = get_settings()
    api_base = (settings.storefront_api_base or settings.backend_url).rstrip("/")
    callback_url = f"{api_base}/api/shop/pay/callback?shop={ctx.slug}&provider={gateway.provider}"
    redirect_url = shop_payment.start_payment(db, order, ctx.storefront, gateway, callback_url)
    return {"redirect_url": redirect_url}


@router.api_route("/pay/callback", methods=["GET", "POST"])
async def pay_callback(request: Request, db: Session = Depends(get_db)):
    """بازگشتِ درگاه (هر سه provider). مستأجر از پارامترِ shop (=slug) بی‌زمینه پیدا،
    provider مشخص، و پارامترها با آداپتورِ همان درگاه پارس و verify می‌شوند.

    GET برای زرین‌پال/زیبال و POSTِ فرم برای آی‌دی‌پی؛ پارامترهای query و form ادغام می‌شوند.
    """
    params: dict[str, str] = dict(request.query_params)
    if request.method == "POST":
        form = await request.form()
        params.update({k: str(v) for k, v in form.items()})

    shop = params.get("shop", "")
    provider_key = params.get("provider", "zarinpal")
    provider = get_provider(provider_key)

    tenant = db.query(Tenant).filter(Tenant.slug == shop).first()
    if tenant is None or tenant.status != "active" or provider is None:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    bind_session_tenant(db, tenant.id)
    apply_tenant_to_transaction(db, tenant.id)

    parsed = provider.parse_callback(params)
    storefront = db.query(Storefront).first()
    order = (
        db.query(StorefrontOrder)
        .filter(StorefrontOrder.payment_authority == parsed.authority)
        .first()
        if parsed.authority
        else None
    )
    dest = (storefront.allowed_origin if storefront else "") or ""

    def result(ok: bool) -> RedirectResponse:
        code = order.tracking_code if order else ""
        target = f"{dest}/#/order-result?status={'ok' if ok else 'failed'}&code={code}" if dest else "/"
        return RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)

    if order is None or storefront is None:
        return result(False)
    if not parsed.ok_signal:
        if order.payment_status == "pending":
            order.payment_status = "failed"
            db.flush()
        return result(False)

    gateway = shop_payment.gateway_for(db, provider_key)
    actor = shop_payment.tenant_actor(db, tenant.id)
    ok = bool(gateway and actor and shop_payment.verify_and_finalize(db, order, storefront, gateway, parsed.authority, actor))
    if not ok and order.payment_status == "pending":
        order.payment_status = "failed"
        db.flush()
    return result(ok)
