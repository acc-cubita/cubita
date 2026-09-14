"""ورودیِ عواملِ متغیر در یک دوره — لایه‌ای که نبود.

**آنچه پروب نشان داد.** عاملی با `kind = 'variable'` روی حکم، دو ماهِ پیاپی:

    ماهِ ۱: مأموریت — ۵٬۰۰۰٬۰۰۰  (origin: contract)
    ماهِ ۲: مأموریت — ۵٬۰۰۰٬۰۰۰  (origin: contract)

دقیقاً یک عدد. `PayrollFactor.kind` نوشته می‌شد، اعتبارسنجی می‌شد، برگردانده
می‌شد — و هیچ‌جا خوانده نمی‌شد. پس مأموریت و پاداش و کارانه نمی‌توانستند
ماه‌به‌ماه فرق کنند، و برای عوض‌کردنِ یک ماه باید **حکمِ حقوقی** ویرایش می‌شد.

این تست‌ها چهار چیز را نگه می‌دارند: (۱) عاملِ متغیر بالاخره متغیر است، (۲)
ورودی به نسبتِ کارکرد کوچک **نمی‌شود** ولی مبلغِ حکم می‌شود، (۳) قاعده‌ی مشارکت
روی ورودی هم همان قاعده است، (۴) دوره‌ی فیش‌دار قفل است.
"""
from decimal import Decimal

import pytest

from app.models.payroll import PayrollFactorParticipation, PayslipLine
from tests.test_payroll_settings_policy import (
    BASE, _contract, _employee, _factors, _hybrid, _run, _settings, _year,
)


# ───────────────────────────── کمکی‌ها ─────────────────────────────


def _variable(client, name: str, category: str = "benefit") -> dict:
    res = client.post(
        "/api/payroll-factors",
        json={"name": name, "category": category, "kind": "variable"},
    )
    assert res.status_code == 201, res.text
    return res.json()


def _period(client, year: int, month: int) -> dict:
    return client.post("/api/payroll-periods", json={"year": year, "month": month}).json()


def _put_inputs(client, period_id: str, rows: list[dict]):
    return client.put(f"/api/payroll-periods/{period_id}/factor-inputs", json={"rows": rows})


def _generate(client, period_id: str) -> list[dict]:
    res = client.post(f"/api/payroll-periods/{period_id}/generate-payslips", json={})
    assert res.status_code == 200, res.text
    return res.json()


def _lines(db, slip: dict) -> list[PayslipLine]:
    return (
        db.query(PayslipLine)
        .filter(PayslipLine.payslip_id == slip["id"])
        .order_by(PayslipLine.seq)
        .all()
    )


def _line_for(db, slip: dict, factor_id: str) -> PayslipLine | None:
    return next((l for l in _lines(db, slip) if str(l.factor_id) == factor_id), None)


def _setup(db, client, *, month: int = 1):
    """یک کارمند، حکمِ فقط‌پایه، و دوره‌ی خواسته‌شده."""
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    _contract(client, employee["id"], [{"factor_id": _factors(client)["base"], "amount": BASE}])
    return year, employee, _period(client, year, month)


def _twins(db, client):
    """دو کارمندِ **هم‌حکم** در یک دوره — شاهد و آزمون.

    مقایسه عمداً داخلِ همان ماه است: مالیاتِ حقوق تجمعیِ سال است، پس دو ماهِ
    مختلف ذاتاً دو عدد می‌دهند و تفاوتشان چیزی را ثابت نمی‌کند.
    """
    _hybrid(db)
    year = _year()
    _settings(client, year)
    base_factor = _factors(client)["base"]
    control, subject = _employee(client), _employee(client)
    for who in (control, subject):
        _contract(client, who["id"], [{"factor_id": base_factor, "amount": BASE}])
    return year, control, subject, _period(client, year, 1)


def _slip_of(slips: list[dict], employee: dict) -> dict:
    return next(s for s in slips if s["employee_id"] == employee["id"])


# ─────────── ۱) عاملِ متغیر بالاخره متغیر است ───────────


