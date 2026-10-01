"""Two-owner, outbound-only pairing of an enterprise server to a cloud account.

Cloud sees the signed enterprise license and its installation ID, not the
company's local database.  The local owner displays a short-lived code; the
cloud account owner claims it.  The long-lived bearer credential is stored
only as a hash in the cloud and encrypted on premises.  A recoverable,
encrypted one-time delivery copy remains on the cloud until authenticated.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.licensing import keys
from app.licensing.token import LicenseError, verify
from app.models.enterprise_license_registry import EnterpriseLicenseRecord
from app.models.enterprise_market_bridge import EnterpriseMarketCatalog, EnterpriseMarketLink, EnterpriseMarketEvent
from app.models.marketplace import MarketplaceListing, MarketplaceOrder, MarketplaceReturn, MarketplaceSettings
from app.models.tenant import Tenant
from app.secrets_at_rest import decrypt, encrypt, is_configured

PAIR_MINUTES = 15
PAIR_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def _hash(kind: str, value: str) -> str:
    return hashlib.sha256(f"cubita-market-{kind}-v1:{value}".encode("utf-8")).hexdigest()


def _license(db: Session, token: str) -> tuple[EnterpriseLicenseRecord, str]:
    try:
        payload = verify(token, keys.TRUSTED_PUBLIC_KEYS)
    except LicenseError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    lic = payload.get("lic")
    install = payload.get("install")
    if not isinstance(lic, str) or not isinstance(install, str) or not install:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "مجوزِ نصب شناسهٔ معتبر ندارد")
    record = db.query(EnterpriseLicenseRecord).filter(EnterpriseLicenseRecord.lic_id == lic).with_for_update().first()
    if record is None or record.status != "active" or record.install_id != install:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "مجوزِ این نصب در ابر فعال نیست")
    now = datetime.now(timezone.utc)
    if record.expires_at is not None and now >= record.expires_at + timedelta(days=record.grace_days):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "مجوزِ نصب منقضی شده است")
    return record, install


def start(db: Session, token: str) -> tuple[EnterpriseMarketLink, str]:
    """On-prem server starts pairing over outbound TLS using its signed license."""
    if not is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "SECRETS_KEY برای پیوند امن بازار تنظیم نشده است")
    record, install = _license(db, token)
    link = db.query(EnterpriseMarketLink).filter(
        EnterpriseMarketLink.install_id == install, EnterpriseMarketLink.status != "revoked"
    ).with_for_update().first()
    if link is not None and link.status == "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "این نصب قبلاً به حساب ابری پیوند خورده است")
    if link is None:
        link = EnterpriseMarketLink(license_id=record.id, install_id=install, status="pending")
        db.add(link)
    code = "".join(secrets.choice(PAIR_ALPHABET) for _ in range(12))
    link.license_id = record.id
    link.pairing_code_hash = _hash("pair", code)
    link.pairing_expires_at = datetime.now(timezone.utc) + timedelta(minutes=PAIR_MINUTES)
    link.credential_hash = None
    link.credential_delivery_encrypted = None
    db.flush()
    return link, code


def _assert_no_open_market_work(db: Session, tenant_id: UUID) -> None:
    open_order = db.query(MarketplaceOrder.id).filter(
        (MarketplaceOrder.distributor_tenant_id == tenant_id) | (MarketplaceOrder.retailer_tenant_id == tenant_id),
        MarketplaceOrder.status.notin_(("delivered", "received", "rejected", "cancelled")),
    ).first()
    open_return = db.query(MarketplaceReturn.id).filter(
        (MarketplaceReturn.distributor_tenant_id == tenant_id) | (MarketplaceReturn.retailer_tenant_id == tenant_id),
        MarketplaceReturn.status.in_(("requested", "sync_pending")),
    ).first()
    if open_order or open_return:
        raise HTTPException(status.HTTP_409_CONFLICT, "ابتدا سفارش‌ها و مرجوعی‌های ناتمام این حساب را تعیین تکلیف کنید")


def claim(db: Session, code: str, cloud_tenant_id: UUID, cloud_owner_id: UUID) -> EnterpriseMarketLink:
    """Cloud owner approves pairing; old catalog is frozen, never republished."""
    if not is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "SECRETS_KEY برای پیوند امن بازار تنظیم نشده است")
    normalized = "".join(code.upper().split()).replace("-", "")
    if len(normalized) != 12 or any(ch not in PAIR_ALPHABET for ch in normalized):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کد پیوند نامعتبر است")
    link = db.query(EnterpriseMarketLink).filter(
        EnterpriseMarketLink.pairing_code_hash == _hash("pair", normalized),
        EnterpriseMarketLink.status == "pending",
    ).with_for_update().first()
    if link is None or link.pairing_expires_at is None or link.pairing_expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کد پیوند پیدا نشد یا منقضی شده است")
    existing = db.query(EnterpriseMarketLink).filter(
        EnterpriseMarketLink.cloud_tenant_id == cloud_tenant_id,
        EnterpriseMarketLink.status == "active",
    ).first()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این حساب ابری به نصب دیگری پیوند دارد")
    tenant = db.query(Tenant).filter(Tenant.id == cloud_tenant_id).with_for_update().one()
    _assert_no_open_market_work(db, cloud_tenant_id)
    credential = secrets.token_urlsafe(48)
    link.cloud_tenant_id = cloud_tenant_id
    link.cloud_owner_id = cloud_owner_id
    link.original_kind = tenant.kind
    market_settings = db.query(MarketplaceSettings).filter(
        MarketplaceSettings.distributor_tenant_id == cloud_tenant_id
    ).first()
    link.original_market_settings = (
        {
            "present": True,
            "is_active": market_settings.is_active,
            "settlement_mode": market_settings.settlement_mode,
            "display_name": market_settings.display_name,
            "require_delivery": market_settings.require_delivery,
            "return_policy": market_settings.return_policy,
            "return_window_days": market_settings.return_window_days,
            "target_trades": list(market_settings.target_trades or []),
        }
        if market_settings is not None else {"present": False}
    )
    link.credential_hash = _hash("credential", credential)
    link.credential_delivery_encrypted = encrypt(credential)
    link.status = "active"
    link.linked_at = datetime.now(timezone.utc)
    link.pairing_code_hash = None
    link.pairing_expires_at = None
    # The existing cloud catalog is historical, not a new local publication.
    db.query(MarketplaceListing).filter(MarketplaceListing.distributor_tenant_id == cloud_tenant_id).update(
        {MarketplaceListing.is_published: False}, synchronize_session=False
    )
    tenant.kind = "both"
    db.flush()
    return link


def poll(db: Session, token: str, link_id: UUID) -> tuple[str, EnterpriseMarketLink, str | None]:
    """Local server retrieves credential after the cloud owner's approval."""
    _, install = _license(db, token)
    link = db.query(EnterpriseMarketLink).filter(
        EnterpriseMarketLink.id == link_id,
        EnterpriseMarketLink.install_id == install,
    ).first()
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درخواست پیوند پیدا نشد")
    if link.status == "revoked":
        return "revoked", link, None
    if link.status != "active":
        return "pending", link, None
    if not link.credential_delivery_encrypted:
        raise HTTPException(status.HTTP_409_CONFLICT, "اعتبارنامهٔ پیوند قبلاً تحویل شده است")
    return "active", link, decrypt(link.credential_delivery_encrypted)


