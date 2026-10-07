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
def time_sessions(case_id:UUID|None=None,technician_id:UUID|None=None,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    from app.models.repair_completion import RepairWorkTimeLink
    technician=technician_id or p.user.id
    if technician!=p.user.id and not p.has_permission('repair','approve'): raise HTTPException(403,'زمان تکنسین دیگر دسترسی مدیریت می‌خواهد.')
    query=db.query(RepairTimeSession).filter_by(technician_id=technician)
    if case_id:
        core.case(db,p,case_id)
        query=query.filter_by(case_id=case_id)
    visible_ids=core.visible(db,p).with_entities(RepairCase.id)
    rows=query.filter(RepairTimeSession.case_id.in_(visible_ids)).order_by(RepairTimeSession.started_at.desc()).limit(200).all()
    links={link.session_id:link.work_id for link in db.query(RepairWorkTimeLink).filter(RepairWorkTimeLink.session_id.in_([r.id for r in rows]))}
    return [{**repair_time.out(r),'used_work_id':links.get(r.id)} for r in rows]


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


from app.models.repair_completion import RepairServiceProfile,RepairTypeProtocol,RepairDiagnosticRecord,RepairSupervisorReview,RepairWorkPause,RepairDeadlineAgreement,RepairKnowledgeArticle
from app.schemas.repair_completion import ServiceProfileIn,TypeProtocolIn,DiagnosticRecordIn,SupervisorReviewIn,PauseStartIn,PauseEndIn,DeadlineProposalIn,DeadlineDecisionIn,KnowledgeIn,KnowledgeApprovalIn
from app.services import repair_tools as technical


def case_resource(db,p,model,resource_id,case_id):
    core.case(db,p,case_id)
    result=db.query(model).filter_by(id=resource_id,case_id=case_id).one_or_none()
    if result is None: raise HTTPException(404,'رکورد پرونده پیدا نشد.')
    return result


def branch_resource(db,p,model,resource_id,branch_id):
    core.branch(db,p,branch_id)
    result=db.query(model).filter_by(id=resource_id,branch_id=branch_id).one_or_none()
    if result is None: raise HTTPException(404,'رکورد شعبه پیدا نشد.')
    return result


@router.get('/branches/{branch_id}/service-profiles')
def service_profiles(branch_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return technical.service_profiles(db,p,branch_id)


@router.post('/branches/{branch_id}/service-profiles',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def service_profile(branch_id:UUID,data:ServiceProfileIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.service_profile:'+str(branch_id),payload=data,
        run=lambda:technical.save_service_profile(db,p,branch_id,data),replay=lambda rid:branch_resource(db,p,RepairServiceProfile,rid,branch_id))
    return core.out(result)


@router.get('/branches/{branch_id}/type-protocols/{type_id}')
def type_protocol(branch_id:UUID,type_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    result=technical.protocol(db,p,branch_id,type_id)
    return core.out(result) if result else None


@router.post('/branches/{branch_id}/type-protocols',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def save_type_protocol(branch_id:UUID,data:TypeProtocolIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.type_protocol:'+str(branch_id),payload=data,
        run=lambda:technical.save_protocol(db,p,branch_id,data),replay=lambda rid:branch_resource(db,p,RepairTypeProtocol,rid,branch_id))
    return core.out(result)


@router.get('/cases/{case_id}/technical-records')
def technical_records(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=core.case(db,p,case_id)
    return {'diagnostics':[core.out(r) for r in db.query(RepairDiagnosticRecord).filter_by(case_id=case_id).order_by(RepairDiagnosticRecord.revision.desc()).limit(200)],
        'reviews':[core.out(r) for r in db.query(RepairSupervisorReview).filter_by(case_id=case_id).order_by(RepairSupervisorReview.created_at.desc()).limit(200)],
        'pauses':[technical.pause_out(r) for r in db.query(RepairWorkPause).filter_by(case_id=case_id).order_by(RepairWorkPause.started_at.desc()).limit(200)],
        'agreements':[core.out(r) for r in db.query(RepairDeadlineAgreement).filter_by(case_id=case_id).order_by(RepairDeadlineAgreement.created_at.desc()).limit(200)],
        'similar_cases':technical.similar_cases(db,p,row)}


@router.post('/cases/{case_id}/diagnostic-records',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def diagnostic_record(case_id:UUID,data:DiagnosticRecordIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.diagnostic_record:'+str(case_id),payload=data,
        run=lambda:technical.diagnostic(db,p,core.case(db,p,case_id,lock=True),data),replay=lambda rid:case_resource(db,p,RepairDiagnosticRecord,rid,case_id))
    return core.out(result)


@router.post('/cases/{case_id}/supervisor-reviews',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def supervisor_review(case_id:UUID,data:SupervisorReviewIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.supervisor_review:'+str(case_id),payload=data,
        run=lambda:technical.review(db,p,core.case(db,p,case_id,lock=True),data),replay=lambda rid:case_resource(db,p,RepairSupervisorReview,rid,case_id))
    return core.out(result)


@router.post('/cases/{case_id}/work-pauses',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def start_pause(case_id:UUID,data:PauseStartIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.pause_start:'+str(case_id),payload=data,
        run=lambda:technical.start_pause(db,p,core.case(db,p,case_id,lock=True),data),replay=lambda rid:case_resource(db,p,RepairWorkPause,rid,case_id))
    return technical.pause_out(result)


@router.post('/cases/{case_id}/work-pauses/{pause_id}/end',dependencies=[Depends(require_permission('repair','update'))])
def end_pause(case_id:UUID,pause_id:UUID,data:PauseEndIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.pe:'+case_id.hex+pause_id.hex,payload=data,
        run=lambda:technical.end_pause(db,p,core.case(db,p,case_id,lock=True),pause_id,data),replay=lambda rid:case_resource(db,p,RepairWorkPause,rid,case_id))
    return technical.pause_out(result)


@router.post('/cases/{case_id}/deadline-agreements',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def propose_deadline(case_id:UUID,data:DeadlineProposalIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.deadline_propose:'+str(case_id),payload=data,
        run=lambda:technical.propose_deadline(db,p,core.case(db,p,case_id,lock=True),data),replay=lambda rid:case_resource(db,p,RepairDeadlineAgreement,rid,case_id))
    return core.out(result)


@router.post('/cases/{case_id}/deadline-agreements/{agreement_id}/decision',dependencies=[Depends(require_permission('repair','update'))])
def decide_deadline(case_id:UUID,agreement_id:UUID,data:DeadlineDecisionIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.dd:'+case_id.hex+agreement_id.hex,payload=data,
        run=lambda:technical.decide_deadline(db,p,core.case(db,p,case_id,lock=True),agreement_id,data),replay=lambda rid:case_resource(db,p,RepairDeadlineAgreement,rid,case_id))
    return core.out(result)


@router.get('/branches/{branch_id}/knowledge')
def knowledge(branch_id:UUID,type_id:UUID|None=None,q:str='',db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return technical.knowledge(db,p,branch_id,type_id,q)


@router.post('/branches/{branch_id}/knowledge',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def create_knowledge(branch_id:UUID,data:KnowledgeIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.knowledge_create:'+str(branch_id),payload=data,
        run=lambda:technical.create_knowledge(db,p,branch_id,data),replay=lambda rid:technical.knowledge_row(db,p,rid))
    return core.out(result)


@router.post('/knowledge/{article_id}/approval',dependencies=[Depends(require_permission('repair','approve'))])
def approve_knowledge(article_id:UUID,data:KnowledgeApprovalIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.knowledge_approve:'+str(article_id),payload=data,
        run=lambda:technical.approve_knowledge(db,p,article_id,data),replay=lambda rid:technical.knowledge_row(db,p,rid))
    return core.out(result)


from app.models.repair_completion import RepairPartAssessment,RepairSupplierClaim,RepairHarvest
from app.schemas.repair_completion import PartAssessmentIn,SupplierClaimIn,SupplierClaimResolutionIn,HarvestIn,HarvestVoidIn,VersionIn
from app.services import repair_supply as supply


@router.get('/cases/{case_id}/supply-records')
def supply_records(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    return {'assessments':[core.out(r) for r in db.query(RepairPartAssessment).filter_by(case_id=case_id).order_by(RepairPartAssessment.created_at.desc()).limit(200)],'claims':[core.out(r) for r in db.query(RepairSupplierClaim).filter_by(case_id=case_id).order_by(RepairSupplierClaim.created_at.desc()).limit(200)]}


@router.post('/cases/{case_id}/parts/{part_id}/assessments',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def assess_part(case_id:UUID,part_id:UUID,data:PartAssessmentIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.pa:'+case_id.hex+part_id.hex,payload=data,run=lambda:supply.assessment(db,p,core.case(db,p,case_id,lock=True),part_id,data),replay=lambda rid:case_resource(db,p,RepairPartAssessment,rid,case_id))
    return core.out(result)


@router.post('/cases/{case_id}/supplier-claims',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def create_supplier_claim(case_id:UUID,data:SupplierClaimIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.supplier_claim:'+str(case_id),payload=data,run=lambda:supply.supplier_claim(db,p,core.case(db,p,case_id,lock=True),data),replay=lambda rid:case_resource(db,p,RepairSupplierClaim,rid,case_id))
    return core.out(result)


@router.post('/cases/{case_id}/supplier-claims/{claim_id}/resolution',dependencies=[Depends(require_permission('repair','approve')),Depends(require_permission('invoices','view'))])
def resolve_supplier_claim(case_id:UUID,claim_id:UUID,data:SupplierClaimResolutionIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.sc:'+case_id.hex+claim_id.hex,payload=data,run=lambda:supply.resolve_claim(db,p,core.case(db,p,case_id,lock=True),claim_id,data),replay=lambda rid:case_resource(db,p,RepairSupplierClaim,rid,case_id))
    return core.out(result)


@router.get('/branches/{branch_id}/harvests',dependencies=[Depends(require_permission('repair_harvest','approve'))])
def harvests(branch_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.branch(db,p,branch_id)
    return [core.out(r) for r in db.query(RepairHarvest).filter_by(branch_id=branch_id).order_by(RepairHarvest.created_at.desc()).limit(200)]


@router.post('/branches/{branch_id}/harvests',status_code=201,dependencies=[Depends(require_permission('repair','update')),Depends(require_permission('inventory','create'))])
def create_harvest(branch_id:UUID,data:HarvestIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.harvest_create:'+str(branch_id),payload=data,run=lambda:supply.create_harvest(db,p,branch_id,data),replay=lambda rid:supply.harvest_row(db,p,rid))
    return core.out(result)


@router.post('/harvests/{harvest_id}/approval',dependencies=[Depends(require_permission('repair_harvest','approve')),Depends(require_permission('inventory','create')),Depends(require_permission('accounting','create'))])
def approve_harvest(harvest_id:UUID,data:VersionIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.harvest_approve:'+str(harvest_id),payload=data,run=lambda:supply.approve_harvest(db,p,supply.harvest_row(db,p,harvest_id,lock=True),data),replay=lambda rid:supply.harvest_row(db,p,rid))
    return core.out(result)


@router.post('/harvests/{harvest_id}/void',dependencies=[Depends(require_permission('repair_harvest','approve')),Depends(require_permission('inventory','create')),Depends(require_permission('accounting','create'))])
def void_harvest(harvest_id:UUID,data:HarvestVoidIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.harvest_void:'+str(harvest_id),payload=data,run=lambda:supply.void_harvest(db,p,supply.harvest_row(db,p,harvest_id,lock=True),data),replay=lambda rid:supply.harvest_row(db,p,rid))
    return core.out(result)


from app.models.repair_completion import RepairParticipation,RepairCustomerFollowup,RepairNotificationPolicy
from app.schemas.repair_completion import ParticipationIn,CustomerFollowupIn,NotificationPolicyIn
from app.services import repair_business as business


@router.get('/cases/{case_id}/participations',dependencies=[Depends(require_permission('repair','approve'))])
def participations(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    return [core.out(r) for r in db.query(RepairParticipation).filter_by(case_id=case_id).order_by(RepairParticipation.created_at.desc()).limit(200)]


@router.post('/cases/{case_id}/work/{work_id}/participation',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def approve_participation(case_id:UUID,work_id:UUID,data:ParticipationIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.wp:'+case_id.hex+work_id.hex,payload=data,run=lambda:business.approve_participation(db,p,core.case(db,p,case_id,lock=True),work_id,data),replay=lambda rid:case_resource(db,p,RepairParticipation,rid,case_id))
    return core.out(result)


@router.get('/cases/{case_id}/customer-followups')
def customer_followups(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    return [core.out(r) for r in db.query(RepairCustomerFollowup).filter_by(case_id=case_id).order_by(RepairCustomerFollowup.created_at.desc()).limit(200)]


@router.post('/cases/{case_id}/customer-followups',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def create_customer_followup(case_id:UUID,data:CustomerFollowupIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.customer_followup:'+str(case_id),payload=data,run=lambda:business.followup(db,p,core.case(db,p,case_id,lock=True),data),replay=lambda rid:case_resource(db,p,RepairCustomerFollowup,rid,case_id))
    return core.out(result)


@router.get('/branches/{branch_id}/notification-policy',dependencies=[Depends(require_permission('repair','approve'))])
def notification_policy(branch_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    result=business.notification_policy(db,p,branch_id)
    return core.out(result) if result else None


@router.post('/branches/{branch_id}/notification-policy',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def save_notification_policy(branch_id:UUID,data:NotificationPolicyIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.notification_policy:'+str(branch_id),payload=data,run=lambda:business.save_notification_policy(db,p,branch_id,data),replay=lambda rid:branch_resource(db,p,RepairNotificationPolicy,rid,branch_id))
    return core.out(result)


from fastapi import UploadFile,Form
from datetime import date
from app.services import repair_exchange as exchange
from app.schemas.repair import VersionIn


@router.get('/history-imports/template.xlsx')
def history_template():
    return Response(exchange.workbook([],exchange.HEADERS),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename="repair-history-template.xlsx"','Cache-Control':'no-store'})


@router.post('/branches/{branch_id}/history-imports',status_code=201,dependencies=[Depends(require_permission('repair','create'))])
async def history_preview(branch_id:UUID,file:UploadFile,source_id:str=Form(...),db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    content=await file.read(5*1024*1024+1)
    return core.out(exchange.preview(db,p,branch_id,source_id,content))


@router.get('/history-imports/{import_id}')
def history_import(import_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return core.out(exchange.import_row(db,p,import_id))


@router.post('/history-imports/{import_id}/commit',dependencies=[Depends(require_permission('repair','create'))])
def history_commit(import_id:UUID,data:VersionIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    result=idempotent(db,request,p.user,operation='repair.history_commit:'+str(import_id),payload=data,run=lambda:exchange.commit(db,p,exchange.import_row(db,p,import_id,True),data.version),replay=lambda rid:exchange.import_row(db,p,rid))
    return core.out(result)


@router.get('/branches/{branch_id}/history')
def historical_records(branch_id:UUID,limit:int=100,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    from app.models.repair_completion import RepairHistoricalRecord
    core.branch(db,p,branch_id)
    return [core.out(r) for r in db.query(RepairHistoricalRecord).filter_by(branch_id=branch_id).order_by(RepairHistoricalRecord.created_at.desc(),RepairHistoricalRecord.id).limit(max(1,min(limit,200)))]


from app.services import repair_onsite as onsite,repair_field as field
from app.schemas.repair_completion import OnsiteActionIn,OnsiteApprovalIn
from app.models.repair_completion import RepairOnsiteAction,RepairOnsiteApproval


@router.get('/service-requests/{request_id}/onsite-actions')
def onsite_actions(request_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    field.request(db,p,request_id)
    rows=db.query(RepairOnsiteAction).filter_by(request_id=request_id).order_by(RepairOnsiteAction.created_at).all()
    result=[]
    for row in rows:
        approval=db.query(RepairOnsiteApproval).filter_by(action_id=row.id,action_version=row.version).one_or_none()
        approved={'id':approval.id,'approver_name':approval.approver_name,'created_at':approval.created_at,'action_version':approval.action_version} if approval else None
        result.append({**core.out(row),'approval':approved})
    return result


@router.get('/service-requests/{request_id}/onsite-approvals/{approval_id}',dependencies=[Depends(require_permission('repair_signatures','view'))])
def onsite_approval_document(request_id:UUID,approval_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    field.request(db,p,request_id)
    row=db.query(RepairOnsiteApproval).filter_by(request_id=request_id,id=approval_id).one_or_none()
    if row is None: raise HTTPException(404,'تأیید پیدا نشد.')
    return core.out(row)


@router.post('/service-requests/{request_id}/appointments/{appointment_id}/actions',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def onsite_action(request_id:UUID,appointment_id:UUID,data:OnsiteActionIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    row=idempotent(db,request,p.user,operation='repair.oa:'+request_id.hex+appointment_id.hex,payload=data,run=lambda:onsite.create(db,p,field.request(db,p,request_id,True),appointment_id,data),replay=lambda rid:onsite.action_row(db,p,request_id,rid))
    return core.out(row)


@router.post('/service-requests/{request_id}/onsite-actions/{action_id}/approval',status_code=201,dependencies=[Depends(require_permission('repair_signatures','create'))])
def onsite_approval(request_id:UUID,action_id:UUID,data:OnsiteApprovalIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    keyed(request)
    def replay(rid):
        onsite.action_row(db,p,request_id,action_id)
        row=db.query(RepairOnsiteApproval).filter_by(id=rid,request_id=request_id,action_id=action_id).one_or_none()
        if row is None: raise HTTPException(404,'تأیید پیدا نشد.')
        return row
    row=idempotent(db,request,p.user,operation='repair.os:'+request_id.hex+action_id.hex,payload=data,run=lambda:onsite.approve(db,p,field.request(db,p,request_id,True),onsite.action_row(db,p,request_id,action_id),data),replay=replay)
    return {'id':row.id,'action_id':row.action_id,'action_version':row.action_version,'approver_name':row.approver_name,'created_at':row.created_at}


@router.get('/exchange.xlsx')
def export_excel(branch_id:UUID|None=None,status:str|None=None,from_date:date|None=None,to_date:date|None=None,technician_id:UUID|None=None,search:str='',financial:bool=False,mine:bool=False,overdue:bool=False,inactive_days:int|None=None,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    from sqlalchemy import or_,func
    from app.models.repair import RepairCase
    from app.services.repair_reports import case_report
    if financial and not (p.has_permission('repair','approve') and p.has_permission('invoices','view')): raise HTTPException(403,'مجوز خروجی مالی ندارید.')
    if from_date and to_date and from_date>to_date: raise HTTPException(422,'بازهٔ تاریخ معتبر نیست.')
    query=core.visible(db,p)
    if mine: query=query.filter(RepairCase.assigned_to_id==p.user.id)
    if overdue: query=query.filter(RepairCase.due_date<date.today(),RepairCase.status.notin_(['closed','delivered','cancelled']))
    if inactive_days:
        from datetime import datetime,timezone,timedelta
        if not 1<=inactive_days<=36500: raise HTTPException(422,'تعداد روز عدم فعالیت معتبر نیست.')
        query=query.filter(RepairCase.updated_at<datetime.now(timezone.utc)-timedelta(days=inactive_days),RepairCase.status.notin_(['closed','delivered','cancelled']))
    if branch_id: core.branch(db,p,branch_id);query=query.filter(RepairCase.branch_id==branch_id)
    if status: query=query.filter(RepairCase.status==status)
    if from_date: query=query.filter(RepairCase.admission_date>=from_date)
    if to_date: query=query.filter(RepairCase.admission_date<=to_date)
    if technician_id: query=query.filter(RepairCase.assigned_to_id==technician_id)
    if search.strip():
        from app.models.repair_completion import RepairCaseDetails
        source,target='يك۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','یک01234567890123456789'
        normalized=search.strip().translate(str.maketrans(source,target))
        needle='%'+normalized.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        def match(column): return func.translate(column,source,target).ilike(needle,escape='\\')
        tests=[match(RepairCase.owner_snapshot[k].astext) for k in ('name','phone')]+[match(RepairCase.device_snapshot[k].astext) for k in ('category','brand','model','serial','imei')]
        tests.append(RepairCase.id.in_(db.query(RepairCaseDetails.case_id).filter(match(RepairCaseDetails.display_number))))
        numeric=normalized[1:] if normalized.startswith('R') else normalized
        if numeric.isdecimal() and len(numeric)<10: tests.append(RepairCase.number==int(numeric))
        if normalized.startswith('cubita:repair:'):
            try: tests.append(RepairCase.id==UUID(normalized.removeprefix('cubita:repair:')))
            except ValueError: pass
        query=query.filter(or_(*tests))
    cases=query.order_by(RepairCase.admission_date,RepairCase.number).limit(2001).all()
    if len(cases)>2000: raise HTTPException(422,'برای خروجی بیش از ۲۰۰۰ پرونده فیلتر محدودتری انتخاب کنید.')
    headers=['شناسه','شماره','پذیرش','موعد','مشتری','دستگاه','وضعیت']
    if financial: headers+=['درآمد خالص اسناد','هزینه قطعات','حاشیه ثبت‌شده','مانده مشتری']
    rows=[]
    for case in cases:
        values=[str(case.id),case.number,case.admission_date.isoformat(),case.due_date.isoformat() if case.due_date else '',case.owner_snapshot['name'],case.device_snapshot['model'],case.status]
        if financial:
            report=case_report(db,p,case,True)['financial'];values += [report[k] for k in ['revenue_net_rial','parts_cost_rial','recorded_margin_rial','remaining_balance_rial']]
        rows.append(values)
    return Response(exchange.workbook(rows,headers),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename="repair.xlsx"','Cache-Control':'no-store'})
