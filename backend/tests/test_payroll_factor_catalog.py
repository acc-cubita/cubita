"""کاتالوگِ عوامل: «فعال»، اولویتِ نمایش، و پروفایلِ حسابداریِ عامل.

سه ستون روی `payroll_factors` بودند و **هیچ‌کدام مصرف‌کننده نداشتند**
(`is_active`، `is_extraordinary`، `kind`). یعنی عاملی که کاربر غیرفعال کرده بود
همچنان به حکمِ تازه اضافه می‌شد و در فیش می‌آمد — پرچمی که زده می‌شود و هیچ
اثری ندارد.

مهاجرتِ ۰۱۴۰ خودِ آن ستون‌ها را عوض نکرد؛ کد از آن به بعد می‌خوانَدشان. چیزی که
اضافه شد اولویتِ نمایش و پروفایلِ حسابداریِ عامل است، و **پیش‌فرضِ هر دو یعنی
رفتارِ دست‌نخورده**.
"""
from decimal import Decimal

from app.models.accounting import Account, JournalEntry, JournalLine
from app.services import chart_codes as cc
from tests.test_payroll_settings_policy import (
    BASE,
    _contract,
    _d,
    _employee,
    _entry_totals,
    _factor,
    _factors,
    _hybrid,
    _run,
    _settings,
    _year,
)


def _leaf_account(db, code: str = "5102") -> Account:
    """یک حسابِ برگیِ هزینه برای نگاشتِ عامل — همان حسابِ هزینه‌ی حقوق."""
    return db.query(Account).filter(Account.code == code, Account.is_group.is_(False)).first()


def _lines(db, slip: dict) -> list[JournalLine]:
    entry = db.get(JournalEntry, slip["journal_entry_id"])
    return db.query(JournalLine).filter(JournalLine.entry_id == entry.id).all()


# ── «فعال» بالاخره کاری می‌کند ───────────────────────────────────────────────


def test_an_inactive_factor_is_refused_on_a_new_contract(db, user, client):
    """**باگی که بسته شد.** `is_active` نوشته می‌شد و هیچ‌کس نمی‌خوانْدَش."""
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    bonus = _factor(client, f"پاداش غیرفعال {year}", category="benefit")
    res = client.patch(f"/api/payroll-factors/{bonus['id']}", json={"is_active": False})
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False

    res = client.post(
        "/api/salary-contracts",
        json={
            "employee_id": employee["id"],
            "effective_from": "2021-01-01",
            "lines": [
                {"factor_id": _factors(client)["base"], "amount": BASE},
                {"factor_id": bonus["id"], "amount": 5_000_000},
            ],
        },
    )
    assert res.status_code == 400, res.text
    assert "غیرفعال" in res.json()["detail"]


def test_deactivating_a_factor_does_not_touch_an_issued_payslip(db, user, client):
    """**«دیگر انتخاب نشو»، نه «از گذشته پاک شو».**

    غیرفعال‌کردن فقط استفاده‌ی آینده را می‌بندد؛ فیشی که صادر شده ردیفش را
    نگه می‌دارد، وگرنه غیرفعال‌کردن تاریخ را بازنویسی می‌کرد.
    """
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    bonus = _factor(client, f"حق مسئولیت {year}", category="benefit")
    _contract(
        client,
        employee["id"],
        [
            {"factor_id": _factors(client)["base"], "amount": BASE},
            {"factor_id": bonus["id"], "amount": 5_000_000},
        ],
    )
    slip = _run(client, year)[0]
    before = [line["factor_name"] for line in slip["lines"]]
    assert f"حق مسئولیت {year}" in before

    client.patch(f"/api/payroll-factors/{bonus['id']}", json={"is_active": False})

    rows = client.get(f"/api/payslips?period_id={slip['period_id']}").json()["items"]
    after = next(r for r in rows if r["id"] == slip["id"])
    assert [line["factor_name"] for line in after["lines"]] == before


def test_an_active_factor_still_works(db, user, client):
    """گاردِ عدم‌تغییر — عاملِ فعال (پیش‌فرض) دقیقاً مثلِ دیروز رفتار می‌کند."""
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    _contract(client, employee["id"], [{"factor_id": _factors(client)["base"], "amount": BASE}])
    assert _d(_run(client, year)[0], "gross_pay") == Decimal(BASE)


