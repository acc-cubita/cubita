from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal, get_principal, require_module, require_permission
from app.models.inventory import Warehouse
from app.models.repair import RepairPartMovement, RepairWork, RepairQualityCheck, RepairOutsource, RepairRemovedPart, RepairPurchaseRequest
from app.schemas.repair import DeviceSecretIn, PartActionIn, PartIn, WorkIn, QualityIn, OutsourceIn, OutsourceReturnIn, RemovedPartIn, SecretRevealIn, VersionIn, PurchaseRequestIn, PurchaseRequestUpdateIn
from app.services import repair as core, repair_parts as svc, repair_access
from app.services.idempotency import idempotent, read_key

router = APIRouter(prefix='/api/repair',tags=['repair'],dependencies=[Depends(require_module('repair')),Depends(require_permission('repair','view'))])


def once(db,request,p,operation,payload,run,replay):
    if not read_key(request): raise HTTPException(400,'Idempotency-Key لازم است؛ عملیات بدون محافظت ثبت نشد.')
    return idempotent(db,request,p.user,operation=operation,payload=payload,run=run,replay=replay)


def related(db,model,case_id,resource_id):
    row = db.query(model).filter_by(case_id=case_id,id=resource_id).one_or_none()
    if row is None: raise HTTPException(404,'رکورد مربوط به این پرونده پیدا نشد.')
    return row


@router.get('/warehouses')
def warehouses(db: Session = Depends(get_db)):
    return [{'id':w.id,'name':w.name} for w in db.query(Warehouse).filter_by(is_active=True).order_by(Warehouse.name).all()]


@router.get('/items/{item_id}/quantity-options')
def quantity_options(item_id:UUID,warehouse_id:UUID|None=None,db:Session=Depends(get_db)):
    from app.models.inventory import Item
    from app.models.item_units import ItemUnit,ItemUnitConversion
    from app.models.advanced_inventory import StockBatch
    from app.services import units,batches
    item=db.get(Item,item_id)
    if item is None or not item.is_active or item.is_service: raise HTTPException(404,'قطعهٔ فعال پیدا نشد.')
    unit_rows=db.query(ItemUnit).filter_by(item_id=item.id,is_active=True,inventory_allowed=True).all()
    rules=db.query(ItemUnitConversion).filter_by(item_id=item.id,is_active=True).all()
    batch_rows=db.query(StockBatch).filter_by(item_id=item.id,warehouse_id=warehouse_id).order_by(StockBatch.created_at,StockBatch.id).limit(200).all() if warehouse_id else []
    views=batches.qty_view(db,batch_rows)
    return {'units':[units.item_unit_row(db,item,u) for u in unit_rows],'rules':[units.rule_row(r) for r in rules],
            'batches':[{'id':b.id,'batch_number':b.batch_number,'qty':str(views[b.id]['qty'])} for b in batch_rows]}


