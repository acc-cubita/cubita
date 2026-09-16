"""تراکنشِ مالک و شریک — نوعِ صریح، و گاردی که قاعده‌ی پایدارِ ۲ هرگز نداشت.

**چه کم بود.** آورده‌ی مالک، برداشتش و وام‌های دوطرفه‌ی شریک هیچ موجودیتی
نداشتند. روی تولید، آورده‌ی ۲۰۰ میلیونیِ مالک به‌صورتِ **سندِ دستی** ثبت شده
(سند ۵، `source_type='manual'`). حسابداری‌اش درست است، ولی هیچ داده‌ای نمی‌گوید
این یک آورده بوده — پس «صورت تغییرات در حقوق صاحبان سهام» ساختاراً ناممکن بود.

**قاعده‌ی ۵۲:** «Direction یا PartyRole به‌تنهایی نوعِ حسابداری را تعیین نکند.»
ورودِ پول سه معنای متفاوت دارد و از روی جهت نمی‌شود فهمید کدام است. این فایل
همان را گارد می‌کند.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.accounting import JournalEntry, JournalLine
from app.models.inventory import Contact
from app.models.owner_transactions import OwnerTransaction
from app.schemas.owner_transactions import OwnerTransactionIn
from app.services import chart_codes as cc
from app.services.common import get_account
from app.services.owner_transactions import create_owner_transaction, partner_balance
from tests.factories import make_contact

TODAY = date(2026, 6, 1)


def _partner(db, name="شریکِ آزمون") -> Contact:
    contact = make_contact(db, name=name)
    contact.is_shareholder = True
    contact.share_percent = Decimal(40)
    db.flush()
    return contact


def _post(db, user, contact, kind, amount=1_000_000, on=TODAY):
    return create_owner_transaction(
        db,
        OwnerTransactionIn(
            type=kind, transaction_date=on, contact_id=contact.id,
            amount=Decimal(amount), method="cash",
        ),
        user,
    )


def _sides(db, entry_id) -> dict[str, tuple[Decimal, Decimal]]:
    """{کدِ حساب: (بدهکار، بستانکار)} — برای سنجشِ جهتِ سند."""
    out: dict[str, tuple[Decimal, Decimal]] = {}
    for line in db.query(JournalLine).filter(JournalLine.entry_id == entry_id).all():
        acc = line.account
        out[acc.code] = (Decimal(line.debit), Decimal(line.credit))
    return out


# ─────────────── قاعده‌ی ۵۲: جهت، نوع را تعیین نمی‌کند ───────────────


def test_three_inflows_with_the_same_direction_post_differently(db, user):
    """**هسته‌ی این اصلاح.**

    هر سه، پولِ **ورودی**اند. اگر نوع از جهت مشتق می‌شد، هر سه یک سند می‌زدند.
    """
    partner = _partner(db)
    capital = _post(db, user, partner, "capital_contribution")
    loan = _post(db, user, partner, "loan_to_entity")
    repay = _post(db, user, partner, "repayment_from_partner")

    capital_code = get_account(db, cc.OWNER_CAPITAL).code
    partner_code = get_account(db, cc.PARTNER_CURRENT).code

    assert capital_code in _sides(db, capital.journal_entry_id)
    assert partner_code in _sides(db, loan.journal_entry_id)
    assert partner_code in _sides(db, repay.journal_entry_id)
    assert capital_code not in _sides(db, loan.journal_entry_id), (
        "*** وامِ شریک روی حسابِ سرمایه نشست — جهت، نوع را تعیین کرد ***"
    )


def test_the_type_is_required_and_has_no_default(db):
    """پیش‌فرض‌دادن یعنی حدس‌زدنِ نوع از جهت — همان چیزی که قاعده منع می‌کند."""
    with pytest.raises(ValidationError):
        OwnerTransactionIn(
            transaction_date=TODAY, contact_id="00000000-0000-0000-0000-000000000001",
            amount=Decimal(1), method="cash",
        )


def test_an_unknown_type_is_refused(db):
    with pytest.raises(ValidationError):
        OwnerTransactionIn(
            type="owner_bonus", transaction_date=TODAY,
            contact_id="00000000-0000-0000-0000-000000000001",
            amount=Decimal(1), method="cash",
        )


# ─────────────── قاعده‌ی پایدارِ ۲: آورده ≠ درآمد ───────────────


def test_a_contribution_never_touches_an_income_account(db, user):
    """گارد ساختاری است، نه بررسی: کاربر حسابِ مقصد را انتخاب نمی‌کند.

    با سندِ دستی — تنها راهِ دیروز — هیچ چیزی جلوی نشاندنِ آورده در حسابِ درآمد
    را نمی‌گرفت.
    """
    partner = _partner(db)
    txn = _post(db, user, partner, "capital_contribution", amount=5_000_000)

    for line in db.query(JournalLine).filter(JournalLine.entry_id == txn.journal_entry_id).all():
        assert line.account.type != "income", "*** آورده در حسابِ درآمد نشست ***"
    assert get_account(db, cc.OWNER_CAPITAL).code in _sides(db, txn.journal_entry_id)


def test_a_withdrawal_never_touches_an_expense_account(db, user):
    partner = _partner(db)
    txn = _post(db, user, partner, "capital_withdrawal", amount=2_000_000)
    for line in db.query(JournalLine).filter(JournalLine.entry_id == txn.journal_entry_id).all():
        assert line.account.type != "expense", "*** برداشت در حسابِ هزینه نشست ***"


# ─────────────── جهتِ درستِ هر نوع ───────────────


def test_a_contribution_credits_capital(db, user):
    partner = _partner(db)
    txn = _post(db, user, partner, "capital_contribution", amount=3_000_000)
    debit, credit = _sides(db, txn.journal_entry_id)[get_account(db, cc.OWNER_CAPITAL).code]
    assert (debit, credit) == (Decimal(0), Decimal(3_000_000))


def test_a_capital_withdrawal_debits_capital(db, user):
    partner = _partner(db)
    txn = _post(db, user, partner, "capital_withdrawal", amount=1_500_000)
    debit, credit = _sides(db, txn.journal_entry_id)[get_account(db, cc.OWNER_CAPITAL).code]
    assert (debit, credit) == (Decimal(1_500_000), Decimal(0))


def test_the_partner_account_swings_both_ways(db, user):
    """قاعده‌ی ۵۲: «CurrentPartnerAccount می‌تواند بسته به رویداد debit یا credit شود».

    تنها حسابِ عمداً دوطرفه‌ی چارت.
    """
    partner = _partner(db)
    code = get_account(db, cc.PARTNER_CURRENT).code

    lent = _post(db, user, partner, "loan_to_entity", amount=4_000_000)
    assert _sides(db, lent.journal_entry_id)[code] == (Decimal(0), Decimal(4_000_000))

    took = _post(db, user, partner, "loan_from_entity", amount=1_000_000)
    assert _sides(db, took.journal_entry_id)[code] == (Decimal(1_000_000), Decimal(0))


def test_every_entry_balances(db, user):
    """قاعده‌ی پایدارِ ۷ — روی هر شش نوع."""
    partner = _partner(db)
    for kind in (
        "capital_contribution", "capital_withdrawal", "loan_to_entity",
        "loan_from_entity", "repayment_to_partner", "repayment_from_partner",
    ):
        txn = _post(db, user, partner, kind, amount=700_000)
        rows = db.query(JournalLine).filter(JournalLine.entry_id == txn.journal_entry_id).all()
        assert sum(Decimal(r.debit) for r in rows) == sum(Decimal(r.credit) for r in rows), kind


# ─────────────── طرفِ حساب باید سهامدار باشد ───────────────


def test_a_plain_customer_is_refused(db, user):
    """`Contact.is_shareholder` از قبل بود و هیچ‌کس استفاده‌اش نمی‌کرد.

    بی این گارد، «آورده‌ی سرمایه» به نامِ یک مشتریِ معمولی ثبت می‌شد و بعد هیچ
    گزارشی نمی‌توانست بگوید مالکانِ شرکت چه کسانی‌اند.
    """
    customer = make_contact(db, name="مشتریِ معمولی")
    with pytest.raises(HTTPException) as err:
        _post(db, user, customer, "capital_contribution")
    assert err.value.status_code == 400
    assert "سهامدار" in err.value.detail


# ─────────────── ماندهٔ شریک — مشتق، نه ذخیره‌شده ───────────────


def test_the_partner_balance_is_derived_from_the_documents(db, user):
    partner = _partner(db)
    _post(db, user, partner, "loan_to_entity", amount=10_000_000)
    _post(db, user, partner, "repayment_to_partner", amount=4_000_000)
    assert partner_balance(db, partner.id) == Decimal(6_000_000)


def test_capital_is_not_part_of_the_partner_balance(db, user):
    """آورده‌ی سرمایه بدهیِ شرکت به شریک نمی‌سازد — مالکیت است، نه وام.

    اگر این دو قاطی شوند، «صورت تغییرات در حقوق صاحبان سهام» سرمایه را دوبار
    می‌شمارد: یک‌بار در حقوق صاحبان سهام و یک‌بار در بدهی.
    """
    partner = _partner(db)
    _post(db, user, partner, "capital_contribution", amount=50_000_000)
    assert partner_balance(db, partner.id) == Decimal(0)


def test_a_withdrawal_makes_the_partner_owe_the_company(db, user):
    """تعارضِ C-04 — سمتِ «قابلِ بازپرداخت»ش."""
    partner = _partner(db)
    _post(db, user, partner, "loan_from_entity", amount=3_000_000)
    assert partner_balance(db, partner.id) == Decimal(-3_000_000)


def test_each_partner_keeps_their_own_balance(db, user):
    one = _partner(db, name="شریکِ الف")
    two = _partner(db, name="شریکِ ب")
    _post(db, user, one, "loan_to_entity", amount=8_000_000)
    _post(db, user, two, "loan_from_entity", amount=2_000_000)

    assert partner_balance(db, one.id) == Decimal(8_000_000)
    assert partner_balance(db, two.id) == Decimal(-2_000_000)


# ─────────────── چارت و نقش‌ها ───────────────


def test_the_two_new_roles_map_to_chart_codes(db):
    """نقشی که در راه‌اندازی روی حسابی ننشیند، نقشی است که کسی نمی‌تواند بدهدش —
    `system_role` از API قابلِ تنظیم نیست."""
    assert cc.DEFAULT_CODE_BY_ROLE[cc.OWNER_CAPITAL] == "3101"
    assert cc.DEFAULT_CODE_BY_ROLE[cc.PARTNER_CURRENT] == "2115"
    assert cc.ROLE_BY_DEFAULT_CODE["3101"] == cc.OWNER_CAPITAL
    assert cc.ROLE_BY_DEFAULT_CODE["2115"] == cc.PARTNER_CURRENT


def test_the_base_chart_has_a_partner_current_account(db):
    from app.seed import CHART_OF_ACCOUNTS

    row = next((r for r in CHART_OF_ACCOUNTS if r[0] == "2115"), None)
    assert row is not None, "*** حسابِ جاری شرکا از چارتِ پایه رفت ***"
    assert row[2] == "liability", "*** جاری شرکا بدهی است، نه حقوق صاحبان سهام ***"


def test_the_partner_account_is_financing_in_the_cash_flow(db):
    """وامِ شریک «تأمین مالی» است نه «عملیاتی» — قاعده‌ی ۲۰."""
    from app.services.reports import _cash_flow_category

    assert _cash_flow_category(get_account(db, cc.PARTNER_CURRENT)) == "financing"
    assert _cash_flow_category(get_account(db, cc.OWNER_CAPITAL)) == "financing"


# ─────────────── اندپوینت ───────────────


def test_the_endpoint_records_and_lists(client, db, user):
    partner = _partner(db, name="شریکِ اندپوینت")
    db.commit()

    response = client.post(
        "/api/owner-transactions",
        json={
            "type": "capital_contribution",
            "transaction_date": TODAY.isoformat(),
            "contact_id": str(partner.id),
            "amount": "9000000",
            "method": "cash",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["type_label"] == "آورده‌ی سرمایه"

    rows = client.get("/api/owner-transactions").json()["items"]
    assert any(r["contact_name"] == "شریکِ اندپوینت" for r in rows)

    balances = client.get("/api/owner-transactions/partner-balances").json()
    mine = next(b for b in balances if b["contact_id"] == str(partner.id))
    assert Decimal(mine["balance"]) == Decimal(0)
    assert Decimal(mine["share_percent"]) == Decimal(40)


def test_the_source_of_the_entry_points_back_at_the_transaction(db, user):
    """از سندِ حسابداری باید بشود به تراکنشِ شریک رسید — وگرنه سند یتیم است."""
    from app.services.entry_source import resolve_source

    partner = _partner(db)
    txn = _post(db, user, partner, "capital_contribution")
    entry = db.get(JournalEntry, txn.journal_entry_id)

    source = resolve_source(db, entry)
    assert source is not None, "*** سند به منبعش وصل نیست ***"
    assert source["model"] == "OwnerTransaction"
    assert source["id"] == txn.id


def test_voidable_documents_are_audited(db):
    """تستِ موجودِ `test_every_voidable_document_is_audited` این را می‌خواهد؛
    این‌جا صریح تکرار می‌شود چون سندِ تازه‌ای است."""
    from app.audit import audited_models

    assert OwnerTransaction in audited_models()
