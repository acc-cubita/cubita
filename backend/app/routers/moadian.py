from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_feature, require_permission
from app.models.user import User
from app.schemas.moadian import (
    MoadianBatchIn,
    MoadianBatchResultOut,
    MoadianConnectionTestOut,
    MoadianPendingInvoiceOut,
    MoadianReadinessOut,
    MoadianSettingsIn,
    MoadianSettingsOut,
    MoadianSubmissionOut,
)
from app.services import moadian as service

# کلِ ماژول قابلیتِ فقط-پلن است: حسابِ آزمایشی هنگامِ بازکردنِ آن ۴۰۲ می‌گیرد و فرانت
# باکسِ «خرید پلن» را نشان می‌دهد. dependencyِ سطحِ روتر هر اندپوینتِ آینده را هم می‌پوشاند.
router = APIRouter(prefix="/api/moadian", tags=["moadian"], dependencies=[Depends(require_feature("moadian"))])


def _settings_out(settings) -> dict:
    return {
        "memory_id": settings.memory_id,
        "economic_code": settings.economic_code,
        "national_id": settings.national_id,
        "has_private_key": bool((settings.private_key_pem or "").strip()),
        "has_certificate": bool((settings.certificate_pem or "").strip()),
        "default_stuff_id": settings.default_stuff_id or "",
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
    settings.default_stuff_id = data.default_stuff_id.strip()
    settings.is_sandbox = data.is_sandbox
    settings.is_active = data.is_active
    settings.base_url_override = data.base_url_override.strip()
    # None یا رشته‌ی خالی یعنی «دست نزن» — تا ذخیره‌ی فرم، کلید/گواهی را پاک نکند.
    if data.private_key_pem and data.private_key_pem.strip():
        settings.private_key_pem = data.private_key_pem.strip()
    if data.certificate_pem and data.certificate_pem.strip():
        settings.certificate_pem = data.certificate_pem.strip()
    db.commit()
    db.refresh(settings)
    return _settings_out(settings)


@router.post("/test-connection", response_model=MoadianConnectionTestOut)
def test_connection(
    db: Session = Depends(get_db),
    # فقط احراز هویت را می‌سنجد و چیزی نمی‌فرستد؛ همان مجوزِ مشاهده کافی است.
    _=Depends(require_permission("moadian", "view")),
):
    return service.test_connection(db)


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


@router.post("/inquiry/{submission_id}", response_model=MoadianSubmissionOut)
def inquire_status(
    submission_id: UUID,
    db: Session = Depends(get_db),
    # استعلام فقط وضعیت را می‌خواند؛ همان مجوزِ مشاهده کافی است.
    _=Depends(require_permission("moadian", "view")),
):
    return service.inquire_status(db, submission_id)


@router.get("/readiness", response_model=MoadianReadinessOut)
def readiness(
    db: Session = Depends(get_db),
    _=Depends(require_permission("moadian", "view")),
):
    return service.readiness(db)


@router.get("/pending", response_model=list[MoadianPendingInvoiceOut])
def pending(
    db: Session = Depends(get_db),
    _=Depends(require_permission("moadian", "view")),
):
    return service.pending_invoices(db)


@router.post("/submit-batch", response_model=list[MoadianBatchResultOut])
def submit_batch(
    data: MoadianBatchIn,
    db: Session = Depends(get_db),
    # همان مجوزِ ارسالِ تکی؛ گروهی‌بودن قدرتِ تازه‌ای نمی‌دهد، فقط تکرار را کم می‌کند.
    user: User = Depends(require_permission("moadian", "approve")),
):
    return service.submit_many(db, data.invoice_ids, user)