def authenticate(db: Session, link_id: UUID, credential: str) -> EnterpriseMarketLink:
    """All cloud sync endpoints use this, never a client/browser JWT."""
    link = db.query(EnterpriseMarketLink).filter(EnterpriseMarketLink.id == link_id).first()
    if link is None or link.status != "active" or not link.credential_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "اتصال بازار معتبر نیست")
    if not secrets.compare_digest(link.credential_hash, _hash("credential", credential)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "اتصال بازار معتبر نیست")
    record = db.get(EnterpriseLicenseRecord, link.license_id)
    if record is None or record.status != "active" or record.install_id != link.install_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "مجوز این نصب در بازار فعال نیست؛ وضعیت مجوز را بررسی کنید")
    if record.expires_at is not None and datetime.now(timezone.utc) >= record.expires_at + timedelta(days=record.grace_days):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "مجوز نصب منقضی شده است؛ ابتدا مجوز را تمدید کنید")
    # Delivery copy is no longer needed once an authenticated request arrives.
    link.credential_delivery_encrypted = None
    return link


def revoke(db: Session, cloud_tenant_id: UUID) -> EnterpriseMarketLink:
    """Cloud owner's unlink request; historical market orders stay untouched."""
    link = db.query(EnterpriseMarketLink).filter(
        EnterpriseMarketLink.cloud_tenant_id == cloud_tenant_id,
        EnterpriseMarketLink.status == "active",
    ).with_for_update().first()
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیوند فعالی برای این حساب پیدا نشد")
    tenant = db.query(Tenant).filter(Tenant.id == cloud_tenant_id).with_for_update().one()
    _assert_no_open_market_work(db, cloud_tenant_id)
    # Completed enterprise orders retain their invoices only at this install.
    # Revocation/transfer would route future returns to a cloud ledger which
    # has no source invoice. Preserve this link until a historical-return
    # handover protocol exists, even if today's return window has elapsed.
    local_history = db.query(EnterpriseMarketEvent.id).join(
        MarketplaceOrder, MarketplaceOrder.id == EnterpriseMarketEvent.order_id,
    ).filter(
        EnterpriseMarketEvent.link_id == link.id,
        EnterpriseMarketEvent.kind == "order",
        ((EnterpriseMarketEvent.side == "seller") & (MarketplaceOrder.distributor_tenant_id == cloud_tenant_id))
        | ((EnterpriseMarketEvent.side == "buyer") & (MarketplaceOrder.retailer_tenant_id == cloud_tenant_id)),
    ).first()
    if local_history is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این پیوند فاکتور محلی بازار دارد؛ برای حفظ مرجوعی‌های آینده، قطع یا انتقال آن تا فراهم‌شدن مسیر انتقال سوابق مجاز نیست")
    db.query(EnterpriseMarketCatalog).filter(EnterpriseMarketCatalog.link_id == link.id).update(
        {EnterpriseMarketCatalog.is_published: False}, synchronize_session=False
    )
    # A revoked installation must not leave its last shadow catalog orderable.
    shadow_ids = db.query(EnterpriseMarketCatalog.cloud_listing_id).filter(
        EnterpriseMarketCatalog.link_id == link.id,
        EnterpriseMarketCatalog.cloud_listing_id.is_not(None),
    )
    db.query(MarketplaceListing).filter(MarketplaceListing.id.in_(shadow_ids)).update(
        {MarketplaceListing.is_published: False}, synchronize_session=False
    )
    settings = db.query(MarketplaceSettings).filter(
        MarketplaceSettings.distributor_tenant_id == cloud_tenant_id
    ).first()
    if settings is not None:
        original = link.original_market_settings or {}
        settings.is_active = bool(original.get("is_active", False))
        settings.settlement_mode = original.get("settlement_mode", "credit")
        if original.get("present"):
            settings.display_name = original["display_name"]
            settings.require_delivery = original["require_delivery"]
            settings.return_policy = original["return_policy"]
            settings.return_window_days = original["return_window_days"]
            settings.target_trades = original["target_trades"]
    tenant.kind = link.original_kind or "standard"
    link.status = "revoked"
    link.credential_hash = None
    link.credential_delivery_encrypted = None
    db.flush()
    return link
