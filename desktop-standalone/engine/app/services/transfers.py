from sqlalchemy import text
from sqlalchemy.orm import Session

from fastapi import HTTPException, status

from app.models.counters import DOC_STOCK_TRANSFER
from app.services.numbering import next_document_number
from app.models.inventory import Item, StockLedger
from app.models.transfers import StockTransfer, StockTransferLine
from app.models.user import User
from app.schemas.transfers import StockTransferIn
from app.services.inventory import get_stock_qty


def post_stock_transfer(db: Session, data: StockTransferIn, user: User) -> StockTransfer:
    items_by_id = {i.id: i for i in db.query(Item).filter(Item.id.in_([l.item_id for l in data.lines])).all()}

    transfer_lines: list[StockTransferLine] = []
    stock_moves: list[StockLedger] = []

    for line in data.lines:
        item = items_by_id.get(line.item_id)
        if item is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کالا با شناسه {line.item_id} یافت نشد")
        if item.is_service:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"«{item.name}» خدمت است و قابل جابه‌جایی بین انبارها نیست")

        available = get_stock_qty(db, line.item_id, data.from_warehouse_id)
        if available < line.qty:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"موجودی «{item.name}» در انبار مبدأ کافی نیست (موجود: {available}, درخواستی: {line.qty})",
            )

        transfer_lines.append(StockTransferLine(item_id=line.item_id, qty=line.qty))
        stock_moves.append(
            StockLedger(
                item_id=line.item_id,
                warehouse_id=data.from_warehouse_id,
                qty=-line.qty,
                unit_cost=item.average_cost,
                entry_date=data.transfer_date,
                source_type="transfer_out",
            )
        )
        stock_moves.append(
            StockLedger(
                item_id=line.item_id,
                warehouse_id=data.to_warehouse_id,
                qty=line.qty,
                unit_cost=item.average_cost,
                entry_date=data.transfer_date,
                source_type="transfer_in",
            )
        )

    number = next_document_number(db, DOC_STOCK_TRANSFER)
    transfer = StockTransfer(
        number=number,
        transfer_date=data.transfer_date,
        from_warehouse_id=data.from_warehouse_id,
        to_warehouse_id=data.to_warehouse_id,
        description=data.description,
        created_by_id=user.id,
        lines=transfer_lines,
    )
    db.add(transfer)
    db.flush()
    for move in stock_moves:
        move.source_id = transfer.id
        db.add(move)

    db.flush()
    db.refresh(transfer)
    return transfer
