"""کارمند هویتِ دوم نیست — نقشی روی همان طرف حساب است.

کوبیتا این را از قبل فهمیده بود: `Contact.is_employee` تیکِ نقش است و
`Contact.employee_id` پیوند، و واقعیت‌های *شخص* (جنسیت، تأهل، فرزند، تحصیلات)
روی خودِ طرف حساب می‌نشینند. کامنتِ مدل هم صریح است: «دو پیوند، نه دو کپی».

ولی دو جا این اصل نقض می‌شد:

  ۱. `Employee` نام و کدِ ملی و تلفن را هنگامِ استخدام **کپی** می‌کرد و بعد
     هرگز همگام نمی‌شد. و چون هر سه خروجیِ قانونی از همان کپی می‌خواندند،
     اصلاحِ نام یا کدِ ملی **هیچ‌وقت به فایلِ بانک و اظهارنامه نمی‌رسید**.

  ۲. `POST /api/employees` کارمندی می‌ساخت که به هیچ طرف حسابی وصل نبود —
     همان هویتِ تکراری که کلِ معماری برای جلوگیری از آن ساخته شده.
"""
from datetime import date
from uuid import UUID
from decimal import Decimal

import pytest

from app.models.inventory import Contact
from app.models.payroll import Employee, PayrollSettings

TODAY = date.today().isoformat()
BRACKETS = [{"up_to": 2_000_000_000, "rate": 0.1}, {"up_to": None, "rate": 0.2}]
EXEMPTION = Decimal("1200000000")


