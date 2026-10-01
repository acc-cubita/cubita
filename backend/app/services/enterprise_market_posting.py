"""Exactly-once local accounting for a cloud-market order event.

The VPS sends only the agreed trade and opaque market references. This service
resolves local item/contact/warehouse IDs inside the enterprise database and
returns only a status receipt.  A unique inbox row and the invoice live in one
transaction, so a retry after a lost HTTP response cannot create a second bill.
"""

import logging
import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.advanced_inventory import StockBatch
from app.models.enterprise_market_bridge import (
    EnterpriseMarketCounterpartyMap, EnterpriseMarketItemMap, EnterpriseMarketLocalPosting,
)
from app.models.inventory import Contact, Item
from app.schemas.enterprise_market_bridge import MarketFinancialEvent, MarketPostingReceipt
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.schemas.returns import PurchaseReturnIn, PurchaseReturnLineIn, SalesReturnIn, SalesReturnLineIn
from app.schemas.treasury import TreasuryTransactionIn
from app.services import marketplace as marketplace_svc, treasury
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.sales_invoices import finalize_immediate_sale
from app.services.returns import post_purchase_return, post_sales_return

log = logging.getLogger(__name__)


class MappingMissing(ValueError):
    pass


def lock_local_finance(db: Session, tenant_id: UUID) -> None:
    # Different events may create the same item/contact mapping concurrently.
    # Repairs must take this same lock before checking historical use, or a
    # worker could post an invoice between that check and a mapping change.
    key = int.from_bytes(hashlib.sha256(b"cubita-market-finance:" + tenant_id.bytes).digest()[:8], "big", signed=True)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def _local_items(db: Session, tenant_id: UUID, event: MarketFinancialEvent) -> dict[UUID, Item]:
    refs = {line.market_item_ref for line in event.lines}
    maps = db.query(EnterpriseMarketItemMap).filter(
        EnterpriseMarketItemMap.tenant_id == tenant_id,
        EnterpriseMarketItemMap.market_item_ref.in_(refs),
    ).all()
    mapped_refs = {row.market_item_ref for row in maps}
    if len(maps) != len(refs) and event.side == "buyer" and event.kind == "order":
        actor = marketplace_svc._tenant_actor(db, tenant_id)
        for line in event.lines:
            if line.market_item_ref in mapped_refs:
                continue
            if not line.name.strip() or not line.unit.strip():
                raise MappingMissing("public item details missing")
            item = Item(
                tenant_id=tenant_id, sku=f"MP-{line.market_item_ref.hex}",
                name=line.name.strip(), unit=line.unit.strip(),
                sales_price=line.consumer_price or line.unit_price, average_cost=0,
            )
            db.add(item)
            db.flush()
            mapping = EnterpriseMarketItemMap(
                tenant_id=tenant_id, market_item_ref=line.market_item_ref,
                local_item_id=item.id, approved_by_id=actor.id,
                approved_at=datetime.now(timezone.utc),
            )
            db.add(mapping)
            maps.append(mapping)
            mapped_refs.add(line.market_item_ref)
        db.flush()
    if len(maps) != len(refs):
        raise MappingMissing("market item mapping incomplete")
    items = db.query(Item).filter(
        Item.tenant_id == tenant_id,
        Item.id.in_([row.local_item_id for row in maps]),
        Item.is_active.is_(True),
    ).all()
    by_id = {item.id: item for item in items}
    if len(by_id) != len(maps):
        raise MappingMissing("local mapped item missing or inactive")
    return {row.market_item_ref: by_id[row.local_item_id] for row in maps}


def _local_contact(db: Session, tenant_id: UUID, event: MarketFinancialEvent) -> Contact:
    mapping = db.query(EnterpriseMarketCounterpartyMap).filter(
        EnterpriseMarketCounterpartyMap.tenant_id == tenant_id,
        EnterpriseMarketCounterpartyMap.cloud_tenant_id == event.counterparty_ref,
    ).with_for_update().first()
    contact = db.get(Contact, mapping.local_contact_id) if mapping else None
    if contact is None:
        contact = Contact(
            tenant_id=tenant_id, name=event.counterparty_name,
            is_customer=event.side == "seller", is_supplier=event.side == "buyer",
        )
        db.add(contact)
        db.flush()
        db.add(EnterpriseMarketCounterpartyMap(
            tenant_id=tenant_id, cloud_tenant_id=event.counterparty_ref, local_contact_id=contact.id,
        ))
    else:
        contact.is_customer = contact.is_customer or event.side == "seller"
        contact.is_supplier = contact.is_supplier or event.side == "buyer"
    db.flush()
    return contact


