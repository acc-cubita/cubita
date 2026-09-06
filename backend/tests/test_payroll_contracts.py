"""فرمِ «قرارداد جدید» — از طرف‌حساب تا رکوردِ قرارداد.

قیدهایی که این تست‌ها نگه می‌دارند و جای دیگری نگهبان ندارند:

* **یک آدم، یک رکورد.** طرف‌حسابی که تیکِ «کارمند» دارد با اولین قراردادش پرونده‌ی
  حقوق و دستمزد می‌گیرد؛ کاربر همان نام و کد ملی را دوباره تایپ نمی‌کند.
* **«استخدام» فقط یک بار**، و «اصلاح قرارداد» فقط بعد از آن.
* **چهار ستونِ مبلغ از ردیف‌ها ساخته می‌شوند.** اگر روزی کسی دوباره آن‌ها را دستی
  پرکردنی کند، `test_the_amount_columns_are_built_from_the_lines` قرمز می‌شود.
* **تاریخِ استخدام روی کارمند می‌نشیند نه قرارداد** — چون واقعیتِ شخص است و می‌تواند
  سال‌ها قبل از تاریخِ صدور باشد.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models.inventory import Contact
from app.models.payroll import Employee, PayrollFactor, SalaryContract
from app.models.tenant import Tenant
from app.tenant_context import session_tenant


def _hybrid(db) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = "hybrid"
    db.flush()


def _make_contact(client, **extra) -> dict:
    payload = {"name": "رضا کارگر", "type": "supplier", "is_employee": True, **extra}
    res = client.post("/api/contacts", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def _factors(client) -> dict[str, str]:
    """عوامل پیش‌فرض را می‌سازد و نگاشتِ کلیدِ سیستمی → شناسه می‌دهد."""
    res = client.post("/api/payroll-factors/defaults", json={})
    assert res.status_code == 200, res.text
    return {row["system_key"]: row["id"] for row in res.json() if row["system_key"]}


def _contract(client, contact_id: str, factors: dict[str, str], **extra) -> dict:
    body = {
        "contact_id": contact_id,
        "effective_from": "2026-01-01",
        "lines": [{"factor_id": factors["base"], "amount": 100000000}],
        **extra,
    }
    return client.post("/api/salary-contracts", json=body)


# ── پلِ طرف‌حساب به کارمند ────────────────────────────────────────────────────


def test_the_first_contract_creates_the_employee_from_the_contact(db, user, client):
    """**قیدِ اصلی.** یک آدم، یک رکورد — کارمند از روی طرف‌حساب ساخته می‌شود."""
    _hybrid(db)
    contact = _make_contact(client, first_name="رضا", last_name="کارگر", national_id="1111111111")
    factors = _factors(client)

    res = _contract(client, contact["id"], factors)

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["contract_type"] == "hire"
    employee = db.get(Employee, body["employee_id"])
    assert employee is not None
    assert employee.first_name == "رضا" and employee.last_name == "کارگر"
    assert employee.national_id == "1111111111"
    #: و طرف‌حساب از این پس به همان پرونده وصل است.
    assert str(db.get(Contact, contact["id"]).employee_id) == body["employee_id"]


def test_a_contact_without_the_employee_tick_is_refused(db, user, client):
    """جریان از طرف‌حساب شروع می‌شود، ولی فقط طرف‌حسابی که کارمند اعلام شده."""
    _hybrid(db)
    contact = _make_contact(client, is_employee=False)
    factors = _factors(client)

    res = _contract(client, contact["id"], factors)

    assert res.status_code == 400, res.text
    assert "کارمند" in res.json()["detail"]


def test_candidates_only_lists_contacts_with_the_employee_tick(db, user, client):
    _hybrid(db)
    _make_contact(client, name="کارمندِ ما")
    _make_contact(client, name="مشتریِ ما", type="customer", is_employee=False)

    rows = client.get("/api/payroll/employee-candidates").json()

    assert [r["name"] for r in rows] == ["کارمندِ ما"]
    assert rows[0]["employee_id"] is None, "هنوز پرونده‌ی حقوق و دستمزد ندارد"


# ── استخدام و اصلاح ──────────────────────────────────────────────────────────


def test_a_second_hire_is_refused(db, user, client):
    """«استخدام» اولین قراردادِ هر شخص است — دومی معنایی ندارد."""
    _hybrid(db)
    contact = _make_contact(client)
    factors = _factors(client)
    assert _contract(client, contact["id"], factors).status_code == 201

    res = _contract(client, contact["id"], factors, effective_from="2026-06-01")

    assert res.status_code == 409, res.text
    assert "اصلاح قرارداد" in res.json()["detail"]


def test_an_amend_without_a_hire_is_refused(db, user, client):
    """و قرینه‌اش: تا وقتی استخدام ثبت نشده، اصلاح قرارداد بی‌معناست."""
    _hybrid(db)
    contact = _make_contact(client)
    factors = _factors(client)

    res = _contract(client, contact["id"], factors, contract_type="amend")

    assert res.status_code == 400, res.text
    assert "استخدام" in res.json()["detail"]


def test_an_amend_is_accepted_after_a_hire(db, user, client):
    _hybrid(db)
    contact = _make_contact(client)
    factors = _factors(client)
    _contract(client, contact["id"], factors)

    res = _contract(client, contact["id"], factors, contract_type="amend", effective_from="2026-07-01")

    assert res.status_code == 201, res.text
    assert res.json()["contract_type"] == "amend"


def test_the_allowed_types_endpoint_follows_the_same_rule(db, user, client):
    """فرم فهرستِ نوعِ قرارداد را از سرور می‌گیرد، نه اینکه خودش حدس بزند."""
    _hybrid(db)
    contact = _make_contact(client)
    factors = _factors(client)

    before = client.get("/api/payroll/contract-types", params={"contact_id": contact["id"]}).json()
    assert before["allowed"] == ["hire"]

    _contract(client, contact["id"], factors)

    after = client.get("/api/payroll/contract-types", params={"contact_id": contact["id"]}).json()
    assert after["allowed"] == ["amend"]
    assert after["labels"]["amend"] == "اصلاح قرارداد"


# ── مبالغ از ردیف‌ها ─────────────────────────────────────────────────────────


def test_the_amount_columns_are_built_from_the_lines(db, user, client):
    """**قیدِ مهم.** یک منبعِ ویرایش: کاربر ردیف می‌نویسد، ستون‌ها ساخته می‌شوند.

    موتورِ فیشِ حقوقی روی چهار ستون حساب می‌کند و اگر ردیف‌ها و ستون‌ها از هم جدا
    بیفتند، فیش عددی می‌دهد که در قرارداد دیده نمی‌شود.
    """
    _hybrid(db)
    contact = _make_contact(client)
    factors = _factors(client)

    res = _contract(
        client, contact["id"], factors,
        lines=[
            {"factor_id": factors["base"], "amount": 100000000},
            {"factor_id": factors["housing"], "amount": 9000000},
            {"factor_id": factors["food"], "amount": 8000000},
            {"factor_id": factors["child"], "amount": 5000000},
        ],
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert Decimal(str(body["base_salary"])) == 100000000
    assert Decimal(str(body["housing_allowance"])) == 9000000
    assert Decimal(str(body["food_allowance"])) == 8000000
    #: «حق اولاد» ستونِ خودش را ندارد، پس در «سایر مزایا» می‌نشیند.
    assert Decimal(str(body["other_allowance"])) == 5000000
    assert len(body["lines"]) == 4


def test_a_user_made_factor_rolls_into_other_allowance(db, user, client):
    """عاملی که کاربر می‌سازد نباید محاسبه را بشکند — در «سایر مزایا» جمع می‌شود."""
    _hybrid(db)
    contact = _make_contact(client)
    factors = _factors(client)
    extra = client.post(
        "/api/payroll-factors", json={"name": "حق ایاب و ذهاب", "category": "benefit"}
    ).json()

    res = _contract(
        client, contact["id"], factors,
        lines=[
            {"factor_id": factors["base"], "amount": 100000000},
            {"factor_id": extra["id"], "amount": 3000000},
        ],
    )

    assert res.status_code == 201, res.text
    assert Decimal(str(res.json()["other_allowance"])) == 3000000


def test_a_deduction_never_reaches_the_pay_columns(db, user, client):
    """کسورات از حقوق کم می‌شوند؛ ریختنشان در مزایا یعنی حقوقِ ناخالصِ غلط."""
    _hybrid(db)
    contact = _make_contact(client)
    factors = _factors(client)
    loan = client.post(
        "/api/payroll-factors", json={"name": "قسط وام", "category": "deduction"}
    ).json()

    res = _contract(
        client, contact["id"], factors,
        lines=[
            {"factor_id": factors["base"], "amount": 100000000},
            {"factor_id": loan["id"], "amount": 4000000},
        ],
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert Decimal(str(body["other_allowance"])) == 0
    assert len(body["lines"]) == 2, "ردیفِ کسور ذخیره می‌شود، فقط وارد ستون‌های مزایا نمی‌شود"


def test_a_contract_without_a_base_salary_line_is_refused(db, user, client):
    _hybrid(db)
    contact = _make_contact(client)
    factors = _factors(client)

    res = _contract(
        client, contact["id"], factors,
        lines=[{"factor_id": factors["housing"], "amount": 9000000}],
    )

    assert res.status_code == 400, res.text
    assert "حقوق پایه" in res.json()["detail"]


# ── تاریخ‌ها ─────────────────────────────────────────────────────────────────


def test_hire_date_lands_on_the_employee_not_the_contract(db, user, client):
    """**قیدِ مهم.** تاریخ استخدام واقعیتِ شخص است و می‌تواند سال‌ها قبل‌تر باشد.

    شرکتی که تا دیروز با اکسل حقوق می‌داد، کارمندش را که تازه استخدام نکرده؛ تاریخِ
    صدور شروعِ محاسبه در این نرم‌افزار است، نه شروعِ کار.
    """
    _hybrid(db)
    contact = _make_contact(client)
    factors = _factors(client)

    res = _contract(client, contact["id"], factors, hire_date="2019-03-21")

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["effective_from"] == "2026-01-01"
    assert "hire_date" not in body, "تاریخ استخدام ستونِ قرارداد نیست"
    assert db.get(Employee, body["employee_id"]).hire_date == date(2019, 3, 21)


@pytest.mark.parametrize("field", ["valid_until", "service_end_date"])
def test_a_date_before_the_issue_date_is_refused(db, user, client, field):
    _hybrid(db)
    contact = _make_contact(client)
    factors = _factors(client)

    res = _contract(client, contact["id"], factors, **{field: "2025-01-01"})

    assert res.status_code == 422, res.text


def test_the_service_end_date_closes_the_employee_record(db, user, client):
    """پایانِ خدمت روی خودِ کارمند هم می‌نشیند، وگرنه در فهرستِ فعال‌ها می‌ماند."""
    _hybrid(db)
    contact = _make_contact(client)
    factors = _factors(client)

    res = _contract(client, contact["id"], factors, service_end_date="2026-12-20")

    assert res.status_code == 201, res.text
    assert db.get(Employee, res.json()["employee_id"]).termination_date == date(2026, 12, 20)


# ── جدول‌های مرجع ────────────────────────────────────────────────────────────


def test_default_factors_can_be_asked_for_twice(db, user, client):
    """ساختِ پیش‌فرض‌ها ایدمپوتنت است — در مهاجرت کاشته نمی‌شوند چون جدول RLS دارد."""
    first = client.post("/api/payroll-factors/defaults", json={}).json()
    second = client.post("/api/payroll-factors/defaults", json={}).json()

    assert len(first) == len(second) == 4
    assert {row["system_key"] for row in second} == {"base", "housing", "food", "child"}
    assert db.query(PayrollFactor).count() == 4


def test_a_service_location_needs_a_code_and_a_name(db, user, client):
    assert client.post("/api/service-locations", json={"code": "", "name": "انبار"}).status_code == 422
    assert client.post("/api/service-locations", json={"code": "01", "name": ""}).status_code == 422
    assert client.post("/api/service-locations", json={"code": "01", "name": "انبار"}).status_code == 201


def test_an_unknown_job_family_is_refused(db, user, client):
    ok = client.post(
        "/api/job-titles", json={"code": "10", "name": "انباردار", "job_family": "انبارداری"}
    )
    bad = client.post(
        "/api/job-titles", json={"code": "11", "name": "فضانورد", "job_family": "چیزی که نیست"}
    )

    assert ok.status_code == 201, ok.text
    assert bad.status_code == 422


def test_a_tax_group_takes_the_default_percent_of_its_kind(db, user, client):
    """درصدِ خالی یعنی پیش‌فرضِ همان نوع — محروم نصف، معاف صفر."""
    rows = {
        kind: client.post("/api/payroll-tax-groups", json={"name": f"گروه {kind}", "kind": kind}).json()
        for kind in ("normal", "deprived", "exempt")
    }

    assert Decimal(str(rows["normal"]["percent"])) == 100
    assert Decimal(str(rows["deprived"]["percent"])) == 50
    assert Decimal(str(rows["exempt"]["percent"])) == 0


def test_the_reference_tables_reach_the_contract(db, user, client):
    """محل خدمت، شغل و مرکز هزینه روی قرارداد می‌نشینند و در فهرست دیده می‌شوند."""
    _hybrid(db)
    contact = _make_contact(client)
    factors = _factors(client)
    location = client.post("/api/service-locations", json={"code": "01", "name": "انبار"}).json()
    job = client.post("/api/job-titles", json={"code": "10", "name": "انباردار"}).json()

    res = _contract(
        client, contact["id"], factors,
        service_location_id=location["id"], job_title_id=job["id"], employment_type="قراردادی",
    )

    assert res.status_code == 201, res.text
    listed = client.get("/api/salary-contracts").json()
    assert listed[0]["service_location_id"] == location["id"]
    assert listed[0]["job_title_id"] == job["id"]
    assert listed[0]["employment_type"] == "قراردادی"
    assert listed[0]["employee_name"], "فهرست باید نام کارمند را نشان دهد نه فقط شناسه"


def test_an_unknown_employment_type_is_refused(db, user, client):
    _hybrid(db)
    contact = _make_contact(client)
    factors = _factors(client)

    res = _contract(client, contact["id"], factors, employment_type="خیالی")

    assert res.status_code == 422, res.text


def test_the_old_column_based_contract_still_works(db, user, client):
    """قراردادهای بی‌ردیف — راهِ قدیمی — نباید بشکنند."""
    employee = Employee(
        first_name="سارا", last_name="محمدی", national_id="2222222222", hire_date=date(2025, 1, 1)
    )
    db.add(employee)
    db.flush()

    res = client.post(
        "/api/salary-contracts",
        json={
            "employee_id": str(employee.id),
            "effective_from": "2026-01-01",
            "base_salary": 90000000,
        },
    )

    assert res.status_code == 201, res.text
    assert Decimal(str(res.json()["base_salary"])) == 90000000
    assert db.query(SalaryContract).count() == 1
