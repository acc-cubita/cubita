"""کارمندی که رفته باید بتواند برود.

**چه کم بود.** `Employee.is_active` در کلِ بک‌اند **یک خواننده** دارد و آن
صدورِ فیشِ حقوقی است ([`payroll.py`](../app/services/payroll.py) →
`filter(Employee.is_active.is_(True))`). و هیچ مسیری آن ستون را نمی‌نوشت:
روترِ کارمند فقط `GET` و `POST` داشت.

گاردِ دومی هم نبود. `get_current_contract` فقط `effective_from <= as_of` را
می‌بیند و **`service_end_date` را نمی‌خواند** — با اینکه docstringِ خودِ
`SalaryContract` می‌گوید «از این‌جا به بعد کارکرد اصلاً محاسبه نمی‌شود». آن
ستون قید دارد، اعتبارسنجی دارد و `employees.termination_date` را هم پر می‌کند؛
ولی هیچ محاسبه‌ای نمی‌خواندش.

جمعِ این دو یعنی **کارمندی که رفته هر دوره فیشِ کامل می‌گیرد**، با سند و بیمه
و مالیاتش.
"""
from datetime import date
from decimal import Decimal

from app.models.payroll import Employee, PayrollSettings, Payslip

BRACKETS = [{"up_to": 2_000_000_000, "rate": 0.1}, {"up_to": None, "rate": 0.2}]
EXEMPTION = Decimal("1200000000")


def _settings(db, year):
    if not db.query(PayrollSettings).filter(PayrollSettings.year == year).first():
        db.add(PayrollSettings(
            year=year,
            insurance_employee_rate=Decimal("0.07"),
            insurance_employer_rate=Decimal("0.23"),
            tax_exemption_annual=EXEMPTION,
            tax_brackets=BRACKETS,
        ))
        db.flush()


