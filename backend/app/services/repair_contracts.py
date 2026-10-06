"""پوشش تاریخ‌دار و سهمیه قرارداد؛ سهمیه دفتر مالی نیست."""
from datetime import date,datetime,timezone,timedelta
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import func
from app.models.tenant import Tenant
from app.models.inventory import Contact
from app.models.repair import RepairMaintenanceContract,RepairContractDevice,RepairContractCase,RepairWork,RepairWarrantyClaim,RepairMaintenancePlan,RepairMaintenanceVisit,RepairAppointment,RepairQualityCheck,RepairConsolidatedBill,RepairConsolidatedBillMember,RepairDevice,RepairCase
from app.schemas.repair import ServiceRequestIn,ContractCaseIn,RepairInvoiceIn
from app.services import repair as core,repair_field,repair_finance


def create(db,p,data):
    db.query(Tenant.id).filter_by(id=p.tenant_id).with_for_update(of=Tenant).one()
    contact=db.get(Contact,data.contact_id)
    if contact is None or not contact.is_active or contact.is_system: raise HTTPException(422,'طرف حساب فعال قرارداد را انتخاب کنید.')
    prior=db.query(RepairMaintenanceContract).filter_by(code=data.code).order_by(RepairMaintenanceContract.version.desc()).first()
    if prior and prior.contact_id!=data.contact_id: raise HTTPException(409,'مالک قرارداد در نسخهٔ جدید تغییر نمی‌کند؛ کد قرارداد مستقل لازم است.')
    ids=set(data.device_ids)
    owned={r[0] for r in core.visible(db,p).filter(RepairCase.contact_id==data.contact_id,RepairCase.device_id.in_(ids)).with_entities(RepairCase.device_id).all()}
    if ids!=owned: raise HTTPException(422,'دستگاه‌های قرارداد باید سابقهٔ پذیرش قابل دسترس برای همین مالک داشته باشند.')
    contract=RepairMaintenanceContract(**data.model_dump(exclude={'device_ids'}),version=prior.version+1 if prior else 1,created_by_id=p.user.id)
    db.add(contract);db.flush();db.add_all([RepairContractDevice(contract_id=contract.id,device_id=did) for did in ids]);db.flush()
    return contract


def for_date(db,cid,on):
    chosen=db.get(RepairMaintenanceContract,cid)
    if chosen is None: raise HTTPException(404,'قرارداد پیدا نشد.')
    latest=db.query(RepairMaintenanceContract).filter(RepairMaintenanceContract.code==chosen.code,RepairMaintenanceContract.valid_from<=on,RepairMaintenanceContract.valid_until>=on).order_by(RepairMaintenanceContract.version.desc()).first()
    if latest is None or latest.id!=cid or not latest.enabled:
        raise HTTPException(422,'نسخهٔ فعال قرارداد در تاریخ خدمت را انتخاب کنید.')
    return chosen


def usage(db,contract):
    links=db.query(RepairContractCase).join(RepairMaintenanceContract,RepairMaintenanceContract.id==RepairContractCase.contract_id).filter(RepairMaintenanceContract.code==contract.code,RepairContractCase.service_date>=contract.valid_from,RepairContractCase.service_date<=contract.valid_until,RepairContractCase.released_at.is_(None)).all()
    return {'visits':len(links),'minutes':sum(l.consumed_minutes if l.consumed_minutes is not None else l.allocated_minutes for l in links),
        'value_rial':sum((l.covered_value_rial for l in links),Decimal(0))}


