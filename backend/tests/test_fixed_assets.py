"""دارایی ثابت و استهلاک خط مستقیم — صحتِ سند دوطرفه، سقفِ استهلاک، و نبودِ دوباره‌کاری."""
from datetime import date
from decimal import Decimal

from app.models.accounting import Account, JournalEntry
from app.schemas.assets import FixedAssetIn
from app.services import assets as svc
from app.services import chart_codes as cc


def _make_asset(db, user, *, cost=1_200_000, salvage=0, life=12, acquired=date(2026, 1, 1)):
    return svc.create_asset(
        db,
        FixedAssetIn(
            name="خودرو",
            category="وسیله نقلیه",
            acquired_date=acquired,
            cost=Decimal(cost),
            salvage_value=Decimal(salvage),
            useful_life_months=life,
        ),
        user,
    )


def test_book_value_and_monthly(db, user):
    a = _make_asset(db, user, cost=1_200_000, salvage=0, life=12)
    assert a["monthly_depreciation"] == Decimal(100_000)
    assert a["book_value"] == Decimal(1_200_000)
    assert a["fully_depreciated"] is False


def test_run_depreciation_posts_balanced_entry(db, user):
    _make_asset(db, user, cost=1_200_000, salvage=0, life=12)
    res = svc.run_depreciation(db, date(2026, 1, 31), user)
    assert res["asset_count"] == 1
    assert res["total_amount"] == Decimal(100_000)

    entry = db.get(JournalEntry, res["journal_entry_id"])
    assert sum(l.debit for l in entry.lines) == sum(l.credit for l in entry.lines) == Decimal(100_000)
    exp = db.query(Account).filter(Account.system_role == cc.DEPRECIATION_EXPENSE).first()
    acc = db.query(Account).filter(Account.system_role == cc.ACCUMULATED_DEPRECIATION).first()
    assert any(l.account_id == exp.id and l.debit == Decimal(100_000) for l in entry.lines)
    assert any(l.account_id == acc.id and l.credit == Decimal(100_000) for l in entry.lines)


def test_same_period_not_depreciated_twice(db, user):
    _make_asset(db, user, cost=1_200_000, salvage=0, life=12)
    svc.run_depreciation(db, date(2026, 1, 31), user)
    res2 = svc.run_depreciation(db, date(2026, 1, 31), user)  # همان دوره دوباره
    assert res2["asset_count"] == 0
    assert res2["total_amount"] == Decimal(0)


def test_depreciation_stops_at_depreciable_base(db, user):
    # عمرِ ۳ ماه، بهای ۱۰۰ با اسقاطِ ۱۰ → مبنای ۹۰، ماهانه ۳۰. سه دوره باید دقیقاً ۹۰ شود.
    _make_asset(db, user, cost=100, salvage=10, life=3)
    for m in (1, 2, 3, 4):  # دوره‌ی چهارم نباید چیزی اضافه کند
        svc.run_depreciation(db, date(2026, m, 28), user)
    assets = svc.list_assets(db)
    a = assets[0]
    assert a["accumulated_depreciation"] == Decimal(90)
    assert a["book_value"] == Decimal(10)  # = ارزش اسقاط
    assert a["fully_depreciated"] is True


def test_not_acquired_yet_is_skipped(db, user):
    _make_asset(db, user, acquired=date(2026, 6, 1), cost=1_200_000, life=12)
    res = svc.run_depreciation(db, date(2026, 1, 31), user)  # قبل از تاریخِ تحصیل
    assert res["asset_count"] == 0


