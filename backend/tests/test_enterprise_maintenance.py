"""نگهداریِ «کوبیتا سازمانی» (ENTERPRISE_PLAN.md، M6).

چهار چیز که روی سرورِ آفلاینِ شرکت، بی ما، باید کار کنند:
۱. افزودنِ کارمند و بازگرداندنِ رمزِ فراموش‌شده **بدونِ ایمیل** — با کدِ ۱۶ نویسه‌ای.
۲. انتقالِ دفتر از ابر، با کاربرانی که روی سرورِ تازه نیستند.
۳. پشتیبانِ شبانه‌ای که شکستش دیده شود.
۴. زیپِ عیب‌یابی‌ای که هیچ رازی بیرون نبرد.
"""

import io
import json
import os
import time
import uuid
import zipfile

import pytest

from app.config import get_settings
from app.models.audit import AuditLog
from app.models.tenant import Membership
from app.models.user import Role, User
from app.onprem import maintenance as mnt
from app.onprem.provision import Layout, ProvisionError
from app.services import tokens

EMPLOYEE = "clerk@m6-test.example.com"


@pytest.fixture
def enterprise(monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, "edition", "enterprise")
    monkeypatch.setattr(settings, "license_dir", str(tmp_path))
    return settings


def _invite(client, email=EMPLOYEE):
    res = client.post(
        "/api/members/invite", json={"email": email, "name": "کارمند آزمون", "role_key": "accountant"}
    )
    assert res.status_code == 201, res.text
    return res.json()


# --- کدِ کوتاه ------------------------------------------------------------------


def test_short_code_is_forgiving_but_long_tokens_are_untouched():
    assert tokens.canonical("abcd-efgh-jkmn-pqrs") == "ABCDEFGHJKMNPQRS"
    #: O و I و L خطای رایجِ خواندن‌اند و به ۰ و ۱ برمی‌گردند.
    assert tokens.canonical("OOOO IIII LLLL 2222") == "0000111111112222"
    long = "x" * 43
    assert tokens.canonical(long) == long


def test_cloud_invite_still_sends_email_and_hides_code(client):
    body = _invite(client)
    assert body["code"] is None


def test_enterprise_invite_returns_code_that_activates_the_account(client, enterprise, db):
    body = _invite(client)
    assert body["email_sent"] is False
    code = body["code"]
    assert len(tokens.canonical(code)) == tokens.SHORT_LEN

    #: کارمند کد را با حروفِ کوچک و بی‌خط‌تیره تایپ می‌کند.
    typed = code.replace("-", "").lower()
    res = client.post("/api/auth/redeem-code", json={"code": typed, "password": "Clerk-Pass-2026", "name": "رضا"})
    assert res.status_code == 200, res.text
    user = db.query(User).filter(User.email == EMPLOYEE).one()
    membership = db.query(Membership).filter(Membership.user_id == user.id).one()
    assert membership.status == "active"
    assert user.name == "رضا"

    #: یک‌بارمصرف.
    again = client.post("/api/auth/redeem-code", json={"code": typed, "password": "Other-Pass-2026"})
    assert again.status_code == 400
    assert "کد" in again.json()["detail"]


def test_redeem_code_does_not_exist_in_cloud(client):
    res = client.post("/api/auth/redeem-code", json={"code": "AAAA-BBBB-CCCC-DDDD", "password": "Whatever-2026"})
    assert res.status_code == 404


def _active_employee(client, db):
    code = _invite(client)["code"]
    client.post("/api/auth/redeem-code", json={"code": code, "password": "Clerk-Pass-2026"})
    user = db.query(User).filter(User.email == EMPLOYEE).one()
    return db.query(Membership).filter(Membership.user_id == user.id).one()


def test_owner_reset_code_lets_employee_choose_a_new_password(client, enterprise, db, tenant_id):
    membership = _active_employee(client, db)
    res = client.post(f"/api/members/{membership.id}/reset-code")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["valid_hours"] == tokens.STAFF_RESET_HOURS

    ok = client.post("/api/auth/redeem-code", json={"code": body["code"], "password": "New-Clerk-Pass-2026"})
    assert ok.status_code == 200, ok.text
    #: مالک رمز را نمی‌داند، ولی صدورِ کد در دفترِ حسابرسی مانده است.
    entry = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "Membership", AuditLog.entity_id == membership.id)
        .one()
    )
    assert "بازنشانی" in entry.summary


def test_reset_code_guards(client, enterprise, db, user):
    own = db.query(Membership).filter(Membership.user_id == user.id).one()
    res = client.post(f"/api/members/{own.id}/reset-code")
    assert res.status_code == 409

    invited = _invite(client)
    res = client.post(f"/api/members/{invited['member']['id']}/reset-code")
    assert res.status_code == 400


def test_reset_code_refuses_owner_target(client, enterprise, db, tenant_id):
    membership = _active_employee(client, db)
    owner_role = db.query(Role).filter(Role.tenant_id == tenant_id, Role.key == "owner").one()
    membership.role_id = owner_role.id
    db.flush()
    db.expire(membership)
    res = client.post(f"/api/members/{membership.id}/reset-code")
    assert res.status_code == 409
    assert "cubita-server" in res.json()["detail"]


