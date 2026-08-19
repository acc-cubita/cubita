"""ثبت/حذفِ دستگاهِ Push و گاردِ احراز هویت."""
from app.models.device_token import DeviceToken


def test_register_device(client, db, user):
    resp = client.post("/api/devices", json={"fcm_token": "tokAAA", "platform": "android"})
    assert resp.status_code == 204, resp.text
    row = db.query(DeviceToken).filter(DeviceToken.fcm_token == "tokAAA").one()
    assert row.user_id == user.id
    assert row.platform == "android"


def test_register_is_idempotent_upsert(client, db):
    client.post("/api/devices", json={"fcm_token": "tokBBB"})
    client.post("/api/devices", json={"fcm_token": "tokBBB"})
    assert db.query(DeviceToken).filter(DeviceToken.fcm_token == "tokBBB").count() == 1


def test_unregister_device(client, db):
    client.post("/api/devices", json={"fcm_token": "tokCCC"})
    resp = client.request("DELETE", "/api/devices", params={"token": "tokCCC"})
    assert resp.status_code == 204
    assert db.query(DeviceToken).filter(DeviceToken.fcm_token == "tokCCC").count() == 0


def test_blank_token_is_rejected(client):
    assert client.post("/api/devices", json={"fcm_token": "   "}).status_code == 422


def test_devices_require_auth(db):
    """بدونِ override‌کردنِ get_principal، احراز هویتِ واقعی اجرا می‌شود → ۴۰۱."""
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    try:
        c = TestClient(app)
        assert c.post("/api/devices", json={"fcm_token": "x"}).status_code == 401
    finally:
        app.dependency_overrides.clear()