def test_acquisition_with_funding_posts_balanced_entry(db, user):
    """با انتخابِ حسابِ تأمین، خریدِ دارایی خودکار سند می‌خورد: بدهکارِ داراییِ ثابت، بستانکارِ همان حساب."""
    cash = db.query(Account).filter(Account.system_role == cc.CASH).first()
    svc.create_asset(
        db,
        FixedAssetIn(
            name="سرور", category="تجهیزات", acquired_date=date(2026, 1, 1),
            cost=Decimal(60_000_000), useful_life_months=60, funding_account_id=cash.id,
        ),
        user,
    )
    entry = db.query(JournalEntry).filter(JournalEntry.source_type == "asset_acquisition").one()
    assert sum(l.debit for l in entry.lines) == sum(l.credit for l in entry.lines) == Decimal(60_000_000)
    fixed = db.query(Account).filter(Account.system_role == cc.FIXED_ASSETS).first()
    assert any(l.account_id == fixed.id and l.debit == Decimal(60_000_000) for l in entry.lines)
    assert any(l.account_id == cash.id and l.credit == Decimal(60_000_000) for l in entry.lines)


def test_acquisition_without_funding_posts_no_entry(db, user):
    """بدونِ حسابِ تأمین (دارایی از قبل در دفاتر/آورده)، سندی زده نمی‌شود — رفتارِ قبلی حفظ می‌شود."""
    _make_asset(db, user, cost=1_200_000)
    assert db.query(JournalEntry).filter(JournalEntry.source_type == "asset_acquisition").count() == 0


# ─────────────────── تحویل/استقرار و جابه‌جایی ───────────────────


def _assign_in(**kw):
    from app.schemas.assets import AssetAssignmentIn

    kw.setdefault("assignment_date", date(2026, 2, 1))
    return AssetAssignmentIn(**kw)


def test_placement_records_the_custodian_on_the_asset(db, user):
    from tests.factories import make_contact

    asset = _make_asset(db, user)
    ali = make_contact(db, name="علی")

    out = svc.place_asset(db, asset["id"], _assign_in(to_custodian_id=ali.id, to_location="دفتر مرکزی"), user)
    assert out["custodian_id"] == ali.id
    assert out["custodian_name"] == "علی"
    assert out["location"] == "دفتر مرکزی"

    history = svc.list_assignments(db, asset_id=asset["id"])
    assert len(history) == 1
    assert history[0]["kind"] == "placement"
    assert history[0]["from_custodian_id"] is None  # اولین استقرار مبدأ ندارد


def test_transfer_keeps_both_ends_of_the_move(db, user):
    """«از چه کسی به چه کسی» باید روی خودِ ردیف باشد، نه حدس از ردیفِ قبلی."""
    from tests.factories import make_contact

    asset = _make_asset(db, user)
    ali, reza = make_contact(db, name="علی"), make_contact(db, name="رضا")

    svc.place_asset(db, asset["id"], _assign_in(to_custodian_id=ali.id, to_location="انبار"), user)
    out = svc.transfer_asset(
        db, asset["id"], _assign_in(assignment_date=date(2026, 3, 1), to_custodian_id=reza.id, to_location="کارگاه"), user
    )
    assert out["custodian_name"] == "رضا"
    assert out["location"] == "کارگاه"

    history = svc.list_assignments(db, asset_id=asset["id"])
    move = next(h for h in history if h["kind"] == "transfer")
    assert move["from_custodian_name"] == "علی"
    assert move["from_location"] == "انبار"
    assert move["to_custodian_name"] == "رضا"
    assert move["to_location"] == "کارگاه"


def test_a_location_only_move_does_not_clear_the_custodian(db, user):
    """جابه‌جاییِ محل نباید جمعدار را پاک کند — فیلدِ خالی یعنی «دست نزن»."""
    from tests.factories import make_contact

    asset = _make_asset(db, user)
    ali = make_contact(db, name="علی")
    svc.place_asset(db, asset["id"], _assign_in(to_custodian_id=ali.id, to_location="انبار"), user)

    out = svc.transfer_asset(db, asset["id"], _assign_in(assignment_date=date(2026, 3, 1), to_location="کارگاه"), user)
    assert out["location"] == "کارگاه"
    assert out["custodian_id"] == ali.id


