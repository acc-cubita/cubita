"""بازارِ عمده‌فروشی — سرویس.

نکته‌ی امنیتیِ کلیدی: جدول‌های بازار سراسری‌اند (بدونِ RLS)، پس **هر** کوئری اینجا باید
صریحاً با `distributor_tenant_id`/`retailer_tenant_id` فیلتر شود — RLS اینجا محافظت نمی‌کند.
اما اعتبارسنجیِ «کالا مالِ خودِ پخش‌کننده است» از RLS استفاده می‌کند: چون در نشستِ بسته‌شده
به مستأجرِ پخش‌کننده، کوئریِ `Item` فقط کالاهای خودش را برمی‌گرداند.
"""
from datetime import date, datetime, timezone
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import get_settings as get_app_settings
from app.jalali import gregorian_to_jalali
from app.models.banking import BankAccount
from app.models.advanced_inventory import StockBatch
from app.models.inventory import Contact, Item, Warehouse
from app.models.marketplace import (
    MarketplaceCommission,
    MarketplaceConnection,
    MarketplaceItemLink,
    MarketplaceListing,
    MarketplaceListingComponent,
    MarketplaceMessage,
    MarketplaceOrder,
    MarketplaceOrderLine,
    MarketplaceReturn,
    MarketplaceReturnLine,
    MarketplaceSettings,
    MarketplaceZone,
)
from app.models.storefront_native import PaymentGateway
from app.models.tenant import Membership, Tenant
from app.models.user import Role, User
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.schemas.returns import (
    PurchaseReturnIn,
    PurchaseReturnLineIn,
    SalesReturnIn,
    SalesReturnLineIn,
)
from app.schemas.treasury import TreasuryTransactionIn
from app.services import treasury
from app.services.inventory import _allocate_discount, post_purchase_invoice, post_sales_invoice
from app.services.returns import post_purchase_return, post_sales_return
from app.services.payment_providers import ProviderError, get_provider
from app.tenant_context import tenant_scope


# ── تنظیماتِ پخش‌کننده ────────────────────────────────────────────────
def get_settings(db: Session, distributor_tenant_id: UUID) -> MarketplaceSettings:
    row = (
        db.query(MarketplaceSettings)
        .filter(MarketplaceSettings.distributor_tenant_id == distributor_tenant_id)
        .first()
    )
    if row is None:
        row = MarketplaceSettings(distributor_tenant_id=distributor_tenant_id)
        db.add(row)
        db.flush()
    return row


def update_settings(db: Session, distributor_tenant_id: UUID, data) -> MarketplaceSettings:
    row = get_settings(db, distributor_tenant_id)
    row.display_name = data.display_name.strip()
    row.settlement_mode = data.settlement_mode
    row.is_active = data.is_active
    row.return_policy = data.return_policy.strip()
    row.return_window_days = data.return_window_days
    db.flush()
    return row


# ── لیستینگ‌ها ────────────────────────────────────────────────────────
def _own_items(db: Session, item_ids: list[UUID]) -> dict[UUID, Item]:
    """کالاها را در نشستِ خودِ پخش‌کننده می‌خواند (RLS تضمین می‌کند فقط مالِ خودش)."""
    if not item_ids:
        return {}
    found = {i.id: i for i in db.query(Item).filter(Item.id.in_(item_ids)).all()}
    for iid in item_ids:
        if iid not in found:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "کالای انتخاب‌شده یافت نشد یا مالِ شما نیست")
    return found


def _resolve_components(db: Session, data) -> tuple[UUID | None, list[tuple[UUID, Decimal, str]]]:
    """اجزای لیستینگ را حل می‌کند: single = یک جزءِ qty=1؛ pack = اجزای واردشده.

    خروجی: (distributor_item_id برای single یا None، فهرستِ (item_id, qty, item_name)).
    """
    if data.kind == "single":
        pairs = [(data.item_id, Decimal(1))]
        single_id = data.item_id
    else:
        pairs = [(c.item_id, Decimal(c.qty)) for c in data.components]
        single_id = None
    items = _own_items(db, [iid for iid, _ in pairs])
    resolved = [(iid, qty, items[iid].name) for iid, qty in pairs]
    return single_id, resolved


def list_listings(db: Session, distributor_tenant_id: UUID) -> list[MarketplaceListing]:
    return (
        db.query(MarketplaceListing)
        .filter(MarketplaceListing.distributor_tenant_id == distributor_tenant_id)
        .order_by(MarketplaceListing.created_at.desc())
        .all()
    )


def _get_own_listing(db: Session, distributor_tenant_id: UUID, listing_id: UUID) -> MarketplaceListing:
    listing = (
        db.query(MarketplaceListing)
        .filter(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.distributor_tenant_id == distributor_tenant_id,
        )
        .first()
    )
    if listing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "لیستینگ یافت نشد")
    return listing


def create_listing(db: Session, distributor_tenant_id: UUID, data) -> MarketplaceListing:
    single_id, comps = _resolve_components(db, data)
    listing = MarketplaceListing(
        distributor_tenant_id=distributor_tenant_id,
        kind=data.kind,
        title=data.title.strip(),
        code=data.code.strip(),
        unit=(data.unit.strip() or "عدد"),
        wholesale_price=data.wholesale_price,
        consumer_price=data.consumer_price,
        currency_code=data.currency_code.strip(),
        description=data.description,
        images=data.images or [],
        category=data.category.strip(),
        is_published=data.is_published,
        min_order_qty=data.min_order_qty,
        max_order_qty=data.max_order_qty,
        daily_order_limit=data.daily_order_limit,
        distributor_item_id=single_id,
    )
    for iid, qty, name in comps:
        listing.components.append(
            MarketplaceListingComponent(distributor_item_id=iid, item_name=name, qty=qty)
        )
    db.add(listing)
    db.flush()
    return listing


def update_listing(db: Session, distributor_tenant_id: UUID, listing_id: UUID, data) -> MarketplaceListing:
    listing = _get_own_listing(db, distributor_tenant_id, listing_id)
    single_id, comps = _resolve_components(db, data)

    listing.kind = data.kind
    listing.title = data.title.strip()
    listing.code = data.code.strip()
    listing.unit = data.unit.strip() or "عدد"
    listing.wholesale_price = data.wholesale_price
    listing.consumer_price = data.consumer_price
    listing.currency_code = data.currency_code.strip()
    listing.description = data.description
    listing.images = data.images or []
    listing.category = data.category.strip()
    listing.is_published = data.is_published
    listing.min_order_qty = data.min_order_qty
    listing.max_order_qty = data.max_order_qty
    listing.daily_order_limit = data.daily_order_limit
    listing.distributor_item_id = single_id

    # اجزا کاملاً جایگزین می‌شوند (delete-orphan آن‌ها را پاک می‌کند).
    listing.components.clear()
    db.flush()
    for iid, qty, name in comps:
        listing.components.append(
            MarketplaceListingComponent(distributor_item_id=iid, item_name=name, qty=qty)
        )
    db.flush()
    return listing


def set_published(db: Session, distributor_tenant_id: UUID, listing_id: UUID, is_published: bool) -> MarketplaceListing:
    listing = _get_own_listing(db, distributor_tenant_id, listing_id)
    listing.is_published = is_published
    db.flush()
    return listing


def delete_listing(db: Session, distributor_tenant_id: UUID, listing_id: UUID) -> None:
    listing = _get_own_listing(db, distributor_tenant_id, listing_id)
    db.delete(listing)
    db.flush()


def listing_dict(listing: MarketplaceListing) -> dict:
    return {
        "id": listing.id,
        "kind": listing.kind,
        "title": listing.title,
        "code": listing.code,
        "unit": listing.unit,
        "wholesale_price": listing.wholesale_price,
        "consumer_price": listing.consumer_price,
        "currency_code": listing.currency_code,
        "description": listing.description,
        "images": listing.images or [],
        "category": listing.category,
        "is_published": listing.is_published,
        "min_order_qty": listing.min_order_qty,
        "max_order_qty": listing.max_order_qty,
        "daily_order_limit": listing.daily_order_limit,
        "item_id": listing.distributor_item_id,
        "components": [
            {"item_id": c.distributor_item_id, "item_name": c.item_name, "qty": c.qty}
            for c in listing.components
        ],
    }


# ── نام‌ها (جدول‌های سراسری، بدونِ RLS؛ آزادانه میان‌مستأجری خوانده می‌شوند) ──────
def _tenant_name(db: Session, tenant_id: UUID) -> str:
    t = db.get(Tenant, tenant_id)
    return t.name if t else ""


def distributor_display_name(db: Session, distributor_tenant_id: UUID) -> str:
    """نامِ نمایشیِ پخش‌کننده در بازار = display_nameِ تنظیمات، وگرنه نامِ کسب‌وکار."""
    s = (
        db.query(MarketplaceSettings)
        .filter(MarketplaceSettings.distributor_tenant_id == distributor_tenant_id)
        .first()
    )
    if s and s.display_name.strip():
        return s.display_name.strip()
    return _tenant_name(db, distributor_tenant_id)


