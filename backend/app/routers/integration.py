import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.services.storefront_integration import StorefrontConfigError, sync_all

router = APIRouter(prefix="/api/integration", tags=["integration"])


@router.post("/sync")
def trigger_sync(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    try:
        return sync_all(db, user)
    except StorefrontConfigError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err))
    except httpx.HTTPError as err:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"ارتباط با سایت فروشگاهی برقرار نشد: {err}")