def test_the_same_factor_can_differ_between_two_periods(db, client):
    """**باگی که بسته شد.** دو ماه، دو عدد — چیزی که تا امروز ممکن نبود."""
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    _contract(client, employee["id"], [{"factor_id": _factors(client)["base"], "amount": BASE}])
    mission = _variable(client, f"مأموریت {year}")

    amounts = {}
    for month, value in ((1, 5_000_000), (2, 3_000_000)):
        period = _period(client, year, month)
        assert _put_inputs(
            client, period["id"],
            [{"employee_id": employee["id"], "factor_id": mission["id"], "amount": value}],
        ).status_code == 200
        slip = _generate(client, period["id"])[0]
        line = _line_for(db, slip, mission["id"])
        assert line is not None, f"ردیفِ مأموریت در ماهِ {month} نیامد"
        amounts[month] = Decimal(str(line.amount))
        assert line.origin == "input", "برچسبِ منشأ هنوز «حکم» است"

    assert amounts[1] == Decimal(5_000_000)
    assert amounts[2] == Decimal(3_000_000)


def test_an_input_raises_gross_and_net(db, client):
    year, control, subject, period = _twins(db, client)
    bonus = _variable(client, f"پاداش {year}")
    _put_inputs(
        client, period["id"],
        [{"employee_id": subject["id"], "factor_id": bonus["id"], "amount": 10_000_000}],
    )
    slips = _generate(client, period["id"])
    before, after = _slip_of(slips, control), _slip_of(slips, subject)
    assert Decimal(after["gross_pay"]) - Decimal(before["gross_pay"]) == Decimal(10_000_000)
    assert Decimal(after["net_pay"]) > Decimal(before["net_pay"])


def test_a_deduction_input_lowers_net_without_touching_gross(db, client):
    """کسورِ ورودی مثلِ کسورِ حکم است: از **خالص** کم می‌شود، نه از ناخالص."""
    year, control, subject, period = _twins(db, client)
    fine = _variable(client, f"مساعده {year}", category="deduction")
    _put_inputs(
        client, period["id"],
        [{"employee_id": subject["id"], "factor_id": fine["id"], "amount": 4_000_000}],
    )
    slips = _generate(client, period["id"])
    before, after = _slip_of(slips, control), _slip_of(slips, subject)
    assert Decimal(after["gross_pay"]) == Decimal(before["gross_pay"])
    assert Decimal(before["net_pay"]) - Decimal(after["net_pay"]) == Decimal(4_000_000)


def test_no_input_means_yesterdays_payslip(db, client):
    """**جدولِ خالی یعنی هیچ عددی عوض نشده.**"""
    year, employee, period = _setup(db, client)
    _variable(client, f"پاداشِ بی‌ورودی {year}")
    slip = _generate(client, period["id"])[0]
    assert not [l for l in _lines(db, slip) if l.origin == "input"]


# ─────────── ۲) نسبتِ کارکرد ───────────


def test_an_input_is_not_prorated_but_the_contract_amount_is(db, client):
    """مبلغِ حکم ماهانه است، ورودیِ دوره عددِ **همین ماه**.

    نصفِ ماه کار کرده: پایه نصف می‌شود، مأموریت کامل می‌ماند.
    """
    year, employee, period = _setup(db, client)
    mission = _variable(client, f"مأموریت {year}")
    res = client.put(
        "/api/attendance",
        json={
            "employee_id": employee["id"], "period_id": period["id"],
            "worked_days": 15, "absent_days": 15, "overtime_hours": 0,
        },
    )
    assert res.status_code in (200, 201), res.text
    _put_inputs(
        client, period["id"],
        [{"employee_id": employee["id"], "factor_id": mission["id"], "amount": 6_000_000}],
    )
    slip = _generate(client, period["id"])[0]

    assert Decimal(slip["base_salary"]) == Decimal(BASE) / 2, "پایه به نسبتِ کارکرد کوچک نشد"
    line = _line_for(db, slip, mission["id"])
    assert Decimal(str(line.amount)) == Decimal(6_000_000), "ورودیِ دوره به نسبتِ کارکرد کوچک شد"


# ─────────── ۳) قاعده‌ی مشارکت، یکی برای هر دو مسیر ───────────


