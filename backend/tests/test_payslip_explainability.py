"""فیشِ حقوقی نباید جعبه‌ی سیاه باشد.

`Payslip` اعدادش را از لحظه‌ی صدور snapshot می‌گیرد و این درست است — حقوقِ تیر با
جدولِ مالیاتِ مرداد بازمحاسبه نمی‌شود. ولی snapshot در سطحِ **جمع** بود:
`allowances_total` یک عدد، و هر عاملی که `housing`/`food` نبود اول در
`other_allowance` جمع می‌شد و بعد در آن یک عدد.

پس «این ۳٬۲۰۰٬۰۰۰ مزایا از چه ساخته شد؟» جواب نداشت — و بازخواندنش از قرارداد
هم جواب نمی‌دهد، چون قرارداد می‌تواند از آن موقع عوض شده باشد. دقیقاً همان دلیلی
که snapshot برایش وجود دارد.

سه ادعای این فایل:

  ۱. جمعِ تفکیک **دقیقاً** خالصِ فیش است — دو عدد نمی‌شوند.
  ۲. هر عامل ردیفِ **خودش** را دارد، با نامی که در لحظه‌ی صدور داشت.
  ۳. تغییرِ قرارداد و نامِ عامل، فیشِ صادرشده را دست نمی‌زند.
"""
from decimal import Decimal

from app.models.payroll import PayrollFactor, PayrollSettings, Payslip, PayslipLine

BRACKETS = [{"up_to": 2_000_000_000, "rate": 0.1}, {"up_to": None, "rate": 0.2}]
EXEMPTION = Decimal("1200000000")


