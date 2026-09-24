"""نگهداریِ سرورِ سازمانی از داخلِ برنامه — فقط مالک، فقط نسخه‌ی سازمانی.

- `GET /api/maintenance/backups`: وضعیتِ پشتیبانِ خودکار (پایه‌ی نوارِ قرمزِ «پشتیبانِ کهنه»).
- `POST /api/maintenance/backups/run`: یک پشتیبانِ همین حالا، مثلاً پیش از کاری پرریسک.
- `GET /api/maintenance/diagnostics`: زیپِ عیب‌یابی برای پشتیبانی، بی هیچ رازی.

منطق در `app/onprem/maintenance.py` است؛ اگر API بالا نیاید، همان کارها از
`cubita-server backup` و `cubita-server diagnostics` روی خودِ سرور در دسترس‌اند.
"""

import time
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal
from app.licensing import state as license_state
from app.licensing.state import license_file
from app.onprem import maintenance as mnt
from app.onprem import updates as upd
from app.onprem.provision import Layout, ProvisionError, current_revision, read_env

router = APIRouter(prefix="/api/maintenance", tags=["enterprise-maintenance"])


def _layout() -> Layout:
    #: همان پوشه‌ی داده‌ی `license.lic` و `.env` (نصاب `LICENSE_DIR` را آنجا می‌گذارد).
    return Layout(license_file().parent)


def _owner_only(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.role.key != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "نگهداریِ سرور فقط کارِ مالکِ کسب‌وکار است.")
    return principal


class BackupStatusOut(BaseModel):
    last_at: str | None
    age_hours: float | None
    count: int
    total_bytes: int
    folder: str
    last_error: str | None
    stale: bool
    #: False یعنی این API روی سرورِ نصب‌شده نیست (توسعه) و پشتیبانِ خودکار ندارد.
    automatic: bool


def _status_out(layout: Layout) -> BackupStatusOut:
    return BackupStatusOut(**asdict(mnt.status(layout)), automatic=mnt.resolve_pg_bin() is not None)


@router.get("/backups", response_model=BackupStatusOut)
def backup_status(_: Principal = Depends(_owner_only)):
    return _status_out(_layout())


@router.post("/backups/run", response_model=BackupStatusOut)
def backup_now(_: Principal = Depends(_owner_only)):
    layout = _layout()
    pg_bin = mnt.resolve_pg_bin()
    url = read_env(layout).get("MIGRATION_DATABASE_URL")
    if pg_bin is None or not url:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "پشتیبانِ سرور فقط روی سرورِ نصب‌شده با نصابِ کوبیتا سازمانی کار می‌کند.",
        )
    try:
        mnt.run_backup(layout, pg_bin, url)
    except mnt.BackupBusy as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ProvisionError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"پشتیبان‌گیری شکست خورد: {exc}") from exc
    return _status_out(layout)


@router.get("/diagnostics")
def diagnostics(principal: Principal = Depends(_owner_only), db: Session = Depends(get_db)):
    from app.models.tenant import Membership

    layout = _layout()
    info = mnt.base_info(layout)
    lic = license_state.current(db)
    info["license"] = {
        "mode": lic.mode,
        "writable": lic.writable,
        "message": lic.message,
        "days_left": lic.days_left,
        "expires_at": lic.expires_at,
        "org": lic.org,
        "seats": lic.seats,
        "license_id": lic.license_id,
    }
    info["members"] = db.scalar(
        select(func.count()).select_from(Membership).where(Membership.tenant_id == principal.tenant_id)
    )
    info["update"] = asdict(upd.status(layout.home))
    url = read_env(layout).get("MIGRATION_DATABASE_URL")
    if url:
        try:
            info["db_revision"] = current_revision(url)
        except Exception as exc:  # noqa: BLE001 — زیپِ عیب‌یابی نباید با خطای خودِ دیتابیس بشکند
            info["db_revision"] = f"خطا: {exc}"
    name = f"cubita-diagnostics-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    return Response(
        mnt.diagnostics_zip(layout, info),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
