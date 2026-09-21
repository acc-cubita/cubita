"""حذفِ کاملِ اکانت — روی مستأجری که **داده دارد**.

جدولِ خالی این طبقه از شکست را ساختاراً پنهان می‌کند: بدونِ ردیف، هیچ قیدِ کلیدِ
خارجی‌ای ارزیابی نمی‌شود و حذف همیشه سبز است. پس هر تستِ حذف باید اول بکارد.

قاعده‌ی حذفِ کلیدهای خارجیِ `tenant_id` جای دیگری قفل شده
(`test_migration_drift.test_every_tenant_fk_cascades_in_the_migrated_schema`)،
چون آن انحراف فقط در اسکیمای **مهاجرت‌ساخته** دیده می‌شود و اسکیمای این تست‌ها
با `create_all` ساخته می‌شود. این پرونده چیزِ دیگری را می‌سنجد: قیدهای **میانِ
دو جدولِ مستأجرمحور**، که با آبشارِ مستأجر هم می‌توانند به ترتیبِ حذف گیر کنند.
"""
import pytest
from sqlalchemy import text

from app.models.staff_audit import StaffAuditLog


@pytest.fixture
def super_client(staff_client):
    return staff_client(role="owner")


def _create(super_client, email="purge@example.com"):
    return super_client.post(
        "/api/admin/accounts",
        json={
            "business_name": "کسب‌وکارِ پرداده",
            "owner_name": "نگار احمدی",
            "email": email,
            "password": "verylongpassword",
            "days": 365,
        },
    ).json()


def _delete(super_client, row, reason="پایانِ همکاری با مشتری"):
    return super_client.request(
        "DELETE",
        f"/api/admin/accounts/{row['tenant_id']}",
        json={"confirm_slug": row["slug"], "reason": reason},
    )


def test_a_fresh_account_already_has_seeded_rows(super_client, db):
    """پیش‌شرطِ بقیه‌ی این پرونده.

    اگر روزی `provision_tenant` دیگر چیزی نکارد، تست‌های پایین بی‌صدا بی‌معنا
    می‌شوند — سبز می‌مانند ولی هیچ قیدی را ارزیابی نمی‌کنند.
    """
    row = _create(super_client, email="seeded@example.com")
    counts = {
        table: db.execute(
            text(f"SELECT count(*) FROM {table} WHERE tenant_id = :t"), {"t": row["tenant_id"]}
        ).scalar()
        for table in ("units_of_measure", "accounts", "warehouses")
    }
    assert all(c > 0 for c in counts.values()), counts


def test_purging_an_account_with_items_and_units(super_client, db):
    """`items.primary_unit_id → units_of_measure.id` هیچ `ondelete`ی ندارد.

    با آبشارِ مستأجر هر دو جدول پاک می‌شوند، ولی قیدِ میانشان `NO ACTION` است —
    یعنی اگر واحدها پیش از کالاها حذف شوند، کلِ حذف رد می‌شود.
    """
    from app.models.inventory import Item, UnitOfMeasure
    from app.tenant_context import tenant_scope

    row = _create(super_client, email="items@example.com")
    tenant_id = row["tenant_id"]

    with tenant_scope(db, tenant_id):
        unit = db.query(UnitOfMeasure).filter(UnitOfMeasure.tenant_id == tenant_id).first()
        assert unit is not None, "کسب‌وکارِ تازه باید واحدِ اندازه‌گیری داشته باشد"
        db.add(
            Item(
                tenant_id=tenant_id,
                sku="P-1",
                name="کالای آزمایشی",
                primary_unit_id=unit.id,
                secondary_unit_id=unit.id,
            )
        )
        db.flush()

    assert _delete(super_client, row).status_code == 200

    assert db.execute(
        text("SELECT count(*) FROM tenants WHERE id = :t"), {"t": tenant_id}
    ).scalar() == 0
    assert db.execute(
        text("SELECT count(*) FROM units_of_measure WHERE tenant_id = :t"), {"t": tenant_id}
    ).scalar() == 0


def test_purging_does_not_delete_staff_users(super_client, db, staff_user):
    """کارمندِ ستاد عضویتی ندارد — ولی یتیم نیست.

    `purge_tenant` کاربرانِ بی‌عضویت را پاک می‌کند. هویتِ ستاد عمداً بی‌عضویت
    است، پس بدونِ استثنا اولین حذفِ اکانت روی
    `platform_admins_user_id_fkey` می‌شکست و **هیچ اکانتی قابلِ حذف نبود**.
    """
    admin = staff_user(email="survivor@staff.cubita.ir", role="admin")
    row = _create(super_client, email="alongside@example.com")

    assert _delete(super_client, row).status_code == 200

    assert db.execute(
        text("SELECT count(*) FROM users WHERE id = :u"), {"u": admin.user_id}
    ).scalar() == 1


def test_the_owner_of_the_deleted_tenant_is_cleaned_up(super_client, db):
    """قرینه‌ی تستِ بالا: کاربرِ واقعاً یتیم باید برود (offboardingِ کامل)."""
    row = _create(super_client, email="leaving@example.com")
    assert _delete(super_client, row).status_code == 200
    assert db.execute(
        text("SELECT count(*) FROM users WHERE email = :e"), {"e": "leaving@example.com"}
    ).scalar() == 0


def test_the_audit_record_survives(super_client, db):
    row = _create(super_client, email="traced@example.com")
    _delete(super_client, row, reason="بستنِ پرونده به درخواستِ مشتری")
    (record,) = db.query(StaffAuditLog).filter(StaffAuditLog.action == "account_delete").all()
    assert "بستنِ پرونده" in record.summary
