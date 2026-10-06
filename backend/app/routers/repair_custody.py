from uuid import UUID
from fastapi import APIRouter,Depends,Request,HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal,get_principal,require_module,require_permission
from app.models.repair import RepairCustodyTransfer,RepairCustodyLeg
from app.schemas.repair import CustodyTransferIn,CustodyLegIn,CustodyReceiveIn
from app.services import repair as core,repair_custody as svc
from app.routers.repair_operations import once
router=APIRouter(prefix='/api/repair',tags=['repair'],dependencies=[Depends(require_module('repair')),Depends(require_permission('repair','view'))])

def related(db,case_id,rid):
    row=db.query(RepairCustodyTransfer).filter_by(case_id=case_id,id=rid).one_or_none()
    if row is None: raise HTTPException(404,'حمل این پرونده پیدا نشد.')
    return row

@router.get('/cases/{case_id}/custody')
def history(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return svc.overview(db,core.case(db,p,case_id))

@router.post('/cases/{case_id}/custody',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def dispatch(case_id:UUID,data:CustodyTransferIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    return core.out(once(db,request,p,'repair.custody:'+str(case_id),data,lambda:svc.dispatch(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:related(db,case_id,rid)))

@router.post('/cases/{case_id}/custody/{rid}/handover',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def handover(case_id:UUID,rid:UUID,data:CustodyLegIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    def replay(lid):
        transfer=related(db,case_id,rid);leg=db.query(RepairCustodyLeg).filter_by(id=lid,transfer_id=transfer.id).one_or_none()
        if leg is None: raise HTTPException(404,'تحویل بین راه پیدا نشد.')
        return leg
    return core.out(once(db,request,p,'repair.custody-leg:'+str(rid),data,lambda:svc.handover(db,p,core.case(db,p,case_id,lock=True),related(db,case_id,rid),data),replay))

@router.post('/cases/{case_id}/custody/{rid}/receive',dependencies=[Depends(require_permission('repair','approve'))])
def receive(case_id:UUID,rid:UUID,data:CustodyReceiveIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    return core.out(once(db,request,p,'repair.custody-receive:'+str(rid),data,lambda:svc.receive(db,p,core.case(db,p,case_id,lock=True),related(db,case_id,rid),data),lambda result_id:related(db,case_id,result_id)))
