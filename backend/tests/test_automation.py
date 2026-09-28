from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.deps import Principal, get_principal
from app.main import app
from app.models.tenant import Membership, Tenant
from app.models.user import Role, User
from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant


@pytest.fixture
def actors(db, user, tenant_id):
    def make(name, actions=("view", "create", "update")):
        u = User(name=name, email=f"{uuid4()}@example.invalid", hashed_password="not-a-login", active=True)
        role = Role(key=str(uuid4()), name=name, permissions={"automation": list(actions)})
        db.add_all([u, role])
        db.flush()
        m = Membership(user_id=u.id, tenant_id=tenant_id, role_id=role.id, status="active")
        db.add(m)
        db.flush()
        return Principal(u, m)
    owner = Principal(user, db.query(Membership).filter_by(user_id=user.id, tenant_id=tenant_id).one())
    return owner, make("فرستنده"), make("گیرنده"), make("بی‌ارتباط")


def as_user(p):
    app.dependency_overrides[get_principal] = lambda: p


@pytest.fixture
def office_enterprise_license(monkeypatch):
    from app.config import get_settings
    from app.licensing import state as license_state

    monkeypatch.setattr(get_settings(), "edition", "enterprise")
    license_ = [license_state.LicenseStatus(mode="active", writable=True, mods=frozenset({"automation"}))]
    # یک منبع برای گیت نوشتن و فهرست ماژول‌ها؛ هیچ مجوز واقعی یا فایلِ نصب لمس نمی‌شود.
    monkeypatch.setattr(license_state, "current", lambda _db: license_[0])
    monkeypatch.setattr(license_state, "peek", lambda: license_[0])
    return license_


def draft(client, **kwargs):
    response = client.post("/api/automation/letters", json={"kind": "incoming", "subject": "آزمایش نامه",
        "body": "متن نامه", "letter_date": "2026-09-27", **kwargs})
    assert response.status_code == 201, response.text
    return response.json()


def registered(client, **kwargs):
    row = draft(client, **kwargs)
    response = client.post(f"/api/automation/letters/{row['id']}/register", json={"version": row["version"]})
    assert response.status_code == 200, response.text
    return response.json()


def test_letter_lifecycle_and_idempotent_number(client, actors):
    _, sender, recipient, _ = actors
    as_user(sender)
    row = registered(client)
    path = f"/api/automation/letters/{row['id']}"
    assert row["number"] == 1
    assert client.post(path + "/register", json={"version": 1}).json()["number"] == 1
    assert registered(client)["number"] == 2
    assert registered(client, kind="outgoing")["number"] == 1
    ref = client.post(path + "/refer", json={"recipients": [str(recipient.user.id)], "instruction": "پاسخ بدهید"})
    assert ref.status_code == 200, ref.text
    rid = ref.json()["referrals"][0]["id"]
    assert client.post(path + "/archive", json={"version": row["version"]}).status_code == 409
    assert client.post(f"/api/automation/referrals/{rid}/complete", json={"response": "نباید"}).status_code == 404
    as_user(recipient)
    assert client.get("/api/automation/letters?unread=true").json()["items"][0]["id"] == row["id"]
    read = client.post(path + "/read").json()
    assert read["referrals"][0]["read_at"]
    assert client.get("/api/automation/letters?unread=true").json()["items"] == []
    assert client.post(f"/api/automation/referrals/{rid}/complete", json={"response": "انجام شد"}).status_code == 200
    assert client.post(f"/api/automation/referrals/{rid}/complete", json={"response": "بازنویسی"}).status_code == 409
    as_user(sender)
    archived = client.post(path + "/archive", json={"version": row["version"]})
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"
    assert {e["action"] for e in archived.json()["events"]} >= {"created", "registered", "referred", "read", "completed", "archived"}
    assert client.post(path + "/refer", json={"recipients": [str(recipient.user.id)], "instruction": "دوباره"}).status_code == 409


