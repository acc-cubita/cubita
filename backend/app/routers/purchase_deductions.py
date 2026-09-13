"""انواعِ کسورِ خرید خدمات — داده‌ی پایه‌ی مالیات تکلیفی و بیمه.

مجوزها روی ماژولِ `invoices` می‌نشینند، همان‌جا که خودِ فاکتور خرید است: کسی که
فاکتور می‌زند باید بتواند ببیند چه کسری در دسترس است.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.schemas.purchase_deductions import PurchaseDeductionTypeIn, PurchaseDeductionTypeOut
from app.services import purchase_deductions as svc

router = APIRouter(prefix="/api/purchase-deduction-types", tags=["purchase-deductions"])


@router.get("", response_model=list[PurchaseDeductionTypeOut])
def list_deduction_types(
    include_inactive: bool = Query(True),
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    return svc.list_types(db, include_inactive=include_inactive)


@router.post("", response_model=PurchaseDeductionTypeOut, status_code=201)
def create_deduction_type(
    data: PurchaseDeductionTypeIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "create")),
):
    return svc.create_type(db, data)


@router.patch("/{type_id}", response_model=PurchaseDeductionTypeOut)
def update_deduction_type(
    type_id: UUID,
    data: PurchaseDeductionTypeIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "update")),
):
    return svc.update_type(db, type_id, data)


@router.delete("/{type_id}", status_code=204)
def delete_deduction_type(
    type_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "delete")),
):
    svc.delete_type(db, type_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
