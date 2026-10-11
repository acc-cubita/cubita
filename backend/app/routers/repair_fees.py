from uuid import UUID
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal, get_principal, require_module, require_permission
from app.models.repair import RepairFeeRule, RepairTechnicianFee
from app.schemas.repair import FeeRuleIn, FeeDraftIn, FeeApproveIn
from app.services import repair as core, repair_fees as svc
from app.routers.repair_operations import once
from app.routers.repair_finance import related

router=APIRouter(prefix='/api/repair',tags=['repair'],dependencies=[Depends(require_module('repair')),Depends(require_permission('repair','view')),Depends(require_permission('repair','approve'))])

@router.get('/fee-rules')
def rules(db:Session=Depends(get_db)):
    return [core.out(r) for r in db.query(RepairFeeRule).order_by(RepairFeeRule.created_at.desc()).limit(200)]

@router.post('/fee-rules',status_code=201)
def rule(data:FeeRuleIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    def replay(rid):
        row=db.get(RepairFeeRule,rid)
        if row is None: raise HTTPException(404,'قاعده پیدا نشد.')
        return row
    return core.out(once(db,request,p,'repair.fee-rule',data,lambda:svc.create_rule(db,p,data),replay))

@router.get('/cases/{case_id}/technician-fees',dependencies=[Depends(require_permission('invoices','view'))])
def fees(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    return [svc.projection(db,f) for f in db.query(RepairTechnicianFee).filter_by(case_id=case_id).order_by(RepairTechnicianFee.created_at.desc()).limit(200)]

@router.post('/cases/{case_id}/technician-fees',status_code=201)
def draft(case_id:UUID,data:FeeDraftIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    return core.out(once(db,request,p,'repair.fee:'+str(case_id),data,lambda:svc.draft(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:related(db,RepairTechnicianFee,case_id,rid)))

@router.post('/cases/{case_id}/technician-fees/{fee_id}/approve',dependencies=[Depends(require_permission('invoices','create'))])
def approve(case_id:UUID,fee_id:UUID,data:FeeApproveIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    return core.out(once(db,request,p,'repair.fee-approve:'+str(fee_id),data,lambda:svc.approve(db,p,core.case(db,p,case_id,lock=True),related(db,RepairTechnicianFee,case_id,fee_id),data),lambda rid:related(db,RepairTechnicianFee,case_id,rid)))