def test_private_letter_file_print_and_history_cannot_leak(client, actors):
    owner, sender, _, stranger = actors
    as_user(sender)
    row = draft(client)
    path = f"/api/automation/letters/{row['id']}"
    uploaded = client.post(path + "/attachments?filename=sample.pdf", content=b"%PDF-1.4\nexample")
    assert uploaded.status_code == 200, uploaded.text
    aid = uploaded.json()["attachments"][0]["id"]
    assert "content" not in uploaded.json()["attachments"][0]
    as_user(stranger)
    assert client.get("/api/automation/letters?box=all").json()["items"] == []
    for suffix in ("", "/print"):
        assert client.get(path + suffix).status_code == 404
    assert client.get(f"/api/automation/attachments/{aid}").status_code == 404
    assert client.delete(f"/api/automation/attachments/{aid}").status_code == 404
    as_user(owner)
    assert client.get(path).status_code == 200
    assert client.get(f"/api/automation/attachments/{aid}").content.startswith(b"%PDF-")


def test_draft_edit_version_lock_and_registered_immutability(client):
    row = draft(client, sender="نام جعلی")
    path = f"/api/automation/letters/{row['id']}"
    assert row["sender"] == row["creator_name"]
    payload = {"kind": "internal", "subject": "ویرایش", "sender": "نام جعلی دوم", "letter_date": "2026-09-27", "version": 1}
    edited = client.put(path, json=payload)
    assert edited.status_code == 200
    assert edited.json()["sender"] == row["sender"]
    assert client.put(path, json=payload).status_code == 409
    client.post(path + "/register", json={"version": 2})
    payload["version"] = 3
    assert client.put(path, json=payload).status_code == 409
    assert client.post(path + "/attachments?filename=a.pdf", content=b"%PDF-1.4").status_code == 409


@pytest.mark.parametrize("name,content,expected", [("x.html", b"<script>x</script>", 400),
    ("x.pdf", b"not a PDF", 400), ("x.pdf", b"", 413), ("x.pdf", b"%PDF-" + b"a" * (5*1024*1024), 413)],
    ids=["html", "invalid-pdf", "empty", "oversized"])
def test_invalid_uploads(client, name, content, expected):
    row = draft(client)
    assert client.post(f"/api/automation/letters/{row['id']}/attachments", params={"filename": name}, content=content).status_code == expected


def test_referral_recipient_permissions_and_duplicate(client, actors):
    _, _, recipient, stranger = actors
    row = registered(client)
    path = f"/api/automation/letters/{row['id']}/refer"
    data = {"recipients": [str(recipient.user.id)], "instruction": "رسیدگی"}
    assert client.post(path, json=data).status_code == 200
    assert client.post(path, json=data).status_code == 409
    stranger.membership.status = "disabled"
    assert client.post(path, json={**data, "recipients": [str(stranger.user.id)]}).status_code == 400
    assert client.post(path, json={**data, "recipients": [str(uuid4())]}).status_code == 400


def test_no_permission_and_expired_recipient(client, actors, db):
    _, _, recipient, stranger = actors
    stranger.membership.permissions = {"calendar": ["view"]}
    db.flush()
    as_user(Principal(stranger.user, stranger.membership))
    # عضوِ عادی می‌تواند کارتابلِ خصوصی داشته باشد، ولی نامهٔ بی‌ارتباط را نمی‌بیند.
    assert client.get("/api/automation/letters").json()["items"] == []
    assert client.get("/api/automation/recipients").status_code == 403
    assert client.post("/api/automation/letters", json={"kind": "internal", "subject": "بدون مجوز", "letter_date": "2026-09-27"}).status_code == 403
    as_user(actors[0])
    recipient.membership.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.flush()
    assert str(recipient.user.id) not in [r["id"] for r in client.get("/api/automation/recipients").json()]


