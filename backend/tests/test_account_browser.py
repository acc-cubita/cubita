"""«مرور حساب‌ها» (UI-02) — درختِ تجمیعی و دفترِ صفحه‌بندی‌شده.

دو قید این‌جا قفل می‌شود:

1. **رقمِ هر سرفصل جمعِ منطقیِ زیرشاخه‌هایش است** و رقمِ هر برگ عیناً رقمِ تراز.
   جمع در سرور زده می‌شود (`get_balance_tree`) نه در مرورگر؛ اگر روزی کسی آن را
   به هسته‌ی دیگری وصل کند که با تراز فرق دارد، این‌جا لو می‌رود.
2. **برشِ دفتر همان مانده‌ای را دارد که دفترِ کامل.** صفحه‌بندی نباید مانده‌ی در حال
   اجرا را از صفر شروع کند.

هر تست چارتِ کوچکِ خودش را می‌سازد (کدهای یکتا) تا عددهایش به ترتیبِ اجرا وابسته
نباشد — همان دلیلی که `test_report_filters` حسابِ اختصاصی می‌سازد.
"""
from datetime import date
from decimal import Decimal
import itertools

import pytest

from app.models.accounting import Account, JournalLine
from app.models.cost_center import CostCenter
from app.services import accounting_ops as ops
from app.services.common import make_journal_entry
from app.services.reports import ReportFilters, get_general_ledger

JAN = date(2026, 1, 10)
MAR = date(2026, 3, 15)
JUN = date(2026, 6, 20)

_SEQ = itertools.count(1)


def _acc(db, name, kind, parent=None, group=False, nature=None) -> Account:
    row = Account(
        code=f"B{next(_SEQ):05d}",
        name=name,
        type=kind,
        is_group=group,
        nature=nature,
        parent_id=parent.id if parent else None,
    )
    db.add(row)
    db.flush()
    return row


def _post(db, user, when, debit_acc, credit_acc, amount, center=None):
    make_journal_entry(
        db, when, "آزمونِ مرور", "manual", user,
        [
            JournalLine(account_id=debit_acc.id, debit=Decimal(amount), credit=0,
                        cost_center_id=center.id if center else None),
            JournalLine(account_id=credit_acc.id, debit=0, credit=Decimal(amount),
                        cost_center_id=center.id if center else None),
        ],
    )
    db.flush()


def _tree(db, **kw):
    date_from = kw.pop("date_from", None)
    date_to = kw.pop("date_to", None)
    rows = ops.get_balance_tree(db, date_from, date_to, ReportFilters(date_from=date_from, date_to=date_to, **kw))
    return {r["account_id"]: r for r in rows}


@pytest.fixture
def bank_chart(db):
    """سناریوی بانک (§۳۷): دارایی / دارایی جاری / موجودی نقد و بانک / {بانک ملی، صندوق}."""
    assets = _acc(db, "دارایی", "asset", group=True)
    current = _acc(db, "دارایی جاری", "asset", assets, group=True)
    cash = _acc(db, "موجودی نقد و بانک", "asset", current, group=True)
    melli = _acc(db, "بانک ملی آزمون", "asset", cash)
    box = _acc(db, "صندوق آزمون", "asset", cash)
    income = _acc(db, "درآمد", "income", group=True)
    sales = _acc(db, "فروش آزمون", "income", income)
    return dict(assets=assets, current=current, cash=cash, melli=melli, box=box, income=income, sales=sales)


# ── سناریوی بانک ────────────────────────────────────────────────────────────


def test_bank_scenario_rolls_up_every_level(db, user, bank_chart):
    c = bank_chart
    _post(db, user, MAR, c["melli"], c["sales"], 20_000_000)

    tree = _tree(db)
    for key in ("melli", "cash", "current", "assets"):
        node = tree[c[key].id]
        assert node["closing"] == Decimal(20_000_000), key
        assert node["period_debit"] == Decimal(20_000_000), key
        assert node["period_credit"] == Decimal(0), key
        assert node["has_activity"], key
    #: سمتِ بستانکار: درآمد مانده‌ی منفی (= بستانکار) دارد.
    assert tree[c["sales"].id]["closing"] == Decimal(-20_000_000)
    assert tree[c["income"].id]["closing"] == Decimal(-20_000_000)
    #: صندوق بی‌گردش است ولی در درخت هست — حذف‌شده به نظر نمی‌رسد.
    assert tree[c["box"].id]["closing"] == 0
    assert tree[c["box"].id]["has_activity"] is False

    assert tree[c["cash"].id]["child_count"] == 2
    assert tree[c["melli"].id]["depth"] == tree[c["assets"].id]["depth"] + 3


