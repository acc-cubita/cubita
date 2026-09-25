"""اصلاحِ طبقه‌بندیِ مانده — بدونِ دست‌زدن به تاریخ.

**این با «انتقال حساب به سرفصل دیگر» یکی نیست.** آن یکی `parent_id`ِ خودِ حساب را
عوض می‌کند، یعنی گزارشِ *پارسال* هم از امروز طورِ دیگری دیده می‌شود. این یکی
اسنادِ گذشته را دست نمی‌زند و مانده را با یک سندِ متوازنِ تاریخ‌دار جابه‌جا می‌کند.

قیدِ اصلی که این فایل نگه می‌دارد: **فقط مانده‌ی همان تفصیلی منتقل می‌شود**، نه
مانده‌ی کلِ حسابِ معین.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.analytic import AnalyticAccount
from app.models.tenant import Tenant
from app.services import accounting_ops as ops
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.tenant_context import session_tenant

DAY = date(2026, 6, 1)
LATER = date(2026, 6, 10)


def _set_mode(db, mode: str) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = mode
    db.flush()


def _analytic(db, user, code: str, name: str) -> AnalyticAccount:
    row = AnalyticAccount(code=code, name=name, created_by_id=user.id)
    db.add(row)
    db.flush()
    return row


def _post(db, user, account, analytic, amount: int, *, day=DAY) -> JournalEntry:
    """مبلغ را بدهکارِ (حساب، تفصیلی) می‌کند و بستانکارِ سرمایه."""
    equity = get_account(db, cc.RETAINED_EARNINGS)
    return make_journal_entry(
        db,
        day,
        "ثبتِ اولیه",
        "manual",
        user,
        [
            JournalLine(account_id=account.id, analytic_id=analytic.id if analytic else None,
                        debit=Decimal(amount), credit=0),
            JournalLine(account_id=equity.id, debit=0, credit=Decimal(amount)),
        ],
    )


def _balance(db, account, analytic_id, as_of=LATER) -> Decimal:
    for acc, aid, raw in ops.analytic_balances(db, as_of, {account.id}):
        if aid == analytic_id:
            return raw
    return Decimal(0)


def _pair(db):
    """دو حسابِ تفصیلی‌پذیر: مبدأ و مقصد."""
    src = get_account(db, cc.BANK)
    dest = get_account(db, cc.CASH)
    src.accepts_tafsili = True
    dest.accepts_tafsili = True
    db.flush()
    return src, dest


# ── قیدِ اصلی: فقط همان تفصیلی ──────────────────────────────────────────────


def test_only_the_selected_analytic_moves(db, user):
    """**قیدِ §۱۳.** حساب ده‌ها تفصیلی دارد؛ فقط یکی اشتباه طبقه‌بندی شده."""
    _set_mode(db, "hybrid")
    src, dest = _pair(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    beta = _analytic(db, user, "B1", "شرکت بتا")
    _post(db, user, src, alpha, 18_000_000)
    _post(db, user, src, beta, 25_000_000)

    ops.issue_reclass(
        db, user, LATER, [{"account_id": src.id, "analytic_id": alpha.id}], dest.id, alpha.id, ""
    )
    db.flush()

    assert _balance(db, src, alpha.id) == 0, "مبدأ باید صفر شود"
    assert _balance(db, src, beta.id) == Decimal(25_000_000), "تفصیلیِ دوم دست‌نخورده"
    assert _balance(db, dest, alpha.id) == Decimal(18_000_000)


def test_history_is_untouched(db, user):
    """**رگرسیونِ §۳.** اسنادِ گذشته بازنویسی نمی‌شوند."""
    _set_mode(db, "hybrid")
    src, dest = _pair(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    original = _post(db, user, src, alpha, 18_000_000)
    before = [(l.account_id, l.analytic_id, l.debit, l.credit) for l in original.lines]

    ops.issue_reclass(
        db, user, LATER, [{"account_id": src.id, "analytic_id": alpha.id}], dest.id, alpha.id, ""
    )
    db.flush()
    db.refresh(original)

    assert [(l.account_id, l.analytic_id, l.debit, l.credit) for l in original.lines] == before
    assert original.voided_at is None


# ── جهت از مانده می‌آید ─────────────────────────────────────────────────────


def test_a_credit_balance_reverses_the_direction(db, user):
    """**§۱۲.** «مبدأ بدهکار / مقصد بستانکار» هیچ‌جا ثابت نوشته نشده."""
    _set_mode(db, "hybrid")
    src, dest = _pair(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    #: این بار مبدأ *بستانکار* می‌شود.
    equity = get_account(db, cc.RETAINED_EARNINGS)
    make_journal_entry(
        db, DAY, "بستانکار", "manual", user,
        [
            JournalLine(account_id=src.id, analytic_id=alpha.id, debit=0, credit=Decimal(7_000_000)),
            JournalLine(account_id=equity.id, debit=Decimal(7_000_000), credit=0),
        ],
    )

    out = ops.issue_reclass(
        db, user, LATER, [{"account_id": src.id, "analytic_id": alpha.id}], dest.id, alpha.id, ""
    )
    db.flush()
    entry = db.get(JournalEntry, out["entry_id"])
    source_line = next(l for l in entry.lines if l.account_id == src.id)

    assert Decimal(source_line.debit) == Decimal(7_000_000), "مبدأِ بستانکار باید بدهکار شود"
    assert _balance(db, src, alpha.id) == 0
    assert _balance(db, dest, alpha.id) == Decimal(-7_000_000)


def test_the_entry_is_balanced_and_nets_to_zero(db, user):
    """**§۱۰.** اصلاحِ طبقه‌بندی از هیچ، دارایی یا سود نمی‌سازد."""
    _set_mode(db, "hybrid")
    src, dest = _pair(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    _post(db, user, src, alpha, 18_000_000)

    preview = ops.reclass_preview(
        db, LATER, [{"account_id": src.id, "analytic_id": alpha.id}], dest.id, alpha.id
    )
    assert preview["difference"] == 0

    out = ops.issue_reclass(
        db, user, LATER, [{"account_id": src.id, "analytic_id": alpha.id}], dest.id, alpha.id, ""
    )
    db.flush()
    entry = db.get(JournalEntry, out["entry_id"])
    assert sum((Decimal(l.debit) for l in entry.lines), Decimal(0)) == sum(
        (Decimal(l.credit) for l in entry.lines), Decimal(0)
    )


# ── گاردها ──────────────────────────────────────────────────────────────────


def test_a_group_destination_is_rejected(db, user):
    _set_mode(db, "hybrid")
    src, _ = _pair(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    _post(db, user, src, alpha, 1_000_000)
    group = db.query(Account).filter(Account.is_group.is_(True)).first()

    with pytest.raises(HTTPException):
        ops.reclass_preview(
            db, LATER, [{"account_id": src.id, "analytic_id": alpha.id}], group.id, None
        )


def test_the_same_source_and_destination_is_rejected(db, user):
    """سندی که هیچ اثری ندارد نباید ثبت شود."""
    _set_mode(db, "hybrid")
    src, _ = _pair(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    _post(db, user, src, alpha, 1_000_000)

    with pytest.raises(HTTPException):
        ops.reclass_preview(
            db, LATER, [{"account_id": src.id, "analytic_id": alpha.id}], src.id, alpha.id
        )


def test_a_source_without_a_balance_is_rejected(db, user):
    _set_mode(db, "hybrid")
    src, dest = _pair(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")

    with pytest.raises(HTTPException):
        ops.reclass_preview(
            db, LATER, [{"account_id": src.id, "analytic_id": alpha.id}], dest.id, alpha.id
        )


def test_no_sources_is_rejected(db, user):
    _, dest = _pair(db)
    with pytest.raises(HTTPException):
        ops.reclass_preview(db, LATER, [], dest.id, None)


# ── هشدار، نه مسدودی ────────────────────────────────────────────────────────


def test_a_system_role_account_warns_but_passes(db, user):
    """**§۲۴ و §۱۵.** بردنِ مانده مشروع است؛ آنچه کاربر باید بداند این است که
    ثبت‌های خودکارِ آینده همچنان به همان حساب می‌آیند."""
    _set_mode(db, "hybrid")
    src, dest = _pair(db)
    assert src.system_role, "حسابِ بانک باید نقشِ سیستمی داشته باشد"
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    _post(db, user, src, alpha, 5_000_000)

    preview = ops.reclass_preview(
        db, LATER, [{"account_id": src.id, "analytic_id": alpha.id}], dest.id, alpha.id
    )
    assert preview["warnings"], "باید هشدار بدهد"

    ops.issue_reclass(  # ولی نباید جلویش را بگیرد
        db, user, LATER, [{"account_id": src.id, "analytic_id": alpha.id}], dest.id, alpha.id, ""
    )


# ── تفصیلیِ مقصد: این‌جا گارد درست است ──────────────────────────────────────


def test_strict_mode_requires_a_destination_analytic(db, user):
    """برخلافِ تسعیر و اختتامیه، این‌جا کاربر خودش مقصد را انتخاب می‌کند —
    پس گاردِ تفصیلی گارد است، نه تله."""
    _set_mode(db, "hybrid")
    src, dest = _pair(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    _post(db, user, src, alpha, 3_000_000)
    _set_mode(db, "strict")

    with pytest.raises(HTTPException):
        ops.issue_reclass(
            db, user, LATER, [{"account_id": src.id, "analytic_id": alpha.id}], dest.id, None, ""
        )


# ── چند مبدأ ────────────────────────────────────────────────────────────────


def test_several_sources_keep_their_own_line_pair(db, user):
    """**§۲۷.** از روی خودِ سند باید معلوم باشد کدام مبلغ از کجا آمد."""
    _set_mode(db, "hybrid")
    src, dest = _pair(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    beta = _analytic(db, user, "B1", "شرکت بتا")
    _post(db, user, src, alpha, 4_000_000)
    _post(db, user, src, beta, 6_000_000)

    out = ops.issue_reclass(
        db, user, LATER,
        [
            {"account_id": src.id, "analytic_id": alpha.id},
            {"account_id": src.id, "analytic_id": beta.id},
        ],
        dest.id, None, "",
    )
    db.flush()
    assert out["line_count"] == 4  # دو جفت
    assert _balance(db, dest, None) == Decimal(10_000_000)
