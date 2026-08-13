"""بازارِ عمده‌فروشی — سرویس.

نکته‌ی امنیتیِ کلیدی: جدول‌های بازار سراسری‌اند (بدونِ RLS)، پس **هر** کوئری اینجا باید
صریحاً با `distributor_tenant_id`/`retailer_tenant_id` فیلتر شود — RLS اینجا محافظت نمی‌کند.
اما اعتبارسنجیِ «کالا مالِ خودِ پخش‌کننده است» از RLS استفاده می‌کند: چون در نشستِ بسته‌شده
به مستأجرِ پخش‌کننده، کوئریِ `Item` فقط کالاهای خودش را برمی‌گرداند.
"""
from datetime import date
from decimal import ROUND_CEILING, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.banking import BankAccount
from app.models.inventory import Contact, Item, Warehouse
from app.models.marketplace import (
    MarketplaceConnection,
    MarketplaceItemLink,
    MarketplaceListing,
    MarketplaceListingComponent,
    MarketplaceOrder,
    MarketplaceOrderLine,
    MarketplaceSettings,
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
from app.schemas.treasury import TreasuryTransactionIn
from app.services import treasury
from app.services.inventory import _allocate_discount, post_purchase_invoice, post_sales_invoice
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
        currency_code=data.currency_code.strip(),
        description=data.description,
        images=data.images or [],
        category=data.category.strip(),
        is_published=data.is_published,
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
    listing.currency_code = data.currency_code.strip()
    listing.description = data.description
    listing.images = data.images or []
    listing.category = data.category.strip()
    listing.is_published = data.is_published
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
        "currency_code": listing.currency_code,
        "description": listing.description,
        "images": listing.images or [],
        "category": listing.category,
        "is_published": listing.is_published,
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


def connection_dict(db: Session, conn: MarketplaceConnection) -> dict:
    return {
        "id": conn.id,
        "distributor_tenant_id": conn.distributor_tenant_id,
        "retailer_tenant_id": conn.retailer_tenant_id,
        "distributor_name": distributor_display_name(db, conn.distributor_tenant_id),
        "retailer_name": _tenant_name(db, conn.retailer_tenant_id),
        "status": conn.status,
        "requested_by": conn.requested_by,
    }


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
                "currency_code": l.currency_code,
                "description": l.description,
                "images": l.images or [],
                "category": l.category,
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
        unit_price = Decimal(listing.wholesale_price)
        line_total = unit_price * Decimal(ln.qty)
        subtotal += line_total
        order_lines.append(
            MarketplaceOrderLine(
                listing_id=listing.id,
                title=listing.title,
                unit_price=unit_price,
                qty=Decimal(ln.qty),
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


def _resolve_retailer_item(
    db: Session,
    retailer_tenant_id: UUID,
    distributor_tenant_id: UUID,
    distributor_item_id: UUID,
    name: str,
    unit: str,
    price: Decimal,
) -> Item:
    """کالای متناظرِ فروشگاه را برمی‌گرداند؛ بارِ اول می‌سازد و لینک می‌کند (درونِ scopeِ فروشگاه).

    نگاشتِ ضدِتکرار در `marketplace_item_links` است: هر کالای پخش‌کننده در انبارِ فروشگاه
    فقط یک کالای متناظر می‌سازد؛ سفارش‌های بعدی همان کالا را پیدا و تعدادش را اضافه می‌کنند.
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
            return item

    item = Item(
        sku=f"MP-{distributor_item_id.hex}",
        name=(name or "کالای بازار"),
        unit=(unit or "عدد"),
        sales_price=price,
        average_cost=0,
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
        for f in fulfillment:
            ret_item = _resolve_retailer_item(
                db, retailer_id, distributor_id, f["distributor_item_id"], f["name"], f["unit"], f["unit_price"]
            )
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

    order.distributor_sales_invoice_id = sales_invoice_id
    order.retailer_purchase_invoice_id = purchase_invoice_id
    order.status = "confirmed"
    db.flush()
    return conn


def confirm_order(db: Session, distributor_tenant_id: UUID, distributor_user: User, order_id: UUID) -> MarketplaceOrder:
    """پخش‌کننده سفارشِ اعتباری را تأیید می‌کند → پستِ دوطرفه.

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

    _fulfill(db, order, distributor_user)
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
    db.flush()


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


def order_dict(db: Session, order: MarketplaceOrder) -> dict:
    return {
        "id": order.id,
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
        "distributor_sales_invoice_id": order.distributor_sales_invoice_id,
        "retailer_purchase_invoice_id": order.retailer_purchase_invoice_id,
        "lines": [
            {
                "listing_id": ln.listing_id,
                "title": ln.title,
                "unit_price": ln.unit_price,
                "qty": ln.qty,
                "line_total": ln.line_total,
            }
            for ln in order.lines
        ],
    }
