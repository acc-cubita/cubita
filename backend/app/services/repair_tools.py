"""Versioned technical records; no stock or financial postings."""
from datetime import datetime,timezone
from decimal import Decimal
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import or_
from app.models.inventory import Item
from app.models.repair import RepairBranch,RepairDevice,RepairCase,RepairEstimate
from app.models.repair_completion import RepairServiceProfile,RepairTypeProtocol,RepairDiagnosticRecord,RepairSupervisorReview,RepairWorkPause,RepairDeadlineAgreement,RepairKnowledgeArticle
from app.services import repair as core
from app.services.repair_completion import ENDED


def lock_branch(db,p,branch_id):
    core.branch(db,p,branch_id)
    db.query(RepairBranch).filter_by(id=branch_id).with_for_update().one()


def editable(row,version):
    core.check_version(row,version)
    if row.status in ENDED: raise HTTPException(409,'پروندهٔ پایان‌یافته بازنویسی نمی‌شود.')


def service_profiles(db,p,branch_id):
    core.branch(db,p,branch_id)
    rows=db.query(RepairServiceProfile).filter_by(branch_id=branch_id).order_by(RepairServiceProfile.service_id,RepairServiceProfile.revision.desc()).distinct(RepairServiceProfile.service_id).limit(200).all()
    result=[]
    for row in rows:
        item=db.get(Item,row.service_id)
        if item and item.is_active and item.is_service:
            result.append({**core.out(row),'service_name':item.name})
    return result


def save_service_profile(db,p,branch_id,data):
    lock_branch(db,p,branch_id)
    item=db.get(Item,data.service_id)
    if item is None or not item.is_active or not item.is_service: raise HTTPException(422,'خدمت فعال را از کالاهای خدماتی انتخاب کنید.')
    old=db.query(RepairServiceProfile).filter_by(branch_id=branch_id,service_id=data.service_id).order_by(RepairServiceProfile.revision.desc()).first()
    if (old.revision if old else 0)!=data.previous_revision: raise HTTPException(409,'تنظیم خدمت تغییر کرده؛ نسخهٔ تازه را دریافت کنید.')
    row=RepairServiceProfile(branch_id=branch_id,revision=data.previous_revision+1,recorded_by_id=p.user.id,**data.model_dump(exclude={'previous_revision'}))
    db.add(row);db.flush();return row


def protocol(db,p,branch_id,type_id):
    core.branch(db,p,branch_id)
    from app.models.repair import RepairDeviceType
    if db.get(RepairDeviceType,type_id) is None: raise HTTPException(404,'نوع دستگاه پیدا نشد.')
    return db.query(RepairTypeProtocol).filter_by(branch_id=branch_id,type_id=type_id).order_by(RepairTypeProtocol.revision.desc()).first()


def save_protocol(db,p,branch_id,data):
    lock_branch(db,p,branch_id);core.device_type(db,data.type_id)
    old=protocol(db,p,branch_id,data.type_id)
    if (old.revision if old else 0)!=data.previous_revision: raise HTTPException(409,'دستور اندازه‌گیری تغییر کرده؛ نسخهٔ تازه را دریافت کنید.')
    row=RepairTypeProtocol(branch_id=branch_id,type_id=data.type_id,revision=data.previous_revision+1,metrics=[m.model_dump(mode='json') for m in data.metrics],checklist=data.checklist,requires_supervisor_review=data.requires_supervisor_review,recorded_by_id=p.user.id)
    db.add(row);db.flush();return row


