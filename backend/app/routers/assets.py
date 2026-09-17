from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.assets import (
    AssetAssignmentIn,
    AssetAssignmentOut,
    AssetDisposalIn,
    AssetDisposalOut,
    DepreciationEntryOut,
    DepreciationRunIn,
    DepreciationRunOut,
    FixedAssetIn,
    FixedAssetOut,
)
from app.services import assets as assets_service

router = APIRouter(tags=["assets"])


@router.get("/api/fixed-assets", response_model=list[FixedAssetOut])
def list_assets(
    include_disposed: bool = Query(True),
    db: Session = Depends(get_db),
    _=Depends(require_permission("assets", "view")),
):
    return assets_service.list_assets(db, include_disposed=include_disposed)


@router.post("/api/fixed-assets", response_model=FixedAssetOut, status_code=201)
def create_asset(
    data: FixedAssetIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("assets", "create")),
):
    return assets_service.create_asset(db, data, user)


@router.put("/api/fixed-assets/{asset_id}", response_model=FixedAssetOut)
def update_asset(
    asset_id: UUID,
    data: FixedAssetIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("assets", "update")),
):
    return assets_service.update_asset(db, asset_id, data)


@router.post("/api/fixed-assets/{asset_id}/dispose", response_model=FixedAssetOut)
def dispose_asset(
    asset_id: UUID,
    data: AssetDisposalIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("assets", "approve")),
):
    """خروجِ دارایی (فروش/اسقاط/اهدا) — مجوزِ «approve» چون سندِ مالی می‌سازد."""
    return assets_service.dispose_asset(db, asset_id, data, user)


@router.get("/api/asset-disposals", response_model=list[AssetDisposalOut])
def list_disposals(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    disposal_type: str | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("assets", "view")),
):
    """گزارشِ خروج و فروشِ دارایی — ارزشِ دفتری، مبلغِ دریافتی و سود/زیانِ هر واگذاری."""
    return assets_service.list_disposals(
        db, date_from=date_from, date_to=date_to, disposal_type=disposal_type
    )


@router.delete("/api/fixed-assets/{asset_id}", status_code=204)
def delete_asset(
    asset_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("assets", "delete")),
):
    assets_service.delete_asset(db, asset_id)


@router.post("/api/depreciation/run", response_model=DepreciationRunOut)
def run_depreciation(
    data: DepreciationRunIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("assets", "approve")),
):
    """استهلاکِ دوره را ثبت می‌کند — مجوز «approve» چون سندِ مالی می‌سازد."""
    return assets_service.run_depreciation(db, data.period_date, user)


@router.get("/api/depreciation", response_model=list[DepreciationEntryOut])
def list_depreciation(
    db: Session = Depends(get_db),
    _=Depends(require_permission("assets", "view")),
):
    return assets_service.list_depreciation_entries(db)


# ── تحویل/استقرار و جابه‌جایی ───────────────────────────
@router.post("/api/fixed-assets/{asset_id}/placement", response_model=FixedAssetOut, status_code=201)
def place_asset(
    asset_id: UUID,
    data: AssetAssignmentIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("assets", "update")),
):
    """تحویل/استقرارِ دارایی — تخصیص به شخص، محل یا مرکزِ هزینه."""
    return assets_service.place_asset(db, asset_id, data, user)


@router.post("/api/fixed-assets/{asset_id}/transfer", response_model=FixedAssetOut, status_code=201)
def transfer_asset(
    asset_id: UUID,
    data: AssetAssignmentIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("assets", "update")),
):
    """جابه‌جاییِ دارایی بینِ جمعداران، محل‌ها یا مراکزِ هزینه."""
    return assets_service.transfer_asset(db, asset_id, data, user)


@router.get("/api/asset-assignments", response_model=list[AssetAssignmentOut])
def list_assignments(
    asset_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("assets", "view")),
):
    """فهرستِ جابه‌جایی‌ها و تحویل‌ها — تاریخچه‌ی محلِ استقرار و تحویل‌گیرندگان."""
    return assets_service.list_assignments(db, asset_id=asset_id)
