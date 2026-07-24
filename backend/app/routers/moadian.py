from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.moadian import MoadianSettingsIn, MoadianSettingsOut, MoadianSubmissionOut
from app.services import moadian as service

router = APIRouter(prefix="/api/moadian", tags=["moadian"])


def _settings_out(settings) -> dict:
    return {
        "memory_id": settings.memory_id,
        "economic_code": settings.economic_code,
        "national_id": settings.national_id,
        "has_private_key": bool((settings.private_key_pem or "").strip()),
        "is_sandbox": settings.is_sandbox,
        "is_active": settings.is_active,
        "base_url_override": settings.base_url_override,
        "last_serial": settings.last_serial,
        "effective_base_url": service.base_url_for(settings),
    }


@router.get("/settings", response_model=MoadianSettingsOut)
def get_settings(
    db: Session = Depends(get_db),
    _=Depends(require_permission("moadian", "view")),
):
    return _settings_out(service.get_settings(db))


@router.put("/settings", response_model=MoadianSettingsOut)
def update_settings(
    data: MoadianSettingsIn,
    db: Session = Depends(get_db),
    # نوشتنِ اعتبارنامه مجوزِ جداگانه دارد: هرکسی که می‌تواند صورتحساب بفرستد
    # لزوماً نباید بتواند کلیدِ امضا را عوض کند.
    _=Depends(require_permission("moadian", "update")),
):
    settings = service.get_settings(db)
    settings.memory_id = data.memory_id.strip().upper()
    settings.economic_code = data.economic_code.strip()
    settings.national_id = data.national_id.strip()
    settings.is_sandbox = data.is_sandbox
    settings.is_active = data.is_active
    settings.base_url_override = data.base_url_override.strip()
    # None یا رشته‌ی خالی یعنی «دست نزن» — تا ذخیره‌ی فرم، کلید را پاک نکند.
    if data.private_key_pem and data.private_key_pem.strip():
        settings.private_key_pem = data.private_key_pem.strip()
    db.commit()
    db.refresh(settings)
    return _settings_out(settings)


@router.get("/submissions", response_model=list[MoadianSubmissionOut])
def list_submissions(
    db: Session = Depends(get_db),
    _=Depends(require_permission("moadian", "view")),
):
    return service.list_submissions(db)


@router.post("/submit/{invoice_id}", response_model=MoadianSubmissionOut)
def submit_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    # ارسال یک اقدامِ قانونی است، پس مجوزِ approve می‌خواهد.
    user: User = Depends(require_permission("moadian", "approve")),
):
    return service.submit_invoice(db, invoice_id, user)
