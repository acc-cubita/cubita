"""Hybrid order fulfillment: cloud market broker, each party's own ledger."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.advanced_inventory import StockBatch
from app.models.enterprise_market_bridge import EnterpriseMarketCloudItemMap, EnterpriseMarketEvent, EnterpriseMarketLink
from app.models.inventory import Item
from app.models.marketplace import MarketplaceConnection, MarketplaceItemLink, MarketplaceListing, MarketplaceOrder, MarketplaceReturn
from app.models.user import User
from app.schemas.enterprise_market_bridge import MarketFinancialEvent, MarketFinancialLine
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.schemas.returns import PurchaseReturnIn, PurchaseReturnLineIn, SalesReturnIn, SalesReturnLineIn
from app.schemas.treasury import TreasuryTransactionIn
from app.services import marketplace as market, treasury
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.sales_invoices import finalize_immediate_sale
from app.services.returns import post_purchase_return, post_sales_return
from app.tenant_context import tenant_scope


def linked_parties(db: Session, order: MarketplaceOrder) -> dict[str, EnterpriseMarketLink]:
    links = db.query(EnterpriseMarketLink).filter(
        EnterpriseMarketLink.status == "active",
        EnterpriseMarketLink.cloud_tenant_id.in_((order.distributor_tenant_id, order.retailer_tenant_id)),
    ).all()
    return {
        "seller" if row.cloud_tenant_id == order.distributor_tenant_id else "buyer": row
        for row in links
    }


def _public_lines(db: Session, fulfillment: list[dict], *, seller_linked: bool) -> list[MarketFinancialLine]:
    item_ids = {row["distributor_item_id"] for row in fulfillment}
    maps = db.query(EnterpriseMarketCloudItemMap).filter(EnterpriseMarketCloudItemMap.cloud_item_id.in_(item_ids)).all()
    refs = {row.cloud_item_id: row.market_item_ref for row in maps}
    if seller_linked and any(item_id not in refs for item_id in item_ids):
        raise HTTPException(status.HTTP_409_CONFLICT, "شناسهٔ عمومی یکی از کالاهای فروشنده نگاشت نشده است")
    return [MarketFinancialLine(
        market_item_ref=refs.get(row["distributor_item_id"], row["distributor_item_id"]),
        name=row["name"], unit=row["unit"],
        qty=row["units"], unit_price=row["unit_price"], discount=row["discount"],
        consumer_price=row["consumer_price"],
    ) for row in fulfillment]


def _post_cash_side(db: Session, order: MarketplaceOrder, conn: MarketplaceConnection, side: str, amount: Decimal) -> None:
    if amount <= 0:
        return
    tenant_id = order.distributor_tenant_id if side == "seller" else order.retailer_tenant_id
    contact_id = conn.distributor_customer_contact_id if side == "seller" else conn.retailer_supplier_contact_id
    with tenant_scope(db, tenant_id):
        method, bank_id = market._money_method(db)
        payment = TreasuryTransactionIn(
            transaction_date=date.today(), contact_id=contact_id, amount=amount,
            method=method, bank_account_id=bank_id,
            description=f"تسویهٔ نقدی سفارش بازار #{order.order_number}",
        )
        actor = market._tenant_actor(db, tenant_id)
        if side == "seller":
            treasury.create_receipt(db, payment, actor)
        else:
            treasury.create_payment(db, payment, actor)


def _post_cloud_native_side(
    db: Session, order: MarketplaceOrder, conn: MarketplaceConnection,
    side: str, fulfillment: list[dict], distributor_user: User, cash_amount: Decimal,
) -> None:
    """One existing cloud account is posted here; linked party is never posted here."""
    tag = f"سفارشِ بازار #{order.order_number}"
    if side == "seller":
        with tenant_scope(db, order.distributor_tenant_id):
            customer = market._find_or_create_customer(db, conn, order.retailer_tenant_id)
            warehouse = market._default_warehouse(db, order.distributor_tenant_id)
            invoice = post_sales_invoice(
                db, SalesInvoiceIn(
                    invoice_date=date.today(), warehouse_id=warehouse.id,
                    contact_id=customer.id, description=tag,
                    lines=[SalesInvoiceLineIn(
                        item_id=row["distributor_item_id"], qty=row["units"],
                        unit_price=row["unit_price"], discount=row["discount"],
                    ) for row in fulfillment],
                ), distributor_user, move_inventory=False, issue_accounting=False,
            )
            finalize_immediate_sale(db, invoice, warehouse.id, distributor_user)
            order.distributor_sales_invoice_id = invoice.id
            market._release_order_stock(db, order, consumed=True)
    else:
        with tenant_scope(db, order.distributor_tenant_id):
            barcodes = {
                iid: bc for iid, bc in db.query(Item.id, Item.barcode).filter(
                    Item.id.in_({row["distributor_item_id"] for row in fulfillment})
                ).all()
            }
        with tenant_scope(db, order.retailer_tenant_id):
            actor = market._tenant_actor(db, order.retailer_tenant_id)
            supplier = market._find_or_create_supplier(db, conn, order.distributor_tenant_id)
            warehouse = market._default_warehouse(db, order.retailer_tenant_id)
            purchase_lines = []
            consumer_by_item: dict[UUID, Decimal] = {}
            for row in fulfillment:
                item = market._resolve_retailer_item(
                    db, order.retailer_tenant_id, order.distributor_tenant_id,
                    row["distributor_item_id"], row["name"], row["unit"], row["unit_price"],
                    barcode=barcodes.get(row["distributor_item_id"]),
                )
                if row["consumer_price"] > 0:
                    consumer_by_item[item.id] = row["consumer_price"]
                purchase_lines.append(PurchaseInvoiceLineIn(
                    item_id=item.id, qty=row["units"], unit_cost=row["unit_price"], discount=row["discount"],
                ))
            invoice = post_purchase_invoice(
                db, PurchaseInvoiceIn(
                    invoice_date=date.today(), warehouse_id=warehouse.id,
                    contact_id=supplier.id, description=tag, lines=purchase_lines,
                ), actor,
            )
            order.retailer_purchase_invoice_id = invoice.id
            if consumer_by_item:
                for batch in db.query(StockBatch).filter(StockBatch.source_id == invoice.id).all():
                    price = consumer_by_item.get(batch.item_id)
                    if price is not None:
                        batch.consumer_price = price
    _post_cash_side(db, order, conn, side, cash_amount)


def queue_fulfillment(db: Session, order: MarketplaceOrder, distributor_user: User, cash_amount: Decimal) -> None:
    """Called while order row is locked; no commission until both receipts posted."""
    links = linked_parties(db, order)
    if not links:
        raise HTTPException(status.HTTP_409_CONFLICT, "هیچ سمت سازمانی در این سفارش نیست")
    if order.settlement_mode == "online":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "درگاه آنلاین برای طرف سازمانی پشتیبانی نمی‌شود")
    existing = db.query(EnterpriseMarketEvent.id).filter(EnterpriseMarketEvent.operation_ref == order.id).first()
    if existing is not None:
        return
    conn = market._get_connection(db, order.distributor_tenant_id, order.retailer_tenant_id)
    if conn is None or conn.status != "approved":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "اتصال طرفین تأییدشده نیست")
    listing_ids = [line.listing_id for line in order.lines if line.listing_id is not None]
    listings = {row.id: row for row in db.query(MarketplaceListing).filter(MarketplaceListing.id.in_(listing_ids)).all()}
    fulfillment = market._explode_order(order, listings)
    lines = _public_lines(db, fulfillment, seller_linked="seller" in links)
    for side in ("seller", "buyer"):
        link = links.get(side)
        counterparty_id = order.retailer_tenant_id if side == "seller" else order.distributor_tenant_id
        event = MarketFinancialEvent(
            event_id=uuid.uuid4(), operation_ref=order.id, order_id=order.id,
            kind="order", side=side, counterparty_ref=counterparty_id,
            counterparty_name=market._tenant_name(db, counterparty_id),
            order_date=date.today(), order_number=order.order_number,
            cash_amount=cash_amount, lines=lines,
        )
        row = EnterpriseMarketEvent(
            id=event.event_id, link_id=(link or next(iter(links.values()))).id,
            operation_ref=order.id, order_id=order.id, side=side, kind="order",
            payload=event.model_dump(mode="json"),
            status="pending" if link is not None else "posted",
            posted_at=None if link is not None else datetime.now(timezone.utc),
        )
        db.add(row)
        if link is None:
            _post_cloud_native_side(db, order, conn, side, fulfillment, distributor_user, cash_amount)
    order.cash_amount = cash_amount
    order.status = "sync_pending"
    db.flush()


def _post_cloud_native_return_side(
    db: Session, order: MarketplaceOrder, ret: MarketplaceReturn,
    dist_items: dict[UUID, Decimal], side: str, distributor_user: User,
) -> None:
    tag = f"مرجوعی بازار #{ret.return_number}"
    if side == "seller":
        if order.distributor_sales_invoice_id is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "فاکتور فروش سفارش یافت نشد")
        with tenant_scope(db, order.distributor_tenant_id):
            document = post_sales_return(
                db, SalesReturnIn(
                    return_date=date.today(), sales_invoice_id=order.distributor_sales_invoice_id,
                    description=tag,
                    lines=[SalesReturnLineIn(item_id=item_id, qty=qty) for item_id, qty in dist_items.items()],
                ), distributor_user, physical=True,
            )
        ret.distributor_sales_return_id = document.id
    else:
        if order.retailer_purchase_invoice_id is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "فاکتور خرید سفارش یافت نشد")
        with tenant_scope(db, order.retailer_tenant_id):
            actor = market._tenant_actor(db, order.retailer_tenant_id)
            mapped = db.query(MarketplaceItemLink).filter(
                MarketplaceItemLink.retailer_tenant_id == order.retailer_tenant_id,
                MarketplaceItemLink.distributor_item_id.in_(dist_items),
            ).all()
            ids = {row.distributor_item_id: row.retailer_item_id for row in mapped}
            if len(ids) != len(dist_items):
                raise HTTPException(status.HTTP_409_CONFLICT, "کالای متناظر برای مرجوعی یافت نشد")
            document = post_purchase_return(
                db, PurchaseReturnIn(
                    return_date=date.today(), purchase_invoice_id=order.retailer_purchase_invoice_id,
                    description=tag,
                    lines=[PurchaseReturnLineIn(item_id=ids[item_id], qty=qty) for item_id, qty in dist_items.items()],
                ), actor,
            )
        ret.retailer_purchase_return_id = document.id


def queue_return(db: Session, order: MarketplaceOrder, ret: MarketplaceReturn, distributor_user: User) -> None:
    """Post native side now; linked sides acknowledge local return documents later."""
    links = linked_parties(db, order)
    if not links:
        raise HTTPException(status.HTTP_409_CONFLICT, "هیچ سمت سازمانی در این مرجوعی نیست")
    original = db.query(EnterpriseMarketEvent).filter(
        EnterpriseMarketEvent.operation_ref == order.id,
        EnterpriseMarketEvent.kind == "order",
    ).all()
    if len(original) != 2 or any(row.status != "posted" for row in original):
        raise HTTPException(status.HTTP_409_CONFLICT, "ثبت مالی سفارش هنوز کامل نشده است")
    if db.query(EnterpriseMarketEvent.id).filter(EnterpriseMarketEvent.operation_ref == ret.id).first():
        return
    dist_items = market._explode_return(db, order, ret)
    with tenant_scope(db, order.distributor_tenant_id):
        public_items = {
            row.id: row for row in db.query(Item).filter(Item.id.in_(dist_items)).all()
        }
    if len(public_items) != len(dist_items):
        raise HTTPException(status.HTTP_409_CONFLICT, "اطلاعات عمومی یکی از اقلام مرجوعی در دسترس نیست")
    fulfillment = [{
        "distributor_item_id": item_id, "name": public_items[item_id].name,
        "unit": public_items[item_id].unit, "units": qty,
        # The original local invoice determines the return valuation; the
        # public return event only needs item/quantity and total for display.
        "unit_price": Decimal(0), "discount": Decimal(0), "consumer_price": Decimal(0),
    } for item_id, qty in dist_items.items()]
    lines = _public_lines(db, fulfillment, seller_linked="seller" in links)
    for side in ("seller", "buyer"):
        link = links.get(side)
        counterparty_id = order.retailer_tenant_id if side == "seller" else order.distributor_tenant_id
        event = MarketFinancialEvent(
            event_id=uuid.uuid4(), operation_ref=ret.id, order_id=order.id,
            kind="return", return_id=ret.id, return_number=ret.return_number,
            return_total=Decimal(ret.total), side=side, counterparty_ref=counterparty_id,
            counterparty_name=market._tenant_name(db, counterparty_id),
            order_date=date.today(), order_number=order.order_number,
            cash_amount=Decimal(0), lines=lines,
        )
        db.add(EnterpriseMarketEvent(
            id=event.event_id, link_id=(link or next(iter(links.values()))).id,
            operation_ref=ret.id, order_id=order.id, side=side, kind="return",
            payload=event.model_dump(mode="json"),
            status="pending" if link else "posted",
            posted_at=None if link else datetime.now(timezone.utc),
        ))
        if link is None:
            _post_cloud_native_return_side(db, order, ret, dist_items, side, distributor_user)
    ret.status = "sync_pending"
    db.flush()