# ── کشفِ پخش‌کننده‌ها (سمتِ فروشگاه) ───────────────────────────────────
def _active_distributor(db: Session, distributor_tenant_id: UUID) -> Tenant:
    """پخش‌کننده باید موجود، نوعِ distributor، مستأجرِ فعال، و در بازار فعال باشد."""
    t = db.get(Tenant, distributor_tenant_id)
    if t is None or t.kind != "distributor" or t.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پخش‌کننده یافت نشد")
    s = (
        db.query(MarketplaceSettings)
        .filter(MarketplaceSettings.distributor_tenant_id == distributor_tenant_id)
        .first()
    )
    if s is None or not s.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این پخش‌کننده در بازار فعال نیست")
    return t


def list_distributors_for_retailer(db: Session, retailer_tenant_id: UUID) -> list[dict]:
    """پخش‌کننده‌های فعالِ بازار + وضعیتِ اتصالِ این فروشگاه به هرکدام."""
    conns = {
        c.distributor_tenant_id: c.status
        for c in db.query(MarketplaceConnection)
        .filter(MarketplaceConnection.retailer_tenant_id == retailer_tenant_id)
        .all()
    }
    rows: list[dict] = []
    for s in db.query(MarketplaceSettings).filter(MarketplaceSettings.is_active.is_(True)).all():
        t = db.get(Tenant, s.distributor_tenant_id)
        if t is None or t.kind != "distributor" or t.status != "active":
            continue
        rows.append(
            {
                "tenant_id": s.distributor_tenant_id,
                "display_name": s.display_name.strip() or t.name,
                "connection_status": conns.get(s.distributor_tenant_id),
            }
        )
    rows.sort(key=lambda d: d["display_name"])
    return rows


# ── اتصال‌ها ──────────────────────────────────────────────────────────
def _get_connection(db: Session, distributor_tenant_id: UUID, retailer_tenant_id: UUID) -> MarketplaceConnection | None:
    return (
        db.query(MarketplaceConnection)
        .filter(
            MarketplaceConnection.distributor_tenant_id == distributor_tenant_id,
            MarketplaceConnection.retailer_tenant_id == retailer_tenant_id,
        )
        .first()
    )


def request_connection(db: Session, retailer_tenant_id: UUID, distributor_tenant_id: UUID) -> MarketplaceConnection:
    """فروشگاه درخواستِ اتصال می‌دهد. idempotent؛ blocked قابلِ درخواستِ دوباره نیست."""
    if retailer_tenant_id == distributor_tenant_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "درخواستِ اتصال به خود ممکن نیست")
    _active_distributor(db, distributor_tenant_id)

    conn = _get_connection(db, distributor_tenant_id, retailer_tenant_id)
    if conn is None:
        conn = MarketplaceConnection(
            distributor_tenant_id=distributor_tenant_id,
            retailer_tenant_id=retailer_tenant_id,
            status="pending",
            requested_by="retailer",
        )
        db.add(conn)
        db.flush()
        return conn
    if conn.status == "blocked":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "این پخش‌کننده اتصالِ شما را مسدود کرده است")
    if conn.status == "rejected":
        # رد شده بود؛ درخواستِ دوباره مجاز است.
        conn.status = "pending"
        conn.requested_by = "retailer"
        db.flush()
    # pending/approved → همان را برمی‌گرداند (بی‌اثر بودنِ کلیکِ دوباره).
    return conn


def set_connection_status(
    db: Session, distributor_tenant_id: UUID, connection_id: UUID, new_status: str
) -> MarketplaceConnection:
    """پخش‌کننده اتصال را تأیید/رد/بلاک می‌کند — فقط اتصال‌های خودش."""
    conn = (
        db.query(MarketplaceConnection)
        .filter(
            MarketplaceConnection.id == connection_id,
            MarketplaceConnection.distributor_tenant_id == distributor_tenant_id,
        )
        .first()
    )
    if conn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اتصال یافت نشد")
    conn.status = new_status
    db.flush()
    return conn


def list_connections(db: Session, *, distributor_tenant_id: UUID | None = None, retailer_tenant_id: UUID | None = None) -> list[MarketplaceConnection]:
    q = db.query(MarketplaceConnection)
    if distributor_tenant_id is not None:
        q = q.filter(MarketplaceConnection.distributor_tenant_id == distributor_tenant_id)
    if retailer_tenant_id is not None:
        q = q.filter(MarketplaceConnection.retailer_tenant_id == retailer_tenant_id)
    return q.order_by(MarketplaceConnection.created_at.desc()).all()


def connection_dict(db: Session, conn: MarketplaceConnection, viewer_tenant_id: UUID | None = None) -> dict:
    # وقتی بیننده مشخص است، شمارشِ خوانده‌نشده و آخرین پیام را هم می‌دهیم تا فهرستِ اتصال‌ها
    # نشانِ گفتگو داشته باشد (بدونِ یک فراخوانِ جدا). فقط اتصالِ approved گفتگو دارد.
    unread = 0
    last = _last_message(db, conn.id)
    if viewer_tenant_id is not None and conn.status == "approved":
        if viewer_tenant_id == conn.distributor_tenant_id:
            unread = unread_count(db, conn, "distributor")
        elif viewer_tenant_id == conn.retailer_tenant_id:
            unread = unread_count(db, conn, "retailer")
    zone = db.get(MarketplaceZone, conn.zone_id) if conn.zone_id else None
    return {
        "id": conn.id,
        "distributor_tenant_id": conn.distributor_tenant_id,
        "retailer_tenant_id": conn.retailer_tenant_id,
        "distributor_name": distributor_display_name(db, conn.distributor_tenant_id),
        "retailer_name": _tenant_name(db, conn.retailer_tenant_id),
        "status": conn.status,
        "requested_by": conn.requested_by,
        "zone_id": conn.zone_id,
        "zone_name": zone.name if zone else None,
        "unread_count": unread,
        "last_message_at": last.created_at if last else None,
        "last_message_preview": (last.body[:80] if last else ""),
    }


# ── گفتگوی اتصال (فروشگاه↔پخش‌کننده) — رشته‌ی دائم به‌ازای هر اتصالِ approved ──────
MESSAGE_MAX_LEN = 4000


def load_connection_for_member(
    db: Session, tenant_id: UUID, connection_id: UUID
) -> tuple[MarketplaceConnection, str]:
    """اتصال را برای عضوی از یکی از دو سمت + نقشِ فراخوان ('distributor'|'retailer') برمی‌گرداند.

    اگر tenant هیچ‌کدام از دو سمتِ اتصال نباشد → ۴۰۴ (نه ۴۰۳ افشاگر: وجودِ اتصالِ دیگران را
    لو نمی‌دهد). گفتگو فقط روی اتصالِ approved باز است.
    """
    conn = db.get(MarketplaceConnection, connection_id)
    if conn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اتصال یافت نشد")
    if tenant_id == conn.distributor_tenant_id:
        role = "distributor"
    elif tenant_id == conn.retailer_tenant_id:
        role = "retailer"
    else:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اتصال یافت نشد")
    if conn.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "گفتگو فقط روی اتصالِ تأییدشده باز است")
    return conn, role


def list_messages(
    db: Session, connection_id: UUID, after: datetime | None = None
) -> list[MarketplaceMessage]:
    q = db.query(MarketplaceMessage).filter(MarketplaceMessage.connection_id == connection_id)
    if after is not None:
        q = q.filter(MarketplaceMessage.created_at > after)
    return q.order_by(MarketplaceMessage.created_at.asc()).all()


def _last_message(db: Session, connection_id: UUID) -> MarketplaceMessage | None:
    return (
        db.query(MarketplaceMessage)
        .filter(MarketplaceMessage.connection_id == connection_id)
        .order_by(MarketplaceMessage.created_at.desc())
        .first()
    )


def post_message(
    db: Session,
    conn: MarketplaceConnection,
    *,
    sender_tenant_id: UUID,
    sender_role: str,
    sender_user_id: UUID | None,
    body: str,
) -> MarketplaceMessage:
    text = (body or "").strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "متنِ پیام خالی است")
    text = text[:MESSAGE_MAX_LEN]
    msg = MarketplaceMessage(
        connection_id=conn.id,
        sender_tenant_id=sender_tenant_id,
        sender_role=sender_role,
        sender_user_id=sender_user_id,
        body=text,
    )
    db.add(msg)
    # فرستنده رشته را خوانده فرض می‌شود (پیامِ خودش خوانده‌نشده حساب نشود).
    mark_read(db, conn, sender_role)
    db.flush()
    return msg


def mark_read(db: Session, conn: MarketplaceConnection, role: str, when: datetime | None = None) -> None:
    ts = when or datetime.now(timezone.utc)
    if role == "distributor":
        conn.distributor_last_read_at = ts
    else:
        conn.retailer_last_read_at = ts
    db.flush()


def unread_count(db: Session, conn: MarketplaceConnection, role: str) -> int:
    """پیام‌های خوانده‌نشده‌ی این سمت = پیام‌های سمتِ مقابل که بعد از last_readِ من ثبت شده‌اند."""
    last_read = conn.distributor_last_read_at if role == "distributor" else conn.retailer_last_read_at
    other_role = "retailer" if role == "distributor" else "distributor"
    q = db.query(func.count(MarketplaceMessage.id)).filter(
        MarketplaceMessage.connection_id == conn.id,
        MarketplaceMessage.sender_role == other_role,
    )
    if last_read is not None:
        q = q.filter(MarketplaceMessage.created_at > last_read)
    return int(q.scalar() or 0)