# ── طبقه‌ی عاملِ در استفاده قفل است ──────────────────────────────────────────


def test_the_category_of_a_used_factor_is_frozen(db, user, client):
    """بردنِ یک عامل از «مزایا» به «کسورات» علامتِ مبلغش را برمی‌گرداند.

    روی عاملی که در حکم نشسته یعنی معنیِ داده‌ی گذشته بی‌صدا عوض شود.
    """
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    bonus = _factor(client, f"کارانه {year}", category="benefit")
    _contract(
        client,
        employee["id"],
        [
            {"factor_id": _factors(client)["base"], "amount": BASE},
            {"factor_id": bonus["id"], "amount": 3_000_000},
        ],
    )
    res = client.patch(f"/api/payroll-factors/{bonus['id']}", json={"category": "deduction"})
    assert res.status_code == 400, res.text
    assert "قفل" in res.json()["detail"]


def test_an_unused_factor_can_still_change_category(db, user, client):
    _hybrid(db)
    bonus = _factor(client, f"عاملِ بی‌استفاده {_year()}", category="benefit")
    res = client.patch(f"/api/payroll-factors/{bonus['id']}", json={"category": "deduction"})
    assert res.status_code == 200, res.text
    assert res.json()["category"] == "deduction"


def test_renaming_a_used_factor_is_still_allowed(db, user, client):
    """عنوان فقط نمایشی است؛ هویت `factor_id` است، نه نام."""
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    bonus = _factor(client, f"ایاب و ذهاب {year}", category="benefit")
    _contract(
        client,
        employee["id"],
        [
            {"factor_id": _factors(client)["base"], "amount": BASE},
            {"factor_id": bonus["id"], "amount": 2_000_000},
        ],
    )
    res = client.patch(f"/api/payroll-factors/{bonus['id']}", json={"name": f"ایاب و ذهاب اصلاحی {year}"})
    assert res.status_code == 200, res.text


# ── اولویتِ نمایش ────────────────────────────────────────────────────────────


def test_display_priority_orders_the_payslip_rows(db, user, client):
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    factors = _factors(client)
    last = _factor(client, f"آخر {year}", category="benefit")
    first = _factor(client, f"یکم {year}", category="benefit")
    client.patch(f"/api/payroll-factors/{last['id']}", json={"display_priority": 90})
    client.patch(f"/api/payroll-factors/{first['id']}", json={"display_priority": 10})
    _contract(
        client,
        employee["id"],
        [
            {"factor_id": factors["base"], "amount": BASE},
            {"factor_id": last["id"], "amount": 1_000_000},
            {"factor_id": first["id"], "amount": 2_000_000},
        ],
    )
    names = [line["factor_name"] for line in _run(client, year)[0]["lines"]]
    assert names.index(f"یکم {year}") < names.index(f"آخر {year}")


def test_changing_display_priority_leaves_an_issued_payslip_alone(db, user, client):
    """§۷۰ — اولویت فقط نمایشی است و **فیشِ گذشته را کهنه نمی‌کند**.

    `PayslipLine.seq` لحظه‌ی صدور منجمد می‌شود.
    """
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    factors = _factors(client)
    a = _factor(client, f"الف {year}", category="benefit")
    b = _factor(client, f"ب {year}", category="benefit")
    _contract(
        client,
        employee["id"],
        [
            {"factor_id": factors["base"], "amount": BASE},
            {"factor_id": a["id"], "amount": 1_000_000},
            {"factor_id": b["id"], "amount": 2_000_000},
        ],
    )
    slip = _run(client, year)[0]
    before = [(line["seq"], line["factor_name"]) for line in slip["lines"]]

    client.patch(f"/api/payroll-factors/{b['id']}", json={"display_priority": 1})
    client.patch(f"/api/payroll-factors/{a['id']}", json={"display_priority": 99})

    rows = client.get(f"/api/payslips?period_id={slip['period_id']}").json()["items"]
    after = next(r for r in rows if r["id"] == slip["id"])
    assert [(line["seq"], line["factor_name"]) for line in after["lines"]] == before