def _contact(client, *, national_id, first="سارا", last="کاظمی"):
    r = client.post("/api/contacts", json={
        "name": f"{first} {last}", "first_name": first, "last_name": last,
        "type": "customer", "national_id": national_id, "is_employee": True,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _hire(client, contact_id, hire_date="2025-01-01"):
    r = client.post("/api/employees", json={"contact_id": contact_id, "hire_date": hire_date})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _contract(client, contact_id, **kw):
    base = next(
        x["id"] for x in client.post("/api/payroll-factors/defaults", json={}).json()
        if x.get("system_key") == "base"
    )
    r = client.post("/api/salary-contracts", json={
        "contact_id": contact_id, "effective_from": "2026-01-01",
        "lines": [{"factor_id": base, "amount": 500_000_000}], **kw,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _run_payroll(client, db, *, year=1405, month=6):
    _settings(db, year)
    period = client.post("/api/payroll-periods", json={"year": year, "month": month})
    assert period.status_code in (200, 201), period.text
    pid = period.json()["id"]
    issued = client.post(f"/api/payroll-periods/{pid}/generate-payslips", json={})
    assert issued.status_code == 200, issued.text
    return pid


def _payslip_ids(db, period_id):
    return {p.employee_id for p in db.query(Payslip).filter(Payslip.period_id == period_id).all()}


# ═══════════ ۱) درِ ورود: ویرایشِ پرونده‌ی کارمند ═══════════


def test_the_patch_route_exists_at_all(client, db):
    """تا امروز روترِ کارمند فقط `GET` و `POST` داشت ⇒ ۴۰۵."""
    emp = _hire(client, _contact(client, national_id="0072534891"))
    res = client.patch(f"/api/employees/{emp}", json={"bank_account_number": "IR000"})
    assert res.status_code != 405, "*** مسیرِ ویرایش دوباره ناپدید شد ***"
    assert res.status_code == 200, res.text


def test_an_employee_can_be_deactivated_and_reactivated(client, db):
    emp = _hire(client, _contact(client, national_id="0072534892"))

    off = client.patch(f"/api/employees/{emp}", json={"is_active": False})
    assert off.status_code == 200, off.text
    assert off.json()["is_active"] is False

    on = client.patch(f"/api/employees/{emp}", json={"is_active": True})
    assert on.json()["is_active"] is True


def test_a_partial_edit_does_not_silently_reactivate(client, db):
    """همان تله‌ی `exclude_unset` که در طرف‌حساب هم بود."""
    emp = _hire(client, _contact(client, national_id="0072534893"))
    client.patch(f"/api/employees/{emp}", json={"is_active": False})

    res = client.patch(f"/api/employees/{emp}", json={"bank_account_number": "IR820540"})
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False, "*** ویرایشِ جزئی دوباره فعالش کرد ***"


def test_a_termination_date_before_hire_is_refused(client, db):
    """**با `hire_date`ِ ذخیره‌شده سنجیده می‌شود، نه فقط با آنچه در درخواست آمده.**

    درخواستِ زیر فقط تاریخِ پایان را می‌فرستد. اگر گارد تنها به بدنه نگاه می‌کرد،
    این حالت — که حالتِ رایج است — از دستش در می‌رفت.
    """
    emp = _hire(client, _contact(client, national_id="0072534894"), hire_date="2025-06-01")
    res = client.patch(f"/api/employees/{emp}", json={"termination_date": "2025-01-01"})
    assert res.status_code == 400, res.text
    assert "استخدام" in res.json()["detail"]


def test_a_missing_employee_is_404(client, db):
    from uuid import uuid4
    assert client.patch(f"/api/employees/{uuid4()}", json={"is_active": False}).status_code == 404


# ═══════════ ۲) اثرِ واقعی: فیشِ حقوقی ═══════════


def test_a_deactivated_employee_gets_no_payslip(client, db):
    """**هدفِ اصلیِ این فصل.**

    تا امروز `is_active` نوشتنی نبود، پس این تنها گاردِ موجود هم بی‌استفاده بود.
    """
    stays = _contact(client, national_id="0072534895", first="مینا")
    goes = _contact(client, national_id="0072534896", first="حسین")
    emp_stays, emp_goes = _hire(client, stays), _hire(client, goes)
    _contract(client, stays)
    _contract(client, goes)

    assert client.patch(f"/api/employees/{emp_goes}", json={"is_active": False}).status_code == 200

    period_id = _run_payroll(client, db, month=6)
    got = _payslip_ids(db, period_id)
    from uuid import UUID
    assert UUID(emp_stays) in got, "کارمندِ فعال باید فیش بگیرد"
    assert UUID(emp_goes) not in got, "*** کارمندِ غیرفعال فیش گرفت ***"


def test_a_finished_contract_stops_the_payslip(client, db):
    """**گاردِ دوم — و دلیلِ اینکه `is_active` تنها کافی نیست.**

    کاربر «تاریخ پایان خدمت» را روی حکم پر می‌کند و انتظار دارد همان کافی باشد.
    تا امروز `get_current_contract` فقط `effective_from` را می‌دید، پس حکمی که
    خدمتش تمام شده بود همچنان «حکمِ جاری» بود و فیشِ کامل می‌داد.
    """
    left = _contact(client, national_id="0072534897", first="نازنین")
    stays = _contact(client, national_id="0072534900", first="فرهاد")
    emp_left, emp_stays = _hire(client, left), _hire(client, stays)
    _contract(client, left, service_end_date="2026-02-15")
    _contract(client, stays)

    period_id = _run_payroll(client, db, month=7)
    got = _payslip_ids(db, period_id)
    from uuid import UUID
    assert UUID(emp_left) not in got, "*** کارمندی که خدمتش تمام شده فیش گرفت ***"
    #: همکارِ شاغل باید فیشش را بگیرد — وگرنه گارد به‌جای یک نفر کلِ دوره را
    #: خاموش کرده و تست از یک ۴۰۰ِ «هیچ کارمندی نبود» سبز در می‌آمد.
    assert UUID(emp_stays) in got, "*** گارد همکارِ شاغل را هم برد ***"


def test_an_open_ended_contract_still_pays(client, db):
    """**پیش‌فرض = رفتارِ دیروز.** حکمِ بی‌تاریخِ پایان نباید هیچ فرقی کند."""
    here = _contact(client, national_id="0072534898", first="کامران")
    emp = _hire(client, here)
    _contract(client, here)

    period_id = _run_payroll(client, db, month=8)
    from uuid import UUID
    assert UUID(emp) in _payslip_ids(db, period_id)


def test_valid_until_is_deliberately_not_a_guard(client, db):
    """**تصمیمِ صریح، تا کسی «اصلاحش» نکند.**

    `valid_until` یعنی «اعتبارِ این حکم تا این‌جاست»، نه «این آدم رفته». در
    ایران تمدیدِ حکم اغلب دیر می‌رسد؛ اگر این ستون حقوق را قطع می‌کرد، کارمندِ
    شاغل بی‌صدا بی‌حقوق می‌ماند — خرابی‌ای بدتر از آنچه می‌بست.
    """
    here = _contact(client, national_id="0072534899", first="بهاره")
    emp = _hire(client, here)
    _contract(client, here, valid_until="2026-02-15")

    period_id = _run_payroll(client, db, month=9)
    from uuid import UUID
    assert UUID(emp) in _payslip_ids(db, period_id), (
        "*** `valid_until` نباید حقوق را قطع کند ***"
    )
