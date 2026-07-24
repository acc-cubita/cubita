from decimal import ROUND_HALF_UP, Decimal
from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import JournalLine
from app.models.assets import DepreciationEntry, FixedAsset
from app.models.user import User
from app.schemas.assets import FixedAssetIn
from app.services import chart_codes as cc
from app.services.common import get_or_create_account, make_journal_entry


def _accumulated_depreciation_account(db: Session):
    return get_or_create_account(
        db,
        cc.ACCUMULATED_DEPRECIATION,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.ACCUMULATED_DEPRECIATION],
        name="استهلاک انباشته",
        acc_type="asset",  # کاهنده‌ی دارایی؛ ماندهٔ بستانکار دارد و جمع دارایی‌ها را کم می‌کند
        parent_code="11",
    )


def _depreciation_expense_account(db: Session):
    return get_or_create_account(
        db,
        cc.DEPRECIATION_EXPENSE,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.DEPRECIATION_EXPENSE],
        name="هزینه استهلاک",
        acc_type="expense",
        parent_code="5",
    )


def _depreciable_base(asset: FixedAsset) -> Decimal:
    return Decimal(asset.cost) - Decimal(asset.salvage_value)


def monthly_depreciation(asset: FixedAsset) -> Decimal:
    """استهلاک ماهانه‌ی خط مستقیم، گردشده به عددِ صحیح (ROUND_HALF_UP)."""
    if asset.useful_life_months <= 0:
        return Decimal(0)
    return (_depreciable_base(asset) / Decimal(asset.useful_life_months)).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def to_out(asset: FixedAsset) -> dict:
    base = _depreciable_base(asset)
    accumulated = Decimal(asset.accumulated_depreciation)
    return {
        "id": asset.id,
        "name": asset.name,
        "category": asset.category,
        "acquired_date": asset.acquired_date,
        "cost": Decimal(asset.cost),
        "salvage_value": Decimal(asset.salvage_value),
        "useful_life_months": asset.useful_life_months,
        "method": asset.method,
        "accumulated_depreciation": accumulated,
        "is_disposed": asset.is_disposed,
        "disposed_date": asset.disposed_date,
        "notes": asset.notes,
        "book_value": Decimal(asset.cost) - accumulated,
        "monthly_depreciation": monthly_depreciation(asset),
        "fully_depreciated": accumulated >= base,
    }


def list_assets(db: Session, *, include_disposed: bool = True) -> list[dict]:
    q = db.query(FixedAsset)
    if not include_disposed:
        q = q.filter(FixedAsset.is_disposed.is_(False))
    assets = q.order_by(FixedAsset.acquired_date.desc(), FixedAsset.created_at.desc()).all()
    return [to_out(a) for a in assets]


def get_asset(db: Session, asset_id: UUID) -> FixedAsset:
    asset = db.get(FixedAsset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دارایی پیدا نشد")
    return asset


def create_asset(db: Session, data: FixedAssetIn, user: User) -> dict:
    asset = FixedAsset(
        name=data.name.strip(),
        category=data.category.strip(),
        acquired_date=data.acquired_date,
        cost=data.cost,
        salvage_value=data.salvage_value,
        useful_life_months=data.useful_life_months,
        notes=data.notes,
        created_by_id=user.id,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return to_out(asset)


def update_asset(db: Session, asset_id: UUID, data: FixedAssetIn) -> dict:
    asset = get_asset(db, asset_id)
    # مبنای مالیِ گذشته دست‌نخورده می‌ماند: اگر قبلاً استهلاک خورده، تغییرِ بهای
    # تمام‌شده نباید از استهلاکِ ثبت‌شده کمتر شود، وگرنه ارزش دفتری بی‌معنا می‌شود.
    if Decimal(data.cost) - Decimal(data.salvage_value) < Decimal(asset.accumulated_depreciation):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "مبنای استهلاکِ جدید از استهلاکِ انباشته‌ی ثبت‌شده کمتر است؛ اول اسناد استهلاک را بررسی کنید.",
        )
    asset.name = data.name.strip()
    asset.category = data.category.strip()
    asset.acquired_date = data.acquired_date
    asset.cost = data.cost
    asset.salvage_value = data.salvage_value
    asset.useful_life_months = data.useful_life_months
    asset.notes = data.notes
    db.commit()
    db.refresh(asset)
    return to_out(asset)


def dispose_asset(db: Session, asset_id: UUID, disposed_date: date) -> dict:
    asset = get_asset(db, asset_id)
    asset.is_disposed = True
    asset.disposed_date = disposed_date
    db.commit()
    db.refresh(asset)
    return to_out(asset)


def delete_asset(db: Session, asset_id: UUID) -> None:
    asset = get_asset(db, asset_id)
    if asset.depreciation_entries:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "این دارایی سندِ استهلاک دارد و حذف نمی‌شود؛ به‌جایش آن را «واگذارشده» علامت بزنید.",
        )
    db.delete(asset)
    db.commit()