def diagnostic(db,p,row,data):
    editable(row,data.version)
    device=db.get(RepairDevice,row.device_id)
    latest=protocol(db,p,row.branch_id,device.type_id)
    if (latest.id if latest else None)!=data.protocol_id: raise HTTPException(409,'دستور اندازه‌گیری عوض شده؛ فرم را تازه کنید.')
    native_type=core.device_type(db,device.type_id)
    definitions=latest.metrics if latest else []
    checks=latest.checklist if latest else native_type.diagnostic_checklist
    values={value.key:value.value for value in data.measurements}
    keys={metric['key'] for metric in definitions}
    if not set(values).issubset(keys) or any(metric['required'] and metric['key'] not in values for metric in definitions):
        raise HTTPException(422,'اندازه‌گیری‌های الزامی دستور همین نوع دستگاه را تکمیل کنید.')
    if set(data.checklist)!=set(checks): raise HTTPException(422,'همهٔ موارد چک‌لیست همین نسخه را بررسی کنید.')
    measurements=[];failed=any(not value for value in data.checklist.values())
    for metric in definitions:
        if metric['key'] not in values: continue
        value=values[metric['key']]
        passed=(metric['minimum'] is None or value>=Decimal(metric['minimum'])) and (metric['maximum'] is None or value<=Decimal(metric['maximum']))
        failed=failed or not passed
        measurements.append({'key':metric['key'],'title':metric['title'],'unit':metric['unit'],'value':str(value),'minimum':metric['minimum'],'maximum':metric['maximum'],'passed':passed})
    if failed and not data.test_failure_reason: raise HTTPException(422,'علت شکست آزمون را ثبت کنید.')
    old=db.query(RepairDiagnosticRecord).filter_by(case_id=row.id).order_by(RepairDiagnosticRecord.revision.desc()).first()
    result=RepairDiagnosticRecord(case_id=row.id,protocol_id=latest.id if latest else None,revision=(old.revision if old else 0)+1,work_version=row.work_version,
        protocol_snapshot={'type_id':str(device.type_id),'revision':latest.revision if latest else 0,'metrics':definitions,'checklist':checks,'requires_supervisor_review':latest.requires_supervisor_review if latest else False},measurements=measurements,checklist=data.checklist,root_cause=data.root_cause,test_failure_reason=data.test_failure_reason,recorded_by_id=p.user.id)
    db.add(result);db.flush();core.event(db,p,row,'diagnostic_recorded',{'diagnostic_id':str(result.id),'revision':result.revision,'failed':failed})
    return result


def review(db,p,row,data):
    editable(row,data.version)
    record=db.query(RepairDiagnosticRecord).filter_by(id=data.diagnostic_id,case_id=row.id).one_or_none()
    if record is None: raise HTTPException(404,'اندازه‌گیری مربوط به این پرونده پیدا نشد.')
    if db.query(RepairSupervisorReview.id).filter_by(diagnostic_id=record.id).first(): raise HTTPException(409,'این نسخه قبلاً بازبینی شده؛ بازبینی قبلی بازنویسی نمی‌شود.')
    latest=db.query(RepairDiagnosticRecord).filter_by(case_id=row.id).order_by(RepairDiagnosticRecord.revision.desc()).first()
    if data.approved and (latest.id!=record.id or record.work_version!=row.work_version): raise HTTPException(409,'تشخیص یا کار عوض شده؛ نسخهٔ تازه را بازبینی کنید.')
    result=RepairSupervisorReview(case_id=row.id,diagnostic_id=record.id,approved=data.approved,reason=data.reason,reviewed_by_id=p.user.id)
    db.add(result);db.flush();core.event(db,p,row,'diagnostic_reviewed',{'review_id':str(result.id),'diagnostic_id':str(record.id),'approved':result.approved})
    return result


def assert_reviewed(db,row):
    if db.query(RepairWorkPause.id).filter_by(case_id=row.id,ended_at=None).first():
        raise HTTPException(409,'پیش از آمادهٔ تحویل کردن، توقف فعال کار را پایان دهید.')
    record=db.query(RepairDiagnosticRecord).filter_by(case_id=row.id).order_by(RepairDiagnosticRecord.revision.desc()).first()
    if record and record.protocol_snapshot.get('requires_supervisor_review'):
        approved=db.query(RepairSupervisorReview).filter_by(diagnostic_id=record.id,approved=True).one_or_none()
        if approved is None or record.work_version!=row.work_version:
            raise HTTPException(409,'تشخیص همین نسخهٔ کار نیازمند تأیید سرپرست است.')


