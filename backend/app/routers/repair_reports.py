from datetime import date, datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal, get_principal, require_module, require_permission
from app.models.repair import RepairCase
from app.services import repair as core, repair_reports as svc

router=APIRouter(prefix='/api/repair',tags=['repair'],dependencies=[Depends(require_module('repair')),Depends(require_permission('repair','view'))])

@router.get('/reports')
def report(from_date:date|None=None,to_date:date|None=None,cursor:UUID|None=None,limit:int=Query(default=50,ge=1,le=200),financial:bool=False,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    if from_date and to_date and from_date>to_date: raise HTTPException(422,'بازهٔ تاریخ پذیرش معتبر نیست.')
    if financial and not (p.has_permission('repair','approve') and p.has_permission('invoices','view')):
        raise HTTPException(403,'گزارش مالی به مجوز مدیریت تعمیرگاه و مشاهدهٔ فاکتور نیاز دارد.')
    query=core.visible(db,p)
    if from_date: query=query.filter(RepairCase.admission_date>=from_date)
    if to_date: query=query.filter(RepairCase.admission_date<=to_date)
    counts=dict(query.with_entities(RepairCase.status,func.count(RepairCase.id)).group_by(RepairCase.status).all())
    if cursor: query=query.filter(RepairCase.id>cursor)
    rows=query.order_by(RepairCase.id).limit(limit+1).all()
    return {'generated_at':datetime.now(timezone.utc),'date_basis':'admission_date','financial_basis':'current_documents_not_historical_as_of',
        'status_counts':counts,'items':[svc.case_report(db,p,row,financial) for row in rows[:limit]],'next_cursor':str(rows[limit-1].id) if len(rows)>limit else None}

@router.get('/cases/{case_id}/report')
def case_report(case_id:UUID,financial:bool=False,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    if financial and not (p.has_permission('repair','approve') and p.has_permission('invoices','view')): raise HTTPException(403,'مجوز گزارش مالی ندارید.')
    return svc.case_report(db,p,core.case(db,p,case_id),financial)