def bind(db,p,row,data):
    core.check_version(row,data.version)
    if db.query(RepairContractCase).filter_by(case_id=row.id).first(): raise HTTPException(409,'پوشش این پرونده قبلاً ثبت شده است.')
    if db.query(RepairWork).filter_by(case_id=row.id).first() or row.status not in {'accepted','diagnosing','awaiting_customer'}:
        raise HTTPException(409,'پوشش را پیش از ثبت کار واقعی تعیین کنید.')
    if db.query(RepairWarrantyClaim).filter_by(revisit_case_id=row.id).first(): raise HTTPException(409,'پوشش ضمانت و قرارداد را روی یک مراجعه هم‌زمان ثبت نکنید.')
    db.query(Contact.id).filter_by(id=row.contact_id).with_for_update(of=Contact).one()
    contract=for_date(db,data.contract_id,data.service_date)
    if contract.contact_id!=row.contact_id or not db.query(RepairContractDevice).filter_by(contract_id=contract.id,device_id=row.device_id).first():
        raise HTTPException(422,'مالک و دستگاه تحت پوشش این قرارداد نیستند.')
    if data.service_date<row.admission_date: raise HTTPException(422,'تاریخ خدمت نمی‌تواند پیش از پذیرش باشد.')
    used=usage(db,contract)
    for current,extra,ceiling in ((used['visits'],1,contract.visit_quota),(used['minutes'],data.allocated_minutes,contract.minute_quota),(used['value_rial'],data.covered_value_rial,contract.value_quota_rial)):
        if ceiling is not None and current+extra>ceiling: raise HTTPException(409,'سهمیهٔ قرارداد برای این پوشش کافی نیست؛ پوشش یا قرارداد را بازبینی کنید.')
    from app.models.repair import RepairServiceRequest
    source=db.query(RepairServiceRequest).filter_by(case_id=row.id).first()
    now=source.created_at if source else row.created_at
    link=RepairContractCase(case_id=row.id,contract_id=contract.id,service_date=data.service_date,allocated_minutes=data.allocated_minutes,
        covered_value_rial=data.covered_value_rial,snapshot={'code':contract.code,'version':contract.version,'title':contract.title,'valid_from':contract.valid_from.isoformat(),
        'valid_until':contract.valid_until.isoformat(),'terms':contract.terms,'covers_labor':contract.covers_labor,'covers_parts':contract.covers_parts},
        response_due_at=now+timedelta(hours=contract.response_hours),completion_due_at=now+timedelta(hours=contract.completion_hours),recorded_by_id=p.user.id)
    db.add(link);db.flush();core.event(db,p,row,'contract_coverage',{'contract_id':str(contract.id),'contract_version':contract.version,'service_date':data.service_date.isoformat(),
        'allocated_minutes':data.allocated_minutes,'covered_value_rial':str(data.covered_value_rial)})
    return link


def outside(db,p,row,data):
    core.check_version(row,data.version)
    link=db.query(RepairContractCase).filter_by(case_id=row.id).one_or_none()
    if link is None: raise HTTPException(409,'این پرونده پوشش قرارداد ندارد.')
    estimate,decision=core.approved_estimate(db,row)
    if estimate.id!=data.estimate_id: raise HTTPException(409,'هزینهٔ خارج از پوشش باید به آخرین برآورد تأییدشدهٔ مشتری وصل شود.')
    link.outside_estimate_id=estimate.id
    core.event(db,p,row,'outside_coverage_approved',{'estimate_id':str(estimate.id),'customer_name':decision.customer_name,'reason':data.reason})
    return link


def assert_outside(db,row,link):
    estimate,_=core.approved_estimate(db,row)
    if link.outside_estimate_id!=estimate.id: raise HTTPException(409,'ابتدا آخرین برآورد خارج از پوشش را با تأیید واقعی مشتری به قرارداد وصل کنید.')


def assert_work(db,row,amount,minutes,on):
    link=db.query(RepairContractCase).filter_by(case_id=row.id).one_or_none()
    if link is None: return
    if amount: assert_outside(db,row,link);return
    if not link.snapshot['covers_labor']: raise HTTPException(409,'اجرت تحت پوشش قرارداد نیست؛ برآورد خارج از پوشش لازم است.')
    if not date.fromisoformat(link.snapshot['valid_from'])<=on<=date.fromisoformat(link.snapshot['valid_until']):
        raise HTTPException(409,'تاریخ انجام کار خارج از پوشش ثبت‌شده است.')
    used=db.query(func.sum(RepairWork.work_minutes)).filter_by(case_id=row.id,charge_amount=0).scalar() or 0
    if used+minutes>link.allocated_minutes: raise HTTPException(409,'زمان کار تحت پوشش از سهمیهٔ تخصیص‌یافته بیشتر است؛ کار اضافی به برآورد خارج از پوشش نیاز دارد.')


