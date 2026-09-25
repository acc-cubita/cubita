"""فرمِ «تماس برای خرید»ِ سایت و کارتابلِ فروشِ ستاد.

* ثبت بی‌احراز است ولی: دستِ‌کم تلفن یا ایمیل، شماره با ارقامِ فارسی یکسان‌سازی می‌شود، محصولِ ناشناخته
  رد می‌شود، و میدانِ تله درخواستِ ربات را بی‌صدا دور می‌اندازد.
* سقفِ نرخِ IP صفِ فروش را از پرشدنِ خودکار نگه می‌دارد.
* ستاد: فهرست با شمارِ «تازه»ها، تغییرِ وضعیت با ردِ ستاد، و مجوزِ حوزه‌ی `sales` برای هر نقش.
* نسخه‌ی سازمانی هیچ‌کدام از این مسیرها را ندارد (در `CLOUD_ONLY`).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import rate_limit
from app.database import get_db
from app.main import app
from app.models.sales_inquiry import SalesInquiry
from app.models.staff_audit import StaffAuditLog
from app.routing import CLOUD_ONLY
from app.routers import admin_sales, sales_inquiries

FORM = {
    "name": "مریم احمدی",
    "company": "بازرگانی پارس",
    "phone": "۰۹۱۲ ۱۲۳ ۴۵۶۷",
    "email": "",
    "product": "enterprise",
    "seats": 12,
    "message": "برای ۱۲ حسابدار و یک سرور",
}


@pytest.fixture
def public(db):
    rate_limit.reset_all()
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        rate_limit.reset_all()


def test_inquiry_is_stored_with_normalized_phone(public, db):
    r = public.post("/api/sales-inquiries", json=FORM)
    assert r.status_code == 201, r.text
    row = db.query(SalesInquiry).one()
    assert (row.name, row.company, row.phone, row.product, row.seats, row.status) == (
        "مریم احمدی",
        "بازرگانی پارس",
        "09121234567",
        "enterprise",
        12,
        "new",
    )


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"phone": "", "email": ""}, "شماره‌ی تماس یا ایمیل"),
        ({"phone": "12", "email": ""}, "شماره‌ی تماس درست نیست"),
        ({"email": "not-an-email"}, "ایمیل درست نیست"),
        ({"name": "   "}, "نامِ خود"),
    ],
)
def test_contact_details_are_validated(public, db, patch, message):
    r = public.post("/api/sales-inquiries", json={**FORM, **patch})
    assert r.status_code == 422
    assert message in r.text
    assert db.query(SalesInquiry).count() == 0


def test_unknown_product_is_rejected(public):
    assert public.post("/api/sales-inquiries", json={**FORM, "product": "gold-plan"}).status_code == 422


def test_honeypot_is_accepted_silently_but_not_stored(public, db):
    r = public.post("/api/sales-inquiries", json={**FORM, "website": "http://spam.example"})
    assert r.status_code == 201
    assert db.query(SalesInquiry).count() == 0


def test_rate_limit_caps_automated_filling(public):
    codes = [public.post("/api/sales-inquiries", json=FORM).status_code for _ in range(6)]
    assert codes[:5] == [201] * 5
    assert codes[5] == 429


def test_staff_sees_queue_and_updates_with_audit(public, staff_client, db):
    public.post("/api/sales-inquiries", json=FORM)
    public.post("/api/sales-inquiries", json={**FORM, "name": "علی", "product": "cloud", "phone": "", "email": "ali@example.com"})
    c = staff_client(role="support", email="sales@staff.cubita.ir")
    listing = c.get("/api/admin/sales-inquiries").json()
    assert listing["new_count"] == 2
    #: هر دو در یک تراکنشِ آزمون‌اند و `created_at`ِ یکسان دارند؛ ترتیبِ «تازه‌ترین اول» در درخواست‌های جدا معنا دارد.
    assert sorted(i["name"] for i in listing["items"]) == sorted(["علی", "مریم احمدی"])
    target = next(i["id"] for i in listing["items"] if i["name"] == "مریم احمدی")
    r = c.patch(f"/api/admin/sales-inquiries/{target}", json={"status": "contacted", "staff_note": "فردا دمو"})
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["handled_by"]) == ("contacted", "sales@staff.cubita.ir")
    assert c.get("/api/admin/sales-inquiries", params={"status": "new"}).json()["new_count"] == 1
    audit = db.query(StaffAuditLog).filter(StaffAuditLog.action == "sales_inquiry_update").one()
    assert audit.target_label == "بازرگانی پارس"
    #: بدونِ تغییر خطاست، نه ردِ خالی در کارنامه.
    assert c.patch(f"/api/admin/sales-inquiries/{target}", json={"status": "contacted"}).status_code == 422


def test_finance_can_only_view(public, staff_client):
    public.post("/api/sales-inquiries", json=FORM)
    c = staff_client(role="finance", email="fin@staff.cubita.ir")
    items = c.get("/api/admin/sales-inquiries").json()["items"]
    assert c.patch(f"/api/admin/sales-inquiries/{items[0]['id']}", json={"status": "won"}).status_code == 403


def test_tenant_token_cannot_read_the_queue(client):
    assert client.get("/api/admin/sales-inquiries").status_code in (401, 403)


def test_both_routes_are_cloud_only():
    assert any(r is sales_inquiries.router for r in CLOUD_ONLY)
    assert any(r is admin_sales.router for r in CLOUD_ONLY)
