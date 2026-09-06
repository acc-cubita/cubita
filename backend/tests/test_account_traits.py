"""ویژگی‌های حساب — شش پرچمِ فرمِ ویرایش، و پیگیریِ ردیفِ سند.

قیدِ حاکم بر همه‌ی این تست‌ها: **هیچ‌کدام از این پرچم‌ها نباید رفتارِ چارتِ موجود را
عوض کند.** مهاجرتِ ۰۰۸۸ هیچ ردیفی را backfill نکرد، پس اگر پیش‌فرضی روزی طوری
تغییر کند که گزارشی خالی یا ثبتی مسدود شود، تست‌های این فایل قرمز می‌شوند.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.user import User
from app.services import accounting_ops
from app.services import reports as reports_service

#: پرچم و پیش‌فرضش — عیناً همان چیزی که مهاجرت روی ستون‌ها گذاشت.
TRAIT_DEFAULTS = {
    "nature_control": False,
    "is_fx": False,
    "fx_revaluable": False,
    "accepts_tafsili": False,
    "has_tracking": False,
    "in_management_reports": True,
}


def _account(db, code: str) -> Account:
    return db.query(Account).filter(Account.code == code).one()


def _user_id(db):
    return db.query(User.id).scalar()


def _post(db, *, debit_code: str, credit_code: str, amount: int) -> JournalEntry:
    entry = JournalEntry(entry_date=date(2026, 1, 1), description="آزمون", created_by_id=_user_id(db))
    entry.lines = [
        JournalLine(account_id=_account(db, debit_code).id, debit=Decimal(amount), credit=Decimal(0)),
        JournalLine(account_id=_account(db, credit_code).id, debit=Decimal(0), credit=Decimal(amount)),
    ]
    db.add(entry)
    db.flush()
    return entry


# ── پیش‌فرض‌ها ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("trait,expected", TRAIT_DEFAULTS.items())
def test_seeded_chart_carries_the_documented_defaults(db, trait, expected):
    """چارتِ کاشته‌شده باید دقیقاً پیش‌فرضِ مهاجرت را داشته باشد، نه چیزِ دیگری."""
    values = {getattr(a, trait) for a in db.query(Account).all()}
    assert values == {expected}, f"«{trait}» باید در کلِ چارت {expected} باشد"


def test_traits_round_trip_through_the_api(db, user, client):
    account = db.query(Account).filter(Account.is_group.is_(False)).order_by(Account.code).first()

    res = client.patch(
        f"/api/accounts/{account.id}",
        json={"nature_control": True, "is_fx": True, "fx_revaluable": True, "has_tracking": True},
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["nature_control"] is True
    assert body["is_fx"] is True
    assert body["fx_revaluable"] is True
    assert body["has_tracking"] is True
    #: فیلدهای نیامده دست‌نخورده می‌مانند — `exclude_unset` باید واقعاً کار کند،
    #: وگرنه فرمی که فقط یک تیک می‌فرستد بقیه را به پیش‌فرض برمی‌گرداند.
    assert body["in_management_reports"] is True
    assert body["accepts_tafsili"] is False


# ── ارزی و تسعیرپذیر ─────────────────────────────────────────────────────────


def test_revaluable_without_fx_is_rejected_on_create(db, user, client):
    grp = db.query(Account).filter(Account.is_group.is_(True)).order_by(Account.code).first()
    code = client.get(f"/api/accounts/next-code?parent_id={grp.id}").json()["code"]

    res = client.post(
        "/api/accounts",
        json={"code": code, "name": "x", "type": grp.type, "parent_id": str(grp.id), "fx_revaluable": True},
    )

    assert res.status_code == 400, res.text
    assert "ارزی" in res.json()["detail"]


def test_revaluable_without_fx_is_rejected_on_update(db, user, client):
    account = db.query(Account).filter(Account.is_group.is_(False)).order_by(Account.code).first()

    res = client.patch(f"/api/accounts/{account.id}", json={"fx_revaluable": True})

    assert res.status_code == 400, res.text


def test_turning_fx_off_while_revaluable_is_rejected(db, user, client):
    """قید روی *نتیجه* سنجیده می‌شود، نه روی ورودی.

    بدونِ این، فرستادنِ تنهای `is_fx=false` حساب را در حالتی می‌گذاشت که قیدِ
    پایگاه‌داده ردش می‌کرد و کاربر به‌جای پیامِ فارسی، خطای خامِ IntegrityError
    می‌دید.
    """
    account = db.query(Account).filter(Account.is_group.is_(False)).order_by(Account.code).first()
    account.is_fx = True
    account.fx_revaluable = True
    db.flush()

    res = client.patch(f"/api/accounts/{account.id}", json={"is_fx": False})

    assert res.status_code == 400, res.text


def test_revaluation_still_sees_an_untouched_account(db, user):
    """**قیدِ اصلیِ تسعیر.** پیش‌فرضِ خاموشِ `fx_revaluable` نباید صفحه‌ی تسعیر را
    خالی کند.

    اگر این پرچم «انتخاب» بود نه «انصراف»، مهاجرتِ ۰۰۸۸ همه‌ی حساب‌های ارزیِ موجود
    را یک‌شبه از سندِ تسعیر بیرون می‌انداخت — بی‌هیچ خطایی، فقط یک فهرستِ خالی.
    """
    cash = _account(db, "1101")
    revenue = _account(db, "4101")
    entry = JournalEntry(entry_date=date(2026, 1, 1), description="ارزی", created_by_id=_user_id(db))
    entry.lines = [
        JournalLine(
            account_id=cash.id, debit=Decimal(1_000_000), credit=Decimal(0),
            currency_code="USD", fx_amount=Decimal(100), fx_rate=Decimal(10_000),
        ),
        JournalLine(account_id=revenue.id, debit=Decimal(0), credit=Decimal(1_000_000)),
    ]
    db.add(entry)
    db.flush()
    _rate(db, "USD", date(2026, 1, 1), 12_000)

    assert cash.is_fx is False and cash.fx_revaluable is False
    preview = accounting_ops.fx_revaluation_preview(db, date(2026, 1, 1))

    assert any(i["account_id"] == cash.id for i in preview["items"]), "حسابِ دست‌نخورده باید تسعیر شود"


def test_marking_fx_without_revaluable_opts_the_account_out(db, user):
    """و راهِ کنارگذاشتنِ یک حساب: «ارزی هست، ولی تسعیرش نکن»."""
    cash = _account(db, "1101")
    revenue = _account(db, "4101")
    entry = JournalEntry(entry_date=date(2026, 1, 1), description="ارزی", created_by_id=_user_id(db))
    entry.lines = [
        JournalLine(
            account_id=cash.id, debit=Decimal(1_000_000), credit=Decimal(0),
            currency_code="USD", fx_amount=Decimal(100), fx_rate=Decimal(10_000),
        ),
        JournalLine(account_id=revenue.id, debit=Decimal(0), credit=Decimal(1_000_000)),
    ]
    db.add(entry)
    db.flush()
    _rate(db, "USD", date(2026, 1, 1), 12_000)

    cash.is_fx = True
    cash.fx_revaluable = False
    db.flush()

    preview = accounting_ops.fx_revaluation_preview(db, date(2026, 1, 1))

    assert not any(i["account_id"] == cash.id for i in preview["items"])


def _rate(db, code: str, on: date, value: int) -> None:
    from app.models.currency import ExchangeRate

    db.add(
        ExchangeRate(currency_code=code, rate_date=on, rate=Decimal(value), created_by_id=_user_id(db))
    )
    db.flush()


# ── کنترلِ ماهیت طی دوره ─────────────────────────────────────────────────────


def test_nature_report_is_unfiltered_by_default(db):
    """**قیدِ اصلیِ گزارش.** تیکِ تازه نباید گزارشِ موجود را بی‌صدا خالی کند."""
    _post(db, debit_code="5104", credit_code="1101", amount=1_000_000)

    rows = reports_service.get_nature_violations(db, None, None)

    assert any(r["account_code"] == "1101" for r in rows), "بدونِ درخواستِ صریح، همه‌چیز می‌آید"
    assert all(r["nature_control"] is False for r in rows), "و ستونِ کنترل هم گزارش می‌شود"


def test_controlled_only_narrows_the_report(db):
    _post(db, debit_code="5104", credit_code="1101", amount=1_000_000)

    assert reports_service.get_nature_violations(db, None, None, controlled_only=True) == []

    _account(db, "1101").nature_control = True
    db.flush()

    rows = reports_service.get_nature_violations(db, None, None, controlled_only=True)
    assert [r["account_code"] for r in rows] == ["1101"]
    assert rows[0]["nature_control"] is True


def test_controlled_only_is_opt_in_over_http(db, user, client):
    _post(db, debit_code="5104", credit_code="1101", amount=1_000_000)

    assert client.get("/api/reports/nature-violations").json(), "پیش‌فرض: بدونِ صافی"
    assert client.get("/api/reports/nature-violations?controlled_only=true").json() == []


# ── نمایش در گزارشاتِ مدیریتی ────────────────────────────────────────────────


def test_trial_balance_is_unfiltered_by_default(db, user, client):
    _post(db, debit_code="5104", credit_code="1101", amount=1_000_000)
    _account(db, "1101").in_management_reports = False
    db.flush()

    codes = {r["account_code"] for r in client.get("/api/reports/trial-balance").json()}

    assert "1101" in codes, "ترازِ کامل مبنای کنترلِ توازن است و نباید صافی بخورد"


def test_management_only_drops_the_excluded_account(db, user, client):
    _post(db, debit_code="5104", credit_code="1101", amount=1_000_000)
    _account(db, "1101").in_management_reports = False
    db.flush()

    codes = {
        r["account_code"] for r in client.get("/api/reports/trial-balance?management_only=true").json()
    }

    assert "1101" not in codes
    assert "5104" in codes, "بقیه سرِ جایشان می‌مانند"


# ── تفصیلی‌پذیری ─────────────────────────────────────────────────────────────


def test_tafsili_can_always_be_turned_on(db, user, client):
    """روشن‌کردن هیچ‌وقت قفل نمی‌شود — ردیف‌های بعدی تفصیلی می‌گیرند و ضرری ندارد."""
    account = _account(db, "1101")
    _post(db, debit_code="1101", credit_code="4101", amount=1000)

    res = client.patch(f"/api/accounts/{account.id}", json={"accepts_tafsili": True})

    assert res.status_code == 200, res.text
    assert res.json()["accepts_tafsili"] is True


def test_tafsili_cannot_be_turned_off_once_lines_carry_one(db, user, client):
    """**قفلِ یک‌طرفه.** خاموش‌کردن گزارشِ تفصیلی را نصفه می‌کند.

    مشخصاتِ سپیدار قفلِ دوطرفه می‌خواهد («بعد از یک سند، پرچم قفل، مگر همه‌ی اسناد
    پاک شوند»). در کوبیتا آن یعنی قفلِ ابدی، چون سند هرگز پاک نمی‌شود و فقط باطل
    می‌شود. این قاعده همان ضرر را می‌بندد بدونِ ابدی‌کردنِ قفل: تا وقتی هیچ ردیفی
    تفصیلی نگرفته، پرچم آزاد است.
    """
    account = _account(db, "1101")
    account.accepts_tafsili = True
    db.flush()
    analytic = _an_analytic(db)
    entry = _post(db, debit_code="1101", credit_code="4101", amount=1000)
    entry.lines[0].analytic_id = analytic.id
    db.flush()

    res = client.patch(f"/api/accounts/{account.id}", json={"accepts_tafsili": False})

    assert res.status_code == 409, res.text


def test_tafsili_can_be_turned_off_while_no_line_used_one(db, user, client):
    """ولی تا وقتی هیچ ردیفی تفصیلی نگرفته، برداشتنش آزاد است."""
    account = _account(db, "1101")
    account.accepts_tafsili = True
    db.flush()
    _post(db, debit_code="1101", credit_code="4101", amount=1000)

    res = client.patch(f"/api/accounts/{account.id}", json={"accepts_tafsili": False})

    assert res.status_code == 200, res.text


def test_tafsili_flag_does_not_gate_building_the_tree(db, user, client):
    """**قیدِ جداسازی.** این پرچم درباره‌ی تفصیلیِ شناور است، نه زیرشاخه‌ی درختی.

    اگر روزی کسی دوباره ساختِ زیرحساب را به این پرچم گره بزند، همان اشتباهی تکرار
    می‌شود که یک‌بار شد: کدینگِ چهارسطحی (بانک ملی زیرِ بانک) و بُعدِ تحلیلیِ ردیفِ
    سند دو چیزِ متفاوت‌اند.
    """
    parent = db.query(Account).filter(Account.is_group.is_(False)).order_by(Account.code).first()
    assert parent.accepts_tafsili is False

    code = client.get(f"/api/accounts/next-code?parent_id={parent.id}").json()["code"]
    res = client.post(
        "/api/accounts",
        json={"code": code, "name": "زیرشاخه", "type": parent.type, "parent_id": str(parent.id)},
    )

    assert res.status_code == 201, res.text


# ── تفصیلیِ اجباری در ثبتِ سند ───────────────────────────────────────────────


def _an_analytic(db):
    from app.models.analytic import AnalyticAccount

    row = db.query(AnalyticAccount).first()
    if row is None:
        row = AnalyticAccount(code="T1", name="تفصیلیِ آزمون", created_by_id=_user_id(db))
        db.add(row)
        db.flush()
    return row


def _payload(db, *, code: str, other: str, **line_extra) -> dict:
    return {
        "entry_date": "2026-01-01",
        "description": "آزمونِ تفصیلی",
        "lines": [
            {"account_id": str(_account(db, code).id), "debit": 1000, "credit": 0, **line_extra},
            {"account_id": str(_account(db, other).id), "debit": 0, "credit": 1000},
        ],
    }


def test_tafsili_account_rejects_a_line_without_one(db, user, client):
    """**قیدِ اصلی.** حسابِ تفصیل‌پذیر بدونِ تفصیلی سوراخی در همان گزارشی می‌سازد
    که کاربر برایش پرچم را روشن کرده."""
    _account(db, "1101").accepts_tafsili = True
    db.flush()

    res = client.post("/api/journal-entries", json=_payload(db, code="1101", other="4101"))

    assert res.status_code == 400, res.text
    assert "تفصیلی" in res.json()["detail"]
    assert "1101" in res.json()["detail"], "پیام باید بگوید کدام حساب"


def test_tafsili_supplied_on_the_line_is_accepted(db, user, client):
    _account(db, "1101").accepts_tafsili = True
    db.flush()
    analytic = _an_analytic(db)

    res = client.post(
        "/api/journal-entries",
        json=_payload(db, code="1101", other="4101", analytic_id=str(analytic.id)),
    )

    assert res.status_code == 201, res.text


def test_entry_level_tafsili_satisfies_the_guard(db, user, client):
    """تفصیلیِ سطحِ سند به ردیف‌ها ارث می‌رسد، پس گارد باید *پس از* ارث‌بری بسنجد.

    اگر گارد ورودیِ خام را می‌سنجید، سندی که تفصیلی‌اش را یک‌بار بالا داده رد می‌شد.
    """
    _account(db, "1101").accepts_tafsili = True
    db.flush()
    analytic = _an_analytic(db)
    payload = _payload(db, code="1101", other="4101")
    payload["analytic_id"] = str(analytic.id)

    res = client.post("/api/journal-entries", json=payload)

    assert res.status_code == 201, res.text
    assert all(line["analytic_id"] == str(analytic.id) for line in res.json()["lines"])


def test_a_plain_account_never_needs_tafsili(db, user, client):
    """حسابِ بی‌پرچم دست‌نخورده می‌ماند — این گارد فقط به تیک‌خورده‌ها کار دارد."""
    res = client.post("/api/journal-entries", json=_payload(db, code="1101", other="4101"))

    assert res.status_code == 201, res.text


# ── پیگیری ───────────────────────────────────────────────────────────────────


def _entry_payload(db, *, tracked_code: str, other_code: str, **line_extra) -> dict:
    return {
        "entry_date": "2026-01-01",
        "description": "آزمونِ پیگیری",
        "lines": [
            {"account_id": str(_account(db, tracked_code).id), "debit": 1000, "credit": 0, **line_extra},
            {"account_id": str(_account(db, other_code).id), "debit": 0, "credit": 1000},
        ],
    }


def test_tracking_is_stored_on_the_line(db, user, client):
    _account(db, "1101").has_tracking = True
    db.flush()

    res = client.post(
        "/api/journal-entries",
        json=_entry_payload(
            db, tracked_code="1101", other_code="4101",
            tracking_no="حواله ۱۲۳", tracking_date="2026-01-05",
        ),
    )

    assert res.status_code == 201, res.text
    tracked = next(line for line in res.json()["lines"] if line["tracking_no"])
    assert tracked["tracking_no"] == "حواله ۱۲۳"
    assert tracked["tracking_date"] == "2026-01-05"


def test_tracking_on_a_plain_account_is_rejected_not_dropped(db, user, client):
    """**قیدِ اصلیِ پیگیری.** ارجاعِ کاربر نباید بی‌صدا دور ریخته شود.

    اگر سرور فقط نادیده‌اش می‌گرفت، سند با موفقیت ثبت می‌شد و شماره‌ی حواله برای
    همیشه گم بود — بی‌آنکه کسی خطایی ببیند.
    """
    assert _account(db, "1101").has_tracking is False

    res = client.post(
        "/api/journal-entries",
        json=_entry_payload(db, tracked_code="1101", other_code="4101", tracking_no="حواله ۱۲۳"),
    )

    assert res.status_code == 400, res.text
    assert "پیگیری" in res.json()["detail"]
    assert "1101" in res.json()["detail"], "پیام باید بگوید کدام حساب"


def test_entries_without_tracking_are_untouched(db, user, client):
    """سندِ معمولی نباید هیچ اثری از این قابلیت ببیند."""
    res = client.post("/api/journal-entries", json=_entry_payload(db, tracked_code="1101", other_code="4101"))

    assert res.status_code == 201, res.text
    assert all(line["tracking_no"] is None for line in res.json()["lines"])


def test_blank_tracking_number_is_not_a_value(db, user, client):
    """رشته‌ی خالیِ فرم همان «ندارد» است — وگرنه سندِ دست‌نخورده هم رد می‌شد."""
    assert _account(db, "1101").has_tracking is False

    res = client.post(
        "/api/journal-entries",
        json=_entry_payload(db, tracked_code="1101", other_code="4101", tracking_no="   "),
    )

    assert res.status_code == 201, res.text


def test_voiding_carries_the_tracking_reference(db, user, client):
    """سندِ برگشتی باید با همان ارجاع پیدا شود که سندِ اصلی."""
    _account(db, "1101").has_tracking = True
    db.flush()
    created = client.post(
        "/api/journal-entries",
        json=_entry_payload(
            db, tracked_code="1101", other_code="4101",
            tracking_no="حواله ۹۹", tracking_date="2026-01-05",
        ),
    )
    assert created.status_code == 201, created.text

    voided = client.post(
        f"/api/journal-entries/{created.json()['id']}/void",
        json={"void_date": "2026-01-10", "reason": "آزمون"},
    )
    assert voided.status_code == 200, voided.text

    reversal = db.get(JournalEntry, voided.json()["reversal_entry_id"])
    assert {line.tracking_no for line in reversal.lines} == {"حواله ۹۹", None}


# ── سه‌گانه‌ی ارزی ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "extra,missing_word",
    [
        ({"currency_code": "USD", "fx_amount": 100}, "نرخ"),
        ({"currency_code": "USD", "fx_rate": 10000}, "مبلغِ ارزی"),
        ({"fx_amount": 100, "fx_rate": 10000}, "ارز"),
        ({"currency_code": "USD"}, "مبلغِ ارزی"),
    ],
)
def test_partial_fx_line_is_rejected(db, user, client, extra, missing_word):
    """**قیدِ اصلیِ ارز.** ردیفِ نیمه‌کاره بی‌صدا خراب می‌شود، نه با خطا.

    بدونِ نرخ، نرخِ لحظه‌ی ثبت برای همیشه گم می‌شود و حسابرسی ناممکن؛ بدونِ مبلغِ
    ارزی، ردیف از `fx_revaluation_preview` بیرون می‌افتد و تسعیرِ پایانِ دوره کمتر
    از واقعیت درمی‌آید — بی‌آنکه جایی خطایی بیاید.
    """
    res = client.post(
        "/api/journal-entries", json=_payload(db, code="1101", other="4101", **extra)
    )

    assert res.status_code == 422, res.text
    assert missing_word in res.text


def test_complete_fx_line_is_accepted(db, user, client):
    res = client.post(
        "/api/journal-entries",
        json=_payload(
            db, code="1101", other="4101",
            currency_code="USD", fx_amount=100, fx_rate=10000,
        ),
    )

    assert res.status_code == 201, res.text
    line = next(l for l in res.json()["lines"] if l["currency_code"])
    assert line["fx_rate"] is not None, "نرخِ لحظه‌ی ثبت باید ذخیره شود"


def test_a_plain_rial_line_is_untouched(db, user, client):
    """هیچ‌کدام از سه فیلد = ردیفِ ریالیِ معمولی. اکثریتِ قاطعِ ردیف‌ها همین‌اند."""
    res = client.post("/api/journal-entries", json=_payload(db, code="1101", other="4101"))

    assert res.status_code == 201, res.text


def test_zero_or_negative_rate_is_rejected(db, user, client):
    res = client.post(
        "/api/journal-entries",
        json=_payload(
            db, code="1101", other="4101", currency_code="USD", fx_amount=100, fx_rate=0
        ),
    )

    assert res.status_code == 422, res.text


# ── خام‌سازیِ درختواره ───────────────────────────────────────────────────────


def test_wipe_is_refused_once_anything_is_posted(db, user, client):
    """**گاردِ خام‌سازی.** با یک سند هم رد می‌شود — نه «تا جایی که می‌شود پاک کن»،
    چون نتیجه‌ی نصفه بدتر از انجام‌نشدن است."""
    _post(db, debit_code="1101", credit_code="4101", amount=1000)

    res = client.delete("/api/accounts")

    assert res.status_code == 409, res.text
    assert db.query(Account).count() > 0, "و هیچ حسابی هم نباید رفته باشد"


def test_wipe_clears_the_chart_when_nothing_is_posted(db, user, client):
    """بدونِ سند، هیچ عددی به هیچ حسابی گره نخورده، پس خام‌سازی هیچ دفتری را
    نمی‌شکند — همان گاردی که خودِ مشخصات می‌گوید."""
    before = db.query(Account).count()
    assert before > 0

    res = client.delete("/api/accounts")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["deleted"] > 0
    #: هرچه ماند باید دلیل داشته باشد؛ عددِ خالی به کاربر نمی‌گوید چرا.
    assert all(k["reason"] for k in body["kept"])
    assert body["deleted"] + len(body["kept"]) == before
