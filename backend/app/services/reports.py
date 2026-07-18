from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry, JournalLine

CREDIT_NORMAL_TYPES = ("liability", "equity", "income")


def _signed_balance(account_type: str, total_debit: Decimal, total_credit: Decimal) -> Decimal:
    if account_type in CREDIT_NORMAL_TYPES:
        return total_credit - total_debit
    return total_debit - total_credit


def get_general_ledger(
    db: Session, account_id: UUID, date_from: date | None, date_to: date | None
) -> dict:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب یافت نشد")

    query = db.query(JournalLine, JournalEntry).join(JournalEntry, JournalLine.entry_id == JournalEntry.id).filter(
        JournalLine.account_id == account_id
    )

    opening_balance = Decimal(0)
    if date_from is not None:
        opening_rows = query.filter(JournalEntry.entry_date < date_from).all()
        opening_debit = sum((r[0].debit for r in opening_rows), Decimal(0))
        opening_credit = sum((r[0].credit for r in opening_rows), Decimal(0))
        opening_balance = _signed_balance(account.type, opening_debit, opening_credit)
        query = query.filter(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        query = query.filter(JournalEntry.entry_date <= date_to)

    rows = query.order_by(JournalEntry.entry_date, JournalEntry.number).all()

    running = opening_balance
    lines = []
    for line, entry in rows:
        delta = _signed_balance(account.type, line.debit, line.credit)
        running += delta
        lines.append(
            {
                "entry_id": entry.id,
                "entry_number": entry.number,
                "entry_date": entry.entry_date,
                "description": line.description or entry.description,
                "debit": line.debit,
                "credit": line.credit,
                "balance": running,
            }
        )

    return {
        "account_id": account.id,
        "account_code": account.code,
        "account_name": account.name,
        "opening_balance": opening_balance,
        "lines": lines,
        "closing_balance": running,
    }


def _leaf_account_totals(
    db: Session, date_from: date | None, date_to: date | None, types: tuple[str, ...] | None = None
) -> list[tuple[Account, Decimal, Decimal]]:
    query = (
        db.query(Account, func.coalesce(func.sum(JournalLine.debit), 0), func.coalesce(func.sum(JournalLine.credit), 0))
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .filter(Account.is_group.is_(False))
    )
    if types is not None:
        query = query.filter(Account.type.in_(types))
    if date_from is not None:
        query = query.filter(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        query = query.filter(JournalEntry.entry_date <= date_to)
    query = query.group_by(Account.id)

    return [(acc, Decimal(debit), Decimal(credit)) for acc, debit, credit in query.all()]


def get_trial_balance(db: Session, date_from: date | None, date_to: date | None) -> list[dict]:
    rows = _leaf_account_totals(db, date_from, date_to)
    result = [
        {
            "account_id": acc.id,
            "account_code": acc.code,
            "account_name": acc.name,
            "account_type": acc.type,
            "total_debit": debit,
            "total_credit": credit,
            "balance": _signed_balance(acc.type, debit, credit),
        }
        for acc, debit, credit in rows
    ]
    return sorted(result, key=lambda r: r["account_code"])


def get_income_statement(db: Session, date_from: date | None, date_to: date | None) -> dict:
    rows = _leaf_account_totals(db, date_from, date_to, types=("income", "expense"))
    income = sorted(
        (
            {"account_id": a.id, "account_code": a.code, "account_name": a.name, "balance": _signed_balance(a.type, d, c)}
            for a, d, c in rows
            if a.type == "income"
        ),
        key=lambda r: r["account_code"],
    )
    expenses = sorted(
        (
            {"account_id": a.id, "account_code": a.code, "account_name": a.name, "balance": _signed_balance(a.type, d, c)}
            for a, d, c in rows
            if a.type == "expense"
        ),
        key=lambda r: r["account_code"],
    )
    total_income = sum((r["balance"] for r in income), Decimal(0))
    total_expenses = sum((r["balance"] for r in expenses), Decimal(0))
    return {
        "date_from": date_from,
        "date_to": date_to,
        "income": income,
        "expenses": expenses,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": total_income - total_expenses,
    }


def get_balance_sheet(db: Session, as_of: date) -> dict:
    income_statement = get_income_statement(db, None, as_of)
    current_period_profit = income_statement["net_profit"]

    rows = _leaf_account_totals(db, None, as_of, types=("asset", "liability", "equity"))
    by_type: dict[str, list[dict]] = {"asset": [], "liability": [], "equity": []}
    for acc, debit, credit in rows:
        by_type[acc.type].append(
            {
                "account_id": acc.id,
                "account_code": acc.code,
                "account_name": acc.name,
                "balance": _signed_balance(acc.type, debit, credit),
            }
        )
    for key in by_type:
        by_type[key].sort(key=lambda r: r["account_code"])

    total_assets = sum((r["balance"] for r in by_type["asset"]), Decimal(0))
    total_liabilities = sum((r["balance"] for r in by_type["liability"]), Decimal(0))
    total_equity = sum((r["balance"] for r in by_type["equity"]), Decimal(0))

    return {
        "as_of": as_of,
        "assets": by_type["asset"],
        "liabilities": by_type["liability"],
        "equity": by_type["equity"],
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "current_period_profit": current_period_profit,
    }
