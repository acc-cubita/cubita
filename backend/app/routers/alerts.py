from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.schemas.alerts import AlertsOut
from app.services.alerts import get_alerts

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=AlertsOut)
def list_alerts(
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return get_alerts(db)
