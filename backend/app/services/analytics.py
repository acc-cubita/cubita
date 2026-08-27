"""تفصیلیِ سایر — CRUDِ بُعدِ تحلیلیِ آزادِ ردیفِ سند.

کوچک و بی‌ادعا به‌عمد. تنها منطقِ واقعی‌اش این است که یک تفصیلیِ *استفاده‌شده* پاک
نمی‌شود: FK با `SET NULL` جلوی خطای پایگاه‌داده را می‌گیرد، ولی نتیجه‌اش ردیف‌های
سندی است که بی‌صدا بُعدشان را از دست داده‌اند و هیچ گزارشی دیگر پیدایشان نمی‌کند.
پس حذف فقط وقتی مجاز است که هیچ ردیفی به آن اشاره نکند؛ بقیه‌ی موارد «غیرفعال» است.
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import JournalLine
from app.models.analytic import AnalyticAccount
from app.models.user import User
from app.schemas.accounting_ops import AnalyticIn, AnalyticUpdateIn


def _usage(db: Session) -> dict[UUID, int]:
    rows = (
        db.query(JournalLine.analytic_id, func.count(JournalLine.id))
        .filter(JournalLine.analytic_id.isnot(None))
        .group_by(JournalLine.analytic_id)
        .all()
    )
    return {aid: int(n) for aid, n in rows}


def list_analytics(db: Session, *, include_inactive: bool = True) -> list[dict]:
    query = db.query(AnalyticAccount)
    if not include_inactive:
        query = query.filter(AnalyticAccount.is_active.is_(True))
    usage = _usage(db)
    return [
        {
            "id": a.id,
            "code": a.code,
            "name": a.name,
            "group_name": a.group_name,
            "description": a.description,
            "is_active": a.is_active,
            "line_count": usage.get(a.id, 0),
        }
        for a in query.order_by(AnalyticAccount.code).all()
    ]


def _assert_code_free(db: Session, code: str, exclude_id: UUID | None = None) -> None:
    query = db.query(AnalyticAccount).filter(AnalyticAccount.code == code)
    if exclude_id is not None:
        query = query.filter(AnalyticAccount.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کدِ «{code}» قبلاً استفاده شده است")


def create_analytic(db: Session, data: AnalyticIn, user: User) -> dict:
    _assert_code_free(db, data.code)
    row = AnalyticAccount(
        code=data.code,
        name=data.name,
        group_name=data.group_name,
        description=data.description,
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    return {
        "id": row.id, "code": row.code, "name": row.name, "group_name": row.group_name,
        "description": row.description, "is_active": row.is_active, "line_count": 0,
    }


def update_analytic(db: Session, analytic_id: UUID, data: AnalyticUpdateIn) -> dict:
    row = db.get(AnalyticAccount, analytic_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تفصیلی یافت نشد")
    if data.code is not None and data.code != row.code:
        _assert_code_free(db, data.code, exclude_id=row.id)
        row.code = data.code
    for field in ("name", "group_name", "description", "is_active"):
        value = getattr(data, field)
        if value is not None:
            setattr(row, field, value)
    db.flush()
    return {
        "id": row.id, "code": row.code, "name": row.name, "group_name": row.group_name,
        "description": row.description, "is_active": row.is_active,
        "line_count": _usage(db).get(row.id, 0),
    }


def delete_analytic(db: Session, analytic_id: UUID) -> None:
    row = db.get(AnalyticAccount, analytic_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تفصیلی یافت نشد")
    used = _usage(db).get(row.id, 0)
    if used:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"این تفصیلی روی {used} ردیفِ سند نشسته؛ به‌جای حذف، غیرفعالش کنید",
        )
    db.delete(row)
    db.flush()


def resolve_analytic_id(db: Session, analytic_id: UUID | None) -> UUID | None:
    """اعتبارسنجیِ تفصیلیِ ارسالی هنگامِ ثبتِ سند (مثلِ `resolve_cost_center_id`)."""
    if analytic_id is None:
        return None
    row = db.get(AnalyticAccount, analytic_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تفصیلیِ انتخابی یافت نشد")
    if not row.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"تفصیلیِ «{row.name}» غیرفعال است")
    return row.id
