"""فرمِ کاملِ طرف حساب — هویت، نقشِ واسطه، کنترلِ اعتبار، و پیوند به تفصیلی و کارمند.

قیدِ اصلیِ این قابلیت که تست‌ها نگهش می‌دارند: **کد و عنوانِ تفصیلیِ طرف حساب ستونِ
`contacts` نیستند.** به `analytic_accounts` وصل می‌شوند تا ردیفِ سند، گزارشِ تفصیلی و
فرمِ طرف حساب از یک منبع بخوانند. اگر روزی کسی این را به دو ستونِ متنی تبدیل کند،
`test_tafsili_is_a_link_not_a_copy` قرمز می‌شود.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models.analytic import AnalyticAccount
from app.models.inventory import Contact
from app.models.tenant import Tenant
from app.tenant_context import session_tenant


def _set_mode(db, mode: str) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = mode
    db.flush()


def _payload(**extra) -> dict:
    return {"name": "آزمون", "type": "customer", **extra}


# ── پیوندِ تفصیلی ─────────────────────────────────────────────────────────────


def test_tafsili_is_a_link_not_a_copy(db, user, client):
    """**قیدِ اصلی.** کدِ تفصیلی در `analytic_accounts` می‌نشیند، نه روی طرف‌حساب."""
    _set_mode(db, "hybrid")

    res = client.post(
        "/api/contacts",
        json=_payload(tafsili_code="9001", tafsili_title="مشتریِ آزمون", tafsili_title2="Test"),
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["tafsili_code"] == "9001"
    assert body["analytic_id"] is not None

    #: و واقعاً یک تفصیلیِ مستقل ساخته شده که در فهرستِ تفصیلی‌ها هم دیده می‌شود.
    row = db.query(AnalyticAccount).filter(AnalyticAccount.code == "9001").one()
    assert row.name == "مشتریِ آزمون"
    assert row.name2 == "Test"
    assert {c.name for c in Contact.__table__.columns}.isdisjoint({"tafsili_code", "tafsili_title"})


def test_strict_mode_generates_a_code_when_none_is_given(db, user, client):
    """در «اجباری» طرف‌حساب حتماً تفصیلی می‌گیرد — و کدِ خالی یعنی «خودت بده».

    این تست یک‌بار عوض شده: اول ادعا می‌کرد کدِ خالی خطای ۴۰۰ می‌دهد. کاربر گفت کد
    باید خودکار ساخته شود، و درست هم هست: شماره‌ی تفصیلی ارجاعِ داخلی است و کاربر
    معمولاً حرفی درباره‌اش ندارد؛ اجبار کردنش فقط یک مانع بود. آنچه اجباری ماند
    *داشتنِ* تفصیلی است، نه *تایپ کردنِ* کدش.
    """
    _set_mode(db, "strict")

    res = client.post("/api/contacts", json=_payload())

    assert res.status_code == 201, res.text
    assert res.json()["analytic_id"] is not None, "تفصیلی باید ساخته شده باشد"
    assert res.json()["tafsili_code"], "و کدش خودکار پر شده باشد"


def test_the_generated_code_is_unique_across_contacts(db, user, client):
    """دو طرف‌حسابِ پشتِ‌هم نباید کدِ یکسان بگیرند."""
    _set_mode(db, "strict")

    first = client.post("/api/contacts", json=_payload(name="اولی")).json()
    second = client.post("/api/contacts", json=_payload(name="دومی")).json()

    assert first["tafsili_code"] != second["tafsili_code"]


def test_a_duplicate_title_is_reported_but_not_refused(db, user, client):
    """**قاعده‌ی عنوانِ تکراری.** دو نفرِ هم‌نام واقعاً ممکن‌اند، پس رد نمی‌شود —
    ولی فرم باید بتواند قرمزش کند، و این نقطه‌ی پایانی همان را می‌گوید."""
    _set_mode(db, "hybrid")
    client.post("/api/contacts", json=_payload(tafsili_code="6001", tafsili_title="رجبی بهنام"))

    taken = client.get("/api/contacts/tafsili-title-taken", params={"title": "رجبی بهنام"})
    free = client.get("/api/contacts/tafsili-title-taken", params={"title": "کسِ دیگر"})

    assert taken.json()["taken"] is True
    assert free.json()["taken"] is False

    #: و ساختنِ دومی با همان عنوان باید *بگیرد* — هشدار است، نه گارد.
    res = client.post("/api/contacts", json=_payload(tafsili_code="6002", tafsili_title="رجبی بهنام"))
    assert res.status_code == 201, res.text


def test_strict_mode_accepts_a_contact_with_a_code(db, user, client):
    _set_mode(db, "strict")

    res = client.post("/api/contacts", json=_payload(tafsili_code="9002"))

    assert res.status_code == 201, res.text
    assert res.json()["tafsili_code"] == "9002"


def test_hybrid_mode_allows_a_contact_without_one(db, user, client):
    """در «ترکیبی» می‌شود کد داد ولی اجباری نیست."""
    _set_mode(db, "hybrid")

    res = client.post("/api/contacts", json=_payload())

    assert res.status_code == 201, res.text
    assert res.json()["analytic_id"] is None


def test_floating_mode_ignores_the_code_entirely(db, user, client):
    """در «شناور» فیلد پنهان است، پس کدی هم که اشتباهاً بیاید تفصیلی نمی‌سازد."""
    _set_mode(db, "floating")

    res = client.post("/api/contacts", json=_payload(tafsili_code="9003"))

    assert res.status_code == 201, res.text
    assert res.json()["analytic_id"] is None
    assert db.query(AnalyticAccount).filter(AnalyticAccount.code == "9003").first() is None


def test_loosening_the_mode_never_drops_an_existing_tafsili(db, user, client):
    """**قیدِ مهم.** عوض‌کردنِ یک تنظیم نباید داده‌ی ثبت‌شده را پاک کند."""
    _set_mode(db, "hybrid")
    created = client.post("/api/contacts", json=_payload(tafsili_code="9004")).json()
    _set_mode(db, "floating")

    res = client.patch(f"/api/contacts/{created['id']}", json=_payload(name="آزمونِ ویرایش‌شده"))

    assert res.status_code == 200, res.text
    assert res.json()["analytic_id"] == created["analytic_id"], "تفصیلی باید سرِ جایش بماند"


def test_a_duplicate_tafsili_code_is_refused(db, user, client):
    _set_mode(db, "hybrid")
    client.post("/api/contacts", json=_payload(tafsili_code="9005"))

    res = client.post("/api/contacts", json=_payload(name="دومی", tafsili_code="9005"))

    assert res.status_code == 400, res.text
    assert "قبلاً استفاده شده" in res.json()["detail"]


def test_requirement_endpoint_follows_the_mode(db, user, client):
    for mode, expected in [("strict", "required"), ("hybrid", "optional"), ("floating", "hidden")]:
        _set_mode(db, mode)
        body = client.get("/api/contacts/tafsili-requirement").json()
        assert body["requirement"] == expected, mode
        assert body["mode"] == mode
        #: کدِ پیشنهادی فقط وقتی می‌آید که فرم قرار است فیلد را نشان دهد.
        assert (body["suggested_code"] is None) == (expected == "hidden")


def test_the_suggested_code_is_actually_free(db, user, client):
    _set_mode(db, "hybrid")
    code = client.get("/api/contacts/tafsili-requirement").json()["suggested_code"]

    res = client.post("/api/contacts", json=_payload(tafsili_code=code))

    assert res.status_code == 201, res.text


# ── هویت ─────────────────────────────────────────────────────────────────────


def test_display_name_is_composed_from_the_split_names(db, user, client):
    """`name` نامِ نمایشی می‌ماند — فاکتور و گزارشِ فصلی همه آن را می‌خوانند."""
    _set_mode(db, "hybrid")

    res = client.post(
        "/api/contacts",
        json=_payload(name="نادیده", first_name="علی", last_name="رضایی"),
    )

    assert res.status_code == 201, res.text
    assert res.json()["name"] == "علی رضایی"


def test_a_one_piece_name_still_works(db, user, client):
    """شرکت نامِ یک‌تکه دارد و نباید مجبور به تفکیک شود."""
    _set_mode(db, "hybrid")

    res = client.post("/api/contacts", json=_payload(name="شرکتِ الف"))

    assert res.status_code == 201, res.text
    assert res.json()["name"] == "شرکتِ الف"
    assert res.json()["first_name"] == ""


def test_the_extra_identity_fields_round_trip(db, user, client):
    _set_mode(db, "hybrid")

    res = client.post(
        "/api/contacts",
        json=_payload(
            sub_type="دولتی",
            website="https://example.ir",
            registration_no="12345",
            passport_no="X9988",
            marriage_date="2020-03-21",
            is_blacklisted=True,
            first_name2="Ali",
            last_name2="Rezaei",
        ),
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["sub_type"] == "دولتی"
    assert body["registration_no"] == "12345"
    assert body["passport_no"] == "X9988"
    assert body["marriage_date"] == "2020-03-21"
    assert body["is_blacklisted"] is True
    assert body["last_name2"] == "Rezaei"


def test_blacklist_is_separate_from_active(db, user, client):
    """غیرفعال یعنی «دیگر کار نمی‌کنیم»، لیستِ سیاه یعنی «با احتیاط». هر دو ممکن‌اند."""
    _set_mode(db, "hybrid")

    body = client.post("/api/contacts", json=_payload(is_blacklisted=True)).json()

    assert body["is_blacklisted"] is True
    assert body["is_active"] is True


# ── نقشِ واسطه و نرخ‌ها ───────────────────────────────────────────────────────


def test_broker_is_an_independent_flag(db, user, client):
    """**قیدِ سازگاری.** واسطه مقدارِ تازه‌ی `type` نیست.

    ده‌ها فیلتر و گزارش روی (customer, supplier, both) تکیه دارند؛ اگر روزی کسی
    `broker` را به `CONTACT_TYPES` اضافه کند، همه‌شان باید بازبینی شوند.
    """
    from app.models.inventory import CONTACT_TYPES

    assert "broker" not in CONTACT_TYPES
    _set_mode(db, "hybrid")

    body = client.post(
        "/api/contacts", json=_payload(type="customer", is_broker=True, commission_rate=2.5)
    ).json()

    assert body["type"] == "customer", "نقشِ اصلی دست‌نخورده می‌ماند"
    assert body["is_broker"] is True
    assert float(body["commission_rate"]) == 2.5


@pytest.mark.parametrize("field", ["discount_rate", "commission_rate"])
@pytest.mark.parametrize("bad", [-1, 101])
def test_rates_outside_zero_to_hundred_are_refused(db, user, client, field, bad):
    _set_mode(db, "hybrid")

    res = client.post("/api/contacts", json=_payload(**{field: bad}))

    assert res.status_code == 422, res.text


# ── کنترلِ اعتبار ─────────────────────────────────────────────────────────────


def test_credit_action_defaults_to_none(db, user, client):
    """**قیدِ مهاجرت.** `credit_limit` تا امروز هیچ‌جا اعمال نمی‌شد.

    پیش‌فرضِ `none` یعنی همان رفتار، پس سقف‌هایی که از قبل ثبت شده‌اند یک‌شبه جلوی
    فروش را نمی‌گیرند.
    """
    _set_mode(db, "hybrid")

    body = client.post("/api/contacts", json=_payload(credit_limit=1000)).json()

    assert body["credit_action"] == "none"


@pytest.mark.parametrize("action", ["none", "warn", "block"])
def test_every_credit_action_is_accepted(db, user, client, action):
    _set_mode(db, "hybrid")

    res = client.post("/api/contacts", json=_payload(credit_action=action))

    assert res.status_code == 201, res.text


def test_an_invalid_credit_action_is_refused(db, user, client):
    _set_mode(db, "hybrid")

    res = client.post("/api/contacts", json=_payload(credit_action="explode"))

    assert res.status_code == 422, res.text


# ── پیوندِ کارمند ─────────────────────────────────────────────────────────────


def test_employee_link_points_at_the_payroll_record(db, user, client):
    """**قیدِ اصلیِ تبِ «مشخصات کارمند».** پیوند است نه کپی — یک آدم، یک رکورد."""
    from app.models.payroll import Employee

    employee = Employee(
        first_name="سارا", last_name="محمدی", national_id="1234509876", hire_date=date(2025, 1, 1)
    )
    db.add(employee)
    db.flush()
    _set_mode(db, "hybrid")

    body = client.post("/api/contacts", json=_payload(employee_id=str(employee.id))).json()

    assert body["employee_id"] == str(employee.id)
    #: و هیچ فیلدِ کارمندی روی خودِ طرف‌حساب کپی نشده.
    assert "hire_date" not in body
    assert "bank_account_number" not in body


def test_a_title_alone_creates_the_tafsili_in_hybrid(db, user, client):
    """**ایرادِ واقعیِ پیداشده در آزمونِ زنده.** عنوان دادن یعنی «تفصیلی می‌خواهم».

    پیش از این، در حالتِ «ترکیبی» عنوانِ بدونِ کد بی‌صدا دور ریخته می‌شد: کاربر
    عنوانی می‌نوشت که فرم از نامش پیشنهاد داده بود، و هیچ تفصیلی‌ای ساخته نمی‌شد.
    """
    _set_mode(db, "hybrid")

    res = client.post("/api/contacts", json=_payload(tafsili_title="رجبی بهنام"))

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["analytic_id"] is not None
    assert body["tafsili_code"], "کد باید خودکار ساخته شده باشد"
    assert body["tafsili_title"] == "رجبی بهنام"


def test_neither_code_nor_title_in_hybrid_creates_nothing(db, user, client):
    """و قرینه‌اش: در «ترکیبی» سکوتِ کامل یعنی تفصیلی نمی‌خواهم."""
    _set_mode(db, "hybrid")

    res = client.post("/api/contacts", json=_payload())

    assert res.status_code == 201, res.text
    assert res.json()["analytic_id"] is None


# ── نقش‌های هم‌زمان ───────────────────────────────────────────────────────────


def test_a_contact_can_hold_every_role_at_once(db, user, client):
    """**قیدِ اصلیِ نقش‌ها.** مشتری، تأمین‌کننده، واسطه و سهامدار هم‌زمان ممکن‌اند.

    در فرم چهار تیکِ مستقل‌اند نه یک کشوییِ تک‌انتخابی: کسی که از ما می‌خرد، به ما
    می‌فروشد، مشتری معرفی می‌کند و سهامدار هم هست، یک آدم است نه چهارتا. دو نقشِ
    معاملاتی در `type` می‌نشینند و دو نقشِ دیگر پرچمِ خودشان را دارند.
    """
    _set_mode(db, "hybrid")

    res = client.post(
        "/api/contacts",
        json=_payload(
            name="شرکتِ چندنقشه",
            type="both",
            is_broker=True,
            commission_rate="3.5",
            is_shareholder=True,
            share_percent="12.5",
        ),
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["type"] == "both"
    assert body["is_broker"] is True
    assert Decimal(str(body["commission_rate"])) == Decimal("3.5")
    assert body["is_shareholder"] is True
    assert Decimal(str(body["share_percent"])) == Decimal("12.5")


def test_a_partial_edit_keeps_the_roles_it_did_not_send(db, user, client):
    """**ایرادِ واقعی.** PATCH یعنی «همین‌ها را عوض کن»، نه «بقیه را دور بریز».

    فرمِ ساده‌ی طرف‌حسابِ ماژولِ فروش فقط چند فیلدِ پایه می‌فرستد. تا پیش از این،
    ویرایشِ یک شماره‌تلفن از آن‌جا نقشِ واسطه و سهامدار، نرخِ پورسانت و مشخصاتِ
    شخصی را به پیش‌فرضِ اسکیما برمی‌گرداند.
    """
    _set_mode(db, "hybrid")
    created = client.post(
        "/api/contacts",
        json=_payload(is_broker=True, commission_rate="4", is_shareholder=True, gender="male"),
    ).json()

    res = client.patch(
        f"/api/contacts/{created['id']}", json={"name": "نامِ تازه", "phone": "021-9999"}
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "نامِ تازه"
    assert body["phone"] == "021-9999"
    assert body["is_broker"] is True, "نقشِ واسطه نباید با ویرایشِ نام پاک شود"
    assert Decimal(str(body["commission_rate"])) == Decimal("4")
    assert body["is_shareholder"] is True
    assert body["gender"] == "male"


def test_a_partial_edit_keeps_the_tafsili_title_the_user_chose(db, user, client):
    """عنوانِ تفصیلی هم داده است: ویرایشی که نفرستاده‌اش نباید بازنویسی‌اش کند."""
    _set_mode(db, "hybrid")
    created = client.post(
        "/api/contacts",
        json=_payload(
            tafsili_code="9101", tafsili_title="رجبی بهنام ـ دفتر", tafsili_title2="Rajabi"
        ),
    ).json()
    assert created["analytic_id"] is not None

    res = client.patch(f"/api/contacts/{created['id']}", json={"name": "نامِ دیگر"})

    assert res.status_code == 200, res.text
    row = db.query(AnalyticAccount).filter(AnalyticAccount.code == "9101").one()
    assert row.name == "رجبی بهنام ـ دفتر"
    assert row.name2 == "Rajabi"