def test_reset_code_does_not_exist_in_cloud(client, db):
    res = client.post(f"/api/members/{uuid.uuid4()}/reset-code")
    assert res.status_code == 404


def test_server_side_owner_code_restores_owner_access(client, enterprise, db, user):
    issued = mnt.owner_reset_codes(db, user.email)
    assert [e for e, _, _ in issued] == [user.email]
    code = issued[0][2]
    res = client.post("/api/auth/redeem-code", json={"code": code, "password": "Owner-Back-2026"})
    assert res.status_code == 200, res.text
    assert mnt.owner_reset_codes(db, "nobody@example.com") == []


# --- انتقال از ابر -----------------------------------------------------------------


@pytest.fixture
def ledger_with_author(db, user, tenant_id):
    """یک ردیفِ دفتر که به کاربر ارجاع دارد — همان چیزی که انتقال را روی سرورِ تازه می‌شکست."""
    for summary in ("سندِ آزمونِ انتقال", "سندِ مالکِ ابری"):
        db.add(
            AuditLog(
                tenant_id=tenant_id, actor_id=user.id, actor_email=user.email, action="create",
                entity_type="Test", entity_id=uuid.uuid4(), summary=summary,
            )
        )
    db.flush()


def _user_ref(export, user_id):
    """ردیفِ آزمونِ `ledger_with_author` در خروجی: (جدول، ستون، ردیف)."""
    for row in export["tables"]["audit_log"]:
        if row["summary"] == "سندِ آزمونِ انتقال" and row["actor_id"] == str(user_id):
            return "audit_log", "actor_id", row
    raise AssertionError("ردیفِ آزمون در خروجی نیست")


def test_export_lists_users_without_password_hashes(client, user):
    export = client.get("/api/backup/export").json()
    emails = {u["email"] for u in export["users"]}
    assert user.email in emails
    assert "hashed_password" not in json.dumps(export["users"])
    assert "account_code_widths" in export["tenant_settings"]


def test_enterprise_import_recreates_missing_users_as_disabled_members(
    client, enterprise, db, user, ledger_with_author
):
    export = client.get("/api/backup/export").json()
    _table, col, row = _user_ref(export, user.id)

    #: کارمندِ ابری‌ای که روی این سرور نیست و یک سند زده است.
    ghost = str(uuid.uuid4())
    row[col] = ghost
    export["users"].append(
        {"id": ghost, "email": "ghost@m6-test.example.com", "name": "کارمندِ ابری", "role_key": "accountant",
         "member_status": "active", "permissions": None}
    )
    #: مالکِ ابری با شناسه‌ی دیگری ولی همان ایمیل — باید به مالکِ همین سرور نگاشته شود.
    cloud_owner = str(uuid.uuid4())
    text = json.dumps(export).replace(str(user.id), cloud_owner)
    payload = json.loads(text)

    res = client.post("/api/backup/import", json=payload)
    assert res.status_code == 200, res.text

    ghost_user = db.get(User, uuid.UUID(ghost))
    assert ghost_user is not None and ghost_user.email == "ghost@m6-test.example.com"
    membership = db.query(Membership).filter(Membership.user_id == ghost_user.id).one()
    #: صندلیِ مجوز نمی‌گیرد و تا مالک فعالش نکند کسی با آن وارد نمی‌شود.
    assert membership.status == "disabled"
    assert db.get(User, uuid.UUID(cloud_owner)) is None
    db.expire_all()
    authors = {
        a.actor_id for a in db.query(AuditLog).filter(AuditLog.summary == "سندِ آزمونِ انتقال").all()
    }
    assert authors == {uuid.UUID(ghost)}
    #: ردیف‌های مالکِ ابری (شناسه‌ی دیگر، همان ایمیل) به مالکِ همین سرور برگشتند.
    owner_row = db.query(AuditLog).filter(AuditLog.summary == "سندِ مالکِ ابری").one()
    assert owner_row.actor_id == user.id


def test_enterprise_import_rejects_old_file_without_users(client, enterprise, db, user, ledger_with_author):
    export = client.get("/api/backup/export").json()
    _table, col, row = _user_ref(export, user.id)
    row[col] = str(uuid.uuid4())
    export.pop("users")
    res = client.post("/api/backup/import", json=export)
    assert res.status_code == 400
    assert "پشتیبانِ تازه" in res.json()["detail"]


# --- پشتیبانِ شبانه -----------------------------------------------------------------


def _touch(path, hours_ago):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PGDMP")
    t = time.time() - hours_ago * 3600
    os.utime(path, (t, t))