def total_unread(db: Session, tenant_id: UUID, role: str) -> int:
    """جمعِ خوانده‌نشده‌ی این tenant برای نشانِ نویگیشن — هم رشته‌های کلیِ اتصال و هم
    رشته‌های سطحِ سفارش."""
    side = (
        MarketplaceConnection.distributor_tenant_id
        if role == "distributor"
        else MarketplaceConnection.retailer_tenant_id
    )
    conns = (
        db.query(MarketplaceConnection)
        .filter(side == tenant_id, MarketplaceConnection.status == "approved")
        .all()
    )
    conn_unread = sum(unread_count(db, c, role) for c in conns)

    # رشته‌های سفارش — فقط سفارش‌هایی که اصلاً پیام دارند (تا روی هر سفارشِ بی‌گفتگو کوئری نزنیم).
    order_side = (
        MarketplaceOrder.distributor_tenant_id
        if role == "distributor"
        else MarketplaceOrder.retailer_tenant_id
    )
    chatted = db.query(MarketplaceMessage.order_id).filter(MarketplaceMessage.order_id.isnot(None)).distinct()
    orders = (
        db.query(MarketplaceOrder)
        .filter(order_side == tenant_id, MarketplaceOrder.id.in_(chatted))
        .all()
    )
    order_unread = sum(order_unread_count(db, o, role) for o in orders)
    return conn_unread + order_unread


def message_dict(msg: MarketplaceMessage) -> dict:
    return {
        "id": msg.id,
        "sender_role": msg.sender_role,
        "sender_user_id": msg.sender_user_id,
        "body": msg.body,
        "created_at": msg.created_at,
    }


# ── گفتگوی زیرِ هر سفارش — رشته‌ی جدا به‌ازای هر سفارش (هر دو سمتِ همان سفارش) ──────
def load_order_for_member(db: Session, tenant_id: UUID, order_id: UUID) -> tuple[MarketplaceOrder, str]:
    """سفارش را برای یکی از دو سمتش + نقشِ فراخوان برمی‌گرداند (وگرنه ۴۰۴).

    برخلافِ گفتگوی اتصال، اینجا گیتِ وضعیت نیست: طرفین درباره‌ی سفارش در هر وضعیتی
    (ثبت‌شده/تأییدشده/ردشده/…) می‌توانند حرف بزنند.
    """
    order = db.get(MarketplaceOrder, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش یافت نشد")
    if tenant_id == order.distributor_tenant_id:
        role = "distributor"
    elif tenant_id == order.retailer_tenant_id:
        role = "retailer"
    else:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش یافت نشد")
    return order, role


def list_order_messages(db: Session, order_id: UUID, after: datetime | None = None) -> list[MarketplaceMessage]:
    q = db.query(MarketplaceMessage).filter(MarketplaceMessage.order_id == order_id)
    if after is not None:
        q = q.filter(MarketplaceMessage.created_at > after)
    return q.order_by(MarketplaceMessage.created_at.asc()).all()


def _last_order_message(db: Session, order_id: UUID) -> MarketplaceMessage | None:
    return (
        db.query(MarketplaceMessage)
        .filter(MarketplaceMessage.order_id == order_id)
        .order_by(MarketplaceMessage.created_at.desc())
        .first()
    )


def mark_order_read(db: Session, order: MarketplaceOrder, role: str, when: datetime | None = None) -> None:
    ts = when or datetime.now(timezone.utc)
    if role == "distributor":
        order.distributor_last_read_at = ts
    else:
        order.retailer_last_read_at = ts
    db.flush()


def post_order_message(
    db: Session,
    order: MarketplaceOrder,
    *,
    sender_tenant_id: UUID,
    sender_role: str,
    sender_user_id: UUID | None,
    body: str,
) -> MarketplaceMessage:
    text = (body or "").strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "متنِ پیام خالی است")
    text = text[:MESSAGE_MAX_LEN]
    msg = MarketplaceMessage(
        order_id=order.id,
        sender_tenant_id=sender_tenant_id,
        sender_role=sender_role,
        sender_user_id=sender_user_id,
        body=text,
    )
    db.add(msg)
    mark_order_read(db, order, sender_role)  # فرستنده پیامِ خودش را خوانده فرض می‌شود
    db.flush()
    return msg


def order_unread_count(db: Session, order: MarketplaceOrder, role: str) -> int:
    last_read = order.distributor_last_read_at if role == "distributor" else order.retailer_last_read_at
    other_role = "retailer" if role == "distributor" else "distributor"
    q = db.query(func.count(MarketplaceMessage.id)).filter(
        MarketplaceMessage.order_id == order.id,
        MarketplaceMessage.sender_role == other_role,
    )
    if last_read is not None:
        q = q.filter(MarketplaceMessage.created_at > last_read)
    return int(q.scalar() or 0)


# ── کاتالوگِ سمتِ فروشگاه ──────────────────────────────────────────────
def approved_distributor_ids(db: Session, retailer_tenant_id: UUID) -> set[UUID]:
    """شناسه‌ی پخش‌کننده‌هایی که این فروشگاه با آن‌ها اتصالِ approved دارد."""
    rows = (
        db.query(MarketplaceConnection.distributor_tenant_id)
        .filter(
            MarketplaceConnection.retailer_tenant_id == retailer_tenant_id,
            MarketplaceConnection.status == "approved",
        )
        .all()
    )
    return {r[0] for r in rows}


def list_catalog(db: Session, retailer_tenant_id: UUID, distributor_tenant_id: UUID | None = None) -> list[dict]:
    """لیستینگ‌های منتشرشده‌ی پخش‌کننده‌های تأییدشده. با فیلترِ صریحِ اتصال (RLS نیست)."""
    allowed = approved_distributor_ids(db, retailer_tenant_id)
    if distributor_tenant_id is not None:
        if distributor_tenant_id not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "به این پخش‌کننده متصل نیستید")
        allowed = {distributor_tenant_id}
    if not allowed:
        return []

    listings = (
        db.query(MarketplaceListing)
        .filter(
            MarketplaceListing.distributor_tenant_id.in_(allowed),
            MarketplaceListing.is_published.is_(True),
        )
        .order_by(MarketplaceListing.created_at.desc())
        .all()
    )
    names: dict[UUID, str] = {}
    out: list[dict] = []
    for l in listings:
        did = l.distributor_tenant_id
        if did not in names:
            names[did] = distributor_display_name(db, did)
        out.append(
            {
                "id": l.id,
                "distributor_tenant_id": did,
                "distributor_name": names[did],
                "kind": l.kind,
                "title": l.title,
                "code": l.code,
                "unit": l.unit,
                "wholesale_price": l.wholesale_price,
                "consumer_price": l.consumer_price,
                "currency_code": l.currency_code,
                "description": l.description,
                "images": l.images or [],
                "category": l.category,
                "min_order_qty": l.min_order_qty,
                "max_order_qty": l.max_order_qty,
                "daily_order_limit": l.daily_order_limit,
                "components": [{"item_name": c.item_name, "qty": c.qty} for c in l.components],
            }
        )
    return out


# ── سفارش‌ها (M4) ──────────────────────────────────────────────────────
def _order_query(db: Session):
    return db.query(MarketplaceOrder)


def list_orders(
    db: Session, *, distributor_tenant_id: UUID | None = None, retailer_tenant_id: UUID | None = None
) -> list[MarketplaceOrder]:
    q = _order_query(db)
    if distributor_tenant_id is not None:
        q = q.filter(MarketplaceOrder.distributor_tenant_id == distributor_tenant_id)
    if retailer_tenant_id is not None:
        q = q.filter(MarketplaceOrder.retailer_tenant_id == retailer_tenant_id)
    return q.order_by(MarketplaceOrder.created_at.desc()).all()


def _fmt_qty(x: Decimal) -> str:
    """نمایشِ خوانا برای پیامِ خطا: عددِ صحیح بدونِ اعشار، وگرنه نرمال‌شده."""
    x = Decimal(x)
    return str(int(x)) if x == x.to_integral_value() else str(x.normalize())


def _orders_today_with_listing(db: Session, retailer_tenant_id: UUID, listing_id: UUID) -> int:
    """تعدادِ سفارش‌های امروزِ این فروشگاه که شاملِ این لیستینگ‌اند (به‌جز رد/لغوشده).

    پایه‌ی سقفِ «دفعاتِ سفارش در روز». امروز از `current_date`ِ پایگاه‌داده گرفته می‌شود
    تا مرزِ روز با created_at (timestamptz) در همان منطقه‌ی زمانیِ نشست هم‌خوان بماند.
    """
    return (
        db.query(func.count(func.distinct(MarketplaceOrder.id)))
        .join(MarketplaceOrderLine, MarketplaceOrderLine.order_id == MarketplaceOrder.id)
        .filter(
            MarketplaceOrder.retailer_tenant_id == retailer_tenant_id,
            MarketplaceOrderLine.listing_id == listing_id,
            MarketplaceOrder.status.notin_(("rejected", "cancelled")),
            MarketplaceOrder.created_at >= func.current_date(),
        )
        .scalar()
    ) or 0


