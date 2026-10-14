from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal, get_principal, require_module, require_permission
from app.models.repair_completion import RepairTechnicalSummary
from app.routers.repair_completion import private_response
from app.routers.repair_operations import once, related
from app.schemas.repair_identity import TechnicalSummaryIn
from app.services import repair as core, repair_summary as svc

router = APIRouter(prefix='/api/repair', tags=['repair'], dependencies=[Depends(require_module('repair')),
    Depends(require_permission('repair','view')), Depends(private_response)])


@router.get('/cases/{case_id}/technical-summaries')
def summaries(case_id:UUID, db:Session=Depends(get_db), p:Principal=Depends(get_principal)):
    row = core.case(db,p,case_id)
    return {'items':svc.for_recipient(db,row)}


@router.get('/cases/{case_id}/technical-summary-preview', dependencies=[Depends(require_permission('repair_technical_summary','approve'))])
def preview(case_id:UUID, db:Session=Depends(get_db), p:Principal=Depends(get_principal)):
    return svc.preview(db,p,core.case(db,p,case_id))


@router.post('/cases/{case_id}/technical-summaries', status_code=201, dependencies=[Depends(require_permission('repair_technical_summary','approve'))])
def approve(case_id:UUID, data:TechnicalSummaryIn, request:Request, db:Session=Depends(get_db), p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    result = once(db,request,p,'repair.summary:'+str(case_id),data,
        lambda:svc.approve(db,p,core.case(db,p,case_id,lock=True),data),
        lambda rid:related(db,RepairTechnicalSummary,case_id,rid))
    return svc.public(result)
