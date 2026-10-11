"""لینک فقط هش‌شده ذخیره می‌شود؛ همهٔ دسترسی‌ها به یک پرونده محدودند."""
import hashlib
import json
import secrets
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from uuid import UUID
from fastapi import HTTPException
from app.config import get_settings
from app.models.tenant import Tenant
from app.models.repair import RepairCase,RepairPortalToken,RepairPortalSubmission,RepairCustomerMessage,RepairEstimate,RepairEstimateDecision,RepairAttachment,RepairWork
from app.schemas.repair import EstimateDecisionIn
from app.services import repair as core
from app.services.modules import is_module_visible
from app.tenant_context import bind_session_tenant,apply_tenant_to_transaction


def issue(db,p,row,data):
    core.check_version(row,data.version)
    raw=secrets.token_urlsafe(32)
    token=RepairPortalToken(case_id=row.id,token_hash=hashlib.sha256(raw.encode()).hexdigest(),expires_at=datetime.now(timezone.utc)+timedelta(days=data.expires_days),created_by_id=p.user.id)
    db.add(token);db.flush()
    core.event(db,p,row,'portal_link_created',{'token_id':str(token.id),'expires_at':token.expires_at.isoformat()})
    # fragment به سرور، access log و Referer فرستاده نمی‌شود.
    url=get_settings().app_url.rstrip('/')+'/repair-track#token='+str(row.tenant_id)+'.'+raw
    return {'id':token.id,'expires_at':token.expires_at,'url':url}


def authenticate(db,authorization,*,lock=False):
    try:
        scheme,credential=authorization.split(' ',1)
        tenant_text,raw=credential.split('.',1)
        tenant_id=UUID(tenant_text)
        if scheme!='RepairPortal' or len(raw)!=43: raise ValueError()
    except (ValueError,AttributeError): raise HTTPException(404,'لینک معتبر پیدا نشد؛ از تعمیرگاه لینک تازه بگیرید.')
    tenant=db.get(Tenant,tenant_id)
    if not tenant or tenant.status!='active' or not is_module_visible(tenant,'repair'):
        raise HTTPException(404,'لینک معتبر پیدا نشد؛ از تعمیرگاه لینک تازه بگیرید.')
    bind_session_tenant(db,tenant_id);apply_tenant_to_transaction(db,tenant_id)
    token=db.query(RepairPortalToken).filter_by(token_hash=hashlib.sha256(raw.encode()).hexdigest()).first()
    if token is None: raise HTTPException(404,'لینک معتبر پیدا نشد؛ از تعمیرگاه لینک تازه بگیرید.')
    query=db.query(RepairCase).filter_by(id=token.case_id)
    row=query.with_for_update().populate_existing().one() if lock else query.one()
    if lock:
        token=db.query(RepairPortalToken).filter_by(id=token.id).with_for_update().populate_existing().one()
    if token.revoked_at or token.expires_at<=datetime.now(timezone.utc):
        raise HTTPException(404,'این لینک منقضی یا لغو شده است؛ از تعمیرگاه لینک تازه بگیرید.')
    return row,token


def once(db,row,token,request,operation,payload,run,model):
    key=request.headers.get('Idempotency-Key','')
    if not key or len(key)>128 or not key.isascii(): raise HTTPException(400,'کلید یکتاسازی معتبر لازم است؛ صفحه را تازه کنید.')
    encoded=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    digest=hashlib.sha256(encoded).hexdigest()
    old=db.query(RepairPortalSubmission).filter_by(token_id=token.id,operation=operation,request_key=key).first()
    if old:
        if old.payload_hash!=digest: raise HTTPException(409,'این درخواست قبلاً با محتوای دیگری ثبت شده است؛ صفحه را تازه کنید.')
        resource=db.query(model).filter_by(id=old.resource_id,case_id=row.id).one_or_none()
        if resource is None: raise HTTPException(404,'نتیجهٔ درخواست پیدا نشد؛ با تعمیرگاه تماس بگیرید.')
        return resource
    result=run()
    db.add(RepairPortalSubmission(case_id=row.id,token_id=token.id,operation=operation,request_key=key,payload_hash=digest,resource_id=result.id));db.flush()
    return result