def place_order(db: Session, retailer_tenant_id: UUID, data) -> MarketplaceOrder:
    """فروشگاه سفارش می‌سازد. فقط از پخش‌کننده‌ی approved و لیستینگ‌های منتشرشده‌اش."""
    distributor_id = data.distributor_tenant_id
    if distributor_id not in approved_distributor_ids(db, retailer_tenant_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "به این پخش‌کننده متصل نیستید یا اتصال هنوز تأیید نشده است")

    listing_ids = [ln.listing_id for ln in data.lines]
    listings = {
        l.id: l
        for l in db.query(MarketplaceListing)
        .filter(
            MarketplaceListing.id.in_(listing_ids),
            MarketplaceListing.distributor_tenant_id == distributor_id,
            MarketplaceListing.is_published.is_(True),
        )
        .all()
    }

    order_lines: list[MarketplaceOrderLine] = []
    subtotal = Decimal(0)
    for ln in data.lines:
        listing = listings.get(ln.listing_id)
        if listing is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "یکی از اقلامِ سفارش در کاتالوگِ این پخش‌کننده نیست")
        # محدودیت‌های سفارش‌گذاریِ پخش‌کننده روی این لیستینگ (۰ = بی‌حد).
        qty = Decimal(ln.qty)
        minq = Decimal(listing.min_order_qty or 0)
        maxq = Decimal(listing.max_order_qty or 0)
        if minq > 0 and qty < minq:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"حداقلِ سفارشِ «{listing.title}» {_fmt_qty(minq)} است"
            )
        if maxq > 0 and qty > maxq:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"حداکثرِ سفارشِ «{listing.title}» در هر بار {_fmt_qty(maxq)} است"
            )
        if listing.daily_order_limit and listing.daily_order_limit > 0:
            if _orders_today_with_listing(db, retailer_tenant_id, listing.id) >= listing.daily_order_limit:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"برای «{listing.title}» فقط {listing.daily_order_limit} بار در روز می‌توانید سفارش دهید",
                )
        unit_price = Decimal(listing.wholesale_price)
        line_total = unit_price * qty
        subtotal += line_total
        order_lines.append(
            MarketplaceOrderLine(
                listing_id=listing.id,
                title=listing.title,
                unit_price=unit_price,
                qty=qty,
                line_total=line_total,
            )
        )

    settings = get_settings(db, distributor_id)
    order_number = settings.next_order_number
    settings.next_order_number = order_number + 1

    order = MarketplaceOrder(
        distributor_tenant_id=distributor_id,
        retailer_tenant_id=retailer_tenant_id,
        order_number=order_number,
        status="placed",
        settlement_mode=settings.settlement_mode,
        payment_status="unpaid",
        note=(data.note or "").strip(),
        subtotal=subtotal,
        total=subtotal,
        lines=order_lines,
    )
    db.add(order)
    db.flush()
    return order


def _default_warehouse(db: Session, tenant_id: UUID) -> Warehouse:
    """انبارِ فعالِ پیش‌فرضِ مستأجرِ جاری (باید درونِ tenant_scope فراخوانی شود)."""
    wh = (
        db.query(Warehouse)
        .filter(Warehouse.is_active.is_(True))
        .order_by(Warehouse.code)
        .first()
    )
    if wh is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای این حساب انبارِ فعالی تعریف نشده است")
    return wh


def _tenant_actor(db: Session, tenant_id: UUID) -> User:
    """کاربرِ مسئولِ سند در مستأجرِ جاری — مالک را ترجیح می‌دهد (درونِ tenant_scope)."""
    owner_role = db.query(Role).filter(Role.key == "owner").first()
    membership = None
    if owner_role is not None:
        membership = (
            db.query(Membership)
            .filter(
                Membership.tenant_id == tenant_id,
                Membership.role_id == owner_role.id,
                Membership.status == "active",
            )
            .first()
        )
    if membership is None:
        membership = (
            db.query(Membership)
            .filter(Membership.tenant_id == tenant_id, Membership.status == "active")
            .first()
        )
    if membership is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کاربرِ فعالی برای ثبتِ سندِ این حساب یافت نشد")
    return db.get(User, membership.user_id)


def _find_or_create_customer(db: Session, conn: MarketplaceConnection, retailer_tenant_id: UUID) -> Contact:
    """طرف‌حسابِ «مشتری» در دفترِ پخش‌کننده (همان فروشگاه) — درونِ scopeِ پخش‌کننده."""
    if conn.distributor_customer_contact_id is not None:
        existing = db.get(Contact, conn.distributor_customer_contact_id)
        if existing is not None:
            return existing
    contact = Contact(name=(_tenant_name(db, retailer_tenant_id) or "فروشگاهِ بازار"), type="customer")
    db.add(contact)
    db.flush()
    conn.distributor_customer_contact_id = contact.id
    return contact


def _find_or_create_supplier(db: Session, conn: MarketplaceConnection, distributor_tenant_id: UUID) -> Contact:
    """طرف‌حسابِ «تأمین‌کننده» در دفترِ فروشگاه (همان پخش‌کننده) — درونِ scopeِ فروشگاه."""
    if conn.retailer_supplier_contact_id is not None:
        existing = db.get(Contact, conn.retailer_supplier_contact_id)
        if existing is not None:
            return existing
    contact = Contact(name=(distributor_display_name(db, distributor_tenant_id) or "پخش‌کننده"), type="supplier")
    db.add(contact)
    db.flush()
    conn.retailer_supplier_contact_id = contact.id
    return contact


def _barcode_free(db: Session, barcode: str, exclude_id: UUID | None = None) -> bool:
    """آیا این بارکد در انبارِ جاری (scopeِ فروشگاه) آزاد است؟ برای انتقالِ بی‌تصادمِ بارکد."""
    q = db.query(Item.id).filter(Item.barcode == barcode)
    if exclude_id is not None:
        q = q.filter(Item.id != exclude_id)
    return q.first() is None


def _resolve_retailer_item(
    db: Session,
    retailer_tenant_id: UUID,
    distributor_tenant_id: UUID,
    distributor_item_id: UUID,
    name: str,
    unit: str,
    price: Decimal,
    barcode: str | None = None,
) -> Item:
    """کالای متناظرِ فروشگاه را برمی‌گرداند؛ بارِ اول می‌سازد و لینک می‌کند (درونِ scopeِ فروشگاه).

    نگاشتِ ضدِتکرار در `marketplace_item_links` است: هر کالای پخش‌کننده در انبارِ فروشگاه
    فقط یک کالای متناظر می‌سازد؛ سفارش‌های بعدی همان کالا را پیدا و تعدادش را اضافه می‌کنند.

    `barcode` (بارکدِ کالای پخش‌کننده) هنگامِ ساختِ کالای تازه منتقل می‌شود تا فروشگاه
    مجبور نباشد دستی تنظیمش کند؛ اگر همان بارکد در انبارِ فروشگاه قبلاً برای کالای دیگری
    باشد، از انتقال صرف‌نظر می‌شود (تصادم با یکتاییِ بارکد). برای کالای لینک‌شده‌ی قبلی که
    هنوز بارکد ندارد هم به‌صورتِ فرصت‌طلبانه پُر می‌شود.
    """
    link = (
        db.query(MarketplaceItemLink)
        .filter(
            MarketplaceItemLink.retailer_tenant_id == retailer_tenant_id,
            MarketplaceItemLink.distributor_item_id == distributor_item_id,
        )
        .first()
    )
    if link is not None:
        item = db.get(Item, link.retailer_item_id)
        if item is not None:
            # بک‌فیلِ بارکد روی کالای موجود اگر هنوز خالی است و بارکد آزاد است
            if barcode and not item.barcode and _barcode_free(db, barcode, exclude_id=item.id):
                item.barcode = barcode
                db.flush()
            return item

    item = Item(
        sku=f"MP-{distributor_item_id.hex}",
        name=(name or "کالای بازار"),
        unit=(unit or "عدد"),
        sales_price=price,
        average_cost=0,
        barcode=(barcode if (barcode and _barcode_free(db, barcode)) else None),
    )
    db.add(item)
    db.flush()
    if link is not None:
        link.retailer_item_id = item.id
    else:
        db.add(
            MarketplaceItemLink(
                retailer_tenant_id=retailer_tenant_id,
                distributor_tenant_id=distributor_tenant_id,
                distributor_item_id=distributor_item_id,
                retailer_item_id=item.id,
            )
        )
    db.flush()
    return item


def _explode_order(order: MarketplaceOrder, listings: dict) -> list[dict]:
    """هر ردیفِ سفارش را به اجزای کالای پخش‌کننده باز می‌کند و قیمتِ ردیف را بینِ اجزا تسهیم می‌کند.

    خروجی برای هر جزء: distributor_item_id، snapshotِ نام/واحد، تعدادِ کل، و قیمتِ واحدِ صحیح
    به‌همراهِ تخفیفِ باقی‌مانده تا `units×unit_price − discount` دقیقاً برابرِ سهمِ آن جزء شود
    (ستون‌ها ریالِ صحیح‌اند، پس قیمتِ واحدِ کسری مجاز نیست).
    """
    fulfillment: list[dict] = []
    for ol in order.lines:
        listing = listings.get(ol.listing_id)
        if listing is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "یکی از اقلامِ سفارش دیگر در کاتالوگ نیست؛ امکانِ تأیید نیست"
            )
        comps = list(listing.components)
        if not comps:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "لیستینگِ سفارش جزئی برای تحویل ندارد")
        units_list = [Decimal(c.qty) * Decimal(ol.qty) for c in comps]
        shares = _allocate_discount(Decimal(ol.line_total), units_list)
        for comp, units, share in zip(comps, units_list, shares):
            if units <= 0:
                continue
            unit_price = (share / units).to_integral_value(rounding=ROUND_CEILING)
            discount = unit_price * units - share
            fulfillment.append(
                {
                    "distributor_item_id": comp.distributor_item_id,
                    "name": comp.item_name,
                    "unit": listing.unit,
                    "units": units,
                    "unit_price": unit_price,
                    "discount": discount,
                    # قیمتِ مصرف‌کننده فقط برای لیستینگِ تکی معنا دارد (پک را نمی‌توان بینِ اجزا تقسیم کرد).
                    "consumer_price": (Decimal(listing.consumer_price) if len(comps) == 1 else Decimal(0)),
                }
            )
    return fulfillment


