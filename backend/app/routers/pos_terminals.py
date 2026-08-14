from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.pos_terminal import PosTerminal
from app.schemas.pos_terminal import PosTerminalIn, PosTerminalOut

router = APIRouter(tags=["pos-terminals"])


def _clear_default(db: Session) -> None:
    """پیش‌فرض یکتاست: قبل از ست‌کردنِ پیش‌فرضِ تازه، بقیه را از حالتِ پیش‌فرض درمی‌آورد."""
    for t in db.query(PosTerminal).filter(PosTerminal.is_default.is_(True)).all():
        t.is_default = False


@router.get("/api/pos-terminals", response_model=list[PosTerminalOut])
def list_terminals(
    db: Session = Depends(get_db),
    # نمای فهرست را فروشنده/صندوق‌دار هم لازم دارد تا دکمه‌ی پرداخت بداند به کدام
    # ترمینال/حسابِ بانکی وصل شود؛ پس با مجوزِ فروش (نه صرفاً checks_bank) گیت می‌شود.
    _=Depends(require_permission("invoices", "view")),
):
    return db.query(PosTerminal).order_by(PosTerminal.label).all()


@router.post("/api/pos-terminals", response_model=PosTerminalOut, status_code=201)
def create_terminal(
    data: PosTerminalIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "update")),
):
    if data.is_default:
        _clear_default(db)
    terminal = PosTerminal(**data.model_dump())
    db.add(terminal)
    db.flush()
    db.refresh(terminal)
    return terminal


@router.patch("/api/pos-terminals/{terminal_id}", response_model=PosTerminalOut)
def update_terminal(
    terminal_id: UUID,
    data: PosTerminalIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "update")),
):
    terminal = db.get(PosTerminal, terminal_id)
    if terminal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دستگاهِ کارتخوان یافت نشد")
    if data.is_default and not terminal.is_default:
        _clear_default(db)
    for field, value in data.model_dump().items():
        setattr(terminal, field, value)
    db.flush()
    db.refresh(terminal)
    return terminal


@router.delete("/api/pos-terminals/{terminal_id}", status_code=204)
def delete_terminal(
    terminal_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "update")),
):
    terminal = db.get(PosTerminal, terminal_id)
    if terminal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دستگاهِ کارتخوان یافت نشد")
    db.delete(terminal)
