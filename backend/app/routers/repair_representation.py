from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal,get_principal,require_module,require_permission
from app.models.repair_completion import RepairRepresentativeAuthorization as Authorization
from app.pagination import PageParams,paginate
from app.routers.repair_completion import private_response
from app.routers.repair_operations import once
from app.schemas.repair_identity import RepresentativeIn,RepresentativeRevokeIn
from app.services import repair as core,repair_representation as svc

router=APIRouter(prefix='/api/repair',tags=['repair'],dependencies=[Depends(require_module('repair')),
    Depends(require_permission('repair','view')),Depends(private_response)])


@router.get('/cases/{case_id}/representatives')
def representatives(case_id:UUID,params:PageParams=Depends(),db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=core.case(db,p,case_id)
    if not any(p.has_permission(resource,action) for resource,action in [('repair_representation','view'),('repair_representation','approve'),('repair_signatures','create')]):
        raise HTTPException(403,'مشاهدهٔ نمایندگان به مجوز مستقل نیاز دارد.')
    rows,cursor=paginate(db.query(Authorization).filter_by(tenant_id=p.tenant_id,case_id=case_id),[Authorization.created_at],params)
    return {'items':[svc.public(db,row,r,evidence=p.has_permission('repair_representation','view')) for r in rows],'next_cursor':cursor}


@router.post('/cases/{case_id}/representatives',status_code=201,dependencies=[Depends(require_permission('repair_representation','approve'))])
def approve(case_id:UUID,data:RepresentativeIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=core.case(db,p,case_id)
    result=once(db,request,p,'repair.representative:'+str(case_id),data,
        lambda:svc.approve(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:svc.get(db,row,rid))
    return svc.public(db,row,result,evidence=p.has_permission('repair_representation','view'))


@router.post('/cases/{case_id}/representatives/{rid}/revoke',status_code=201,dependencies=[Depends(require_permission('repair_representation','approve'))])
def revoke(case_id:UUID,rid:UUID,data:RepresentativeRevokeIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=core.case(db,p,case_id)
    result=once(db,request,p,'repair.representative.revoke:'+str(rid),data,
        lambda:svc.revoke(db,p,core.case(db,p,case_id,lock=True),rid,data),lambda result_id:svc.get(db,row,result_id))
    return svc.public(db,row,result,evidence=p.has_permission('repair_representation','view'))
