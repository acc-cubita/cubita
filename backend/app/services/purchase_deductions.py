"""کسوراتِ خریدِ خدمت — تعریف، محاسبه، و حسابی که رویش می‌نشیند.

**کسر تخفیف نیست.** تخفیف قیمتِ خدمت را کم می‌کند؛ مالیات تکلیفی و بیمه قیمت را
دست نمی‌زنند و فقط می‌گویند بخشی از بدهی به **چه کسی** است. پس:

* هزینه‌ی خدمت همان مبلغِ کامل می‌ماند؛
* هر کسر یک ردیفِ بستانکارِ مستقل روی حسابِ بدهیِ خودش می‌شود؛
* و بدهیِ تأمین‌کننده فقط مابقی است — همان عددی که تسویه و اعلامیه‌ی پرداخت
  باید ببینند.

هیچ درصدی این‌جا نیست. نرخ از «نوعِ کسر» می‌آید که خودِ کسب‌وکار تعریف کرده، و
مبلغِ نهایی را کاربر می‌تواند روی فاکتور عوض کند.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import Account
from app.models.purchase_deductions import (
    DEDUCTION_BASIS_LABELS,
    DEDUCTION_NATURE_LABELS,
    PurchaseDeductionType,
    PurchaseInvoiceDeduction,
)
from app.schemas.purchase_deductions import PurchaseDeductionTypeIn
from app.services import chart_codes as cc
from app.services.common import assert_postable_account, get_or_create_account

_ROLE_BY_NATURE = {
    "withholding_tax": cc.WITHHOLDING_TAX_PAYABLE,
    "insurance": cc.CONTRACT_INSURANCE_PAYABLE,
}
_DEFAULT_ACCOUNT_NAME = {
    "withholding_tax": "مالیات تکلیفی پرداختنی",
    "insurance": "حق بیمه پرداختنی اشخاص ثالث",
}


def default_account(db: Session, nature: str) -> Account:
    """حسابِ پیش‌فرضِ یک ماهیت — و اگر نبود، ساختنش.

    `get_or_create` است نه `get`: این دو نقش بعد از استقرارِ کسب‌وکارهای موجود
    اضافه شده‌اند و چارتِ هیچ‌کدامشان آن‌ها را ندارد. همان الگوی «هزینه خرید خدمات».
    """
    role = _ROLE_BY_NATURE[nature]
    return get_or_create_account(
        db,
        role,
        code=cc.DEFAULT_CODE_BY_ROLE[role],
        name=_DEFAULT_ACCOUNT_NAME[nature],
        acc_type="liability",
        parent_code="21",
    )


def _default_account_or_none(db: Session, nature: str) -> Account | None:
    """همان، **بدونِ ساختن** — بازکردنِ فهرستِ انواعِ کسر نباید در چارت حساب بسازد."""
    return db.query(Account).filter(Account.system_role == _ROLE_BY_NATURE[nature]).first()


def _assert_account(db: Session, nature: str, account_id: UUID | None) -> None:
    if account_id is None:
        return
    assert_postable_account(db, account_id, allow_role=_ROLE_BY_NATURE[nature], subject="نوعِ کسر")
    account = db.get(Account, account_id)
    if account is not None and account.type != "liability":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"«{account.name}» حسابِ بدهی نیست. کسرِ خریدِ خدمت بدهی به سازمانِ مالیاتی یا "
            "بیمه است و باید روی حسابی با ماهیتِ بدهی بنشیند.",
        )


# ───────────────────────────── تعریفِ نوعِ کسر ─────────────────────────────


def _in_use_ids(db: Session, ids: Iterable[UUID]) -> set[UUID]:
    ids = list(ids)
    if not ids:
        return set()
    rows = (
        db.query(PurchaseInvoiceDeduction.deduction_type_id)
        .filter(PurchaseInvoiceDeduction.deduction_type_id.in_(ids))
        .distinct()
        .all()
    )
    return {type_id for (type_id,) in rows}


def _row(row: PurchaseDeductionType, *, in_use: bool, accounts: dict[UUID, Account], defaults: dict) -> dict:
    account = accounts.get(row.account_id) if row.account_id else defaults.get(row.nature)
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "nature": row.nature,
        "nature_label": DEDUCTION_NATURE_LABELS[row.nature],
        "basis": row.basis,
        "basis_label": DEDUCTION_BASIS_LABELS[row.basis],
        "rate": Decimal(row.rate),
        "account_id": row.account_id,
        "account_code": account.code if account else "",
        "account_name": account.name if account else _DEFAULT_ACCOUNT_NAME[row.nature],
        "account_is_default": row.account_id is None,
        "is_active": row.is_active,
        "description": row.description,
        "in_use": in_use,
    }


def _rows(db: Session, types: list[PurchaseDeductionType]) -> list[dict]:
    in_use = _in_use_ids(db, [t.id for t in types])
    account_ids = {t.account_id for t in types if t.account_id}
    accounts = (
        {a.id: a for a in db.query(Account).filter(Account.id.in_(account_ids)).all()}
        if account_ids
        else {}
    )
    defaults = {nature: _default_account_or_none(db, nature) for nature in _ROLE_BY_NATURE}
    return [_row(t, in_use=t.id in in_use, accounts=accounts, defaults=defaults) for t in types]


def _get(db: Session, type_id: UUID) -> PurchaseDeductionType:
    row = db.get(PurchaseDeductionType, type_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "نوعِ کسر یافت نشد")
    return row


def _assert_name_free(db: Session, name: str, *, skip_id: UUID | None = None) -> None:
    query = db.query(PurchaseDeductionType.id).filter(PurchaseDeductionType.name == name)
    if skip_id is not None:
        query = query.filter(PurchaseDeductionType.id != skip_id)
    if query.first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"نوعِ کسری با نامِ «{name}» از قبل هست")


def list_types(db: Session, *, include_inactive: bool = True) -> list[dict]:
    query = db.query(PurchaseDeductionType)
    if not include_inactive:
        query = query.filter(PurchaseDeductionType.is_active.is_(True))
    return _rows(db, query.order_by(PurchaseDeductionType.code, PurchaseDeductionType.name).all())


def create_type(db: Session, data: PurchaseDeductionTypeIn) -> dict:
    _assert_name_free(db, data.name)
    _assert_account(db, data.nature, data.account_id)
    row = PurchaseDeductionType(**data.model_dump())
    db.add(row)
    db.flush()
    return _rows(db, [row])[0]


def update_type(db: Session, type_id: UUID, data: PurchaseDeductionTypeIn) -> dict:
    """ویرایش فقط **فاکتورهای بعدی** را عوض می‌کند.

    ردیف‌های کسرِ فاکتورهای ثبت‌شده Snapshotاند؛ عوض‌شدنِ نرخ یا حساب این‌جا سندِ
    دیروز را بازنویسی نمی‌کند. ولی **ماهیتِ** کسری که در فاکتوری خورده عوض نمی‌شود:
    آن‌وقت «جمعِ بیمه»ی فهرستِ فاکتورها از ردیف‌هایی می‌آمد که نامشان مالیات است.
    """
    row = _get(db, type_id)
    _assert_name_free(db, data.name, skip_id=type_id)
    if data.nature != row.nature and _in_use_ids(db, [type_id]):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"«{row.name}» در فاکتور خورده و ماهیتش عوض نمی‌شود؛ برای ماهیتِ دیگر نوعِ تازه‌ای بسازید.",
        )
    _assert_account(db, data.nature, data.account_id)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.flush()
    return _rows(db, [row])[0]


def delete_type(db: Session, type_id: UUID) -> None:
    row = _get(db, type_id)
    if _in_use_ids(db, [type_id]):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"«{row.name}» در فاکتور خورده و حذف نمی‌شود — سابقه‌ی فاکتورها به آن ارجاع دارد. "
            "غیرفعالش کنید تا در فاکتورِ تازه نیاید.",
        )
    db.delete(row)
    db.flush()


# ───────────────────────────── محاسبه روی فاکتور ─────────────────────────────


def build_deductions(
    db: Session,
    requested: list,
    *,
    gross: Decimal,
    net_before_tax: Decimal,
    ceiling: Decimal,
) -> list[PurchaseInvoiceDeduction]:
    """ردیف‌های کسرِ یک فاکتور — Snapshotِ نوع، مبنا، نرخ، مبلغ و حساب.

    `ceiling` جمعِ فاکتور (با مالیات) است: کسورات نمی‌توانند از آن بیشتر شوند،
    وگرنه بدهی به تأمین‌کننده منفی می‌شد — یعنی ما طلبکارِ کسی بودیم که فقط
    خدمت داده.
    """
    if not requested:
        return []
    ids = [item.deduction_type_id for item in requested]
    if len(set(ids)) != len(ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "هر نوعِ کسر فقط یک بار در فاکتور می‌آید")
    types = {t.id: t for t in db.query(PurchaseDeductionType).filter(PurchaseDeductionType.id.in_(ids)).all()}

    rows: list[PurchaseInvoiceDeduction] = []
    total = Decimal(0)
    for seq, item in enumerate(requested, start=1):
        kind = types.get(item.deduction_type_id)
        if kind is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوعِ کسرِ انتخاب‌شده یافت نشد")
        if not kind.is_active:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"«{kind.name}» غیرفعال است و در فاکتورِ تازه نمی‌آید.",
            )
        basis_amount = Decimal(gross if kind.basis == "gross" else net_before_tax)
        rate = Decimal(item.rate) if item.rate is not None else Decimal(kind.rate)
        amount = (
            Decimal(item.amount)
            if item.amount is not None
            else (basis_amount * rate / Decimal(100)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        )
        if amount <= 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"مبلغِ «{kind.name}» صفر است؛ نرخ یا مبلغ را وارد کنید، یا این کسر را از فاکتور بردارید.",
            )
        if amount > basis_amount:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"«{kind.name}» ({amount:,}) از مبنای خودش ({basis_amount:,}) بیشتر است.",
            )
        rows.append(
            PurchaseInvoiceDeduction(
                seq=seq,
                deduction_type_id=kind.id,
                nature=kind.nature,
                name_snapshot=kind.name,
                basis=kind.basis,
                basis_amount=basis_amount,
                rate=rate,
                amount=amount,
                #: حساب **همین حالا** حل می‌شود و روی ردیف می‌ماند؛ عوض‌شدنِ حسابِ
                #: نوعِ کسر در آینده این فاکتور را تکان نمی‌دهد.
                account_id=kind.account_id or default_account(db, kind.nature).id,
            )
        )
        total += amount

    if total > ceiling:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"جمعِ کسورات ({total:,}) از جمعِ فاکتور ({ceiling:,}) بیشتر است؛ "
            "بدهی به تأمین‌کننده منفی می‌شد.",
        )
    return rows


def totals_by_nature(deductions: Iterable[PurchaseInvoiceDeduction]) -> dict[str, Decimal]:
    totals = {nature: Decimal(0) for nature in _ROLE_BY_NATURE}
    for row in deductions:
        totals[row.nature] = totals.get(row.nature, Decimal(0)) + Decimal(row.amount)
    return totals
