"""تکمیل پذیرش با همان چرخه و همان مراجع مالی/انبار منتشرشده."""
import hashlib
import json
from decimal import Decimal
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from app.models.tenant import Membership
from app.models.inventory import Contact
from app.models.repair import RepairCase, RepairBranch, RepairTechnicianSkill, RepairDelivery
from app.models.repair_completion import RepairBranchSettings, RepairCaseDetails, RepairIntakeBatch, RepairTechnicianCapacity, RepairAcknowledgment, RepairBulkOperation
from app.schemas.repair import AdmissionIn, AssignmentIn
from app.services import repair as core
from app.services.printing import gregorian_to_jalali

ENDED={'cancelled','delivered','closed','unrepairable'}
ORG={'organization_unit','representative','organization_order','representative_contact_id','organization_unit_contact_id'}
PERSON_FIELDS={'representative_contact_id':'representative','organization_unit_contact_id':'organization_unit'}


def person_name(db,contact_id):
    person=db.get(Contact,contact_id)
    if person is None or not person.is_active or person.is_system:
        raise HTTPException(422,'نماینده و واحد سازمانی را از اشخاص فعال همین شرکت انتخاب کنید.')
    return person.name


def settings(db,p,branch_id,*,lock=False):
    core.branch(db,p,branch_id)
    q=db.query(RepairBranchSettings).filter_by(branch_id=branch_id)
    return (q.with_for_update() if lock else q).one_or_none()


def save_settings(db,p,branch_id,data):
    core.branch(db,p,branch_id)
    db.query(RepairBranch.id).filter_by(id=branch_id).with_for_update().one()
    row=settings(db,p,branch_id,lock=True)
    if (row.version if row else 0)!=data.version:
        raise HTTPException(409,'تنظیمات شعبه تغییر کرده؛ آن را تازه کنید.')
    values=data.model_dump(exclude={'version'})
    if row is None:
        row=RepairBranchSettings(branch_id=branch_id,**values);db.add(row)
    else:
        for key,value in values.items(): setattr(row,key,value)
        row.version+=1
    db.flush()
    return row


def metadata(db,row,*,create=False):
    result=db.query(RepairCaseDetails).filter_by(case_id=row.id).one_or_none()
    if result is None and create:
        result=RepairCaseDetails(case_id=row.id,display_number=str(row.number));db.add(result);db.flush()
    return result


def register_admission(db,p,row):
    config=settings(db,p,row.branch_id,lock=True)
    meta=metadata(db,row,create=True)
    if config:
        meta.settings_snapshot=jsonable_encoder(core.out(config))
        meta.display_number=config.number_format.format(branch=config.code,year=gregorian_to_jalali(row.admission_date)[0],number=row.number)
    db.flush()
    return meta


def quick(db,p,data,*,batch_id=None):
    people={name:person_name(db,getattr(data,field)) for field,name in PERSON_FIELDS.items() if getattr(data,field)}
    values=data.model_dump(exclude=ORG)
    config=settings(db,p,data.branch_id,lock=True)
    for field,default in (('storage_location','default_location'),('terms','terms')):
        if not values[field]:
            if config is None:
                raise HTTPException(409,'برای پذیرش سریع، مدیر باید محل و شرایط شعبه را تنظیم کند؛ یا فرم کامل را پر کنید.')
            values[field]=getattr(config,default)
    row=core.create(db,p,AdmissionIn.model_validate(values))
    meta=metadata(db,row,create=True)
    meta.batch_id=batch_id
    for field in ORG: setattr(meta,field,getattr(data,field))
    for name,value in people.items(): setattr(meta,name,value)
    db.flush()
    return row


def batch(db,p,data):
    with db.begin_nested():
        result=RepairIntakeBatch(contact_id=data.contact_id,created_by_id=p.user.id)
        db.add(result);db.flush()
        for intake in data.admissions: quick(db,p,intake,batch_id=result.id)
    return result