def test_a_disposed_asset_cannot_be_moved(db, user):
    from tests.factories import make_contact

    asset = _make_asset(db, user)
    svc.dispose_asset(db, asset["id"], _disposal_in(disposal_date=date(2026, 6, 1), disposal_type="scrap"), user)
    ali = make_contact(db, name="علی")

    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as err:
        svc.transfer_asset(db, asset["id"], _assign_in(assignment_date=date(2026, 7, 1), to_custodian_id=ali.id), user)
    assert err.value.status_code == 409


def test_an_assignment_before_acquisition_is_rejected(db, user):
    from tests.factories import make_contact

    asset = _make_asset(db, user, acquired=date(2026, 5, 1))
    ali = make_contact(db, name="علی")

    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as err:
        svc.place_asset(db, asset["id"], _assign_in(assignment_date=date(2026, 4, 1), to_custodian_id=ali.id), user)
    assert err.value.status_code == 400


# ─────────────────── خروجِ دارایی (فروش/اسقاط/اهدا) ───────────────────


def _disposal_in(**kw):
    from app.schemas.assets import AssetDisposalIn

    kw.setdefault("disposal_date", date(2026, 6, 1))
    return AssetDisposalIn(**kw)


def _acc(db, role):
    return db.query(Account).filter(Account.system_role == role).first()


def test_disposal_removes_cost_and_accumulated_from_the_books(db, user):
    """باگی که این فاز می‌بندد: تا پیش از این، دارایی خارج‌شده با بهای کامل در ترازنامه می‌ماند.

    بهای ۱٫۲م، سه ماه استهلاک (۳۰۰ هزار) → ارزشِ دفتری ۹۰۰ هزار؛ فروش به ۹۰۰ هزار
    یعنی سود و زیانِ صفر و سندی که دقیقاً همان دو عدد را از دفتر بیرون می‌برد.
    """
    cash = _acc(db, cc.CASH)
    asset = _make_asset(db, user, cost=1_200_000, life=12)
    for m in (1, 2, 3):
        svc.run_depreciation(db, date(2026, m, 28), user)

    svc.dispose_asset(
        db, asset["id"],
        _disposal_in(disposal_type="sale", proceeds=Decimal(900_000), settlement_account_id=cash.id),
        user,
    )

    entry = db.query(JournalEntry).filter(JournalEntry.source_type == "asset_disposal").one()
    assert sum(l.debit for l in entry.lines) == sum(l.credit for l in entry.lines) == Decimal(1_200_000)
    assert any(l.account_id == _acc(db, cc.ACCUMULATED_DEPRECIATION).id and l.debit == Decimal(300_000) for l in entry.lines)
    assert any(l.account_id == cash.id and l.debit == Decimal(900_000) for l in entry.lines)
    assert any(l.account_id == _acc(db, cc.FIXED_ASSETS).id and l.credit == Decimal(1_200_000) for l in entry.lines)
    #: سود و زیانِ صفر یعنی هیچ ردیفِ سود/زیانی زده نشده
    assert len(entry.lines) == 3


def test_sale_above_book_value_books_a_gain(db, user):
    cash = _acc(db, cc.CASH)
    asset = _make_asset(db, user, cost=1_200_000, life=12)
    svc.run_depreciation(db, date(2026, 1, 31), user)  # انباشته ۱۰۰ هزار → دفتری ۱٫۱م

    svc.dispose_asset(
        db, asset["id"],
        _disposal_in(disposal_type="sale", proceeds=Decimal(1_500_000), settlement_account_id=cash.id),
        user,
    )
    rows = svc.list_disposals(db)
    assert len(rows) == 1
    assert rows[0]["book_value"] == Decimal(1_100_000)
    assert rows[0]["gain_loss"] == Decimal(400_000)

    entry = db.query(JournalEntry).filter(JournalEntry.source_type == "asset_disposal").one()
    assert any(l.account_id == _acc(db, cc.ASSET_DISPOSAL_GAIN).id and l.credit == Decimal(400_000) for l in entry.lines)
    assert sum(l.debit for l in entry.lines) == sum(l.credit for l in entry.lines)


