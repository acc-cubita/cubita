"""تنظیماتِ حقوق: پارامترهای قانونی، و مشارکتِ عامل‌ها در مبناها.

سه خانواده‌ی ادعا این‌جا قفل می‌شوند:

* **پارامترهای قانونی دیگر در سورس‌کد نیستند** (مهاجرتِ ۰۱۳۸) — و پیش‌فرضِ هر
  کدام همان ثابتی است که جایش را گرفته، پس هیچ عددی با مهاجرت عوض نشد.
* **مشارکتِ عامل به‌ازای هر هدف فرق می‌کند** (مهاجرتِ ۰۱۳۹) — «مشمولِ بیمه» یک
  پرچمِ واحد نیست، و جدولِ خالی یعنی رفتارِ دیروز.
* **سندِ حقوق متوازن است.** یک باگِ از پیش موجود: ردیف‌های کسوراتِ قرارداد خالص
  را کم می‌کردند ولی هیچ ردیفِ بستانکاری نداشتند، پس سند دقیقاً به همان اندازه
  نامتوازن ثبت می‌شد و تراز آزمایشی بی‌صدا به‌هم می‌خورد.

**سالِ یکتا برای هر تست.** تست‌های کلاینت کامیت می‌کنند و
`payroll_settings (tenant, year)` یکتاست؛ سالِ ثابت یعنی تصادمِ بین تست‌ها.
"""
from decimal import Decimal
from itertools import count

import pytest

from app.models.accounting import JournalEntry, JournalLine
from app.models.payroll import PayrollFactorParticipation, PayrollSettings
from app.models.tenant import Tenant
from app.tenant_context import session_tenant

#: سالِ شمسیِ دور از امروز، تا حکمِ نمونه (اجرا از ۲۰۲۱) پیش از دوره بیفتد
#: و هر تست سالِ خودش را داشته باشد — `payroll_settings` روی سال یکتاست.
_YEARS = count(1500)
_IDS = count(7000000000)

BRACKETS = [{"up_to": 2_000_000_000, "rate": 0.1}, {"up_to": None, "rate": 0.2}]
EXEMPTION = 1_200_000_000
BASE = 300_000_000


def _year() -> int:
    return next(_YEARS)


def _national_id() -> str:
    return str(next(_IDS))


def _hybrid(db) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = "hybrid"
    db.flush()


