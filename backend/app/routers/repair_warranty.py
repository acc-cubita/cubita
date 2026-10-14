from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal, get_principal, require_module, require_permission
from app.models.repair import RepairWarranty
from app.schemas.repair import WarrantyIn, WarrantyClaimIn
from app.services import repair as core, repair_warranty as svc
from app.routers.repair_operations import once
from app.routers.repair_finance import related
from app.models.repair_completion import RepairWarrantyTransfer
from app.schemas.repair_identity import WarrantyTransferIn

router=APIRouter(prefix='/api/repair',tags=['repair'],dependencies=[Depends(require_module('repair')),Depends(require_permission('repair','view'))])


@router.get('/cases/{case_id}/warranties/{warranty_id}/transfer-preview',dependencies=[Depends(require_permission('repair_warranty_transfer','approve'))])
def transfer_preview(case_id:UUID,warranty_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return svc.transfer_preview(db,p,core.case(db,p,case_id),warranty_id)


@router.post('/cases/{case_id}/warranties/{warranty_id}/transfers',status_code=201,dependencies=[Depends(require_permission('repair_warranty_transfer','approve'))])
def transfer(case_id:UUID,warranty_id:UUID,data:WarrantyTransferIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    row=once(db,request,p,'repair.warranty.transfer:'+str(warranty_id),data,
        lambda:svc.transfer(db,p,core.case(db,p,case_id,lock=True),warranty_id,data),
        lambda rid:related(db,RepairWarrantyTransfer,case_id,rid))
    return core.out(row)

@router.get('/cases/{case_id}/warranties')
def overview(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return svc.overview(db,p,core.case(db,p,case_id))

@router.post('/cases/{case_id}/warranties',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def issue(case_id:UUID,data:WarrantyIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    row=once(db,request,p,'repair.warranty:'+str(case_id),data,
        lambda:svc.issue(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:related(db,RepairWarranty,case_id,rid))
    return core.out(row)

@router.post('/cases/{case_id}/revisits',status_code=201,dependencies=[Depends(require_permission('repair','approve')),Depends(require_permission('repair','create'))])
def revisit(case_id:UUID,data:WarrantyClaimIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    row=once(db,request,p,'repair.revisit:'+str(case_id),data,
        lambda:svc.revisit(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:core.case(db,p,rid))
    return core.out(row)