def run_depreciation(db: Session, period_date: date, user: User) -> dict:
    """استهلاکِ همه‌ی دارایی‌های واجدِ شرایط را برای این دوره ثبت می‌کند.

    قاعده‌ها: دارایی واگذارشده مستهلک نمی‌شود؛ داراییِ کاملاً مستهلک‌شده نه؛ دارایی‌ای
    که هنوز خریداری نشده (acquired_date بعد از دوره) نه؛ و دوره‌ای که قبلاً برای یک
    دارایی ثبت شده دوباره ثبت نمی‌شود (قیدِ یکتا). همه‌ی استهلاکِ دوره در یک سند
    واحد جمع می‌شود: بدهکارِ «هزینه استهلاک»، بستانکارِ «استهلاک انباشته».
    """
    assets = (
        db.query(FixedAsset)
        .filter(FixedAsset.is_disposed.is_(False), FixedAsset.acquired_date <= period_date)
        .all()
    )
    already = {
        e.asset_id
        for e in db.query(DepreciationEntry.asset_id).filter(DepreciationEntry.period_date == period_date).all()
    }

    pending: list[tuple[FixedAsset, Decimal]] = []
    for asset in assets:
        if asset.id in already:
            continue
        base = _depreciable_base(asset)
        accumulated = Decimal(asset.accumulated_depreciation)
        remaining = base - accumulated
        if remaining <= 0:
            continue
        amount = min(monthly_depreciation(asset), remaining)  # دوره‌ی آخر ممکن است کمتر باشد
        if amount <= 0:
            continue
        pending.append((asset, amount))

    if not pending:
        return {
            "period_date": period_date,
            "asset_count": 0,
            "total_amount": Decimal(0),
            "journal_entry_id": None,
            "journal_entry_number": None,
        }

    total = sum((amt for _, amt in pending), Decimal(0))
    entry = make_journal_entry(
        db,
        period_date,
        f"استهلاک دوره ({len(pending)} دارایی)",
        "depreciation",
        user,
        [
            JournalLine(account_id=_depreciation_expense_account(db).id, debit=total, credit=0, description="هزینه استهلاک دوره"),
            JournalLine(account_id=_accumulated_depreciation_account(db).id, debit=0, credit=total, description="استهلاک انباشته دوره"),
        ],
    )

    for asset, amount in pending:
        asset.accumulated_depreciation = Decimal(asset.accumulated_depreciation) + amount
        db.add(
            DepreciationEntry(
                asset_id=asset.id,
                period_date=period_date,
                amount=amount,
                journal_entry_id=entry.id,
                created_by_id=user.id,
            )
        )
    db.commit()
    return {
        "period_date": period_date,
        "asset_count": len(pending),
        "total_amount": total,
        "journal_entry_id": entry.id,
        "journal_entry_number": entry.number,
    }


def list_depreciation_entries(db: Session) -> list[dict]:
    rows = (
        db.query(DepreciationEntry)
        .order_by(DepreciationEntry.period_date.desc(), DepreciationEntry.created_at.desc())
        .all()
    )
    return [
        {
            "id": e.id,
            "asset_id": e.asset_id,
            "asset_name": e.asset.name,
            "period_date": e.period_date,
            "amount": Decimal(e.amount),
            "journal_entry_id": e.journal_entry_id,
        }
        for e in rows
    ]
