"""بازارِ عمده‌فروشی — روتر.

اندپوینت‌های سمتِ پخش‌کننده (M2). دو گاردِ روی هم:
- `distributor_principal`: حساب باید نوعِ distributor باشد (وگرنه ۴۰۳).
- `require_permission("marketplace", ...)`: RBAC + اعمالِ اشتراک/تریال (owner با wildcard می‌گذرد).

مالکیت همیشه با فیلترِ صریحِ `distributor_tenant_id == principal.tenant_id` تضمین می‌شود،
چون این جدول‌ها RLS ندارند.
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings as get_app_settings
from app.database import get_db
from app.deps import Principal, get_principal, require_permission, require_super_admin
from app.models.marketplace import MarketplaceOrder
from app.models.user import User
from app.services.payment_providers import get_provider
from app.schemas.marketplace import (
    CatalogListingOut,
    CommissionOverviewOut,
    CommissionPeriodOut,
    CommissionSettleIn,
    CommissionSettleOut,
    ConnectionOut,
    ConnectionRequestIn,
    ConnectionStatusIn,
    DistributorCardOut,
    ListingIn,
    ListingOut,
    MarketplaceSettingsIn,
    MarketplaceSettingsOut,
    MessageIn,
    MessageOut,
    MessagesPage,
    OrderConfirmIn,
    OrderOut,
    OrderPlaceIn,
)
from app.services import marketplace as svc
from app.services import push

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


def distributor_principal(principal: Principal = Depends(get_principal)) -> Principal:
    """فقط حسابِ پخش‌کننده. جدا از require_permission چون «نوعِ حساب» در RBAC نیست."""
    if principal.membership.tenant.kind != "distributor":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "این بخش فقط برای حسابِ پخش‌کننده در بازار است")
    return principal


def retailer_principal(principal: Principal = Depends(get_principal)) -> Principal:
    """فقط حسابِ فروشگاه. جدا از require_permission چون «نوعِ حساب» در RBAC نیست."""
    if principal.membership.tenant.kind != "retailer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "این بخش فقط برای حسابِ فروشگاه در بازار است")
    return principal


# ── تنظیمات ───────────────────────────────────────────────────────────
@router.get("/distributor/settings", response_model=MarketplaceSettingsOut)
def get_settings(
    principal: Principal = Depends(distributor_principal),
    db: Session = Depends(get_db),
):
    return MarketplaceSettingsOut.model_validate(svc.get_settings(db, principal.tenant_id))


@router.put("/distributor/settings", response_model=MarketplaceSettingsOut)
def update_settings(
    data: MarketplaceSettingsIn,
    principal: Principal = Depends(distributor_principal),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketplace", "update")),
):
    return MarketplaceSettingsOut.model_validate(svc.update_settings(db, principal.tenant_id, data))


# ── لیستینگ‌ها ────────────────────────────────────────────────────────
@router.get("/distributor/listings", response_model=list[ListingOut])
def list_listings(
    principal: Principal = Depends(distributor_principal),
    db: Session = Depends(get_db),
):
    return [ListingOut(**svc.listing_dict(l)) for l in svc.list_listings(db, principal.tenant_id)]


@router.post("/distributor/listings", response_model=ListingOut, status_code=201)
def create_listing(
    data: ListingIn,
    principal: Principal = Depends(distributor_principal),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketplace", "create")),
):
    listing = svc.create_listing(db, principal.tenant_id, data)
    return ListingOut(**svc.listing_dict(listing))


@router.put("/distributor/listings/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: UUID,
    data: ListingIn,
    principal: Principal = Depends(distributor_principal),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketplace", "update")),
):
    listing = svc.update_listing(db, principal.tenant_id, listing_id, data)
    return ListingOut(**svc.listing_dict(listing))


@router.post("/distributor/listings/{listing_id}/publish", response_model=ListingOut)
def set_published(
    listing_id: UUID,
    is_published: bool,
    principal: Principal = Depends(distributor_principal),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketplace", "update")),
):
    listing = svc.set_published(db, principal.tenant_id, listing_id, is_published)
    return ListingOut(**svc.listing_dict(listing))


@router.delete("/distributor/listings/{listing_id}", status_code=204)
def delete_listing(
    listing_id: UUID,
    principal: Principal = Depends(distributor_principal),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketplace", "delete")),
):
    svc.delete_listing(db, principal.tenant_id, listing_id)


# ── اتصال‌ها: سمتِ پخش‌کننده ──────────────────────────────────────────
@router.get("/distributor/connections", response_model=list[ConnectionOut])
def distributor_connections(
    principal: Principal = Depends(distributor_principal),
    db: Session = Depends(get_db),
):
    conns = svc.list_connections(db, distributor_tenant_id=principal.tenant_id)
    return [ConnectionOut(**svc.connection_dict(db, c, principal.tenant_id)) for c in conns]


@router.post("/distributor/connections/{connection_id}/status", response_model=ConnectionOut)
def set_connection_status(
    connection_id: UUID,
    data: ConnectionStatusIn,
    principal: Principal = Depends(distributor_principal),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketplace", "update")),
):
    conn = svc.set_connection_status(db, principal.tenant_id, connection_id, data.status)
    return ConnectionOut(**svc.connection_dict(db, conn, principal.tenant_id))


# ── کشف/اتصال/کاتالوگ: سمتِ فروشگاه ───────────────────────────────────
@router.get("/retailer/distributors", response_model=list[DistributorCardOut])
def list_distributors(
    principal: Principal = Depends(retailer_principal),
    db: Session = Depends(get_db),
):
    return [DistributorCardOut(**d) for d in svc.list_distributors_for_retailer(db, principal.tenant_id)]


@router.get("/retailer/connections", response_model=list[ConnectionOut])
def retailer_connections(
    principal: Principal = Depends(retailer_principal),
    db: Session = Depends(get_db),
):
    conns = svc.list_connections(db, retailer_tenant_id=principal.tenant_id)
    return [ConnectionOut(**svc.connection_dict(db, c, principal.tenant_id)) for c in conns]


@router.post("/retailer/connections", response_model=ConnectionOut, status_code=201)
def request_connection(
    data: ConnectionRequestIn,
    principal: Principal = Depends(retailer_principal),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketplace", "create")),
):
    conn = svc.request_connection(db, principal.tenant_id, data.distributor_tenant_id)
    # اعلانِ Push به پخش‌کننده فقط روی درخواستِ تازه‌ی pending (نه کلیکِ بی‌اثرِ دوباره).
    if conn.status == "pending" and conn.requested_by == "retailer":
        push.safe_notify_tenant(
            db,
            conn.distributor_tenant_id,
            title="درخواستِ اتصالِ تازه",
            body=f"«{svc._tenant_name(db, principal.tenant_id)}» می‌خواهد به شما متصل شود",
            data={"route": "market"},
        )
    return ConnectionOut(**svc.connection_dict(db, conn, principal.tenant_id))


# ── گفتگوی اتصال (فروشگاه↔پخش‌کننده) — رشته‌ی مشترک؛ هر دو سمت ──────────
# این اندپوینت‌ها نقشِ خاص نمی‌خواهند: هر عضوی از یکی از دو سمتِ اتصالِ approved می‌تواند
# بخواند/بفرستد. مالکیت با `load_connection_for_member` (تطبیقِ tenant با یکی از دو سمت) است.
@router.get("/connections/{connection_id}/messages", response_model=MessagesPage)
def list_connection_messages(
    connection_id: UUID,
    after: datetime | None = None,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    conn, role = svc.load_connection_for_member(db, principal.tenant_id, connection_id)
    msgs = svc.list_messages(db, conn.id, after)
    # باز/پول‌کردنِ رشته = خواندنش؛ نشانِ خوانده‌نشده صفر می‌شود.
    svc.mark_read(db, conn, role)
    return MessagesPage(my_role=role, messages=[MessageOut(**svc.message_dict(m)) for m in msgs])


@router.post("/connections/{connection_id}/messages", response_model=MessageOut, status_code=201)
def post_connection_message(
    connection_id: UUID,
    data: MessageIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketplace", "create")),
):
    conn, role = svc.load_connection_for_member(db, principal.tenant_id, connection_id)
    msg = svc.post_message(
        db,
        conn,
        sender_tenant_id=principal.tenant_id,
        sender_role=role,
        sender_user_id=principal.user.id,
        body=data.body,
    )
    # اعلان به سمتِ مقابلِ همین اتصال (deep-link به همان رشته‌ی گفتگو).
    other_tenant = conn.retailer_tenant_id if role == "distributor" else conn.distributor_tenant_id
    push.safe_notify_tenant(
        db,
        other_tenant,
        title="پیامِ تازه در بازار",
        body=msg.body[:120],
        data={"route": f"chat/connection/{conn.id}"},
        exclude_user_id=principal.user.id,
    )
    return MessageOut(**svc.message_dict(msg))


# ── گفتگوی زیرِ هر سفارش — رشته‌ی جدا؛ هر دو سمتِ همان سفارش (بدونِ گیتِ وضعیت) ──
@router.get("/orders/{order_id}/messages", response_model=MessagesPage)
def get_order_messages(
    order_id: UUID,
    after: datetime | None = None,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    order, role = svc.load_order_for_member(db, principal.tenant_id, order_id)
    msgs = svc.list_order_messages(db, order.id, after)
    svc.mark_order_read(db, order, role)
    return MessagesPage(my_role=role, messages=[MessageOut(**svc.message_dict(m)) for m in msgs])


@router.post("/orders/{order_id}/messages", response_model=MessageOut, status_code=201)
def create_order_message(
    order_id: UUID,
    data: MessageIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketplace", "create")),
):
    order, role = svc.load_order_for_member(db, principal.tenant_id, order_id)
    msg = svc.post_order_message(
        db,
        order,
        sender_tenant_id=principal.tenant_id,
        sender_role=role,
        sender_user_id=principal.user.id,
        body=data.body,
    )
    # اعلان به سمتِ مقابلِ همین سفارش (deep-link به رشته‌ی گفتگوی سفارش).
    other_tenant = order.retailer_tenant_id if role == "distributor" else order.distributor_tenant_id
    push.safe_notify_tenant(
        db,
        other_tenant,
        title=f"پیامِ تازه — سفارش #{order.order_number}",
        body=msg.body[:120],
        data={"route": f"chat/order/{order.id}"},
        exclude_user_id=principal.user.id,
    )
    return MessageOut(**svc.message_dict(msg))


@router.get("/unread", response_model=int)
def marketplace_unread(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """جمعِ پیام‌های خوانده‌نشده‌ی همه‌ی اتصال‌های approvedِ این حساب — برای نشانِ نویگیشن."""
    kind = principal.membership.tenant.kind
    if kind not in ("distributor", "retailer"):
        return 0
    return svc.total_unread(db, principal.tenant_id, kind)


@router.get("/retailer/catalog", response_model=list[CatalogListingOut])
def retailer_catalog(
    distributor_id: UUID | None = None,
    principal: Principal = Depends(retailer_principal),
    db: Session = Depends(get_db),
):
    return [CatalogListingOut(**d) for d in svc.list_catalog(db, principal.tenant_id, distributor_id)]


# ── سفارش‌ها: سمتِ فروشگاه ────────────────────────────────────────────
@router.get("/retailer/orders", response_model=list[OrderOut])
def retailer_orders(
    principal: Principal = Depends(retailer_principal),
    db: Session = Depends(get_db),
):
    orders = svc.list_orders(db, retailer_tenant_id=principal.tenant_id)
    return [OrderOut(**svc.order_dict(db, o, principal.tenant_id)) for o in orders]


@router.post("/retailer/orders", response_model=OrderOut, status_code=201)
def place_order(
    data: OrderPlaceIn,
    principal: Principal = Depends(retailer_principal),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketplace", "create")),
):
    order = svc.place_order(db, principal.tenant_id, data)
    # اعلانِ سفارشِ تازه به پخش‌کننده.
    push.safe_notify_tenant(
        db,
        order.distributor_tenant_id,
        title="سفارشِ تازه",
        body=f"سفارش #{order.order_number} از «{svc._tenant_name(db, principal.tenant_id)}»",
        data={"route": "market"},
    )
    return OrderOut(**svc.order_dict(db, order))


# ── سفارش‌ها: سمتِ پخش‌کننده ──────────────────────────────────────────
@router.get("/distributor/orders", response_model=list[OrderOut])
def distributor_orders(
    principal: Principal = Depends(distributor_principal),
    db: Session = Depends(get_db),
):
    orders = svc.list_orders(db, distributor_tenant_id=principal.tenant_id)
    return [OrderOut(**svc.order_dict(db, o, principal.tenant_id)) for o in orders]


@router.post("/distributor/orders/{order_id}/confirm", response_model=OrderOut)
def confirm_order(
    order_id: UUID,
    body: OrderConfirmIn | None = None,
    principal: Principal = Depends(distributor_principal),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketplace", "approve")),
):
    # بدنه اختیاری است؛ نبودنش یعنی «۰٪ نقد» (کاملاً اعتباری، رفتارِ قبلی).
    cash_percent = body.cash_percent if body is not None else None
    order = svc.confirm_order(
        db, principal.tenant_id, principal.user, order_id, cash_percent if cash_percent is not None else 0
    )
    return OrderOut(**svc.order_dict(db, order))


@router.post("/distributor/orders/{order_id}/reject", response_model=OrderOut)
def reject_order(
    order_id: UUID,
    principal: Principal = Depends(distributor_principal),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketplace", "update")),
):
    order = svc.reject_order(db, principal.tenant_id, order_id)
    return OrderOut(**svc.order_dict(db, order))


# ── پرداختِ آنلاین (M5) ────────────────────────────────────────────────
@router.post("/retailer/orders/{order_id}/pay")
def pay_order(
    order_id: UUID,
    principal: Principal = Depends(retailer_principal),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("marketplace", "create")),
):
    """پرداختِ آنلاینِ سفارش با درگاهِ پخش‌کننده؛ لینکِ درگاه را برمی‌گرداند تا فروشگاه به آن برود."""
    order = svc.get_retailer_order(db, principal.tenant_id, order_id)
    settings = get_app_settings()
    callback_base = (settings.storefront_api_base or settings.backend_url).rstrip("/")
    redirect_url = svc.start_order_payment(db, order, callback_base)
    return {"redirect_url": redirect_url}


@router.api_route("/pay/callback", methods=["GET", "POST"])
async def pay_callback(request: Request, db: Session = Depends(get_db)):
    """بازگشتِ درگاه (عمومی، بدونِ auth). سفارش با پارامترِ order پیدا و با درگاهِ پخش‌کننده
    verify می‌شود؛ در صورتِ موفقیت پستِ دوطرفه و تسویه انجام و مرورگر به اپ هدایت می‌شود.

    امنیت روی verifyِ درگاه است (authority جعل‌ناپذیر)، نه روی auth — دقیقاً مثلِ callbackِ فروشگاه.
    """
    params: dict[str, str] = dict(request.query_params)
    if request.method == "POST":
        form = await request.form()
        params.update({k: str(v) for k, v in form.items()})

    settings = get_app_settings()
    app_base = (settings.app_url or "").rstrip("/")
    provider_key = params.get("provider", "zarinpal")
    provider = get_provider(provider_key)

    try:
        order_uuid = UUID(params.get("order", ""))
    except ValueError:
        order_uuid = None
    order = (
        db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_uuid).first()
        if order_uuid
        else None
    )

    def result(ok: bool) -> RedirectResponse:
        num = order.order_number if order else ""
        target = f"{app_base}/?mp_pay={'ok' if ok else 'failed'}&order={num}" if app_base else "/"
        return RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)

    if order is None or provider is None:
        return result(False)

    parsed = provider.parse_callback(params)
    if not parsed.ok_signal:
        return result(order.payment_status == "paid")

    ok = svc.verify_online_payment(db, order, provider_key, parsed.authority)
    return result(ok)


# ══════════ کمیسیونِ پلتفرم (۲٪) ══════════════════════════════════════════
# پنلِ سوپرادمین — فقط مالکِ سامانه (acc.cubita@gmail.com) با require_super_admin.
# جدولِ کمیسیون سراسری است، پس این کوئری‌ها به tenant_scope نیاز ندارند.
@router.get("/admin/commissions/overview", response_model=CommissionOverviewOut)
def commission_overview(
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return CommissionOverviewOut(**svc.commission_overview(db))


@router.get("/admin/commissions", response_model=list[CommissionPeriodOut])
def commission_summary(
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return [CommissionPeriodOut(**r) for r in svc.commission_summary(db)]


@router.post("/admin/commissions/settle", response_model=CommissionSettleOut)
def settle_commission(
    data: CommissionSettleIn,
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return CommissionSettleOut(
        **svc.settle_commission_period(db, data.distributor_tenant_id, data.period, data.note)
    )


# صورتِ کمیسیونِ خودِ پخش‌کننده (شفافیت) — فقط مالِ خودش، با فیلترِ صریحِ tenant.
@router.get("/distributor/commissions", response_model=list[CommissionPeriodOut])
def my_commissions(
    principal: Principal = Depends(distributor_principal),
    db: Session = Depends(get_db),
):
    return [CommissionPeriodOut(**r) for r in svc.commission_summary(db, principal.tenant_id)]
