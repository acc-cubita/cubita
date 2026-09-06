"""قالب‌های آماده‌ی کدینگ: کاملِ صنف، بی‌اثر بودنِ اجرای دوباره، و دست‌نخوردنِ حسابِ موجود."""
import json

import pytest
from fastapi import HTTPException

from app.models.accounting import Account
from app.routers.accounts import (
    AccountCodeIn,
    apply_template,
    change_code,
    list_templates,
    revert_template,
)
from app.services import chart_templates as ct


def test_all_four_industries_exist():
    assert set(ct.TEMPLATES) == {"trading", "services", "manufacturing", "contracting"}


def test_every_row_has_an_existing_parent():
    """والدِ هر ردیف باید پیش از خودش در همان فهرست آمده باشد، وگرنه ساختش می‌شکند."""
    for key in ct.TEMPLATES:
        seen: set[str] = set()
        for code, _name, _t, _g, parent in ct.rows_for(key):
            if parent is not None:
                assert parent in seen, f"{key}: والدِ {code} ({parent}) هنوز تعریف نشده"
            seen.add(code)


def test_codes_unique_within_each_template():
    for key in ct.TEMPLATES:
        codes = [r[0] for r in ct.rows_for(key)]
        assert len(codes) == len(set(codes)), f"کدِ تکراری در قالبِ {key}"


def test_specialised_codes_do_not_clash_between_industries():
    seen: dict[str, str] = {}
    for key, meta in ct.TEMPLATES.items():
        for code, name, *_ in meta["rows"]:
            assert code not in seen, f"کدِ {code} هم در {key} هست هم در {seen[code]}"
            seen[code] = key


def test_apply_creates_common_plus_specialised(db):
    before = db.query(Account).count()
    result = apply_template("manufacturing", db=db)
    after = db.query(Account).count()

    assert result.created > 0
    assert after - before == result.created
    codes = {a.code for a in db.query(Account).all()}
    assert "5141" in codes  # دستمزد مستقیم تولید — تخصصی
    assert "5109" in codes  # هزینه تبلیغات — عمومی


def test_apply_twice_adds_nothing(db):
    apply_template("trading", db=db)
    count = db.query(Account).count()
    second = apply_template("trading", db=db)
    assert second.created == 0
    assert db.query(Account).count() == count


def test_apply_never_touches_existing_account(db):
    cash = db.query(Account).filter(Account.code == "1101").first()
    original_name, original_role = cash.name, cash.system_role
    apply_template("services", db=db)
    db.refresh(cash)
    assert (cash.name, cash.system_role) == (original_name, original_role)


def test_created_accounts_have_no_system_role(db):
    apply_template("contracting", db=db)
    for code in ("5150", "4130", "1150"):
        acc = db.query(Account).filter(Account.code == code).first()
        assert acc is not None and acc.system_role is None


def test_unknown_template_is_404(db):
    with pytest.raises(HTTPException) as err:
        apply_template("bogus", db=db)
    assert err.value.status_code == 404


def test_missing_count_drops_to_zero_after_apply(db):
    before = {t.key: t.missing for t in list_templates(db=db)}
    assert before["trading"] > 0
    apply_template("trading", db=db)
    after = {t.key: t.missing for t in list_templates(db=db)}
    assert after["trading"] == 0


# ── تغییرِ کدِ حساب ───────────────────────────────────────────────────────────


def test_change_code_updates_account(db):
    acc = db.query(Account).filter(Account.code == "5103").first()
    out = change_code(acc.id, AccountCodeIn(code="5203"), db=db)
    assert out.code == "5203"


def test_change_code_rejects_duplicate(db):
    acc = db.query(Account).filter(Account.code == "5103").first()
    with pytest.raises(HTTPException) as err:
        change_code(acc.id, AccountCodeIn(code="1101"), db=db)
    assert err.value.status_code == 409


