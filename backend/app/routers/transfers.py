from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import require_permission
from app.models.transfers import StockTransfer
from app.models.user import User
from app.schemas.transfers import StockTransferIn, StockTransferOut
from app.services.transfers import post_stock_transfer

router = APIRouter(tags=["transfers"])


@router.get("/api/stock-transfers", response_model=list[StockTransferOut])
def list_stock_transfers(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "view"))):
    return (
        db.query(StockTransfer)
        .options(selectinload(StockTransfer.lines))
        .order_by(StockTransfer.transfer_date.desc(), StockTransfer.number.desc())
        .all()
    )


@router.post("/api/stock-transfers", response_model=StockTransferOut, status_code=201)
def create_stock_transfer(
    data: StockTransferIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    return post_stock_transfer(db, data, user)
