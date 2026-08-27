from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import Account
from app.models.budgeting import BudgetLine
from app.models.cost_center import CostCenter
from app.models.user import User
from app.schemas.budgeting import BudgetLineIn
from app.services.reports import CREDIT_NORMAL_TYPES, _leaf_account_totals, _signed_balance


def _to_out(line: BudgetLine) -> dict:
    return {
        "id": line.id,
        "account_id": line.account_id,
        "account_code": line.account.code,
        "account_name": line.account.name,
        "account_type": line.account.type,
        "period_date": line.period_date,
        "amount": Decimal(line.amount),
        "notes": line.notes,
        "cost_center_id": line.cost_center_id,
        "cost_center_name": line.cost_center.name if line.cost_center else "",
    }


def list_budget_lines(db: Session, *, cost_center_id: UUID | None = None) -> list[dict]:
    """ردیف‌های بودجه. بدونِ `cost_center_id` همه برمی‌گردند (سراسری و مرکزی)."""
    query = db.query(BudgetLine).join(Account, BudgetLine.account_id == Account.id)
    if cost_center_id is not None:
        query = query.filter(BudgetLine.cost_center_id == cost_center_id)
    lines = query.order_by(BudgetLine.period_date.desc(), Account.code).all()
    return [_to_out(line) for line in lines]


def _get_line(db: Session, line_id: UUID) -> BudgetLine:
    line = db.get(BudgetLine, line_id)
    if line is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ردیف بودجه پیدا نشد")
    return line


def _validate_account(db: Session, account_id: UUID) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب پیدا نشد")
    if account.is_group:
        # بودجه روی حسابِ گروه بی‌معناست: عملکردِ واقعی فقط روی حساب‌های قابل‌ثبت
        # (برگ) جمع می‌شود، پس بودجه هم باید روی همان‌ها بنشیند وگرنه مقایسه لنگ است.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "بودجه فقط برای حساب‌های قابل‌ثبت (غیرگروه) تعریف می‌شود")
    return account


def _center_family(db: Session, cost_center_id: UUID | None) -> set[UUID] | None:
    """مرکز و همه‌ی زیرشاخه‌هایش؛ None یعنی «بدونِ فیلترِ مرکز»."""
    if cost_center_id is None:
        return None
    from app.services.cost_centers import _descendants, _index

    _by_id, children = _index(db)
    return _descendants(cost_center_id, children)


