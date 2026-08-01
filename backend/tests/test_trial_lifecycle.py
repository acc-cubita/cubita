"""چرخه‌ی عمرِ آزمایشی: یادآوریِ نزدیکِ انقضا و حذفِ بعد از بافرِ ایمنی.

مهم‌ترین دو تست:
- `test_expired_trial_is_purged_only_after_the_grace_buffer` — حذفِ دقیقاً سرِ روزِ
  ۱۴، خریدِ یک‌روز-دیرِ کاربر را نابود می‌کرد؛ بافر همان چیزی است که این را می‌گیرد.
- `test_reminder_is_sent_once` — یادآوریِ روزانه‌ی تکراری، آزارِ کاربر است نه کمک.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.services.provisioning import signup_new_business
from app.services.trial_lifecycle import process_trials

PASSWORD = "AStrongPassword2026"


@pytest.fixture
def reminders(monkeypatch):
    sent: list[dict] = []

    def fake(to, name, days_left, plans_url):
        sent.append({"to": to, "days_left": days_left})
        return True

    monkeypatch.setattr("app.services.trial_lifecycle.mailer.send_trial_reminder", fake)
    return sent


def _new_trial(db):
    tenant, user = signup_new_business(
        db,
        business_name="آزمایشی",
        owner_name="مالک",
        email=f"life-{uuid.uuid4().hex[:8]}@cubita-test.ir",
        password=PASSWORD,
    )
    db.flush()
    return tenant, user


def _set_trial_expiry(db, tenant_id, *, days_from_now: int):
    sub = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).one()
    sub.expires_at = datetime.now(timezone.utc) + timedelta(days=days_from_now)
    db.flush()


def _exists(db, tenant_id) -> bool:
    return db.query(Tenant).filter(Tenant.id == tenant_id).count() == 1


# --- یادآوری -------------------------------------------------------------------------


def test_reminder_is_sent_once_near_expiry(db, reminders):
    tenant, user = _new_trial(db)
    _set_trial_expiry(db, tenant.id, days_from_now=2)  # داخلِ آستانه‌ی ۳ روز

    process_trials(db)
    assert any(r["to"] == user.email for r in reminders), "یادآوری برای مالک نرفت"
    assert tenant.trial_reminder_sent_at is not None

    # اجرای دوباره نباید دوباره بفرستد
    before = len(reminders)
    process_trials(db)
    assert len(reminders) == before, "یادآوری دوباره فرستاده شد"


def test_no_reminder_when_far_from_expiry(db, reminders):
    tenant, _ = _new_trial(db)
    _set_trial_expiry(db, tenant.id, days_from_now=10)

    process_trials(db)
    assert reminders == []
    assert tenant.trial_reminder_sent_at is None


# --- حذف -----------------------------------------------------------------------------


def test_expired_trial_is_purged_only_after_the_grace_buffer(db, reminders):
    grace = get_settings().trial_purge_grace_days

    # منقضی ولی هنوز داخلِ بافر → نباید حذف شود
    within, _ = _new_trial(db)
    _set_trial_expiry(db, within.id, days_from_now=-(grace - 1))
    process_trials(db)
    assert _exists(db, within.id), "حسابِ داخلِ بافرِ ایمنی نباید حذف شود"

    # منقضی و گذشته از بافر → حذف
    past, _ = _new_trial(db)
    _set_trial_expiry(db, past.id, days_from_now=-(grace + 1))
    result = process_trials(db)
    assert not _exists(db, past.id), "حسابِ گذشته از بافر باید حذف شود"
    assert result["purged"] >= 1


def test_active_trial_is_never_purged(db, reminders):
    tenant, _ = _new_trial(db)
    _set_trial_expiry(db, tenant.id, days_from_now=5)
    process_trials(db)
    assert _exists(db, tenant.id)