def _fulfill(db: Session, order: MarketplaceOrder, distributor_user: User) -> MarketplaceConnection:
    """پستِ دوطرفه‌ی سند/انبار برای یک سفارش — بدونِ اعتبارسنجیِ وضعیت (فراخوان‌ها آن را می‌کنند).

    - سمتِ پخش‌کننده (`tenant_scope`): فاکتورِ فروش → کسر از انبار + طلب/درآمد.
    - سمتِ فروشگاه (`tenant_scope`): کالا خودکار در انبارش ساخته/پیدا می‌شود و
      فاکتورِ خرید → **افزودن به انبار (تعداد اضافه می‌شود)** + بدهی به پخش‌کننده.
    وضعیتِ سفارش را confirmed و شناسه‌ی دو فاکتور را روی آن می‌گذارد؛ conn را برمی‌گرداند
    (طرف‌حساب‌های ساخته‌شده رویش نشسته‌اند تا تسویه‌ی آنلاین از همان‌ها استفاده کند).
    """
    distributor_id = order.distributor_tenant_id
    retailer_id = order.retailer_tenant_id
    conn = _get_connection(db, distributor_id, retailer_id)
    if conn is None or conn.status != "approved":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "اتصال با این فروشگاه تأییدشده نیست")

    listing_ids = [ol.listing_id for ol in order.lines if ol.listing_id is not None]
    listings = {l.id: l for l in db.query(MarketplaceListing).filter(MarketplaceListing.id.in_(listing_ids)).all()}
    fulfillment = _explode_order(order, listings)
    today = date.today()
    order_tag = f"سفارشِ بازار #{order.order_number}"

    # ── دفترِ پخش‌کننده: فاکتورِ فروش ───────────────────────────────────
    with tenant_scope(db, distributor_id):
        customer = _find_or_create_customer(db, conn, retailer_id)
        dist_wh = _default_warehouse(db, distributor_id)
        sales_lines = [
            SalesInvoiceLineIn(
                item_id=f["distributor_item_id"], qty=f["units"], unit_price=f["unit_price"], discount=f["discount"]
            )
            for f in fulfillment
        ]
        # بارکدِ کالاهای پخش‌کننده را همین‌جا (در scopeِ خودش، جایی که RLS اجازه می‌دهد)
        # می‌خوانیم تا هنگامِ ساختِ کالای متناظرِ فروشگاه خودکار منتقل شود.
        dist_item_ids = {f["distributor_item_id"] for f in fulfillment}
        barcodes = {
            iid: bc
            for iid, bc in db.query(Item.id, Item.barcode).filter(Item.id.in_(dist_item_ids)).all()
        }
        sales_invoice = post_sales_invoice(
            db,
            SalesInvoiceIn(
                invoice_date=today, warehouse_id=dist_wh.id, contact_id=customer.id, lines=sales_lines, description=order_tag
            ),
            distributor_user,
        )
        sales_invoice_id = sales_invoice.id

    # ── دفترِ فروشگاه: فاکتورِ خرید (ورودِ انبار) ────────────────────────
    with tenant_scope(db, retailer_id):
        retailer_user = _tenant_actor(db, retailer_id)
        supplier = _find_or_create_supplier(db, conn, distributor_id)
        ret_wh = _default_warehouse(db, retailer_id)
        purchase_lines = []
        consumer_by_item: dict[UUID, Decimal] = {}  # کالای فروشگاه → قیمتِ مصرف‌کننده (برای بچ)
        for f in fulfillment:
            ret_item = _resolve_retailer_item(
                db, retailer_id, distributor_id, f["distributor_item_id"], f["name"], f["unit"], f["unit_price"],
                barcode=barcodes.get(f["distributor_item_id"]),
            )
            cp = f.get("consumer_price") or Decimal(0)
            if cp > 0:
                consumer_by_item[ret_item.id] = cp
            purchase_lines.append(
                PurchaseInvoiceLineIn(
                    item_id=ret_item.id, qty=f["units"], unit_cost=f["unit_price"], discount=f["discount"]
                )
            )
        purchase_invoice = post_purchase_invoice(
            db,
            PurchaseInvoiceIn(
                invoice_date=today, warehouse_id=ret_wh.id, contact_id=supplier.id, lines=purchase_lines, description=order_tag
            ),
            retailer_user,
        )
        purchase_invoice_id = purchase_invoice.id
        # قیمتِ مصرف‌کننده‌ی اعلامیِ پخش‌کننده را روی بارهای تازه‌ی این خرید می‌نشانیم
        # (خودکار، مثلِ کارِ ویزیتور: خرید X، فروش Y). بچ‌ها را post_purchase_invoice ساخته.
        if consumer_by_item:
            for batch in db.query(StockBatch).filter(StockBatch.source_id == purchase_invoice_id).all():
                cp = consumer_by_item.get(batch.item_id)
                if cp and cp > 0:
                    batch.consumer_price = cp
            db.flush()

    order.distributor_sales_invoice_id = sales_invoice_id
    order.retailer_purchase_invoice_id = purchase_invoice_id
    order.status = "confirmed"
    # کمیسیونِ ۲٪ِ پلتفرم روی این سفارشِ قطعی‌شده (یک بار، سراسری، بدونِ سند در دفترِ پخش‌کننده)
    _record_commission(db, order)
    db.flush()
    return conn


def confirm_order(
    db: Session,
    distributor_tenant_id: UUID,
    distributor_user: User,
    order_id: UUID,
    cash_percent: Decimal = Decimal(0),
) -> MarketplaceOrder:
    """پخش‌کننده سفارشِ اعتباری را تأیید می‌کند → پستِ دوطرفه + تسویه‌ی سهمِ نقد.

    `cash_percent` (۰..۱۰۰): چند درصد از فاکتور همین حالا نقد دریافت می‌شود؛ بقیه اعتباری
    (طلب/بدهی) می‌ماند. سهمِ نقد در خزانه‌ی هر دو طرف سند می‌خورد.

    idempotent: تأییدِ دوباره فاکتورِ دوم نمی‌سازد. قفلِ ردیفِ سفارش رقابتِ همزمان را هم می‌بندد.
    سفارشِ آنلاین باید اول توسطِ فروشگاه پرداخت شود (callback خودش آن را نهایی می‌کند).
    """
    order = (
        _order_query(db)
        .filter(MarketplaceOrder.id == order_id, MarketplaceOrder.distributor_tenant_id == distributor_tenant_id)
        .with_for_update()
        .first()
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش یافت نشد")
    if order.status == "confirmed":
        return order  # بی‌اثر بودنِ تأییدِ دوباره
    if order.status != "placed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فقط سفارشِ ثبت‌شده قابلِ تأیید است")
    if order.settlement_mode == "online" and order.payment_status != "paid":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سفارشِ آنلاین باید ابتدا توسطِ فروشگاه پرداخت شود")

    conn = _fulfill(db, order, distributor_user)
    # سهمِ نقد (٪ روی جمعِ فاکتور) را همان لحظه در خزانه‌ی هر دو طرف ثبت کن؛ بقیه اعتباری.
    pct = min(max(Decimal(cash_percent or 0), Decimal(0)), Decimal(100))
    cash_amount = (Decimal(order.total) * pct / Decimal(100)).to_integral_value(rounding=ROUND_HALF_UP)
    cash_amount = min(cash_amount, Decimal(order.total))
    _settle_cash(db, order, conn, cash_amount)
    order.cash_amount = cash_amount
    db.flush()
    return order


# ── تسویه‌ی آنلاین (M5) ────────────────────────────────────────────────
def _money_method(db: Session) -> tuple[str, UUID | None]:
    """روشِ واریز برای تسویه: اگر بانکی تعریف شده «bank» + شناسه‌اش، وگرنه «cash» (درونِ scope)."""
    bank = db.query(BankAccount).order_by(BankAccount.created_at.asc()).first()
    if bank is not None:
        return "bank", bank.id
    return "cash", None


def _active_gateway(db: Session) -> PaymentGateway | None:
    """درگاهِ فعالِ مستأجرِ جاری با کمترین sort (درونِ scope؛ PaymentGateway RLS‌دار است)."""
    return (
        db.query(PaymentGateway)
        .filter(PaymentGateway.is_active.is_(True), PaymentGateway.merchant_id != "")
        .order_by(PaymentGateway.sort.asc(), PaymentGateway.created_at.asc())
        .first()
    )


def _gateway_for(db: Session, provider: str) -> PaymentGateway | None:
    return (
        db.query(PaymentGateway)
        .filter(
            PaymentGateway.is_active.is_(True),
            PaymentGateway.merchant_id != "",
            PaymentGateway.provider == provider,
        )
        .first()
    )


