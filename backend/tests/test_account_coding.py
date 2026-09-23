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


def test_a_posted_account_can_take_children(db):
    """حسابِ سندخورده هم زیرحساب می‌گیرد — و ردیف‌های قدیمی‌اش سرِ جایشان می‌مانند.

    تا ۱۴۰۵/۰۷/۰۱ این تست عکسش را قفل می‌کرد (۴۰۹)، با این ترس که «مانده دو منبع
    پیدا می‌کند و هر گزارشی باید حدس بزند». ترس سنجیده شد و واقعی نبود؛ دلیل در
    `routers/accounts.create_account`. کاربری که «صندوق» را به صندوق‌های جدا تقسیم
    می‌کرد، بعد از اولین سند راهی نداشت.

    مثالِ واقعیِ همان گزارش: «صندوق» حسابِ **سیستمی** است و سند خورده.
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

    child = _create(db, tenant, code="110101", name="زیرصندوق", parent=cash)

    assert child.parent_id == cash.id
    #: هیچ ردیفی جابه‌جا نشد — جابه‌جاکردن یعنی بازنویسیِ سندِ دائم.
    lines_on_cash = db.query(JournalLine).filter(JournalLine.account_id == cash.id).count()
    lines_on_child = db.query(JournalLine).filter(JournalLine.account_id == child.id).count()
    assert (lines_on_cash, lines_on_child) == (1, 0)
    #: و والد حسابِ گروه نشد؛ وگرنه ردیف‌های خودش از گزارش‌هایی که روی
    #: `is_group=False` صافی می‌گذارند بی‌صدا بیرون می‌افتادند.
    db.refresh(cash)
    assert cash.is_group is False


def test_trial_balance_keeps_a_posted_parents_own_lines(db):
    """همان چیزی که گاردِ قدیمی از آن می‌ترسید: آیا مانده گم یا دوبار شمرده می‌شود؟

    والدِ زیرحساب‌دار باید با ردیف‌های خودش در تراز بیاید، فرزند با ردیف‌های خودش،
    و جمعِ کل دقیقاً همان بماند. هر ردیفِ سند مالِ یک حساب است، پس نه جا افتادن
    ممکن است نه دوبارشمردن — ولی این تست همان را واقعاً می‌سنجد، نه ادعا می‌کند.
    """
    from datetime import date
    from decimal import Decimal

    from app.models.accounting import JournalEntry, JournalLine
    from app.models.user import User
    from app.services.reports import get_trial_balance

    tenant = _tenant(db)
    user_id = db.query(User.id).scalar()
    cash = db.query(Account).filter(Account.code == "1101").one()
    revenue = db.query(Account).filter(Account.code == "4101").one()

    def post(account, amount):
        e = JournalEntry(entry_date=date(2026, 1, 1), description="آزمون", created_by_id=user_id)
        e.lines = [
            JournalLine(account_id=account.id, debit=Decimal(amount), credit=Decimal(0)),
            JournalLine(account_id=revenue.id, debit=Decimal(0), credit=Decimal(amount)),
        ]
        db.add(e)
        db.flush()

    post(cash, 700)  # پیش از زیرحساب — روی خودِ صندوق
    child = _create(db, tenant, code="110101", name="صندوقِ اصلی", parent=cash)
    post(child, 300)  # پس از زیرحساب — روی زیرحساب

    rows = {r["account_code"]: r for r in get_trial_balance(db, None, None)}
    assert rows["1101"]["total_debit"] == Decimal(700), "ردیف‌های خودِ والد جا نیفتادند"
    assert rows["110101"]["total_debit"] == Decimal(300)
    total_debit = sum(r["total_debit"] for r in rows.values())
    total_credit = sum(r["total_credit"] for r in rows.values())
    assert total_debit == total_credit, "تراز باید همچنان متوازن باشد"


def test_a_group_takes_children_even_with_no_documents(db):
    """سرفصل همیشه فرزند می‌گیرد — رفتارِ قبلی نباید عوض شده باشد."""
    tenant = _tenant(db)
    current = db.query(Account).filter(Account.code == "11").one()
    assert current.is_group is True

    child = _create(db, tenant, code="1150", name="حسابِ آزمایشی", parent=current)
    assert child.parent_id == current.id
