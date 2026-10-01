"""Cloud broker boundary for an on-premise marketplace connection.

Only this router accepts a signed installation token and a scoped bridge
credential.  Ordinary enterprise client JWTs never travel to the VPS.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import Principal, get_principal
from app.rate_limit import limit_license_activate
from app.schemas.enterprise_market_bridge import MarketCatalogFinalize, MarketCatalogPage
from app.schemas.enterprise_market_bridge import MarketFinancialEvent, MarketPostingReceipt
from app.services import enterprise_market_catalog as catalog
from app.services import enterprise_market_commands as commands
from app.services import enterprise_market_pairing as pairing
from app.services import enterprise_market_transport as transport
from app.services import enterprise_market_views as views
from app.services import marketplace as market
from app.schemas.marketplace import MessageOut, MessagesPage

router = APIRouter(prefix="/api/enterprise/market", tags=["enterprise-market-cloud"])


def enabled() -> None:
    if not get_settings().market_bridge_enabled or get_settings().is_enterprise:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")


class LicenseProof(BaseModel):
    token: str = Field(min_length=20, max_length=4096)


class PairPollIn(LicenseProof):
    link_id: UUID


class PairClaimIn(BaseModel):
    code: str = Field(min_length=12, max_length=16)


class MarketCommandIn(BaseModel):
    request_id: UUID
    operation: str = Field(min_length=3, max_length=40)
    actor_name: str = Field(min_length=1, max_length=200)
    payload: dict


@router.post("/pair/start", dependencies=[Depends(enabled), Depends(limit_license_activate)])
def pair_start(data: LicenseProof, db: Session = Depends(get_db)):
    link, code = pairing.start(db, data.token)
    return {"link_id": link.id, "pair_code": code, "expires_at": link.pairing_expires_at}


@router.post("/pair/claim", dependencies=[Depends(enabled), Depends(limit_license_activate)])
def pair_claim(
    data: PairClaimIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    if principal.role.key != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "فقط مالک حساب ابری می‌تواند پیوند را تأیید کند")
    link = pairing.claim(db, data.code, principal.tenant_id, principal.user.id)
    return {"link_id": link.id, "status": link.status}


@router.post("/pair/revoke", dependencies=[Depends(enabled)])
def pair_revoke(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if principal.role.key != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "فقط مالک حساب ابری می‌تواند پیوند را قطع کند")
    link = pairing.revoke(db, principal.tenant_id)
    return {"link_id": link.id, "status": link.status}


@router.post("/pair/poll", dependencies=[Depends(enabled), Depends(limit_license_activate)])
def pair_poll(data: PairPollIn, db: Session = Depends(get_db)):
    state, link, credential = pairing.poll(db, data.token, data.link_id)
    return {"status": state, "link_id": link.id, "cloud_tenant_id": link.cloud_tenant_id, "credential": credential}


@router.get("/sync/{link_id}/ping", dependencies=[Depends(enabled)])
def sync_ping(link_id: UUID, authorization: str = Header(default=""), db: Session = Depends(get_db)):
    link = _sync_link(db, link_id, authorization)
    return {"status": "ok", "cloud_tenant_id": link.cloud_tenant_id}


def _sync_link(db: Session, link_id: UUID, authorization: str):
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credential:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "اتصال بازار معتبر نیست")
    return pairing.authenticate(db, link_id, credential)


@router.post("/sync/{link_id}/command", dependencies=[Depends(enabled)])
def market_command(
    link_id: UUID, data: MarketCommandIn, authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    link = _sync_link(db, link_id, authorization)
    return commands.execute(db, link, data.request_id, data.operation, data.payload, data.actor_name)


@router.post("/sync/{link_id}/catalog/page", dependencies=[Depends(enabled)])
def catalog_page(
    link_id: UUID, data: MarketCatalogPage, authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    return {"accepted": catalog.accept_page(db, _sync_link(db, link_id, authorization), data)}


@router.post("/sync/{link_id}/catalog/finalize", dependencies=[Depends(enabled)])
def catalog_finalize(
    link_id: UUID, data: MarketCatalogFinalize, authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    return {"published": catalog.finalize(db, _sync_link(db, link_id, authorization), data)}


@router.get("/sync/{link_id}/events", dependencies=[Depends(enabled)])
def pending_events(link_id: UUID, authorization: str = Header(default=""), db: Session = Depends(get_db)):
    link = _sync_link(db, link_id, authorization)
    return [MarketFinancialEvent.model_validate(row.payload).model_dump(mode="json") for row in transport.pending_for_link(db, link.id)]


@router.get("/sync/{link_id}/snapshot", dependencies=[Depends(enabled)])
def market_snapshot(link_id: UUID, authorization: str = Header(default=""), db: Session = Depends(get_db)):
    link = _sync_link(db, link_id, authorization)
    if link.cloud_tenant_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "حساب بازار هنوز پیوند نشده است")
    return views.snapshot(db, link.cloud_tenant_id)


@router.get("/sync/{link_id}/messages/{kind}/{thread_id}", dependencies=[Depends(enabled)], response_model=MessagesPage)
def market_messages(
    link_id: UUID, kind: str, thread_id: UUID,
    authorization: str = Header(default=""), db: Session = Depends(get_db),
):
    link = _sync_link(db, link_id, authorization)
    if link.cloud_tenant_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "حساب بازار هنوز پیوند نشده است")
    if kind == "connection":
        thread, role = market.load_connection_for_member(db, link.cloud_tenant_id, thread_id)
        messages = market.list_messages(db, thread.id, latest_limit=200)
        market.mark_read(db, thread, role)
    elif kind == "order":
        thread, role = market.load_order_for_member(db, link.cloud_tenant_id, thread_id)
        messages = market.list_order_messages(db, thread.id, latest_limit=200)
        market.mark_order_read(db, thread, role)
    else:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "گفتگو یافت نشد")
    return MessagesPage(my_role=role, messages=[MessageOut(**market.message_dict(row)) for row in messages])


@router.post("/sync/{link_id}/events/{event_id}/receipt", dependencies=[Depends(enabled)])
def event_receipt(
    link_id: UUID, event_id: UUID, data: MarketPostingReceipt,
    authorization: str = Header(default=""), db: Session = Depends(get_db),
):
    link = _sync_link(db, link_id, authorization)
    return transport.record_receipt(db, link.id, event_id, data)
