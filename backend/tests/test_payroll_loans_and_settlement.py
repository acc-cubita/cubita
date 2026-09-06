"""وامِ پرسنلی، تسویه حساب، و اطلاعاتِ استقرار.

قیدهایی که این‌ها نگه می‌دارند و جای دیگری نگهبان ندارند:

* **جمعِ اقساط دقیقاً برابرِ مبلغِ وام است** — باقی‌مانده روی قسطِ آخر می‌نشیند، نه
  گم می‌شود نه اضافه می‌آید.
* **هیچ قسطی دوبار کسر نمی‌شود** و ابطالِ دوره اقساطش را آزاد می‌کند.
* **بازپرداختِ وام از خالص کم می‌شود، نه از ناخالص** — مبنای بیمه و مالیات را
  تکان نمی‌دهد و سندِ حقوق همچنان متوازن است.
* **تسویه‌حساب مانده‌ی وام را از خودِ اقساط می‌خواند**، نه از عددی که کاربر تایپ کند.
"""
from datetime import date
from decimal import Decimal

from app.models.payroll import (
    EmployeeLoan,
    EmployeeLoanInstallment,
    PayrollSettings,
)
from app.models.tenant import Tenant
from app.services import payroll_loans
from app.tenant_context import session_tenant


def _hybrid(db) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = "hybrid"
    db.flush()