def _post_document(db: Session, tenant_id: UUID, event: MarketFinancialEvent) -> UUID:
    items = _local_items(db, tenant_id, event)
    actor = marketplace_svc._tenant_actor(db, tenant_id)
    if event.kind == "return":
        original = db.query(EnterpriseMarketLocalPosting).filter(
            EnterpriseMarketLocalPosting.tenant_id == tenant_id,
            EnterpriseMarketLocalPosting.order_id == event.order_id,
            EnterpriseMarketLocalPosting.side == event.side,
            EnterpriseMarketLocalPosting.kind == "order",
            EnterpriseMarketLocalPosting.status == "posted",
        ).first()
        if original is None or original.local_document_id is None:
            raise MappingMissing("original order document missing")
        description = f"مرجوعی بازار #{event.return_number} ({event.return_id})"
        if event.side == "seller":
            document = post_sales_return(
                db, SalesReturnIn(
                    return_date=event.order_date, sales_invoice_id=original.local_document_id,
                    description=description,
                    lines=[SalesReturnLineIn(item_id=items[line.market_item_ref].id, qty=line.qty) for line in event.lines],
                ), actor, physical=True,
            )
        else:
            document = post_purchase_return(
                db, PurchaseReturnIn(
                    return_date=event.order_date, purchase_invoice_id=original.local_document_id,
                    description=description,
                    lines=[PurchaseReturnLineIn(item_id=items[line.market_item_ref].id, qty=line.qty) for line in event.lines],
                ), actor,
            )
        db.flush()
        return document.id
    contact = _local_contact(db, tenant_id, event)
    warehouse = marketplace_svc._default_warehouse(db, tenant_id)
    description = f"سفارش بازار #{event.order_number} ({event.order_id})"
    if event.side == "seller":
        invoice = post_sales_invoice(
            db,
            SalesInvoiceIn(
                invoice_date=event.order_date, warehouse_id=warehouse.id,
                contact_id=contact.id, description=description,
                lines=[SalesInvoiceLineIn(
                    item_id=items[line.market_item_ref].id, qty=line.qty,
                    unit_price=line.unit_price, discount=line.discount,
                ) for line in event.lines],
            ),
            actor, move_inventory=False, issue_accounting=False,
        )
        finalize_immediate_sale(db, invoice, warehouse.id, actor)
    else:
        invoice = post_purchase_invoice(
            db,
            PurchaseInvoiceIn(
                invoice_date=event.order_date, warehouse_id=warehouse.id,
                contact_id=contact.id, description=description,
                lines=[PurchaseInvoiceLineIn(
                    item_id=items[line.market_item_ref].id, qty=line.qty,
                    unit_cost=line.unit_price, discount=line.discount,
                ) for line in event.lines],
            ),
            actor,
        )
        consumer_by_item = {
            items[line.market_item_ref].id: line.consumer_price
            for line in event.lines if line.consumer_price > 0
        }
        if consumer_by_item:
            for batch in db.query(StockBatch).filter(StockBatch.source_id == invoice.id).all():
                price = consumer_by_item.get(batch.item_id)
                if price is not None:
                    batch.consumer_price = price
    if event.cash_amount > 0:
        method, bank_id = marketplace_svc._money_method(db)
        payment = TreasuryTransactionIn(
            transaction_date=event.order_date, contact_id=contact.id,
            amount=event.cash_amount, method=method, bank_account_id=bank_id,
            description=f"تسویهٔ نقدی {description}",
        )
        if event.side == "seller":
            treasury.create_receipt(db, payment, actor)
        else:
            treasury.create_payment(db, payment, actor)
    db.flush()
    return invoice.id


def consume(db: Session, tenant_id: UUID, event: MarketFinancialEvent) -> MarketPostingReceipt:
    """Caller commits this transaction before acknowledging the VPS."""
    lock_local_finance(db, tenant_id)
    payload = event.model_dump(mode="json")
    db.execute(
        pg_insert(EnterpriseMarketLocalPosting).values(
            id=uuid.uuid4(), tenant_id=tenant_id, event_id=event.event_id,
            order_id=event.order_id, side=event.side, kind=event.kind,
            payload=payload, status="pending", attempts=0, error_code="",
        ).on_conflict_do_nothing(index_elements=["tenant_id", "event_id"])
    )
    row = db.query(EnterpriseMarketLocalPosting).filter(
        EnterpriseMarketLocalPosting.tenant_id == tenant_id,
        EnterpriseMarketLocalPosting.event_id == event.event_id,
    ).with_for_update().one()
    if row.payload != payload:
        return MarketPostingReceipt(
            event_id=event.event_id, order_id=event.order_id, side=event.side,
            outcome="blocked", error_code="event_payload_mismatch",
        )
    if row.status == "posted":
        return MarketPostingReceipt(event_id=event.event_id, order_id=event.order_id, side=event.side, outcome="posted")
    row.attempts += 1
    try:
        with db.begin_nested():
            document_id = _post_document(db, tenant_id, event)
    except MappingMissing as exc:
        row.status = "blocked"
        row.error_code = "item_mapping_missing"
        row.error_detail = ("فاکتور محلی سفارش اصلی پیدا نشد؛ ابتدا ثبت سفارش اصلی را تکمیل کنید."
                            if "original order" in str(exc) else
                            "نگاشت کالا کامل نیست یا کالا غیرفعال است؛ نگاشت را اصلاح و دوباره تلاش کنید.")
    except Exception as exc:  # noqa: BLE001 — finance failure must remain retryable, not lose the event
        log.warning("local market posting failed: %s", type(exc).__name__)
        row.status = "retryable_error"
        row.error_code = "local_posting_failed"
        row.error_detail = (exc.detail[:1000] if isinstance(exc, HTTPException) and isinstance(exc.detail, str)
                            else "ثبت مالی محلی انجام نشد؛ موجودی، دورهٔ مالی و تنظیم حساب‌ها را بررسی و دوباره تلاش کنید.")
    else:
        row.local_document_id = document_id
        row.status = "posted"
        row.error_code = ""
        row.error_detail = ""
        row.posted_at = datetime.now(timezone.utc)
    db.flush()
    return MarketPostingReceipt(
        event_id=event.event_id, order_id=event.order_id, side=event.side,
        outcome=row.status if row.status != "pending" else "retryable_error",
        error_code=row.error_code,
    )
