"""رفرش‌توکنِ نشستِ بلندمدت — «همیشه‌واردمانده»ی اپ موبایل.

جریان: login یک رفرشِ خام می‌دهد؛ اپ آن را امن نگه می‌دارد و هر وقت accessِ ۸ساعته
منقضی شد، `/api/auth/refresh` را صدا می‌زند. هر رفرش **چرخشی** است: توکنِ ارائه‌شده
همان‌جا باطل و یک رفرشِ تازه صادر می‌شود — پس یک رفرشِ لو‌رفته حداکثر یک بار کار می‌کند
و اگر بعداً دوباره ارائه شود (توکنِ باطل) رد می‌شود.

سه مرزِ ابطال: انقضای بلندمدت، ابطالِ صریح (خروج/چرخش)، و گره به `user.token_version`
تا **تغییرِ رمز همه‌ی رفرش‌ها را هم — مثلِ اکسس‌ها — یک‌جا بکشد**.
"""
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken
from app.models.tenant import Membership, Tenant
from app.models.user import User
from app.services.tokens import TOKEN_BYTES, hash_token

#: عمرِ رفرش. بلند تا کاربر ماه‌ها بی‌ورودِ دوباره بماند؛ چرخش خطرِ توکنِ رهاشده را می‌بندد.
REFRESH_TTL_DAYS = 60


def issue_refresh(db: Session, *, user: User, tenant_id: UUID | None) -> str:
    """رفرشِ تازه می‌سازد و مقدارِ خامش را برمی‌گرداند (تنها لحظه‌ای که خام وجود دارد)."""
    raw = secrets.token_urlsafe(TOKEN_BYTES)
    db.add(
        RefreshToken(
            token_hash=hash_token(raw),
            user_id=user.id,
            tenant_id=tenant_id,
            token_version=user.token_version or 0,
            expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TTL_DAYS),
        )
    )
    db.flush()
    return raw


def _load_valid(db: Session, raw: str) -> RefreshToken | None:
    """ردیفِ رفرش اگر وجود دارد، باطل‌نشده و منقضی‌نشده است — وگرنه None (بدونِ تفکیک)."""
    if not raw:
        return None
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(raw)).first()
    if row is None or row.revoked_at is not None:
        return None
    if row.expires_at <= datetime.now(timezone.utc):
        return None
    return row


def _active_membership(db: Session, user_id: UUID, tenant_id: UUID | None):
    """عضویتِ فعالِ کاربر در کسب‌وکارِ فعال — نشستی که کسب‌وکارش رفته نباید زنده بماند."""
    if tenant_id is None:
        return None
    return (
        db.query(Membership)
        .filter(
            Membership.user_id == user_id,
            Membership.tenant_id == tenant_id,
            Membership.status == "active",
        )
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .filter(Tenant.status == "active")
        .first()
    )


def rotate(db: Session, raw: str) -> tuple[User, UUID | None, str] | None:
    """رفرشِ ارائه‌شده را می‌سنجد، باطل می‌کند و یک رفرشِ تازه صادر می‌کند.

    خروجی: (کاربر، شناسه‌ی مستأجر، رفرشِ تازه‌ی خام) یا None اگر هر بررسی‌ای رد شود.
    وقتی None برمی‌گرداند هیچ چیزی باطل یا صادر نمی‌کند (رفرشِ سالم دست‌نخورده می‌ماند).
    """
    row = _load_valid(db, raw)
    if row is None:
        return None

    user = db.get(User, row.user_id)
    if user is None or not user.active:
        return None
    # رمز عوض شده → همه‌ی رفرش‌های نسلِ قبل مرده‌اند.
    if row.token_version != (user.token_version or 0):
        return None
    if _active_membership(db, user.id, row.tenant_id) is None:
        return None

    now = datetime.now(timezone.utc)
    row.revoked_at = now
    row.last_used_at = now
    db.flush()
    new_raw = issue_refresh(db, user=user, tenant_id=row.tenant_id)
    return user, row.tenant_id, new_raw


def revoke(db: Session, raw: str) -> None:
    """خروج: رفرش را باطل می‌کند. بی‌صدا — رفرشِ ناموجود/منقضی هم «باطل» است."""
    row = _load_valid(db, raw)
    if row is not None:
        row.revoked_at = datetime.now(timezone.utc)
        db.flush()