def test_display_priority_changes_no_amount(db, user, client):
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    factors = _factors(client)
    extra = _factor(client, f"حق سرپرستی {year}", category="benefit")
    client.patch(f"/api/payroll-factors/{extra['id']}", json={"display_priority": 7})
    _contract(
        client,
        employee["id"],
        [
            {"factor_id": factors["base"], "amount": BASE},
            {"factor_id": extra["id"], "amount": 4_000_000},
        ],
    )
    slip = _run(client, year)[0]
    assert _d(slip, "gross_pay") == Decimal(BASE) + Decimal(4_000_000)


# ── پروفایلِ حسابداریِ عامل ─────────────────────────────────────────────────


def test_a_factor_without_an_account_leaves_the_journal_exactly_as_it_was(db, user, client):
    """**قیدِ مرکزی.** تا وقتی هیچ عاملی حساب نگرفته، سند همان سندِ دیروز است."""
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
    expense = [x for x in _lines(db, slip) if x.debit > 0]
    assert len(expense) == 1, "بدونِ حسابِ اختصاصی باید فقط یک ردیفِ هزینه باشد"
    assert expense[0].account_id == db.query(Account).filter(Account.system_role == cc.PAYROLL_EXPENSE).first().id


def test_a_factor_with_its_own_expense_account_gets_its_own_line(db, user, client):
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    factors = _factors(client)
    own = _leaf_account(db, "5103") or _leaf_account(db, "5104")
    assert own is not None, "برای این آزمون یک حسابِ برگیِ هزینه لازم است"

    supervision = _factor(client, f"حق سرپرستی ویژه {year}", category="benefit")
    res = client.patch(
        f"/api/payroll-factors/{supervision['id']}",
        json={"expense_account_id": str(own.id)},
    )
    assert res.status_code == 200, res.text

    _contract(
        client,
        employee["id"],
        [
            {"factor_id": factors["base"], "amount": BASE},
            {"factor_id": supervision["id"], "amount": 6_000_000},
        ],
    )
    slip = _run(client, year)[0]
    lines = _lines(db, slip)
    own_line = [x for x in lines if x.account_id == own.id]
    assert len(own_line) == 1
    assert Decimal(str(own_line[0].debit)) == Decimal(6_000_000)

    debit, credit = _entry_totals(db, slip)
    assert debit == credit, "تفکیکِ حساب نباید توازن را به‌هم بزند"


def test_a_cost_center_detail_lands_on_the_split_line(db, user, client):
    from app.models.cost_center import CostCenter

    _hybrid(db)
    year = _year()
    _settings(client, year)
    own = _leaf_account(db, "5103") or _leaf_account(db, "5104")
    center = CostCenter(code=f"CC{year}", name=f"مرکز {year}", created_by_id=user.id)
    db.add(center)
    db.flush()

    supervision = _factor(client, f"حق مسئولیت مرکزدار {year}", category="benefit")
    client.patch(
        f"/api/payroll-factors/{supervision['id']}",
        json={"expense_account_id": str(own.id), "expense_detail_class": "cost_center"},
    )
    employee = _employee(client)
    res = client.post(
        "/api/salary-contracts",
        json={
            "employee_id": employee["id"],
            "effective_from": "2021-01-01",
            "cost_center_id": str(center.id),
            "lines": [
                {"factor_id": _factors(client)["base"], "amount": BASE},
                {"factor_id": supervision["id"], "amount": 3_000_000},
            ],
        },
    )
    assert res.status_code == 201, res.text

    slip = _run(client, year)[0]
    own_line = [x for x in _lines(db, slip) if x.account_id == own.id]
    assert len(own_line) == 1
    assert own_line[0].cost_center_id == center.id


def test_an_expense_account_is_refused_on_a_deduction_factor(db, user, client):
    """**دو سمت مستقل‌اند.** کسور هزینه‌ی کارفرما نیست و مزایا پرداختنیِ جدا ندارد."""
    _hybrid(db)
    own = _leaf_account(db, "5103") or _leaf_account(db, "5104")
    row = _factor(client, f"کسورِ حساب‌دار {_year()}", category="deduction")
    res = client.patch(f"/api/payroll-factors/{row['id']}", json={"expense_account_id": str(own.id)})
    assert res.status_code == 400, res.text