def _settings(client, year: int, **overrides) -> dict:
    body = {
        "year": year,
        "insurance_employee_rate": 0.07,
        "insurance_employer_rate": 0.23,
        "tax_exemption_annual": EXEMPTION,
        "tax_brackets": [{"up_to": b["up_to"], "rate": b["rate"]} for b in BRACKETS],
        "min_base_wage": 0,
        "annual_leave_days": 26,
        "notes": "",
        **overrides,
    }
    res = client.put("/api/payroll-settings", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def _employee(client) -> dict:
    res = client.post(
        "/api/employees",
        json={
            "first_name": "رضا",
            "last_name": "کارگر",
            "national_id": _national_id(),
            "hire_date": "2020-01-01",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _factors(client) -> dict[str, str]:
    rows = client.post("/api/payroll-factors/defaults", json={}).json()
    return {r["system_key"]: r["id"] for r in rows if r["system_key"]}


def _factor(client, name: str, category: str = "deduction") -> dict:
    res = client.post("/api/payroll-factors", json={"name": name, "category": category, "kind": "fixed"})
    assert res.status_code == 201, res.text
    return res.json()


def _contract(client, employee_id: str, lines: list[dict]) -> dict:
    res = client.post(
        "/api/salary-contracts",
        json={"employee_id": employee_id, "effective_from": "2021-01-01", "lines": lines},
    )
    assert res.status_code == 201, res.text
    return res.json()


def _run(client, year: int, month: int = 1) -> list[dict]:
    period = client.post("/api/payroll-periods", json={"year": year, "month": month}).json()
    res = client.post(f"/api/payroll-periods/{period['id']}/generate-payslips", json={})
    assert res.status_code == 200, res.text
    return res.json()


def _simple_run(client, db, **settings_overrides) -> dict:
    """یک کارمند، یک حکمِ فقط‌پایه، یک فیش. کوتاه‌ترین مسیر تا یک عدد."""
    _hybrid(db)
    year = _year()
    _settings(client, year, **settings_overrides)
    employee = _employee(client)
    _contract(client, employee["id"], [{"factor_id": _factors(client)["base"], "amount": BASE}])
    return _run(client, year)[0]


def _entry_totals(db, slip: dict) -> tuple[Decimal, Decimal]:
    entry = db.get(JournalEntry, slip["journal_entry_id"])
    lines = db.query(JournalLine).filter(JournalLine.entry_id == entry.id).all()
    return (
        sum((Decimal(str(x.debit)) for x in lines), Decimal(0)),
        sum((Decimal(str(x.credit)) for x in lines), Decimal(0)),
    )


def _d(slip: dict, field: str) -> Decimal:
    return Decimal(str(slip[field]))


# ── باگِ توازن ───────────────────────────────────────────────────────────────


def test_a_contract_deduction_no_longer_unbalances_the_journal(db, user, client):
    """**باگِ از پیش موجود.** ردیفِ کسور خالص را کم می‌کرد و هیچ‌جا بستانکار نمی‌شد.

    با پروب اندازه گرفته شد: بدهکار ۳۶۹٬۰۰۰٬۰۰۰ در برابر بستانکار ۳۶۴٬۰۰۰٬۰۰۰ —
    اختلاف دقیقاً همان ۵٬۰۰۰٬۰۰۰ِ کسور. سند بی هیچ خطایی ثبت می‌شد.
    """
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    supplementary = _factor(client, f"بیمه تکمیلی {year}")
    _contract(
        client,
        employee["id"],
        [
            {"factor_id": _factors(client)["base"], "amount": BASE},
            {"factor_id": supplementary["id"], "amount": 5_000_000},
        ],
    )

    slip = _run(client, year)[0]
    assert _d(slip, "other_deductions") == Decimal(5_000_000)

    debit, credit = _entry_totals(db, slip)
    assert debit == credit, f"سند نامتوازن است: بدهکار {debit} در برابر بستانکار {credit}"


def test_the_plain_payroll_journal_still_balances(db, user, client):
    """گاردِ نظیر — بی هیچ کسوری هم باید متوازن بماند."""
    slip = _simple_run(client, db)
    debit, credit = _entry_totals(db, slip)
    assert debit == credit


# ── سقفِ بیمه ────────────────────────────────────────────────────────────────


def test_zero_ceiling_means_no_ceiling(db, user, client):
    """پیش‌فرضِ صفر = رفتارِ پیش از مهاجرت: نرخ روی کلِ ناخالص."""
    slip = _simple_run(client, db)
    assert _d(slip, "insurance_employee_share") == Decimal(BASE) * Decimal("0.07")


def test_a_daily_ceiling_caps_the_insurable_wage(db, user, client):
    """سقفِ روزانه × روزهای ماه، سقفِ ماهانه است و بیمه از آن بالاتر نمی‌رود."""
    slip = _simple_run(client, db, insurance_daily_ceiling=1_000_000)  # ماهانه ۳۰٬۰۰۰٬۰۰۰
    assert _d(slip, "gross_pay") == Decimal(BASE), "سقف نباید ناخالص را تکان بدهد"
    assert _d(slip, "insurance_employee_share") == Decimal(30_000_000) * Decimal("0.07")


def test_a_ceiling_above_the_wage_changes_nothing(db, user, client):
    """سقفی که از دستمزد بالاتر است نباید عددی را عوض کند."""
    slip = _simple_run(client, db, insurance_daily_ceiling=100_000_000)
    assert _d(slip, "insurance_employee_share") == Decimal(BASE) * Decimal("0.07")


def test_the_ceiling_prorates_with_worked_days(db, user, client):
    """نصفِ ماه کار، نصفِ سقف — وگرنه سقف برای کارکردِ ناقص بی‌اثر می‌شد."""
    _hybrid(db)
    year = _year()
    _settings(client, year, insurance_daily_ceiling=1_000_000)
    employee = _employee(client)
    _contract(client, employee["id"], [{"factor_id": _factors(client)["base"], "amount": BASE}])
    period = client.post("/api/payroll-periods", json={"year": year, "month": 1}).json()
    client.put(
        "/api/attendance",
        json={"employee_id": employee["id"], "period_id": period["id"], "worked_days": 15,
              "absent_days": 15, "overtime_hours": 0},
    )
    slip = client.post(f"/api/payroll-periods/{period['id']}/generate-payslips", json={}).json()[0]
    #: ناخالص نصف شده (۱۵۰٬۰۰۰٬۰۰۰) و سقفِ ماهانه هم نصف (۱۵٬۰۰۰٬۰۰۰).
    assert _d(slip, "insurance_employee_share") == Decimal(15_000_000) * Decimal("0.07")


# ── بیمه‌ی بیکاری و مشاغل سخت ────────────────────────────────────────────────


def test_unemployment_rate_adds_to_the_employer_share_only(db, user, client):
    slip = _simple_run(client, db, unemployment_rate=0.03)
    assert _d(slip, "insurance_employer_share") == Decimal(BASE) * Decimal("0.26")
    assert _d(slip, "insurance_employee_share") == Decimal(BASE) * Decimal("0.07")


def test_hard_job_rate_is_stored_but_not_applied(db, user, client):
    """**عمداً اعمال نمی‌شود.** شمولِ مشاغل سخت به کارمند وابسته است و کوبیتا
    هنوز جایی برای آن پرچم ندارد؛ اعمالش روی همه یعنی کسر از کسانی که مشمول
    نیستند. نرخ ذخیره می‌شود تا وقتی آن پرچم آمد، عدد سرِ جایش باشد.
    """
    _hybrid(db)
    year = _year()
    saved = _settings(client, year, hard_job_rate=0.04)
    assert Decimal(str(saved["hard_job_rate"])) == Decimal("0.04")
    employee = _employee(client)
    _contract(client, employee["id"], [{"factor_id": _factors(client)["base"], "amount": BASE}])
    slip = _run(client, year)[0]
    assert _d(slip, "insurance_employer_share") == Decimal(BASE) * Decimal("0.23")


# ── اضافه‌کار و مبنای روزِ کاری ───────────────────────────────────────────────


def test_overtime_multiplier_and_monthly_hours_come_from_settings(db, user, client):
    _hybrid(db)
    year = _year()
    _settings(client, year, standard_monthly_hours=200, overtime_multiplier=2)
    employee = _employee(client)
    _contract(client, employee["id"], [{"factor_id": _factors(client)["base"], "amount": BASE}])
    period = client.post("/api/payroll-periods", json={"year": year, "month": 1}).json()
    client.put(
        "/api/attendance",
        json={"employee_id": employee["id"], "period_id": period["id"], "worked_days": 30,
              "absent_days": 0, "overtime_hours": 10},
    )
    slip = client.post(f"/api/payroll-periods/{period['id']}/generate-payslips", json={}).json()[0]
    #: ۳۰۰٬۰۰۰٬۰۰۰ ÷ ۲۰۰ × ۲ × ۱۰ = ۳۰٬۰۰۰٬۰۰۰ (با ۱۹۴ و ۱٫۴ می‌شد ۲۱٬۶۴۹٬۴۸۵)
    assert _d(slip, "overtime_pay") == Decimal(30_000_000)


def test_monthly_work_days_drives_proration(db, user, client):
    """مبنای ۲۶ روز یعنی ۲۶ روز کارکرد = ماهِ کامل، نه ۸۷٪."""
    _hybrid(db)
    year = _year()
    _settings(client, year, monthly_work_days=26)
    employee = _employee(client)
    _contract(client, employee["id"], [{"factor_id": _factors(client)["base"], "amount": BASE}])
    period = client.post("/api/payroll-periods", json={"year": year, "month": 1}).json()
    client.put(
        "/api/attendance",
        json={"employee_id": employee["id"], "period_id": period["id"], "worked_days": 26,
              "absent_days": 0, "overtime_hours": 0},
    )
    slip = client.post(f"/api/payroll-periods/{period['id']}/generate-payslips", json={}).json()[0]
    assert _d(slip, "base_salary") == Decimal(BASE)


# ── مبنای مالیات ─────────────────────────────────────────────────────────────


def test_social_exemption_coefficient_of_zero_taxes_the_whole_gross(db, user, client):
    """ضریبِ صفر یعنی هیچ بخشی از بیمه از مبنای مالیات کم نشود.

    **صفر به پیش‌فرض برنمی‌گردد** — انتخابِ صریحِ کاربر است، نه نبودِ مقدار.
    """
    slip = _simple_run(client, db, tax_exempt_coef_social=0)
    assert _d(slip, "taxable_pay") == _d(slip, "gross_pay")


def test_the_default_coefficient_deducts_the_whole_insurance_share(db, user, client):
    slip = _simple_run(client, db)
    assert _d(slip, "taxable_pay") == _d(slip, "gross_pay") - _d(slip, "insurance_employee_share")


def test_a_supplementary_insurance_factor_reduces_the_tax_base(db, user, client):
    """§۱۷ — ضریبِ معافیتِ بیمه‌ی تکمیلی بی «کدام عامل؟» بی‌مصرف بود."""
    _hybrid(db)
    year = _year()
    _settings(client, year)
    supplementary = _factor(client, f"بیمه تکمیلی سهم کارمند {year}")
    _settings(client, year, supplementary_employee_factor_id=supplementary["id"])
    employee = _employee(client)
    _contract(
        client,
        employee["id"],
        [
            {"factor_id": _factors(client)["base"], "amount": BASE},
            {"factor_id": supplementary["id"], "amount": 10_000_000},
        ],
    )
    slip = _run(client, year)[0]
    expected = _d(slip, "gross_pay") - _d(slip, "insurance_employee_share") - Decimal(10_000_000)
    assert _d(slip, "taxable_pay") == expected


def test_negative_tax_is_suppressed_by_default(db, user, client):
    """پیش‌فرضِ `allow_negative_tax` خاموش است — همان `max(0, …)`ِ همیشگی."""
    slip = _simple_run(client, db)
    assert _d(slip, "tax_amount") >= 0


# ── رندِ پرداخت ──────────────────────────────────────────────────────────────


def test_no_rounding_by_default(db, user, client):
    slip = _simple_run(client, db)
    assert _d(slip, "rounding_adjustment") == 0


def test_rounding_moves_the_net_and_lands_on_its_own_account(db, user, client):
    """خالص تا هزار ریال گِرد می‌شود، و **سند همچنان متوازن است**.

    اختلافِ رند داخلِ هزینه‌ی حقوق گم نمی‌شود؛ ردیفِ خودش را می‌گیرد تا
    هزینه‌ی حقوقِ دفتر با جمعِ فیش‌ها بخواند.
    """
    slip = _simple_run(client, db, payment_rounding_digits=3)
    net = _d(slip, "net_pay")
    assert net % 1000 == 0, f"خالص تا هزار ریال گِرد نشد: {net}"

    adjustment = _d(slip, "rounding_adjustment")
    assert abs(adjustment) < 1000
    #: تساویِ فیش باید با تعدیل بسته شود.
    assert net == (
        _d(slip, "gross_pay")
        - _d(slip, "insurance_employee_share")
        - _d(slip, "tax_amount")
        - _d(slip, "loan_deduction")
        - _d(slip, "other_deductions")
        + adjustment
    )
    debit, credit = _entry_totals(db, slip)
    assert debit == credit


def test_the_rounding_row_shows_up_in_the_breakdown(db, user, client):
    """تعدیلِ رند یک ردیفِ دیدنیِ فیش است، نه چند ریالِ بی‌توضیح در ته آن."""
    slip = _simple_run(client, db, payment_rounding_digits=3)
    if _d(slip, "rounding_adjustment") == 0:
        pytest.skip("این ترکیب اتفاقاً رُند بود")
    assert any(line["factor_name"] == "تعدیل رند" for line in slip["lines"])


# ── مشارکتِ عامل‌ها ──────────────────────────────────────────────────────────


def test_an_empty_participation_table_means_yesterdays_behaviour(db, user, client):
    """**قیدِ مرکزیِ مهاجرتِ ۰۱۳۹.** جدولِ خالی = مبنای بیمه همان ناخالص."""
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    factors = _factors(client)
    _contract(
        client,
        employee["id"],
        [
            {"factor_id": factors["base"], "amount": BASE},
            {"factor_id": factors["housing"], "amount": 20_000_000},
        ],
    )
    slip = _run(client, year)[0]
    assert _d(slip, "gross_pay") == Decimal(320_000_000)
    assert _d(slip, "insurance_employee_share") == Decimal(320_000_000) * Decimal("0.07")


def test_excluding_a_factor_from_the_insurance_base_lowers_only_the_insurance(db, user, client):
    """§۱۳ §۱۴ — «مشمولِ بیمه» یک پرچمِ واحد نیست.

    عاملی که از مبنای بیمه بیرون می‌رود، از **ناخالص** بیرون نمی‌رود: کارمند
    همچنان پولش را می‌گیرد.
    """
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    factors = _factors(client)
    _contract(
        client,
        employee["id"],
        [
            {"factor_id": factors["base"], "amount": BASE},
            {"factor_id": factors["housing"], "amount": 20_000_000},
        ],
    )
    res = client.put(
        f"/api/payroll-factors/{factors['housing']}/participation",
        json={"participation": {"insurance_base": 0}},
    )
    assert res.status_code == 200, res.text
    assert Decimal(str(res.json()["participation"]["insurance_base"])) == 0

    slip = _run(client, year)[0]
    assert _d(slip, "gross_pay") == Decimal(320_000_000), "ناخالص نباید تکان بخورد"
    assert _d(slip, "insurance_employee_share") == Decimal(BASE) * Decimal("0.07")


def test_the_benefit_bases_default_to_base_salary_only(db, user, client):
    """§۴۳ — پیش‌فرضِ عیدی/سنوات/مرخصی «فقط حقوق پایه» است، نه «همه‌ی عوامل».

    این عدمِ‌تقارن با مبنای بیمه عمدی است: دقیقاً همان چیزی را رمزگذاری می‌کند
    که کد پیش از مهاجرتِ ۰۱۳۹ انجام می‌داد.
    """
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    factors = _factors(client)
    _contract(
        client,
        employee["id"],
        [
            {"factor_id": factors["base"], "amount": BASE},
            {"factor_id": factors["housing"], "amount": 20_000_000},
        ],
    )
    rows = client.get("/api/payroll-factors").json()
    by_id = {r["id"]: r for r in rows}
    for purpose in ("eidi_base", "severance_base", "leave_base"):
        assert Decimal(str(by_id[factors["base"]]["participation"][purpose])) == 1
        assert Decimal(str(by_id[factors["housing"]]["participation"][purpose])) == 0
    for purpose in ("insurance_base", "tax_base"):
        assert Decimal(str(by_id[factors["housing"]]["participation"][purpose])) == 1


def test_adding_a_factor_to_the_eidi_base_raises_the_eidi(db, user, client):
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    factors = _factors(client)
    _contract(
        client,
        employee["id"],
        [
            {"factor_id": factors["base"], "amount": BASE},
            {"factor_id": factors["housing"], "amount": 20_000_000},
        ],
    )
    before = client.get(f"/api/payroll/benefits?year={year}").json()
    client.put(
        f"/api/payroll-factors/{factors['housing']}/participation",
        json={"participation": {"eidi_base": 1}},
    )
    after = client.get(f"/api/payroll/benefits?year={year}").json()
    assert Decimal(str(after["total_eidi"])) > Decimal(str(before["total_eidi"]))


def test_setting_a_participation_back_to_its_default_deletes_the_row(db, user, client):
    """**جدولِ استثناهاست، نه جدولِ همه‌چیز.**

    اگر ردیفِ «مثلِ پیش‌فرض» هم ذخیره می‌شد، دو نمایشِ یک حقیقت پیدا می‌کردیم و
    تغییرِ بعدیِ پیش‌فرض به ردیف‌های ذخیره‌شده نمی‌رسید.
    """
    _hybrid(db)
    factors = _factors(client)
    housing = factors["housing"]
    client.put(f"/api/payroll-factors/{housing}/participation", json={"participation": {"insurance_base": 0}})
    assert db.query(PayrollFactorParticipation).filter(
        PayrollFactorParticipation.factor_id == housing
    ).count() == 1

    client.put(f"/api/payroll-factors/{housing}/participation", json={"participation": {"insurance_base": 1}})
    assert db.query(PayrollFactorParticipation).filter(
        PayrollFactorParticipation.factor_id == housing
    ).count() == 0


def test_an_unknown_purpose_is_rejected(db, user, client):
    _hybrid(db)
    factors = _factors(client)
    res = client.put(
        f"/api/payroll-factors/{factors['base']}/participation",
        json={"participation": {"bonus_base": 1}},
    )
    assert res.status_code == 422, res.text


# ── اعتبارسنجیِ پارامترها ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "field,value",
    [
        ("unemployment_rate", 1.5),
        ("hard_job_rate", -0.1),
        ("eidi_base_multiplier", 0),
        ("severance_days_per_year", 0),
        ("monthly_work_days", 40),
        ("overtime_multiplier", 0),
        ("tax_exempt_coef_social", 2),
        ("payment_rounding_digits", 9),
        ("insurance_daily_ceiling", -1),
    ],
)
def test_out_of_range_parameters_are_refused_with_a_persian_message(db, user, client, field, value):
    """قیدِ `CHECK` هست، ولی کاربر باید پیامِ فارسی بگیرد نه `IntegrityError`ِ خام."""
    res = client.put(
        "/api/payroll-settings",
        json={
            "year": _year(),
            "insurance_employee_rate": 0.07,
            "insurance_employer_rate": 0.23,
            "tax_exemption_annual": EXEMPTION,
            "tax_brackets": BRACKETS,
            field: value,
        },
    )
    assert res.status_code == 422, res.text


def test_saved_parameters_round_trip(db, user, client):
    """هر ستونِ تازه باید در هر دو مسیرِ ساخت و ویرایش نوشته شود."""
    _hybrid(db)
    year = _year()
    _settings(client, year)  # ساخت
    saved = _settings(  # ویرایش
        client,
        year,
        insurance_daily_ceiling=5_000_000,
        unemployment_rate=0.03,
        eidi_base_multiplier=3,
        severance_days_per_year=45,
        monthly_work_days=26,
        standard_monthly_hours=176,
        overtime_multiplier=1.5,
        payment_rounding_digits=3,
        allow_negative_tax=True,
    )
    assert Decimal(str(saved["insurance_daily_ceiling"])) == 5_000_000
    assert Decimal(str(saved["unemployment_rate"])) == Decimal("0.03")
    assert Decimal(str(saved["eidi_base_multiplier"])) == 3
    assert saved["severance_days_per_year"] == 45
    assert Decimal(str(saved["monthly_work_days"])) == 26
    assert Decimal(str(saved["standard_monthly_hours"])) == 176
    assert Decimal(str(saved["overtime_multiplier"])) == Decimal("1.5")
    assert saved["payment_rounding_digits"] == 3
    assert saved["allow_negative_tax"] is True


# ── عیدی و سنوات ────────────────────────────────────────────────────────────


def test_eidi_multiplier_is_configurable(db, user, client):
    """§۴۷ — `base * 2` در کد بود. پیش‌فرض همان ۲ می‌ماند."""
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    _contract(client, employee["id"], [{"factor_id": _factors(client)["base"], "amount": BASE}])
    two = Decimal(str(client.get(f"/api/payroll/benefits?year={year}").json()["total_eidi"]))

    _settings(client, year, eidi_base_multiplier=3)
    three = Decimal(str(client.get(f"/api/payroll/benefits?year={year}").json()["total_eidi"]))
    assert three == two / 2 * 3


def test_severance_days_per_year_is_configurable(db, user, client):
    """§۵۳ §۵۴ — ۳۰ روز در کد ثابت بود؛ ۶۰ باید دقیقاً دو برابر بدهد."""
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    _contract(client, employee["id"], [{"factor_id": _factors(client)["base"], "amount": BASE}])
    thirty = Decimal(str(client.get(f"/api/payroll/benefits?year={year}").json()["total_severance"]))
    assert thirty > 0

    _settings(client, year, severance_days_per_year=60)
    sixty = Decimal(str(client.get(f"/api/payroll/benefits?year={year}").json()["total_severance"]))
    assert abs(sixty - thirty * 2) <= 1


# ── گذشته بازنویسی نمی‌شود ──────────────────────────────────────────────────


def test_changing_settings_does_not_rewrite_an_issued_payslip(db, user, client):
    """§۳ — فیشِ صادرشده عکسِ اعداد است، نه ارجاع به تنظیماتِ امروز."""
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    _contract(client, employee["id"], [{"factor_id": _factors(client)["base"], "amount": BASE}])
    slip = _run(client, year)[0]
    before = _d(slip, "insurance_employee_share")

    _settings(client, year, insurance_daily_ceiling=1_000_000, unemployment_rate=0.05)

    rows = client.get(f"/api/payslips?period_id={slip['period_id']}").json()["items"]
    after = next(r for r in rows if r["id"] == slip["id"])
    assert Decimal(str(after["insurance_employee_share"])) == before


def test_saving_settings_creates_no_journal(db, user, client):
    """§۱۲ §۷۶ — ذخیره‌ی تنظیمات نه سند می‌زند نه حرکتِ خزانه."""
    _hybrid(db)
    before = db.query(JournalEntry).count()
    _settings(client, _year(), insurance_daily_ceiling=9_000_000, payment_rounding_digits=2)
    assert db.query(JournalEntry).count() == before


# ── پرچم‌های بیمه‌ی حکم ──────────────────────────────────────────────────────
#
# **شش ستونِ مرده.** `salary_contracts` این‌ها را از قبل داشت و هیچ‌کدام خوانده
# نمی‌شدند: کاربر «معاف از بیمه» را تیک می‌زد و بیمه کامل کسر می‌شد. با پروب
# اندازه گرفته شد — حکمی با `is_insured=False` باز هم ۲۱٬۰۰۰٬۰۰۰ می‌گرفت.


def _flagged_run(db, client, **flags) -> dict:
    from app.models.payroll import SalaryContract

    _hybrid(db)
    year = _year()
    _settings(client, year, unemployment_rate=0.03, hard_job_rate=0.04)
    employee = _employee(client)
    made = _contract(client, employee["id"], [{"factor_id": _factors(client)["base"], "amount": BASE}])
    row = db.get(SalaryContract, made["id"])
    for field, value in flags.items():
        setattr(row, field, value)
    db.flush()
    return _run(client, year)[0]


def test_an_uninsured_contract_pays_no_insurance_at_all(db, user, client):
    slip = _flagged_run(db, client, is_insured=False)
    assert _d(slip, "insurance_employee_share") == 0
    assert _d(slip, "insurance_employer_share") == 0
    assert _d(slip, "gross_pay") == Decimal(BASE), "ناخالص نباید تکان بخورد"


def test_employee_insurance_exemption_leaves_the_employer_share_alone(db, user, client):
    slip = _flagged_run(db, client, exempt_employee_insurance=True)
    assert _d(slip, "insurance_employee_share") == 0
    assert _d(slip, "insurance_employer_share") > 0


def test_a_checked_employer_exemption_with_no_percent_means_full_exemption(db, user, client):
    """**درصدِ صفر با تیکِ معافیت یعنی معافیتِ کامل.**

    فرم آن میدان را فقط وقتی نشان می‌دهد که تیک خورده باشد؛ خواندنِ «صفر درصد
    معاف» یعنی تیک هیچ کاری نکند — همان باگی که بسته شد. نرخِ بیکاری مستقل است
    و باقی می‌ماند.
    """
    slip = _flagged_run(db, client, exempt_employer_insurance=True)
    assert _d(slip, "insurance_employer_share") == Decimal(BASE) * Decimal("0.03")


def test_a_partial_employer_exemption_scales_the_employer_rate(db, user, client):
    slip = _flagged_run(db, client, exempt_employer_insurance=True, employer_exempt_percent=Decimal(50))
    #: ۲۳٪ نصف می‌شود، و ۳٪ بیکاری دست‌نخورده می‌ماند.
    assert _d(slip, "insurance_employer_share") == Decimal(BASE) * (Decimal("0.115") + Decimal("0.03"))


def test_unemployment_exemption_removes_only_that_rate(db, user, client):
    slip = _flagged_run(db, client, exempt_unemployment_insurance=True)
    assert _d(slip, "insurance_employer_share") == Decimal(BASE) * Decimal("0.23")


def test_a_hard_job_contract_finally_picks_up_the_hard_job_rate(db, user, client):
    """**تصحیحِ یک ادعای غلطِ قبلی.** در PR #51 نوشتم کوبیتا پرچمِ مشاغل سخت
    ندارد؛ `SalaryContract.is_hard_job` از قبل بود و فقط خوانده نمی‌شد.
    """
    slip = _flagged_run(db, client, is_hard_job=True)
    assert _d(slip, "insurance_employer_share") == Decimal(BASE) * Decimal("0.30")  # ۲۳ + ۳ + ۴


def test_a_plain_contract_is_untouched_by_any_of_it(db, user, client):
    """گاردِ عدم‌تغییر: حکمی که پرچم‌ها را دست نزده دقیقاً نرخ‌های تنظیمات را می‌گیرد."""
    slip = _flagged_run(db, client)
    assert _d(slip, "insurance_employee_share") == Decimal(BASE) * Decimal("0.07")
    assert _d(slip, "insurance_employer_share") == Decimal(BASE) * Decimal("0.26")  # ۲۳ + ۳ بیکاری


def test_the_housing_loan_exemption_lowers_the_tax_base(db, user, client):
    slip = _flagged_run(db, client, housing_loan_exempt_amount=Decimal(10_000_000))
    expected = _d(slip, "gross_pay") - _d(slip, "insurance_employee_share") - Decimal(10_000_000)
    assert _d(slip, "taxable_pay") == expected
