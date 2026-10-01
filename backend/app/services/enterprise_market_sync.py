"""Outbound-only, retrying enterprise market synchronization.

The Windows server process owns this worker. Clients never contact the VPS.
Every upload uses the explicit marketplace DTO; accounting, batch, warehouse,
purchase-cost, and local-document tables remain in the on-premise database.
"""

import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status

from app.config import get_settings
from app.database import SessionLocal
from app.licensing import state as license_state
from app.models.enterprise_license import EnterpriseLicense
from app.models.enterprise_market_bridge import EnterpriseMarketLocalState
from app.models.tenant import Tenant
from app.secrets_at_rest import decrypt, encrypt, is_configured
from app.schemas.enterprise_market_bridge import MarketFinancialEvent, MarketSellerSettingsSnapshot, MarketViewSnapshot
from app.services.enterprise_market_catalog import selected_snapshots
from app.services import marketplace as marketplace_svc
from app.services.enterprise_market_posting import consume
from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant

log = logging.getLogger(__name__)
_sync_lock = threading.Lock()


def _base_url() -> str:
    settings = get_settings()
    url = settings.license_server_url.rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.path:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "نشانی بازار ابری باید فقط یک مبدأ HTTPS باشد")
    return url


def cloud_post(path: str, body: dict, *, credential: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {credential}"} if credential is not None else {}
    try:
        response = httpx.post(
            f"{_base_url()}/api/enterprise/market/{path}",
            json=body, headers=headers, timeout=15, follow_redirects=False,
        )
        response.raise_for_status()
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError("invalid cloud response")
        return value
    except httpx.HTTPStatusError as exc:
        if 400 <= exc.response.status_code < 500:
            try:
                detail = exc.response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            raise HTTPException(exc.response.status_code, detail if isinstance(detail, str) else "درخواست بازار رد شد") from exc
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "بازار ابری موقتاً پاسخ‌گو نیست") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ارتباط امن با بازار ابری برقرار نشد؛ بعداً دوباره تلاش کنید") from exc


def cloud_get(path: str, *, credential: str) -> object:
    try:
        response = httpx.get(
            f"{_base_url()}/api/enterprise/market/{path}",
            headers={"Authorization": f"Bearer {credential}"},
            timeout=15, follow_redirects=False,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        # Authentication and revocation failures must never unlock an offline
        # cache fallback. Only unavailable transport/server failures may do so.
        if 400 <= exc.response.status_code < 500:
            try:
                detail = exc.response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            raise HTTPException(exc.response.status_code, detail if isinstance(detail, str) else "دسترسی بازار رد شد؛ وضعیت پیوند و مجوز را بررسی کنید") from exc
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "همگام‌سازی بازار موقتاً در دسترس نیست") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "همگام‌سازی بازار موقتاً در دسترس نیست") from exc


def _scoped_session():
    db = SessionLocal()
    tenant = db.query(Tenant).first()  # Enterprise edition has one local tenant.
    if tenant is None:
        db.close()
        return None, None
    bind_session_tenant(db, tenant.id)
    apply_tenant_to_transaction(db, tenant.id)
    return db, tenant.id


def _finish_pending_pair(db, state: EnterpriseMarketLocalState) -> bool:
    row = db.get(EnterpriseLicense, 1)
    if row is None or not row.token:
        return False
    result = cloud_post("pair/poll", {"token": row.token, "link_id": str(state.link_id)})
    if result.get("status") == "revoked":
        state.status = "revoked"
        state.credential_encrypted = None
        return False
    if result.get("status") != "active":
        return False
    cloud_tenant_id = uuid.UUID(result["cloud_tenant_id"])
    credential = result["credential"]
    if not isinstance(credential, str) or len(credential) < 32:
        raise ValueError("invalid market credential")
    state.cloud_tenant_id = cloud_tenant_id
    state.credential_encrypted = encrypt(credential)
    state.status = "active"
    return True