def test_a_detail_class_without_an_account_is_refused(db, user, client):
    _hybrid(db)
    res = client.post(
        "/api/payroll-factors",
        json={
            "name": f"عاملِ بی‌حساب {_year()}",
            "category": "benefit",
            "kind": "fixed",
            "expense_detail_class": "cost_center",
        },
    )
    assert res.status_code == 400, res.text


def test_a_group_account_is_refused(db, user, client):
    """حسابِ گروه ردیفِ سند نمی‌گیرد؛ گاردِ مرکزیِ کوبیتا همین را می‌گوید."""
    _hybrid(db)
    group = db.query(Account).filter(Account.is_group.is_(True)).first()
    row = _factor(client, f"عاملِ گروهی {_year()}", category="benefit")
    res = client.patch(f"/api/payroll-factors/{row['id']}", json={"expense_account_id": str(group.id)})
    assert res.status_code == 400, res.text


def test_a_deduction_factors_payable_account_takes_its_own_credit_line(db, user, client):
    _hybrid(db)
    year = _year()
    _settings(client, year)
    #: حسابِ تازه، چون همه‌ی «۲۱۰x»ِ seed نقشِ سیستمی دارند و گاردِ مرکزی
    #: نگاشتنشان را به‌درستی رد می‌کند.
    parent = db.query(Account).filter(Account.code == "21", Account.is_group.is_(True)).first()
    payable = Account(
        code=f"21{year % 100:02d}9", name=f"بیمه‌گر تکمیلی {year}", type="liability",
        is_group=False, parent_id=parent.id,
    )
    db.add(payable)
    db.flush()

    insurer = _factor(client, f"بیمه تکمیلی بیمه‌گر {year}", category="deduction")
    res = client.patch(
        f"/api/payroll-factors/{insurer['id']}",
        json={"payable_account_id": str(payable.id)},
    )
    assert res.status_code == 200, res.text

    employee = _employee(client)
    _contract(
        client,
        employee["id"],
        [
            {"factor_id": _factors(client)["base"], "amount": BASE},
            {"factor_id": insurer["id"], "amount": 5_000_000},
        ],
    )
    slip = _run(client, year)[0]
    own_line = [x for x in _lines(db, slip) if x.account_id == payable.id and x.credit > 0]
    assert len(own_line) == 1
    assert Decimal(str(own_line[0].credit)) == Decimal(5_000_000)

    debit, credit = _entry_totals(db, slip)
    assert debit == credit


# ── بدونِ اثرِ سند/خزانه ─────────────────────────────────────────────────────


def test_creating_or_editing_a_factor_posts_nothing(db, user, client):
    """§۸۱–§۸۶ — تعریف و فعال‌سازیِ عامل نه سند می‌زند نه حرکتِ خزانه."""
    _hybrid(db)
    before = db.query(JournalEntry).count()
    own = _leaf_account(db, "5103") or _leaf_account(db, "5104")
    row = _factor(client, f"عاملِ بی‌سند {_year()}", category="benefit")
    client.patch(
        f"/api/payroll-factors/{row['id']}",
        json={"expense_account_id": str(own.id), "display_priority": 5, "is_active": False},
    )
    assert db.query(JournalEntry).count() == before


def test_the_factor_list_reports_whether_each_one_is_in_use(db, user, client):
    _hybrid(db)
    year = _year()
    _settings(client, year)
    employee = _employee(client)
    used = _factor(client, f"عاملِ استفاده‌شده {year}", category="benefit")
    idle = _factor(client, f"عاملِ بی‌کار {year}", category="benefit")
    _contract(
        client,
        employee["id"],
        [
            {"factor_id": _factors(client)["base"], "amount": BASE},
            {"factor_id": used["id"], "amount": 1_000_000},
        ],
    )
    by_id = {r["id"]: r for r in client.get("/api/payroll-factors").json()}
    assert by_id[used["id"]]["in_use"] is True
    assert by_id[idle["id"]]["in_use"] is False
