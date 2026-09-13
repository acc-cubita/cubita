"""شعبه‌ی بیمه و حوزه‌ی مالیاتی: یک نام بود، حالا یک هویت است.

سه چیزی که این فصل بست:

  ۱. شعبه به هیچ **طرف حسابی** وصل نبود. بدهیِ بیمه و مالیاتِ تکلیفی واقعاً به
     همان سازمان پرداخت می‌شود، ولی آن سازمان در دفترِ کوبیتا وجود نداشت — فقط
     نامش روی قرارداد نشسته بود.

  ۲. `tax_branch_id` و `insurance_branch_id` روی قرارداد بودند و **هیچ‌جا خوانده
     نمی‌شدند**. کاربر شعبه را انتخاب می‌کرد و هیچ اتفاقی نمی‌افتاد — نه در
     محاسبه، نه در فایلِ بیمه، نه در فایلِ مالیات.

  ۳. تغییرِ شعبه هیچ ردِ حسابرسی نمی‌گذاشت، با اینکه روی همه‌ی قراردادهای وصل به
     آن اثر دارد.
"""
from datetime import date
from decimal import Decimal

from app.audit import audited_models, bind_session_actor
from app.models.audit import AuditLog
from app.models.inventory import Contact
from app.models.payroll import InsuranceTaxBranch, PayrollSettings

TODAY = date.today().isoformat()
BRACKETS = [{"up_to": 2_000_000_000, "rate": 0.1}, {"up_to": None, "rate": 0.2}]


