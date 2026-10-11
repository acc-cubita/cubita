from datetime import date
from uuid import UUID
from fastapi import APIRouter,Depends,Request,HTTPException,Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal,get_principal,require_module,require_permission
from app.models.repair import RepairMaintenanceContract,RepairContractCase,RepairMaintenancePlan,RepairMaintenanceVisit,RepairConsolidatedBill,RepairDevice,RepairCase
from app.schemas.repair import MaintenanceContractIn,ContractCaseIn,OutsideCoverageIn,MaintenancePlanIn,MaintenanceCompleteIn,ConsolidatedBillIn
from app.services import repair as core,repair_contracts as svc
from app.routers.repair_operations import once
router=APIRouter(prefix='/api/repair',tags=['repair'],dependencies=[Depends(require_module('repair')),Depends(require_permission('repair','view'))])

@router.get('/contract-devices',dependencies=[Depends(require_permission('repair','approve'))])
def devices(contact_id:UUID,q:str=Query(default='',max_length=120),db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    ids=core.visible(db,p).filter_by(contact_id=contact_id).with_entities(RepairCase.device_id)
    query=db.query(RepairDevice).filter(RepairDevice.id.in_(ids))
    if q: query=query.filter(RepairDevice.model.ilike('%'+q+'%')|RepairDevice.serial.ilike('%'+q+'%'))
    return [core.out(d) for d in query.order_by(RepairDevice.id).limit(200)]

@router.get('/maintenance-contracts',dependencies=[Depends(require_permission('repair','approve'))])
def contracts(db:Session=Depends(get_db)):
    return [svc.projection(db,c) for c in db.query(RepairMaintenanceContract).order_by(RepairMaintenanceContract.created_at.desc(),RepairMaintenanceContract.version.desc()).limit(200)]

@router.post('/maintenance-contracts',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def create(data:MaintenanceContractIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    def replay(rid):
        row=db.get(RepairMaintenanceContract,rid)
        if row is None:raise HTTPException(404,'قرارداد پیدا نشد.')
        return row
    return svc.projection(db,once(db,request,p,'repair.contract',data,lambda:svc.create(db,p,data),replay))

@router.get('/cases/{case_id}/contract')
def case_contract(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return svc.case_view(db,core.case(db,p,case_id))

@router.post('/cases/{case_id}/contract',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def bind(case_id:UUID,data:ContractCaseIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    def replay(rid):
        link=db.query(RepairContractCase).filter_by(id=rid,case_id=case_id).one_or_none()
        if link is None:raise HTTPException(404,'پوشش پیدا نشد.')
        return link
    return core.out(once(db,request,p,'repair.contract-case:'+str(case_id),data,lambda:svc.bind(db,p,core.case(db,p,case_id,lock=True),data),replay))

@router.post('/cases/{case_id}/outside-coverage',dependencies=[Depends(require_permission('repair','approve'))])
def outside(case_id:UUID,data:OutsideCoverageIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return core.out(svc.outside(db,p,core.case(db,p,case_id,lock=True),data))

@router.get('/maintenance-plans',dependencies=[Depends(require_permission('repair','approve'))])
def plans(due_only:bool=False,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    q=db.query(RepairMaintenancePlan).filter(RepairMaintenancePlan.branch_id.in_(core.branch_query(db,p).with_entities(core.RepairBranch.id)))
    if due_only:q=q.filter(RepairMaintenancePlan.enabled.is_(True),RepairMaintenancePlan.next_due<=date.today())
    result=[]
    for plan in q.order_by(RepairMaintenancePlan.next_due,RepairMaintenancePlan.id).limit(200):
        result.append({**core.out(plan),'visits':[core.out(v) for v in db.query(RepairMaintenanceVisit).filter_by(plan_id=plan.id).order_by(RepairMaintenanceVisit.due_date.desc()).limit(100)]})
    return result

@router.post('/maintenance-plans',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def plan(data:MaintenancePlanIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    def replay(rid):
        row=db.get(RepairMaintenancePlan,rid)
        if row is None:raise HTTPException(404,'برنامه پیدا نشد.')
        core.branch(db,p,row.branch_id);return row
    return core.out(once(db,request,p,'repair.maintenance-plan',data,lambda:svc.create_plan(db,p,data),replay))

@router.post('/maintenance-plans/{pid}/request',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def request_visit(pid:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    plan=db.query(RepairMaintenancePlan).filter_by(id=pid).with_for_update().populate_existing().one_or_none()
    if plan is None:raise HTTPException(404,'برنامه پیدا نشد.')
    return core.out(svc.request_visit(db,p,plan))

@router.post('/maintenance-plans/{pid}/visits/{vid}/complete',dependencies=[Depends(require_permission('repair','approve'))])
def complete(pid:UUID,vid:UUID,data:MaintenanceCompleteIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    plan=db.query(RepairMaintenancePlan).filter_by(id=pid).with_for_update().populate_existing().one_or_none()
    if plan is None:raise HTTPException(404,'برنامه پیدا نشد.')
    visit=db.query(RepairMaintenanceVisit).filter_by(id=vid,plan_id=pid).one_or_none()
    if visit is None:raise HTTPException(404,'مراجعه پیدا نشد.')
    return core.out(svc.complete_visit(db,p,plan,visit,data))

@router.post('/consolidated-bills',status_code=201,dependencies=[Depends(require_permission('repair','approve')),Depends(require_permission('invoices','create')),Depends(require_permission('invoices','view'))])
def bill(data:ConsolidatedBillIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    def replay(rid):
        row=db.get(RepairConsolidatedBill,rid)
        if row is None:raise HTTPException(404,'صورتحساب پیدا نشد.')
        return row
    return svc.bill_view(db,p,once(db,request,p,'repair.consolidated-bill',data,lambda:svc.bundle(db,p,data),replay))

@router.get('/consolidated-bills',dependencies=[Depends(require_permission('repair','approve')),Depends(require_permission('invoices','view'))])
def bills(db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return [svc.bill_view(db,p,b) for b in db.query(RepairConsolidatedBill).order_by(RepairConsolidatedBill.created_at.desc()).limit(100)]


@router.get('/consolidated-bills/{bid}/print',dependencies=[Depends(require_permission('repair','approve')),Depends(require_permission('invoices','view'))])
def print_bill(bid:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    from fastapi.responses import HTMLResponse
    from html import escape
    from decimal import Decimal
    from app.services.printing import fa_number,format_jalali
    bill=db.get(RepairConsolidatedBill,bid)
    if bill is None:raise HTTPException(404,'صورتحساب پیدا نشد.')
    view=svc.bill_view(db,p,bill);body=[];remaining=Decimal(0)
    for member in view['members']:
        current=member['current_document'];amount=Decimal(current['remaining_amount']) if current and not current['voided'] else Decimal(0)
        remaining+=amount
        body.append('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in (fa_number(member['case_number']),fa_number(member['invoice_snapshot']['number']),fa_number(member['invoice_snapshot']['net_rial']),fa_number(member['invoice_snapshot']['tax_rial']),fa_number(amount),'ابطال شده' if current and current['voided'] else 'فعال'))+'</tr>')
    return HTMLResponse('<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>صورتحساب تجمیعی تعمیرگاه</title><style>body{font-family:Tahoma;margin:24px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:8px}</style><h1>'+escape(bill.title)+'</h1><p>صورتحساب تجمیعی تعمیرگاه — '+escape(format_jalali(bill.issued_date))+'</p><p>این گزارش شامل فاکتورهای مستقل است و سند فروش یا بدهی دوباره ایجاد نمی‌کند. همه مبالغ ریال هستند.</p><table><thead><tr><th>پذیرش</th><th>فاکتور</th><th>خالص زمان صدور</th><th>مالیات زمان صدور</th><th>ماندهٔ فعلی</th><th>وضعیت</th></tr></thead><tbody>'+''.join(body)+'</tbody></table><p>جمع ماندهٔ فعلی: '+escape(fa_number(remaining))+' ریال</p></html>',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