@router.post('/cases/{case_id}/parts',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def part(case_id: UUID,data: PartIn,request: Request,db: Session = Depends(get_db),p: Principal = Depends(get_principal)):
    core.case(db,p,case_id)
    row = once(db,request,p,'repair.part:'+str(case_id),data,lambda:svc.request_part(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:svc.get_part(db,p,case_id,rid))
    return svc.projection(db,row)


@router.post('/cases/{case_id}/parts/{part_id}/actions',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def move(case_id: UUID,part_id: UUID,data: PartActionIn,request: Request,db: Session = Depends(get_db),p: Principal = Depends(get_principal)):
    svc.get_part(db,p,case_id,part_id)
    def replay(rid):
        row = db.query(RepairPartMovement).filter_by(part_id=part_id,id=rid).one_or_none()
        if row is None: raise HTTPException(404,'گردش مربوط به این قطعه پیدا نشد.')
        return row
    row = once(db,request,p,'repair.part-action:'+str(part_id),data,lambda:svc.move(db,p,core.case(db,p,case_id,lock=True),svc.get_part(db,p,case_id,part_id),data),replay)
    return core.out(row)


@router.post('/cases/{case_id}/work',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def work(case_id: UUID,data: WorkIn,request: Request,db: Session = Depends(get_db),p: Principal = Depends(get_principal)):
    core.case(db,p,case_id)
    row = once(db,request,p,'repair.work:'+str(case_id),data,lambda:svc.work(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:related(db,RepairWork,case_id,rid))
    return core.out(row)


@router.post('/cases/{case_id}/quality',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def quality(case_id: UUID,data: QualityIn,request: Request,db: Session = Depends(get_db),p: Principal = Depends(get_principal)):
    core.case(db,p,case_id)
    row = once(db,request,p,'repair.quality:'+str(case_id),data,lambda:svc.quality(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:related(db,RepairQualityCheck,case_id,rid))
    return core.out(row)


@router.post('/cases/{case_id}/outsources',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def outsource(case_id: UUID,data: OutsourceIn,request: Request,db: Session = Depends(get_db),p: Principal = Depends(get_principal)):
    core.case(db,p,case_id)
    row = once(db,request,p,'repair.outsource:'+str(case_id),data,lambda:svc.outsource(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:related(db,RepairOutsource,case_id,rid))
    return core.out(row)


@router.post('/cases/{case_id}/outsources/{outsource_id}/return',dependencies=[Depends(require_permission('repair','update'))])
def outsource_return(case_id: UUID,outsource_id: UUID,data: OutsourceReturnIn,db: Session = Depends(get_db),p: Principal = Depends(get_principal)):
    return core.out(svc.outsource_return(db,p,core.case(db,p,case_id,lock=True),outsource_id,data))


@router.post('/cases/{case_id}/removed-parts',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def removed(case_id: UUID,data: RemovedPartIn,request: Request,db: Session = Depends(get_db),p: Principal = Depends(get_principal)):
    core.case(db,p,case_id)
    row = once(db,request,p,'repair.removed:'+str(case_id),data,lambda:svc.removed(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:related(db,RepairRemovedPart,case_id,rid))
    return core.out(row)


@router.post('/cases/{case_id}/parts/{part_id}/purchase-request',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def purchase_request(case_id: UUID,part_id: UUID,data: PurchaseRequestIn,request: Request,db: Session = Depends(get_db),p: Principal = Depends(get_principal)):
    svc.get_part(db,p,case_id,part_id)
    def replay(rid):
        row = db.query(RepairPurchaseRequest).filter_by(id=rid,part_id=part_id).one_or_none()
        if row is None: raise HTTPException(404,'درخواست خرید مربوط به این قطعه پیدا نشد.')
        return row
    return core.out(once(db,request,p,'repair.purchase-request:'+str(part_id),data,lambda:svc.purchase_request(db,p,core.case(db,p,case_id,lock=True),svc.get_part(db,p,case_id,part_id),data),replay))


@router.put('/cases/{case_id}/parts/{part_id}/purchase-request',dependencies=[Depends(require_permission('repair','update'))])
def update_purchase_request(case_id: UUID,part_id: UUID,data: PurchaseRequestUpdateIn,db: Session = Depends(get_db),p: Principal = Depends(get_principal)):
    return core.out(svc.update_purchase_request(db,p,core.case(db,p,case_id,lock=True),svc.get_part(db,p,case_id,part_id),data))


@router.get('/access-capabilities')
def access_capabilities():
    return {'encrypted_storage_available':repair_access.available()}


@router.put('/cases/{case_id}/device-secret',dependencies=[Depends(require_permission('repair_access','update'))])
def secret(case_id: UUID,data: DeviceSecretIn,db: Session = Depends(get_db),p: Principal = Depends(get_principal)):
    return repair_access.set_secret(db,p,core.case(db,p,case_id,lock=True),data)


@router.post('/cases/{case_id}/device-secret/reveal',dependencies=[Depends(require_permission('repair_access','view'))])
def reveal(case_id: UUID,data: SecretRevealIn,response: Response,db: Session = Depends(get_db),p: Principal = Depends(get_principal)):
    response.headers['Cache-Control'] = 'no-store'
    return repair_access.reveal(db,p,core.case(db,p,case_id,lock=True),data)


@router.post('/cases/{case_id}/device-secret/clear',dependencies=[Depends(require_permission('repair_access','update'))])
def clear_secret(case_id: UUID,data: VersionIn,db: Session = Depends(get_db),p: Principal = Depends(get_principal)):
    return repair_access.clear(db,p,core.case(db,p,case_id,lock=True),data)


@router.put('/cases/{case_id}/removed-parts/{removed_id}/disposition',dependencies=[Depends(require_permission('repair','update'))])
def removed_disposition(case_id:UUID,removed_id:UUID,data:RemovedPartIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=core.case(db,p,case_id,lock=True);core.check_version(row,data.version)
    if row.status in {'delivered','closed'}: raise HTTPException(409,'تحویل قطعهٔ پروندهٔ پایان‌یافته بازنویسی نمی‌شود.')
    part=related(db,RepairRemovedPart,case_id,removed_id)
    if part.disposition!='retained' or data.disposition=='retained' or data.title!=part.title: raise HTTPException(409,'تنها قطعهٔ نگهداری‌شده با عنوان قبلی قابل تعیین تکلیف است.')
    before=core.out(part)
    for k,v in data.model_dump(exclude={'version','title'}).items(): setattr(part,k,v)
    part.recorded_by_id=p.user.id
    core.event(db,p,row,'removed_part_disposition',{'before':{k:str(v) for k,v in before.items() if k!='created_at' and k!='updated_at'},'after':data.model_dump(mode='json')})
    return core.out(part)
