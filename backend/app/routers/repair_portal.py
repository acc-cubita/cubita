import hashlib
from datetime import datetime,timezone
from html import escape
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Request,Response,UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal,get_principal,require_module,require_permission
from app.models.repair import RepairPortalToken,RepairCustomerMessage,RepairAttachment,RepairEstimateDecision
from app.schemas.repair import RepairPortalTokenIn,RepairPortalDecisionIn,RepairCustomerMessageIn,RepairAttachmentVisibilityIn,VersionIn
from app.services import repair as core,repair_portal as svc


def private_response(response:Response):
    response.headers['Cache-Control']='no-store'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Content-Type-Options']='nosniff'


router=APIRouter(prefix='/api/repair',tags=['repair'],dependencies=[Depends(require_module('repair')),Depends(require_permission('repair','view')),Depends(private_response)])
public_router=APIRouter(prefix='/api/repair-portal',tags=['repair-portal'],dependencies=[Depends(private_response)])


@router.get('/cases/{case_id}/portal-links',dependencies=[Depends(require_permission('repair','approve'))])
def links(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    return [{'id':t.id,'created_at':t.created_at,'expires_at':t.expires_at,'revoked_at':t.revoked_at} for t in db.query(RepairPortalToken).filter_by(case_id=case_id).order_by(RepairPortalToken.created_at.desc()).limit(200)]


@router.post('/cases/{case_id}/portal-links',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def issue(case_id:UUID,data:RepairPortalTokenIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=core.case(db,p,case_id,lock=True)
    if db.query(RepairPortalToken).filter(RepairPortalToken.case_id==case_id,RepairPortalToken.revoked_at.is_(None),RepairPortalToken.expires_at>datetime.now(timezone.utc)).count()>=5:
        raise HTTPException(409,'پنج لینک فعال وجود دارد؛ ابتدا لینک قدیمی را لغو کنید.')
    return svc.issue(db,p,row,data)


@router.post('/cases/{case_id}/portal-links/{link_id}/revoke',dependencies=[Depends(require_permission('repair','approve'))])
def revoke(case_id:UUID,link_id:UUID,data:VersionIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=core.case(db,p,case_id,lock=True);core.check_version(row,data.version)
    link=db.query(RepairPortalToken).filter_by(case_id=case_id,id=link_id).with_for_update().one_or_none()
    if link is None: raise HTTPException(404,'لینک این پرونده پیدا نشد.')
    if link.revoked_at is None:
        link.revoked_at=datetime.now(timezone.utc)
        core.event(db,p,row,'portal_link_revoked',{'token_id':str(link.id)})
    return {'id':link.id,'revoked_at':link.revoked_at}


@router.get('/cases/{case_id}/customer-messages')
def messages(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    return [core.out(m) for m in db.query(RepairCustomerMessage).filter_by(case_id=case_id).order_by(RepairCustomerMessage.created_at.desc()).limit(200)]


@router.put('/cases/{case_id}/attachments/{attachment_id}/visibility',dependencies=[Depends(require_permission('repair','approve'))])
def visibility(case_id:UUID,attachment_id:UUID,data:RepairAttachmentVisibilityIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=core.case(db,p,case_id,lock=True);core.check_version(row,data.version)
    attachment=db.query(RepairAttachment).filter_by(case_id=case_id,id=attachment_id).one_or_none()
    if attachment is None: raise HTTPException(404,'پیوست این پرونده پیدا نشد.')
    attachment.customer_visible=data.customer_visible
    core.event(db,p,row,'attachment_visibility',{'attachment_id':str(attachment.id),'customer_visible':data.customer_visible})
    return {'id':attachment.id,'customer_visible':attachment.customer_visible}


def authorized(db,request,*,lock=False):
    return svc.authenticate(db,request.headers.get('Authorization',''),lock=lock)


@public_router.get('/case')
def case(request:Request,db:Session=Depends(get_db)):
    row,_=authorized(db,request)
    return svc.projection(db,row)


@public_router.post('/decision',status_code=201)
def decision(data:RepairPortalDecisionIn,request:Request,db:Session=Depends(get_db)):
    row,token=authorized(db,request,lock=True)
    decision=svc.once(db,row,token,request,'decision',data.model_dump(mode='json'),lambda:svc.decide(db,row,token,data),RepairEstimateDecision)
    return {'id':decision.id,'decision':decision.decision,'created_at':decision.created_at}


@public_router.post('/messages',status_code=201)
def add_message(data:RepairCustomerMessageIn,request:Request,db:Session=Depends(get_db)):
    row,token=authorized(db,request,lock=True)
    result=svc.once(db,row,token,request,'message',data.model_dump(mode='json'),lambda:svc.message(db,row,token,data),RepairCustomerMessage)
    return {'id':result.id,'created_at':result.created_at}


@public_router.get('/attachments/{attachment_id}')
def download(attachment_id:UUID,request:Request,db:Session=Depends(get_db)):
    row,_=authorized(db,request)
    attachment=db.query(RepairAttachment).filter_by(case_id=row.id,id=attachment_id,customer_visible=True).one_or_none()
    if attachment is None: raise HTTPException(404,'فایل قابل دریافت این پرونده پیدا نشد.')
    return Response(attachment.content,media_type=attachment.content_type,headers={'Content-Disposition':'attachment','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'})


@public_router.post('/attachments',status_code=201)
async def upload(request:Request,file:UploadFile,db:Session=Depends(get_db)):
    row,token=authorized(db,request,lock=True)
    content=await file.read(5*1024*1024+1)
    allowed={'image/jpeg':content.startswith(b'\xff\xd8\xff'),'image/png':content.startswith(b'\x89PNG\r\n\x1a\n'),'application/pdf':content.startswith(b'%PDF-')}
    if not content or len(content)>5*1024*1024 or not allowed.get(file.content_type):
        raise HTTPException(422,'تصویر JPEG/PNG یا PDF معتبر تا پنج مگابایت انتخاب کنید.')
    digest=hashlib.sha256(content).hexdigest()
    attachment=db.query(RepairAttachment).filter_by(case_id=row.id,sha256=digest).first()
    if attachment:
        if not attachment.customer_visible: raise HTTPException(409,'این فایل قابل ثبت از صفحهٔ مشتری نیست؛ با تعمیرگاه تماس بگیرید.')
        return {'id':attachment.id}
    if db.query(RepairAttachment).filter_by(case_id=row.id).count()>=100: raise HTTPException(409,'سقف پیوست‌ها پر شده؛ با تعمیرگاه تماس بگیرید.')
    attachment=RepairAttachment(case_id=row.id,filename=(file.filename or 'تصویر مشتری').replace('\\','/').split('/')[-1][:200],content_type=file.content_type,
        sha256=digest,size=len(content),content=content,uploaded_by_id=None,portal_token_id=token.id,customer_visible=True)
    db.add(attachment);db.flush()
    from types import SimpleNamespace
    core.event(db,SimpleNamespace(user=SimpleNamespace(id=None)),row,'customer_attachment',{'attachment_id':str(attachment.id),'token_id':str(token.id)})
    return {'id':attachment.id}


@public_router.get('/receipt',response_class=HTMLResponse)
def receipt(request:Request,db:Session=Depends(get_db)):
    row,_=authorized(db,request)
    from app.services.printing import format_jalali
    values={'شماره پذیرش':row.number,'مشتری':row.owner_snapshot.get('name',''),'دستگاه':row.device_snapshot.get('model',''),'شناسه دستگاه':row.device_snapshot.get('serial',''),
        'پذیرش':format_jalali(row.admission_date),'وضعیت':core.STATE_LABELS[row.status],'ایراد اعلام‌شده':row.reported_issue,'لوازم همراه':row.accessories,'شرایط پذیرش':row.terms}
    body=''.join(f'<p><b>{escape(k)}:</b> {escape(str(v))}</p>' for k,v in values.items())
    return HTMLResponse('<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>رسید پذیرش تعمیرگاه</title><style>body{font-family:Tahoma;max-width:800px;margin:32px auto;line-height:2;padding:16px}p{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>رسید پذیرش تعمیرگاه</h1>'+body+'</html>',headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff'})


@public_router.get('/documents/{document_ref_id}',response_class=HTMLResponse)
def financial_document(document_ref_id:UUID,request:Request,db:Session=Depends(get_db)):
    from types import SimpleNamespace
    from app.models.repair import RepairDocument
    from app.models.tenant import Tenant
    from app.services.repair_finance import MODELS
    from app.services.printing import render_invoice,render_receipt
    row,_=authorized(db,request)
    ref=db.query(RepairDocument).filter_by(case_id=row.id,id=document_ref_id).one_or_none()
    if ref is None or ref.document_type not in {'sales_invoice','receipt'}: raise HTTPException(404,'سند قابل دریافت این پرونده پیدا نشد.')
    doc=db.get(MODELS[ref.document_type],ref.document_id)
    if doc is None or not doc.journal_entry_id: raise HTTPException(404,'سند قطعی این پرونده پیدا نشد.')
    tenant=db.get(Tenant,row.tenant_id)
    if ref.document_type=='sales_invoice':
        # همان موتور چاپ و snapshot سند؛ DTO آن هزینه و یادداشت تعمیر را ندارد.
        from app.routers.invoices import _sales_render_kwargs
        kwargs=_sales_render_kwargs(db,SimpleNamespace(membership=SimpleNamespace(tenant=tenant)),doc)
        kwargs['void_reason']=''  # دلیل ابطال ممکن است یادداشت داخلی خزانه باشد.
        html=render_invoice(**kwargs)
    else:
        from app.services.receipts import components
        safe=[{'kind':c['kind'],'amount':c['amount'],'label':{'cash':'نقد','card':'پرداخت کارتی','transfer':'حواله','cheque':'چک'}[c['kind']]} for c in components(db,doc)]
        html=render_receipt(business_name=tenant.name,number=doc.number,receipt_date=doc.receipt_date,type_label='دریافت از مشتری',
            party_name=row.owner_snapshot.get('name',''),party_detail='',description=f'پذیرش {row.number}',components=safe,
            receipt_amount=doc.base_currency_amount,discount_amount=doc.discount_amount,settlement_total=doc.base_currency_amount+doc.discount_amount,voided_at=doc.voided_at)
    return HTMLResponse(html,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff'})
