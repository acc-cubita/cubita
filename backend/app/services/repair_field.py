"""درخواست خدمت و ظرفیت واقعی تقویم؛ هیچ هزینه‌ای با صرف برنامه‌ریزی ثبت نمی‌شود."""
from datetime import datetime, timezone
from fastapi import HTTPException
from app.models.inventory import Contact
from app.models.tenant import Membership
from app.models.repair import RepairServiceRequest, RepairTechnicianSkill, RepairAppointment, RepairFieldEvent, RepairDevice
from app.services import repair as core


def visible(db,p):
    return db.query(RepairServiceRequest).filter(RepairServiceRequest.branch_id.in_(core.branch_query(db,p).with_entities(core.RepairBranch.id)))


def request(db,p,rid,lock=False):
    query=visible(db,p).filter_by(id=rid)
    if lock: query=query.with_for_update().populate_existing()
    row=query.one_or_none()
    if row is None: raise HTTPException(404,'درخواست خدمت در دسترس نیست.')
    return row


def event(db,p,row,action,detail):
    row.version+=1;db.add(RepairFieldEvent(request_id=row.id,actor_id=p.user.id,action=action,detail=detail));db.flush()


def create(db,p,data):
    branch=core.branch(db,p,data.branch_id)
    if not branch.is_active: raise HTTPException(422,'شعبهٔ فعال انتخاب کنید.')
    contact=db.get(Contact,data.contact_id)
    if contact is None or not contact.is_active or contact.is_system: raise HTTPException(422,'طرف حساب فعال انتخاب کنید.')
    core.device_type(db,data.type_id)
    row=RepairServiceRequest(**data.model_dump(),created_by_id=p.user.id);db.add(row);db.flush()
    db.add(RepairFieldEvent(request_id=row.id,actor_id=p.user.id,action='requested',detail={'device':row.device_description}));db.flush()
    return row


def skills(db,p,uid,data):
    member=db.query(Membership).filter_by(tenant_id=p.tenant_id,user_id=uid,status='active').with_for_update(of=Membership).one_or_none()
    if member is None: raise HTTPException(422,'تکنسین فعال همین کسب‌وکار را انتخاب کنید.')
    for tid in set(data.type_ids): core.device_type(db,tid)
    db.query(RepairTechnicianSkill).filter_by(technician_id=uid).delete(synchronize_session=False)
    db.add_all([RepairTechnicianSkill(technician_id=uid,type_id=tid) for tid in set(data.type_ids)]);db.flush()


def schedule(db,p,row,data):
    core.check_version(row,data.version)
    if row.status!='open': raise HTTPException(409,'درخواست پایان‌یافته قابل برنامه‌ریزی نیست.')
    try:
        start=datetime.fromisoformat(data.starts_at);end=datetime.fromisoformat(data.ends_at)
        if start.tzinfo is None or end.tzinfo is None or end<=start or (end-start).total_seconds()>24*3600: raise ValueError()
    except ValueError: raise HTTPException(422,'زمان شروع و پایان با منطقهٔ زمانی و مدت حداکثر یک روز لازم است.')
    if data.technician_id not in {t['id'] for t in core.technicians(db,p,row.branch_id)}:
        raise HTTPException(422,'تکنسین فعال و مجاز همین شعبه را انتخاب کنید.')
    # قفل عضویت، برنامه‌ریزی دو درخواست متفاوت برای یک تکنسین را سری می‌کند.
    db.query(Membership.id).filter_by(tenant_id=p.tenant_id,user_id=data.technician_id).with_for_update(of=Membership).one()
    if not db.query(RepairTechnicianSkill).filter_by(technician_id=data.technician_id,type_id=row.type_id).first():
        raise HTTPException(422,'تخصص این نوع دستگاه برای تکنسین ثبت نشده است.')
    conflict=db.query(RepairAppointment).filter(RepairAppointment.technician_id==data.technician_id,RepairAppointment.status.in_(['scheduled','dispatched','onsite']),RepairAppointment.starts_at<end,RepairAppointment.ends_at>start).first()
    if conflict: raise HTTPException(409,'تکنسین در این بازه نوبت فعال دیگری دارد؛ زمان یا تکنسین را تغییر دهید.')
    if db.query(RepairAppointment).filter(RepairAppointment.request_id==row.id,RepairAppointment.status.in_(['scheduled','dispatched','onsite'])).first():
        raise HTTPException(409,'این درخواست نوبت فعال دارد؛ ابتدا آن را تعیین تکلیف کنید.')
    appointment=RepairAppointment(request_id=row.id,technician_id=data.technician_id,starts_at=start,ends_at=end,created_by_id=p.user.id)
    db.add(appointment);db.flush();event(db,p,row,'scheduled',{'appointment_id':str(appointment.id),'starts_at':start.isoformat(),'ends_at':end.isoformat(),'technician_id':str(data.technician_id)})
    return appointment