def _contact(client, name, national_id):
    r = client.post(
        "/api/contacts",
        json={"name": name, "type": "supplier", "national_id": national_id},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _branch(client, name, kind="insurance", code="", contact_id=None):
    r = client.post(
        "/api/insurance-tax-branches",
        json={"name": name, "kind": kind, "code": code, "contact_id": contact_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _employee(client, *, first, last, national_id):
    contact_id = _contact(client, f"{first} {last}", national_id)
    client.patch(
        f"/api/contacts/{contact_id}",
        json={"name": f"{first} {last}", "first_name": first, "last_name": last,
              "type": "customer", "is_employee": True, "national_id": national_id},
    )
    return contact_id


def _settings(db, year=1405):
    if db.query(PayrollSettings).filter(PayrollSettings.year == year).first():
        return
    db.add(
        PayrollSettings(
            year=year,
            insurance_employee_rate=Decimal("0.07"),
            insurance_employer_rate=Decimal("0.23"),
            tax_exemption_annual=Decimal("1200000000"),
            tax_brackets=BRACKETS,
        )
    )
    db.flush()


def _payroll(client, db, contact_id, *, month, insurance_branch=None, tax_branch=None, year=1405):
    """یک حکم و یک دوره‌ی واقعی، تا خروجی‌های قانونی چیزی برای نوشتن داشته باشند."""
    _settings(db, year)
    factors = client.post("/api/payroll-factors/defaults", json={}).json()
    base = next(f["id"] for f in factors if f.get("system_key") == "base")
    body = {
        "contact_id": contact_id,
        "effective_from": "2026-01-01",
        "lines": [{"factor_id": base, "amount": 500_000_000}],
    }
    if insurance_branch:
        body["insurance_branch_id"] = insurance_branch
    if tax_branch:
        body["tax_branch_id"] = tax_branch
    r = client.post("/api/salary-contracts", json=body)
    assert r.status_code == 201, r.text

    period = client.post("/api/payroll-periods", json={"year": year, "month": month}).json()
    issued = client.post(f"/api/payroll-periods/{period['id']}/generate-payslips", json={})
    assert issued.status_code == 200, issued.text
    return period["id"]


# ═══════════════ ۱) شعبه هویتِ حسابداری پیدا کرد ═══════════════


def test_a_branch_can_carry_the_organisation_as_a_party(client, db):
    """شعبه به طرف حساب وصل می‌شود — نه با یک رشته‌ی نام، با شناسه‌ی پایدار."""
    org = _contact(client, "سازمان تأمین اجتماعی", "10100000001")
    branch = _branch(client, "شعبه ۱۲ تهران", code="12", contact_id=org)

    assert branch["contact_id"] == org
    assert branch["contact_name"] == "سازمان تأمین اجتماعی"


def test_the_party_name_is_read_live_not_copied(client, db):
    """اگر نامِ سازمان اصلاح شود، شعبه نامِ تازه را نشان می‌دهد.

    اگر نام کپی می‌شد، همان باگی تکرار می‌شد که فصلِ «تعریف کارمند» بست: دو حقیقت
    از یک آدم، و اصلاحِ یکی هیچ‌وقت به دیگری نمی‌رسد.
    """
    org = _contact(client, "اداره مالیات قدیم", "10100000002")
    branch = _branch(client, "حوزه ۲۰۳", kind="tax", contact_id=org)

    r = client.patch(f"/api/contacts/{org}", json={"name": "اداره امور مالیاتی شمال", "type": "supplier"})
    assert r.status_code == 200, r.text

    listed = client.get("/api/insurance-tax-branches?kind=tax").json()
    row = next(b for b in listed if b["id"] == branch["id"])
    assert row["contact_name"] == "اداره امور مالیاتی شمال"


def test_an_existing_branch_can_be_linked_afterwards(client, db):
    """شعبه‌های پیش از ۰۱۳۶ باید بتوانند بعداً طرف حساب بگیرند.

    بی مسیرِ ویرایش، `contact_id` ستونی می‌شد که فقط شعبه‌های تازه پرش می‌کردند.
    """
    branch = _branch(client, "شعبه بی‌هویت")
    assert branch["contact_id"] is None

    org = _contact(client, "سازمان تأمین اجتماعی — بعداً", "10100000003")
    r = client.patch(
        f"/api/insurance-tax-branches/{branch['id']}",
        json={"name": branch["name"], "kind": branch["kind"], "code": "44", "contact_id": org},
    )
    assert r.status_code == 200, r.text
    assert r.json()["contact_id"] == org
    assert r.json()["code"] == "44"


def test_an_unknown_party_is_refused(client, db):
    from uuid import uuid4

    r = client.post(
        "/api/insurance-tax-branches",
        json={"name": "شعبه خیالی", "kind": "insurance", "contact_id": str(uuid4())},
    )
    assert r.status_code == 400, r.text


def test_a_branch_without_a_party_still_works(client, db):
    """پیوند اختیاری است — نبودنش هیچ‌چیز را نمی‌شکند."""
    branch = _branch(client, "شعبه بدون سازمان", code="99")
    assert branch["contact_id"] is None
    assert branch["contact_name"] == ""

    listed = client.get("/api/insurance-tax-branches").json()
    assert any(b["id"] == branch["id"] for b in listed)


# ═══════════════ ۲) انتخابِ شعبه بالاخره اثر دارد ═══════════════


def test_the_insurance_file_carries_the_branch(client, db):
    """باگی که این فصل بست: شعبه انتخاب می‌شد و در هیچ فایلی دیده نمی‌شد."""
    org = _contact(client, "تأمین اجتماعی", "10100000010")
    branch = _branch(client, "شعبه ۷ کرج", code="07", contact_id=org)
    employee = _employee(client, first="رضا", last="بیمه‌ای", national_id="8000000001")

    period_id = _payroll(client, db, employee, month=4, insurance_branch=branch["id"])

    csv_text = client.get(f"/api/payroll-periods/{period_id}/insurance-list.csv").text
    assert "کد شعبه بیمه" in csv_text, "ستونِ شعبه باید در سرصفحه باشد"
    assert "شعبه ۷ کرج" in csv_text, "نامِ شعبه باید در ردیفِ کارمند بیاید"
    assert "07" in csv_text


def test_the_tax_file_carries_the_tax_office(client, db):
    office = _contact(client, "امور مالیاتی", "10100000011")
    branch = _branch(client, "حوزه ۳۰۱", kind="tax", code="301", contact_id=office)
    employee = _employee(client, first="سارا", last="مالیاتی", national_id="8000000002")

    period_id = _payroll(client, db, employee, month=5, tax_branch=branch["id"])

    csv_text = client.get(f"/api/payroll-periods/{period_id}/tax-list.csv").text
    assert "حوزه مالیاتی" in csv_text
    assert "حوزه ۳۰۱" in csv_text
    assert "301" in csv_text


def test_a_missing_branch_leaves_the_column_empty_not_guessed(client, db):
    """حکمی که شعبه ندارد، ستونِ خالی می‌دهد — نه یک شعبه‌ی حدسی.

    پرکردنِ حدسی یعنی فایل چیزی را به سازمان بگوید که کسی تصمیمش نگرفته.
    """
    employee = _employee(client, first="بی", last="شعبه", national_id="8000000003")
    period_id = _payroll(client, db, employee, month=6)

    csv_text = client.get(f"/api/payroll-periods/{period_id}/insurance-list.csv").text
    row = next(line for line in csv_text.splitlines() if "8000000003" in line)
    #: کد ملی، نام، نام خانوادگی، کد شعبه، شعبه، …  ← دو ستونِ چهارم و پنجم خالی
    cells = row.split(",")
    assert cells[3] == "" and cells[4] == "", f"ستونِ شعبه باید خالی باشد: {cells}"


def test_the_wrong_kind_of_branch_does_not_leak_into_the_other_file(client, db):
    """حوزه‌ی مالیاتیِ یک کارمند نباید در فایلِ بیمه‌اش ظاهر شود."""
    branch = _branch(client, "حوزه فقط-مالیاتی", kind="tax", code="777")
    employee = _employee(client, first="فقط", last="مالیات", national_id="8000000004")
    period_id = _payroll(client, db, employee, month=7, tax_branch=branch["id"])

    insurance = client.get(f"/api/payroll-periods/{period_id}/insurance-list.csv").text
    assert "حوزه فقط-مالیاتی" not in insurance
    assert "777" not in insurance

    tax = client.get(f"/api/payroll-periods/{period_id}/tax-list.csv").text
    assert "حوزه فقط-مالیاتی" in tax


# ═══════════════ ۳) ردِ حسابرسی ═══════════════


def test_the_branch_is_in_the_audit_registry():
    assert InsuranceTaxBranch in audited_models()


def test_changing_a_branch_leaves_a_trail(client, db, user):
    """عوض‌کردنِ طرف حسابِ یک شعبه یعنی بدهیِ ده‌ها قرارداد جای دیگری برود.

    هیچ سندی این تغییر را نشان نمی‌دهد — و دقیقاً به همین دلیل حسابرسی‌اش لازم
    است، نه کمتر.
    """
    bind_session_actor(db, user)
    branch = _branch(client, "شعبه قابل‌ردیابی", code="55")

    before = db.query(AuditLog).filter(AuditLog.entity_id == branch["id"]).count()

    org = _contact(client, "سازمانِ تازه", "10100000020")
    r = client.patch(
        f"/api/insurance-tax-branches/{branch['id']}",
        json={"name": "شعبه قابل‌ردیابی", "kind": "insurance", "code": "55", "contact_id": org},
    )
    assert r.status_code == 200, r.text

    db.expire_all()
    after = db.query(AuditLog).filter(AuditLog.entity_id == branch["id"]).count()
    assert after > before, "تغییرِ شعبه باید ردِ حسابرسی بگذارد"


def test_a_contact_the_branch_points_at_is_readable_through_the_party(client, db):
    """پیوند به *طرف حساب* است نه به تفصیلی — و تفصیلی از همان‌جا می‌آید."""
    org = _contact(client, "سازمان با تفصیلی", "10100000030")
    branch = _branch(client, "شعبه تفصیلی‌دار", contact_id=org)

    db.expire_all()
    row = db.get(InsuranceTaxBranch, branch["id"])
    assert row.contact is not None
    assert isinstance(row.contact, Contact)
    #: تفصیلی ممکن است بسته به تنظیمِ مستأجر ساخته نشده باشد؛ چیزی که این‌جا
    #: تضمین می‌شود مسیرِ رسیدن است، نه وجودِ حتمیِ تفصیلی.
    assert hasattr(row.contact, "analytic_id")