@pytest.mark.parametrize("edition", ["cloud", "enterprise"])
def test_staff_sender_recipient_and_file_send(client, actors, db, edition, request):
    if edition == "enterprise":
        request.getfixturevalue("office_enterprise_license")
    owner, _, courier, stranger = actors
    courier.membership.permissions = {"automation": ["view", "create", "update"], "marketplace": ["view", "deliver"]}
    stranger.membership.permissions = {"calendar": ["view"]}
    db.flush()
    as_user(Principal(courier.user, courier.membership))
    options = client.get("/api/automation/recipients")
    assert options.status_code == 200
    assert {r["id"] for r in options.json()} >= {str(owner.user.id), str(courier.user.id)}
    assert next(r["role_name"] for r in options.json() if r["id"] == str(owner.user.id)) == owner.role.name
    assert all(set(r) == {"id", "name", "role_name"} for r in options.json())
    row = draft(client, sender="دیگری", addressee="نام آزاد")
    assert row["sender"] == courier.user.name
    path = f"/api/automation/letters/{row['id']}"
    bad = client.post(path + "/send", json={"version": row["version"], "recipient_id": str(uuid4())})
    assert bad.status_code == 400
    assert client.get(path).json()["status"] == "draft"
    blob = b"%PDF-1.4\nattachment"
    row = client.post(path + "/attachments?filename=note.pdf", content=blob).json()
    sent = client.post(path + "/send", json={"version": row["version"], "recipient_id": str(owner.user.id),
                                        "instruction": "بررسی کنید"})
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "registered"
    assert sent.json()["number"] == 1
    assert sent.json()["addressee"] == owner.user.name
    assert sent.json()["sender"] == courier.user.name
    assert sent.json()["referrals"][0]["to_user_id"] == str(owner.user.id)
    assert sent.json()["attachments"][0]["filename"] == "note.pdf"
    assert client.post(path + "/send", json={"version": row["version"], "recipient_id": str(owner.user.id)}).status_code == 409
    as_user(Principal(stranger.user, stranger.membership))
    assert client.get(path).status_code == 404
    as_user(Principal(courier.user, courier.membership))
    referred = client.post(path + "/refer", json={"recipients": [str(stranger.user.id)], "instruction": "پاسخ بدهید"})
    assert referred.status_code == 200, referred.text
    ref_id = next(r["id"] for r in referred.json()["referrals"] if r["to_user_id"] == str(stranger.user.id))
    as_user(Principal(stranger.user, stranger.membership))
    assert client.get(path).status_code == 200
    assert client.get(f"/api/automation/attachments/{sent.json()['attachments'][0]['id']}").content == blob
    assert client.post(f"/api/automation/referrals/{ref_id}/complete", json={"response": "انجام شد"}).status_code == 200
    as_user(owner)
    assert client.get("/api/automation/letters?box=inbox").json()["items"][0]["id"] == row["id"]
    assert client.get(f"/api/automation/attachments/{sent.json()['attachments'][0]['id']}").content == blob


def test_enterprise_expired_license_keeps_private_mail_readable(client, actors, db, office_enterprise_license):
    from app.licensing.state import LicenseStatus

    _, sender, recipient, _ = actors
    as_user(sender)
    row = draft(client, kind="internal")
    path = f"/api/automation/letters/{row['id']}"
    blob = b"%PDF-1.4\nenterprise-private-file"
    row = client.post(path + "/attachments?filename=enterprise.pdf", content=blob).json()
    sent = client.post(path + "/send", json={"version": row["version"], "recipient_id": str(recipient.user.id)})
    assert sent.status_code == 200, sent.text
    recipient.membership.permissions = {"calendar": ["view"]}
    db.flush()
    office_enterprise_license[0] = LicenseStatus(mode="expired", writable=False,
        message="مجوز شرکت منقضی شده است.", mods=frozenset({"automation"}))
    as_user(Principal(recipient.user, recipient.membership))
    assert client.get(path).status_code == 200
    assert client.get(f"/api/automation/attachments/{sent.json()['attachments'][0]['id']}").content == blob
    referral = sent.json()["referrals"][0]["id"]
    response = client.post(f"/api/automation/referrals/{referral}/complete", json={"response": "اقدام شد"})
    assert response.status_code == 402, response.text
    as_user(sender)
    assert client.post("/api/automation/letters", json={"kind": "internal", "subject": "تازه",
        "letter_date": "2026-09-28"}).status_code == 402