def batch_result(db,p,batch_id):
    group=db.get(RepairIntakeBatch,batch_id)
    if group is None: raise HTTPException(404,'پذیرش گروهی پیدا نشد.')
    rows=core.visible(db,p).join(RepairCaseDetails,RepairCaseDetails.case_id==RepairCase.id).filter(RepairCaseDetails.batch_id==batch_id).order_by(RepairCase.number).all()
    if not rows: raise HTTPException(404,'پذیرش گروهی پیدا نشد.')
    return {'id':group.id,'items':[core.detail(db,p,r) for r in rows]}


def amend(db,p,row,data):
    core.check_version(row,data.version)
    if row.status in ENDED: raise HTTPException(409,'جزئیات پذیرش پروندهٔ پایان‌یافته بازنویسی نمی‌شود.')
    values=data.model_dump(exclude={'version'},exclude_unset=True)
    if any(value is None and field not in PERSON_FIELDS for field,value in values.items()):
        raise HTTPException(422,'برای خالی‌کردن فیلد، متن خالی بفرستید.')
    people={field:person_name(db,value) for field,value in values.items() if field in PERSON_FIELDS and value is not None}
    meta=metadata(db,row,create=True)
    changes={}
    for field,value in values.items():
        target=meta if field in ORG else row
        if getattr(target,field)!=value:
            changes[field]={'before':getattr(target,field),'after':value}
            setattr(target,field,value)
        if field in PERSON_FIELDS and value is not None:
            name=PERSON_FIELDS[field];snapshot=people[field]
            if getattr(meta,name)!=snapshot:
                changes[name]={'before':getattr(meta,name),'after':snapshot};setattr(meta,name,snapshot)
    if changes:
        meta.receipt_revision+=1
        core.event(db,p,row,'intake_details_amended',jsonable_encoder({'changes':changes,'receipt_revision':meta.receipt_revision}))
    return row


def save_capacity(db,p,user_id,data):
    member=db.query(Membership).filter_by(tenant_id=p.tenant_id,user_id=user_id,status='active').with_for_update().one_or_none()
    if member is None: raise HTTPException(422,'تکنسین عضو فعال همین شرکت نیست.')
    row=db.query(RepairTechnicianCapacity).filter_by(technician_id=user_id).with_for_update().one_or_none()
    if (row.version if row else 0)!=data.version: raise HTTPException(409,'ظرفیت تغییر کرده؛ آن را تازه کنید.')
    if row is None:
        row=RepairTechnicianCapacity(technician_id=user_id,max_active_cases=data.max_active_cases);db.add(row)
    else: row.max_active_cases=data.max_active_cases;row.version+=1
    db.flush()
    return row


def workload(db,user_id,*,exclude=None):
    q=db.query(RepairCase).filter(RepairCase.assigned_to_id==user_id,RepairCase.status.notin_(ENDED))
    if exclude: q=q.filter(RepairCase.id!=exclude)
    return q.count()


def check_capacity(db,p,row,data):
    if not data.user_id: return
    db.query(Membership).filter_by(tenant_id=p.tenant_id,user_id=data.user_id).with_for_update().one()
    limit=db.query(RepairTechnicianCapacity).filter_by(technician_id=data.user_id).one_or_none()
    count=workload(db,data.user_id,exclude=row.id)
    if limit and limit.max_active_cases is not None and count>=limit.max_active_cases:
        if not data.capacity_override or not p.has_permission('repair','approve'):
            raise HTTPException(409,'ظرفیت پرونده‌های تکنسین کامل است؛ تکنسین دیگری انتخاب کنید یا استثنای مستند مدیر بگیرید.')
        core.event(db,p,row,'capacity_override',{'technician_id':str(data.user_id),'active_cases':count,'limit':limit.max_active_cases,'reason':data.reason})


def suggestions(db,p,branch_id,type_id=None):
    core.branch(db,p,branch_id)
    result=[]
    for person in core.technicians(db,p,branch_id):
        policy=db.query(RepairTechnicianCapacity).filter_by(technician_id=person['id']).one_or_none()
        active=workload(db,person['id'])
        skilled=bool(type_id and db.query(RepairTechnicianSkill.id).filter_by(technician_id=person['id'],type_id=type_id).first())
        maximum=policy.max_active_cases if policy else None
        result.append({**person,'active_cases':active,'max_active_cases':maximum,'capacity_version':policy.version if policy else 0,'has_skill':skilled,'available':maximum is None or active<maximum})
    return sorted(result,key=lambda r:(not r['has_skill'],not r['available'],r['active_cases'],r['name']))


