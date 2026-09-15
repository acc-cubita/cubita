"""حذفِ طرف حساب — و چیزهایی که نباید بگذارند حذف شود.

**چه کم بود.** `DELETE /api/contacts/{id}` اصلاً وجود نداشت و ۴۰۵ برمی‌گرداند.
یعنی طرف‌حسابی که اشتباه ثبت شده بود تا ابد در فهرست می‌ماند.

الگو همان حذفِ حساب است: قیدهای کلیدِ خارجی مرجعِ حقیقت‌اند و حذف داخلِ
SAVEPOINT انجام می‌شود، چون بیش از بیست جدول به `contacts.id` ارجاع می‌دهند و
شمردنشان در پایتون فهرستی می‌سازد که با اولین جدولِ تازه از واقعیت عقب می‌افتد.
"""
from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.company import ContactAddress, ContactChannel
from app.models.inventory import Contact
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 3, 15)


def _contact(db, **kw):
    row = Contact(name=f"طرف {uuid4().hex[:8]}", type="customer", **kw)
    db.add(row)
    db.flush()
    return row


# ─────────── مسیرِ موفق ───────────


def test_an_unused_contact_is_deleted(db, client):
    row = _contact(db)
    db.commit()

    res = client.delete(f"/api/contacts/{row.id}")
    assert res.status_code == 204, res.text
    assert db.get(Contact, row.id) is None


def test_its_addresses_and_channels_go_with_it(db, client):
    """نشانی و کانال **مالِ** طرف‌حساب‌اند، نه موجودیتِ مستقل."""
    row = _contact(db)
    db.add(ContactAddress(contact_id=row.id, title="انبار", address="جایی"))
    db.add(ContactChannel(contact_id=row.id, kind="phone", value="02100000000"))
    db.flush()
    db.commit()

    assert client.delete(f"/api/contacts/{row.id}").status_code == 204
    assert db.query(ContactAddress).filter_by(contact_id=row.id).count() == 0
    assert db.query(ContactChannel).filter_by(contact_id=row.id).count() == 0


def test_a_missing_contact_is_404(db, client):
    assert client.delete(f"/api/contacts/{uuid4()}").status_code == 404


# ─────────── گاردها ───────────


def test_a_system_contact_is_refused(db, client):
    """«فروشِ کارتیِ گذری» و همتاهایش را ثبتِ خودکار می‌سازد و لازمشان دارد."""
    row = _contact(db, is_system=True)
    db.commit()

    res = client.delete(f"/api/contacts/{row.id}")
    assert res.status_code == 409
    assert "سیستمی" in res.json()["detail"]
    assert db.get(Contact, row.id) is not None


def test_an_opening_balance_blocks_the_delete(db, client):
    """**این گارد کلیدِ خارجی ندارد**، پس قید نمی‌گیردش.

    مانده‌ی اول دوره عددی روی خودِ ردیف است؛ بدونِ گاردِ صریح، طرف‌حساب پاک
    می‌شد و ردیفِ سندِ افتتاحیه بی‌صاحب می‌ماند.
    """
    row = _contact(db, opening_ar_amount=Decimal(5_000_000))
    db.commit()

    res = client.delete(f"/api/contacts/{row.id}")
    assert res.status_code == 409
    assert "اول دوره" in res.json()["detail"]
    assert db.get(Contact, row.id) is not None


def test_a_contact_with_an_invoice_is_refused(db, client, user):
    """**گاردِ اصلی.** دفتر به نامِ این طرف‌حساب ارجاع می‌دهد."""
    row = _contact(db)
    wh = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(100_000))],
        ),
        user,
    )
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            contact_id=row.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(200_000))],
        ),
        user,
    )
    db.commit()

    res = client.delete(f"/api/contacts/{row.id}")
    assert res.status_code == 409
    assert "غیرفعال" in res.json()["detail"]
    assert db.get(Contact, row.id) is not None