def test_change_code_keeps_system_role_working(db):
    """کدِ حسابِ نقش‌دار عوض می‌شود ولی ثبتِ خودکار باید همچنان پیدایش کند."""
    from app.services import chart_codes as cc
    from app.services.common import get_account

    cash = db.query(Account).filter(Account.system_role == cc.CASH).first()
    change_code(cash.id, AccountCodeIn(code="9901"), db=db)
    assert get_account(db, cc.CASH).id == cash.id


def test_seed_chart_never_squats_on_a_template_code():
    """چارتِ پایه نباید کدی را بگیرد که قالبِ صنفی با نامِ دیگری برایش دارد.

    محافظ در برابرِ یک خرابیِ بی‌صداست که یک‌بار رخ داد: حساب‌های تسعیر ارز روی ۴۱۰۴
    و ۵۱۰۷ نشستند که مالِ «تخفیفات و برگشت از فروش» و «هزینه آب، برق، گاز و تلفن»
    بود. `apply_template` کدِ موجود را رد می‌کند، پس آن دو حساب هرگز ساخته نمی‌شدند و
    در شمارشِ «چند حساب کم دارید» هم موجود به حساب می‌آمدند.
    """
    from app.seed import CHART_OF_ACCOUNTS

    seed_names = {code: name for code, name, *_ in CHART_OF_ACCOUNTS}
    for key in ct.TEMPLATES:
        for code, name, *_ in ct.rows_for(key):
            if code in seed_names:
                assert seed_names[code] == name, (
                    f"کدِ {code}: چارتِ پایه «{seed_names[code]}» ولی قالبِ {key} «{name}»"
                )


def test_setup_status_is_untouched_on_a_fresh_chart(db):
    """کسب‌وکارِ تازه چارتِ پایه دارد ولی هنوز کاری نکرده — پس «انجام نشده»."""
    from app.routers.accounts import setup_status

    out = setup_status(db=db)
    assert out.custom == 0
    assert out.applied_template is None
    assert out.total > 0


def test_setup_status_turns_done_after_applying_a_template(db):
    from app.routers.accounts import setup_status

    apply_template(key="trading", db=db)
    out = setup_status(db=db)
    assert out.applied_template == "trading"
    assert out.custom > 0


def test_setup_status_counts_a_hand_built_account(db):
    """چارت را دستی هم می‌شود ساخت؛ نشانِ «انجام شده» نباید فقط به قالب گره بخورد."""
    from app.routers.accounts import setup_status

    db.add(Account(code="5301", name="هزینه‌ی دلخواه", type="expense", is_group=False))
    db.flush()
    out = setup_status(db=db)
    assert out.custom == 1
    assert out.applied_template is None


# ── برگرداندنِ قالب ───────────────────────────────────────────────────────────


def test_revert_removes_exactly_what_apply_added(db):
    """چرخه باید بسته باشد: درج و برگرداندن، چارت را سرِ جای اولش بگذارد."""
    before = {c for (c,) in db.query(Account.code).all()}
    added = apply_template("trading", db=db).created
    assert added > 0

    result = revert_template("trading", db=db)

    assert result.removed == added
    assert {c for (c,) in db.query(Account.code).all()} == before
    assert result.kept == []


def test_revert_keeps_an_account_that_has_a_document(db):
    """قیدِ اصلی: حسابی که در سند آمده نباید برود — دفتر می‌شکند."""
    from datetime import date
    from decimal import Decimal

    from app.models.accounting import JournalEntry, JournalLine
    from app.models.user import User

    apply_template("trading", db=db)
    victim = db.query(Account).filter(Account.code == "1120").one()
    user_id = db.query(User.id).scalar()
    cash = db.query(Account).filter(Account.code == "1101").one()

    entry = JournalEntry(entry_date=date(2026, 1, 1), description="آزمون", created_by_id=user_id)
    entry.lines = [
        JournalLine(account_id=victim.id, debit=Decimal(1), credit=Decimal(0)),
        JournalLine(account_id=cash.id, debit=Decimal(0), credit=Decimal(1)),
    ]
    db.add(entry)
    db.flush()

    result = revert_template("trading", db=db)

    kept_codes = {k.code for k in result.kept}
    assert "1120" in kept_codes
    assert next(k for k in result.kept if k.code == "1120").reason == "در سند استفاده شده"
    assert db.query(Account).filter(Account.code == "1120").first() is not None


