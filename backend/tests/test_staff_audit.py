"""دفترِ ردِ کارهای ستاد.

تا پیش از این کوچ، حذفِ برگشت‌ناپذیرِ یک مشتری، تعلیقِ اکانت و بازنشانیِ رمزِ
مالک **صفر رد** می‌گذاشتند: `audit_log` مستأجرمحور است و هیچ مدلِ پلتفرمی‌ای در
`audited_models()` نیست. این پرونده همان شکاف را قفل می‌کند.
"""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app.models.staff_audit import StaffAuditLog

OWNER = "test-owner@example.invalid"


@pytest.fixture
def super_client(staff_client):
    return staff_client(role="owner")


def _create(super_client, email="audited@example.com"):
    return super_client.post(
        "/api/admin/accounts",
        json={
            "business_name": "مشتریِ ردگیری‌شده",
            "owner_name": "زهرا محمدی",
            "email": email,
            "password": "verylongpassword",
            "days": 365,
        },
    ).json()


def _rows(db, action: str):
    return db.query(StaffAuditLog).filter(StaffAuditLog.action == action).all()


# ── هر کنش یک رد ────────────────────────────────────────────────────────────


def test_creating_an_account_is_recorded(super_client, db):
    row = _create(super_client)
    records = _rows(db, "account_create")
    assert len(records) == 1
    record = records[0]
    assert record.tenant_id == row["tenant_id"] or str(record.tenant_id) == row["tenant_id"]
    assert record.target_label == "مشتریِ ردگیری‌شده"
    assert record.actor_role == "owner"
    assert record.via == "staff"


def test_suspending_is_recorded_with_the_business_name(super_client, db):
    row = _create(super_client, email="susp@example.com")
    super_client.post(
        f"/api/admin/accounts/{row['tenant_id']}/status", json={"status": "suspended"}
    )
    (record,) = _rows(db, "account_status")
    assert "تعلیق" in record.summary
    assert record.target_label == "مشتریِ ردگیری‌شده"


def test_the_password_value_is_never_recorded(super_client, db):
    """قاعده‌ی `SECRET_FIELDS`: واقعه و هدف ثبت می‌شوند، مقدار هرگز."""
    secret = "SuperSecretPassword!2026"
    row = _create(super_client, email="pw-audit@example.com")
    super_client.post(
        f"/api/admin/accounts/{row['tenant_id']}/reset-password", json={"password": secret}
    )
    (record,) = _rows(db, "account_reset_password")
    blob = f"{record.summary}{record.details}"
    assert secret not in blob


def test_extending_records_the_amount(super_client, db):
    row = _create(super_client, email="ext-audit@example.com")
    super_client.post(f"/api/admin/accounts/{row['tenant_id']}/extend", json={"days": 90})
    (record,) = _rows(db, "account_extend")
    assert record.details["days"] == 90


# ── ناوردای اصلی: رد از حذفِ مشتری جان سالم به در می‌برد ──────────────────────


def test_the_delete_record_outlives_the_tenant(super_client, db):
    """**مهم‌ترین تستِ این پرونده.**

    اگر `staff_audit_log.tenant_id` کلیدِ خارجی داشت، حذفِ مستأجر ردِ حذف را هم
    با خودش می‌برد — یعنی تنها سندی که می‌گوید چه کسی و چرا این مشتری را پاک
    کرد، دقیقاً در لحظه‌ی پاک‌شدن نابود می‌شد.
    """
    row = _create(super_client, email="gone@example.com")
    tenant_id = row["tenant_id"]

    r = super_client.request(
        "DELETE",
        f"/api/admin/accounts/{tenant_id}",
        json={"confirm_slug": row["slug"], "reason": "درخواستِ خودِ مشتری برای حذفِ کامل"},
    )
    assert r.status_code == 200, r.text

    #: مستأجر واقعاً رفته…
    assert db.execute(
        text("SELECT count(*) FROM tenants WHERE id = :t"), {"t": tenant_id}
    ).scalar() == 0

    #: …ولی رد مانده، با نام و دلیلش.
    (record,) = _rows(db, "account_delete")
    assert str(record.tenant_id) == tenant_id
    assert record.target_label == "مشتریِ ردگیری‌شده"
    assert "درخواستِ خودِ مشتری" in record.summary


# ── فقط‌افزودنی در سطحِ پایگاه‌داده ──────────────────────────────────────────


def test_records_cannot_be_edited(super_client, db):
    _create(super_client, email="immutable@example.com")
    (record,) = _rows(db, "account_create")
    savepoint = db.begin_nested()
    with pytest.raises(DatabaseError):
        db.execute(
            text("UPDATE staff_audit_log SET summary = 'دست‌کاری' WHERE id = :i"),
            {"i": record.id},
        )
    savepoint.rollback()


def test_records_cannot_be_deleted(super_client, db):
    """حتی حذف — دریچه‌ی `app.audit_purge` فقط در `purge_tenant` باز می‌شود و
    آن تابع هرگز این جدول را لمس نمی‌کند."""
    _create(super_client, email="undeletable@example.com")
    (record,) = _rows(db, "account_create")
    savepoint = db.begin_nested()
    with pytest.raises(DatabaseError):
        db.execute(text("DELETE FROM staff_audit_log WHERE id = :i"), {"i": record.id})
    savepoint.rollback()


# ── ردیفی که مستأجر ندارد، مهرِ مستأجر نمی‌خورد ─────────────────────────────


def test_a_login_record_has_no_tenant(db, staff_user):
    """`_stamp_tenant_on_new_rows` نباید ردِ ورود را به یک مشتریِ بی‌ربط بچسباند.

    مهرِ خودکار روی هر مدلی که ستونِ `tenant_id` دارد می‌نشیند؛ `StaffAuditLog`
    با `__tenant_stamp__ = False` از آن بیرون است. بدونِ آن، ردِ ورودِ کارمندِ
    ستاد در گزارشِ یک مشتریِ تصادفی ظاهر می‌شد.
    """
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    staff_user(email="stamp@staff.cubita.ir")
    app.dependency_overrides[get_db] = lambda: db
    try:
        r = TestClient(app).post(
            "/api/admin/auth/login",
            json={"email": "stamp@staff.cubita.ir", "password": "StaffPassword!2026"},
        )
        assert r.status_code == 200, r.text
    finally:
        app.dependency_overrides.clear()

    (record,) = _rows(db, "login")
    assert record.tenant_id is None
