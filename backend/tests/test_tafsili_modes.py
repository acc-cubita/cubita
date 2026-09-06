"""سطحِ اجبارِ تفصیلی — انتخابِ کسب‌وکار میانِ «اجباری»، «ترکیبی» و «شناور».

قیدِ اصلیِ این قابلیت که تست‌ها نگهش می‌دارند: **گزارش در هر سه حالت کار می‌کند.**
سطحِ اجبار تعیین می‌کند چه چیزی *مسدود* شود، نه چه چیزی *دیده* شود؛ پس حتی در
سست‌ترین حالت هم ردیفِ بی‌تفصیلی نامرئی نمی‌ماند. اگر روزی کسی گزارش را به حالت گره
بزند، `test_report_works_in_every_mode` قرمز می‌شود.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.analytic import AnalyticAccount
from app.models.tenant import Tenant
from app.services import tafsili
from app.services.common import make_journal_entry
from app.tenant_context import session_tenant


def _account(db, code: str) -> Account:
    return db.query(Account).filter(Account.code == code).one()


def _user_id(db):
    from app.models.user import User

    return db.query(User.id).scalar()


def _analytic(db) -> AnalyticAccount:
    row = db.query(AnalyticAccount).first()
    if row is None:
        row = AnalyticAccount(code="T1", name="تفصیلیِ آزمون", created_by_id=_user_id(db))
        db.add(row)
        db.flush()
    return row


def _set_mode(db, mode: str) -> None:
    tenant = db.get(Tenant, session_tenant(db))
    tenant.tafsili_enforcement = mode
    db.flush()


def _tafsili_account(db) -> Account:
    acc = _account(db, "1101")
    acc.accepts_tafsili = True
    db.flush()
    return acc


def _manual_payload(db) -> dict:
    return {
        "entry_date": "2026-01-01",
        "description": "آزمونِ حالت",
        "lines": [
            {"account_id": str(_account(db, "1101").id), "debit": 1000, "credit": 0},
            {"account_id": str(_account(db, "4101").id), "debit": 0, "credit": 1000},
        ],
    }


def _module_lines(db) -> list[JournalLine]:
    return [
        JournalLine(account_id=_account(db, "1101").id, debit=Decimal(1000), credit=Decimal(0)),
        JournalLine(account_id=_account(db, "4101").id, debit=Decimal(0), credit=Decimal(1000)),
    ]


def _post_from_module(db, user, source_type="sales_invoice") -> JournalEntry:
    return make_journal_entry(
        db, date(2026, 1, 1), "ردیفِ ماژول", source_type, user, _module_lines(db)
    )


# ── پیش‌فرض ──────────────────────────────────────────────────────────────────


def test_default_is_hybrid_and_not_explicit(db, user, client):
    """مهاجرتِ ۰۰۸۹ هیچ کسب‌وکاری را تکان نمی‌دهد: NULL یعنی همان رفتارِ قبلی."""
    tenant = db.get(Tenant, session_tenant(db))
    assert tenant.tafsili_enforcement is None
    assert tafsili.get_mode(db) == "hybrid"

    res = client.get("/api/accounts/tafsili-mode")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["mode"] == "hybrid"
    assert body["is_explicit"] is False, "هنوز انتخابِ کاربر نیست، پیش‌فرضِ سرویس است"
    assert {o["key"] for o in body["options"]} == set(tafsili.TAFSILI_MODES)
    assert all(o["hint"] for o in body["options"]), "هر گزینه باید توضیحِ خودش را داشته باشد"


# ── سندِ دستی ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("mode,expected", [("strict", 400), ("hybrid", 400), ("floating", 201)])
def test_manual_entry_by_mode(db, user, client, mode, expected):
    """سندِ دستی فقط در «شناور» بدونِ تفصیلی می‌گذرد."""
    _tafsili_account(db)
    _set_mode(db, mode)

    res = client.post("/api/journal-entries", json=_manual_payload(db))

    assert res.status_code == expected, res.text


# ── ردیفِ ماژول ──────────────────────────────────────────────────────────────


def test_module_line_is_blocked_only_in_strict(db, user):
    """**تفاوتِ اصلیِ «اجباری» و «ترکیبی».**

    این همان سوراخی است که کاربر با انتخابِ «اجباری» می‌بندد: ردیفی که فاکتور
    می‌سازد هم باید تفصیلی داشته باشد.
    """
    _tafsili_account(db)
    _set_mode(db, "strict")

    with pytest.raises(HTTPException) as err:
        _post_from_module(db, user)
    assert err.value.status_code == 400
    assert "تنظیمات" in err.value.detail, "پیام باید بگوید کجا می‌شود عوضش کرد"


@pytest.mark.parametrize("mode", ["hybrid", "floating"])
def test_module_line_passes_in_the_looser_modes(db, user, mode):
    """و در دو حالتِ دیگر فاکتور نمی‌شکند — همان چیزی که «اجباری» را اختیاری می‌کند."""
    _tafsili_account(db)
    _set_mode(db, mode)

    entry = _post_from_module(db, user)

    assert entry.id is not None


def test_strict_lets_a_module_line_through_when_tafsili_is_present(db, user):
    """«اجباری» ماژول را کور مسدود نمی‌کند — فقط ردیفِ بی‌تفصیلی را."""
    _tafsili_account(db)
    _set_mode(db, "strict")
    analytic = _analytic(db)
    lines = _module_lines(db)
    lines[0].analytic_id = analytic.id

    entry = make_journal_entry(db, date(2026, 1, 1), "با تفصیلی", "sales_invoice", user, lines)

    assert entry.id is not None


def test_void_is_never_blocked(db, user):
    """**قیدِ مهم.** سندِ برگشتی ابعادش را از اصل کپی می‌کند.

    اگر ابطال به‌خاطرِ قاعده‌ای که *بعد از* ثبتِ اصل سخت‌گیرتر شده رد شود، کاربر در
    سندی گیر می‌افتد که نه می‌تواند نگه دارد نه برگرداند.
    """
    _tafsili_account(db)
    _set_mode(db, "floating")
    original = _post_from_module(db, user)
    _set_mode(db, "strict")  # قاعده بعد از ثبت سخت‌گیر شد

    reversal = make_journal_entry(
        db, date(2026, 2, 1), "برگشت", f"void_{original.source_type}", user, _module_lines(db)
    )

    assert reversal.id is not None


# ── گزارش ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("mode", ["strict", "hybrid", "floating"])
def test_report_works_in_every_mode(db, user, mode):
    """**قیدِ اصلی.** سطحِ اجبار تعیین می‌کند چه چیزی مسدود شود، نه چه چیزی دیده شود.

    ردیف در حالتِ «شناور» ثبت می‌شود و بعد حالت عوض می‌شود؛ گزارش باید در هر سه
    حالت همان ردیف را نشان بدهد.
    """
    _tafsili_account(db)
    _set_mode(db, "floating")
    _post_from_module(db, user)
    _set_mode(db, mode)

    rows = tafsili.find_missing_tafsili(db)

    assert any(r["account_code"] == "1101" for r in rows), "ردیفِ بی‌تفصیلی باید دیده شود"
    row = next(r for r in rows if r["account_code"] == "1101")
    assert row["is_manual"] is False, "منبع باید معلوم باشد تا کاربر بداند از کجا آمده"


def test_report_ignores_lines_that_have_tafsili(db, user):
    _tafsili_account(db)
    _set_mode(db, "floating")
    analytic = _analytic(db)
    lines = _module_lines(db)
    lines[0].analytic_id = analytic.id
    entry = make_journal_entry(db, date(2026, 1, 1), "با تفصیلی", "sales_invoice", user, lines)

    #: سنجه روی *همین* سند است، نه «هیچ ردیفی برای ۱۱۰۱ نباشد»: دیتابیسِ تست ممکن
    #: است ردیف‌های دیگری روی همین حساب داشته باشد و آن‌ها ربطی به این تست ندارند.
    assert not [r for r in tafsili.find_missing_tafsili(db) if r["entry_id"] == entry.id]


def test_report_ignores_accounts_that_are_not_tafsili(db, user):
    """حسابِ بی‌پرچم اصلاً موضوعِ این گزارش نیست."""
    _set_mode(db, "floating")
    _post_from_module(db, user)

    assert tafsili.find_missing_tafsili(db) == []


def test_report_endpoint_is_reachable(db, user, client):
    _tafsili_account(db)
    _set_mode(db, "floating")
    _post_from_module(db, user)

    res = client.get("/api/reports/missing-tafsili")

    assert res.status_code == 200, res.text
    assert any(r["account_code"] == "1101" for r in res.json())


# ── تغییرِ تنظیم ─────────────────────────────────────────────────────────────


def test_setting_the_mode_sticks(db, user, client):
    res = client.patch("/api/accounts/tafsili-mode", json={"mode": "strict"})

    assert res.status_code == 200, res.text
    assert res.json()["mode"] == "strict"
    assert res.json()["is_explicit"] is True


def test_an_invalid_mode_is_refused(db, user, client):
    res = client.patch("/api/accounts/tafsili-mode", json={"mode": "whatever"})

    assert res.status_code == 400, res.text


def test_tightening_the_mode_does_not_invalidate_past_entries(db, user, client):
    """**قیدِ مهم.** سختگیرتر شدن نباید سندِ دیروز را نامعتبر کند.

    فقط ثبت‌های *بعدی* را می‌سنجد؛ گذشته در گزارش دیده می‌شود، نه اینکه بشکند.
    """
    _tafsili_account(db)
    _set_mode(db, "floating")
    entry = _post_from_module(db, user)

    client.patch("/api/accounts/tafsili-mode", json={"mode": "strict"})

    assert db.get(JournalEntry, entry.id) is not None, "سندِ گذشته سرِ جایش می‌ماند"
    assert any(r["entry_id"] == entry.id for r in tafsili.find_missing_tafsili(db))