def test_enterprise_automation_requires_licensed_module(client, office_enterprise_license):
    from app.licensing.state import LicenseStatus

    office_enterprise_license[0] = LicenseStatus(mode="active", writable=True, mods=frozenset({"accounting"}))
    for path in ("/api/automation/letters", "/api/automation/recipients"):
        assert client.get(path).status_code == 403
    assert client.post("/api/automation/letters", json={"kind": "internal", "subject": "تازه",
        "letter_date": "2026-09-28"}).status_code == 403


def test_recipient_response_still_obeys_subscription(client, actors, db, tenant_id):
    from app.models.subscription import Subscription
    from app.services.subscriptions import GRACE_DAYS

    _, sender, recipient, _ = actors
    as_user(sender)
    row = registered(client)
    path = f"/api/automation/letters/{row['id']}"
    referred = client.post(path + "/refer", json={"recipients": [str(recipient.user.id)], "instruction": "پاسخ"}).json()
    recipient.membership.permissions = {"calendar": ["view"]}
    db.query(Subscription).filter_by(tenant_id=tenant_id).delete()
    db.add(Subscription(tenant_id=tenant_id, starts_at=datetime.now(timezone.utc) - timedelta(days=365),
                        expires_at=datetime.now(timezone.utc) - timedelta(days=GRACE_DAYS + 1)))
    db.flush()
    as_user(Principal(recipient.user, recipient.membership))
    assert client.get(path).status_code == 200
    assert client.post(f"/api/automation/referrals/{referred['referrals'][0]['id']}/complete", json={"response": "اقدام"}).status_code == 402
    recipient.membership.tenant.is_trial = True
    db.flush()
    assert client.get(path).status_code == 402


def test_filters_pagination_print_escaping(client, actors):
    _, sender, recipient, _ = actors
    as_user(sender)
    row = registered(client, subject="<script>alert(1)</script>", body="<img src=x onerror=alert(2)>")
    path = f"/api/automation/letters/{row['id']}"
    printed = client.get(path + "/print")
    assert printed.status_code == 200
    assert "<script>" not in printed.text and "&lt;script&gt;" in printed.text
    assert client.get("/api/automation/letters?box=all&q=پیدانشد").json()["items"] == []
    for _ in range(3):
        registered(client)
    first = client.get("/api/automation/letters?box=all&limit=2").json()
    second = client.get("/api/automation/letters", params={"box": "all", "limit": 2, "cursor": first["next_cursor"]}).json()
    assert len({r["id"] for r in first["items"] + second["items"]}) == 4
    client.post(path + "/refer", json={"recipients": [str(recipient.user.id)], "instruction": "فوری", "due_date": "2000-01-01"})
    as_user(recipient)
    assert len(client.get("/api/automation/letters?overdue=true").json()["items"]) == 1


def test_cross_tenant_explicit_scope_and_rls(client, actors, db, tenant_id):
    row = registered(client)
    other = Tenant(name="دیگری", slug=f"other-{uuid4()}", status="active")
    db.add(other)
    db.flush()
    # همان هویت در کسب‌وکاری دیگر: دانستن شناسهٔ نامه دسترسی نمی‌دهد.
    principal = actors[0]
    principal.tenant_id = other.id
    as_user(principal)
    assert client.get(f"/api/automation/letters/{row['id']}").status_code == 404
    bind_session_tenant(db, other.id)
    apply_tenant_to_transaction(db, other.id)
    assert db.execute(text("select count(*) from office_letters")).scalar() == 0
    bind_session_tenant(db, tenant_id)
    apply_tenant_to_transaction(db, tenant_id)


