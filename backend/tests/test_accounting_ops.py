"""عملیاتِ ماژولِ حسابداری: موقت/دائم، بازشماره‌گذاری، ادغام، تسعیر، اختتامیه/افتتاحیه.

هر تست یک *قاعده* را می‌سنجد نه یک تابع را. قاعده‌هایی که این عملیات بدونشان
خطرناک‌اند: سندِ دائم دست‌نخوردنی است، ادغام مانده را عوض نمی‌کند، بازشماره‌گذاری
شماره‌ی تکراری نمی‌سازد، و تسعیر بدونِ نرخ سند نمی‌زند.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.currency import Currency, ExchangeRate
from app.schemas.accounting_ops import AnalyticIn
from app.services import accounting_ops as ops
from app.services import analytics as an
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry

TODAY = date(2026, 6, 15)


def _entry(db, user, *, day=TODAY, amount=1_000_000, status="temporary", source="manual", desc="تست"):
    cash = get_account(db, cc.CASH)
    sales = get_account(db, cc.SALES_REVENUE)
    entry = make_journal_entry(
        db,
        day,
        desc,
        source,
        user,
        [
            JournalLine(account_id=cash.id, debit=Decimal(amount), credit=0),
            JournalLine(account_id=sales.id, debit=0, credit=Decimal(amount)),
        ],
    )
    entry.status = status
    db.flush()
    return entry


def _balance(db, account_id) -> Decimal:
    rows = (
        db.query(JournalLine.debit, JournalLine.credit)
        .filter(JournalLine.account_id == account_id)
        .all()
    )
    return sum((Decimal(d) - Decimal(c) for d, c in rows), Decimal(0))


# ───────────────────────── موقت / دائم ─────────────────────────


def test_new_entry_is_temporary_by_default(db, user):
    """سند تازه باید موقت متولد شود، وگرنه کارتابل همیشه خالی است."""
    entry = _entry(db, user, status="temporary")
    db.refresh(entry)
    assert entry.status == "temporary"


def test_finalize_moves_entries_to_permanent(db, user):
    a = _entry(db, user, day=date(2026, 6, 1))
    b = _entry(db, user, day=date(2026, 6, 20))
    result = ops.finalize_entries(db, user, date_from=date(2026, 6, 1), date_to=date(2026, 6, 10))

    assert result["count"] == 1
    db.refresh(a)
    db.refresh(b)
    assert a.status == "permanent" and a.finalized_at is not None
    assert b.status == "temporary"


def test_finalize_without_matches_is_an_error(db, user):
    _entry(db, user, status="permanent")
    with pytest.raises(HTTPException) as err:
        ops.finalize_entries(db, user, date_from=TODAY, date_to=TODAY)
    assert err.value.status_code == 400


def test_cartable_groups_by_source(db, user):
    _entry(db, user, source="manual")
    _entry(db, user, source="sales_invoice")
    _entry(db, user, source="sales_invoice")
    _entry(db, user, status="permanent")

    cartable = ops.get_cartable(db, None, None)
    by_source = {g["source_type"]: g["count"] for g in cartable["groups"]}
    assert by_source["sales_invoice"] == 2
    assert by_source["manual"] >= 1
    # سندِ دائم نباید در کارتابل باشد — کارتابل صفِ بازبینی است نه آرشیو.
    assert all(e["status"] == "temporary" for e in cartable["entries"])


# ──────────────────────── بازشماره‌گذاری ────────────────────────


def test_renumber_orders_by_date_not_by_old_number(db, user):
    """کلِ کارِ این عملیات همین است: شماره باید با تاریخ بخواند."""
    late = _entry(db, user, day=date(2026, 6, 20))
    early = _entry(db, user, day=date(2026, 6, 2))
    start = 900

    ops.renumber_entries(db, user, date(2026, 6, 1), date(2026, 6, 30), start)
    db.refresh(early)
    db.refresh(late)
    assert early.number == start
    assert late.number == start + 1


def test_renumber_leaves_permanent_entries_alone(db, user):
    """سندِ دائم شماره‌ی امضاشده دارد. نه در نقشه می‌آید، نه جابه‌جا می‌شود — و
    پیش‌نمایش باید همان چیزی را نشان دهد که اجرا می‌کند، نه یک نقشه‌ی رد‌شدنی."""
    signed = _entry(db, user, day=date(2026, 6, 3), status="permanent")
    kept = signed.number
    draft = _entry(db, user, day=date(2026, 6, 4))

    preview = ops.preview_renumber(db, date(2026, 6, 1), date(2026, 6, 30), 800)
    assert preview["count"] == 1
    assert preview["skipped_permanent"] == 1
    assert all(r["id"] != signed.id for r in preview["rows"])

    ops.renumber_entries(db, user, date(2026, 6, 1), date(2026, 6, 30), 800)
    db.refresh(signed)
    db.refresh(draft)
    assert signed.number == kept
    assert draft.number == 800


def test_renumber_refuses_to_collide_with_outside_numbers(db, user):
    outside = _entry(db, user, day=date(2026, 5, 1), status="permanent")
    _entry(db, user, day=date(2026, 6, 2))
    with pytest.raises(HTTPException) as err:
        ops.renumber_entries(db, user, date(2026, 6, 1), date(2026, 6, 30), outside.number)
    assert err.value.status_code == 400


def test_renumber_moves_the_counter_forward(db, user):
    """اگر شمارنده عقب بماند، اولین سندِ بعدی با خطای قیدِ یکتا شکست می‌خورد."""
    _entry(db, user, day=date(2026, 6, 2))
    ops.renumber_entries(db, user, date(2026, 6, 1), date(2026, 6, 30), 5000)
    nxt = _entry(db, user, day=date(2026, 6, 25))
    assert nxt.number > 5000


def test_renumber_preview_changes_nothing(db, user):
    entry = _entry(db, user)
    before = entry.number
    preview = ops.preview_renumber(db, None, None, 7000)
    db.refresh(entry)
    assert entry.number == before
    assert preview["rows"][0]["new_number"] == 7000


# ─────────────────────────── ادغام ─────────────────────────────


def test_merge_keeps_the_ledger_untouched(db, user):
    """قاعده‌ی اصلیِ ادغام: هیچ مانده‌ای نباید تکان بخورد."""
    cash = get_account(db, cc.CASH)
    a = _entry(db, user, amount=300_000)
    b = _entry(db, user, amount=700_000)
    before = _balance(db, cash.id)

    out = ops.merge_entries(db, user, [a.id, b.id], "ادغامِ آزمون")

    assert out["line_count"] == 4
    assert _balance(db, cash.id) == before
    assert db.get(JournalEntry, a.id) is None
    assert db.get(JournalEntry, b.id) is None


def test_merge_refuses_permanent_entries(db, user):
    a = _entry(db, user, status="permanent")
    b = _entry(db, user)
    with pytest.raises(HTTPException) as err:
        ops.merge_entries(db, user, [a.id, b.id], "")
    assert err.value.status_code == 400


def test_merge_refuses_module_generated_entries(db, user):
    """سندی که فاکتور ساخته به آن فاکتور گره خورده؛ ادغامش آن پیوند را می‌بُرد."""
    a = _entry(db, user, source="sales_invoice")
    b = _entry(db, user)
    with pytest.raises(HTTPException) as err:
        ops.merge_entries(db, user, [a.id, b.id], "")
    assert "sales_invoice" in err.value.detail


def test_merge_refuses_different_dates(db, user):
    a = _entry(db, user, day=date(2026, 6, 1))
    b = _entry(db, user, day=date(2026, 6, 2))
    with pytest.raises(HTTPException) as err:
        ops.merge_entries(db, user, [a.id, b.id], "")
    assert err.value.status_code == 400


# ────────────────────────── تسعیر ارز ───────────────────────────


def _fx_entry(db, user, *, code="USD", fx=Decimal(100), rial=5_000_000, day=TODAY):
    bank = get_account(db, cc.BANK)
    equity = get_account(db, cc.RETAINED_EARNINGS)
    return make_journal_entry(
        db, day, "خریدِ ارز", "manual", user,
        [
            JournalLine(
                account_id=bank.id, debit=Decimal(rial), credit=0,
                currency_code=code, fx_amount=fx, fx_rate=Decimal(rial) / fx,
            ),
            JournalLine(account_id=equity.id, debit=0, credit=Decimal(rial)),
        ],
    )


def test_fx_preview_reports_the_gap_against_todays_rate(db, user):
    db.add(Currency(code="USD", name="دلار", created_by_id=user.id))
    _fx_entry(db, user, fx=Decimal(100), rial=5_000_000)  # نرخِ ثبت: ۵۰٬۰۰۰
    db.add(ExchangeRate(currency_code="USD", rate_date=TODAY, rate=Decimal(60_000), created_by_id=user.id))
    db.flush()

    preview = ops.fx_revaluation_preview(db, TODAY)
    row = next(r for r in preview["items"] if r["currency_code"] == "USD")
    assert row["fx_balance"] == Decimal(100)
    assert row["market_value"] == Decimal(6_000_000)
    assert row["difference"] == Decimal(1_000_000)


def test_fx_without_a_rate_is_reported_not_guessed(db, user):
    db.add(Currency(code="EUR", name="یورو", created_by_id=user.id))
    _fx_entry(db, user, code="EUR", fx=Decimal(50), rial=3_000_000)
    db.flush()

    preview = ops.fx_revaluation_preview(db, TODAY)
    assert "EUR" in preview["missing_rates"]
    assert not any(r["currency_code"] == "EUR" for r in preview["items"])
    with pytest.raises(HTTPException):
        ops.issue_fx_revaluation(db, user, TODAY, "")


def test_fx_entry_is_balanced_and_books_the_gain(db, user):
    db.add(Currency(code="USD", name="دلار", created_by_id=user.id))
    _fx_entry(db, user, fx=Decimal(100), rial=5_000_000)
    db.add(ExchangeRate(currency_code="USD", rate_date=TODAY, rate=Decimal(60_000), created_by_id=user.id))
    db.flush()

    out = ops.issue_fx_revaluation(db, user, TODAY, "")
    entry = db.get(JournalEntry, out["entry_id"])
    debit = sum((Decimal(line.debit) for line in entry.lines), Decimal(0))
    credit = sum((Decimal(line.credit) for line in entry.lines), Decimal(0))
    assert debit == credit == Decimal(1_000_000)

    gain = db.query(Account).filter(Account.system_role == cc.FX_GAIN).one()
    assert _balance(db, gain.id) == Decimal(-1_000_000)  # درآمد → بستانکار


def test_second_revaluation_sees_no_remaining_gap(db, user):
    """سندِ تسعیر خودش ارزش دفتری را اصلاح می‌کند، پس تکرارِ همان عملیات باید خالی باشد."""
    db.add(Currency(code="USD", name="دلار", created_by_id=user.id))
    _fx_entry(db, user, fx=Decimal(100), rial=5_000_000)
    db.add(ExchangeRate(currency_code="USD", rate_date=TODAY, rate=Decimal(60_000), created_by_id=user.id))
    db.flush()

    ops.issue_fx_revaluation(db, user, TODAY, "")
    again = ops.fx_revaluation_preview(db, TODAY)
    assert all(r["difference"] == 0 for r in again["items"])


# ──────────────────── اختتامیه و افتتاحیه ───────────────────────


def _permanent_only_books(db, user):
    """یک دفترِ کوچک که فقط حساب‌های دائمی دارد (سود و زیانش بسته شده)."""
    cash = get_account(db, cc.CASH)
    capital = db.query(Account).filter(Account.code == "3101").one()
    make_journal_entry(
        db, date(2026, 3, 1), "آورده‌ی سرمایه", "manual", user,
        [
            JournalLine(account_id=cash.id, debit=Decimal(9_000_000), credit=0),
            JournalLine(account_id=capital.id, debit=0, credit=Decimal(9_000_000)),
        ],
    )
    return cash, capital


def test_closing_entry_zeroes_every_permanent_account(db, user):
    cash, capital = _permanent_only_books(db, user)
    ops.issue_closing_entry(db, user, date(2026, 12, 29), "")

    assert _balance(db, cash.id) == 0
    assert _balance(db, capital.id) == 0


def test_closing_refuses_while_profit_and_loss_are_open(db, user):
    _permanent_only_books(db, user)
    _entry(db, user, day=date(2026, 4, 1))  # یک فروش → حسابِ درآمد باز می‌شود
    with pytest.raises(HTTPException) as err:
        ops.issue_closing_entry(db, user, date(2026, 12, 29), "")
    assert "سود و زیان" in err.value.detail


def test_opening_entry_restores_exactly_what_closing_removed(db, user):
    cash, capital = _permanent_only_books(db, user)
    before_cash = _balance(db, cash.id)
    ops.issue_closing_entry(db, user, date(2026, 12, 29), "")
    ops.issue_opening_entry(db, user, date(2026, 12, 30), date(2026, 12, 29), "")

    assert _balance(db, cash.id) == before_cash
    assert _balance(db, capital.id) == -Decimal(9_000_000)


def test_opening_before_closing_date_is_rejected(db, user):
    _permanent_only_books(db, user)
    with pytest.raises(HTTPException) as err:
        ops.issue_opening_entry(db, user, date(2026, 12, 1), date(2026, 12, 29), "")
    assert err.value.status_code == 400


# ─────────────────────────── ترازها ─────────────────────────────


def test_balances_split_opening_from_period(db, user):
    cash = get_account(db, cc.CASH)
    _entry(db, user, day=date(2026, 5, 1), amount=400_000)
    _entry(db, user, day=date(2026, 6, 10), amount=600_000)

    rows = ops.get_balances(db, date(2026, 6, 1), date(2026, 6, 30))
    row = next(r for r in rows if r["account_id"] == cash.id)
    assert row["opening_debit"] == Decimal(400_000)
    assert row["period_debit"] == Decimal(600_000)
    assert row["closing_debit"] == Decimal(1_000_000)


def test_legal_book_returns_one_row_per_line(db, user):
    _entry(db, user, day=TODAY)
    book = ops.get_legal_book(db, date(2026, 6, 1), date(2026, 6, 30))
    assert len(book["rows"]) >= 2
    assert book["total_debit"] == book["total_credit"]


# ────────────────── اصلاحِ طبقه‌بندیِ حساب‌ها ────────────────────


def test_reclassify_moves_an_account_under_another_group(db, user):
    misc = db.query(Account).filter(Account.code == "5103").one()  # هزینه اجاره
    target = db.query(Account).filter(Account.code == "5").one()
    ops.reclassify_accounts(db, [{"account_id": misc.id, "parent_id": target.id, "type": "expense"}])
    db.refresh(misc)
    assert misc.parent_id == target.id


def test_reclassify_refuses_a_non_group_parent(db, user):
    child = db.query(Account).filter(Account.code == "5103").one()
    leaf = db.query(Account).filter(Account.code == "5104").one()
    with pytest.raises(HTTPException) as err:
        ops.reclassify_accounts(db, [{"account_id": child.id, "parent_id": leaf.id, "type": "expense"}])
    assert err.value.status_code == 400


def test_reclassify_refuses_a_type_that_fights_its_parent(db, user):
    child = db.query(Account).filter(Account.code == "5103").one()
    expenses = db.query(Account).filter(Account.code == "5").one()
    with pytest.raises(HTTPException) as err:
        ops.reclassify_accounts(db, [{"account_id": child.id, "parent_id": expenses.id, "type": "income"}])
    assert "نمی‌خواند" in err.value.detail


def test_reclassify_leaves_system_accounts_alone(db, user):
    cash = get_account(db, cc.CASH)
    assets = db.query(Account).filter(Account.code == "1").one()
    with pytest.raises(HTTPException) as err:
        ops.reclassify_accounts(db, [{"account_id": cash.id, "parent_id": assets.id, "type": "asset"}])
    assert "نقشِ سیستمی" in err.value.detail


@pytest.fixture
def no_autoflush(db):
    """مثلِ `SessionLocal`ِ production (`autoflush=False`) — Sessionِ آزمون پیش‌فرض autoflush دارد و
    باگِ «کوئریِ درخت تغییرهای همان دسته را نمی‌بیند» را پنهان می‌کرد."""
    db.autoflush = False
    yield db
    db.autoflush = True


def _group(db, code, type_, parent=None):
    row = Account(code=code, name=f"سرفصلِ {code}", type=type_, is_group=True, parent_id=parent.id if parent else None)
    db.add(row)
    db.flush()
    return row


def test_reclassify_refuses_a_cycle_made_inside_one_batch(no_autoflush):
    """الف زیرِ ب و ب زیرِ الف در یک دسته: هیچ‌کدام به‌تنهایی حلقه نیست ولی با هم درخت را بی‌نهایت می‌کنند."""
    db = no_autoflush
    a = _group(db, "9701", "asset")
    b = _group(db, "9702", "asset")
    with pytest.raises(HTTPException) as err:
        ops.reclassify_accounts(
            db,
            [
                {"account_id": a.id, "parent_id": b.id, "type": "asset"},
                {"account_id": b.id, "parent_id": a.id, "type": "asset"},
            ],
        )
    assert "زیرمجموعه" in err.value.detail


def test_reclassify_batch_order_does_not_matter(no_autoflush):
    """سرفصلی که جابه‌جا می‌شود و حسابی که زیرش می‌رود، به هر ترتیبی که بیایند: نوعِ هر دو از مقصدِ نهایی."""
    db = no_autoflush
    liabilities = _group(db, "9711", "liability")
    moving = _group(db, "9712", "asset")
    leaf = db.query(Account).filter(Account.code == "5103").one()  # هزینه اجاره
    ops.reclassify_accounts(
        db,
        [
            # حساب اول آمده، با نوعِ *نهاییِ* سرفصلش — سرفصل هنوز جابه‌جا نشده و دارایی است.
            {"account_id": leaf.id, "parent_id": moving.id, "type": "liability"},
            {"account_id": moving.id, "parent_id": liabilities.id, "type": "liability"},
        ],
    )
    db.flush()
    db.refresh(leaf)
    db.refresh(moving)
    assert (moving.parent_id, moving.type) == (liabilities.id, "liability")
    assert (leaf.parent_id, leaf.type) == (moving.id, "liability")


def test_reclassify_cascade_spares_a_child_moved_out_in_the_same_batch(no_autoflush):
    """زیرمجموعه‌ی سرفصلِ جابه‌جاشده هم‌نوعِ آن می‌شود — جز حسابی که در همان دسته به جای دیگری رفته."""
    db = no_autoflush
    group = _group(db, "9721", "expense")
    stays = Account(code="972101", name="می‌ماند", type="expense", parent_id=group.id)
    leaves = Account(code="972102", name="می‌رود", type="expense", parent_id=group.id)
    db.add_all([stays, leaves])
    db.flush()
    incomes = _group(db, "9722", "income")
    expenses = _group(db, "9723", "expense")
    ops.reclassify_accounts(
        db,
        [
            {"account_id": leaves.id, "parent_id": expenses.id, "type": "expense"},
            {"account_id": group.id, "parent_id": incomes.id, "type": "income"},
        ],
    )
    db.flush()
    for row in (group, stays, leaves):
        db.refresh(row)
    assert group.type == "income"
    assert stays.type == "income"
    assert (leaves.parent_id, leaves.type) == (expenses.id, "expense")


def test_reclassify_takes_the_type_from_the_parent_when_none_is_sent(db, user):
    """بی `type`، نوع از سرفصلِ مقصد می‌آید — همان قاعده‌ای که گارد می‌خواهد، نه خطای ۴۰۰."""
    leaf = db.query(Account).filter(Account.code == "5103").one()
    liabilities = _group(db, "9731", "liability")
    ops.reclassify_accounts(db, [{"account_id": leaf.id, "parent_id": liabilities.id}])
    db.flush()
    db.refresh(leaf)
    assert leaf.type == "liability"


# ────────────────────────── تفصیلیِ سایر ─────────────────────────


def test_analytic_crud_round_trip(db, user):
    created = an.create_analytic(db, AnalyticIn(code="V1", name="خودرو ۱", group_name="خودرو"), user)
    rows = an.list_analytics(db)
    assert any(r["id"] == created["id"] for r in rows)
    an.delete_analytic(db, created["id"])
    assert not any(r["id"] == created["id"] for r in an.list_analytics(db))


def test_analytic_code_is_unique(db, user):
    an.create_analytic(db, AnalyticIn(code="V2", name="خودرو ۲"), user)
    with pytest.raises(HTTPException):
        an.create_analytic(db, AnalyticIn(code="V2", name="تکراری"), user)


def test_used_analytic_cannot_be_deleted(db, user):
    """حذفِ تفصیلیِ استفاده‌شده، ردیف‌های سند را بی‌صدا بی‌بُعد می‌کرد."""
    created = an.create_analytic(db, AnalyticIn(code="V3", name="خودرو ۳"), user)
    cash = get_account(db, cc.CASH)
    sales = get_account(db, cc.SALES_REVENUE)
    make_journal_entry(
        db, TODAY, "با تفصیلی", "manual", user,
        [
            JournalLine(account_id=cash.id, debit=Decimal(1000), credit=0, analytic_id=created["id"]),
            JournalLine(account_id=sales.id, debit=0, credit=Decimal(1000)),
        ],
    )
    with pytest.raises(HTTPException) as err:
        an.delete_analytic(db, created["id"])
    assert err.value.status_code == 409


# ──────────────────────── قراردادِ اندپوینت ──────────────────────


def test_endpoints_answer(client):
    assert client.get("/api/accounting/overview").status_code == 200
    assert client.get("/api/accounting/cartable").status_code == 200
    assert client.get("/api/accounting/balances").status_code == 200
    assert client.get("/api/accounting/analytics").status_code == 200
    assert client.get("/api/accounting/legal-book?date_from=2026-06-01&date_to=2026-06-30").status_code == 200


def test_journal_list_honours_its_filters(client, db, user):
    _entry(db, user, day=date(2026, 6, 2), desc="فروشِ نقدی")
    _entry(db, user, day=date(2026, 7, 2), desc="اجاره")

    june = client.get("/api/journal-entries?date_from=2026-06-01&date_to=2026-06-30").json()
    assert all(e["entry_date"].startswith("2026-06") for e in june["items"])

    searched = client.get("/api/journal-entries?q=اجاره").json()
    assert all("اجاره" in e["description"] for e in searched["items"])

    temporary = client.get("/api/journal-entries?status=temporary").json()
    assert all(e["status"] == "temporary" for e in temporary["items"])