def test_an_excluded_factor_stays_excluded_when_it_arrives_as_an_input(db, client):
    """پاداشی که از مبنای بیمه مستثناست، چه از حکم بیاید چه از ورودیِ ماه."""
    year, control, subject, period = _twins(db, client)
    bonus = _variable(client, f"پاداشِ غیرمشمول {year}")
    res = client.put(
        f"/api/payroll-factors/{bonus['id']}/participation",
        json={"participation": {"insurance_base": 0}},
    )
    assert res.status_code == 200, res.text

    _put_inputs(
        client, period["id"],
        [{"employee_id": subject["id"], "factor_id": bonus["id"], "amount": 20_000_000}],
    )
    slips = _generate(client, period["id"])
    baseline, slip = _slip_of(slips, control), _slip_of(slips, subject)

    assert Decimal(slip["gross_pay"]) - Decimal(baseline["gross_pay"]) == Decimal(20_000_000)
    assert slip["insurance_employee_share"] == baseline["insurance_employee_share"], (
        "پاداشِ غیرمشمول مبنای بیمه را بالا برد"
    )


def test_by_default_an_input_is_insurable_and_taxable(db, client):
    """پیش‌فرضِ بیمه و مالیات «همه شریک‌اند» است — برای ورودی هم همان."""
    year, control, subject, period = _twins(db, client)
    bonus = _variable(client, f"پاداشِ مشمول {year}")
    _put_inputs(
        client, period["id"],
        [{"employee_id": subject["id"], "factor_id": bonus["id"], "amount": 20_000_000}],
    )
    slips = _generate(client, period["id"])
    baseline, slip = _slip_of(slips, control), _slip_of(slips, subject)
    assert Decimal(slip["insurance_employee_share"]) > Decimal(baseline["insurance_employee_share"])
    assert Decimal(slip["tax_amount"]) > Decimal(baseline["tax_amount"])


# ─────────── ۴) گاردها ───────────


def test_a_variable_factor_is_refused_on_a_contract(db, client):
    """حکم شرایطِ **ماندگار** را می‌گوید؛ مبلغِ متغیر شرطِ ماندگار نیست."""
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    mission = _variable(client, f"مأموریت {year}")
    res = client.post(
        "/api/salary-contracts",
        json={
            "employee_id": employee["id"],
            "effective_from": "2021-01-01",
            "lines": [
                {"factor_id": _factors(client)["base"], "amount": BASE},
                {"factor_id": mission["id"], "amount": 5_000_000},
            ],
        },
    )
    assert res.status_code == 400
    assert "متغیر" in res.json()["detail"]


def test_a_fixed_factor_is_refused_as_a_period_input(db, client):
    """جهتِ دیگرِ همان مرز — وگرنه یک عدد دو حقیقت پیدا می‌کرد."""
    year, employee, period = _setup(db, client)
    res = _put_inputs(
        client, period["id"],
        [{"employee_id": employee["id"], "factor_id": _factors(client)["base"], "amount": 1_000}],
    )
    assert res.status_code == 400
    assert "قراردادی" in res.json()["detail"]


def test_inputs_are_locked_once_the_period_has_payslips(db, client):
    """«هرگز گذشته را بازنویسی نکن» — عددِ فیشِ صادرشده باید توضیح‌پذیر بماند."""
    year, employee, period = _setup(db, client)
    bonus = _variable(client, f"پاداش {year}")
    _put_inputs(
        client, period["id"],
        [{"employee_id": employee["id"], "factor_id": bonus["id"], "amount": 1_000_000}],
    )
    _generate(client, period["id"])
    res = _put_inputs(
        client, period["id"],
        [{"employee_id": employee["id"], "factor_id": bonus["id"], "amount": 9_000_000}],
    )
    assert res.status_code == 400
    #: صدورِ فیش خودش دوره را نهایی می‌کند، پس گاردِ «نهایی‌شده» اول می‌گیرد.
    #: هر دو یک چیز را می‌گویند: عددِ فیشِ صادرشده قفل است.
    assert "قفل" in res.json()["detail"] or "فیش" in res.json()["detail"]


def test_zero_removes_the_row_rather_than_storing_a_zero(db, client):
    year, employee, period = _setup(db, client)
    bonus = _variable(client, f"پاداش {year}")
    _put_inputs(
        client, period["id"],
        [{"employee_id": employee["id"], "factor_id": bonus["id"], "amount": 7_000_000}],
    )
    assert len(client.get(f"/api/payroll-periods/{period['id']}/factor-inputs").json()) == 1
    _put_inputs(
        client, period["id"],
        [{"employee_id": employee["id"], "factor_id": bonus["id"], "amount": 0}],
    )
    assert client.get(f"/api/payroll-periods/{period['id']}/factor-inputs").json() == []