def decide(db,row,token,data):
    estimate=db.query(RepairEstimate).filter_by(id=data.estimate_id,case_id=row.id).one_or_none()
    if estimate is None: raise HTTPException(404,'برآورد مربوط به این پرونده پیدا نشد.')
    principal=SimpleNamespace(user=SimpleNamespace(id=None))
    decision=core.decide(db,principal,row,estimate,EstimateDecisionIn(**data.model_dump(exclude={'estimate_id'}),method='written'))
    decision.portal_token_id=token.id
    db.flush()
    return decision


def message(db,row,token,data):
    if data.kind=='survey' and row.status not in {'delivered','closed'}:
        raise HTTPException(409,'امتیاز رضایت پس از تحویل دستگاه ثبت می‌شود.')
    if (data.kind=='survey')!=(data.rating is not None):
        raise HTTPException(422,'امتیاز یک تا پنج فقط برای نظرسنجی لازم است.')
    if db.query(RepairCustomerMessage).filter_by(case_id=row.id).count()>=200:
        raise HTTPException(409,'سقف پیام‌های این پرونده پر شده؛ با تعمیرگاه تماس بگیرید.')
    row_message=RepairCustomerMessage(case_id=row.id,token_id=token.id,**data.model_dump())
    db.add(row_message);db.flush()
    core.event(db,SimpleNamespace(user=SimpleNamespace(id=None)),row,'customer_'+data.kind,{'message_id':str(row_message.id),'token_id':str(token.id)})
    return row_message


def projection(db,row):
    from app.models.repair import RepairWarranty
    estimate=db.query(RepairEstimate).filter_by(case_id=row.id).order_by(RepairEstimate.version.desc()).first()
    decision=db.query(RepairEstimateDecision).filter_by(estimate_id=estimate.id).first() if estimate else None
    estimate_view=None
    if estimate:
        options=[{'title':o['title'],'total':o['total'],'lines':[{k:l[k] for k in ('kind','title','qty','unit_price','amount') if k in l} for l in o['lines']]} for o in estimate.options]
        estimate_view={'id':estimate.id,'version':estimate.version,'valid_until':estimate.valid_until,'duration_days':estimate.duration_days,'currency':'IRR','options':options,
            'decision':{'decision':decision.decision,'customer_name':decision.customer_name,'created_at':decision.created_at,'option_index':decision.option_index,'authorized_ceiling':str(decision.authorized_ceiling) if decision.authorized_ceiling is not None else None} if decision else None}
    return {'number':row.number,'version':row.version,'status':row.status,'status_label':core.STATE_LABELS[row.status],
            'admission_date':row.admission_date,'due_date':row.due_date,'device':{k:row.device_snapshot.get(k,'') for k in ('category','brand','model','serial','imei')},
            'customer':row.owner_snapshot.get('name',''),'reported_issue':row.reported_issue,'accessories':row.accessories,'terms':row.terms,
            'warranties':[{k:getattr(w,k) for k in ('scope','title','terms','exclusions','valid_from','valid_until')} for w in db.query(RepairWarranty).filter_by(case_id=row.id).order_by(RepairWarranty.created_at).all()],
            'estimate':estimate_view,'results':[w.customer_result for w in db.query(RepairWork).filter_by(case_id=row.id).order_by(RepairWork.created_at) if w.customer_result],
            'attachments':[{'id':a.id,'filename':a.filename,'size':a.size} for a in db.query(RepairAttachment).filter_by(case_id=row.id,customer_visible=True).order_by(RepairAttachment.created_at)],
            'messages':[{'id':m.id,'kind':m.kind,'name':m.name,'body':m.body,'rating':m.rating,'created_at':m.created_at} for m in db.query(RepairCustomerMessage).filter_by(case_id=row.id).order_by(RepairCustomerMessage.created_at).all()],
            **payment_status(db,row)}


def payment_status(db,row):
    from app.services.repair_payments import public_status
    from app.services.repair_finance import financial
    status=public_status(db,row)
    status['documents']=[{k:d[k] for k in ('id','document_type','number','amount','voided')} for d in financial(db,row)['documents'] if d['document_type'] in {'sales_invoice','receipt'}]
    return status
