"""تلفن/نشانیِ اضافه‌ی طرف حساب، و مانده‌ی اول دوره‌اش.

دو قیدِ اصلی که تست‌ها نگهشان می‌دارند:

۱. **کانالِ اصلی کپی نمی‌شود.** `contacts.phone` و `contacts.address` تنها جای
   کانالِ اصلی‌اند؛ `contact_channels` فقط کانال‌های *اضافه* را نگه می‌دارد.
۲. **مانده‌ی اول دوره فقط یک عدد نیست.** به سندِ افتتاحیه می‌رود، در کارتِ حسابِ
   شخص دیده می‌شود، و در تحلیلِ سنی می‌آید — وگرنه رقمی است که هیچ‌جا اثر ندارد.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models.accounting import JournalEntry
from app.models.inventory import Contact
from app.models.tenant import Tenant
from app.services import reports as reports_service
from app.services.onboarding import create_opening_entry
from app.schemas.onboarding import OpeningBalancesIn
from app.tenant_context import session_tenant


def _hybrid(db) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = "hybrid"
    db.flush()


def _payload(**extra) -> dict:
    return {"name": "آزمون", "type": "customer", **extra}


def _make(client, **extra) -> dict:
    res = client.post("/api/contacts", json=_payload(**extra))
    assert res.status_code == 201, res.text
    return res.json()


# ── کانال‌های اضافه ───────────────────────────────────────────────────────────


def test_extra_channels_are_stored_and_listed(db, user, client):
    _hybrid(db)
    contact = _make(client, phone="021-1111")

    for payload in (
        {"kind": "phone", "label": "انبار", "value": "021-2222"},
        {"kind": "address", "label": "دفتر مرکزی", "value": "تهران، خیابانِ آزادی"},
    ):
        res = client.post(f"/api/contacts/{contact['id']}/channels", json=payload)
        assert res.status_code == 201, res.text

    rows = client.get(f"/api/contacts/{contact['id']}/channels").json()
    assert {r["kind"] for r in rows} == {"phone", "address"}
    assert {r["label"] for r in rows} == {"انبار", "دفتر مرکزی"}


def test_the_primary_channel_stays_on_the_contact(db, user, client):
    """**قیدِ اصلی.** تلفنِ اصلی روی طرف‌حساب می‌ماند و در جدولِ کانال‌ها تکرار نمی‌شود.

    ده‌ها جا (فاکتور، صورت‌حساب، گزارشِ فصلی) مستقیم `contacts.phone` را می‌خوانند؛
    کپی‌کردنش این‌جا یعنی دو مقدار که دیر یا زود با هم نمی‌خوانند.
    """
    _hybrid(db)
    contact = _make(client, phone="021-1111", address="نشانیِ اصلی")

    rows = client.get(f"/api/contacts/{contact['id']}/channels").json()

    assert rows == [], "ساختِ طرف‌حساب نباید کانالی بسازد"
    assert contact["phone"] == "021-1111"
    assert contact["address"] == "نشانیِ اصلی"


def test_a_channel_can_be_removed(db, user, client):
    _hybrid(db)
    contact = _make(client)
    ch = client.post(
        f"/api/contacts/{contact['id']}/channels", json={"kind": "phone", "value": "021-3333"}
    ).json()

    res = client.delete(f"/api/contacts/{contact['id']}/channels/{ch['id']}")

    assert res.status_code == 204, res.text
    assert client.get(f"/api/contacts/{contact['id']}/channels").json() == []


def test_a_blank_value_is_refused(db, user, client):
    _hybrid(db)
    contact = _make(client)

    res = client.post(f"/api/contacts/{contact['id']}/channels", json={"kind": "phone", "value": "   "})

    assert res.status_code == 422, res.text


def test_an_unknown_kind_is_refused(db, user, client):
    _hybrid(db)
    contact = _make(client)

    res = client.post(f"/api/contacts/{contact['id']}/channels", json={"kind": "telepathy", "value": "x"})

    assert res.status_code == 422, res.text


def test_channels_die_with_their_contact(db, user, client):
    """کانال بدونِ طرف‌حساب معنایی ندارد — `CASCADE` روی کلیدِ خارجی."""
    _hybrid(db)
    contact = _make(client)
    client.post(f"/api/contacts/{contact['id']}/channels", json={"kind": "phone", "value": "021-4444"})

    db.delete(db.get(Contact, contact["id"]))
    db.flush()

    from app.models.company import ContactChannel

    assert db.query(ContactChannel).filter(ContactChannel.contact_id == contact["id"]).count() == 0


# ── مانده‌ی اول دوره ─────────────────────────────────────────────────────────


def test_opening_balance_round_trips(db, user, client):
    _hybrid(db)

    body = _make(client, opening_ar_amount=500000, opening_ar_side="debit")

    assert Decimal(body["opening_ar_amount"]) == 500000
    assert body["opening_ar_side"] == "debit"


def test_a_negative_opening_balance_is_refused(db, user, client):
    """مبلغ نامنفی است و سمت جداست — منفی یعنی کاربر سمت را اشتباه فهمیده."""
    _hybrid(db)

    res = client.post("/api/contacts", json=_payload(opening_ar_amount=-1))

    assert res.status_code == 422, res.text


def test_opening_balance_reaches_the_opening_entry(db, user, client):
    """**قیدِ اصلی.** عددِ روی طرف‌حساب باید به سند برسد، وگرنه فقط یک برچسب است."""
    _hybrid(db)
    _make(client, name="مشتریِ بدهکار", opening_ar_amount=700000, opening_ar_side="debit")

    entry = create_opening_entry(
        db,
        OpeningBalancesIn(
            entry_date=date(2026, 1, 1),
            lines=[],
            stock=[],
            balancing_account_id=_capital_account_id(db),
        ),
        user,
    )

    amounts = [Decimal(line.debit) for line in entry.lines if Decimal(line.debit) == 700000]
    assert amounts, "ردیفِ مانده‌ی اول دوره باید در سند باشد"
    assert sum(Decimal(l.debit) for l in entry.lines) == sum(Decimal(l.credit) for l in entry.lines)


def test_opening_balance_carries_the_contact_tafsili(db, user, client):
    """تفصیلیِ طرف‌حساب روی ردیف می‌نشیند تا مانده‌ی افتتاحیه هم تفکیک شود."""
    _hybrid(db)
    contact = _make(client, opening_ar_amount=300000, tafsili_code="8001")

    entry = create_opening_entry(
        db,
        OpeningBalancesIn(
            entry_date=date(2026, 1, 1), lines=[], stock=[],
            balancing_account_id=_capital_account_id(db),
        ),
        user,
    )

    line = next(l for l in entry.lines if Decimal(l.debit) == 300000)
    assert str(line.analytic_id) == contact["analytic_id"]


def test_opening_balance_is_locked_after_the_opening_entry(db, user, client):
    """**قیدِ مهم.** پس از ثبتِ افتتاحیه، عددِ روی طرف‌حساب و ردیفِ سند نباید جدا شوند."""
    _hybrid(db)
    contact = _make(client, opening_ar_amount=100000)
    create_opening_entry(
        db,
        OpeningBalancesIn(
            entry_date=date(2026, 1, 1), lines=[], stock=[],
            balancing_account_id=_capital_account_id(db),
        ),
        user,
    )

    res = client.patch(
        f"/api/contacts/{contact['id']}", json=_payload(opening_ar_amount=999999)
    )

    assert res.status_code == 409, res.text
    assert "افتتاحیه" in res.json()["detail"]


def test_editing_other_fields_after_opening_still_works(db, user, client):
    """قفل فقط روی مانده است — نام و تلفن باید همیشه قابلِ اصلاح باشند."""
    _hybrid(db)
    contact = _make(client, opening_ar_amount=100000)
    create_opening_entry(
        db,
        OpeningBalancesIn(
            entry_date=date(2026, 1, 1), lines=[], stock=[],
            balancing_account_id=_capital_account_id(db),
        ),
        user,
    )

    res = client.patch(
        f"/api/contacts/{contact['id']}",
        json=_payload(name="نامِ تازه", opening_ar_amount=100000),
    )

    assert res.status_code == 200, res.text
    assert res.json()["name"] == "نامِ تازه"


def test_opening_balance_shows_in_the_contact_statement(db, user, client):
    """**قیدِ اصلی.** گزارشی که این عدد برایش ثبت شده باید نشانش بدهد."""
    _hybrid(db)
    contact = _make(client, opening_ar_amount=250000, opening_ar_side="debit")
    create_opening_entry(
        db,
        OpeningBalancesIn(
            entry_date=date(2026, 1, 1), lines=[], stock=[],
            balancing_account_id=_capital_account_id(db),
        ),
        user,
    )

    statement = reports_service.get_contact_statement(db, contact["id"], None, None)

    opening = [ln for ln in statement["lines"] if ln["kind"] == "opening"]
    assert opening, "مانده‌ی اول دوره باید در کارتِ حساب بیاید"
    assert opening[0]["debit"] == Decimal(250000)


def test_opening_balance_shows_in_aging(db, user, client):
    """و در تحلیلِ سنی — قدیمی‌ترین و معمولاً پرخطرترین بخشِ مطالبات."""
    _hybrid(db)
    contact = _make(client, opening_ar_amount=400000, opening_ar_side="debit")
    create_opening_entry(
        db,
        OpeningBalancesIn(
            entry_date=date(2026, 1, 1), lines=[], stock=[],
            balancing_account_id=_capital_account_id(db),
        ),
        user,
    )

    report = reports_service.get_aging(db, "receivable", date(2026, 6, 1))

    row = next((r for r in report["rows"] if str(r["contact_id"]) == contact["id"]), None)
    assert row is not None, "طرف‌حسابِ دارای مانده‌ی افتتاحیه باید در گزارشِ سنی بیاید"
    assert row["total"] == Decimal(400000)


def test_a_credit_side_opening_is_not_a_receivable(db, user, client):
    """پیش‌دریافت از مشتری بدهیِ اوست نه طلبِ ما — نباید در سنیِ مطالبات بیاید."""
    _hybrid(db)
    contact = _make(client, opening_ar_amount=400000, opening_ar_side="credit")
    create_opening_entry(
        db,
        OpeningBalancesIn(
            entry_date=date(2026, 1, 1), lines=[], stock=[],
            balancing_account_id=_capital_account_id(db),
        ),
        user,
    )

    report = reports_service.get_aging(db, "receivable", date(2026, 6, 1))

    assert not [r for r in report["rows"] if str(r["contact_id"]) == contact["id"]]


def _capital_account_id(db):
    """حسابِ سرمایه — اختلافِ تراز افتتاحیه به آن بسته می‌شود."""
    from app.models.accounting import Account

    row = (
        db.query(Account)
        .filter(Account.type == "equity", Account.is_group.is_(False))
        .order_by(Account.code)
        .first()
    )
    assert row is not None, "چارتِ تستی باید یک حسابِ سرمایه داشته باشد"
    return row.id


# ── نشانی‌های چندگانه ─────────────────────────────────────────────────────────


def test_addresses_carry_type_and_delivery_fields(db, user, client):
    """نشانی جدولِ خودش را دارد چون شکلش با تلفن فرق می‌کند — شانزده فیلد در برابر سه.

    کاربردِ عملیاتی‌اش ارسالِ کالاست: نوع، مختصات و کدِ مسیر همان چیزی است که به
    مأمورِ ارسال داده می‌شود.
    """
    _hybrid(db)
    contact = _make(client)

    res = client.post(
        f"/api/contacts/{contact['id']}/addresses",
        json={
            "address_type": "shipping",
            "is_primary": True,
            "title": "انبارِ مرکزی",
            "address": "تهران، خیابان انقلاب، پلاک ۱",
            "postal_code": "1234567890",
            "latitude": "35.700000",
            "longitude": "51.400000",
            "route_code": "Z-14",
            "route_title": "زونِ مرکز",
        },
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["address_type"] == "shipping"
    assert body["route_code"] == "Z-14", "کدِ مسیر همان زونِ توزیع است"
    assert body["is_primary"] is True


#: «سایر» درِ خروجِ فهرست است — کارگاه، نمایشگاه، دفترِ موقت. بی آن، کاربر یکی از
#: هفت‌تای دیگر را دروغ انتخاب می‌کرد و فیلترِ «ارسال کالا» نشانی‌هایی برمی‌گرداند
#: که نشانیِ ارسال نبودند.
@pytest.mark.parametrize(
    "kind",
    ["official", "business", "billing", "shipping", "warehouse", "home", "postal", "other"],
)
def test_every_address_type_is_accepted(db, user, client, kind):
    _hybrid(db)
    contact = _make(client)

    res = client.post(
        f"/api/contacts/{contact['id']}/addresses", json={"address_type": kind, "address": "x"}
    )

    assert res.status_code == 201, res.text


def test_an_unknown_address_type_is_refused(db, user, client):
    _hybrid(db)
    contact = _make(client)

    res = client.post(
        f"/api/contacts/{contact['id']}/addresses", json={"address_type": "moon", "address": "x"}
    )

    assert res.status_code == 422, res.text


def test_half_a_coordinate_is_refused(db, user, client):
    """نیم‌مختصات روی نقشه هیچ نقطه‌ای نیست — مأمورِ ارسال نمی‌تواند استفاده‌اش کند."""
    _hybrid(db)
    contact = _make(client)

    res = client.post(
        f"/api/contacts/{contact['id']}/addresses",
        json={"address_type": "shipping", "latitude": "35.7"},
    )

    assert res.status_code == 422, res.text


def test_only_one_address_stays_primary(db, user, client):
    """**قاعده‌ی «اصلی».** نیتِ کاربری که «اصلی» را روی نشانی تازه می‌زند روشن است؛
    قبلی خودکار پایین می‌آید به‌جای اینکه ثبت رد شود."""
    _hybrid(db)
    contact = _make(client)
    first = client.post(
        f"/api/contacts/{contact['id']}/addresses",
        json={"address_type": "official", "address": "اولی", "is_primary": True},
    ).json()

    client.post(
        f"/api/contacts/{contact['id']}/addresses",
        json={"address_type": "shipping", "address": "دومی", "is_primary": True},
    )

    rows = client.get(f"/api/contacts/{contact['id']}/addresses").json()
    primaries = [r for r in rows if r["is_primary"]]
    assert len(primaries) == 1, "فقط یک نشانی می‌تواند اصلی باشد"
    assert primaries[0]["address"] == "دومی"
    assert next(r for r in rows if r["id"] == first["id"])["is_primary"] is False


def test_only_one_phone_stays_primary(db, user, client):
    """همان قاعده برای تلفن."""
    _hybrid(db)
    contact = _make(client)
    client.post(
        f"/api/contacts/{contact['id']}/channels",
        json={"kind": "phone", "channel_type": "office", "value": "021-1", "is_primary": True},
    )
    client.post(
        f"/api/contacts/{contact['id']}/channels",
        json={"kind": "phone", "channel_type": "mobile", "value": "0912-2", "is_primary": True},
    )

    rows = client.get(f"/api/contacts/{contact['id']}/channels").json()
    assert len([r for r in rows if r["is_primary"]]) == 1


def test_addresses_die_with_their_contact(db, user, client):
    _hybrid(db)
    contact = _make(client)
    client.post(f"/api/contacts/{contact['id']}/addresses", json={"address": "x"})

    db.delete(db.get(Contact, contact["id"]))
    db.flush()

    from app.models.company import ContactAddress

    assert db.query(ContactAddress).filter(ContactAddress.contact_id == contact["id"]).count() == 0


# ── مشخصاتِ شخصی و سهامدار ───────────────────────────────────────────────────


def test_person_fields_live_on_the_contact_not_the_employee(db, user, client):
    """**تصمیمِ جای‌گذاری.** جنسیت و تأهل و تحصیلات واقعیتِ *شخص*اند نه شغلش.

    اگر روی `employees` می‌نشستند، مشتریِ غیرکارمند هیچ‌وقت نمی‌توانست داشته باشدشان.
    واقعیت‌های *استخدام* سرِ جایشان در حقوق و دستمزد می‌مانند.
    """
    from app.models.payroll import Employee

    _hybrid(db)

    body = _make(
        client,
        gender="male",
        marital_status="married",
        marital_status_date="2020-03-21",
        children_count=2,
        dependents_count=3,
        education_level="کارشناسی",
        education_field="حسابداری",
        is_employee=True,
    )

    assert body["gender"] == "male"
    assert body["children_count"] == 2
    assert body["education_field"] == "حسابداری"
    #: و هیچ‌کدام روی جدولِ کارمند تکرار نشده‌اند.
    assert {"gender", "marital_status", "children_count"}.isdisjoint(
        {c.name for c in Employee.__table__.columns}
    )


def test_shareholder_is_a_fourth_independent_role(db, user, client):
    """مثلِ واسطه، پرچمِ مستقل — نه مقدارِ تازه‌ی `type`."""
    from app.models.inventory import CONTACT_TYPES

    assert "shareholder" not in CONTACT_TYPES
    _hybrid(db)

    body = _make(client, type="customer", is_shareholder=True, share_percent=12.5)

    assert body["type"] == "customer"
    assert body["is_shareholder"] is True
    assert float(body["share_percent"]) == 12.5


@pytest.mark.parametrize("bad", [-1, 101])
def test_share_percent_outside_zero_to_hundred_is_refused(db, user, client, bad):
    _hybrid(db)

    res = client.post("/api/contacts", json=_payload(share_percent=bad))

    assert res.status_code == 422, res.text


def test_an_invalid_gender_is_refused(db, user, client):
    _hybrid(db)

    res = client.post("/api/contacts", json=_payload(gender="alien"))

    assert res.status_code == 422, res.text


def test_gender_and_marital_status_may_stay_empty(db, user, client):
    """رشته‌ی خالی = وارد نشده. مشتریِ حقوقی جنسیت ندارد و نباید مجبور به انتخاب شود."""
    _hybrid(db)

    body = _make(client, entity_type="legal", name="شرکتِ الف")

    assert body["gender"] == ""
    assert body["marital_status"] == ""


def test_related_person_keeps_its_second_names(db, user, client):
    """**ایرادِ واقعیِ پیداشده در آزمونِ زنده.** `name2`/`role2` در سرویس جا افتاده
    بودند: ورودی می‌آمد، در پایگاه‌داده ستون داشت، ولی نه ذخیره می‌شد نه برمی‌گشت."""
    _hybrid(db)
    contact = _make(client)

    res = client.post(
        "/api/company/persons",
        json={
            "contact_id": contact["id"],
            "name": "مریم رجبی",
            "role": "همسر",
            "name2": "Maryam Rajabi",
            "role2": "Spouse",
        },
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name2"] == "Maryam Rajabi"
    assert body["role2"] == "Spouse"
    assert body["name"] == "مریم رجبی", "نسخه‌ی لاتین نباید فارسی را عوض کند"


def test_a_partial_edit_does_not_trip_the_opening_lock(db, user, client):
    """قفل روی مانده است، نه روی کلِ طرف‌حساب.

    ویرایشی که اصلاً مانده را نفرستاده نباید ۴۰۹ بگیرد — و نباید عددِ ثبت‌شده را هم
    صفر کند. تا پیش از این هر دو اتفاق می‌افتاد: فرمِ ساده مانده را نمی‌فرستاد،
    اسکیما صفر می‌گذاشت، و صفرِ ساختگی با عددِ سند فرق داشت.
    """
    _hybrid(db)
    contact = _make(client, opening_ar_amount=100000)
    create_opening_entry(
        db,
        OpeningBalancesIn(
            entry_date=date(2026, 1, 1), lines=[], stock=[],
            balancing_account_id=_capital_account_id(db),
        ),
        user,
    )

    res = client.patch(f"/api/contacts/{contact['id']}", json={"name": "نامِ تازه"})

    assert res.status_code == 200, res.text
    assert Decimal(str(res.json()["opening_ar_amount"])) == 100000
