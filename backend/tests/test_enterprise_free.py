"""«کوبیتا سازمانی» رایگان — ثبت‌نامِ پیامکی، مجوزِ دائمیِ سه‌کاربره، و مسیرِ آفلاینِ ستاد.

قاعده‌هایی که این تست‌ها نگه می‌دارند:
- رایگان **دائمی** است، سقفِ سه کاربر دارد و هیچ قابلیتِ پولی (مؤدیان) ندارد.
- کدِ پیامکی به **همان سرور** گره است و سقفِ تلاش دارد.
- ثبت‌نامِ دوباره‌ی همان سرور همان مجوز را برمی‌گرداند، نه ردیفِ تازه.
- رایگان و پولی یک مسیرِ صدور دارند؛ توکنِ پولی بی‌`tier` می‌ماند (سازگار با نسخه‌های قبلی).
"""

from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app.licensing import keys
from app.licensing import state as license_state
from app.licensing.token import LicenseError, verify
from app.models.enterprise_license_registry import EnterpriseLicenseEvent, EnterpriseLicenseRecord
from app.models.tenant import Tenant
from app.services import enterprise_free as free
from app.services import sms
from tests.test_enterprise_admin import (  # noqa: F401 — فیکسچرها
    FP_A,
    FP_B,
    _create,
    enterprise,
    license_client,
    public_client,
    request_code,
    signing,
)

PHONE = "09121234567"


@pytest.fixture
def inbox(monkeypatch):
    """پیامک‌های فرستاده‌شده — به‌جای ملی‌پیامک."""
    sent: dict[str, str] = {}

    def fake_send(to, code):
        sent[sms.normalize_phone(to)] = code
        return True

    monkeypatch.setattr(sms, "send_verification_code", fake_send)
    return sent


def _register(db, inbox, req, phone=PHONE, org="شرکت رایگان"):
    free.send_code(db, phone, req)
    return free.activate(db, phone, inbox[sms.normalize_phone(phone)], req, org)


# --- سرویسِ ابر ---------------------------------------------------------------


def test_free_registration_issues_perpetual_three_seat_token(db, signing, inbox):
    token = _register(db, inbox, request_code(FP_A))
    payload = verify(token, keys.TRUSTED_PUBLIC_KEYS)
    assert payload["tier"] == "free"
    assert payload["seats"] == free.FREE_SEATS == 3
    assert payload["feat"] == []
    assert "exp" not in payload  # دائمی
    assert payload["fp"] == FP_A

    record = db.query(EnterpriseLicenseRecord).filter_by(lic_id=payload["lic"]).one()
    assert (record.tier, record.contact, record.org_name) == ("free", PHONE, "شرکت رایگان")
    events = {(e.kind, e.actor) for e in db.query(EnterpriseLicenseEvent).filter_by(license_id=record.id)}
    assert ("activate", "free") in events


def test_paid_token_has_no_tier(db, signing):
    # توکنِ پولی باید بایت‌به‌بایت مثلِ قبل بماند؛ نسخه‌های قدیمی‌تر `tier` را نمی‌شناسند.
    from app.services import enterprise_licenses as svc

    _record, code = _create(db)
    payload = verify(svc.activate_online(db, code, request_code(FP_A)), keys.TRUSTED_PUBLIC_KEYS)
    assert "tier" not in payload


def test_wrong_codes_lock_the_code(db, signing, inbox):
    req = request_code(FP_A)
    free.send_code(db, PHONE, req)
    right = inbox[PHONE]
    wrong = "000000" if right != "000000" else "111111"
    for _ in range(free.MAX_ATTEMPTS):
        with pytest.raises(LicenseError):
            free.activate(db, PHONE, wrong, req, None)
    # بعد از سقف حتی کدِ درست هم رد می‌شود.
    with pytest.raises(LicenseError):
        free.activate(db, PHONE, right, req, None)


def test_code_is_bound_to_the_server_it_was_sent_for(db, signing, inbox):
    free.send_code(db, PHONE, request_code(FP_A, install="inst-A"))
    with pytest.raises(LicenseError, match="کدِ تأیید"):
        free.activate(db, PHONE, inbox[PHONE], request_code(FP_B, install="inst-B"), None)


