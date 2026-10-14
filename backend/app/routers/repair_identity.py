from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal, get_principal, require_module, require_permission
from app.models.repair import RepairDeviceIdentityEvent
from app.pagination import PageParams, paginate
from app.routers.repair_completion import private_response, keyed
from app.schemas.repair_identity import DeviceMergeIn, DeviceOwnershipIn, DeviceProfileIn
from app.services import repair as core, repair_identity as svc
from app.services.idempotency import idempotent
from fastapi.responses import HTMLResponse

router = APIRouter(prefix='/api/repair/devices', tags=['repair'], dependencies=[
    Depends(require_module('repair')), Depends(require_permission('repair', 'view')), Depends(private_response)])


@router.get('')
def search(q: str = Query('', max_length=200), limit: int = Query(30, ge=1, le=200),
           db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return {'items': svc.search(db, p, q, limit)}


@router.get('/{device_id}')
def identity(device_id: UUID, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.public_identity(db, p, svc.device(db, p, device_id))


@router.get('/{device_id}/label', response_class=HTMLResponse)
def label(device_id: UUID, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    from app.services.repair_printing import device_label_html
    return HTMLResponse(device_label_html(svc.device(db,p,device_id)), headers={'Cache-Control':'no-store'})


@router.get('/{device_id}/cases')
def history(device_id: UUID, params: PageParams = Depends(), db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    query = svc.history(db, p, svc.device(db, p, device_id)).order_by(None)
    from app.models.repair import RepairCase
    rows, cursor = paginate(query, [RepairCase.number], params)
    return {'items': [core.out(row) for row in rows], 'next_cursor': cursor}


@router.get('/{device_id}/identity-events', dependencies=[Depends(require_permission('repair_identity', 'view'))])
def events(device_id: UUID, params: PageParams = Depends(), db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    svc.device(db, p, device_id)
    from sqlalchemy import or_
    from app.models.repair import RepairCase
    visible_cases = core.visible(db,p).with_entities(RepairCase.id)
    query = db.query(RepairDeviceIdentityEvent).filter_by(tenant_id=p.tenant_id, device_id=device_id).filter(
        RepairDeviceIdentityEvent.kind.in_(['merge','ownership','profile']),
        or_(RepairDeviceIdentityEvent.case_id.is_(None),RepairDeviceIdentityEvent.case_id.in_(visible_cases)))
    rows, cursor = paginate(query, [RepairDeviceIdentityEvent.revision], params)
    return {'items': [core.out(row) for row in rows], 'next_cursor': cursor,
            'ownership_status': 'confirmed' if svc.latest(db, p, device_id, 'ownership') else 'unverified'}


@router.post('/{device_id}/merge-preview', dependencies=[Depends(require_permission('repair_identity', 'approve'))])
def preview(device_id: UUID, data: DeviceMergeIn, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    source, target = svc.merge_preview(db, p, device_id, data)
    return {'source': svc.public_identity(db, p, source), 'target': svc.public_identity(db, p, target),
            'owners':svc.merge_owners(db,p,source,target),
            'preserves_historical_cases': True, 'transfers_financial_records': False}


def record(db, p, rid):
    return db.query(RepairDeviceIdentityEvent).filter_by(tenant_id=p.tenant_id, id=rid).one()


@router.post('/{device_id}/merge', status_code=201, dependencies=[Depends(require_permission('repair_identity', 'approve'))])
def merge(device_id: UUID, data: DeviceMergeIn, request: Request, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    keyed(request)
    result = idempotent(db, request, p.user, operation=f'repair.device.merge.{device_id}', payload=data,
        run=lambda: svc.merge(db, p, device_id, data), replay=lambda rid: record(db, p, rid))
    return core.out(result)


@router.post('/{device_id}/ownership', status_code=201, dependencies=[Depends(require_permission('repair_identity', 'approve'))])
def ownership(device_id: UUID, data: DeviceOwnershipIn, request: Request, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    keyed(request)
    result = idempotent(db, request, p.user, operation=f'repair.device.ownership.{device_id}', payload=data,
        run=lambda: svc.ownership(db, p, device_id, data), replay=lambda rid: record(db, p, rid))
    return core.out(result)


@router.post('/{device_id}/profile',status_code=201,dependencies=[Depends(require_permission('repair_identity','approve'))])
def profile(device_id:UUID,data:DeviceProfileIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation=f'repair.device.profile.{device_id}',payload=data,
        run=lambda:svc.profile(db,p,device_id,data),replay=lambda rid:record(db,p,rid))
    return core.out(result)
