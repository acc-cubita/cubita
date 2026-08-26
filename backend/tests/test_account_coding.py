"""قاعده‌ی کدینگِ چارت: طولِ کد در هر سطح، پیشنهادِ کدِ آزاد، و دست‌نخوردنِ حسابِ موجود."""
import pytest
from fastapi import HTTPException

from app.models.accounting import Account
from app.models.tenant import Tenant
from app.schemas.accounting import AccountCreateIn
from app.services import account_coding as coding


class _P:
    """جانشینِ Principal — روتر فقط tenant_id را می‌خواهد."""

    def __init__(self, tenant_id):
        self.tenant_id = tenant_id


def _tenant(db) -> Tenant:
    return db.query(Tenant).first()


# ── خودِ قاعده ───────────────────────────────────────────────────────────────


def test_default_matches_the_existing_chart(db):
    """پیش‌فرض باید همان ساختارِ چارتِ کاشته‌شده باشد، وگرنه چارتِ هر مشتری نامعتبر می‌شود."""
    widths = coding.get_widths(_tenant(db))
    assert widths == [1, 1, 2, 2]
    assert coding.preview(widths) == ["1", "11", "1101", "110101"]

    for code in ("1", "11", "1101"):
        acc = db.query(Account).filter(Account.code == code).first()
        assert acc is not None
        parent = db.get(Account, acc.parent_id) if acc.parent_id else None
        # هیچ خطایی نباید بدهد.
        coding.validate_new_code(db, code=acc.code, parent=parent, widths=widths)


def test_widths_are_clamped(db):
    t = _tenant(db)
    coding.set_widths(t, [0, 99, 3, -5])
    assert coding.get_widths(t) == [1, 6, 3, 1]


def test_missing_or_broken_value_falls_back(db):
    t = _tenant(db)
    t.account_code_widths = "خراب"
    assert coding.get_widths(t) == list(coding.DEFAULT_WIDTHS)


def test_expected_length_is_cumulative():
    w = [2, 2, 2, 2]
    assert [coding.expected_code_length(w, d) for d in range(4)] == [2, 4, 6, 8]


def test_deeper_than_defined_uses_last_width():
    w = [1, 1, 2, 3]
    assert coding.width_for(w, 9) == 3


# ── اعتبارسنجی ──────────────────────────────────────────────────────────────


def test_wrong_length_is_rejected(db):
    widths = coding.get_widths(_tenant(db))
    parent = db.query(Account).filter(Account.code == "11").first()
    with pytest.raises(ValueError) as err:
        coding.validate_new_code(db, code="11012", parent=parent, widths=widths)
    assert "معین" in str(err.value)


def test_code_must_start_with_parent_code(db):
    widths = coding.get_widths(_tenant(db))
    parent = db.query(Account).filter(Account.code == "11").first()
    with pytest.raises(ValueError) as err:
        coding.validate_new_code(db, code="9999", parent=parent, widths=widths)
    assert "والد" in str(err.value)


def test_non_numeric_code_is_rejected(db):
    widths = coding.get_widths(_tenant(db))
    with pytest.raises(ValueError):
        coding.validate_new_code(db, code="AB", parent=None, widths=widths)


def test_two_digit_rule_applies_where_there_is_no_precedent(db):
    """قاعده جایی حاکم است که سابقه‌ای نباشد؛ وگرنه قراردادِ شاخه مقدم است."""
    t = _tenant(db)
    coding.set_widths(t, [2, 2, 2, 2])
    widths = coding.get_widths(t)

    group12 = db.query(Account).filter(Account.code == "12").first()
    empty = Account(code="1288", name="سرفصلِ خالی", type="asset", is_group=True, parent_id=group12.id)
    db.add(empty)
    db.flush()

    coding.validate_new_code(db, code="128801", parent=empty, widths=widths)
    with pytest.raises(ValueError):
        coding.validate_new_code(db, code="12881", parent=empty, widths=widths)


# ── پیشنهادِ کد ──────────────────────────────────────────────────────────────


