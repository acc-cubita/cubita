from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import require_permission
from app.models.transfers import StockTransfer
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.transfers import StockTransferIn, StockTransferOut
from app.services.transfers import post_stock_transfer

router = APIRouter(tags=["transfers"])


@router.get("/api/stock-transfers", response_model=Page[StockTransferOut])
def list_stock_transfers(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("inventory", "view")),
):
    items, next_cursor = paginate(
        db.query(StockTransfer).options(selectinload(StockTransfer.lines)),
        [StockTransfer.transfer_date, StockTransfer.number],
        params,
    )
    return Page(items=items, next_cursor=next_cursor)


@router.post("/api/stock-transfers", response_model=StockTransferOut, status_code=201)
def create_stock_transfer(
    data: StockTransferIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    return post_stock_transfer(db, data, user)