def _contact(client, *, national_id, first="رضا", last="محمدی", phone="09120000001"):
    r = client.post(
        "/api/contacts",
        json={
            "name": f"{first} {last}",
            "first_name": first,
            "last_name": last,
            "type": "customer",
            "national_id": national_id,
            "phone": phone,
            "is_employee": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _hire(client, contact_id, **kw):
    return client.post(
        "/api/employees",
        json={"contact_id": contact_id, "hire_date": TODAY, **kw},
    )


def _rename(client, contact_id, *, last, national_id=None, first="رضا"):
    """نامِ طرف حساب را عوض می‌کند. `PATCH` بدنه‌ی کامل می‌خواهد، نه میدانِ تکی."""
    body = {
        "name": f"{first} {last}",
        "first_name": first,
        "last_name": last,
        "type": "customer",
        "is_employee": True,
    }
    if national_id is not None:
        body["national_id"] = national_id
    r = client.patch(f"/api/contacts/{contact_id}", json=body)
    assert r.status_code == 200, r.text
    return r


def _settings(db, year):
    db.add(
        PayrollSettings(
            year=year,
            insurance_employee_rate=Decimal("0.07"),
            insurance_employer_rate=Decimal("0.23"),
            tax_exemption_annual=EXEMPTION,
            tax_brackets=BRACKETS,
        )
    )
    db.flush()


def _payroll(client, db, contact_id, year=1405, month=1):
    """یک دوره‌ی واقعی با فیش، تا خروجی‌های قانونی چیزی برای نوشتن داشته باشند."""
    if not db.query(PayrollSettings).filter(PayrollSettings.year == year).first():
        _settings(db, year)
    f = client.post("/api/payroll-factors/defaults", json={}).json()
    base = next(x["id"] for x in f if x.get("system_key") == "base")
    r = client.post(
        "/api/salary-contracts",
        json={
            "contact_id": contact_id,
            "effective_from": "2026-01-01",
            "lines": [{"factor_id": base, "amount": 500_000_000}],
        },
    )
    assert r.status_code == 201, r.text
    period = client.post("/api/payroll-periods", json={"year": year, "month": month}).json()
    issued = client.post(f"/api/payroll-periods/{period['id']}/generate-payslips", json={})
    assert issued.status_code == 200, issued.text
    return period["id"]


# ═══════════════ ۱) یک آدم، یک حقیقت ═══════════════


def test_correcting_a_name_reaches_the_bank_file(client, db):
    """باگی که این فصل بست.

    نامِ روی دیسکتِ پرداخت باید نامِ **امروزِ** آن آدم باشد. تا امروز نامی بود که
    سالِ پیش موقعِ استخدام کپی شده بود.
    """
    cid = _contact(client, national_id="7000000001", last="محمدی")
    assert _hire(client, cid).status_code == 201
    period_id = _payroll(client, db, cid)

    #: نام و کدِ ملیِ طرف حساب اصلاح می‌شوند.
    _rename(client, cid, last="محمدیِ اصلاح‌شده", national_id="7000000099")

    csv_text = client.get(f"/api/payroll-periods/{period_id}/payment-list.csv").text
    assert "محمدیِ اصلاح‌شده" in csv_text, "دیسکتِ پرداخت باید نامِ اصلاح‌شده را بگیرد"
    assert "7000000099" in csv_text, "و کدِ ملیِ اصلاح‌شده را"


def test_the_tax_and_insurance_files_follow_too(client, db):
    """هر سه خروجیِ قانونی از یک هویت می‌خوانند، نه سه‌تا."""
    cid = _contact(client, national_id="7000000002", last="کریمی")
    assert _hire(client, cid).status_code == 201
    period_id = _payroll(client, db, cid, month=2)

    _rename(client, cid, last="کریمیِ تازه")

    for path in ("tax-list.csv", "insurance-list.csv"):
        text = client.get(f"/api/payroll-periods/{period_id}/{path}").text
        assert "کریمیِ تازه" in text, f"{path} نامِ کهنه دارد"


def test_the_payslip_numbers_are_untouched_by_an_identity_change(client, db):
    """هویت از طرف حساب می‌آید، ولی **اعداد** همان snapshotِ فیش‌اند.

    این مرز مهم است: نامِ روی فایلِ این ماه باید تازه باشد، ولی مبلغِ حقوقِ
    ماهِ گذشته نه.
    """
    from app.models.payroll import Payslip

    cid = _contact(client, national_id="7000000003", last="نوری")
    assert _hire(client, cid).status_code == 201
    period_id = _payroll(client, db, cid, month=3)

    db.expire_all()
    before = {(p.id, Decimal(p.net_pay)) for p in db.query(Payslip).filter(Payslip.period_id == period_id)}

    _rename(client, cid, last="نوریِ تازه")

    db.expire_all()
    after = {(p.id, Decimal(p.net_pay)) for p in db.query(Payslip).filter(Payslip.period_id == period_id)}
    assert before == after, "تغییرِ هویت نباید عددِ فیش را تکان دهد"


# ═══════════════ ۲) درِ پشتی بسته شد ═══════════════


def test_the_old_shape_still_works_but_no_longer_makes_an_orphan(client, db):
    """فرمِ قدیمی نمی‌شکند — ولی دیگر هویتِ بی‌طرف‌حساب نمی‌سازد.

    شکستنِ این شکل یعنی رابطِ مستقر تا رسیدنِ باندلِ تازه کار نکند، بی‌آنکه چیزی
    به درستیِ داده اضافه شود.
    """
    r = client.post(
        "/api/employees",
        json={"first_name": "الف", "last_name": "تازه‌وارد", "national_id": "7000000004",
              "hire_date": TODAY},
    )
    assert r.status_code == 201, r.text

    db.expire_all()
    linked = db.query(Contact).filter(Contact.employee_id == UUID(r.json()["id"])).one_or_none()
    assert linked is not None, "طرف حساب باید ساخته و وصل شده باشد"
    assert linked.is_employee is True
    assert linked.national_id == "7000000004"


def test_the_old_shape_reuses_an_existing_person(client, db):
    """اگر همان آدم از قبل مشتری بوده، رکوردِ دوم ساخته نمی‌شود."""
    cid = _contact(client, national_id="7000000010", last="ازقبل‌مشتری")

    r = client.post(
        "/api/employees",
        json={"first_name": "رضا", "last_name": "ازقبل‌مشتری", "national_id": "7000000010",
              "hire_date": TODAY},
    )
    assert r.status_code == 201, r.text

    db.expire_all()
    assert db.query(Contact).filter(Contact.national_id == "7000000010").count() == 1,         "کدِ ملیِ یکسان نباید طرف حسابِ دوم بسازد"
    assert str(db.get(Contact, cid).employee_id) == r.json()["id"]


def test_an_employee_needs_some_identity(client, db):
    r = client.post("/api/employees", json={"hire_date": TODAY})
    assert r.status_code == 422


def test_hiring_links_the_contact_and_ticks_the_role(client, db):
    cid = _contact(client, national_id="7000000005", last="سعیدی")
    r = _hire(client, cid, bank_account_number="IR-123")
    assert r.status_code == 201, r.text

    db.expire_all()
    contact = db.get(Contact, cid)
    assert contact.employee_id is not None, "پیوند باید برقرار شود"
    assert contact.is_employee is True, "تیکِ نقش باید روشن شود"
    employee = db.get(Employee, contact.employee_id)
    assert employee.bank_account_number == "IR-123"


def test_hiring_twice_returns_the_same_file(client, db):
    """تکرار بی‌خطر است — پرونده‌ی دوم ساخته نمی‌شود."""
    cid = _contact(client, national_id="7000000006", last="رضوی")
    first = _hire(client, cid)
    second = _hire(client, cid, bank_account_number="IR-999")
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"], "همان کارمند"

    db.expire_all()
    assert db.query(Employee).filter(Employee.national_id == "7000000006").count() == 1
    #: و شماره‌حسابِ تازه روی همان پرونده نشست.
    assert db.get(Employee, first.json()["id"]).bank_account_number == "IR-999"


def test_an_unknown_contact_is_refused(client, db):
    from uuid import uuid4

    r = _hire(client, str(uuid4()))
    assert r.status_code == 400


# ═══════════════ ۳) میراث دست‌نخورده ═══════════════


def test_a_legacy_employee_without_a_contact_still_exports(client, db):
    """کارمندانِ بی‌طرف‌حسابِ قدیمی نباید از فایل‌ها بیفتند.

    ستون‌های خودِ `Employee` پشتیبان‌اند، نه حقیقتِ دوم — و همین‌جا کارشان را
    می‌کنند.
    """
    from app.services.payroll import employee_identity

    legacy = Employee(
        first_name="قدیمی",
        last_name="بی‌طرف‌حساب",
        national_id="7000000007",
        hire_date=date(2025, 1, 1),
    )
    db.add(legacy)
    db.flush()

    who = employee_identity(db, legacy.id)
    assert who is not None
    assert who.from_contact is False, "هویت از خودِ کارمند آمد"
    assert who.full_name == "قدیمی بی‌طرف‌حساب"
    assert who.national_id == "7000000007"


def test_identity_comes_from_the_contact_when_linked(client, db):
    from app.services.payroll import employee_identity

    cid = _contact(client, national_id="7000000008", last="وصل‌شده")
    employee_id = UUID(_hire(client, cid).json()["id"])

    who = employee_identity(db, employee_id)
    assert who.from_contact is True
    assert who.last_name == "وصل‌شده"


@pytest.mark.parametrize("blank", ["", None])
def test_a_cleared_national_id_shows_as_empty_not_stale(client, db, blank):
    """اگر کاربر کدِ ملی را پاک کرده، فایل هم باید خالی باشد.

    برگرداندنِ مقدارِ کهنه یعنی فایل چیزی را جا می‌زند که کاربر عمداً برداشته.
    """
    from app.services.payroll import employee_identity

    cid = _contact(client, national_id="7000000009", last="پاک‌شده")
    employee_id = UUID(_hire(client, cid).json()["id"])

    db.expire_all()
    db.get(Contact, cid).national_id = blank
    db.flush()

    who = employee_identity(db, employee_id)
    assert who.national_id == "", "کدِ ملیِ پاک‌شده خالی می‌ماند، نه کهنه"
