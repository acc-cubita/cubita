"""بررسی‌های خانواده‌ی حسابرسی و نمره‌ی سلامت.

مهم‌ترین تستِ این فایل `test_ledger_family_output_is_unchanged` است: موتور مشترک
است و صفحه‌ی «بررسی یکپارچگی» را حسابدار هر روز باز می‌کند. هر تغییری در آن نُه
بررسی — حتی ترتیبشان — باید این‌جا قرمز بدهد.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.invoices import PurchaseInvoice
from app.models.user import User
from app.services import assurance_score, integrity
from app.services.integrity import FAMILY_ASSURANCE, FAMILY_LEDGER
from app.services.reports import ReportFilters

OWNER = "test-owner@example.invalid"

#: نُه بررسیِ خانواده‌ی دفتر، با همین ترتیب. این فهرست قفل است.
LEDGER_KEYS = [
    "unbalanced_entries",
    "group_account_lines",
    "leaf_with_children",
    "trial_vs_ledger",
    "empty_entries",
    "over_allocated",
    "unsettleable_balance",
    "inventory_vs_ledger",
    "stale_valuation",
]

RANGE = ReportFilters(date_from=date(2026, 1, 1), date_to=date(2026, 12, 29))


@pytest.fixture
def owner(db) -> User:
    return db.query(User).filter(User.email == OWNER).one()


def _run(db, filters=RANGE, families=(FAMILY_LEDGER, FAMILY_ASSURANCE)):
    return integrity.run_integrity_check(db, filters, families=families, row_limit=200)


def _keys(report) -> list[str]:
    return [c["key"] for c in report["checks"]]


def _check(report, key) -> dict:
    return next(c for c in report["checks"] if c["key"] == key)


def _entry(db, owner, **kwargs) -> JournalEntry:
    defaults = dict(
        number=kwargs.pop("number", 9_000),
        atf_number=kwargs.pop("atf_number", 9_000),
        entry_date=date(2026, 3, 1),
        description="آزمون",
        source_type="manual",
        created_by_id=owner.id,
        status="temporary",
    )
    defaults.update(kwargs)
    entry = JournalEntry(**defaults)
    db.add(entry)
    db.flush()
    return entry


def _purchase(db, owner, **kwargs) -> PurchaseInvoice:
    defaults = dict(
        number=kwargs.pop("number", 8_000),
        invoice_date=date(2026, 3, 1),
        supplier_invoice_number="",
        total_amount=Decimal(1_000_000),
        created_by_id=owner.id,
    )
    defaults.update(kwargs)
    invoice = PurchaseInvoice(**defaults)
    db.add(invoice)
    db.flush()
    return invoice


# ── قفلِ خانواده‌ی دفتر ──────────────────────────────────────────────────────


def test_ledger_family_output_is_unchanged(db):
    """صفحه‌ی حسابدار ذره‌ای عوض نشده: همان نُه بررسی، همان ترتیب، همان سقف."""
    report = integrity.run_integrity_check(db, RANGE)
    assert _keys(report) == LEDGER_KEYS
    assert all(c["family"] == FAMILY_LEDGER for c in report["checks"])


def test_default_call_excludes_assurance_family(db):
    report = integrity.run_integrity_check(db, RANGE)
    assert not any(c["family"] == FAMILY_ASSURANCE for c in report["checks"])


def test_assurance_family_is_added_on_request(db):
    report = _run(db)
    assert _keys(report)[: len(LEDGER_KEYS)] == LEDGER_KEYS
    assert len(report["checks"]) > len(LEDGER_KEYS)


def test_row_limit_parameter_raises_the_display_cap(db, owner):
    """سقفِ ۵۰ برای ابزارِ زنده است؛ snapshot باید بیشتر بگیرد."""
    for i in range(60):
        _purchase(db, owner, number=7_000 + i, supplier_invoice_number="")
    narrow = integrity.run_integrity_check(
        db, RANGE, families=(FAMILY_ASSURANCE,), row_limit=50
    )
    wide = integrity.run_integrity_check(
        db, RANGE, families=(FAMILY_ASSURANCE,), row_limit=200
    )
    assert len(_check(narrow, "missing_supplier_reference")["rows"]) == 50
    assert _check(narrow, "missing_supplier_reference")["truncated"] is True
    assert len(_check(wide, "missing_supplier_reference")["rows"]) == 60
    assert _check(wide, "missing_supplier_reference")["truncated"] is False
    #: شمارشِ کامل در هر دو یکی است — همان چیزی که در `summary` منجمد می‌شود.
    assert _check(narrow, "missing_supplier_reference")["count"] == 60


# ── بررسی‌ها ────────────────────────────────────────────────────────────────


def test_duplicate_supplier_invoice_is_flagged(db, owner):
    from app.models.inventory import Contact

    supplier = Contact(name="تأمین‌کننده")
    db.add(supplier)
    db.flush()
    _purchase(db, owner, number=8_001, contact_id=supplier.id, supplier_invoice_number="INV-7")
    _purchase(db, owner, number=8_002, contact_id=supplier.id, supplier_invoice_number="INV-7")

    check = _check(_run(db), "duplicate_supplier_invoice")
    assert check["count"] == 1
    assert check["severity"] == "error"
    assert "INV-7" in check["rows"][0]["label"]


def test_different_suppliers_with_the_same_number_are_not_flagged(db, owner):
    """شماره‌ی فاکتور مالِ فروشنده است؛ دو فروشنده می‌توانند شماره‌ی یکسان بدهند."""
    from app.models.inventory import Contact

    a, b = Contact(name="الف"), Contact(name="ب")
    db.add_all([a, b])
    db.flush()
    _purchase(db, owner, number=8_003, contact_id=a.id, supplier_invoice_number="INV-9")
    _purchase(db, owner, number=8_004, contact_id=b.id, supplier_invoice_number="INV-9")

    assert _check(_run(db), "duplicate_supplier_invoice")["count"] == 0


def test_voided_purchase_is_not_counted_as_duplicate(db, owner):
    from app.models.inventory import Contact

    supplier = Contact(name="تأمین‌کننده")
    db.add(supplier)
    db.flush()
    _purchase(db, owner, number=8_005, contact_id=supplier.id, supplier_invoice_number="INV-8")
    voided = _purchase(
        db, owner, number=8_006, contact_id=supplier.id, supplier_invoice_number="INV-8"
    )
    voided.voided_at = datetime.now(timezone.utc)
    db.flush()

    assert _check(_run(db), "duplicate_supplier_invoice")["count"] == 0


def test_missing_supplier_reference_is_flagged(db, owner):
    _purchase(db, owner, number=8_010, supplier_invoice_number="")
    assert _check(_run(db), "missing_supplier_reference")["count"] == 1


def test_undocumented_manual_entry_is_flagged(db, owner):
    _entry(db, owner, number=9_001, atf_number=9_001, description="")
    check = _check(_run(db), "undocumented_manual_entries")
    assert check["count"] == 1
    assert check["rows"][0]["entry_id"] is not None


def test_backdated_entry_is_flagged(db, owner):
    """تاریخِ سند خیلی عقب‌تر از لحظه‌ی ثبت."""
    entry = _entry(db, owner, number=9_002, atf_number=9_002, entry_date=date(2026, 1, 5))
    entry.created_at = datetime.now(timezone.utc)
    db.flush()
    keys = [r["entry_id"] for r in _check(_run(db), "backdated_entries")["rows"]]
    assert entry.id in keys


def test_opening_entry_is_not_treated_as_backdated(db, owner):
    """افتتاحیه عمداً عقب‌دار است؛ اگر این‌جا بیاید، بررسی در ماهِ اول بی‌اعتبار می‌شود."""
    entry = _entry(
        db,
        owner,
        number=9_003,
        atf_number=9_003,
        entry_date=date(2026, 1, 5),
        source_type="opening",
    )
    keys = [r["entry_id"] for r in _check(_run(db), "backdated_entries")["rows"]]
    assert entry.id not in keys


def test_long_lived_temporary_entry_is_flagged(db, owner):
    _entry(db, owner, number=9_004, atf_number=9_004, entry_date=date(2026, 1, 1), status="temporary")
    narrow = ReportFilters(date_from=date(2026, 1, 1), date_to=date(2026, 12, 29))
    check = _check(_run(db, narrow), "long_lived_temporary")
    assert check["count"] >= 1


def test_void_soon_after_create_is_flagged(db, owner):
    entry = _entry(db, owner, number=9_005, atf_number=9_005)
    entry.voided_at = entry.created_at + timedelta(minutes=2)
    db.flush()
    keys = [r["entry_id"] for r in _check(_run(db), "void_soon_after_create")["rows"]]
    assert entry.id in keys


def test_same_actor_create_and_finalize_is_flagged(db, owner):
    entry = _entry(db, owner, number=9_006, atf_number=9_006, status="permanent")
    entry.finalized_at = datetime.now(timezone.utc)
    entry.finalized_by_id = owner.id
    db.flush()
    assert _check(_run(db), "same_actor_create_and_finalize")["count"] >= 1


def test_off_hours_entries_group_by_actor(db, owner):
    """چهارده سندِ نیمه‌شب باید یک ردیف بدهد، نه چهارده ردیفِ تکراری."""
    midnight = datetime(2026, 3, 1, 0, 30, tzinfo=timezone.utc)
    for i in range(3):
        entry = _entry(db, owner, number=9_100 + i, atf_number=9_100 + i)
        entry.created_at = midnight
    db.flush()
    check = _check(_run(db), "off_hours_entries")
    assert check["count"] == 1, "باید یک ردیف به‌ازای هر کاربر باشد"


def test_out_of_sequence_numbers_detects_inversion(db, owner):
    """وارونگی، نه «با شمارشِ از ۱ جور نیست»."""
    _entry(db, owner, number=9_200, atf_number=9_200, entry_date=date(2026, 2, 1))
    _entry(db, owner, number=9_199, atf_number=9_199, entry_date=date(2026, 2, 2))
    assert _check(_run(db), "out_of_sequence_numbers")["count"] >= 1


def test_sequential_numbering_starting_high_is_not_flagged(db, owner):
    """دفتری که از ۹۳۰۰ شماره خورده ولی مرتب است، نباید هشدار بگیرد."""
    _entry(db, owner, number=9_300, atf_number=9_300, entry_date=date(2026, 5, 1))
    _entry(db, owner, number=9_301, atf_number=9_301, entry_date=date(2026, 5, 2))
    narrow = ReportFilters(date_from=date(2026, 5, 1), date_to=date(2026, 5, 30))
    assert _check(_run(db, narrow), "out_of_sequence_numbers")["count"] == 0


def test_expense_deviation_needs_a_range(db):
    check = _check(_run(db, ReportFilters()), "expense_period_deviation")
    assert check["count"] == 0


def test_expense_deviation_flags_a_jump(db, owner):
    account = (
        db.query(Account)
        .filter(Account.type == "expense", Account.is_group.is_(False))
        .first()
    )
    assert account is not None, "چارتِ پیش‌فرض باید حسابِ هزینه داشته باشد"

    def _expense(number: int, when: date, amount: int) -> None:
        entry = _entry(db, owner, number=number, atf_number=number, entry_date=when)
        db.add(JournalLine(entry_id=entry.id, seq=1, account_id=account.id, debit=amount, credit=0))
        db.flush()

    _expense(9_400, date(2026, 2, 10), 1_000_000)   # دوره‌ی قبل
    _expense(9_401, date(2026, 3, 10), 9_000_000)   # دوره‌ی جاری

    window = ReportFilters(date_from=date(2026, 3, 1), date_to=date(2026, 3, 31))
    check = _check(_run(db, window), "expense_period_deviation")
    assert check["count"] >= 1
    assert "افزایش" in check["rows"][0]["detail"]


# ── نمره ─────────────────────────────────────────────────────────────────────


def test_clean_ledger_scores_100(db):
    scored = assurance_score.score_report(
        {"checks": [], "total_debit": Decimal(0), "total_credit": Decimal(0)}
    )
    assert scored["score"] == Decimal("100.00")
    assert scored["grade"] == "healthy"


def test_every_check_key_has_a_weight(db):
    """بررسیِ تازه نباید بی‌صدا رایگان بماند."""
    report = _run(db)
    for check in report["checks"]:
        assert assurance_score.weight_for(check["key"], check["severity"]) > 0, check["key"]


def test_single_error_costs_a_fifth_of_its_weight():
    scored = assurance_score.score_report(
        {
            "checks": [
                {"key": "duplicate_supplier_invoice", "title": "x", "severity": "error", "count": 1}
            ],
            "total_debit": Decimal(0),
            "total_credit": Decimal(0),
        }
    )
    #: وزنِ این کلید ۱۲ است و اشباعِ خطا ۵ → ۱۲ × ۱/۵ = ۲٫۴
    assert scored["score"] == Decimal("97.60")


def test_saturation_caps_the_penalty():
    many = assurance_score.score_report(
        {
            "checks": [
                {"key": "duplicate_supplier_invoice", "title": "x", "severity": "error", "count": 500}
            ],
            "total_debit": Decimal(0),
            "total_credit": Decimal(0),
        }
    )
    assert many["score"] == Decimal("88.00")


def test_unbalanced_ledger_is_always_critical():
    scored = assurance_score.score_report(
        {"checks": [], "total_debit": Decimal(10), "total_credit": Decimal(9)}
    )
    assert scored["score"] == Decimal("100.00")
    assert scored["grade"] == "critical", "دفترِ ناتراز هر نمره‌ای بگیرد، بحرانی است"


def test_score_never_goes_below_zero():
    checks = [
        {"key": f"k{i}", "title": "x", "severity": "error", "count": 99} for i in range(40)
    ]
    scored = assurance_score.score_report(
        {"checks": checks, "total_debit": Decimal(0), "total_credit": Decimal(0)}
    )
    assert scored["score"] == Decimal("0.00")


def test_summary_freezes_the_weights_used(db):
    report = _run(db)
    scored = assurance_score.score_report(report)
    for row in scored["summary"]:
        assert "weight" in row and "lost" in row and "count" in row
