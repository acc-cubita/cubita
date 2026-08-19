"""سرویسِ Push — no-opِ بی‌خطا، هدف‌گیریِ گیرنده، و مقاومتِ قلاب‌ها در برابرِ خطا.

مسیرِ شبکه (`_deliver`) هرگز در تست اجرا نمی‌شود: push_enabled در تست False است، پس
send_push قبل از رسیدن به شبکه no-op می‌کند. جایی که تحویل لازم است monkeypatch می‌شود.
"""
from app.services import push


def test_send_push_is_noop_when_unconfigured(monkeypatch):
    called = {}
    monkeypatch.setattr(push, "_deliver", lambda *a, **k: called.setdefault("hit", True))
    # FCM کانفیگ نشده (تست) → _deliver اصلاً صدا زده نمی‌شود.
    assert push.send_push(["t1", "t2"], title="a", body="b") == 0
    assert "hit" not in called


def test_send_push_ignores_empty_token_list():
    assert push.send_push([], title="a", body="b") == 0
    assert push.send_push([None, ""], title="a", body="b") == 0


def test_notify_user_collects_all_device_tokens(client, db, user, monkeypatch):
    client.post("/api/devices", json={"fcm_token": "d1"})
    client.post("/api/devices", json={"fcm_token": "d2"})

    captured = {}
    monkeypatch.setattr(
        push, "send_push", lambda tokens, **k: captured.update(tokens=sorted(tokens)) or len(tokens)
    )
    n = push.notify_user(db, user.id, title="t", body="b")
    assert n == 2
    assert captured["tokens"] == ["d1", "d2"]


def test_notify_tenant_targets_members_and_excludes_sender(db, user, tenant_id, monkeypatch):
    seen: list = []
    monkeypatch.setattr(push, "notify_user", lambda db, uid, **k: seen.append(uid) or 0)

    push.notify_tenant(db, tenant_id, title="t", body="b")
    assert user.id in seen  # مالکِ کسب‌وکار عضوِ فعال است و اعلان می‌گیرد.

    seen.clear()
    push.notify_tenant(db, tenant_id, title="t", body="b", exclude_user_id=user.id)
    assert user.id not in seen  # فرستنده‌ی خودش کنار گذاشته می‌شود.


def test_safe_notify_tenant_swallows_errors(db, tenant_id, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("مثلاً شبکه قطع شد")

    monkeypatch.setattr(push, "notify_tenant", boom)
    # نباید استثنا بیرون بدهد — قلابِ رویداد نباید تراکنش را بشکند.
    push.safe_notify_tenant(db, tenant_id, title="t", body="b")
