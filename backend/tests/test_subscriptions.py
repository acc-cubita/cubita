"""چرخه‌ی عمر اشتراک.

تا پیش از این، پلن‌ها `billing_period: "yearly"` داشتند و میلیون‌ها تومان **در
سال** فروخته می‌شدند، ولی هیچ فیلد انقضایی در هیچ مدلی نبود — یعنی مشتری یک بار
پرداخت می‌کرد و سال دوم رایگان بود.

مهم‌ترین تست این پرونده `test_an_expired_tenant_can_still_read_its_books` است.
دفاتر مالی سند قانونی خودِ مشتری‌اند؛ قفل کردنشان پشت پرداخت یعنی گروگان گرفتن
چیزی که مال ما نیست.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.models.subscription import Subscription
from app.services.subscriptions import GRACE_DAYS, days_for_period, grant, state_for


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _set_expiry(db, tenant_id, *, days_from_now: int, cancelled: bool = False) -> Subscription:
    db.query(Subscription).filter(Subscription.tenant_id == tenant_id).delete()
    sub = Subscription(
        tenant_id=tenant_id,
        starts_at=_now() - timedelta(days=365),
        expires_at=_now() + timedelta(days=days_from_now),
        cancelled_at=_now() if cancelled else None,
        note="تست",
    )
    db.add(sub)
    db.flush()
    return sub


# --- محاسبه‌ی وضعیت ---------------------------------------------------------------


def test_a_future_expiry_is_active(db, tenant_id):
    _set_expiry(db, tenant_id, days_from_now=30)
    assert state_for(db, tenant_id).status == "active"


def test_just_past_expiry_is_grace_not_expired(db, tenant_id):
    """قطع ناگهانی در روز انقضا یک کسب‌وکار را وسط ماه زمین می‌زند."""
    _set_expiry(db, tenant_id, days_from_now=-1)
    state = state_for(db, tenant_id)
    assert state.status == "grace"
    assert state.can_write, "در مهلت ارفاق هنوز باید بشود سند ثبت کرد"


def test_past_the_grace_period_is_expired(db, tenant_id):
    _set_expiry(db, tenant_id, days_from_now=-(GRACE_DAYS + 1))
    state = state_for(db, tenant_id)
    assert state.status == "expired"
    assert not state.can_write


def test_the_grace_boundary_is_inclusive(db, tenant_id):
    """مرز دقیقاً روی GRACE_DAYS هنوز ارفاق است، نه انقضا."""
    _set_expiry(db, tenant_id, days_from_now=-(GRACE_DAYS - 1))
    assert state_for(db, tenant_id).status == "grace"


def test_no_subscription_row_means_open_not_locked(db, tenant_id):
    """برخلاف امنیت، اینجا fail-open درست است.

    اشتباهِ بستن یعنی مشتری پولی از دفتر خودش بیرون می‌ماند؛ اشتباهِ باز گذاشتن
    یعنی یک ماه رایگان. این دو هزینه هم‌اندازه نیستند.
    """
    db.query(Subscription).filter(Subscription.tenant_id == tenant_id).delete()
    db.flush()
    state = state_for(db, tenant_id)
    assert state.status == "none"
    assert state.can_write


def test_a_cancelled_subscription_still_runs_until_its_end(db, tenant_id):
    """لغو یعنی «تمدید نکن»، نه «همین حالا قطع کن». مشتری بابت این دوره پول داده."""
    _set_expiry(db, tenant_id, days_from_now=10, cancelled=True)
    state = state_for(db, tenant_id)
    assert state.status == "active"
    assert state.can_write


# --- تمدید ------------------------------------------------------------------------


def test_renewing_early_adds_to_the_end_not_from_today(db, tenant_id):
    """اگر از امروز حساب می‌شد، تمدید زودهنگام جریمه داشت.

    مشتری‌ای که یک ماه زودتر تمدید می‌کند نباید آن یک ماه را از دست بدهد.
    """
    _set_expiry(db, tenant_id, days_from_now=30)
    before = state_for(db, tenant_id).expires_at

    grant(db, tenant_id, days=365, note="تمدید")

    after = state_for(db, tenant_id).expires_at
    added = (after - before).days
    assert added == 365, f"تمدید باید ۳۶۵ روز به انتهای دوره اضافه کند، نه {added}"


def test_renewing_after_expiry_starts_from_today(db, tenant_id):
    """دوره‌ی گذشته نباید از اشتراک تازه کم شود."""
    _set_expiry(db, tenant_id, days_from_now=-100)

    grant(db, tenant_id, days=365, note="تمدید بعد از انقضا")

    days_left = state_for(db, tenant_id).days_left
    assert 363 <= days_left <= 365, f"انتظار ~۳۶۵ روز بود، {days_left} شد"


def test_yearly_and_monthly_periods(db):
    assert days_for_period("yearly") == 365
    assert days_for_period("semiannual") == 180
    assert days_for_period("monthly") == 30
    assert days_for_period("چیز ناشناخته") == 365, "پیش‌فرض ناشناخته باید سالانه باشد"


# --- اعمال روی اندپوینت واقعی ------------------------------------------------------


def _make_invoice_body(db):
    from app.models.inventory import Contact, Item, Warehouse

    wh = db.query(Warehouse).first()
    item = db.query(Item).first()
    if item is None:
        item = Item(sku="SUB-1", name="کالای اشتراک", unit="عدد", sales_price=1000)
        db.add(item)
    contact = db.query(Contact).filter(Contact.type == "supplier").first()
    if contact is None:
        contact = Contact(name="تأمین‌کننده اشتراک", type="supplier")
        db.add(contact)
    db.flush()
    return {
        "invoice_date": "2026-07-20",
        "warehouse_id": str(wh.id),
        "contact_id": str(contact.id),
        "description": "آزمون اشتراک",
        "lines": [{"item_id": str(item.id), "qty": 1, "unit_cost": 1000, "description": ""}],
    }


def test_an_expired_tenant_cannot_post_new_documents(client, db, tenant_id):
    body = _make_invoice_body(db)
    _set_expiry(db, tenant_id, days_from_now=-(GRACE_DAYS + 1))

    res = client.post("/api/purchase-invoices", json=body)

    assert res.status_code == 402, f"انتظار ۴۰۲ بود، {res.status_code} آمد"
    assert "تمدید" in res.json()["detail"]


def test_an_expired_tenant_can_still_read_its_books(client, db, tenant_id):
    """مهم‌ترین تست این پرونده.

    دفتر مالی سند قانونی خودِ مشتری است. مشتری‌ای که نتواند اظهارنامه‌ی
    مالیاتی‌اش را دربیاورد هرگز برنمی‌گردد — و قفل کردن دفترش پشت پرداخت،
    گروگان گرفتن چیزی است که مال ما نیست.
    """
    _set_expiry(db, tenant_id, days_from_now=-(GRACE_DAYS + 1))

    for path in ("/api/accounts", "/api/purchase-invoices", "/api/reports/trial-balance"):
        res = client.get(path)
        assert res.status_code == 200, f"{path} برای مستأجر منقضی بسته شد ({res.status_code})"


def test_a_tenant_in_grace_can_still_post(client, db, tenant_id):
    body = _make_invoice_body(db)
    _set_expiry(db, tenant_id, days_from_now=-1)

    res = client.post("/api/purchase-invoices", json=body)

    assert res.status_code == 201, f"در مهلت ارفاق ثبت باید کار کند، ولی {res.status_code} آمد"


def test_an_active_tenant_is_unaffected(client, db, tenant_id):
    body = _make_invoice_body(db)
    _set_expiry(db, tenant_id, days_from_now=200)

    res = client.post("/api/purchase-invoices", json=body)

    assert res.status_code == 201


# --- اتصال به پرداخت ---------------------------------------------------------------


def test_a_verified_purchase_extends_the_subscription(db, tenant_id):
    """بدون این، پرداخت فقط یک ردیف در purchases می‌ساخت و هیچ حقی نمی‌داد."""
    from app.models.billing import Plan, Purchase
    from app.services.provisioning import _extend_subscription

    plan = db.query(Plan).filter(Plan.billing_period == "yearly").first()
    assert plan is not None, "پلن سالانه‌ای در seed نیست"

    _set_expiry(db, tenant_id, days_from_now=5)
    before = state_for(db, tenant_id).expires_at

    purchase = Purchase(
        plan_id=plan.id, customer_name="مشتری", customer_email="x@example.invalid",
        amount_toman=plan.price_toman, status="paid",
    )
    db.add(purchase)
    db.flush()
    _extend_subscription(db, tenant_id, purchase, note="تست")
    db.flush()

    after = state_for(db, tenant_id).expires_at
    assert (after - before).days == 365


def test_the_subscription_table_is_global_not_tenant_scoped():
    """داده‌ی صفحه‌ی کنترل پلتفرم است، نه دفتر مشتری."""
    from app.tenancy import is_tenant_table

    assert not is_tenant_table("subscriptions")


def test_a_warning_appears_before_expiry_not_after(db, tenant_id):
    """هشدارِ بعد از قطع شدن بی‌فایده است؛ باید قبلش برسد."""
    _set_expiry(db, tenant_id, days_from_now=10)
    assert state_for(db, tenant_id).should_warn

    _set_expiry(db, tenant_id, days_from_now=200)
    assert not state_for(db, tenant_id).should_warn