def sync_once() -> str:
    """Run one attempt. Failure is recorded; normal accounting is untouched."""
    settings = get_settings()
    if not settings.is_enterprise or not settings.market_bridge_enabled:
        return "disabled"
    if not is_configured():
        return "secrets_key_missing"
    if not _sync_lock.acquire(blocking=False):
        return "busy"
    tenant_id = None
    try:
        db, tenant_id = _scoped_session()
        if db is None:
            return "not_setup"
        try:
            state = db.query(EnterpriseMarketLocalState).filter(EnterpriseMarketLocalState.tenant_id == tenant_id).with_for_update().first()
            if state is None or state.status == "revoked":
                return "not_linked"
            if state.status == "pending":
                if not _finish_pending_pair(db, state):
                    db.commit()
                    return "pending_pair"
            if license_state.current(db).mode not in ("active", "grace"):
                return "license_invalid"
            if not state.credential_encrypted:
                return "credential_missing"
            credential = decrypt(state.credential_encrypted)
            link_id = state.link_id
            snapshots = selected_snapshots(db, tenant_id)
            seller_settings = marketplace_svc.get_settings(db, tenant_id)
            if seller_settings.settlement_mode == "online":
                raise ValueError("online settlement cannot be used by an enterprise market seller")
            settings_snapshot = MarketSellerSettingsSnapshot(
                display_name=seller_settings.display_name,
                is_active=seller_settings.is_active,
                require_delivery=seller_settings.require_delivery,
                return_policy=seller_settings.return_policy,
                return_window_days=seller_settings.return_window_days,
                target_trades=list(seller_settings.target_trades or []),
            )
            generation = state.pending_generation
            if generation is None or (
                state.pending_started_at is not None
                and datetime.now(timezone.utc) - state.pending_started_at >= timedelta(minutes=15)
            ):
                generation = uuid.uuid4()
                state.pending_generation = generation
                state.pending_started_at = datetime.now(timezone.utc)
            approved = state.catalog_approved
            db.commit()
        finally:
            db.close()

        incoming = cloud_get(f"sync/{link_id}/events", credential=credential)
        if not isinstance(incoming, list) or len(incoming) > 50:
            raise ValueError("invalid market event batch")
        for raw in incoming:
            event = MarketFinancialEvent.model_validate(raw)
            db, _ = _scoped_session()
            assert db is not None
            try:
                receipt = consume(db, tenant_id, event)
                db.commit()
            finally:
                db.close()
            cloud_post(
                f"sync/{link_id}/events/{event.event_id}/receipt",
                receipt.model_dump(mode="json"), credential=credential,
            )

        if not snapshots:
            cloud_post(f"sync/{link_id}/catalog/page", {
                "generation": str(generation), "listings": [],
            }, credential=credential)
        for offset in range(0, len(snapshots), 20):
            cloud_post(f"sync/{link_id}/catalog/page", {
                "generation": str(generation),
                "listings": [s.model_dump(mode="json") for s in snapshots[offset:offset + 20]],
            }, credential=credential)
        cloud_post(f"sync/{link_id}/catalog/finalize", {
            "generation": str(generation), "expected_count": len(snapshots), "owner_approved": approved,
            "seller_settings": settings_snapshot.model_dump(mode="json"),
        }, credential=credential)
        market_view = MarketViewSnapshot.model_validate(
            cloud_get(f"sync/{link_id}/snapshot", credential=credential)
        )

        db, _ = _scoped_session()
        assert db is not None
        try:
            state = db.query(EnterpriseMarketLocalState).filter(EnterpriseMarketLocalState.tenant_id == tenant_id).with_for_update().one()
            if state.pending_generation == generation:
                state.pending_generation = None
                state.pending_started_at = None
                state.last_sync_at = datetime.now(timezone.utc)
                state.last_error_code = ""
                state.market_snapshot = market_view.model_dump(mode="json")
                state.market_snapshot_at = market_view.captured_at
            db.commit()
        finally:
            db.close()
        return "ok"
    except (HTTPException, ValueError, RuntimeError) as exc:
        log.warning("enterprise market sync retry scheduled: %s", type(exc).__name__)
        if tenant_id is not None:
            db, _ = _scoped_session()
            assert db is not None
            try:
                row = db.query(EnterpriseMarketLocalState).filter(EnterpriseMarketLocalState.tenant_id == tenant_id).first()
                if row is not None:
                    row.last_error_code = ("access_denied" if isinstance(exc, HTTPException) and exc.status_code in (401, 402, 403)
                                           else "network_or_sync_error")
                db.commit()
            finally:
                db.close()
        return "retry"
    finally:
        _sync_lock.release()


class MarketSyncScheduler:
    def __init__(self, interval_seconds: int = 60):
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()

    def start(self) -> None:
        if not get_settings().is_enterprise or not get_settings().market_bridge_enabled:
            return
        threading.Thread(target=self._run, name="cubita-market-sync", daemon=True).start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                sync_once()
            except Exception:  # noqa: BLE001 — worker must never terminate API service
                log.exception("enterprise market sync iteration failed")
            self._stop.wait(self.interval_seconds)

    def stop(self) -> None:
        self._stop.set()
