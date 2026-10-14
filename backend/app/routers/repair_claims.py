from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal,get_principal,require_module,require_permission
from app.models.repair import RepairDeviceIdentityEvent as Event
from app.pagination import PageParams,paginate
from app.routers.repair_completion import private_response
from app.routers.repair_operations import once,related
from app.schemas.repair_identity import OwnershipClaimIn,OwnershipClaimDecisionIn
from app.services import repair as core,repair_claims as svc
from app.services import repair_identity as identity

router=APIRouter(prefix='/api/repair',tags=['repair'],dependencies=[Depends(require_module('repair')),
    Depends(require_permission('repair','view')),Depends(private_response)])


@router.get('/cases/{case_id}/ownership-claim-preview',dependencies=[Depends(require_permission('repair_identity','approve'))])
def preview(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    from app.models.inventory import Contact
    row=core.case(db,p,case_id)
    main=identity.canonical(db,p,identity.device(db,p,row.device_id))
    owner=identity.latest(db,p,main.id,'ownership')
    contact=db.query(Contact).filter_by(tenant_id=p.tenant_id,id=owner.contact_id).one_or_none() if owner else None
    return {'device_version':main.version,'previous_ownership_id':owner.id if owner else None,
            'owner_name':contact.name if contact else 'تأییدنشده'}


@router.get('/cases/{case_id}/ownership-claims',dependencies=[Depends(require_permission('repair_identity','view'))])
def claims(case_id:UUID,params:PageParams=Depends(),db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    query=db.query(Event).filter_by(tenant_id=p.tenant_id,case_id=case_id)
    rows,cursor=paginate(query,[Event.revision],params)
    return {'items':[core.out(row) for row in rows],'next_cursor':cursor}


@router.post('/cases/{case_id}/ownership-claims',status_code=201,dependencies=[Depends(require_permission('repair','create'))])
def submit(case_id:UUID,data:OwnershipClaimIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    result=once(db,request,p,'repair.claim:'+str(case_id),data,
        lambda:svc.submit(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:related(db,Event,case_id,rid))
    return core.out(result)


@router.post('/cases/{case_id}/ownership-claims/{claim_id}/decision',status_code=201,dependencies=[Depends(require_permission('repair_identity','approve'))])
def decide(case_id:UUID,claim_id:UUID,data:OwnershipClaimDecisionIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    result=once(db,request,p,'repair.claim.decision:'+str(claim_id),data,
        lambda:svc.resolve(db,p,core.case(db,p,case_id,lock=True),claim_id,data),lambda rid:related(db,Event,case_id,rid))
    return core.out(result)