def test_revert_never_touches_the_baseline_chart(db):
    """حساب‌های پایه مالِ قالب نیستند، حتی اگر کدشان در قالب هم آمده باشد."""
    from app.seed import CHART_OF_ACCOUNTS

    baseline = {code for code, *_ in CHART_OF_ACCOUNTS}
    apply_template("trading", db=db)
    revert_template("trading", db=db)

    survivors = {c for (c,) in db.query(Account.code).all()}
    assert baseline <= survivors, "هیچ حسابِ پایه‌ای نباید با برگرداندنِ قالب برود"


def test_revert_keeps_system_role_accounts(db):
    """نقشِ سیستمی یعنی ثبتِ خودکار به آن تکیه دارد."""
    apply_template("trading", db=db)
    roles_before = db.query(Account).filter(Account.system_role.isnot(None)).count()
    revert_template("trading", db=db)
    assert db.query(Account).filter(Account.system_role.isnot(None)).count() == roles_before


def test_revert_of_unknown_template_is_404(db):
    with pytest.raises(HTTPException) as err:
        revert_template("no-such-industry", db=db)
    assert err.value.status_code == 404


def test_revert_is_safe_to_repeat(db):
    """بارِ دوم چیزی برای برداشتن نیست و نباید خطا بدهد."""
    apply_template("trading", db=db)
    revert_template("trading", db=db)
    again = revert_template("trading", db=db)
    assert again.removed == 0


# ── قالب‌ها به‌عنوانِ داده ────────────────────────────────────────────────────


def test_templates_come_from_the_data_file_not_the_code():
    """قالب‌ها داده‌اند، نه کد — اضافه‌کردنِ حساب باید ویرایشِ JSON باشد نه پایتون."""
    from app.services import chart_templates as t

    assert t.DATA_FILE.exists(), "فایلِ داده باید کنارِ کد باشد و در همان مخزن"
    raw = json.loads(t.DATA_FILE.read_text(encoding="utf-8"))
    assert set(raw) == {"parents", "common", "templates"}
    assert set(raw["templates"]) == {"trading", "services", "manufacturing", "contracting"}


def test_every_parent_code_referenced_is_defined():
    """**قیدِ اصلیِ داده.** والدی که تعریف نشده باشد، درجِ قالب را به ساختنِ سرفصلِ
    ناقص می‌کشاند و درخت جای عجیبی رشد می‌کند. لودر همین را لحظه‌ی بارگذاری می‌سنجد،
    این تست فقط قفلش می‌کند.
    """
    from app.services import chart_templates as t

    defined = {row[0] for key in t.TEMPLATES for row in t.rows_for(key)}
    for key in t.TEMPLATES:
        for code, _name, _type, _group, parent in t.rows_for(key):
            assert parent is None or parent in defined, f"والدِ {parent} برای {code} تعریف نشده"


def test_a_broken_data_file_fails_loudly_at_load_time():
    """خرابیِ داده باید موقعِ بارگذاری پیدا شود، نه وسطِ درجِ قالب برای مشتری."""
    from app.services import chart_templates as t

    with pytest.raises(ValueError, match="نوعِ نامعتبر"):
        t._row({"code": "9999", "title": "x", "type": "not_a_type"}, "آزمون")
    with pytest.raises(ValueError, match="ردیفِ ناقص"):
        t._row({"code": "9999"}, "آزمون")
    with pytest.raises(ValueError, match="غیرعددی"):
        t._row({"code": "abc", "title": "x", "type": "asset"}, "آزمون")


def test_row_order_puts_parents_before_children():
    """ترتیب بخشی از قرارداد است: `apply_template` والد را پیش از فرزند می‌سازد."""
    from app.services import chart_templates as t

    for key in t.TEMPLATES:
        seen: set[str] = set()
        for code, _name, _type, _group, parent in t.rows_for(key):
            assert parent is None or parent in seen, f"{code} پیش از والدش {parent} آمده"
            seen.add(code)
