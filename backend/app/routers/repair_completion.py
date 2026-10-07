from uuid import UUID
from fastapi import APIRouter, Depends, Request, Response, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal, get_principal, require_permission, require_module
from app.models.repair_completion import RepairBulkOperation, RepairAcknowledgment, RepairIntakeBatch
from app.schemas.repair_completion import BranchSettingsIn, QuickAdmissionIn, BatchAdmissionIn, IntakeDetailsIn, CapacityIn, AcknowledgmentIn, BulkOperationIn
from app.services import repair as core, repair_completion as svc
from app.services.idempotency import idempotent, read_key

def private_response(response:Response):
    response.headers['Cache-Control']='no-store'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Content-Type-Options']='nosniff'


router=APIRouter(prefix='/api/repair',tags=['repair'],dependencies=[Depends(require_module('repair')),Depends(require_permission('repair','view')),Depends(private_response)])

from app.models.repair import RepairCase
from app.models.repair_completion import RepairTimeSession
from app.schemas.repair_completion import TimeStartIn, TimeActionIn
from app.services import repair_time


@router.get('/time-sessions')
def time_sessions(case_id:UUID|None=None,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    query=db.query(RepairTimeSession).filter_by(technician_id=p.user.id)
    if case_id:
        core.case(db,p,case_id)
        query=query.filter_by(case_id=case_id)
    visible_ids=core.visible(db,p).with_entities(RepairCase.id)
    return [repair_time.out(r) for r in query.filter(RepairTimeSession.case_id.in_(visible_ids)).order_by(RepairTimeSession.started_at.desc()).limit(200)]


@router.post('/cases/{case_id}/time-sessions',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def start_time(case_id:UUID,data:TimeStartIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    row=idempotent(db,request,p.user,operation='repair.time_start:'+str(case_id),payload=data,
        run=lambda:repair_time.start(db,p,core.case(db,p,case_id,lock=True),data),replay=lambda rid:repair_time.view(db,p,rid))
    return repair_time.out(row)


@router.post('/time-sessions/{session_id}/actions',dependencies=[Depends(require_permission('repair','update'))])
def time_action(session_id:UUID,data:TimeActionIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    row=idempotent(db,request,p.user,operation='repair.time_action:'+str(session_id),payload=data,
        run=lambda:repair_time.change(db,p,session_id,data),replay=lambda rid:repair_time.view(db,p,rid))
    return repair_time.out(row)


def keyed(request):
    if not read_key(request): raise HTTPException(400,'برای جلوگیری از ثبت دوباره، Idempotency-Key لازم است.')


@router.get('/branches/{branch_id}/intake-settings')
def settings(branch_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=svc.settings(db,p,branch_id)
    return core.out(row) if row else None


@router.put('/branches/{branch_id}/intake-settings',dependencies=[Depends(require_permission('repair','approve'))])
def save_settings(branch_id:UUID,data:BranchSettingsIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return core.out(svc.save_settings(db,p,branch_id,data))


@router.post('/quick-admissions',status_code=201,dependencies=[Depends(require_permission('repair','create'))])
def quick(data:QuickAdmissionIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    row=idempotent(db,request,p.user,operation='repair.quick_admission',payload=data,run=lambda:svc.quick(db,p,data),replay=lambda rid:core.case(db,p,rid))
    return core.detail(db,p,row)


@router.post('/intake-batches',status_code=201,dependencies=[Depends(require_permission('repair','create'))])
def batch(data:BatchAdmissionIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    row=idempotent(db,request,p.user,operation='repair.intake_batch',payload=data,run=lambda:svc.batch(db,p,data),replay=lambda rid:db.get(RepairIntakeBatch,rid))
    return svc.batch_result(db,p,row.id)


@router.get('/intake-batches/{batch_id}')
def batch_result(batch_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return svc.batch_result(db,p,batch_id)


@router.patch('/cases/{case_id}/intake-details',dependencies=[Depends(require_permission('repair','update'))])
def amend(case_id:UUID,data:IntakeDetailsIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    row=idempotent(db,request,p.user,operation='repair.intake_details:'+str(case_id),payload=data,
        run=lambda:svc.amend(db,p,core.case(db,p,case_id,lock=True),data),replay=lambda rid:core.case(db,p,rid))
    return core.detail(db,p,row)


@router.get('/technician-suggestions')
def suggestions(branch_id:UUID,type_id:UUID|None=None,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return svc.suggestions(db,p,branch_id,type_id)


@router.put('/technicians/{user_id}/capacity',dependencies=[Depends(require_permission('repair','approve'))])
def capacity(user_id:UUID,data:CapacityIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return core.out(svc.save_capacity(db,p,user_id,data))


@router.post('/bulk-operations',status_code=201)
def bulk(data:BulkOperationIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    row=idempotent(db,request,p.user,operation='repair.bulk',payload=data,run=lambda:svc.bulk(db,p,data),replay=lambda rid:db.get(RepairBulkOperation,rid))
    if row is None or row.created_by_id != p.user.id: raise HTTPException(404,'عملیات گروهی پیدا نشد.')
    return core.out(row)


@router.post('/cases/{case_id}/acknowledgments',status_code=201,dependencies=[Depends(require_permission('repair_signatures','create'))])
def acknowledge(case_id:UUID,data:AcknowledgmentIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    core.case(db,p,case_id)
    row=idempotent(db,request,p.user,operation='repair.acknowledgment:'+str(case_id),payload=data,
        run=lambda:svc.acknowledge(db,p,core.case(db,p,case_id,lock=True),data),replay=lambda rid:db.get(RepairAcknowledgment,rid))
    return {'id':row.id,'kind':row.kind,'document_revision':row.document_revision,'document_hash':row.document_hash}


@router.get('/cases/{case_id}/acknowledgments',dependencies=[Depends(require_permission('repair_signatures','view'))])
def acknowledgments(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    return [core.out(r) for r in db.query(RepairAcknowledgment).filter_by(case_id=case_id).order_by(RepairAcknowledgment.created_at)]


@router.get('/cases/{case_id}/receipt.pdf')
def receipt_pdf(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    from app.services.repair_printing import pdf_receipt
    row=core.case(db,p,case_id)
    return Response(pdf_receipt(db,row),media_type='application/pdf',headers={'Cache-Control':'no-store','Content-Disposition':f'attachment; filename="repair-{row.number}.pdf"'})


@router.get('/cases/{case_id}/label')
def label(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    from app.services.repair_printing import label_html
    return Response(label_html(db,core.case(db,p,case_id)),media_type='text/html',headers={'Cache-Control':'no-store'})