def test_status_and_staleness(tmp_path):
    layout = Layout(tmp_path)
    assert mnt.status(layout).stale and mnt.is_due(layout)
    _touch(layout.backups / "nightly-a.dump", 30)
    s = mnt.status(layout)
    assert s.count == 1 and not s.stale and mnt.is_due(layout)
    _touch(layout.backups / "nightly-b.dump", 1)
    assert not mnt.is_due(layout)
    _touch(layout.backups / "nightly-c.dump", 60)
    os.utime(layout.backups / "nightly-b.dump", (time.time() - 50 * 3600,) * 2)
    os.utime(layout.backups / "nightly-a.dump", (time.time() - 55 * 3600,) * 2)
    assert mnt.status(layout).stale


def test_prune_keeps_pre_upgrade_dumps(tmp_path):
    layout = Layout(tmp_path)
    for i in range(5):
        _touch(layout.backups / f"nightly-{i}.dump", 100 - i)
    _touch(layout.backups / "pre-upgrade-x.dump", 500)
    assert mnt.prune(layout, keep=2) == 3
    names = sorted(p.name for p in layout.backups.glob("*.dump"))
    assert names == ["nightly-3.dump", "nightly-4.dump", "pre-upgrade-x.dump"]


def test_failed_backup_is_visible_until_one_succeeds(tmp_path, monkeypatch):
    layout = Layout(tmp_path)

    def broken(*_a, **_k):
        raise ProvisionError("pg_dump شکست خورد: دیسک پر است")

    monkeypatch.setattr(mnt, "dump", broken)
    with pytest.raises(ProvisionError):
        mnt.run_backup(layout, tmp_path, "postgresql+psycopg://u:p@127.0.0.1:5433/cubita")
    s = mnt.status(layout)
    assert s.stale and "دیسک پر است" in s.last_error

    def ok(_pg, lay, _url, name):
        target = lay.backups / name
        _touch(target, 0)
        return target

    monkeypatch.setattr(mnt, "dump", ok)
    mnt.run_backup(layout, tmp_path, "postgresql+psycopg://u:p@127.0.0.1:5433/cubita")
    s = mnt.status(layout)
    assert not s.stale and s.last_error is None and s.count == 1


def test_scheduler_tick_only_when_due(tmp_path, monkeypatch):
    layout = Layout(tmp_path)
    calls = []

    def ok(_pg, lay, _url, name):
        calls.append(name)
        target = lay.backups / name
        _touch(target, 0)
        return target

    monkeypatch.setattr(mnt, "dump", ok)
    sched = mnt.BackupScheduler(layout, tmp_path, "postgresql+psycopg://u:p@h/db")
    assert sched.tick() is not None
    assert sched.tick() is None
    assert len(calls) == 1


# --- زیپِ عیب‌یابی --------------------------------------------------------------------


def test_redact_hides_passwords_and_tokens():
    line = (
        "DATABASE_URL=postgresql+psycopg://cubita_app:s3cr3t@127.0.0.1:5433/cubita "
        "auth eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc_DEF-123"
    )
    out = mnt.redact(line)
    assert "s3cr3t" not in out and "eyJzdWIi" not in out
    assert "cubita_app" not in out or ":***@" in out


def test_diagnostics_zip_never_contains_secrets(tmp_path):
    layout = Layout(tmp_path)
    layout.env_file.write_text("JWT_SECRET=top-secret-value\n", encoding="utf-8")
    layout.secrets_file.write_text('{"app_password": "hunter2"}', encoding="utf-8")
    layout.logs.mkdir()
    (layout.logs / "CubitaApi.out.log").write_text(
        "connect postgresql+psycopg://cubita_migrate:hunter2@127.0.0.1:5433/cubita\nINFO ok\n", encoding="utf-8"
    )
    data = mnt.diagnostics_zip(layout, mnt.base_info(layout))
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        blob = "".join(zf.read(n).decode("utf-8") for n in names)
    assert "info.json" in names and "logs/CubitaApi.out.log" in names
    assert ".env" not in names and "secrets.json" not in names
    assert "hunter2" not in blob and "top-secret-value" not in blob
    assert "INFO ok" in blob


@pytest.fixture
def maintenance_client(client):
    """روترِ نگهداری فقط در بیلدِ سازمانی سوار است؛ اینجا روی همان اپِ تست سوارش می‌کنیم."""
    from app.main import app
    from app.routers import enterprise_maintenance

    before = len(app.router.routes)
    app.include_router(enterprise_maintenance.router)
    try:
        yield client
    finally:
        del app.router.routes[before:]


def test_maintenance_api(maintenance_client, enterprise, tmp_path):
    res = maintenance_client.get("/api/maintenance/backups")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 0 and body["stale"] is True
    #: در توسعه سرورِ نصب‌شده‌ای نیست؛ پشتیبانِ دستی صادقانه می‌گوید چرا.
    assert maintenance_client.post("/api/maintenance/backups/run").status_code == 503

    zres = maintenance_client.get("/api/maintenance/diagnostics")
    assert zres.status_code == 200
    with zipfile.ZipFile(io.BytesIO(zres.content)) as zf:
        info = json.loads(zf.read("info.json"))
    assert info["license"]["mode"] in {"trial", "trial_expired", "active", "grace", "expired", "clock", "mismatch", "invalid"}
    assert info["members"] >= 1
