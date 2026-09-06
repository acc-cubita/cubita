"""مالیاتِ تجمیعی، گروهِ مالیاتی، و کسورِ فیش.

سه چیزی که تا امروز **ذخیره می‌شد و هیچ اثری نداشت** و این تست‌ها نگهشان می‌دارند:

* **اطلاعاتِ استقرار** — پرداختیِ ماه‌های پیش از آمدن به کوبیتا باید در پلکانِ
  مالیات دیده شود، وگرنه مالیات کمتر از واقع کسر می‌شود.
* **گروهِ مالیاتی** — «مناطق محروم ۵۰٪» باید واقعاً نصف کند، نه اینکه برچسب بماند.
* **ردیف‌های کسوراتِ قرارداد** — تا امروز `payroll_contracts` هر عاملِ غیرِ `benefit`
  را بی‌صدا رد می‌کرد.

و یک قیدِ ساختاری: **فیش باید جمع بزند.**
"""
from decimal import Decimal

import pytest

from app.models.payroll import PayrollSettings, PayrollTaxGroup
from app.models.tenant import Tenant
from app.services.payroll import calc_annual_tax, calc_cumulative_monthly_tax, calc_monthly_tax
from app.tenant_context import session_tenant

BRACKETS = [{"up_to": 2_000_000_000, "rate": 0.1}, {"up_to": None, "rate": 0.2}]
EXEMPTION = Decimal("1200000000")


def _hybrid(db) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = "hybrid"
    db.flush()


