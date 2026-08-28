"""قالب‌های آماده‌ی کدینگ: کاملِ صنف، بی‌اثر بودنِ اجرای دوباره، و دست‌نخوردنِ حسابِ موجود."""
import pytest
from fastapi import HTTPException

from app.models.accounting import Account
from app.routers.accounts import AccountCodeIn, apply_template, change_code, list_templates
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