def assert_part(db,row,part,on=None):
    link=db.query(RepairContractCase).filter_by(case_id=row.id).one_or_none()
    if link is None or part.owner!='company': return
    if part.charge_to_customer: assert_outside(db,row,link);return
    if not link.snapshot['covers_parts']: raise HTTPException(409,'قطعه تحت پوشش قرارداد نیست؛ برآورد خارج از پوشش لازم است.')
    if on and not date.fromisoformat(link.snapshot['valid_from'])<=on<=date.fromisoformat(link.snapshot['valid_until']):
        raise HTTPException(409,'تاریخ مصرف قطعه خارج از پوشش ثبت‌شده است.')


def finish(db,row):
    link=db.query(RepairContractCase).filter_by(case_id=row.id).one_or_none()
    if link:
        link.consumed_minutes=db.query(func.sum(RepairWork.work_minutes)).filter_by(case_id=row.id,charge_amount=0).scalar() or 0


def projection(db,contract):
    result=core.out(contract);result['device_ids']=[d.device_id for d in db.query(RepairContractDevice).filter_by(contract_id=contract.id)]
    result['usage']={k:str(v) if isinstance(v,Decimal) else v for k,v in usage(db,contract).items()}
    return result


def case_view(db,row):
    link=db.query(RepairContractCase).filter_by(case_id=row.id).one_or_none()
    if link is None:return None
    result=core.out(link);now=datetime.now(timezone.utc)
    first=db.query(RepairWork).filter_by(case_id=row.id).order_by(RepairWork.created_at).first()
    passed=db.query(RepairQualityCheck).filter_by(case_id=row.id,passed=True,work_version=row.work_version).first()
    from app.models.repair import RepairServiceRequest
    requests=db.query(RepairServiceRequest.id).filter_by(case_id=row.id)
    arrivals=[a.arrived_at for a in db.query(RepairAppointment).filter(RepairAppointment.request_id.in_(requests),RepairAppointment.arrived_at.isnot(None))]
    candidates=arrivals+([first.started_at or first.created_at] if first else [])
    response=min(candidates) if candidates else None
    result.update(response_at=response,completed_at=passed.created_at if passed else None,
        response_overdue=(response or now)>link.response_due_at,completion_overdue=(passed.created_at if passed else now)>link.completion_due_at)
    return result


def create_plan(db,p,data):
    contract=for_date(db,data.contract_id,data.next_due);core.branch(db,p,data.branch_id)
    if not db.query(RepairContractDevice).filter_by(contract_id=contract.id,device_id=data.device_id).first(): raise HTTPException(422,'دستگاه تحت پوشش این نسخه قرارداد نیست.')
    plan=RepairMaintenancePlan(**data.model_dump(),created_by_id=p.user.id);db.add(plan);db.flush();return plan


def request_visit(db,p,plan):
    core.branch(db,p,plan.branch_id)
    if not plan.enabled: raise HTTPException(409,'برنامه غیرفعال است.')
    pending=db.query(RepairMaintenanceVisit).filter_by(plan_id=plan.id,performed_at=None).first()
    if pending:return pending
    contract=for_date(db,plan.contract_id,plan.next_due);device=db.get(RepairDevice,plan.device_id)
    request=repair_field.create(db,p,ServiceRequestIn(branch_id=plan.branch_id,contact_id=contract.contact_id,type_id=device.type_id,
        device_description=' / '.join(v for v in (device.brand,device.model,device.serial) if v),reported_issue=plan.title,address=contract.address,
        coordinator_name=contract.coordinator_name,coordinator_phone=contract.coordinator_phone))
    visit=RepairMaintenanceVisit(plan_id=plan.id,request_id=request.id,due_date=plan.next_due,recorded_by_id=p.user.id)
    db.add(visit);db.flush();repair_field.event(db,p,request,'maintenance_due',{'plan_id':str(plan.id),'due_date':plan.next_due.isoformat()})
    return visit


