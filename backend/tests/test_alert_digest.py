"""دایجستِ روزانه‌ی هشدارها (Push).

مسیرِ شبکه اجرا نمی‌شود: `send_push` monkeypatch می‌شود تا فقط فراخوانی و محتوایش
سنجیده شود. هدف: فقط مستأجرهای دارای دستگاه، فقط وقتی هشدارِ actionable هست،
با route=alerts.
"""
from datetime import date, timedelta
from decimal import Decimal

from app.models.banking import Check
from app.services import alert_digest, push

AS_OF = date(2026, 6, 15)


def _overdue_check(db, user):
    db.add(
        Check(
            type="payable",
            number="OD1",
            bank_name="ملی",
            amount=Decimal(5_000_000),
            issue_date=AS_OF - timedelta(days=30),
            due_date=AS_OF - timedelta(days=5),  # سررسیدگذشته → danger
            status="issued",
            created_by_id=user.id,
        )
    )
    db.flush()


def test_digest_pushes_when_actionable(db, user, tenant_id, monkeypatch):
    push.register_device(db, user_id=user.id, tenant_id=tenant_id, fcm_token="dev-A", platform="android")
    _overdue_check(db, user)

    captured: dict = {}
    monkeypatch.setattr(push, "send_push", lambda tokens, **k: captured.update(tokens=list(tokens), **k) or len(tokens))

    result = alert_digest.send_daily_digests(db, as_of=AS_OF)

    assert result["pushed"] == 1
    assert "dev-A" in captured["tokens"]
    assert "نیازِ رسیدگی" in captured["title"]
    assert captured["data"]["route"] == "alerts"


def test_digest_skips_when_nothing_actionable(db, user, tenant_id, monkeypatch):
    push.register_device(db, user_id=user.id, tenant_id=tenant_id, fcm_token="dev-B", platform="android")
    called: dict = {}
    monkeypatch.setattr(push, "send_push", lambda tokens, **k: called.setdefault("hit", True) or len(tokens))

    result = alert_digest.send_daily_digests(db, as_of=AS_OF)

    assert result["pushed"] == 0
    assert "hit" not in called  # هیچ هشداری نبود → هیچ اعلانی نرفت


def test_digest_ignores_tenants_without_devices(db, user, monkeypatch):
    _overdue_check(db, user)  # هشدار هست ولی هیچ دستگاهی ثبت نشده
    called: dict = {}
    monkeypatch.setattr(push, "send_push", lambda tokens, **k: called.setdefault("hit", True) or len(tokens))

    result = alert_digest.send_daily_digests(db, as_of=AS_OF)

    assert result["tenants"] == 0
    assert "hit" not in called
