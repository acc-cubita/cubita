from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.contracting import Contract, ContractAmendment, ContractSettlement, ContractStatement
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.contracting import (
    ContractAmendmentIn,
    ContractAmendmentOut,
    ContractIn,
    ContractOut,
    ContractSettlementIn,
    ContractSettlementOut,
    ContractStatementIn,
    ContractStatementOut,
    ContractStatusIn,
    VoidContractSettlementIn,
)
from app.services import contracting as service
from app.services.idempotency import idempotent

router = APIRouter(prefix="/api/contracting", tags=["contracting"])


@router.get("/contracts", response_model=Page[ContractOut])
def list_contracts(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    status: str | None = None,
    contact_id: UUID | None = None,
    _=Depends(require_permission("contracting", "view")),
):
    query = db.query(Contract)
    if status:
        query = query.filter(Contract.status == status)
    if contact_id:
        query = query.filter(Contract.contact_id == contact_id)
    rows, next_cursor = paginate(query, [Contract.created_at, Contract.number], params)
    return Page(items=rows, next_cursor=next_cursor)


@router.post("/contracts", response_model=ContractOut, status_code=201)
def create_contract(
    data: ContractIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("contracting", "create")),
):
    """**idempotent** — دوکلیک نباید دو پیمان با یک شماره بسازد."""
    return idempotent(
        db, request, user, operation="create_contract", payload=data,
        run=lambda: service.create_contract(db, data, user),
        replay=lambda cid: db.get(Contract, cid),
    )


@router.patch("/contracts/{contract_id}/status", response_model=ContractOut)
def change_contract_status(
    contract_id: UUID,
    data: ContractStatusIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("contracting", "update")),
):
    return service.change_contract_status(db, contract_id, data.status, user)


@router.get("/amendments", response_model=Page[ContractAmendmentOut])
def list_contract_amendments(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    contract_id: UUID | None = None,
    _=Depends(require_permission("contracting", "view")),
):
    query = db.query(ContractAmendment)
    if contract_id:
        query = query.filter(ContractAmendment.contract_id == contract_id)
    rows, next_cursor = paginate(query, [ContractAmendment.created_at, ContractAmendment.number], params)
    return Page(items=rows, next_cursor=next_cursor)


@router.post("/amendments", response_model=ContractAmendmentOut, status_code=201)
def create_contract_amendment(
    data: ContractAmendmentIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("contracting", "create")),
):
    """**idempotent** — دوکلیک نباید دو متمم با یک شماره بسازد."""
    return idempotent(
        db, request, user, operation="create_contract_amendment", payload=data,
        run=lambda: service.create_contract_amendment(db, data, user),
        replay=lambda aid: db.get(ContractAmendment, aid),
    )


@router.get("/statements", response_model=Page[ContractStatementOut])
def list_contract_statements(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    contract_id: UUID | None = None,
    _=Depends(require_permission("contracting", "view")),
):
    query = db.query(ContractStatement)
    if contract_id:
        query = query.filter(ContractStatement.contract_id == contract_id)
    rows, next_cursor = paginate(query, [ContractStatement.created_at, ContractStatement.number], params)
    return Page(items=rows, next_cursor=next_cursor)


@router.post("/statements", response_model=ContractStatementOut, status_code=201)
def create_contract_statement(
    data: ContractStatementIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("contracting", "create")),
):
    """**idempotent** — دوکلیک نباید دو صورت‌وضعیت با یک شماره بسازد."""
    return idempotent(
        db, request, user, operation="create_contract_statement", payload=data,
        run=lambda: service.create_contract_statement(db, data, user),
        replay=lambda sid: db.get(ContractStatement, sid),
    )


@router.get("/settlements", response_model=Page[ContractSettlementOut])
def list_contract_settlements(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    contract_id: UUID | None = None,
    _=Depends(require_permission("contracting", "view")),
):
    query = db.query(ContractSettlement)
    if contract_id:
        query = query.filter(ContractSettlement.contract_id == contract_id)
    rows, next_cursor = paginate(query, [ContractSettlement.created_at, ContractSettlement.number], params)
    return Page(items=rows, next_cursor=next_cursor)


@router.post("/settlements", response_model=ContractSettlementOut, status_code=201)
def create_contract_settlement(
    data: ContractSettlementIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("contracting", "create")),
):
    """**idempotent** — دوکلیک نباید دو سندِ تسویه بسازد."""
    return idempotent(
        db, request, user, operation="create_contract_settlement", payload=data,
        run=lambda: service.create_contract_settlement(db, data, user),
        replay=lambda sid: db.get(ContractSettlement, sid),
    )


@router.post("/settlements/{settlement_id}/void", response_model=ContractSettlementOut)
def void_contract_settlement(
    settlement_id: UUID,
    data: VoidContractSettlementIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("contracting", "update")),
):
    return service.void_contract_settlement(db, user, settlement_id, data.reason, data.void_date)