def start_pause(db,p,row,data):
    editable(row,data.version)
    if db.query(RepairWorkPause.id).filter_by(case_id=row.id,ended_at=None).first(): raise HTTPException(409,'توقف فعال پرونده را ابتدا پایان دهید.')
    result=RepairWorkPause(case_id=row.id,reason=data.reason,started_at=datetime.now(timezone.utc),recorded_by_id=p.user.id)
    db.add(result);db.flush();core.event(db,p,row,'work_paused',{'pause_id':str(result.id),'reason':result.reason})
    return result


def end_pause(db,p,row,pause_id,data):
    core.check_version(row,data.version)
    pause=db.query(RepairWorkPause).filter_by(id=pause_id,case_id=row.id).with_for_update().one_or_none()
    if pause is None: raise HTTPException(404,'توقف پرونده پیدا نشد.')
    core.check_version(pause,data.pause_version)
    if pause.ended_at is not None: raise HTTPException(409,'توقف قبلاً پایان یافته است.')
    pause.ended_at=datetime.now(timezone.utc);pause.ended_by_id=p.user.id;pause.end_reason=data.end_reason;pause.version+=1
    core.event(db,p,row,'work_resumed',{'pause_id':str(pause.id),'reason':pause.end_reason})
    return pause


def pause_out(row):
    return {**core.out(row),'duration_seconds':max(0,int(((row.ended_at or datetime.now(timezone.utc))-row.started_at).total_seconds()))}


def propose_deadline(db,p,row,data):
    editable(row,data.version)
    if data.new_due_date<row.admission_date: raise HTTPException(422,'موعد تازه نمی‌تواند پیش از پذیرش باشد.')
    if db.query(RepairDeadlineAgreement.id).filter_by(case_id=row.id,status='pending').first(): raise HTTPException(409,'ابتدا پیشنهاد موعد قبلی را تعیین تکلیف کنید.')
    estimate=None
    if data.estimate_id:
        estimate=db.query(RepairEstimate).filter_by(case_id=row.id).order_by(RepairEstimate.version.desc()).first()
        if estimate is None or estimate.id!=data.estimate_id: raise HTTPException(409,'تغییر هزینه باید به آخرین نسخهٔ برآورد همین پرونده متصل باشد.')
    result=RepairDeadlineAgreement(case_id=row.id,old_due_date=row.due_date,new_due_date=data.new_due_date,estimate_id=estimate.id if estimate else None,estimate_revision=estimate.version if estimate else None,reason=data.reason,recorded_by_id=p.user.id)
    db.add(result);db.flush();core.event(db,p,row,'deadline_proposed',{'agreement_id':str(result.id),'new_due_date':result.new_due_date.isoformat()})
    return result


def decide_deadline(db,p,row,agreement_id,data):
    editable(row,data.version)
    agreement=db.query(RepairDeadlineAgreement).filter_by(id=agreement_id,case_id=row.id).with_for_update().one_or_none()
    if agreement is None: raise HTTPException(404,'پیشنهاد موعد پیدا نشد.')
    core.check_version(agreement,data.agreement_version)
    if agreement.status!='pending': raise HTTPException(409,'توافق قبلاً تعیین تکلیف شده و بازنویسی نمی‌شود.')
    if data.decision=='accepted':
        if row.due_date!=agreement.old_due_date: raise HTTPException(409,'موعد پرونده تغییر کرده؛ توافق تازه لازم است.')
        if agreement.estimate_id:
            estimate,_=core.approved_estimate(db,row)
            if estimate.id!=agreement.estimate_id or estimate.version!=agreement.estimate_revision:
                raise HTTPException(409,'برآورد تغییر هزینه باید جداگانه و با همین نسخه تأیید شده باشد.')
        row.due_date=agreement.new_due_date
    agreement.status=data.decision;agreement.customer_name=data.customer_name;agreement.approval_method=data.method;agreement.decision_reason=data.reason
    agreement.decided_at=datetime.now(timezone.utc);agreement.decided_by_id=p.user.id;agreement.version+=1
    core.event(db,p,row,'deadline_'+data.decision,{'agreement_id':str(agreement.id),'customer_name':data.customer_name,'method':data.method})
    return agreement