def test_suggest_skips_used_codes(db):
    widths = coding.get_widths(_tenant(db))
    parent = db.query(Account).filter(Account.code == "11").first()
    # ۱۱۰۱ تا ۱۱۰۷ در چارتِ پایه هستند.
    assert coding.suggest_code(db, parent=parent, widths=widths) == "1108"


def test_root_keeps_its_existing_one_digit_convention(db):
    """گروه‌های ریشه از قبل یک‌رقمی‌اند؛ تغییرِ قاعده نباید ریشه را دورگه کند."""
    t = _tenant(db)
    coding.set_widths(t, [2, 2, 2, 2])
    code = coding.suggest_code(db, parent=None, widths=coding.get_widths(t))
    assert len(code) == 1


# ── اثر روی اندپوینتِ ساختِ حساب ────────────────────────────────────────────


def test_create_account_rejects_off_rule_code(db, tenant_id):
    from app.routers.accounts import create_account

    parent = db.query(Account).filter(Account.code == "11").first()
    with pytest.raises(HTTPException) as err:
        create_account(
            AccountCreateIn(code="11099", name="حساب بد", type="asset", parent_id=parent.id),
            db=db,
            principal=_P(tenant_id),
        )
    assert err.value.status_code == 400


def test_create_account_accepts_rule_abiding_code(db, tenant_id):
    from app.routers.accounts import create_account

    parent = db.query(Account).filter(Account.code == "11").first()
    out = create_account(
        AccountCreateIn(code="1150", name="حساب خوب", type="asset", parent_id=parent.id),
        db=db,
        principal=_P(tenant_id),
    )
    assert out.code == "1150"


def test_existing_accounts_are_never_renumbered(db, tenant_id):
    """تغییرِ قاعده نباید هیچ کدی را عوض کند."""
    before = {a.id: a.code for a in db.query(Account).all()}
    coding.set_widths(_tenant(db), [2, 2, 2, 2])
    db.flush()
    after = {a.id: a.code for a in db.query(Account).all()}
    assert before == after


# ── قراردادِ شاخه بر قاعده‌ی عمق مقدم است ────────────────────────────────────


def test_sibling_width_wins_over_depth_rule(db):
    """چارتِ پیش‌فرض یکدست نیست: هزینه‌ها ۵ ← ۵۱۰۱ هستند، نه ۵ ← ۵۱ ← ۵۱۰۱."""
    widths = coding.get_widths(_tenant(db))
    group5 = db.query(Account).filter(Account.code == "5").first()

    # قاعده‌ی عمق ۱ رقم می‌گوید، ولی فرزندانِ موجود ۳ رقم افزوده دارند.
    assert coding.width_for(widths, 1) == 1
    assert coding.sibling_width(db, group5) == 3

    # پس هم‌ردیفِ ۵۱۰۱ باید پذیرفته شود، نه رد.
    coding.validate_new_code(db, code="5199", parent=group5, widths=widths)
    with pytest.raises(ValueError):
        coding.validate_new_code(db, code="51", parent=group5, widths=widths)


def test_suggest_follows_sibling_width(db):
    widths = coding.get_widths(_tenant(db))
    group5 = db.query(Account).filter(Account.code == "5").first()
    assert len(coding.suggest_code(db, parent=group5, widths=widths)) == 4


def test_rule_applies_where_there_is_no_precedent(db):
    """سرفصلِ بی‌فرزند سابقه‌ای ندارد، پس قاعده تصمیم می‌گیرد."""
    widths = coding.get_widths(_tenant(db))
    group12 = db.query(Account).filter(Account.code == "12").first()
    empty = Account(code="1299", name="سرفصلِ خالی", type="asset", is_group=True, parent_id=group12.id)
    db.add(empty)
    db.flush()
    assert coding.sibling_width(db, empty) is None
    # عمقِ ۳ (تفصیلی) → ۲ رقم
    assert len(coding.suggest_code(db, parent=empty, widths=widths)) == len("1299") + 2
