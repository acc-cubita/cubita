"""اعلانِ Push (FCM) به اپ موبایل — تک مسیر خروجِ اعلان از سیستم.

مثلِ mailer/sms: **اگر FCM کانفیگ نشده باشد، no-opِ بی‌خطاست** (فقط لاگ). پس روی
نمونه‌ای که هنوز پروژه‌ی Firebase ندارد، هیچ مسیری نمی‌شکند و هیچ اعلانی هم نمی‌رود.

لایه‌بندی عمدی است تا هم تست‌پذیر بماند و هم شبکه از منطق جدا باشد:
- `register_device`/`unregister_device`: مدیریتِ ثبتِ دستگاه (DB).
- `notify_user` / `notify_tenant`: هدف‌گیریِ گیرنده‌ها از روی DB و سپردن به `send_push`.
- `send_push` → `_deliver`: تنها جایی که به FCM/شبکه دست می‌زند (پشتِ گاردِ کانفیگ).
- `safe_notify_tenant`: پوششِ کاملِ استثنا برای قلاب‌های رویداد — شکستِ اعلان هرگز
  نباید تراکنشی را که همین حالا یک پیام/سفارش را ثبت کرده rollback کند.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.device_token import DeviceToken
from app.models.tenant import Membership

logger = logging.getLogger(__name__)

_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


# ── ثبتِ دستگاه ────────────────────────────────────────────────────────
def register_device(
    db: Session, *, user_id: UUID, tenant_id: UUID | None, fcm_token: str, platform: str
) -> DeviceToken:
    """توکنِ دستگاه را ثبت/به‌روزرسانی می‌کند (upsert بر پایه‌ی خودِ توکن).

    اگر همان توکن قبلاً برای کاربرِ دیگری ثبت شده بود، به کاربرِ تازه منتقل می‌شود —
    یک گوشیِ مشترک نباید اعلانِ کاربرِ قبلی را بگیرد.
    """
    token = (fcm_token or "").strip()
    if not token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "توکنِ دستگاه خالی است")

    now = datetime.now(timezone.utc)
    row = db.query(DeviceToken).filter(DeviceToken.fcm_token == token).first()
    if row is None:
        row = DeviceToken(
            fcm_token=token,
            user_id=user_id,
            tenant_id=tenant_id,
            platform=(platform or "android"),
            last_seen_at=now,
        )
        db.add(row)
    else:
        row.user_id = user_id
        row.tenant_id = tenant_id
        row.platform = platform or row.platform
        row.last_seen_at = now
    db.flush()
    return row


def unregister_device(db: Session, *, user_id: UUID, fcm_token: str) -> None:
    """توکنِ دستگاهِ همین کاربر را حذف می‌کند (هنگامِ خروج). فیلترِ user_id تا کسی
    نتواند دستگاهِ دیگری را باطل کند."""
    token = (fcm_token or "").strip()
    if not token:
        return
    db.query(DeviceToken).filter(
        DeviceToken.fcm_token == token, DeviceToken.user_id == user_id
    ).delete()
    db.flush()


# ── هدف‌گیریِ گیرنده‌ها ─────────────────────────────────────────────────
def notify_user(db: Session, user_id: UUID, *, title: str, body: str, data: dict | None = None) -> int:
    """به همه‌ی دستگاه‌های یک کاربر. تعدادِ ارسالِ موفق را برمی‌گرداند."""
    rows = db.query(DeviceToken).filter(DeviceToken.user_id == user_id).all()
    return send_push([r.fcm_token for r in rows], title=title, body=body, data=data)


def notify_tenant(
    db: Session,
    tenant_id: UUID,
    *,
    title: str,
    body: str,
    data: dict | None = None,
    exclude_user_id: UUID | None = None,
) -> int:
    """به همه‌ی اعضای فعالِ یک کسب‌وکار (به‌جز فرستنده‌ی خودش، اگر داده شود)."""
    memberships = (
        db.query(Membership)
        .filter(Membership.tenant_id == tenant_id, Membership.status == "active")
        .all()
    )
    total = 0
    for m in memberships:
        if exclude_user_id is not None and m.user_id == exclude_user_id:
            continue
        total += notify_user(db, m.user_id, title=title, body=body, data=data)
    return total


def safe_notify_tenant(db: Session, tenant_id: UUID, **kwargs) -> None:
    """پوششِ کاملِ استثنا برای قلاب‌های رویداد — هرگز به بالادست نشت نمی‌کند."""
    try:
        notify_tenant(db, tenant_id, **kwargs)
    except Exception:  # noqa: BLE001 — اعلان نباید هیچ تراکنشی را بشکند
        logger.warning("ارسالِ اعلانِ push شکست خورد", exc_info=True)


# ── تحویل (تنها جایِ شبکه) ─────────────────────────────────────────────
def send_push(tokens: list[str], *, title: str, body: str, data: dict | None = None) -> int:
    """به فهرستی از توکن‌های خامِ FCM. no-opِ بی‌خطا اگر Push کانفیگ نشده باشد."""
    tokens = [t for t in tokens if t]
    if not tokens:
        return 0
    settings = get_settings()
    if not settings.push_enabled:
        logger.info(
            "[Push غیرفعال] «%s» به %d دستگاه ارسال نشد (FCM کانفیگ نشده است)", title, len(tokens)
        )
        return 0
    return _deliver(tokens, title=title, body=body, data=data or {})


def _oauth_access_token() -> str | None:
    """توکنِ OAuth2 از service-accountِ Firebase (FCM HTTP v1). None اگر آماده نشد."""
    settings = get_settings()
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError:
        logger.error("پکیجِ google-auth نصب نیست؛ Push کار نمی‌کند (pip install google-auth)")
        return None
    try:
        creds = service_account.Credentials.from_service_account_file(
            settings.fcm_credentials_file, scopes=[_FCM_SCOPE]
        )
        creds.refresh(Request())
        return creds.token
    except Exception:  # noqa: BLE001
        logger.exception("دریافتِ توکنِ OAuth برای FCM ناموفق بود")
        return None


def _deliver(tokens: list[str], *, title: str, body: str, data: dict) -> int:
    """POSTِ FCM HTTP v1 به‌ازای هر توکن. جدا از منطق تا در تست monkeypatch شود."""
    access = _oauth_access_token()
    if not access:
        return 0
    try:
        import httpx
    except ImportError:
        logger.error("httpx نصب نیست؛ Push ارسال نشد")
        return 0

    settings = get_settings()
    url = f"https://fcm.googleapis.com/v1/projects/{settings.fcm_project_id}/messages:send"
    headers = {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}
    # FCM فقط مقدارهای رشته‌ای در data می‌پذیرد.
    string_data = {str(k): str(v) for k, v in (data or {}).items()}
    sent = 0
    for tok in tokens:
        message = {
            "message": {
                "token": tok,
                "notification": {"title": title, "body": body},
                "data": string_data,
                "android": {"priority": "high"},
            }
        }
        try:
            resp = httpx.post(url, json=message, headers=headers, timeout=10)
            if resp.status_code == 200:
                sent += 1
            elif resp.status_code in (400, 404):
                # توکنِ نامعتبر/منقضی — یک کارِ پاک‌سازیِ دوره‌ای بعداً حذفش می‌کند.
                logger.info("توکنِ FCM نامعتبر است (%s)", resp.status_code)
            else:
                logger.warning("FCM %s: %s", resp.status_code, resp.text[:200])
        except Exception:  # noqa: BLE001
            logger.warning("ارسالِ FCM به یک دستگاه ناموفق بود", exc_info=True)
    return sent