def _employee(client, national_id="1111111111") -> dict:
    res = client.post(
        "/api/employees",
        json={
            "first_name": "رضا",
            "last_name": "کارگر",
            "national_id": national_id,
            "hire_date": "2025-01-01",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _settings(db, year: int) -> None:
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


def _factors(client) -> dict[str, str]:
    rows = client.post("/api/payroll-factors/defaults", json={}).json()
    return {r["system_key"]: r["id"] for r in rows if r["system_key"]}


def _contract(client, employee_id: str, base: int, **extra) -> dict:
    factors = _factors(client)
    body = {
        "employee_id": employee_id,
        "effective_from": "2026-01-01",
        "lines": [{"factor_id": factors["base"], "amount": base}],
        **extra,
    }
    res = client.post("/api/salary-contracts", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _run(client, year: int, month: int) -> list[dict]:
    period = client.post("/api/payroll-periods", json={"year": year, "month": month}).json()
    res = client.post(f"/api/payroll-periods/{period['id']}/generate-payslips", json={})
    assert res.status_code == 200, res.text
    return res.json()


# ── تابعِ محاسبه ──────────────────────────────────────────────────────────────


def test_the_cumulative_method_matches_the_old_one_on_a_level_salary(db):
    """**قیدِ سازگاری.** حقوقِ یکنواخت و بی‌سابقه باید همان عددِ قبلی را بدهد.

    اگر این بشکند یعنی روشِ تازه رفتارِ همه‌ی فیش‌های موجود را عوض کرده — که هدف
    نبود؛ هدف فقط دیده‌شدنِ درآمدِ ناهموار و سابقه‌ی استقرار بود.
    """
    monthly = Decimal("500000000")
    old = calc_monthly_tax(monthly, EXEMPTION, BRACKETS)

    #: شبیه‌سازیِ یک سالِ کامل، همان‌طور که موتور اجرا می‌کند: خروجیِ هر ماه ورودیِ
    #: ماهِ بعد می‌شود.
    paid = Decimal(0)
    for month in range(1, 13):
        tax = calc_cumulative_monthly_tax(
            monthly_taxable=monthly,
            prior_taxable=monthly * (month - 1),
            prior_tax=paid,
            month_index=month,
            annual_exemption=EXEMPTION,
            brackets=BRACKETS,
        )
        #: هر ماه در عملْ همان عددِ قبلی است؛ اختلافِ چندریالی از گِردکردن می‌آید.
        assert abs(tax - old) <= 12, f"ماهِ {month}: {tax} در برابر {old}"
        paid += tax

    #: و **خاصیتِ اصلیِ روشِ تجمیعی**: جمعِ دوازده ماه دقیقاً برابرِ مالیاتِ سالانه
    #: است. روشِ قدیمی این را تضمین نمی‌کرد و خطای گِردکردن تا ۱۲ ریال جمع می‌شد.
    annual = calc_annual_tax(max(Decimal(0), monthly * 12 - EXEMPTION), BRACKETS)
    assert paid == annual, f"جمعِ سال {paid} با مالیاتِ سالانه‌ی {annual} نمی‌خواند"


@pytest.mark.parametrize(
    "percent,divisor,why",
    [
        (Decimal(100), 1, "مناطق عادی — کاملِ مالیات"),
        (Decimal(50), 2, "مناطق محروم — نصف"),
        (Decimal(0), None, "معاف — صفر"),
    ],
)
def test_the_tax_group_percent_scales_the_tax(db, percent, divisor, why):
    """درصدِ گروهِ مالیاتی واقعاً ضرب می‌شود، نه اینکه برچسب بماند."""
    monthly = Decimal("500000000")
    full = calc_cumulative_monthly_tax(
        monthly_taxable=monthly, prior_taxable=Decimal(0), prior_tax=Decimal(0),
        month_index=1, annual_exemption=EXEMPTION, brackets=BRACKETS,
    )

    scaled = calc_cumulative_monthly_tax(
        monthly_taxable=monthly, prior_taxable=Decimal(0), prior_tax=Decimal(0),
        month_index=1, annual_exemption=EXEMPTION, brackets=BRACKETS, tax_percent=percent,
    )

    #: یک ریال تلورانس، چون نتیجه گِرد می‌شود و نصفِ یک عددِ فرد اعشار دارد.
    expected = Decimal(0) if divisor is None else full / divisor
    assert abs(scaled - expected) <= 1, why


def test_the_month_tax_is_never_negative(db):
    """ماهِ کم‌درآمد مالیات را مسترد نمی‌کند — آن کارِ تعدیلِ پایانِ سال است."""
    result = calc_cumulative_monthly_tax(
        monthly_taxable=Decimal(0),
        prior_taxable=Decimal("5000000000"),
        prior_tax=Decimal("900000000"),
        month_index=6,
        annual_exemption=EXEMPTION,
        brackets=BRACKETS,
    )

    assert result == Decimal(0)


# ── اثرِ اطلاعاتِ استقرار ─────────────────────────────────────────────────────


def test_deployment_history_pushes_the_tax_into_the_higher_bracket(db, user, client):
    """**قیدِ اصلی.** شرکتی که وسطِ سال می‌آید نباید پلکان را از صفر شروع کند.

    دو کارمندِ با حقوقِ یکسان: یکی سابقه‌ی استقرار دارد، دیگری نه. آنکه سابقه دارد
    باید مالیاتِ بیشتری بدهد، چون درآمدِ واقعی‌اش امسال بیشتر بوده.
    """
    _hybrid(db)
    _settings(db, 1405)
    plain = _employee(client, "1111111111")
    with_history = _employee(client, "2222222222")
    _contract(client, plain["id"], 300_000_000)
    _contract(client, with_history["id"], 300_000_000)

    res = client.put(
        "/api/payroll-deployment",
        json={
            "employee_id": with_history["id"],
            "year": 1405,
            "cumulative_gross": 4_000_000_000,
            "cumulative_insurance": 280_000_000,
            "cumulative_tax": 0,
        },
    )
    assert res.status_code == 200, res.text

    slips = {s["employee_id"]: s for s in _run(client, 1405, 7)}

    plain_tax = Decimal(str(slips[plain["id"]]["tax_amount"]))
    history_tax = Decimal(str(slips[with_history["id"]]["tax_amount"]))
    assert history_tax > plain_tax, (
        "کارمندی که سابقه‌ی استقرار دارد باید مالیاتِ بیشتری بدهد؛ "
        f"بی‌سابقه={plain_tax} با سابقه={history_tax}"
    )


def test_without_deployment_info_nothing_changes(db, user, client):
    """قرینه‌اش: نبودِ سابقه نباید چیزی را عوض کند."""
    _hybrid(db)
    _settings(db, 1405)
    employee = _employee(client)
    _contract(client, employee["id"], 300_000_000)

    slip = _run(client, 1405, 1)[0]

    taxable = Decimal(str(slip["taxable_pay"]))
    assert Decimal(str(slip["tax_amount"])) == calc_monthly_tax(taxable, EXEMPTION, BRACKETS)


# ── گروهِ مالیاتی روی قرارداد ─────────────────────────────────────────────────


def test_a_deprived_area_contract_pays_half(db, user, client):
    """گروهِ مالیاتیِ قرارداد به فیش می‌رسد."""
    _hybrid(db)
    _settings(db, 1405)
    normal = _employee(client, "1111111111")
    deprived = _employee(client, "2222222222")

    group = PayrollTaxGroup(name="مناطق محروم", kind="deprived", percent=Decimal(50))
    db.add(group)
    db.flush()

    _contract(client, normal["id"], 300_000_000)
    _contract(client, deprived["id"], 300_000_000, tax_group_id=str(group.id))

    slips = {s["employee_id"]: s for s in _run(client, 1405, 1)}

    full = Decimal(str(slips[normal["id"]]["tax_amount"]))
    half = Decimal(str(slips[deprived["id"]]["tax_amount"]))
    assert full > 0, "برای آزمون باید مالیاتی وجود داشته باشد"
    assert abs(half - full / 2) <= 1, f"نصف نشد: {half} در برابر {full / 2}"


# ── کسورِ قرارداد و تساویِ فیش ────────────────────────────────────────────────


def test_a_contract_deduction_line_actually_reduces_the_net(db, user, client):
    """**ایرادِ قدیمی.** ردیف‌های کسورات تا امروز بی‌صدا نادیده گرفته می‌شدند."""
    _hybrid(db)
    _settings(db, 1405)
    employee = _employee(client)
    factors = _factors(client)
    supplementary = client.post(
        "/api/payroll-factors",
        json={"name": "بیمه تکمیلی", "category": "deduction", "kind": "fixed"},
    ).json()

    res = client.post(
        "/api/salary-contracts",
        json={
            "employee_id": employee["id"],
            "effective_from": "2026-01-01",
            "lines": [
                {"factor_id": factors["base"], "amount": 300_000_000},
                {"factor_id": supplementary["id"], "amount": 5_000_000},
            ],
        },
    )
    assert res.status_code == 201, res.text

    slip = _run(client, 1405, 1)[0]

    assert Decimal(str(slip["other_deductions"])) == Decimal("5000000")
    #: و مبنای بیمه و مالیات را تکان نداده — کسورِ اختیاری از خالص کم می‌شود.
    assert Decimal(str(slip["gross_pay"])) == Decimal("300000000")


def test_the_payslip_always_adds_up(db, user, client):
    """**قیدِ ساختاری.** خالص = ناخالص − بیمه − مالیات − قسطِ وام − سایر کسورات.

    پیش از افزودنِ این دو ستون، کسرِ وام خالص را کم می‌کرد ولی هیچ‌جا دیده نمی‌شد و
    فیشِ چاپی جمع نمی‌زد.
    """
    _hybrid(db)
    _settings(db, 1405)
    employee = _employee(client)
    factors = _factors(client)
    supplementary = client.post(
        "/api/payroll-factors",
        json={"name": "بیمه تکمیلی", "category": "deduction", "kind": "fixed"},
    ).json()
    client.post(
        "/api/salary-contracts",
        json={
            "employee_id": employee["id"],
            "effective_from": "2026-01-01",
            "lines": [
                {"factor_id": factors["base"], "amount": 300_000_000},
                {"factor_id": supplementary["id"], "amount": 5_000_000},
            ],
        },
    )
    client.post(
        "/api/employee-loans",
        json={
            "employee_id": employee["id"],
            "amount": 12_000_000,
            "loan_date": "2026-01-01",
            "installment_count": 2,
            "first_due_date": "2026-01-05",
        },
    )

    slip = _run(client, 1405, 1)[0]

    keys = (
        "gross_pay", "insurance_employee_share", "tax_amount",
        "loan_deduction", "other_deductions", "net_pay",
    )
    d = {k: Decimal(str(slip[k])) for k in keys}
    assert d["loan_deduction"] > 0, "قسطِ سررسیدشده باید کسر شده باشد"
    assert d["net_pay"] == (
        d["gross_pay"] - d["insurance_employee_share"] - d["tax_amount"]
        - d["loan_deduction"] - d["other_deductions"]
    )
