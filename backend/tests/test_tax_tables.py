"""جدولِ مالیات: یک قاعده‌ی تاریخ‌دار، نه «نرخِ جاری».

چهار چیزی که این فصل بست:

  ۱. **باگِ پلکانِ نامرتب.** موتور فرض می‌کرد فهرست صعودی است ولی هیچ‌کس این را
     نمی‌سنجید. با پلکانِ نامرتب، مالیات بی‌صدا و بی هیچ خطایی اشتباه درمی‌آمد.

  ۲. **جدول فقط یک بُعد داشت — سال.** قاعده‌ی واقعی سه بُعد دارد:
     (تاریخِ اجرا، گروهِ مالیاتی، نوعِ محاسبه).

  ۳. **نرخِ گروه از ضرب ساخته می‌شد.** «مناطق محروم» = مالیاتِ عادی × ۵۰٪. ولی
     هر گروه جدولِ مستقل با نرخ‌های مستقل دارد؛ نصف‌بودنِ عددها یک مشاهده است،
     نه قاعده.

  ۴. **عیدی جدولِ خودش را نداشت** و مالیاتش صفر بود.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.audit import audited_models
from app.models.payroll import PayrollSettings, Payslip, TaxTable
from app.services.payroll import calc_annual_tax
from app.services.tax_tables import explain, resolve_tax_table

TODAY = date.today().isoformat()

#: پلکانِ مرجع: ۱۰٪ تا ۱۰۰، ۲۰٪ تا ۲۰۰، ۳۰٪ بعدش.
BRACKETS = [
    {"up_to": Decimal(100), "rate": Decimal("0.10")},
    {"up_to": Decimal(200), "rate": Decimal("0.20")},
    {"up_to": None, "rate": Decimal("0.30")},
]


#: **تاریخِ یکتا برای هر فراخوانی.** تست‌های `client` کامیت می‌کنند، پس جدول‌های
#: یک تست در تستِ بعدی هم دیده می‌شوند — و دامنه‌ی یکتا (تاریخ + گروه + نوع)
#: آن‌وقت بی‌ربط به کارِ تست شکست می‌خورد. هر تست تاریخِ خودش را می‌گیرد.
_DATES = iter([date(2000 + n // 12, n % 12 + 1, 1) for n in range(400)])


def _date() -> str:
    return next(_DATES).isoformat()


def _payload(**over):
    body = {
        "title": "جدول آزمایشی",
        "effective_from": _date(),
        "tax_group_id": None,
        "calculation_type": "salary",
        "brackets": [{"up_to": "100", "rate": "0.10"}, {"up_to": "200", "rate": "0.20"}, {"up_to": None, "rate": "0.30"}],
    }
    body.update(over)
    return body


def _table(client, **over):
    r = client.post("/api/tax-tables", json=_payload(**over))
    assert r.status_code == 201, r.text
    return r.json()


def _group(client, name, percent):
    r = client.post("/api/payroll-tax-groups", json={"name": name, "kind": "deprived", "percent": str(percent)})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ═══════════════ ۱) باگِ پلکانِ نامرتب ═══════════════


def test_an_unordered_bracket_list_used_to_overcharge():
    """موتور دیگر به ترتیبِ ورودی اعتماد نمی‌کند.

    با پله‌های ۱۰۰@۱۰٪ · ۲۰۰@۲۰٪ · ∞@۳۰٪ و مبنای ۳۰۰ جوابِ درست ۶۰ است.
    پیش از این اصلاح، همان پله‌ها به ترتیبِ دیگری **۱۰۰** می‌دادند — ۶۷٪ اضافه،
    بی هیچ خطایی.
    """
    ordered = [{"up_to": "100", "rate": "0.10"}, {"up_to": "200", "rate": "0.20"}, {"up_to": None, "rate": "0.30"}]
    shuffled = [{"up_to": "200", "rate": "0.20"}, {"up_to": "100", "rate": "0.10"}, {"up_to": None, "rate": "0.30"}]

    assert calc_annual_tax(Decimal(300), ordered) == Decimal(60)
    assert calc_annual_tax(Decimal(300), shuffled) == Decimal(60), "ترتیبِ ورودی نباید مالیات را عوض کند"


def test_the_api_refuses_an_unordered_bracket_list(client, db):
    """و از درِ ورودی هم رد می‌شود، نه فقط در موتور جبران."""
    r = client.post(
        "/api/tax-tables",
        json=_payload(
            brackets=[{"up_to": "200", "rate": "0.20"}, {"up_to": "100", "rate": "0.10"}, {"up_to": None, "rate": "0.30"}]
        ),
    )
    assert r.status_code == 422, r.text
    assert "صعودی" in r.text


def test_an_unbounded_bracket_in_the_middle_is_refused(client, db):
    """سقفِ نامحدودِ وسط یعنی ردیف‌های بعدی هرگز مصرف نمی‌شوند."""
    r = client.post(
        "/api/tax-tables",
        json=_payload(brackets=[{"up_to": None, "rate": "0.10"}, {"up_to": "200", "rate": "0.20"}]),
    )
    assert r.status_code == 422, r.text


def test_payroll_settings_refuse_an_unordered_list_too(client, db):
    """همان قاعده، همان تابع — فرمِ تنظیمات هم باید ردش کند."""
    r = client.put(
        "/api/payroll-settings",
        json={
            "year": 1409,
            "insurance_employee_rate": "0.07",
            "insurance_employer_rate": "0.23",
            "tax_exemption_annual": "0",
            "tax_brackets": [{"up_to": "200", "rate": "0.2"}, {"up_to": "100", "rate": "0.1"}, {"up_to": None, "rate": "0.3"}],
        },
    )
    assert r.status_code == 422, r.text


# ═══════════════ ۲) سه بُعد، نه یک سال ═══════════════


def test_a_table_is_resolved_by_date_not_by_title(client, db):
    """عنوان نمایشی است؛ حل‌کننده هرگز متنش را نمی‌خواند.

    تاریخ‌ها از شمارنده‌ی صعودی می‌آیند، پس «تازه‌ترینِ پیش از این تاریخ» همیشه
    جدولِ همین تست است — حتی اگر تست‌های قبلی جدول‌هایی جا گذاشته باشند.
    """
    first, second = _date(), _date()
    old = _table(client, title="۱۴۰۳", effective_from=first)
    new = _table(client, title="عنوانی که هیچ سالی در آن نیست", effective_from=second)

    assert str(resolve_tax_table(db, on=date.fromisoformat(first), tax_group_id=None).id) == old["id"]
    assert str(resolve_tax_table(db, on=date.fromisoformat(second), tax_group_id=None).id) == new["id"]


def test_a_table_that_has_not_started_yet_is_not_used(client, db):
    _table(client, title="آینده", effective_from="2090-01-01")
    #: پیش از هر تاریخی که این فایل می‌سازد — پس هیچ جدولی نباید پیدا شود.
    assert resolve_tax_table(db, on=date(1990, 1, 1), tax_group_id=None) is None


def test_the_same_scope_twice_is_refused(client, db):
    """دو جدولِ هم‌زمان با همان گروه و همان نوع، محاسبه را مبهم می‌کند."""
    when = _date()
    _table(client, title="اولی", effective_from=when)
    r = client.post("/api/tax-tables", json=_payload(title="دومی", effective_from=when))
    assert r.status_code == 400, r.text
    assert "تاریخ اجرا" in r.text


def test_the_same_date_with_a_different_group_is_fine(client, db):
    """یک سال، چند جدول — بُعدها مستقل‌اند."""
    when = _date()
    _table(client, title="پیش‌فرض", effective_from=when)
    group = _group(client, "مناطق محروم آزمایشی", 50)
    r = client.post("/api/tax-tables", json=_payload(title="محروم", effective_from=when, tax_group_id=group))
    assert r.status_code == 201, r.text


def test_the_same_date_with_a_different_purpose_is_fine(client, db):
    when = _date()
    _table(client, title="حقوق", effective_from=when)
    r = client.post("/api/tax-tables", json=_payload(title="عیدی", effective_from=when, calculation_type="eidi"))
    assert r.status_code == 201, r.text


def test_an_unobserved_calculation_type_is_refused(client, db):
    r = client.post("/api/tax-tables", json=_payload(calculation_type="bonus"))
    assert r.status_code == 422, r.text


# ═══════════════ ۳) گروه، جدولِ خودش را دارد ═══════════════


def test_the_exact_group_beats_the_default(client, db):
    """حکمی که گروه دارد جدولِ گروه را می‌گیرد، نه پیش‌فرض را."""
    when = _date()
    _table(client, title="پیش‌فرض", effective_from=when)
    group = _group(client, "گروه با جدول", 50)
    own = _table(
        client,
        title="جدولِ گروه",
        effective_from=when,
        tax_group_id=group,
        brackets=[{"up_to": None, "rate": "0.05"}],
    )

    picked = resolve_tax_table(db, on=date.fromisoformat(when), tax_group_id=own["tax_group_id"])
    assert str(picked.id) == own["id"]


def test_a_group_without_its_own_table_falls_back_to_the_default(client, db):
    when = _date()
    default = _table(client, title="تنها جدول", effective_from=when)
    group = _group(client, "گروه بی‌جدول", 50)

    picked = resolve_tax_table(db, on=date.fromisoformat(when), tax_group_id=group)
    assert str(picked.id) == default["id"], "بی‌جدولِ اختصاصی، پیش‌فرض جوابگوست"


def test_the_group_rate_is_the_table_not_a_multiplier(client, db):
    """**قاعده‌ی مرکزیِ این فصل.**

    نرخِ گروه از ردیف‌های جدولِ خودش می‌آید، نه از ضربِ درصدِ گروه در نرخِ عادی.
    این‌جا گروهی با درصدِ ۵۰ ساخته می‌شود ولی جدولش نرخِ ۲۵٪ دارد — و همان ۲۵٪
    باید اعمال شود، نه ۵۰٪ِ نرخِ پیش‌فرض.
    """
    when = _date()
    _table(client, title="پیش‌فرض", effective_from=when, brackets=[{"up_to": None, "rate": "0.10"}])
    group = _group(client, "گروهی با نرخِ دلبخواه", 50)
    _table(
        client,
        title="جدولِ همان گروه",
        effective_from=when,
        tax_group_id=group,
        brackets=[{"up_to": None, "rate": "0.25"}],
    )

    table = resolve_tax_table(db, on=date.fromisoformat(when), tax_group_id=group)
    from app.services.tax_tables import bracket_rows

    #: ۲۵٪ از جدول — نه ۵٪ که ضربِ ۱۰٪ در ۵۰٪ می‌داد.
    assert calc_annual_tax(Decimal(1000), bracket_rows(table)) == Decimal(250)


# ═══════════════ ۴) توضیح‌پذیری ═══════════════


def test_the_breakdown_reconciles_with_the_total():
    """جمعِ «مبلغ جزء»ها باید همان مالیاتِ کل باشد."""
    rows = [{"up_to": "100", "rate": "0.10"}, {"up_to": "200", "rate": "0.20"}, {"up_to": None, "rate": "0.30"}]
    steps = explain(rows, Decimal(300))

    assert [s.consumed for s in steps] == [Decimal(100), Decimal(100), Decimal(100)]
    assert [s.tax for s in steps] == [Decimal(10), Decimal(20), Decimal(30)]
    assert steps[-1].cumulative == calc_annual_tax(Decimal(300), rows)


def test_the_breakdown_stops_at_the_consumed_bracket():
    rows = [{"up_to": "100", "rate": "0.10"}, {"up_to": "200", "rate": "0.20"}, {"up_to": None, "rate": "0.30"}]
    steps = explain(rows, Decimal(150))
    assert len(steps) == 2
    assert steps[-1].consumed == Decimal(50)


def test_a_zero_base_has_no_steps():
    assert explain([{"up_to": None, "rate": "0.10"}], Decimal(0)) == []


def test_a_decimal_rate_survives():
    """۷٫۵٪ باید دقیقاً ۷٫۵٪ بماند — نه ۷٪، نه ۸٪."""
    assert calc_annual_tax(Decimal(1000), [{"up_to": None, "rate": "0.075"}]) == Decimal(75)


def test_a_decimal_rate_round_trips_through_the_api(client, db):
    table = _table(client, brackets=[{"up_to": None, "rate": "0.075"}])
    assert Decimal(str(table["brackets"][0]["rate"])) == Decimal("0.075")


def test_the_from_amount_is_derived_not_stored(client, db):
    """«از مبلغ» ستون نیست — از سقفِ ردیفِ قبل می‌آید، پس دو نما از یک عدد نمی‌سازد."""
    table = _table(client)
    lows = [Decimal(str(b["from_amount"])) for b in table["brackets"]]
    assert lows == [Decimal(0), Decimal(100), Decimal(200)]


# ═══════════════ ۵) ردیابی و تاریخچه ═══════════════


def _settings(db, year=1405):
    if db.query(PayrollSettings).filter(PayrollSettings.year == year).first():
        return
    db.add(
        PayrollSettings(
            year=year,
            insurance_employee_rate=Decimal("0.07"),
            insurance_employer_rate=Decimal("0.23"),
            tax_exemption_annual=Decimal("1200000000"),
            tax_brackets=[{"up_to": "2000000000", "rate": "0.1"}, {"up_to": None, "rate": "0.2"}],
        )
    )
    db.flush()


def _employee(client, *, first, last, national_id):
    contact_id = client.post(
        "/api/contacts",
        json={"name": f"{first} {last}", "type": "customer", "national_id": national_id,
              "first_name": first, "last_name": last, "is_employee": True},
    ).json()["id"]
    return contact_id


def _payroll(client, db, contact_id, *, month, year=1405):
    _settings(db, year)
    factors = client.post("/api/payroll-factors/defaults", json={}).json()
    base = next(f["id"] for f in factors if f.get("system_key") == "base")
    r = client.post(
        "/api/salary-contracts",
        json={"contact_id": contact_id, "effective_from": "2026-01-01",
              "lines": [{"factor_id": base, "amount": 500_000_000}]},
    )
    assert r.status_code == 201, r.text
    period = client.post("/api/payroll-periods", json={"year": year, "month": month}).json()
    issued = client.post(f"/api/payroll-periods/{period['id']}/generate-payslips", json={})
    assert issued.status_code == 200, issued.text
    return period["id"], issued.json()


def test_a_payslip_records_which_rule_made_its_tax(client, db):
    """`tax_amount` دیگر یک عددِ بی‌توضیح نیست."""
    _table(client, title="جدولِ مؤثر", effective_from="1995-01-01",
           brackets=[{"up_to": "2000000000", "rate": "0.1"}, {"up_to": None, "rate": "0.2"}])
    contact = _employee(client, first="مالیات", last="دهنده", national_id="9000000001")
    _, slips = _payroll(client, db, contact, month=1)

    db.expire_all()
    payslip = db.get(Payslip, slips[0]["id"])
    assert payslip.tax_table_id is not None, "فیش باید بگوید از کدام جدول آمد"

    r = client.get(f"/api/payslips/{payslip.id}/tax-breakdown")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tax_table_title"] == "جدولِ مؤثر"
    assert body["steps"], "تفکیک نباید خالی باشد"


def test_editing_a_table_does_not_move_an_issued_payslip(client, db):
    """اعدادِ فیش عکس‌اند؛ ویرایشِ جدول محاسبه‌ی گذشته را عوض نمی‌کند."""
    table = _table(client, title="جدولِ ویرایش‌شونده", effective_from="1995-01-01",
                   brackets=[{"up_to": "2000000000", "rate": "0.1"}, {"up_to": None, "rate": "0.2"}])
    contact = _employee(client, first="ثابت", last="مانده", national_id="9000000002")
    _, slips = _payroll(client, db, contact, month=2)
    before = Decimal(str(slips[0]["tax_amount"]))

    r = client.patch(
        f"/api/tax-tables/{table['id']}",
        json=_payload(title="جدولِ ویرایش‌شونده", effective_from="1995-01-01",
                      brackets=[{"up_to": None, "rate": "0.9"}]),
    )
    assert r.status_code == 200, r.text

    db.expire_all()
    after = Decimal(str(db.get(Payslip, slips[0]["id"]).tax_amount))
    assert after == before, "ویرایشِ جدول نباید فیشِ صادرشده را تکان دهد"


def test_a_used_table_cannot_be_deleted(client, db):
    """حذفِ جدولِ استفاده‌شده یعنی توضیحِ مالیاتِ گذشته برای همیشه برود."""
    table = _table(client, title="جدولِ پرکاربرد", effective_from="1995-01-01",
                   brackets=[{"up_to": "2000000000", "rate": "0.1"}, {"up_to": None, "rate": "0.2"}])
    contact = _employee(client, first="پر", last="کاربرد", national_id="9000000003")
    _payroll(client, db, contact, month=3)

    r = client.delete(f"/api/tax-tables/{table['id']}")
    assert r.status_code == 400, r.text

    listed = client.get("/api/tax-tables").json()
    row = next(t for t in listed if t["id"] == table["id"])
    assert row["in_use"] is True


def test_an_unused_table_can_be_deleted(client, db):
    table = _table(client, title="جدولِ بی‌استفاده", effective_from=_date())
    assert client.delete(f"/api/tax-tables/{table['id']}").status_code == 204


def test_the_settings_form_mirrors_into_the_default_table(client, db):
    """سالِ تازه از فرمِ تنظیمات هم باید جدول بسازد، وگرنه دو راهِ پیکربندی از هم عقب می‌مانند."""
    r = client.put(
        "/api/payroll-settings",
        json={
            "year": 1410,
            "insurance_employee_rate": "0.07",
            "insurance_employer_rate": "0.23",
            "tax_exemption_annual": "0",
            "tax_brackets": [{"up_to": "500", "rate": "0.1"}, {"up_to": None, "rate": "0.2"}],
        },
    )
    assert r.status_code == 200, r.text

    from app.jalali import jalali_to_gregorian

    table = resolve_tax_table(db, on=jalali_to_gregorian(1410, 6, 1), tax_group_id=None)
    assert table is not None, "فرمِ تنظیمات باید جدولِ پیش‌فرض را بسازد"
    assert [str(b.up_to) if b.up_to is not None else None for b in table.brackets] == ["500", None]


def test_the_table_is_audited():
    assert TaxTable in audited_models()


# ═══════════════ ۶) عیدی جدولِ خودش را دارد ═══════════════


def test_eidi_uses_its_own_table_not_the_salary_one(client, db):
    """جدولِ حقوق برای عیدی به کار نمی‌رود — آستانه‌هایشان یکی نیست."""
    from app.services.tax_tables import eidi_tax

    _table(client, title="حقوق عیدی‌تست", effective_from=_date(), brackets=[{"up_to": None, "rate": "0.30"}])
    assert eidi_tax(db, Decimal(1000), on=date(2026, 1, 1)) == Decimal(0), "بی جدولِ عیدی، مالیاتی نیست"

    _table(client, title="عیدی", effective_from="1995-01-01", calculation_type="eidi",
           brackets=[{"up_to": None, "rate": "0.10"}])
    assert eidi_tax(db, Decimal(1000), on=date(2026, 1, 1)) == Decimal(100), "باید جدولِ عیدی را بگیرد"


def test_eidi_without_a_table_keeps_todays_behaviour(client, db):
    """رفتارِ امروز حفظ می‌شود: بی جدولِ عیدی، عیدی بی‌مالیات است.

    ساختنِ خودکارِ جدولِ عیدی یعنی یک مهاجرت بی‌خبر مالیات کسر کند — و آن تصمیمِ
    کاربر است، نه ما.
    """
    from app.services.tax_tables import eidi_tax

    assert eidi_tax(db, Decimal(50_000_000), on=date(2026, 1, 1)) == Decimal(0)


# ═══════════════ ۷) بی‌سند، بی‌خزانه ═══════════════


@pytest.mark.parametrize("purpose", ["salary", "eidi"])
def test_defining_a_table_posts_nothing(client, db, purpose):
    from app.models.accounting import JournalEntry
    from app.models.treasury import TreasuryTransaction

    before_entries = db.query(JournalEntry).count()
    before_treasury = db.query(TreasuryTransaction).count()

    _table(client, title=f"جدولِ بی‌اثر {purpose}", effective_from=_date(), calculation_type=purpose)
    db.expire_all()

    assert db.query(JournalEntry).count() == before_entries, "تعریف جدول سند نمی‌زند"
    assert db.query(TreasuryTransaction).count() == before_treasury, "و خزانه را تکان نمی‌دهد"


def test_the_table_carries_no_branch_reference(client, db):
    """جدولِ نرخ‌ها شعبه‌محور نیست؛ یک جدول را چند شعبه استفاده می‌کنند."""
    table = _table(client, title="جدولِ بی‌شعبه", effective_from=_date())
    assert "tax_branch_id" not in table