def test_bank_scenario_ledger_opens_the_journal_entry(client, db, user, bank_chart):
    """مرور → دفترِ بانک ملی → همان سند (§۳۷). از راهِ HTTP، همان مسیری که رابط می‌رود."""
    c = bank_chart
    _post(db, user, MAR, c["melli"], c["sales"], 20_000_000)

    ledger = client.get(f"/api/reports/general-ledger/{c['melli'].id}?limit=50").json()
    assert ledger["total_lines"] == 1
    line = ledger["lines"][0]
    assert Decimal(line["debit"]) == Decimal(20_000_000)

    entry = client.get(f"/api/journal-entries/{line['entry_id']}")
    assert entry.status_code == 200
    accounts = {ln["account_id"] for ln in entry.json()["lines"]}
    assert accounts == {str(c["melli"].id), str(c["sales"].id)}


# ── قیدِ مالی: والد = جمعِ فرزندان، برگ = تراز ─────────────────────────────


def test_every_parent_equals_the_sum_of_its_children_across_the_whole_chart(db, user, bank_chart):
    """نه فقط چارتِ آزمون — **کلِ** چارتِ مستأجر، با همه‌ی داده‌ای که تا این‌جا هست."""
    c = bank_chart
    _post(db, user, JAN, c["melli"], c["sales"], 7_000_000)
    _post(db, user, MAR, c["sales"], c["box"], 2_500_000)  # برگشت از فروش، نقدی

    for date_from, date_to in ((None, None), (MAR, JUN)):
        rows = ops.get_balance_tree(db, date_from, date_to, ReportFilters(date_from=date_from, date_to=date_to))
        kids: dict = {}
        for r in rows:
            kids.setdefault(r["parent_id"], []).append(r)
        for r in rows:
            children = kids.get(r["account_id"], [])
            if not children:
                continue
            for field in ("opening", "period_debit", "period_credit", "closing"):
                assert r[field] == sum((ch[field] for ch in children), Decimal(0)), (r["account_code"], field)
        #: هر سند متوازن است، پس جمعِ ریشه‌ها صفر است.
        roots = kids[None]
        assert sum((r["closing"] for r in roots), Decimal(0)) == 0


def test_leaf_numbers_are_the_trial_balance_numbers(db, user, bank_chart):
    c = bank_chart
    _post(db, user, JAN, c["melli"], c["sales"], 4_000_000)
    _post(db, user, JUN, c["box"], c["melli"], 1_000_000)

    tree = _tree(db, date_from=MAR, date_to=JUN)
    for row in ops.get_balances(db, MAR, JUN, ReportFilters(date_from=MAR, date_to=JUN)):
        node = tree[row["account_id"]]
        assert node["period_debit"] == row["period_debit"]
        assert node["period_credit"] == row["period_credit"]
        assert node["closing"] == row["closing_debit"] - row["closing_credit"]
        assert node["opening"] == row["opening_debit"] - row["opening_credit"]


def test_mixed_natures_under_one_parent_net_correctly(db, user):
    """استهلاکِ انباشته (بستانکار) زیرِ دارایی ثابت (بدهکار): والد خالص را نشان می‌دهد."""
    fixed = _acc(db, "دارایی ثابت", "asset", group=True)
    building = _acc(db, "ساختمان", "asset", fixed)
    accum = _acc(db, "استهلاک انباشته", "asset", fixed, nature="credit")
    equity = _acc(db, "سرمایه آزمون", "equity")
    expense = _acc(db, "هزینه استهلاک آزمون", "expense")

    _post(db, user, JAN, building, equity, 100_000_000)
    _post(db, user, MAR, expense, accum, 30_000_000)

    tree = _tree(db)
    assert tree[building.id]["closing"] == Decimal(100_000_000)
    assert tree[accum.id]["closing"] == Decimal(-30_000_000)
    assert tree[fixed.id]["closing"] == Decimal(70_000_000)
    #: ماهیتِ صریحِ بستانکار با مانده‌ی بستانکار — هشدار نیست.
    assert tree[accum.id]["nature_violation"] is False
    assert tree[accum.id]["nature"] == "credit"


def test_a_leaf_against_its_nature_is_flagged_but_a_group_never_is(db, user, bank_chart):
    """اضافه‌برداشت: بانک (بدهکار) مانده‌ی بستانکار می‌گیرد → هشدارِ ماهیت روی برگ."""
    c = bank_chart
    expense = _acc(db, "هزینه آزمون", "expense")
    _post(db, user, MAR, expense, c["melli"], 5_000_000)

    tree = _tree(db)
    assert tree[c["melli"].id]["closing"] == Decimal(-5_000_000)
    assert tree[c["melli"].id]["nature_violation"] is True
    assert tree[c["cash"].id]["nature_violation"] is False