def get_retailer_order(db: Session, retailer_tenant_id: UUID, order_id: UUID) -> MarketplaceOrder:
    order = (
        _order_query(db)
        .filter(MarketplaceOrder.id == order_id, MarketplaceOrder.retailer_tenant_id == retailer_tenant_id)
        .first()
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش یافت نشد")
    return order


def start_order_payment(db: Session, order: MarketplaceOrder, callback_base: str) -> str:
    """پرداختِ آنلاین با درگاهِ **خودِ پخش‌کننده** را شروع و لینکِ درگاه را برمی‌گرداند."""
    if order.settlement_mode != "online":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این سفارش اعتباری است و پرداختِ آنلاین ندارد")
    if order.status != "placed" or order.payment_status == "paid":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این سفارش قابلِ پرداخت نیست")

    with tenant_scope(db, order.distributor_tenant_id):
        gateway = _active_gateway(db)
        if gateway is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "پخش‌کننده درگاهِ پرداختِ آنلاینِ فعالی ندارد")
        provider = get_provider(gateway.provider)
        if provider is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "درگاهِ ناشناخته")
        sandbox = bool((gateway.config or {}).get("sandbox", False))
        callback_url = f"{callback_base}/api/marketplace/pay/callback?order={order.id}&provider={gateway.provider}"
        try:
            result = provider.start(
                merchant_id=gateway.merchant_id,
                amount_rial=int(order.total),
                callback_url=callback_url,
                description=f"سفارشِ بازار #{order.order_number}",
                mobile="",
                email="",
                order_ref=str(order.order_number),
                sandbox=sandbox,
            )
        except ProviderError as err:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(err))
        except Exception:  # noqa: BLE001 - httpx و غیره
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "خطا در اتصال به درگاهِ پرداخت")
        order.payment_authority = result.authority
        order.payment_provider = gateway.provider
    db.flush()
    return result.redirect_url


def verify_online_payment(db: Session, order: MarketplaceOrder, provider_key: str, authority: str) -> bool:
    """پرداخت را با درگاهِ پخش‌کننده verify و در صورتِ موفقیت سفارش را نهایی + تسویه می‌کند.

    idempotent: اگر قبلاً پرداخت‌شده/تأییدشده باشد، دوباره فاکتور/تسویه نمی‌سازد.
    """
    if order.payment_status == "paid" or order.status == "confirmed":
        return True
    if not authority or order.payment_authority != authority:
        return False

    provider = get_provider(provider_key)
    if provider is None:
        return False
    with tenant_scope(db, order.distributor_tenant_id):
        gateway = _gateway_for(db, provider_key)
        if gateway is None:
            return False
        sandbox = bool((gateway.config or {}).get("sandbox", False))
        try:
            ok, ref = provider.verify(
                merchant_id=gateway.merchant_id,
                amount_rial=int(order.total),
                authority=authority,
                order_ref=str(order.order_number),
                sandbox=sandbox,
            )
        except Exception:  # noqa: BLE001
            return False
    if not ok:
        return False

    _finalize_paid_order(db, order, ref)
    return True


def _finalize_paid_order(db: Session, order: MarketplaceOrder, ref: str) -> None:
    """سفارشِ آنلاینِ پرداخت‌شده را نهایی می‌کند: پستِ دوطرفه + تسویه‌ی خزانه (مانده صفر)."""
    distributor_id = order.distributor_tenant_id
    retailer_id = order.retailer_tenant_id
    with tenant_scope(db, distributor_id):
        distributor_user = _tenant_actor(db, distributor_id)

    conn = _fulfill(db, order, distributor_user)

    amount = Decimal(order.total)
    today = date.today()
    if amount > 0:
        # پول از راهِ درگاه گرفته شده؛ AR/AP را همان‌جا تسویه می‌کنیم تا مانده صفر شود.
        with tenant_scope(db, distributor_id):
            method, bank_id = _money_method(db)
            treasury.create_receipt(
                db,
                TreasuryTransactionIn(
                    transaction_date=today,
                    contact_id=conn.distributor_customer_contact_id,
                    amount=amount,
                    method=method,
                    bank_account_id=bank_id,
                    description=f"تسویه‌ی آنلاینِ سفارشِ بازار #{order.order_number}",
                ),
                _tenant_actor(db, distributor_id),
            )
        with tenant_scope(db, retailer_id):
            method, bank_id = _money_method(db)
            treasury.create_payment(
                db,
                TreasuryTransactionIn(
                    transaction_date=today,
                    contact_id=conn.retailer_supplier_contact_id,
                    amount=amount,
                    method=method,
                    bank_account_id=bank_id,
                    description=f"پرداختِ آنلاینِ سفارشِ بازار #{order.order_number}",
                ),
                _tenant_actor(db, retailer_id),
            )

    order.payment_status = "paid"
    order.payment_ref = ref or ""
    order.status = "confirmed"
    order.cash_amount = amount  # آنلاین = کاملاً نقد تسویه شده
    db.flush()


def _settle_cash(db: Session, order: MarketplaceOrder, conn: MarketplaceConnection, cash_amount: Decimal) -> None:
    """سهمِ نقدِ سفارش را در خزانه‌ی هر دو طرف ثبت می‌کند (هنگام تأیید توسطِ پخش‌کننده):
    دریافتِ نقدِ پخش‌کننده + پرداختِ نقدِ فروشگاه. مانده‌ی باقی‌مانده اعتباری/طلب می‌ماند.
    الگو دقیقاً مثلِ تسویه‌ی آنلاین است، فقط مبلغ جزئی و بابتِ «نقد».
    """
    cash_amount = Decimal(cash_amount)
    if cash_amount <= 0:
        return
    today = date.today()
    tag = f"سفارشِ بازار #{order.order_number}"
    with tenant_scope(db, order.distributor_tenant_id):
        method, bank_id = _money_method(db)
        treasury.create_receipt(
            db,
            TreasuryTransactionIn(
                transaction_date=today,
                contact_id=conn.distributor_customer_contact_id,
                amount=cash_amount,
                method=method,
                bank_account_id=bank_id,
                description=f"دریافتِ نقدیِ {tag}",
            ),
            _tenant_actor(db, order.distributor_tenant_id),
        )
    with tenant_scope(db, order.retailer_tenant_id):
        method, bank_id = _money_method(db)
        treasury.create_payment(
            db,
            TreasuryTransactionIn(
                transaction_date=today,
                contact_id=conn.retailer_supplier_contact_id,
                amount=cash_amount,
                method=method,
                bank_account_id=bank_id,
                description=f"پرداختِ نقدیِ {tag}",
            ),
            _tenant_actor(db, order.retailer_tenant_id),
        )


def reject_order(db: Session, distributor_tenant_id: UUID, order_id: UUID) -> MarketplaceOrder:
    order = (
        _order_query(db)
        .filter(MarketplaceOrder.id == order_id, MarketplaceOrder.distributor_tenant_id == distributor_tenant_id)
        .with_for_update()
        .first()
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش یافت نشد")
    if order.status == "confirmed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سفارشِ تأییدشده قابلِ رد نیست")
    order.status = "rejected"
    db.flush()
    return order


def order_dict(db: Session, order: MarketplaceOrder, viewer_tenant_id: UUID | None = None) -> dict:
    # عکسِ نخستِ هر ردیف از روی لیستینگ (snapshot نمی‌شود تا سبک بماند). لیستینگ
    # جدولِ سراسری است، پس از نشستِ هر مستأجری خواندنش مجاز است؛ اگر لیستینگ بعداً
    # حذف شده باشد (`listing_id` = NULL) عکس هم نیست — رفتارِ درست همان None است.
    listing_ids = [ln.listing_id for ln in order.lines if ln.listing_id is not None]
    thumb: dict = {}
    if listing_ids:
        for lid, images in (
            db.query(MarketplaceListing.id, MarketplaceListing.images)
            .filter(MarketplaceListing.id.in_(listing_ids))
            .all()
        ):
            thumb[lid] = (images or [None])[0]
    # گفتگوی سفارش: خوانده‌نشده و آخرین پیام برای سمتِ بیننده (اگر مشخص باشد).
    unread = 0
    last = _last_order_message(db, order.id)
    if viewer_tenant_id is not None:
        if viewer_tenant_id == order.distributor_tenant_id:
            unread = order_unread_count(db, order, "distributor")
        elif viewer_tenant_id == order.retailer_tenant_id:
            unread = order_unread_count(db, order, "retailer")
    # سیاستِ مرجوعیِ پخش‌کننده (تا فروشگاه هنگامِ ثبتِ مرجوعی ببیندش).
    dsettings = (
        db.query(MarketplaceSettings)
        .filter(MarketplaceSettings.distributor_tenant_id == order.distributor_tenant_id)
        .first()
    )
    return {
        "id": order.id,
        "unread_count": unread,
        "last_message_at": last.created_at if last else None,
        "last_message_preview": (last.body[:80] if last else ""),
        "distributor_tenant_id": order.distributor_tenant_id,
        "retailer_tenant_id": order.retailer_tenant_id,
        "distributor_name": distributor_display_name(db, order.distributor_tenant_id),
        "retailer_name": _tenant_name(db, order.retailer_tenant_id),
        "order_number": order.order_number,
        "status": order.status,
        "settlement_mode": order.settlement_mode,
        "payment_status": order.payment_status,
        "note": order.note,
        "subtotal": order.subtotal,
        "total": order.total,
        "cash_amount": order.cash_amount,
        "return_policy": (dsettings.return_policy if dsettings else ""),
        "return_window_days": (dsettings.return_window_days if dsettings else 0),
        "distributor_sales_invoice_id": order.distributor_sales_invoice_id,
        "retailer_purchase_invoice_id": order.retailer_purchase_invoice_id,
        "lines": [
            {
                "id": ln.id,
                "listing_id": ln.listing_id,
                "title": ln.title,
                "unit_price": ln.unit_price,
                "qty": ln.qty,
                "line_total": ln.line_total,
                "image": thumb.get(ln.listing_id),
            }
            for ln in order.lines
        ],
    }