def test_a_refused_delete_leaves_the_addresses_alone(db, client, user):
    """**ظریف‌ترین حالت، و دلیلِ اینکه حذفِ فرزندان داخلِ savepoint است.**

    فرزندان پیش از خودِ طرف‌حساب حذف می‌شوند. اگر بیرونِ savepoint بودند، یک
    حذفِ ردشده نشانی‌ها را می‌برد و طرف‌حساب را می‌گذاشت — خرابیِ بی‌صدایی که
    از خودِ خطا بدتر است، چون کاربر پیامِ «حذف نشد» می‌بیند و فکر می‌کند هیچ
    اتفاقی نیفتاده.
    """
    row = _contact(db)
    db.add(ContactAddress(contact_id=row.id, title="دفتر", address="جایی"))
    db.flush()

    wh = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(100_000))],
        ),
        user,
    )
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            contact_id=row.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(200_000))],
        ),
        user,
    )
    db.commit()

    assert client.delete(f"/api/contacts/{row.id}").status_code == 409
    assert db.query(ContactAddress).filter_by(contact_id=row.id).count() == 1, (
        "*** نشانیِ طرف‌حسابی که حذف نشد، پاک شد ***"
    )


def test_deactivating_is_still_available(db, client):
    """پیامِ خطا «غیرفعالش کنید» می‌گوید — پس آن مسیر باید واقعاً کار کند."""
    row = _contact(db)
    db.commit()

    res = client.patch(f"/api/contacts/{row.id}", json={"name": row.name, "is_active": False})
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False


# ─────────── غیرفعال‌کردن: مسیری که پیامِ خطا به آن ارجاع می‌دهد ───────────


def test_the_active_flag_was_dead_until_now(db, client):
    """**یافته‌ی حینِ کار.** `is_active` در `ContactIn` نبود.

    ستون در ساخت `True` می‌شد و هیچ مسیری عوضش نمی‌کرد — نه API نه رابط — در
    حالی که `ContactOut` نمایشش می‌داد. یعنی کاربر وضعیتی می‌دید که نمی‌توانست
    تغییرش دهد، و پیامِ «به‌جای حذف غیرفعالش کنید» به جای خالی اشاره می‌کرد.
    """
    from app.schemas.inventory import ContactIn

    assert "is_active" in ContactIn.model_fields, "*** دوباره مرده شد ***"


def test_a_contact_can_be_deactivated_and_reactivated(db, client):
    row = _contact(db)
    db.commit()

    off = client.patch(f"/api/contacts/{row.id}", json={"name": row.name, "is_active": False})
    assert off.status_code == 200, off.text
    assert off.json()["is_active"] is False

    on = client.patch(f"/api/contacts/{row.id}", json={"name": row.name, "is_active": True})
    assert on.json()["is_active"] is True


def test_a_partial_edit_does_not_silently_reactivate(db, client):
    """**تله‌ی `exclude_unset`.**

    فرمِ ساده‌ی ماژولِ فروش `is_active` نمی‌فرستد. اگر پیش‌فرضِ اسکیما اعمال
    می‌شد، هر ویرایشِ جزئی یک طرف‌حسابِ غیرفعال را بی‌صدا دوباره فعال می‌کرد.
    """
    row = _contact(db)
    db.commit()
    client.patch(f"/api/contacts/{row.id}", json={"name": row.name, "is_active": False})

    res = client.patch(f"/api/contacts/{row.id}", json={"phone": "02155555555"})
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False, "*** ویرایشِ جزئی دوباره فعالش کرد ***"


def test_the_list_can_filter_by_active(db, client):
    """و پیش‌فرض هر دو را می‌دهد — وگرنه فاکتورِ قدیمی طرف‌حسابش را گم می‌کرد."""
    keep = _contact(db)
    drop = _contact(db)
    db.commit()
    client.patch(f"/api/contacts/{drop.id}", json={"name": drop.name, "is_active": False})

    def ids(**q):
        res = client.get("/api/contacts", params={"limit": 200, **q})
        assert res.status_code == 200, res.text
        return {r["id"] for r in res.json()["items"]}

    both = ids()
    assert str(keep.id) in both and str(drop.id) in both, "پیش‌فرض باید هر دو را بدهد"
    assert str(drop.id) not in ids(active="true")
    assert str(keep.id) not in ids(active="false")
