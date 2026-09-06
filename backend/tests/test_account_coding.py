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


# ── تفصیلی زیرِ معین ─────────────────────────────────────────────────────────


def _create(db, tenant, *, code, name, parent):
    """ساختِ حساب از راهِ روتر، تا همان قیدهای واقعی اعمال شوند."""
    from app.routers.accounts import create_account

    return create_account(
        AccountCreateIn(code=code, name=name, type=parent.type, parent_id=parent.id),
        db=db,
        principal=_P(tenant.id),
    )


def test_tafsili_can_be_created_under_a_moin(db):
    """سطحِ چهارم — «بانک ملی» زیرِ «بانک». معین سرفصل نیست ولی باید فرزند بگیرد."""
    tenant = _tenant(db)
    bank = db.query(Account).filter(Account.code == "1102").one()
    assert bank.is_group is False, "پیش‌فرضِ آزمون: بانک معین است نه سرفصل"

    #: depth_of عمقِ حسابی را می‌دهد که *زیرِ* آرگومان ساخته می‌شود، نه خودش.
    assert coding.level_name(coding.depth_of(db, bank.parent)) == "معین", "بانک معین است"
    assert coding.level_name(coding.depth_of(db, bank)) == "تفصیلی", "فرزندش تفصیلی می‌شود"

    #: از وقتی فرمِ ویرایش تیکِ «تفصیلی پذیر» دارد، معین باید صریحاً پذیرا باشد.
    bank.accepts_tafsili = True
    db.flush()

    child = _create(db, tenant, code="110201", name="بانک ملی", parent=bank)

    assert child.parent_id == bank.id
    assert coding.level_name(coding.depth_of(db, child.parent)) == "تفصیلی"


def test_suggested_code_for_a_tafsili_follows_the_rule(db):
    """کدِ پیشنهادی باید کدِ معین + رقم‌های سطحِ تفصیلی باشد."""
    bank = db.query(Account).filter(Account.code == "1102").one()
    widths = coding.get_widths(_tenant(db))

    code = coding.suggest_code(db, parent=bank, widths=widths)

    assert code.startswith("1102")
    assert len(code) == len("1102") + widths[3]


def test_a_posted_account_cannot_take_children(db):
    """قیدِ اصلی: حسابی که سندِ مستقیم دارد نباید فرزند بگیرد.

    وگرنه مانده‌اش دو منبع پیدا می‌کند — ردیف‌های خودش و جمعِ فرزندان — و هر
    گزارشی باید حدس بزند کدام را جمع بزند.
    """
    from datetime import date
    from decimal import Decimal

    from app.models.accounting import JournalEntry, JournalLine
    from app.models.user import User

    tenant = _tenant(db)
    cash = db.query(Account).filter(Account.code == "1101").one()
    revenue = db.query(Account).filter(Account.code == "4101").one()
    entry = JournalEntry(
        entry_date=date(2026, 1, 1), description="آزمون", created_by_id=db.query(User.id).scalar()
    )
    entry.lines = [
        JournalLine(account_id=cash.id, debit=Decimal(100), credit=Decimal(0)),
        JournalLine(account_id=revenue.id, debit=Decimal(0), credit=Decimal(100)),
    ]
    db.add(entry)
    db.flush()

    with pytest.raises(HTTPException) as err:
        _create(db, tenant, code="110101", name="زیرصندوق", parent=cash)
    assert err.value.status_code == 409


def test_a_group_takes_children_even_with_no_documents(db):
    """سرفصل همیشه فرزند می‌گیرد — رفتارِ قبلی نباید عوض شده باشد."""
    tenant = _tenant(db)
    current = db.query(Account).filter(Account.code == "11").one()
    assert current.is_group is True

    child = _create(db, tenant, code="1150", name="حسابِ آزمایشی", parent=current)
    assert child.parent_id == current.id
