from uuid import UUID
from fastapi import APIRouter,Depends,Request,HTTPException,Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal,get_principal,require_module,require_permission
from app.models.assets import FixedAsset
from app.models.repair import RepairLoan
from app.schemas.repair import LoanIn,LoanReturnIn
from app.services import repair as core,repair_loans as svc
from app.routers.repair_operations import once
from app.routers.repair_finance import related
router=APIRouter(prefix='/api/repair',tags=['repair'],dependencies=[Depends(require_module('repair')),Depends(require_permission('repair','view'))])

@router.get('/loan-assets',dependencies=[Depends(require_permission('assets','view'))])
def choices(q:str=Query(default='',max_length=120),db:Session=Depends(get_db)):
    query=db.query(FixedAsset).filter(FixedAsset.is_disposed.is_(False),~FixedAsset.id.in_(db.query(RepairLoan.asset_id).filter_by(returned_at=None)))
    if q: query=query.filter(FixedAsset.name.ilike('%'+q+'%'))
    return [dict(id=a.id,name=a.name,category=a.category,location=a.location) for a in query.order_by(FixedAsset.name,FixedAsset.id).limit(200)]

@router.get('/cases/{case_id}/loans')
def history(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    return [core.out(l) for l in db.query(RepairLoan).filter_by(case_id=case_id).order_by(RepairLoan.created_at.desc()).limit(200)]

@router.post('/cases/{case_id}/loans',status_code=201,dependencies=[Depends(require_permission('repair','approve')),Depends(require_permission('assets','update'))])
def checkout(case_id:UUID,data:LoanIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    return core.out(once(db,request,p,'repair.loan:'+str(case_id),data,lambda:svc.checkout(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:related(db,RepairLoan,case_id,rid)))

@router.post('/cases/{case_id}/loans/{rid}/return',dependencies=[Depends(require_permission('repair','approve')),Depends(require_permission('assets','update'))])
def checkin(case_id:UUID,rid:UUID,data:LoanReturnIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    return core.out(once(db,request,p,'repair.loan-return:'+str(rid),data,lambda:svc.checkin(db,p,core.case(db,p,case_id,lock=True),related(db,RepairLoan,case_id,rid),data),lambda result_id:related(db,RepairLoan,case_id,result_id)))