def test_saving_one_employee_does_not_erase_another(db, client):
    """**نه جایگزینیِ کامل.** درسِ `PUT /price-lists/{id}/items`."""
    _hybrid(db)
    year = _year()
    _settings(client, year)
    keys = _factors(client)
    first, second = _employee(client), _employee(client)
    for who in (first, second):
        _contract(client, who["id"], [{"factor_id": keys["base"], "amount": BASE}])
    period = _period(client, year, 1)
    bonus = _variable(client, f"پاداش {year}")

    _put_inputs(client, period["id"],
                [{"employee_id": first["id"], "factor_id": bonus["id"], "amount": 1_000_000}])
    _put_inputs(client, period["id"],
                [{"employee_id": second["id"], "factor_id": bonus["id"], "amount": 2_000_000}])

    rows = client.get(f"/api/payroll-periods/{period['id']}/factor-inputs").json()
    assert len(rows) == 2, "ذخیره‌ی نفرِ دوم، نفرِ اول را پاک کرد"


def test_an_inactive_factor_is_refused_as_an_input(db, client):
    year, employee, period = _setup(db, client)
    bonus = _variable(client, f"پاداش {year}")
    client.patch(f"/api/payroll-factors/{bonus['id']}", json={"is_active": False})
    res = _put_inputs(
        client, period["id"],
        [{"employee_id": employee["id"], "factor_id": bonus["id"], "amount": 1_000_000}],
    )
    assert res.status_code == 400
    assert "غیرفعال" in res.json()["detail"]


@pytest.mark.parametrize("amount", [-1, -5_000_000])
def test_a_negative_input_is_refused(db, client, amount):
    """جهت از **طبقه‌ی عامل** می‌آید، نه از علامتِ عدد."""
    year, employee, period = _setup(db, client)
    bonus = _variable(client, f"پاداش {year}")
    res = _put_inputs(
        client, period["id"],
        [{"employee_id": employee["id"], "factor_id": bonus["id"], "amount": amount}],
    )
    assert res.status_code == 422


# ─────────── ۵) سند، و رد ───────────


def test_the_factor_account_applies_to_an_input_line_too(db, client):
    """حسابِ عامل باید روی ردیفِ ورودی هم بنشیند، نه فقط ردیفِ حکم."""
    from app.models.accounting import Account, JournalEntry, JournalLine

    year, employee, period = _setup(db, client)
    account = db.query(Account).filter(
        Account.code == "5102", Account.is_group.is_(False)
    ).first()
    assert account is not None
    bonus = _variable(client, f"پاداشِ حساب‌دار {year}")
    res = client.patch(
        f"/api/payroll-factors/{bonus['id']}",
        json={"expense_account_id": str(account.id)},
    )
    assert res.status_code == 200, res.text

    _put_inputs(
        client, period["id"],
        [{"employee_id": employee["id"], "factor_id": bonus["id"], "amount": 8_000_000}],
    )
    slip = _generate(client, period["id"])[0]
    entry = db.get(JournalEntry, slip["journal_entry_id"])
    lines = db.query(JournalLine).filter(JournalLine.entry_id == entry.id).all()
    hit = [l for l in lines if l.account_id == account.id and Decimal(str(l.debit)) == Decimal(8_000_000)]
    assert hit, "مبلغِ ورودی به حسابِ تنظیم‌شده‌ی عامل نرفت"


def test_participation_rows_survive_the_new_layer(db, client):
    """گاردِ رگرسیون: جدولِ مشارکت دست‌نخورده مانده."""
    year, employee, period = _setup(db, client)
    bonus = _variable(client, f"پاداش {year}")
    client.put(
        f"/api/payroll-factors/{bonus['id']}/participation",
        json={"participation": {"tax_base": 0}},
    )
    rows = db.query(PayrollFactorParticipation).filter(
        PayrollFactorParticipation.factor_id == bonus["id"]
    ).all()
    assert len(rows) == 1 and rows[0].included is False