def _validate_cost_center(db: Session, cost_center_id: UUID | None) -> None:
    if cost_center_id is not None and db.get(CostCenter, cost_center_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مرکز هزینه‌ی انتخاب‌شده معتبر نیست")


def create_budget_line(db: Session, data: BudgetLineIn, user: User) -> dict:
    """بودجه‌ی یک حساب/ماه را ثبت می‌کند؛ اگر از قبل باشد همان را به‌روزرسانی می‌کند.

    upsert به‌جای خطای «تکراری» است چون کاربر معمولاً «بودجه‌ی این ماه را تنظیم کن»
    را دوباره می‌زند تا رقم را اصلاح کند، نه اینکه ردیفِ دومی بخواهد.
    """
    _validate_account(db, data.account_id)
    _validate_cost_center(db, data.cost_center_id)
    # کلیدِ upsert شاملِ مرکز است: بودجه‌ی «حقوق فروردین» برای دو پروژه دو برنامه‌ی
    # متفاوت است، نه یک ردیفِ تکراری.
    center_match = (
        BudgetLine.cost_center_id.is_(None)
        if data.cost_center_id is None
        else BudgetLine.cost_center_id == data.cost_center_id
    )
    existing = (
        db.query(BudgetLine)
        .filter(
            BudgetLine.account_id == data.account_id,
            BudgetLine.period_date == data.period_date,
            center_match,
        )
        .first()
    )
    if existing is not None:
        existing.amount = data.amount
        existing.notes = data.notes
        db.commit()
        db.refresh(existing)
        return _to_out(existing)

    line = BudgetLine(
        account_id=data.account_id,
        period_date=data.period_date,
        amount=data.amount,
        notes=data.notes,
        cost_center_id=data.cost_center_id,
        created_by_id=user.id,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return _to_out(line)


def update_budget_line(db: Session, line_id: UUID, data: BudgetLineIn) -> dict:
    line = _get_line(db, line_id)
    _validate_account(db, data.account_id)
    _validate_cost_center(db, data.cost_center_id)
    line.account_id = data.account_id
    line.period_date = data.period_date
    line.amount = data.amount
    line.notes = data.notes
    line.cost_center_id = data.cost_center_id
    db.commit()
    db.refresh(line)
    return _to_out(line)


def delete_budget_line(db: Session, line_id: UUID) -> None:
    line = _get_line(db, line_id)
    db.delete(line)
    db.commit()


def get_budget_report(
    db: Session,
    date_from: date | None,
    date_to: date | None,
    cost_center_id: UUID | None = None,
) -> dict:
    """بودجه در برابر عملکرد: برای هر حسابِ بودجه‌دار، رقمِ برنامه و ماندهٔ واقعیِ همان بازه.

    فقط حساب‌هایی که بودجه دارند نمایش داده می‌شوند — گزارش دربارهٔ «برنامه در برابر
    واقعیت» است، نه فهرستِ همه‌ی حساب‌ها. عملکرد از همان منطقِ ماندهٔ علامت‌دارِ
    گزارش‌های دیگر (`_signed_balance`) می‌آید تا با تراز آزمایشی و سود و زیان یکی باشد.
    """
    budget_query = db.query(BudgetLine).join(Account, BudgetLine.account_id == Account.id)
    # با انتخابِ مرکز، *هر دو* طرفِ مقایسه به همان مرکز محدود می‌شوند — بودجه و
    # عملکرد. فیلترکردنِ یک طرف، مقایسه را بی‌معنا می‌کرد.
    if cost_center_id is not None:
        budget_query = budget_query.filter(BudgetLine.cost_center_id == cost_center_id)
    else:
        budget_query = budget_query.filter(BudgetLine.cost_center_id.is_(None))
    if date_from is not None:
        budget_query = budget_query.filter(BudgetLine.period_date >= date_from)
    if date_to is not None:
        budget_query = budget_query.filter(BudgetLine.period_date <= date_to)

    budget_by_account: dict[UUID, Decimal] = {}
    account_by_id: dict[UUID, Account] = {}
    for line in budget_query.all():
        budget_by_account[line.account_id] = budget_by_account.get(line.account_id, Decimal(0)) + Decimal(line.amount)
        account_by_id[line.account_id] = line.account

    center_ids = _center_family(db, cost_center_id)
    actual_by_account: dict[UUID, Decimal] = {
        acc.id: _signed_balance(acc.type, debit, credit)
        for acc, debit, credit in _leaf_account_totals(
            db, date_from, date_to, cost_center_ids=center_ids
        )
    }

    rows = []
    for account_id, budget in budget_by_account.items():
        account = account_by_id[account_id]
        actual = actual_by_account.get(account_id, Decimal(0))
        variance = actual - budget
        variance_pct = (
            (variance / budget * Decimal(100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            if budget != 0
            else None
        )
        favorable = actual >= budget if account.type in CREDIT_NORMAL_TYPES else actual <= budget
        rows.append(
            {
                "account_id": account.id,
                "account_code": account.code,
                "account_name": account.name,
                "account_type": account.type,
                "budget": budget,
                "actual": actual,
                "variance": variance,
                "variance_pct": variance_pct,
                "favorable": favorable,
            }
        )

    rows.sort(key=lambda r: r["account_code"])
    total_budget = sum((r["budget"] for r in rows), Decimal(0))
    total_actual = sum((r["actual"] for r in rows), Decimal(0))
    return {
        "date_from": date_from,
        "date_to": date_to,
        "rows": rows,
        "total_budget": total_budget,
        "total_actual": total_actual,
        "total_variance": total_actual - total_budget,
    }