# ══════════ کمیسیونِ پلتفرم (۲٪) ══════════════════════════════════════════
def _commission_rate() -> Decimal:
    return Decimal(str(get_app_settings().marketplace_commission_rate))


def _current_period() -> str:
    """ماهِ شمسیِ جاری به شکلِ ASCIIِ مرتب‌شونده «1405-05»."""
    jy, jm, _ = gregorian_to_jalali(date.today())
    return f"{jy:04d}-{jm:02d}"


def _record_commission(db: Session, order: MarketplaceOrder) -> MarketplaceCommission:
    """کمیسیونِ ۲٪ روی یک سفارشِ قطعی‌شده — idempotent (یک رکورد به‌ازای هر سفارش).

    سراسری است (بدونِ RLS) و هیچ سندی در دفترِ پخش‌کننده نمی‌زند؛ فقط دفترِ پلتفرم.
    """
    existing = db.query(MarketplaceCommission).filter_by(order_id=order.id).first()
    if existing is not None:
        return existing
    rate = _commission_rate()
    base = Decimal(order.total)
    amount = (base * rate).to_integral_value(rounding=ROUND_HALF_UP)
    row = MarketplaceCommission(
        order_id=order.id,
        distributor_tenant_id=order.distributor_tenant_id,
        period=_current_period(),
        base_amount=base,
        rate=rate,
        amount=amount,
        status="pending",
    )
    db.add(row)
    db.flush()
    return row


def commission_summary(db: Session, distributor_tenant_id: UUID | None = None) -> list[dict]:
    """جمعِ کمیسیون به‌تفکیکِ (پخش‌کننده، ماه). اگر distributor بدهی، فقط همان."""
    pending_amt = func.coalesce(
        func.sum(case((MarketplaceCommission.status == "pending", MarketplaceCommission.amount), else_=0)),
        0,
    )
    q = db.query(
        MarketplaceCommission.distributor_tenant_id.label("distributor_tenant_id"),
        MarketplaceCommission.period.label("period"),
        func.count().label("order_count"),
        func.coalesce(func.sum(MarketplaceCommission.base_amount), 0).label("total_base"),
        func.coalesce(func.sum(MarketplaceCommission.amount), 0).label("total_amount"),
        pending_amt.label("pending_amount"),
    )
    if distributor_tenant_id is not None:
        q = q.filter(MarketplaceCommission.distributor_tenant_id == distributor_tenant_id)
    q = q.group_by(
        MarketplaceCommission.distributor_tenant_id, MarketplaceCommission.period
    ).order_by(MarketplaceCommission.period.desc())

    out: list[dict] = []
    for r in q.all():
        pending = Decimal(r.pending_amount)
        total = Decimal(r.total_amount)
        out.append(
            {
                "distributor_tenant_id": r.distributor_tenant_id,
                "distributor_name": distributor_display_name(db, r.distributor_tenant_id),
                "period": r.period,
                "order_count": int(r.order_count),
                "total_base": int(r.total_base),
                "total_amount": int(total),
                "pending_amount": int(pending),
                "settled_amount": int(total - pending),
                "status": "settled" if pending == 0 else "pending",
            }
        )
    return out


def commission_overview(db: Session) -> dict:
    """جمعِ کلِ کمیسیون‌ها برای سرصفحه‌ی پنلِ سوپرادمین."""
    total = Decimal(db.query(func.coalesce(func.sum(MarketplaceCommission.amount), 0)).scalar() or 0)
    pending = Decimal(
        db.query(func.coalesce(func.sum(MarketplaceCommission.amount), 0))
        .filter(MarketplaceCommission.status == "pending")
        .scalar()
        or 0
    )
    distributor_count = (
        db.query(func.count(func.distinct(MarketplaceCommission.distributor_tenant_id))).scalar() or 0
    )
    return {
        "total_amount": int(total),
        "pending_amount": int(pending),
        "settled_amount": int(total - pending),
        "distributor_count": int(distributor_count),
        "rate": float(_commission_rate()),
    }


def settle_commission_period(
    db: Session, distributor_tenant_id: UUID, period: str, note: str = ""
) -> dict:
    """تسویه‌ی دستی: همه‌ی کمیسیون‌های pendingِ (پخش‌کننده، ماه) را settled می‌کند.

    فقط سوپرادمین صدا می‌زند (گاردِ روتر). idempotent: ردیف‌های settled دوباره لمس نمی‌شوند.
    """
    rows = (
        db.query(MarketplaceCommission)
        .filter(
            MarketplaceCommission.distributor_tenant_id == distributor_tenant_id,
            MarketplaceCommission.period == period,
            MarketplaceCommission.status == "pending",
        )
        .all()
    )
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کمیسیونِ پرداخت‌نشده‌ای برای این ماه نیست")
    now = datetime.now(timezone.utc)
    clean_note = (note or "").strip()[:300]
    total = Decimal(0)
    for r in rows:
        r.status = "settled"
        r.settled_at = now
        r.settle_note = clean_note
        total += Decimal(r.amount)
    db.flush()
    return {
        "distributor_tenant_id": distributor_tenant_id,
        "period": period,
        "count": len(rows),
        "amount": int(total),
    }


# ── زونِ ارسال (پخش‌کننده) ──────────────────────────────────────────────
def list_zones(db: Session, distributor_tenant_id: UUID) -> list[dict]:
    """زون‌های این پخش‌کننده + تعدادِ فروشگاه‌های هر زون."""
    zones = (
        db.query(MarketplaceZone)
        .filter(MarketplaceZone.distributor_tenant_id == distributor_tenant_id)
        .order_by(MarketplaceZone.name)
        .all()
    )
    counts = dict(
        db.query(MarketplaceConnection.zone_id, func.count(MarketplaceConnection.id))
        .filter(
            MarketplaceConnection.distributor_tenant_id == distributor_tenant_id,
            MarketplaceConnection.zone_id.isnot(None),
        )
        .group_by(MarketplaceConnection.zone_id)
        .all()
    )
    return [
        {"id": z.id, "name": z.name, "notes": z.notes, "connection_count": int(counts.get(z.id, 0))}
        for z in zones
    ]


def _get_own_zone(db: Session, distributor_tenant_id: UUID, zone_id: UUID) -> MarketplaceZone:
    z = (
        db.query(MarketplaceZone)
        .filter(MarketplaceZone.id == zone_id, MarketplaceZone.distributor_tenant_id == distributor_tenant_id)
        .first()
    )
    if z is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "زون یافت نشد")
    return z


def create_zone(db: Session, distributor_tenant_id: UUID, data) -> MarketplaceZone:
    dup = (
        db.query(MarketplaceZone.id)
        .filter(MarketplaceZone.distributor_tenant_id == distributor_tenant_id, MarketplaceZone.name == data.name)
        .first()
    )
    if dup is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "زونی با این نام از قبل هست")
    z = MarketplaceZone(distributor_tenant_id=distributor_tenant_id, name=data.name, notes=data.notes.strip())
    db.add(z)
    db.flush()
    return z


def update_zone(db: Session, distributor_tenant_id: UUID, zone_id: UUID, data) -> MarketplaceZone:
    z = _get_own_zone(db, distributor_tenant_id, zone_id)
    dup = (
        db.query(MarketplaceZone.id)
        .filter(
            MarketplaceZone.distributor_tenant_id == distributor_tenant_id,
            MarketplaceZone.name == data.name,
            MarketplaceZone.id != zone_id,
        )
        .first()
    )
    if dup is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "زونی با این نام از قبل هست")
    z.name = data.name
    z.notes = data.notes.strip()
    db.flush()
    return z


def delete_zone(db: Session, distributor_tenant_id: UUID, zone_id: UUID) -> None:
    z = _get_own_zone(db, distributor_tenant_id, zone_id)
    db.delete(z)  # اتصال‌های این زون با ondelete SET NULL بدونِ زون می‌شوند
    db.flush()


def assign_zone(db: Session, distributor_tenant_id: UUID, connection_id: UUID, zone_id: UUID | None) -> MarketplaceConnection:
    """پخش‌کننده یک فروشگاهِ متصل را در یک زون می‌گذارد (یا زون را برمی‌دارد)."""
    conn = (
        db.query(MarketplaceConnection)
        .filter(
            MarketplaceConnection.id == connection_id,
            MarketplaceConnection.distributor_tenant_id == distributor_tenant_id,
        )
        .first()
    )
    if conn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اتصال یافت نشد")
    if zone_id is not None:
        _get_own_zone(db, distributor_tenant_id, zone_id)  # باید مالِ خودِ پخش‌کننده باشد
    conn.zone_id = zone_id
    db.flush()
    return conn