def _employee(client) -> dict:
    res = client.post(
        "/api/employees",
        json={
            "first_name": "رضا",
            "last_name": "کارگر",
            "national_id": "1111111111",
            "hire_date": "2025-01-01",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _loan(client, employee_id: str, **extra) -> dict:
    body = {
        "employee_id": employee_id,
        "amount": 30000001,
        "loan_date": "2026-01-01",
        "installment_count": 3,
        **extra,
    }
    res = client.post("/api/employee-loans", json=body)
    assert res.status_code == 201, res.text
    return res.json()


# ── زمان‌بندیِ اقساط ──────────────────────────────────────────────────────────


def test_the_installments_add_up_to_the_loan_exactly(db, user, client):
    """**قیدِ اصلی.** باقی‌مانده‌ی تقسیم روی قسطِ آخر می‌نشیند، نه اینکه گم شود.

    ۳۰٬۰۰۰٬۰۰۱ در سه قسط: دو قسطِ ۱۰٬۰۰۰٬۰۰۰ و یک قسطِ ۱۰٬۰۰۰٬۰۰۱ — نه سه قسطِ
    مساوی که جمعشان یک ریال کم بیاورد.
    """
    _hybrid(db)
    employee = _employee(client)

    loan = _loan(client, employee["id"])

    amounts = [Decimal(str(i["amount"])) for i in loan["installments"]]
    assert len(amounts) == 3
    assert sum(amounts) == Decimal("30000001")
    assert amounts[-1] > amounts[0], "باقی‌مانده باید روی قسطِ آخر باشد"


def test_the_due_dates_walk_month_by_month(db, user, client):
    """سررسیدها ماه‌به‌ماه جلو می‌روند و روزِ ماه ثابت می‌ماند."""
    _hybrid(db)
    employee = _employee(client)

    loan = _loan(client, employee["id"], first_due_date="2026-01-31", installment_count=3)

    dues = [i["due_date"] for i in loan["installments"]]
    #: ۳۱ فروردینِ میلادی در فوریه وجود ندارد؛ باید به آخرِ همان ماه بیفتد نه به مارس.
    assert dues == ["2026-01-31", "2026-02-28", "2026-03-31"]


def test_the_balance_is_derived_from_the_installments(db, user, client):
    """مانده ستون نیست، جمعِ اقساطِ کسرنشده است — پس هیچ‌وقت با آن‌ها اختلاف ندارد."""
    _hybrid(db)
    employee = _employee(client)
    loan = _loan(client, employee["id"])

    assert Decimal(str(loan["balance"])) == Decimal("30000001")

    #: یک قسط را دستی کسرشده علامت می‌زنیم و مانده باید خودش کم شود.
    first = db.query(EmployeeLoanInstallment).order_by(EmployeeLoanInstallment.seq).first()
    period = client.post("/api/payroll-periods", json={"year": 1405, "month": 1}).json()
    first.deducted_period_id = period["id"]
    db.flush()

    rows = client.get("/api/employee-loans").json()
    assert Decimal(str(rows[0]["balance"])) == Decimal("30000001") - Decimal(str(first.amount))


# ── کسر در دوره‌ی حقوقی ───────────────────────────────────────────────────────


def _settings(db, year: int) -> None:
    db.add(
        PayrollSettings(
            year=year,
            insurance_employee_rate=Decimal("0.07"),
            insurance_employer_rate=Decimal("0.23"),
            tax_exemption_annual=Decimal("1200000000"),
            tax_brackets=[{"up_to": None, "rate": 0.1}],
        )
    )
    db.flush()


def _contract_for(client, employee_id: str) -> None:
    factors = client.post("/api/payroll-factors/defaults", json={}).json()
    base = next(f["id"] for f in factors if f["system_key"] == "base")
    res = client.post(
        "/api/salary-contracts",
        json={
            "employee_id": employee_id,
            "effective_from": "2026-01-01",
            "lines": [{"factor_id": base, "amount": 500000000}],
        },
    )
    assert res.status_code == 201, res.text


def test_a_due_installment_is_deducted_from_net_pay_not_gross(db, user, client):
    """**قیدِ اصلی.** بازپرداختِ وام مبنای بیمه و مالیات را تکان نمی‌دهد.

    وام هزینه‌ی کارفرما نیست؛ فقط بخشی از همان خالص به‌جای جیبِ کارمند بدهیِ وامش را
    می‌بندد. اگر روزی از ناخالص کم شود، بیمه و مالیات کمتر از واقع محاسبه می‌شوند.
    """
    _hybrid(db)
    employee = _employee(client)
    _contract_for(client, employee["id"])
    _settings(db, 1405)
    _loan(client, employee["id"], installment_count=1, amount=5000000, first_due_date="2026-01-01")

    period = client.post("/api/payroll-periods", json={"year": 1405, "month": 1}).json()
    res = client.post(f"/api/payroll-periods/{period['id']}/generate-payslips", json={})

    assert res.status_code == 200, res.text
    slip = res.json()[0]
    #: ناخالص و مالیات از حکم می‌آیند؛ وام فقط خالص را کم کرده.
    expected_net = (
        Decimal(str(slip["gross_pay"]))
        - Decimal(str(slip["insurance_employee_share"]))
        - Decimal(str(slip["tax_amount"]))
        - Decimal("5000000")
    )
    assert Decimal(str(slip["net_pay"])) == expected_net


def test_an_installment_is_never_deducted_twice(db, user, client):
    """قسطی که کسر شد، در دوره‌ی بعد دوباره سررسید نمی‌شود."""
    _hybrid(db)
    employee = _employee(client)
    _loan(client, employee["id"], installment_count=1, amount=5000000, first_due_date="2026-01-01")

    from app.models.payroll import PayrollPeriod

    client.post("/api/payroll-periods", json={"year": 1405, "month": 1})
    period = db.query(PayrollPeriod).one()

    first = payroll_loans.deduct_for_period(db, employee["id"], period)
    second = payroll_loans.deduct_for_period(db, employee["id"], period)

    assert first == Decimal("5000000")
    assert second == Decimal(0), "بارِ دوم چیزی برای کسر نمانده"


def test_releasing_a_period_frees_its_installments(db, user, client):
    """ابطالِ دوره اقساطش را آزاد می‌کند و وامِ تسویه‌شده دوباره فعال می‌شود."""
    _hybrid(db)
    employee = _employee(client)
    _loan(client, employee["id"], installment_count=1, amount=5000000, first_due_date="2026-01-01")

    from app.models.payroll import PayrollPeriod

    client.post("/api/payroll-periods", json={"year": 1405, "month": 1})
    period = db.query(PayrollPeriod).one()
    payroll_loans.deduct_for_period(db, employee["id"], period)
    assert db.query(EmployeeLoan).one().status == "settled"

    freed = payroll_loans.release_period(db, period.id)

    assert freed == 1
    assert db.query(EmployeeLoan).one().status == "active", "وام باید دوباره فعال شود"
    assert payroll_loans.employee_loan_balance(db, employee["id"]) == Decimal("5000000")


def test_a_cancelled_loan_stops_being_deducted(db, user, client):
    """لغوِ وام اقساطِ کسرشده را دست نمی‌زند، فقط دیگر قسطی سررسید نمی‌شود."""
    _hybrid(db)
    employee = _employee(client)
    loan = _loan(client, employee["id"], installment_count=2, amount=6000000, first_due_date="2026-01-01")

    res = client.post(f"/api/employee-loans/{loan['id']}/cancel")

    assert res.status_code == 200, res.text
    assert res.json()["status"] == "cancelled"
    assert payroll_loans.employee_loan_balance(db, employee["id"]) == Decimal(0)


# ── تسویه حساب ───────────────────────────────────────────────────────────────


def test_the_settlement_reads_the_loan_balance_from_the_installments(db, user, client):
    """**قیدِ اصلی.** بدهیِ وام از اقساطِ واقعی می‌آید، نه از عددی که کاربر تایپ کند."""
    _hybrid(db)
    employee = _employee(client)
    _loan(client, employee["id"], installment_count=2, amount=6000000)

    res = client.post(
        "/api/payroll-settlements",
        json={
            "employee_id": employee["id"],
            "settlement_date": "2026-06-01",
            "severance_amount": 20000000,
            "leave_payout_amount": 5000000,
        },
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert Decimal(str(body["loan_balance"])) == Decimal("6000000")
    assert Decimal(str(body["net_amount"])) == Decimal("19000000")


def test_a_second_settlement_for_the_same_employee_is_refused(db, user, client):
    """یک تسویه‌ی نهایی برای هر کارمند — دو خالصِ متفاوت در سابقه نمی‌ماند."""
    _hybrid(db)
    employee = _employee(client)
    payload = {"employee_id": employee["id"], "settlement_date": "2026-06-01"}
    assert client.post("/api/payroll-settlements", json=payload).status_code == 201

    res = client.post("/api/payroll-settlements", json=payload)

    assert res.status_code == 409, res.text
    assert "تسویه‌حساب" in res.json()["detail"]


# ── اطلاعاتِ استقرار ──────────────────────────────────────────────────────────


def test_deployment_info_is_one_row_per_employee_and_year(db, user, client):
    """`PUT` دوباره ویرایش است نه ردیفِ دوم — دو وضعیت برای یک سال بی‌معناست."""
    _hybrid(db)
    employee = _employee(client)
    body = {
        "employee_id": employee["id"],
        "year": 1405,
        "cumulative_gross": 400000000,
        "cumulative_tax": 12000000,
        "leave_balance_days": "7.5",
        "prior_service_days": 3650,
    }

    first = client.put("/api/payroll-deployment", json=body)
    second = client.put("/api/payroll-deployment", json={**body, "cumulative_gross": 500000000})

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"], "همان ردیف باید به‌روز شود"
    rows = client.get("/api/payroll-deployment").json()
    assert len(rows) == 1
    assert Decimal(str(rows[0]["cumulative_gross"])) == Decimal("500000000")
    assert Decimal(str(rows[0]["leave_balance_days"])) == Decimal("7.5")


def test_deployment_info_refuses_negative_carry_over(db, user, client):
    """مانده‌ی منفیِ استقرار یعنی داده‌ی غلط، نه حالتِ خاص."""
    _hybrid(db)
    employee = _employee(client)

    res = client.put(
        "/api/payroll-deployment",
        json={"employee_id": employee["id"], "year": 1405, "cumulative_gross": -1},
    )

    assert res.status_code == 422, res.text