def appointment_status(db,p,row,appointment,data):
    core.check_version(row,data.version)
    manager=p.has_permission('repair','approve')
    if appointment.technician_id!=p.user.id and not manager: raise HTTPException(403,'فقط تکنسین این نوبت یا مدیر می‌تواند نتیجه را ثبت کند.')
    transitions={'scheduled':{'dispatched','cancelled'},'dispatched':{'onsite','cancelled'},'onsite':{'completed'}}
    if data.status not in transitions.get(appointment.status,set()): raise HTTPException(409,'این تغییر وضعیت نوبت مجاز نیست.')
    before=appointment.status;appointment.status=data.status;appointment.result=data.result
    if data.status=='onsite': appointment.arrived_at=datetime.now(timezone.utc)
    if data.status=='completed':
        appointment.completed_at=datetime.now(timezone.utc)
        row.status='completed'
    event(db,p,row,'appointment_'+data.status,{'appointment_id':str(appointment.id),'from':before,'result':data.result})
    return appointment


def admit(db,p,row,data):
    core.check_version(row,data.version)
    if row.case_id: raise HTTPException(409,'این درخواست قبلاً به پذیرش وصل شده است.')
    admission=data.admission
    if admission.contact_id!=row.contact_id or admission.branch_id!=row.branch_id:
        raise HTTPException(422,'مالک و شعبهٔ پذیرش باید با درخواست خدمت یکسان باشند.')
    device=db.get(RepairDevice,admission.device_id) if admission.device_id else None
    if admission.device_id and device is None: raise HTTPException(404,'دستگاه در دسترس نیست.')
    type_id=device.type_id if device else admission.device.type_id
    if type_id!=row.type_id: raise HTTPException(422,'نوع دستگاه پذیرش با درخواست خدمت یکسان نیست.')
    from app.models.repair import RepairMaintenanceVisit,RepairMaintenancePlan
    visit=db.query(RepairMaintenanceVisit).filter_by(request_id=row.id).one_or_none()
    plan=db.get(RepairMaintenancePlan,visit.plan_id) if visit else None
    if plan and admission.device_id!=plan.device_id: raise HTTPException(422,'پذیرش سرویس دوره‌ای باید به همان دستگاه تحت پوشش وصل شود.')
    case=core.create(db,p,admission);row.case_id=case.id
    if plan:
        from app.services.repair_contracts import bind
        from app.schemas.repair import ContractCaseIn
        bind(db,p,case,ContractCaseIn(version=case.version,contract_id=plan.contract_id,service_date=admission.admission_date,
            allocated_minutes=plan.allocated_minutes,covered_value_rial=plan.covered_value_rial))
    event(db,p,row,'admitted',{'case_id':str(case.id),'number':case.number})
    core.event(db,p,case,'field_request_linked',{'request_id':str(row.id)})
    return case


def projection(db,row):
    result=core.out(row)
    from app.models.repair import RepairMaintenanceVisit,RepairMaintenancePlan
    visit=db.query(RepairMaintenanceVisit).filter_by(request_id=row.id).one_or_none()
    plan=db.get(RepairMaintenancePlan,visit.plan_id) if visit else None
    result['maintenance_device_id']=plan.device_id if plan else None
    result['appointments']=[core.out(a) for a in db.query(RepairAppointment).filter_by(request_id=row.id).order_by(RepairAppointment.starts_at.desc()).limit(200)]
    result['events']=[core.out(e) for e in db.query(RepairFieldEvent).filter_by(request_id=row.id).order_by(RepairFieldEvent.created_at.desc()).limit(200)]
    return result
