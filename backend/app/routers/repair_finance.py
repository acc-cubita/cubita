from uuid import UUID
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import HTMLResponse
from html import escape
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal, get_principal, require_module, require_permission
from app.models.repair import RepairDelivery, RepairDocument
from app.schemas.repair import RepairInvoiceIn, RepairCashIn, RepairDeliveryIn, RepairDocumentLinkIn, RepairCorrectionIn, VersionIn
from app.services import repair as core, repair_finance as svc
from app.routers.repair_operations import once

router=APIRouter(prefix='/api/repair',tags=['repair'],dependencies=[Depends(require_module('repair')),Depends(require_permission('repair','view'))])


def related(db,model,case_id,rid):
    result=db.query(model).filter_by(case_id=case_id,id=rid).one_or_none()
    if result is None: raise HTTPException(404,'رکورد مربوط به این پرونده پیدا نشد.')
    return result


@router.get('/cases/{case_id}/finance',dependencies=[Depends(require_permission('invoices','view'))])
def finance(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return svc.financial(db,core.case(db,p,case_id))


@router.post('/cases/{case_id}/invoice',status_code=201,dependencies=[Depends(require_permission('repair','update')),Depends(require_permission('invoices','create'))])
def invoice(case_id:UUID,data:RepairInvoiceIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    result=once(db,request,p,'repair.invoice:'+str(case_id),data,lambda:svc.invoice(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:related(db,RepairDocument,case_id,rid))
    return core.out(result)


@router.post('/cases/{case_id}/receipts',status_code=201,dependencies=[Depends(require_permission('repair','update')),Depends(require_permission('checks_bank','create'))])
def receipt(case_id:UUID,data:RepairCashIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    result=once(db,request,p,'repair.receipt:'+str(case_id),data,lambda:svc.cash(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:related(db,RepairDocument,case_id,rid))
    return core.out(result)


@router.post('/cases/{case_id}/refunds',status_code=201,dependencies=[Depends(require_permission('repair','approve')),Depends(require_permission('checks_bank','create'))])
def refund(case_id:UUID,data:RepairCashIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    result=once(db,request,p,'repair.refund:'+str(case_id),data,lambda:svc.cash(db,p,core.case(db,p,case_id,lock=True),data,refund=True),lambda rid:related(db,RepairDocument,case_id,rid))
    return core.out(result)


@router.post('/cases/{case_id}/documents',status_code=201,dependencies=[Depends(require_permission('repair','approve')),Depends(require_permission('invoices','view')),Depends(require_permission('checks_bank','view'))])
def link_document(case_id:UUID,data:RepairDocumentLinkIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    result=once(db,request,p,'repair.document:'+str(case_id),data,lambda:svc.attach_document(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:related(db,RepairDocument,case_id,rid))
    return core.out(result)


@router.post('/cases/{case_id}/delivery',status_code=201,dependencies=[Depends(require_permission('repair',('deliver','approve')))])
def delivery(case_id:UUID,data:RepairDeliveryIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    result=once(db,request,p,'repair.delivery:'+str(case_id),data,lambda:svc.delivery(db,p,core.case(db,p,case_id,lock=True),data),lambda rid:related(db,RepairDelivery,case_id,rid))
    return core.out(result)


@router.post('/cases/{case_id}/close',dependencies=[Depends(require_permission('repair','approve'))])
def close(case_id:UUID,data:VersionIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return core.out(svc.close(db,p,core.case(db,p,case_id,lock=True),data))


@router.get('/cases/{case_id}/delivery-receipt',response_class=HTMLResponse)
def delivery_receipt(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=core.case(db,p,case_id)
    result=db.query(RepairDelivery).filter_by(case_id=row.id).one_or_none()
    if result is None: raise HTTPException(404,'تحویل فیزیکی ثبت نشده است.')
    from app.services.printing import format_jalali,fa_number
    fields={'پذیرش':fa_number(row.number),'دستگاه':' / '.join(row.device_snapshot[k] for k in ('category','brand','model')),'گیرنده':result.receiver_name,'تماس':result.receiver_phone,'تاریخ تحویل':format_jalali(result.delivered_at.date()),'مجوز دریافت':result.authorization,'لوازم تحویل‌شده':result.accessories,'توصیه نگهداری':result.care_instructions}
    body=''.join(f'<dt>{escape(k)}</dt><dd>{escape(v)}</dd>' for k,v in fields.items())
    return HTMLResponse(f'<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>رسید تحویل</title><style>body{{font-family:Tahoma;margin:24px}}dd{{white-space:pre-wrap}}</style><h1>تعمیرگاه — رسید تحویل دستگاه</h1><dl>{body}</dl><p>این رسید تحویل فیزیکی دستگاه است؛ وضعیت تسویه از اسناد مالی محاسبه می‌شود.</p></html>',headers={'Cache-Control':'no-store'})


@router.post('/cases/{case_id}/documents/{document_ref_id}/void',dependencies=[Depends(require_permission('repair','approve'))])
def correct(case_id:UUID,document_ref_id:UUID,data:RepairCorrectionIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    result=once(db,request,p,'repair.void:'+str(document_ref_id),data,lambda:svc.correct(db,p,core.case(db,p,case_id,lock=True),document_ref_id,data),lambda rid:related(db,RepairDocument,case_id,rid))
    return core.out(result)


@router.get('/cases/{case_id}/linkable-documents',dependencies=[Depends(require_permission('invoices','view')),Depends(require_permission('checks_bank','view'))])
def linkable(case_id:UUID,kind:str=Query(pattern='^(receipt|payment|sales_return)$'),db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=core.case(db,p,case_id);model=svc.MODELS[kind]
    q=db.query(model).filter(model.voided_at.is_(None),model.journal_entry_id.isnot(None))
    if kind=='sales_return':
        from app.models.invoices import SalesInvoice
        q=q.join(SalesInvoice,SalesInvoice.id==model.sales_invoice_id).filter(SalesInvoice.contact_id==row.contact_id,SalesInvoice.id.in_(db.query(RepairDocument.document_id).filter_by(case_id=row.id,document_type='sales_invoice')))
    else: q=q.filter(model.contact_id==row.contact_id)
    q=q.filter(~model.id.in_(db.query(RepairDocument.document_id).filter_by(document_type=kind)))
    return [{'id':d.id,'number':d.number} for d in q.order_by(model.created_at.desc(),model.id).limit(200).all()]