def test_same_server_registering_again_gets_the_same_license(db, signing, inbox):
    req = request_code(FP_A)
    first = verify(_register(db, inbox, req), keys.TRUSTED_PUBLIC_KEYS)["lic"]
    # نصبِ دوباره، با یک جزءِ عوض‌شده‌ی اثرانگشت و شماره‌ی دیگر.
    again = request_code({**FP_A, "volume_serial": "z" * 32})
    second = verify(_register(db, inbox, again, phone="09351112233"), keys.TRUSTED_PUBLIC_KEYS)["lic"]
    assert first == second
    record = db.query(EnterpriseLicenseRecord).filter_by(lic_id=first).one()
    assert record.contact == "09351112233"
    assert db.query(EnterpriseLicenseRecord).filter_by(tier="free").count() == 1


def test_cloned_server_gets_its_own_free_license(db, signing, inbox):
    # همان install_id روی رایانه‌ی دیگر (تصویرِ کپی‌شده): رایگان است، «انتقال» لازم نیست.
    a = verify(_register(db, inbox, request_code(FP_A)), keys.TRUSTED_PUBLIC_KEYS)["lic"]
    b = verify(_register(db, inbox, request_code(FP_B)), keys.TRUSTED_PUBLIC_KEYS)["lic"]
    assert a != b


def test_bad_phone_is_refused_before_any_sms(db, signing, inbox):
    with pytest.raises(LicenseError, match="شماره‌ی همراه"):
        free.send_code(db, "12345", request_code(FP_A))
    assert inbox == {}


# --- مسیرِ عمومیِ ابر -----------------------------------------------------------


def test_public_free_endpoints(public_client, db, signing, inbox):
    req = request_code(FP_A)
    r = public_client.post("/api/enterprise/free/send-code", json={"phone": "۰۹۱۲ ۱۲۳ ۴۵۶۷", "request_code": req})
    assert r.status_code == 200, r.text
    assert r.json()["phone"] == "0912****567"
    assert PHONE in inbox

    r = public_client.post(
        "/api/enterprise/free/activate", json={"phone": PHONE, "code": "999999x", "request_code": req}
    )
    assert r.status_code == 400

    r = public_client.post(
        "/api/enterprise/free/activate",
        json={"phone": PHONE, "code": inbox[PHONE], "request_code": req, "org": "شرکت وب"},
    )
    assert r.status_code == 200, r.text
    assert verify(r.json()["token"], keys.TRUSTED_PUBLIC_KEYS)["org"] == "شرکت وب"


def test_public_send_code_is_limited_per_phone(public_client, db, signing, inbox):
    req = request_code(FP_A)
    codes = [
        public_client.post("/api/enterprise/free/send-code", json={"phone": PHONE, "request_code": req}).status_code
        for _ in range(4)
    ]
    assert codes == [200, 200, 200, 429]


# --- سرورِ سازمانی: ثبت‌نام از راهِ ابر -----------------------------------------


def _route_to_cloud(db, monkeypatch):
    def fake_post(url, json, timeout):
        try:
            if url.endswith("/api/enterprise/free/send-code"):
                phone = free.send_code(db, json["phone"], json["request_code"])
                return httpx.Response(200, json={"phone": free.mask_phone(phone), "expires_in": 600})
            if url.endswith("/api/enterprise/free/activate"):
                token = free.activate(db, json["phone"], json["code"], json["request_code"], json["org"])
                return httpx.Response(200, json={"token": token})
        except LicenseError as exc:
            return httpx.Response(400, json={"detail": str(exc)})
        raise AssertionError(url)

    monkeypatch.setattr(httpx, "post", fake_post)


