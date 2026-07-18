from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class GeneralLedgerLineOut(BaseModel):
    entry_id: UUID
    entry_number: int | None
    entry_date: date
    description: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


class GeneralLedgerOut(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    opening_balance: Decimal
    lines: list[GeneralLedgerLineOut]
    closing_balance: Decimal


class TrialBalanceRowOut(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    account_type: str
    total_debit: Decimal
    total_credit: Decimal
    balance: Decimal


class AccountBalanceOut(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    balance: Decimal


class BalanceSheetOut(BaseModel):
    as_of: date
    assets: list[AccountBalanceOut]
    liabilities: list[AccountBalanceOut]
    equity: list[AccountBalanceOut]
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    current_period_profit: Decimal


class IncomeStatementOut(BaseModel):
    date_from: date | None
    date_to: date | None
    income: list[AccountBalanceOut]
    expenses: list[AccountBalanceOut]
    total_income: Decimal
    total_expenses: Decimal
    net_profit: Decimal
