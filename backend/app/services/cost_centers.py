from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import JournalLine
from app.models.cost_center import CostCenter
from app.models.invoices import PurchaseInvoice, SalesInvoice
from app.models.user import User
from app.schemas.cost_center import CostCenterIn


def list_cost_centers(db: Session, *, include_inactive: bool = True) -> list[CostCenter]:
    query = db.query(CostCenter)
    if not include_inactive:
        query = query.filter(CostCenter.is_active.is_(True))
    return query.order_by(CostCenter.is_active.desc(), CostCenter.code, CostCenter.name).all()


def get_cost_center(db: Session, cost_center_id: UUID) -> CostCenter:
    center = db.get(CostCenter, cost_center_id)
    if center is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مرکز هزینه پیدا نشد")
    return center


def resolve_cost_center_id(db: Session, cost_center_id: UUID | None) -> UUID | None:
    """اعتبارِ برچسبِ مرکز را می‌سنجد؛ برای برچسب‌زدنِ فاکتور/سند استفاده می‌شود.

    None (بدون برچسب) مجاز است. اگر شناسه‌ای داده شد ولی به مرکزی نرسید، خطای ۴۰۰
    برمی‌گرداند تا سند با ارجاعِ نامعتبر (که RLS هم آن را نمی‌بیند) ثبت نشود.
    """
    if cost_center_id is None:
        return None
    if db.get(CostCenter, cost_center_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مرکز هزینه‌ی انتخاب‌شده معتبر نیست")
    return cost_center_id


def create_cost_center(db: Session, data: CostCenterIn, user: User) -> CostCenter:
    center = CostCenter(
        code=data.code.strip(),
        name=data.name.strip(),
        is_active=data.is_active,
        notes=data.notes,
        created_by_id=user.id,
    )
    db.add(center)
    db.commit()
    db.refresh(center)
    return center


def update_cost_center(db: Session, cost_center_id: UUID, data: CostCenterIn) -> CostCenter:
    center = get_cost_center(db, cost_center_id)
    center.code = data.code.strip()
    center.name = data.name.strip()
    center.is_active = data.is_active
    center.notes = data.notes
    db.commit()
    db.refresh(center)
    return center


def delete_cost_center(db: Session, cost_center_id: UUID) -> None:
    center = get_cost_center(db, cost_center_id)
    # اگر سندی (ردیفِ سند یا فاکتور) به این مرکز برچسب خورده، حذف تاریخ را می‌شکند؛
    # به‌جایش باید «غیرفعال» شود تا از فرم‌ها حذف ولی در گزارش‌ها بماند.
    referenced = (
        db.query(JournalLine.id).filter(JournalLine.cost_center_id == cost_center_id).first()
        or db.query(SalesInvoice.id).filter(SalesInvoice.cost_center_id == cost_center_id).first()
        or db.query(PurchaseInvoice.id).filter(PurchaseInvoice.cost_center_id == cost_center_id).first()
    )
    if referenced is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "این مرکز در اسناد استفاده شده و حذف نمی‌شود؛ به‌جایش آن را «غیرفعال» کنید.",
        )
    db.delete(center)
    db.commit()