def complete_visit(db,p,plan,visit,data):
    core.branch(db,p,plan.branch_id)
    if visit.performed_at:return visit
    request=repair_field.request(db,p,visit.request_id,True)
    appointment=db.query(RepairAppointment).filter_by(request_id=request.id,status='completed').order_by(RepairAppointment.completed_at.desc()).first()
    if appointment is None: raise HTTPException(409,'نوبت باید با حضور و نتیجهٔ واقعی پایان یافته باشد.')
    if request.case_id:
        row=core.case(db,p,request.case_id,lock=True)
        if not db.query(RepairQualityCheck).filter_by(case_id=row.id,passed=True,work_version=row.work_version).first():raise HTTPException(409,'کنترل کیفیت پروندهٔ مرتبط را تکمیل کنید.')
    visit.performed_at=appointment.completed_at;visit.result=data.result
    plan.next_due=max(visit.due_date,appointment.completed_at.date())+timedelta(days=plan.interval_days)
    repair_field.event(db,p,request,'maintenance_performed',{'visit_id':str(visit.id),'next_due':plan.next_due.isoformat(),'result':data.result})
    return visit


def bundle(db,p,data):
    ids=sorted(set(data.case_ids),key=str)
    rows=[core.case(db,p,cid,lock=True) for cid in ids]
    if len({r.contact_id for r in rows})!=1: raise HTTPException(422,'صورتحساب تجمیعی فقط برای یک مالک سازمانی است.')
    bill=RepairConsolidatedBill(contact_id=rows[0].contact_id,title=data.title,issued_date=data.on,created_by_id=p.user.id)
    db.add(bill);db.flush()
    for row in rows:
        invoice=repair_finance.active_invoice(db,row)
        if invoice is None:
            repair_finance.invoice(db,p,row,RepairInvoiceIn(version=row.version,on=data.on))
            invoice=repair_finance.active_invoice(db,row)
        if data.on<invoice.invoice_date: raise HTTPException(422,'تاریخ صورتحساب نمی‌تواند پیش از فاکتور مبنا باشد.')
        member=RepairConsolidatedBillMember(bill_id=bill.id,case_id=row.id,sales_invoice_id=invoice.id,
            invoice_snapshot={'number':invoice.number,'net_rial':str(invoice.total_amount),'tax_rial':str(invoice.tax_amount)})
        db.add(member);core.event(db,p,row,'consolidated_bill',{'bill_id':str(bill.id),'sales_invoice_id':str(invoice.id)})
    db.flush();return bill


def bill_view(db,p,bill):
    members=db.query(RepairConsolidatedBillMember).filter_by(bill_id=bill.id).all();items=[]
    for member in members:
        row=core.case(db,p,member.case_id)
        doc=next((d for d in repair_finance.financial(db,row)['documents'] if d['document_type']=='sales_invoice' and str(d['document_id'])==str(member.sales_invoice_id)),None)
        items.append({'case_id':row.id,'case_number':row.number,'invoice_id':member.sales_invoice_id,'invoice_snapshot':member.invoice_snapshot,'current_document':doc})
    return {**core.out(bill),'members':items,'basis':'statement_of_independent_posted_invoices; no_additional_journal_or_receivable'}


def release_unused(db,p,row,reason):
    link=db.query(RepairContractCase).filter_by(case_id=row.id).one_or_none()
    if link is None or link.released_at:return
    from app.models.repair import RepairPart,RepairPartMovement,RepairOutsource,RepairServiceRequest
    if db.query(RepairWork).filter_by(case_id=row.id).first() or db.query(RepairOutsource).filter_by(case_id=row.id).first():return
    if db.query(RepairPartMovement).join(RepairPart,RepairPart.id==RepairPartMovement.part_id).filter(RepairPart.case_id==row.id,RepairPartMovement.action.in_(['consume','waste'])).first():return
    requests=db.query(RepairServiceRequest.id).filter_by(case_id=row.id)
    if db.query(RepairAppointment).filter(RepairAppointment.request_id.in_(requests),RepairAppointment.arrived_at.isnot(None)).first():return
    db.query(Contact.id).filter_by(id=row.contact_id).with_for_update(of=Contact).one()
    link.released_at=datetime.now(timezone.utc);link.release_reason=reason;link.consumed_minutes=0
    core.event(db,p,row,'unused_contract_released',{'coverage_id':str(link.id),'reason':reason})