def test_lines_posted_directly_on_a_group_are_counted_and_flagged(db, user, bank_chart):
    """داده‌ی قدیمی: ردیف روی سرفصل. درخت باید با پایانِ دفترِ همان سرفصل بخواند."""
    c = bank_chart
    _post(db, user, MAR, c["melli"], c["sales"], 1_000_000)
    _post(db, user, MAR, c["box"], c["sales"], 500_000)
    # قاعده‌ی فعلی ثبت روی سرفصل را نمی‌پذیرد؛ داده‌ی قدیمی را شبیه‌سازی می‌کنیم.
    c["cash"].is_group = False
    db.flush()
    _post(db, user, MAR, c["cash"], c["sales"], 300_000)
    c["cash"].is_group = True
    db.flush()

    tree = _tree(db)
    node = tree[c["cash"].id]
    assert node["has_direct_lines"] is True
    assert node["closing"] == Decimal(1_800_000)
    assert node["closing"] == Decimal(get_general_ledger(db, c["cash"].id)["closing_balance"])
    assert tree[c["current"].id]["closing"] == Decimal(1_800_000)


# ── سناریوی هزینه و بازه‌ی تاریخ (§۳۸) ─────────────────────────────────────


def test_cost_scenario_the_date_range_moves_tree_and_ledger_together(db, user):
    expenses = _acc(db, "هزینه‌ها", "expense", group=True)
    admin = _acc(db, "هزینه‌های اداری", "expense", expenses, group=True)
    rent = _acc(db, "اجاره", "expense", admin)
    bank = _acc(db, "بانک هزینه آزمون", "asset")

    _post(db, user, JAN, rent, bank, 10_000_000)
    _post(db, user, MAR, rent, bank, 12_000_000)
    _post(db, user, JUN, rent, bank, 15_000_000)

    tree = _tree(db, date_from=MAR, date_to=MAR)
    for acc in (rent, admin, expenses):
        node = tree[acc.id]
        assert node["opening"] == Decimal(10_000_000)
        assert node["period_debit"] == Decimal(12_000_000)
        assert node["closing"] == Decimal(22_000_000)

    f = ReportFilters(date_from=MAR, date_to=MAR)
    ledger = get_general_ledger(db, rent.id, MAR, MAR, f)
    assert Decimal(ledger["opening_balance"]) == tree[rent.id]["opening"]
    assert Decimal(ledger["closing_balance"]) == tree[rent.id]["closing"]
    assert ledger["period_debit"] == tree[rent.id]["period_debit"]
    assert len(ledger["lines"]) == 1

    #: دفترِ سرفصل هم همان عدد را می‌دهد.
    group_ledger = get_general_ledger(db, expenses.id, MAR, MAR, f)
    assert Decimal(group_ledger["closing_balance"]) == tree[expenses.id]["closing"]


def test_cost_center_filter_narrows_tree_and_ledger(db, user):
    center = CostCenter(code=f"CC{next(_SEQ)}", name="شعبه آزمون", created_by_id=user.id)
    db.add(center)
    db.flush()
    rent = _acc(db, "اجاره مرکز", "expense")
    bank = _acc(db, "بانک مرکز", "asset")
    _post(db, user, MAR, rent, bank, 8_000_000, center=center)
    _post(db, user, MAR, rent, bank, 3_000_000)

    assert _tree(db)[rent.id]["closing"] == Decimal(11_000_000)
    assert _tree(db, cost_center_id=center.id)[rent.id]["closing"] == Decimal(8_000_000)

    ledger = get_general_ledger(db, rent.id, None, None, ReportFilters(cost_center_id=center.id))
    assert Decimal(ledger["closing_balance"]) == Decimal(8_000_000)
    assert ledger["lines"][0]["cost_center_name"] == "شعبه آزمون"


# ── صفحه‌بندیِ دفتر ─────────────────────────────────────────────────────────


def test_a_ledger_page_carries_the_running_balance_of_the_full_ledger(db, user):
    acc = _acc(db, "بانک صفحه‌بندی", "asset")
    other = _acc(db, "طرفِ مقابل", "equity")
    amounts = [5_000_000, 2_000_000, 7_000_000, 1_000_000, 9_000_000]
    for i, amount in enumerate(amounts):
        if i % 2:
            _post(db, user, date(2026, 2, 1 + i), other, acc, amount)
        else:
            _post(db, user, date(2026, 2, 1 + i), acc, other, amount)

    full = get_general_ledger(db, acc.id)
    page = get_general_ledger(db, acc.id, limit=2, offset=2)

    assert page["total_lines"] == full["total_lines"] == 5
    assert [ln["line_id"] for ln in page["lines"]] == [ln["line_id"] for ln in full["lines"][2:4]]
    assert [ln["balance"] for ln in page["lines"]] == [ln["balance"] for ln in full["lines"][2:4]]
    #: پایان و جمعِ گردش مالِ کلِ دوره است، نه برش.
    assert page["closing_balance"] == full["closing_balance"] == Decimal(18_000_000)
    assert page["period_debit"] == full["period_debit"] == Decimal(21_000_000)
    assert page["period_credit"] == Decimal(3_000_000)
    assert full["limit"] is None and page["limit"] == 2