def test_enterprise_server_registers_free_through_cloud(license_client, db, enterprise, signing, inbox, monkeypatch, tenant_id):
    _route_to_cloud(db, monkeypatch)
    r = license_client.post("/api/license/free/send-code", json={"phone": PHONE})
    assert r.status_code == 200, r.text
    assert r.json()["phone"] == "0912****567"

    r = license_client.post("/api/license/free/activate", json={"phone": PHONE, "code": "123"})
    assert r.status_code == 422  # کوتاه‌تر از کمینه

    r = license_client.post("/api/license/free/activate", json={"phone": PHONE, "code": inbox[PHONE]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["mode"], body["tier"], body["seats"], body["expires_at"]) == ("active", "free", 3, None)
    assert body["writable"] is True
    # نامِ سازمان، وقتی مالک چیزی ننوشت، نامِ کسب‌وکار است.
    assert body["org"] == db.get(Tenant, tenant_id).name
    assert db.get(Tenant, tenant_id).max_users == 3


def test_enterprise_server_relays_wrong_code(license_client, db, enterprise, signing, inbox, monkeypatch):
    _route_to_cloud(db, monkeypatch)
    license_client.post("/api/license/free/send-code", json={"phone": PHONE})
    r = license_client.post("/api/license/free/activate", json={"phone": PHONE, "code": "0000000"})
    assert r.status_code == 400
    assert "کدِ تأیید" in r.json()["detail"]


def test_free_license_locks_moadian_with_upgrade_message(db, enterprise, signing, inbox):
    from app.deps import require_feature

    license_state.install(db, _register(db, inbox, request_code(FP_A)))
    status_ = license_state.current(db)
    assert (status_.tier, status_.feat) == ("free", frozenset())

    checker = require_feature("moadian")
    principal = SimpleNamespace(user=object())
    with pytest.raises(HTTPException) as exc:
        checker(principal=principal, db=db)
    assert exc.value.status_code == 402
    assert "نسخه‌ی رایگان" in exc.value.detail


def test_trial_expired_message_points_to_free_registration():
    from datetime import datetime, timedelta, timezone

    from app.models.enterprise_license import EnterpriseLicense

    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    row = EnterpriseLicense(id=1, installed_at=now - timedelta(days=40), token=None, last_seen_at=now)
    status_ = license_state.evaluate(row, now, FP_A, keys.TRUSTED_PUBLIC_KEYS, 30)
    assert status_.mode == "trial_expired" and not status_.writable
    assert "ثبت‌نامِ رایگان" in status_.message


def test_enterprise_seat_cap_points_to_commercial_license(db, enterprise, tenant_id, user):
    from app.services import members

    db.get(Tenant, tenant_id).max_users = 1
    db.flush()
    with pytest.raises(HTTPException) as exc:
        members.invite_member(
            db, tenant_id=tenant_id, inviter=user, email="new@example.com", name="تازه", role_key="accountant"
        )
    assert exc.value.status_code == 409
    assert "مجوزِ تجاری" in exc.value.detail


# --- پنلِ ستاد: مجوزِ رایگان برای سرورِ بی‌اینترنت --------------------------------


def test_staff_creates_free_license_for_offline_server(staff_client, db, signing):
    c = staff_client("owner")
    r = c.post(
        "/api/admin/licenses",
        json={"org_name": "شرکت بی‌اینترنت", "tier": "free", "seats": 50, "days": 9999, "feat": ["moadian"]},
    )
    assert r.status_code == 201, r.text
    lic = r.json()["license"]
    # سقف، مدت و قابلیت‌ها از سیاستِ رایگان می‌آیند، نه از فرم.
    assert (lic["tier"], lic["seats"], lic["expires_at"], lic["feat"]) == ("free", 3, None, [])
    assert r.json()["activation_code"]

    r = c.post(f"/api/admin/licenses/{lic['id']}/issue", json={"request_code": request_code(FP_A)})
    assert r.status_code == 200, r.text
    assert verify(r.json()["token"], keys.TRUSTED_PUBLIC_KEYS)["tier"] == "free"

    assert [x["id"] for x in c.get("/api/admin/licenses", params={"tier": "free"}).json()] == [lic["id"]]
    assert c.get("/api/admin/licenses", params={"tier": "paid"}).json() == []