def test_scrapping_writes_the_whole_book_value_off_as_a_loss(db, user):
    """اسقاط عوضی ندارد، پس کلِ ارزشِ دفتری زیان است — همان چیزی که قبلاً هیچ‌جا ثبت نمی‌شد."""
    asset = _make_asset(db, user, cost=1_200_000, life=12)
    svc.run_depreciation(db, date(2026, 1, 31), user)

    svc.dispose_asset(db, asset["id"], _disposal_in(disposal_type="scrap"), user)

    row = svc.list_disposals(db)[0]
    assert row["proceeds"] == Decimal(0)
    assert row["gain_loss"] == Decimal(-1_100_000)
    entry = db.query(JournalEntry).filter(JournalEntry.source_type == "asset_disposal").one()
    assert any(l.account_id == _acc(db, cc.ASSET_DISPOSAL_LOSS).id and l.debit == Decimal(1_100_000) for l in entry.lines)
    assert sum(l.debit for l in entry.lines) == sum(l.credit for l in entry.lines) == Decimal(1_200_000)


def test_disposal_snapshot_survives_a_later_edit_of_the_asset(db, user):
    """گزارشِ خروج نباید با ویرایشِ بعدیِ دارایی عوض شود — اعداد لحظه‌ی خروج عکس‌برداری‌اند."""
    from app.schemas.assets import FixedAssetIn

    asset = _make_asset(db, user, cost=1_200_000, life=12)
    svc.dispose_asset(db, asset["id"], _disposal_in(disposal_type="donation"), user)
    before = svc.list_disposals(db)[0]["cost_at_disposal"]

    svc.update_asset(
        db, asset["id"],
        FixedAssetIn(name="خودرو", category="وسیله نقلیه", acquired_date=date(2026, 1, 1),
                     cost=Decimal(5_000_000), useful_life_months=12),
    )
    assert svc.list_disposals(db)[0]["cost_at_disposal"] == before == Decimal(1_200_000)


def test_an_asset_cannot_be_disposed_twice(db, user):
    import pytest
    from fastapi import HTTPException

    asset = _make_asset(db, user)
    svc.dispose_asset(db, asset["id"], _disposal_in(disposal_type="scrap"), user)
    with pytest.raises(HTTPException) as err:
        svc.dispose_asset(db, asset["id"], _disposal_in(disposal_type="scrap"), user)
    assert err.value.status_code == 409


def test_scrap_with_proceeds_is_rejected(db, user):
    """مبلغِ دریافتی زیرِ عنوانِ «اسقاط» یعنی سودِ فروش گم می‌شود."""
    import pytest
    from pydantic import ValidationError

    cash = _acc(db, cc.CASH)
    with pytest.raises(ValidationError):
        _disposal_in(disposal_type="scrap", proceeds=Decimal(500), settlement_account_id=cash.id)


def test_sale_without_a_settlement_account_is_rejected(db, user):
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _disposal_in(disposal_type="sale", proceeds=Decimal(500))


def test_a_disposed_asset_is_skipped_by_depreciation(db, user):
    asset = _make_asset(db, user, cost=1_200_000, life=12)
    svc.dispose_asset(db, asset["id"], _disposal_in(disposal_date=date(2026, 1, 5), disposal_type="scrap"), user)
    assert svc.run_depreciation(db, date(2026, 1, 31), user)["asset_count"] == 0


def test_disposal_report_filters_by_type_and_range(db, user):
    a1 = _make_asset(db, user, cost=100, life=12)
    a2 = _make_asset(db, user, cost=200, life=12)
    svc.dispose_asset(db, a1["id"], _disposal_in(disposal_date=date(2026, 3, 1), disposal_type="scrap"), user)
    svc.dispose_asset(db, a2["id"], _disposal_in(disposal_date=date(2026, 8, 1), disposal_type="donation"), user)

    assert len(svc.list_disposals(db)) == 2
    assert len(svc.list_disposals(db, disposal_type="scrap")) == 1
    assert len(svc.list_disposals(db, date_from=date(2026, 6, 1))) == 1
    assert len(svc.list_disposals(db, date_to=date(2026, 1, 1))) == 0
