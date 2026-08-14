"""دفتر ردِ حسابرسی.

مهم‌ترین تست‌های این پرونده آن‌هایی هستند که *فقط‌افزودنی بودن* را می‌سنجند. یک
دفتر حسابرسی که بشود ویرایشش کرد بدتر از نداشتنش است: اطمینان کاذب می‌دهد. اگر کسی
بتواند ردِ ابطال خودش را پاک کند، تمام این جدول تزئین است.

تست‌های اینجا عمداً از مسیر واقعی سرویس عبور می‌کنند و نه از ساختن دستی AuditLog —
چیزی که باید اثبات شود این است که ثبت *خودکار* اتفاق می‌افتد، نه اینکه مدل کار
می‌کند.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.audit import PURGE_SETTING, _jsonable, audited_models, bind_session_actor
from app.models.audit import AuditLog
from app.models.base import VoidableMixin


# --- فقط‌افزودنی بودن ------------------------------------------------------------


def _some_entry(db, user, tenant_id) -> AuditLog:
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_id=user.id,
        actor_email=user.email,
        action="create",
        entity_type="Test",
        entity_id=user.id,
        summary="رکورد آزمایشی",
    )
    db.add(entry)
    db.flush()
    return entry


def test_an_audit_row_cannot_be_updated(db, user, tenant_id):
    """مهم‌ترین تست این پرونده.

    اگر رکورد حسابرسی قابل ویرایش باشد، کسی که ردش را عوض می‌کند دقیقاً همان کسی
    است که این جدول برای گرفتنش وجود دارد.
    """
    entry = _some_entry(db, user, tenant_id)

    with pytest.raises(DBAPIError) as err:
        db.execute(text("UPDATE audit_log SET summary = 'دستکاری شد' WHERE id = :i"), {"i": entry.id})
    assert "فقط‌افزودنی" in str(err.value)


def test_an_audit_row_cannot_be_deleted(db, user, tenant_id):
    entry = _some_entry(db, user, tenant_id)

    with pytest.raises(DBAPIError) as err:
        db.execute(text("DELETE FROM audit_log WHERE id = :i"), {"i": entry.id})
    assert "فقط‌افزودنی" in str(err.value)


def test_deletion_is_possible_only_through_the_explicit_purge_switch(db, user, tenant_id):
    """حذف مستأجر باید ممکن بماند، ولی فقط با یک اقدام صریح.

    بدون این دریچه، حذف مشتری (offboarding) اصلاً کار نمی‌کرد. با دریچه‌ی همیشه‌باز،
    همان مسیر برای پاک کردن ردِ یک ابطال هم کار می‌کرد.
    """
    entry = _some_entry(db, user, tenant_id)

    db.execute(text(f"SELECT set_config('{PURGE_SETTING}', 'on', true)"))
    db.execute(text("DELETE FROM audit_log WHERE id = :i"), {"i": entry.id})
    db.execute(text(f"SELECT set_config('{PURGE_SETTING}', 'off', true)"))

    assert db.query(AuditLog).filter(AuditLog.id == entry.id).one_or_none() is None


def test_the_purge_switch_does_not_open_updates(db, user, tenant_id):
    """دریچه فقط برای حذف است. هیچ دلیل مشروعی برای *عوض کردن* رکورد وجود ندارد."""
    entry = _some_entry(db, user, tenant_id)
    db.execute(text(f"SELECT set_config('{PURGE_SETTING}', 'on', true)"))

    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE audit_log SET summary = 'x' WHERE id = :i"), {"i": entry.id})


# --- ثبت خودکار از مسیر واقعی سرویس ------------------------------------------------


def _post_invoice(db, user, tenant_id):
    from app.models.inventory import Contact, Item, Warehouse
    from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
    from app.services.inventory import post_purchase_invoice

    warehouse = db.query(Warehouse).first()
    item = db.query(Item).first()
    if item is None:
        item = Item(sku="AUD-1", name="کالای حسابرسی", unit="عدد", sales_price=1000)
        db.add(item)
        db.flush()
    contact = db.query(Contact).filter(Contact.type == "supplier").first()
    if contact is None:
        contact = Contact(name="تأمین‌کننده حسابرسی", type="supplier")
        db.add(contact)
        db.flush()

    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(),
            warehouse_id=warehouse.id,
            contact_id=contact.id,
            description="خرید برای تست حسابرسی",
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=3, unit_cost=1000, description="")],
        ),
        user,
    )


def test_posting_an_invoice_writes_an_audit_row(db, user, tenant_id):
    """ثبت باید *خودکار* باشد؛ هیچ سرویسی نباید لازم باشد چیزی صدا بزند."""
    bind_session_actor(db, user)
    invoice = _post_invoice(db, user, tenant_id)
    db.flush()

    rows = db.query(AuditLog).filter(AuditLog.entity_id == invoice.id).all()
    assert len(rows) == 1, "ثبت فاکتور رکورد حسابرسی نساخت"
    assert rows[0].action == "create"
    assert rows[0].entity_type == "PurchaseInvoice"
    assert "فاکتور خرید" in rows[0].summary


def test_the_actor_is_recorded(db, user, tenant_id):
    """دفتری که بگوید چیزی عوض شد ولی نگوید توسط چه کسی، نیمی از فایده‌اش را ندارد."""
    bind_session_actor(db, user)
    invoice = _post_invoice(db, user, tenant_id)
    db.flush()

    row = db.query(AuditLog).filter(AuditLog.entity_id == invoice.id).one()
    assert row.actor_id == user.id
    assert row.actor_email == user.email


def test_the_actor_email_is_a_snapshot_not_a_join(db, user, tenant_id):
    """رد حسابرسی نباید با تغییر داده‌ی زنده بازنویسی شود.

    اگر ایمیل از users خوانده می‌شد، عوض کردن ایمیل، گذشته را هم عوض می‌کرد — یعنی
    دقیقاً همان چیزی که رد حسابرسی برای جلوگیری از آن هست.
    """
    bind_session_actor(db, user)
    invoice = _post_invoice(db, user, tenant_id)
    db.flush()
    original = user.email

    user.email = "avazshod@example.invalid"
    db.flush()

    row = db.query(AuditLog).filter(AuditLog.entity_id == invoice.id).one()
    assert row.actor_email == original, "ایمیل رکورد حسابرسی با تغییر کاربر عوض شد"


def test_a_system_action_is_recorded_as_system(db, user, tenant_id):
    """اسکریپت و seed کاربر ندارند؛ خالی گذاشتن بهتر از نسبت دادن به یک نفر است."""
    db.info.pop("cubita_audit_actor", None)
    invoice = _post_invoice(db, user, tenant_id)
    db.flush()

    row = db.query(AuditLog).filter(AuditLog.entity_id == invoice.id).one()
    assert row.actor_id is None
    assert row.actor_email == "سیستم"


# --- ابطال، مهم‌ترین رویداد ----------------------------------------------------------


def test_voiding_is_recorded_as_its_own_action(db, user, tenant_id):
    """ابطال نباید لای UPDATEهای معمولی گم شود — جایی است که تقلب پنهان می‌شود."""
    from app.services.voiding import void_purchase_invoice

    bind_session_actor(db, user)
    invoice = _post_invoice(db, user, tenant_id)
    db.flush()

    void_purchase_invoice(db, invoice.id, reason="ثبت اشتباه", user=user)
    db.flush()

    actions = [r.action for r in db.query(AuditLog).filter(AuditLog.entity_id == invoice.id).all()]
    assert "void" in actions, f"ابطال به‌عنوان رویداد مستقل ثبت نشد؛ ثبت‌شده: {actions}"


def test_the_void_row_carries_the_before_and_after(db, user, tenant_id):
    from app.services.voiding import void_purchase_invoice

    bind_session_actor(db, user)
    invoice = _post_invoice(db, user, tenant_id)
    db.flush()
    void_purchase_invoice(db, invoice.id, reason="ثبت اشتباه", user=user)
    db.flush()

    row = (
        db.query(AuditLog)
        .filter(AuditLog.entity_id == invoice.id, AuditLog.action == "void")
        .one()
    )
    assert row.changes["voided_at"]["from"] is None
    assert row.changes["voided_at"]["to"] is not None
    assert row.changes["void_reason"]["to"] == "ثبت اشتباه"


# --- دامنه و ساختار ----------------------------------------------------------------


def test_every_voidable_document_is_audited():
    """تله‌ی خودکار برای مدل‌های آینده.

    هر مدلی که بشود باطلش کرد یک سند مالی است، و هر سند مالی باید رد حسابرسی
    داشته باشد. بدون این تست، کسی که سند نوع جدیدی اضافه کند بی‌صدا از دفتر
    حسابرسی جا می‌ماند و هیچ بازبینی‌کننده‌ای لازم نیست آن را به یاد بیاورد.
    """
    from app.database import Base

    registry = audited_models()
    voidable = [
        m.class_
        for m in Base.registry.mappers
        if issubclass(m.class_, VoidableMixin)
    ]
    missing = [m.__name__ for m in voidable if m not in registry]
    assert not missing, f"این اسناد قابل ابطال‌اند ولی حسابرسی نمی‌شوند: {missing}"


def test_invoice_lines_do_not_each_get_their_own_row(db, user, tenant_id):
    """ثبت یک فاکتور ده‌ردیفه نباید یازده رکورد بسازد؛ ردیف جزئی از سند است."""
    bind_session_actor(db, user)
    before = db.query(AuditLog).count()
    _post_invoice(db, user, tenant_id)
    db.flush()
    after = db.query(AuditLog).count()

    # فاکتور خرید + سند حسابداری‌اش. نه ردیف‌ها، نه حرکت‌های انبار.
    assert after - before == 2, f"انتظار ۲ رکورد بود، {after - before} تا ثبت شد"


def test_the_audit_table_is_tenant_scoped():
    from app.tenancy import is_tenant_table

    assert is_tenant_table("audit_log"), "دفتر حسابرسی باید زیر RLS باشد"


def test_amounts_survive_as_text_not_float():
    """مبلغی که از float عبور کند دقتش را از دست می‌دهد.

    رد حسابرسی‌ای که عدد را کمی جابه‌جا کند از نبودنش بدتر است، چون قابل استناد
    به‌نظر می‌رسد.
    """
    assert _jsonable(Decimal("12345678901234.99")) == "12345678901234.99"
    assert isinstance(_jsonable(Decimal("1.10")), str)


def test_the_request_id_links_the_audit_row_to_the_logs(db, user, tenant_id):
    """بدون این پل، «چه کسی این را عوض کرد» و «آن درخواست چه کرد» دو دنیای جدا می‌مانند."""
    from app.observability import request_id_var

    token = request_id_var.set("audit-trace-1")
    try:
        bind_session_actor(db, user)
        invoice = _post_invoice(db, user, tenant_id)
        db.flush()
    finally:
        request_id_var.reset(token)

    row = db.query(AuditLog).filter(AuditLog.entity_id == invoice.id).one()
    assert row.request_id == "audit-trace-1"


# --- اندپوینت خواندن ----------------------------------------------------------------


def test_the_audit_endpoint_returns_recorded_events(client, db, user, tenant_id):
    bind_session_actor(db, user)
    invoice = _post_invoice(db, user, tenant_id)
    db.flush()

    res = client.get("/api/audit", params={"entity_id": str(invoice.id)})

    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["entity_type"] == "PurchaseInvoice"
    assert items[0]["actor_email"] == user.email


def test_the_audit_log_can_be_filtered_to_voids(client, db, user, tenant_id):
    """پرکاربردترین کوئری یک حسابرس: «چه چیزهایی باطل شده‌اند؟»"""
    from app.services.voiding import void_purchase_invoice

    bind_session_actor(db, user)
    invoice = _post_invoice(db, user, tenant_id)
    db.flush()
    void_purchase_invoice(db, invoice.id, reason="ثبت اشتباه", user=user)
    db.flush()

    res = client.get("/api/audit", params={"action": "void"})

    assert res.status_code == 200
    actions = {i["action"] for i in res.json()["items"]}
    assert actions == {"void"}, f"فیلتر ابطال چیزهای دیگری هم برگرداند: {actions}"


def test_there_is_no_way_to_write_an_audit_entry_through_the_api(client):
    """دفتری که بشود در آن رکورد *ساخت* به‌اندازه‌ی دفتر قابل‌ویرایش بی‌ارزش است.

    اگر روزی کسی برای «راحتی» یک POST اضافه کند، این تست جلویش را می‌گیرد.
    """
    from app.main import app

    audit_routes = [r for r in app.routes if getattr(r, "path", "").startswith("/api/audit")]
    assert audit_routes, "مسیر حسابرسی اصلاً ثبت نشده"

    for route in audit_routes:
        assert set(route.methods) <= {"GET", "HEAD", "OPTIONS"}, (
            f"مسیر حسابرسی {route.path} متد نوشتن دارد: {route.methods}"
        )


# --- offboarding کامل ---------------------------------------------------------------


def test_purging_a_tenant_removes_its_orphaned_users(tenant_id):
    """حذف کسب‌وکار نباید هویت بی‌صاحب جا بگذارد.

    users جدول سراسری است، پس حذف آبشاری مستأجر به آن نمی‌رسد. اولین بار روی
    production واقعی دیده شد: مستأجر آزمون رفت و ایمیلش ماند.
    """
    from app.database import SessionLocal
    from app.models.user import User
    from app.seed import provision_tenant
    from app.services.provisioning import purge_tenant
    from app.tenant_context import set_current_tenant

    email = "offboard-me@example.invalid"
    s = SessionLocal()
    try:
        t = provision_tenant(
            s, name="کسب‌وکار رفتنی", slug="offboard-test",
            owner_email=email, owner_password="OffboardPass!2026",
        )
        s.commit()
        new_tenant_id = t.id
        assert s.query(User).filter(User.email == email).one_or_none() is not None
    finally:
        s.close()
        set_current_tenant(None)

    s = SessionLocal()
    try:
        purge_tenant(s, new_tenant_id)
        s.commit()
        assert s.query(User).filter(User.email == email).one_or_none() is None, (
            "کاربر بی‌عضویت بعد از حذف کسب‌وکار باقی ماند"
        )
    finally:
        s.close()
        set_current_tenant(None)


def test_purging_does_not_touch_a_user_who_serves_another_business(tenant_id):
    """حسابدار مستقل که دفتر چند کسب‌وکار را می‌برد نباید با رفتن یکی پاک شود."""
    from app.database import SessionLocal
    from app.models.tenant import Membership
    from app.models.user import Role, User
    from app.seed import provision_tenant
    from app.services.provisioning import purge_tenant
    from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant, set_current_tenant

    email = "hesabdar-e-mostaqel@example.invalid"
    s = SessionLocal()
    try:
        t = provision_tenant(
            s, name="کسب‌وکار دوم", slug="second-business",
            owner_email=email, owner_password="SharedPass!2026",
        )
        s.commit()
        second_id = t.id
        # شناسه به‌عنوان مقدار ساده نگه داشته می‌شود، نه شیء ORM: بعد از بسته شدن
        # نشست، شیء detach است و هر دسترسی به خصوصیتش خطا می‌دهد.
        shared_user_id = s.query(User).filter(User.email == email).one().id

        # همان شخص عضو مستأجر اصلی هم می‌شود
        bind_session_tenant(s, tenant_id)
        apply_tenant_to_transaction(s, tenant_id)
        role = s.query(Role).filter(Role.tenant_id == tenant_id, Role.key == "accountant").one()
        s.add(Membership(user_id=shared_user_id, tenant_id=tenant_id, role_id=role.id, status="active"))
        s.commit()
    finally:
        s.close()
        set_current_tenant(None)

    s = SessionLocal()
    try:
        purge_tenant(s, second_id)
        s.commit()
        assert s.query(User).filter(User.email == email).one_or_none() is not None, (
            "کاربری که هنوز در کسب‌وکار دیگری عضو است پاک شد"
        )
        # پاک‌سازی خودِ تست
        s.execute(text("DELETE FROM memberships WHERE user_id = :u"), {"u": shared_user_id})
        s.execute(text("DELETE FROM users WHERE id = :u"), {"u": shared_user_id})
        s.commit()
    finally:
        s.close()
        set_current_tenant(None)