# ── مرجوعیِ بازار (فروشگاه درخواست، پخش‌کننده تأیید) ─────────────────────
def _get_own_order(db: Session, order_id: UUID, *, retailer_tenant_id: UUID | None = None,
                   distributor_tenant_id: UUID | None = None) -> MarketplaceOrder:
    q = db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id)
    if retailer_tenant_id is not None:
        q = q.filter(MarketplaceOrder.retailer_tenant_id == retailer_tenant_id)
    if distributor_tenant_id is not None:
        q = q.filter(MarketplaceOrder.distributor_tenant_id == distributor_tenant_id)
    order = q.first()
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش یافت نشد")
    return order


def _next_return_number(db: Session, distributor_tenant_id: UUID) -> int:
    s = get_settings(db, distributor_tenant_id)
    n = s.next_return_number or 1
    s.next_return_number = n + 1
    db.flush()
    return n


def _returned_qty_by_line(db: Session, order_id: UUID) -> dict[UUID, Decimal]:
    """مجموعِ مقدارِ مرجوع‌شده (درخواست‌شده یا تأییدشده، نه ردشده) به‌ازای هر ردیفِ سفارش."""
    rows = (
        db.query(MarketplaceReturnLine.order_line_id, func.coalesce(func.sum(MarketplaceReturnLine.qty), 0))
        .join(MarketplaceReturn, MarketplaceReturn.id == MarketplaceReturnLine.return_id)
        .filter(MarketplaceReturn.order_id == order_id, MarketplaceReturn.status != "rejected")
        .group_by(MarketplaceReturnLine.order_line_id)
        .all()
    )
    return {lid: Decimal(q) for lid, q in rows}


def request_return(db: Session, retailer_tenant_id: UUID, data) -> MarketplaceReturn:
    """فروشگاه روی یک سفارشِ تأییدشده درخواستِ مرجوعی می‌دهد (کامل یا پارشال)."""
    order = _get_own_order(db, data.order_id, retailer_tenant_id=retailer_tenant_id)
    if order.status != "confirmed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مرجوعی فقط روی سفارشِ تأییدشده ممکن است")

    settings = get_settings(db, order.distributor_tenant_id)
    if settings.return_window_days and settings.return_window_days > 0:
        confirmed_at = order.updated_at or order.created_at
        if confirmed_at is not None:
            elapsed = (datetime.now(timezone.utc) - confirmed_at).days
            if elapsed > settings.return_window_days:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"مهلتِ مرجوعیِ این پخش‌کننده {settings.return_window_days} روز است و گذشته",
                )

    lines_by_id = {ol.id: ol for ol in order.lines}
    already = _returned_qty_by_line(db, order.id)
    ret = MarketplaceReturn(
        order_id=order.id,
        distributor_tenant_id=order.distributor_tenant_id,
        retailer_tenant_id=retailer_tenant_id,
        return_number=_next_return_number(db, order.distributor_tenant_id),
        status="requested",
        reason=(data.reason or "").strip(),
    )
    total = Decimal(0)
    for rl in data.lines:
        ol = lines_by_id.get(rl.order_line_id)
        if ol is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "ردیفِ مرجوعی به این سفارش تعلق ندارد")
        remaining = Decimal(ol.qty) - already.get(ol.id, Decimal(0))
        if rl.qty > remaining:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"مقدارِ مرجوعیِ «{ol.title}» از باقی‌مانده‌ی قابلِ‌مرجوع ({remaining}) بیشتر است",
            )
        line_total = (Decimal(ol.unit_price) * rl.qty).to_integral_value()
        total += line_total
        ret.lines.append(
            MarketplaceReturnLine(
                order_line_id=ol.id, title=ol.title, unit_price=ol.unit_price, qty=rl.qty, line_total=line_total
            )
        )
    ret.total = total
    db.add(ret)
    db.flush()
    return ret


def _explode_return(db: Session, order: MarketplaceOrder, ret: MarketplaceReturn) -> dict[UUID, Decimal]:
    """ردیف‌های مرجوعی را به «کالای پخش‌کننده → مقدار» باز می‌کند (مثلِ _explode_order برای مقدارِ مرجوع)."""
    lines_by_id = {ol.id: ol for ol in order.lines}
    listing_ids = {lines_by_id[rl.order_line_id].listing_id for rl in ret.lines if lines_by_id.get(rl.order_line_id)}
    listings = {l.id: l for l in db.query(MarketplaceListing).filter(MarketplaceListing.id.in_(listing_ids)).all()}
    dist_items: dict[UUID, Decimal] = {}
    for rl in ret.lines:
        ol = lines_by_id.get(rl.order_line_id)
        listing = listings.get(ol.listing_id) if ol else None
        if listing is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "لیستینگِ این قلم دیگر موجود نیست؛ مرجوعیِ خودکار ممکن نیست")
        for comp in listing.components:
            dist_items[comp.distributor_item_id] = dist_items.get(comp.distributor_item_id, Decimal(0)) + Decimal(comp.qty) * Decimal(rl.qty)
    return dist_items


def approve_return(db: Session, distributor_tenant_id: UUID, distributor_user: User, return_id: UUID) -> MarketplaceReturn:
    """پخش‌کننده مرجوعی را تأیید می‌کند: برگشتِ فروش (دفترِ پخش‌کننده) + برگشتِ خرید (دفترِ فروشگاه)."""
    ret = (
        db.query(MarketplaceReturn)
        .filter(MarketplaceReturn.id == return_id, MarketplaceReturn.distributor_tenant_id == distributor_tenant_id)
        .first()
    )
    if ret is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مرجوعی یافت نشد")
    if ret.status != "requested":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این مرجوعی قبلاً پردازش شده است")
    order = db.get(MarketplaceOrder, ret.order_id)
    if order is None or order.distributor_sales_invoice_id is None or order.retailer_purchase_invoice_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فاکتورهای سفارش برای مرجوعی در دسترس نیست")

    dist_items = _explode_return(db, order, ret)
    today = date.today()
    tag = f"مرجوعیِ بازار #{ret.return_number}"

    with tenant_scope(db, ret.distributor_tenant_id):
        sr = post_sales_return(
            db,
            SalesReturnIn(
                return_date=today,
                sales_invoice_id=order.distributor_sales_invoice_id,
                description=tag,
                lines=[SalesReturnLineIn(item_id=iid, qty=qty) for iid, qty in dist_items.items()],
            ),
            distributor_user,
        )
        sales_return_id = sr.id

    with tenant_scope(db, ret.retailer_tenant_id):
        retailer_user = _tenant_actor(db, ret.retailer_tenant_id)
        ret_lines = []
        for dist_item_id, qty in dist_items.items():
            link = (
                db.query(MarketplaceItemLink)
                .filter(
                    MarketplaceItemLink.retailer_tenant_id == ret.retailer_tenant_id,
                    MarketplaceItemLink.distributor_item_id == dist_item_id,
                )
                .first()
            )
            if link is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "کالای متناظرِ فروشگاه برای مرجوعی پیدا نشد")
            ret_lines.append(PurchaseReturnLineIn(item_id=link.retailer_item_id, qty=qty))
        pr = post_purchase_return(
            db,
            PurchaseReturnIn(
                return_date=today,
                purchase_invoice_id=order.retailer_purchase_invoice_id,
                description=tag,
                lines=ret_lines,
            ),
            retailer_user,
        )
        purchase_return_id = pr.id

    ret.distributor_sales_return_id = sales_return_id
    ret.retailer_purchase_return_id = purchase_return_id
    ret.status = "approved"
    db.flush()
    return ret


def reject_return(db: Session, distributor_tenant_id: UUID, return_id: UUID, response_note: str) -> MarketplaceReturn:
    ret = (
        db.query(MarketplaceReturn)
        .filter(MarketplaceReturn.id == return_id, MarketplaceReturn.distributor_tenant_id == distributor_tenant_id)
        .first()
    )
    if ret is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مرجوعی یافت نشد")
    if ret.status != "requested":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این مرجوعی قبلاً پردازش شده است")
    ret.status = "rejected"
    ret.response_note = (response_note or "").strip()
    db.flush()
    return ret


def list_returns(db: Session, *, distributor_tenant_id: UUID | None = None,
                 retailer_tenant_id: UUID | None = None) -> list[MarketplaceReturn]:
    q = db.query(MarketplaceReturn)
    if distributor_tenant_id is not None:
        q = q.filter(MarketplaceReturn.distributor_tenant_id == distributor_tenant_id)
    if retailer_tenant_id is not None:
        q = q.filter(MarketplaceReturn.retailer_tenant_id == retailer_tenant_id)
    return q.order_by(MarketplaceReturn.created_at.desc()).all()


def return_dict(db: Session, ret: MarketplaceReturn) -> dict:
    order = db.get(MarketplaceOrder, ret.order_id)
    return {
        "id": ret.id,
        "order_id": ret.order_id,
        "order_number": order.order_number if order else 0,
        "distributor_tenant_id": ret.distributor_tenant_id,
        "retailer_tenant_id": ret.retailer_tenant_id,
        "distributor_name": distributor_display_name(db, ret.distributor_tenant_id),
        "retailer_name": _tenant_name(db, ret.retailer_tenant_id),
        "return_number": ret.return_number,
        "status": ret.status,
        "reason": ret.reason,
        "response_note": ret.response_note,
        "total": ret.total,
        "created_at": ret.created_at,
        "lines": [
            {
                "order_line_id": rl.order_line_id,
                "title": rl.title,
                "unit_price": rl.unit_price,
                "qty": rl.qty,
                "line_total": rl.line_total,
            }
            for rl in ret.lines
        ],
    }