def document(db,row,kind):
    meta=metadata(db,row)
    if kind=='intake':
        return (meta.receipt_revision if meta else 1),jsonable_encoder({'number':meta.display_number if meta else str(row.number),'owner':row.owner_snapshot,'device':row.device_snapshot,'reported_issue':row.reported_issue,'appearance':row.appearance,'accessories':row.accessories,'terms':row.terms,'delivering_name':row.delivering_name,'admission_date':row.admission_date})
    delivered=db.query(RepairDelivery).filter_by(case_id=row.id).one_or_none()
    if delivered is None: raise HTTPException(409,'ابتدا تحویل واقعی با کنترل مالی ثبت شود؛ امضا جای تحویل نیست.')
    return 1,jsonable_encoder(core.out(delivered))


def acknowledge(db,p,row,data):
    core.check_version(row,data.version)
    revision,snapshot=document(db,row,data.kind)
    existing=db.query(RepairAcknowledgment).filter_by(case_id=row.id,kind=data.kind,document_revision=revision).one_or_none()
    if existing: raise HTTPException(409,'این نسخهٔ سند قبلاً تأیید شده؛ امضا بازنویسی نمی‌شود.')
    result=RepairAcknowledgment(case_id=row.id,kind=data.kind,document_revision=revision,signer_name=data.signer_name,signer_relation=data.signer_relation,
        strokes=jsonable_encoder(data.strokes),document_snapshot=snapshot,document_hash=hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),confirmed_by_id=p.user.id)
    db.add(result);db.flush()
    core.event(db,p,row,'document_acknowledged',{'acknowledgment_id':str(result.id),'kind':data.kind,'revision':revision,'signer_name':data.signer_name})
    return result


def bulk(db,p,data):
    result=RepairBulkOperation(action=data.action,created_by_id=p.user.id)
    db.add(result);db.flush()
    responses=[]
    # هر ردیف savepoint خود را دارد؛ خطای یک پرونده کارهای موفق قبلی را برنمی‌گرداند.
    for item in sorted(data.cases,key=lambda c:str(c.case_id)):
        try:
            with db.begin_nested():
                row=core.case(db,p,item.case_id,lock=True)
                core.check_version(row,item.version)
                if data.action=='assign':
                    if not p.has_permission('repair','update'): raise HTTPException(403,'دسترسی تخصیص تعمیرگاه لازم است.')
                    core.assign(db,p,row,AssignmentIn(version=item.version,user_id=data.technician_id,reason=data.reason,capacity_override=data.capacity_override))
                    info={'version':row.version}
                else:
                    if not p.has_permission('repair','approve'): raise HTTPException(403,'دسترسی مدیریت اعلان لازم است.')
                    if data.notification_event=='ready' and row.status!='ready': raise HTTPException(409,'اعلان آمادهٔ تحویل فقط برای پروندهٔ آماده است.')
                    if data.notification_event=='approval' and row.status!='awaiting_customer': raise HTTPException(409,'پرونده در انتظار تأیید مشتری نیست.')
                    from app.services.repair_notifications import enqueue
                    message=enqueue(db,row,data.notification_event,'bulk:'+str(result.id),strict=True)
                    if message is None: raise HTTPException(409,'الگوی فعال اعلان پیدا نشد؛ تنظیم اعلان را کامل کنید.')
                    core.event(db,p,row,'bulk_notification_queued',{'notification_id':str(message.id),'reason':data.reason})
                    info={'notification_id':str(message.id),'status':message.status,'version':row.version}
                responses.append({'case_id':str(item.case_id),'ok':True,**info})
        except HTTPException as exc:
            responses.append({'case_id':str(item.case_id),'ok':False,'status_code':exc.status_code,'error':exc.detail})
    result.results=responses;db.flush()
    return result
