"""Idempotent cloud market commands from a paired enterprise installation.

The command receipt and market mutation share one database transaction. A
retry after a lost HTTP response therefore returns the original result.
"""

import hashlib
import json
import uuid
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.enterprise_market_bridge import EnterpriseMarketCommand, EnterpriseMarketLink
from app.models.user import User
from app.schemas.marketplace import (
    ConnectionOut, ConnectionRequestIn, ConnectionStatusIn, OrderConfirmIn,
    MessageIn, MessageOut, OrderDeliverIn, OrderOut, OrderPlaceIn, ReturnOut, ReturnRejectIn,
    ReturnRequestIn, ZoneIn, ZoneOut, ConnectionZoneIn,
)
from app.services import marketplace as market


def execute(
    db: Session, link: EnterpriseMarketLink, request_id: UUID, operation: str,
    payload: dict, actor_name: str,
) -> dict:
    if link.cloud_tenant_id is None or link.cloud_owner_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "حساب بازار هنوز پیوند نشده است")
    if operation not in {
        "buyer.connect", "buyer.place", "buyer.return", "seller.connection",
        "seller.confirm", "seller.deliver", "seller.reject", "seller.return.approve", "seller.return.reject",
        "connection.message", "order.message",
        "seller.zone.create", "seller.zone.update", "seller.zone.delete", "seller.connection.zone",
    }:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فرمان بازار شناخته‌شده نیست")
    _validate_payload(operation, payload)
    canonical = json.dumps({"operation": operation, "payload": payload, "actor_name": actor_name}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    command_id = uuid.uuid4()
    # ON CONFLICT serializes concurrent retries on the unique request key.
    # A failed market mutation rolls this insert back as well.
    db.execute(insert(EnterpriseMarketCommand).values(
        id=command_id, link_id=link.id, request_id=request_id,
        operation=operation, actor_name=actor_name, payload_hash=digest,
    ).on_conflict_do_nothing(constraint="uq_em_command_request"))
    receipt = db.query(EnterpriseMarketCommand).filter(
        EnterpriseMarketCommand.link_id == link.id,
        EnterpriseMarketCommand.request_id == request_id,
    ).with_for_update().one()
    if receipt.operation != operation or receipt.payload_hash != digest:
        raise HTTPException(status.HTTP_409_CONFLICT, "این شناسهٔ درخواست قبلاً برای عملیات دیگری استفاده شده است")
    if receipt.result is not None:
        return receipt.result

    tenant_id = link.cloud_tenant_id
    if operation == "buyer.connect":
        data = ConnectionRequestIn.model_validate(payload)
        row = market.request_connection(db, tenant_id, data.distributor_tenant_id)
        result = ConnectionOut(**market.connection_dict(db, row, tenant_id)).model_dump(mode="json")
    elif operation == "buyer.place":
        data = OrderPlaceIn.model_validate(payload)
        row = market.place_order(db, tenant_id, data)
        result = _order_result(db, row, tenant_id)
    elif operation == "buyer.return":
        data = ReturnRequestIn.model_validate(payload)
        row = market.request_return(db, tenant_id, data)
        result = ReturnOut(**market.return_dict(db, row)).model_dump(mode="json")
    elif operation.startswith("seller.zone."):
        if operation == "seller.zone.delete":
            market.delete_zone(db, tenant_id, UUID(payload["zone_id"]))
            result = {"deleted": True}
        else:
            data = ZoneIn.model_validate(payload)
            row = (market.create_zone(db, tenant_id, data) if operation == "seller.zone.create"
                   else market.update_zone(db, tenant_id, UUID(payload["zone_id"]), data))
            result = ZoneOut.model_validate(row).model_dump(mode="json")
    elif operation == "seller.connection.zone":
        data = ConnectionZoneIn.model_validate(payload)
        row = market.assign_zone(db, tenant_id, UUID(payload["connection_id"]), data.zone_id)
        result = ConnectionOut(**market.connection_dict(db, row, tenant_id)).model_dump(mode="json")
    elif operation == "seller.connection":
        connection_id = UUID(payload["connection_id"])
        data = ConnectionStatusIn.model_validate(payload)
        row = market.set_connection_status(db, tenant_id, connection_id, data.status)
        result = ConnectionOut(**market.connection_dict(db, row, tenant_id)).model_dump(mode="json")
    elif operation in ("connection.message", "order.message"):
        data = MessageIn.model_validate(payload)
        thread_id = UUID(payload["thread_id"])
        if operation == "connection.message":
            thread, role = market.load_connection_for_member(db, tenant_id, thread_id)
            row = market.post_message(
                db, thread, sender_tenant_id=tenant_id, sender_role=role,
                sender_user_id=None, sender_name=actor_name, body=data.body,
            )
        else:
            thread, role = market.load_order_for_member(db, tenant_id, thread_id)
            row = market.post_order_message(
                db, thread, sender_tenant_id=tenant_id, sender_role=role,
                sender_user_id=None, sender_name=actor_name, body=data.body,
            )
        result = MessageOut(**market.message_dict(row)).model_dump(mode="json")
    elif operation.startswith("seller.return."):
        return_id = UUID(payload["return_id"])
        if operation == "seller.return.approve":
            actor = db.get(User, link.cloud_owner_id)
            if actor is None:
                raise HTTPException(status.HTTP_409_CONFLICT, "مالک حساب ابری یافت نشد")
            row = market.approve_return(db, tenant_id, actor, return_id)
        else:
            data = ReturnRejectIn.model_validate(payload)
            row = market.reject_return(db, tenant_id, return_id, data.response_note)
        result = ReturnOut(**market.return_dict(db, row)).model_dump(mode="json")
    else:
        order_id = UUID(payload["order_id"])
        actor = db.get(User, link.cloud_owner_id)
        if actor is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "مالک حساب ابری یافت نشد")
        if operation == "seller.confirm":
            data = OrderConfirmIn.model_validate(payload)
            row = market.confirm_order(db, tenant_id, actor, order_id, data.cash_percent)
        elif operation == "seller.deliver":
            data = OrderDeliverIn.model_validate(payload)
            row = market.deliver_order(db, tenant_id, actor, order_id, data.cash_percent)
            # The cloud owner is a technical actor for the on-prem worker.
            # Display the authorized local staff name on the market delivery.
            if actor_name and row.delivered_by_name == (actor.name or "")[:200]:
                row.delivered_by_name = actor_name[:200]
        else:
            row = market.reject_order(db, tenant_id, order_id)
        result = _order_result(db, row, tenant_id)
    receipt.result = result
    db.flush()
    return result