def test_events_append_only(client, db):
    row = draft(client)
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("UPDATE office_events SET description='rewrite' WHERE letter_id=:id"), {"id": row["id"]})


def test_attachment_roundtrips_through_existing_backup(client):
    from app.routers.backup import _de, _ser
    from app.models.automation import OfficeAttachment
    blob = b"%PDF-1.4\n binary\x00\xff"
    assert _de(OfficeAttachment.__table__.c.content, _ser(blob)) == blob


def test_full_backup_restore_preserves_letter_referral_file_and_history(client, actors, db):
    row = draft(client)
    path = f"/api/automation/letters/{row['id']}"
    blob = b"%PDF-1.4\nroundtrip\x00\xff"
    row = client.post(path + "/attachments?filename=نامه.pdf", content=blob).json()
    aid = row["attachments"][0]["id"]
    row = client.post(path + "/register", json={"version": row["version"]}).json()
    assert client.post(path + "/refer", json={"recipients": [str(actors[2].user.id)], "instruction": "بررسی"}).status_code == 200
    before = client.get("/api/backup/export").json()
    response = client.post("/api/backup/import", json=before)
    assert response.status_code == 200, response.text
    db.expire_all()
    after = client.get("/api/backup/export").json()
    for table in ("office_letters", "office_referrals", "office_attachments", "office_events"):
        assert sorted(before["tables"][table], key=lambda r: r["id"]) == sorted(after["tables"][table], key=lambda r: r["id"])
    assert client.get(f"/api/automation/attachments/{aid}").content == blob


def test_attachment_limits_delete_and_freeze(client):
    row = draft(client)
    path = f"/api/automation/letters/{row['id']}"
    for n in range(10):
        uploaded = client.post(path + "/attachments", params={"filename": f"{n}.png"}, content=b"\x89PNG\r\n\x1a\nbytes")
        assert uploaded.status_code == 200
    assert client.post(path + "/attachments?filename=full.pdf", content=b"%PDF-x").status_code == 409
    aid = uploaded.json()["attachments"][0]["id"]
    deleted = client.delete(f"/api/automation/attachments/{aid}")
    assert deleted.status_code == 200
    assert len(deleted.json()["attachments"]) == 9
    assert client.get(f"/api/automation/attachments/{aid}").status_code == 404
    assert client.post(path + "/register", json={"version": deleted.json()["version"]}).status_code == 200
    aid = deleted.json()["attachments"][0]["id"]
    assert client.delete(f"/api/automation/attachments/{aid}").status_code == 409


def test_view_only_and_cross_tenant_recipient_rejected(client, actors, db):
    row = registered(client)
    path = f"/api/automation/letters/{row['id']}"
    other = Tenant(name="شرکت دوم", slug=f"other-{uuid4()}", status="active")
    db.add(other)
    db.flush()
    recipient = actors[2]
    recipient.membership.tenant_id = other.id
    db.flush()
    assert client.post(path + "/refer", json={"recipients": [str(recipient.user.id)], "instruction": "بررسی"}).status_code == 400
    sender = actors[1]
    sender.membership.permissions = {"automation": ["view"]}
    db.flush()
    as_user(Principal(sender.user, sender.membership))
    assert client.post("/api/automation/letters", json={"subject": "نباید", "kind": "internal", "letter_date": "2026-09-27"}).status_code == 403
    assert client.post(path + "/register", json={"version": 1}).status_code == 403


def test_large_number_search_is_safe_and_numbering_accepts_bigint(client, db):
    from app.models.counters import DocumentCounter
    counter = db.query(DocumentCounter).filter_by(doc_type="office_incoming").one()
    counter.last_number = 3000000000
    db.flush()
    row = registered(client)
    assert row["number"] == 3000000001
    assert client.get("/api/automation/letters", params={"box": "all", "q": "9" * 300}).status_code == 200
    assert client.get("/api/automation/letters", params={"box": "all", "q": "۳۰۰۰۰۰۰۰۰۱"}).json()["items"][0]["id"] == row["id"]