def test_a_ledger_page_after_a_date_from_starts_from_the_opening(db, user):
    acc = _acc(db, "بانک افتتاحیه", "asset")
    other = _acc(db, "سرمایه افتتاحیه", "equity")
    _post(db, user, JAN, acc, other, 50_000_000)
    for day in range(1, 4):
        _post(db, user, date(2026, 3, day), acc, other, 1_000_000)

    f = ReportFilters(date_from=MAR, date_to=JUN)
    page = get_general_ledger(db, acc.id, date(2026, 3, 1), JUN, f, limit=1, offset=1)
    assert page["opening_balance"] == Decimal(50_000_000)
    assert page["lines"][0]["balance"] == Decimal(52_000_000)


def test_the_ledger_limit_is_bounded_by_max_limit(client, db, user):
    acc = _acc(db, "حسابِ سقف", "asset")
    assert client.get(f"/api/reports/general-ledger/{acc.id}?limit=201").status_code == 422
    assert client.get(f"/api/reports/general-ledger/{acc.id}?limit=200").status_code == 200


def test_an_unpaged_ledger_keeps_its_old_shape(db, user):
    """رگرسیون: بی‌`limit`، همه‌ی ردیف‌ها مثلِ پیش می‌آیند."""
    acc = _acc(db, "بانک بی‌صفحه", "asset")
    other = _acc(db, "سرمایه بی‌صفحه", "equity")
    for day in range(1, 6):
        _post(db, user, date(2026, 4, day), acc, other, 1_000_000)
    ledger = get_general_ledger(db, acc.id)
    assert len(ledger["lines"]) == ledger["total_lines"] == 5
    assert ledger["lines"][-1]["balance"] == ledger["closing_balance"] == Decimal(5_000_000)


# ── HTTP و مجوز ────────────────────────────────────────────────────────────


def test_balance_tree_endpoint_returns_the_whole_chart(client, db, user, bank_chart):
    c = bank_chart
    _post(db, user, MAR, c["melli"], c["sales"], 20_000_000)
    res = client.get("/api/accounting/balance-tree?date_from=2026-01-01&date_to=2026-12-29")
    assert res.status_code == 200
    rows = {r["account_id"]: r for r in res.json()}
    assert Decimal(rows[str(c["assets"].id)]["closing"]) == Decimal(20_000_000)
    assert rows[str(c["melli"].id)]["parent_id"] == str(c["cash"].id)
    assert rows[str(c["assets"].id)]["is_group"] is True


def test_balance_tree_needs_accounting_view(client, db, user):
    """مرور حساب مجوزِ تازه‌ای نمی‌سازد و هیچ مجوزی را دور نمی‌زند (§۳۱)."""
    from app.deps import get_principal
    from app.main import app

    principal = app.dependency_overrides[get_principal]()
    principal.permissions = {"sales": ["view"]}
    app.dependency_overrides[get_principal] = lambda: principal

    assert client.get("/api/accounting/balance-tree").status_code == 403
    assert client.get("/api/accounting/balances").status_code == 403


def test_fx_totals_cover_the_whole_period_even_on_a_page(db, user):
    acc = _acc(db, "بانک ارزی آزمون", "asset")
    other = _acc(db, "سرمایه ارزی آزمون", "equity")
    for day, fx in ((1, "100"), (2, "40"), (3, "10")):
        make_journal_entry(
            db, date(2026, 5, day), "ارزی", "manual", user,
            [
                JournalLine(account_id=acc.id, debit=Decimal(1_000_000), credit=0,
                            currency_code="USD", fx_amount=Decimal(fx), fx_rate=Decimal(10_000)),
                JournalLine(account_id=other.id, debit=0, credit=Decimal(1_000_000)),
            ],
        )
    db.flush()
    full = get_general_ledger(db, acc.id)
    page = get_general_ledger(db, acc.id, limit=1, offset=2)
    assert len(page["lines"]) == 1
    assert full["fx_totals"] == page["fx_totals"]
    assert Decimal(page["fx_totals"][0]["amount"]) == Decimal(150)