def knowledge_row(db,p,article_id):
    row=db.get(RepairKnowledgeArticle,article_id)
    if row is None: raise HTTPException(404,'نسخهٔ دانش پیدا نشد.')
    core.branch(db,p,row.branch_id)
    if row.approved_at is None and row.recorded_by_id!=p.user.id and not p.has_permission('repair','approve'):
        raise HTTPException(404,'نسخهٔ دانش پیدا نشد.')
    return row


def create_knowledge(db,p,branch_id,data):
    lock_branch(db,p,branch_id);core.device_type(db,data.type_id)
    family=data.family_id or uuid4()
    previous=db.query(RepairKnowledgeArticle).filter_by(branch_id=branch_id,family_id=family).order_by(RepairKnowledgeArticle.revision.desc()).first()
    if (previous.revision if previous else 0)!=data.previous_revision: raise HTTPException(409,'نسخهٔ دانش تغییر کرده؛ تاریخچهٔ تازه را دریافت کنید.')
    if previous and previous.type_id!=data.type_id: raise HTTPException(422,'نوع دستگاه در یک خانوادهٔ دانش تغییر نمی‌کند.')
    row=RepairKnowledgeArticle(branch_id=branch_id,family_id=family,revision=data.previous_revision+1,recorded_by_id=p.user.id,**data.model_dump(exclude={'family_id','previous_revision'}))
    db.add(row);db.flush();return row


def approve_knowledge(db,p,article_id,data):
    row=knowledge_row(db,p,article_id)
    lock_branch(db,p,row.branch_id)
    db.refresh(row);core.check_version(row,data.version)
    if row.approved_at is not None: raise HTTPException(409,'این نسخه قبلاً تأیید شده است.')
    row.approved_at=datetime.now(timezone.utc);row.approved_by_id=p.user.id;row.version+=1;db.flush()
    return row


def knowledge(db,p,branch_id,type_id=None,q=''):
    core.branch(db,p,branch_id)
    query=db.query(RepairKnowledgeArticle).filter_by(branch_id=branch_id)
    if not p.has_permission('repair','approve'): query=query.filter(or_(RepairKnowledgeArticle.approved_at.isnot(None),RepairKnowledgeArticle.recorded_by_id==p.user.id))
    if type_id: query=query.filter_by(type_id=type_id)
    rows=query.order_by(RepairKnowledgeArticle.created_at.desc()).limit(200).all()
    normalized=q.strip().translate(str.maketrans('يك','یک')).casefold()
    return [core.out(r) for r in rows if not normalized or normalized in '\n'.join((r.title,r.symptoms,r.root_cause,r.solution)).translate(str.maketrans('يك','یک')).casefold()]


def similar_cases(db,p,row):
    query=core.visible(db,p).filter(RepairCase.id!=row.id,RepairCase.branch_id==row.branch_id,RepairCase.device_snapshot['category'].astext==row.device_snapshot['category'])
    candidates=query.order_by(RepairCase.updated_at.desc()).limit(100).all()
    ranked=[]
    for candidate in candidates:
        shared=set(row.fault_ids or [])&set(candidate.fault_ids or [])
        score=len(shared)*3+int(candidate.device_snapshot.get('model')==row.device_snapshot.get('model'))
        if score:
            ranked.append({'id':candidate.id,'number':candidate.number,'score':score,'device_model':candidate.device_snapshot.get('model',''),'final_diagnosis':candidate.final_diagnosis})
    return sorted(ranked,key=lambda record:(-record['score'],-record['number']))[:20]