def _validate_payload(operation: str, payload: dict) -> None:
    schemas = {
        "buyer.connect": ConnectionRequestIn, "buyer.place": OrderPlaceIn,
        "buyer.return": ReturnRequestIn, "seller.connection": ConnectionStatusIn,
        "seller.confirm": OrderConfirmIn, "seller.deliver": OrderDeliverIn,
        "seller.return.reject": ReturnRejectIn,
        "connection.message": MessageIn, "order.message": MessageIn,
        "seller.zone.create": ZoneIn, "seller.zone.update": ZoneIn,
        "seller.connection.zone": ConnectionZoneIn,
    }
    identifiers = {
        "seller.connection": "connection_id", "connection.message": "thread_id",
        "order.message": "thread_id", "seller.return.approve": "return_id",
        "seller.return.reject": "return_id", "seller.confirm": "order_id",
        "seller.deliver": "order_id", "seller.reject": "order_id",
        "seller.zone.update": "zone_id", "seller.zone.delete": "zone_id",
        "seller.connection.zone": "connection_id",
    }
    try:
        if operation in schemas:
            schemas[operation].model_validate(payload)
        if operation in identifiers:
            UUID(str(payload[identifiers[operation]]))
    except (ValidationError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "اطلاعات فرمان بازار کامل یا معتبر نیست؛ فرم را بررسی و دوباره ارسال کنید") from exc


def _order_result(db: Session, row, tenant_id: UUID) -> dict:
    data = market.order_dict(db, row, tenant_id)
    # Local invoice identifiers never cross the bridge.
    data["distributor_sales_invoice_id"] = None
    data["retailer_purchase_invoice_id"] = None
    return OrderOut(**data).model_dump(mode="json")