def _employee(client, national_id="2222222222") -> dict:
    r = client.post(
        "/api/employees",
        json={
            "first_name": "مریم",
            "last_name": "حسابدار",
            "national_id": national_id,
            "hire_date": "2025-01-01",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


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


def _custom_factor(client, name: str, category: str) -> str:
    """عاملِ دلخواه با نامِ یکتا —  کامیت می‌کند و تست‌ها مستأجر را شریک‌اند."""
    from uuid import uuid4

    unique = f"{name} {uuid4().hex[:6]}"
    r = client.post(
        "/api/payroll-factors",
        json={"name": unique, "category": category, "kind": "fixed"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"], unique


def _contract(client, employee_id: str, lines: list[dict], **extra) -> dict:
    r = client.post(
        "/api/salary-contracts",
        json={
            "employee_id": employee_id,
            "effective_from": "2026-01-01",
            "lines": lines,
            **extra,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _run(client, year: int, month: int, *, headers=None) -> tuple:
    period = client.post("/api/payroll-periods", json={"year": year, "month": month}).json()
    r = client.post(
        f"/api/payroll-periods/{period['id']}/generate-payslips", json={}, headers=headers or {}
    )
    return r, period


def _issued(client, year=1405, month=1, **kw) -> list[dict]:
    r, _ = _run(client, year, month, **kw)
    assert r.status_code == 200, r.text
    return r.json()


# ═══════════════ ۱) تفکیک با فیش می‌خواند ═══════════════


def test_the_breakdown_sums_exactly_to_the_net(client, db):
    """قیدِ مرکزی: تفکیک و محاسبه دو کدند و باید یک عدد بدهند."""
    _settings(db, 1405)
    emp = _employee(client, "3000000001")
    f = _factors(client)
    _contract(
        client,
        emp["id"],
        [
            {"factor_id": f["base"], "amount": 500_000_000},
            {"factor_id": f["housing"], "amount": 90_000_000},
            {"factor_id": f["food"], "amount": 60_000_000},
        ],
    )

    payslips = _issued(client)
    assert len(payslips) == 1
    slip = payslips[0]
    assert slip["lines"], "فیش باید تفکیک داشته باشد"

    earnings = sum(Decimal(l["amount"]) for l in slip["lines"] if l["direction"] == "earning")
    deductions = sum(Decimal(l["amount"]) for l in slip["lines"] if l["direction"] == "deduction")
    assert earnings - deductions == Decimal(slip["net_pay"])


def test_every_benefit_factor_gets_its_own_row(client, db):
    """تا امروز هر عاملِ غیرِ مسکن/خوار‌وبار در یک عدد گم می‌شد."""
    _settings(db, 1405)
    emp = _employee(client, "3000000002")
    f = _factors(client)
    child, child_name = _custom_factor(client, "حق اولاد", "benefit")
    supplement, supplement_name = _custom_factor(client, "بیمه تکمیلی", "deduction")

    _contract(
        client,
        emp["id"],
        [
            {"factor_id": f["base"], "amount": 400_000_000},
            {"factor_id": f["housing"], "amount": 90_000_000},
            {"factor_id": child, "amount": 30_000_000},
            {"factor_id": supplement, "amount": 12_000_000},
        ],
    )

    slip = _issued(client)[0]
    names = {l["factor_name"]: l for l in slip["lines"]}

    assert child_name in names, "عاملِ دلخواه باید ردیفِ خودش را داشته باشد"
    assert names[child_name]["direction"] == "earning"
    assert names[child_name]["origin"] == "contract"
    assert Decimal(names[child_name]["amount"]) == 30_000_000

    assert supplement_name in names
    assert names[supplement_name]["direction"] == "deduction"
    assert Decimal(names[supplement_name]["amount"]) == 12_000_000

    #: و مزایا دیگر یک عددِ مبهم نیست: جمعِ ردیف‌های مزایا (بی‌احتسابِ پایه و
    #: اضافه‌کار) باید همان `allowances_total` باشد.
    benefits = sum(
        Decimal(l["amount"])
        for l in slip["lines"]
        if l["direction"] == "earning" and l["factor_name"] not in ("حقوق پایه", "اضافه‌کار")
    )
    assert benefits == Decimal(slip["allowances_total"])


def test_system_components_are_explained_too(client, db):
    """بیمه، مالیات و حقوقِ پایه عاملِ کاربر نیستند، ولی باید توضیح داده شوند."""
    _settings(db, 1405)
    emp = _employee(client, "3000000003")
    f = _factors(client)
    _contract(client, emp["id"], [{"factor_id": f["base"], "amount": 600_000_000}])

    slip = _issued(client)[0]
    by_name = {l["factor_name"]: l for l in slip["lines"]}

    assert Decimal(by_name["حقوق پایه"]["amount"]) == Decimal(slip["base_salary"])
    assert by_name["حقوق پایه"]["origin"] == "contract"

    assert Decimal(by_name["بیمه سهم کارمند"]["amount"]) == Decimal(slip["insurance_employee_share"])
    assert by_name["بیمه سهم کارمند"]["origin"] == "settings", "برای عوض‌کردنش به تنظیمات برو"
    assert Decimal(by_name["مالیات بر درآمد حقوق"]["amount"]) == Decimal(slip["tax_amount"])


def test_a_zero_component_gets_no_row(client, db):
    """فیشی با ده ردیفِ صفر توضیح‌پذیرتر نیست — شلوغ‌تر است."""
    _settings(db, 1405)
    emp = _employee(client, "3000000004")
    f = _factors(client)
    _contract(client, emp["id"], [{"factor_id": f["base"], "amount": 300_000_000}])

    slip = _issued(client)[0]
    assert all(Decimal(l["amount"]) != 0 for l in slip["lines"])
    assert not any(l["factor_name"] == "اضافه‌کار" for l in slip["lines"]), "اضافه‌کارِ صفر ردیف نمی‌گیرد"


# ═══════════════ ۲) تفکیک هم snapshot است ═══════════════


def test_renaming_a_factor_does_not_rewrite_an_issued_payslip(client, db):
    """نامِ عامل عکسِ لحظه‌ی ثبت است، وگرنه فیشِ پارسال بازنویسی می‌شد."""
    _settings(db, 1405)
    emp = _employee(client, "3000000005")
    f = _factors(client)
    bonus, bonus_name = _custom_factor(client, "پاداش بهره‌وری", "benefit")
    _contract(
        client,
        emp["id"],
        [
            {"factor_id": f["base"], "amount": 400_000_000},
            {"factor_id": bonus, "amount": 50_000_000},
        ],
    )
    _issued(client)

    #: نامِ عامل عوض می‌شود…
    row = db.get(PayrollFactor, bonus)
    row.name = "پاداشِ تازه"
    db.flush()
    db.expire_all()

    #: …و فیشِ صادرشده همان نامِ قبلی را نگه می‌دارد.
    names = {l.factor_name for l in db.query(PayslipLine).all()}
    assert bonus_name in names
    assert "پاداشِ تازه" not in names


def test_the_breakdown_survives_a_contract_change(client, db):
    """قرارداد عوض می‌شود؛ فیشِ صادرشده و تفکیکش دست نمی‌خورند."""
    _settings(db, 1405)
    emp = _employee(client, "3000000006")
    f = _factors(client)
    _contract(
        client,
        emp["id"],
        [
            {"factor_id": f["base"], "amount": 400_000_000},
            {"factor_id": f["housing"], "amount": 90_000_000},
        ],
    )
    before = _issued(client)[0]
    before_lines = {l["factor_name"]: l["amount"] for l in before["lines"]}

    #: حکمِ تازه با ارقامِ دیگر
    r = client.post(
        "/api/salary-contracts",
        json={
            "employee_id": emp["id"],
            "effective_from": "2026-06-01",
            "contract_type": "amend",
            "lines": [
                {"factor_id": f["base"], "amount": 900_000_000},
                {"factor_id": f["housing"], "amount": 200_000_000},
            ],
        },
    )
    assert r.status_code == 201, r.text

    db.expire_all()
    slip = db.query(Payslip).filter(Payslip.id == before["id"]).one()
    after = {l.factor_name: str(l.amount) for l in slip.lines}
    assert after == before_lines, "تفکیکِ فیشِ صادرشده نباید با حکمِ تازه عوض شود"


# ═══════════════ ۳) تناسبِ کارکرد ═══════════════


def test_a_partial_month_prorates_the_breakdown_too(client, db):
    """اگر تفکیک تناسب نخورد، جمعش با فیش نمی‌خواند."""
    _settings(db, 1405)
    emp = _employee(client, "3000000007")
    f = _factors(client)
    _contract(
        client,
        emp["id"],
        [
            {"factor_id": f["base"], "amount": 600_000_000},
            {"factor_id": f["housing"], "amount": 90_000_000},
        ],
    )

    period = client.post("/api/payroll-periods", json={"year": 1405, "month": 2}).json()
    r = client.put(
        "/api/attendance",
        json={"employee_id": emp["id"], "period_id": period["id"], "worked_days": 15, "overtime_hours": 0},
    )
    assert r.status_code in (200, 201), r.text

    issued = client.post(f"/api/payroll-periods/{period['id']}/generate-payslips", json={})
    assert issued.status_code == 200, issued.text
    slip = issued.json()[0]

    earnings = sum(Decimal(l["amount"]) for l in slip["lines"] if l["direction"] == "earning")
    deductions = sum(Decimal(l["amount"]) for l in slip["lines"] if l["direction"] == "deduction")
    assert earnings - deductions == Decimal(slip["net_pay"])
    #: و نصفِ ماه یعنی نصفِ پایه.
    assert Decimal(slip["base_salary"]) == 300_000_000


# ═══════════════ ۴) ثبتِ دوباره ═══════════════


def test_the_same_request_twice_issues_payroll_once(client, db):
    """فرمانی که حقوقِ همه را صادر می‌کند، بدترین جا برای «نمی‌دانم شد یا نه» است.

    داده از قبل هم خراب نمی‌شد، ولی اجرای دوم **۴۰۰** می‌گرفت و کاربر نمی‌فهمید
    حقوق صادر شده یا نه. حالا همان فهرستِ اول را پس می‌دهد.
    """
    _settings(db, 1405)
    emp = _employee(client, "3000000008")
    f = _factors(client)
    _contract(client, emp["id"], [{"factor_id": f["base"], "amount": 500_000_000}])

    period = client.post("/api/payroll-periods", json={"year": 1405, "month": 3}).json()
    headers = {"Idempotency-Key": "payroll-retry-1"}

    first = client.post(
        f"/api/payroll-periods/{period['id']}/generate-payslips", json={}, headers=headers
    )
    second = client.post(
        f"/api/payroll-periods/{period['id']}/generate-payslips", json={}, headers=headers
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert [p["id"] for p in first.json()] == [p["id"] for p in second.json()], "همان فیش‌ها"

    db.expire_all()
    assert db.query(Payslip).filter(Payslip.period_id == period["id"]).count() == 1


def test_without_the_header_a_second_call_still_refuses(client, db):
    """بی‌کلید، محافظتی نیست — ولی گاردِ «دوره نهایی شده» سرِ جایش می‌ماند."""
    _settings(db, 1405)
    emp = _employee(client, "3000000009")
    f = _factors(client)
    _contract(client, emp["id"], [{"factor_id": f["base"], "amount": 500_000_000}])

    period = client.post("/api/payroll-periods", json={"year": 1405, "month": 4}).json()
    assert client.post(f"/api/payroll-periods/{period['id']}/generate-payslips", json={}).status_code == 200
    again = client.post(f"/api/payroll-periods/{period['id']}/generate-payslips", json={})
    assert again.status_code == 400
    db.expire_all()
    assert db.query(Payslip).filter(Payslip.period_id == period["id"]).count() == 1


# ═══════════════ ۵) حسابرسیِ تنظیمات ═══════════════


def test_payroll_configuration_leaves_an_audit_trail(client, db):
    """پلکانِ مالیات، مالیاتِ همه‌ی کارکنان را عوض می‌کند — و ردی نمی‌گذاشت."""
    from app.audit import audited_models
    from app.models.payroll import PayrollFactor as PF
    from app.models.payroll import PayrollSettings as PS
    from app.models.payroll import PayrollTaxGroup as PTG
    from app.models.payroll import SalaryContract as SC

    labels = audited_models()
    for model in (PS, PF, PTG, SC):
        assert model in labels, f"{model.__name__} باید حسابرسی شود"


def test_changing_the_tax_brackets_is_recorded(client, db):
    from app.models.audit import AuditLog

    _settings(db, 1405)
    db.flush()
    before = db.query(AuditLog).count()

    r = client.put(
        "/api/payroll-settings",
        json={
            "year": 1405,
            "insurance_employee_rate": "0.07",
            "insurance_employer_rate": "0.23",
            "tax_exemption_annual": str(EXEMPTION),
            "tax_brackets": [{"up_to": None, "rate": 0.15}],
        },
    )
    assert r.status_code in (200, 201), r.text

    db.expire_all()
    assert db.query(AuditLog).count() > before, "تغییرِ پلکانِ مالیات باید ثبت شود"
