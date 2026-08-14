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
