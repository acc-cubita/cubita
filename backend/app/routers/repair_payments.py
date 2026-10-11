from uuid import UUID
from html import escape
from fastapi import APIRouter,Depends,Request,HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal,get_principal,require_module,require_permission
from app.models.repair import RepairCase,RepairOnlineSettings,RepairPaymentIntent
from app.models.storefront_native import PaymentGateway
from app.models.tenant import Tenant
from app.schemas.repair import RepairOnlineSettingsIn,RepairPortalPaymentIn,VersionIn
from app.services import repair as core,repair_portal as portal,repair_payments as svc,repair_access
from app.routers.repair_portal import authorized,private_response
from app.tenant_context import bind_session_tenant,apply_tenant_to_transaction

router=APIRouter(prefix='/api/repair',tags=['repair'],dependencies=[Depends(require_module('repair')),Depends(require_permission('repair','view')),Depends(private_response)])
public_router=APIRouter(prefix='/api/repair-portal',tags=['repair-portal'],dependencies=[Depends(private_response)])
callback_router=APIRouter(prefix='/api/repair-payments',tags=['repair-payments'],dependencies=[Depends(private_response)])


@router.get('/branches/{branch_id}/online-payment',dependencies=[Depends(require_permission('repair','approve'))])
def settings(branch_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.branch(db,p,branch_id)
    config=db.query(RepairOnlineSettings).filter_by(branch_id=branch_id).first()
    return {'encrypted_storage_available':repair_access.available(),'settings':{'gateway_id':config.gateway_id,'pos_terminal_id':config.pos_terminal_id,'enabled':config.enabled} if config else None,
            'gateways':[{'id':g.id,'provider':g.provider,'active':g.is_active,'has_merchant':bool(g.merchant_id)} for g in db.query(PaymentGateway).order_by(PaymentGateway.sort)]}


@router.put('/branches/{branch_id}/online-payment',dependencies=[Depends(require_permission('repair','approve')),Depends(require_permission('checks_bank','create'))])
def configure(branch_id:UUID,data:RepairOnlineSettingsIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=svc.configure(db,p,branch_id,data)
    return {'gateway_id':row.gateway_id,'pos_terminal_id':row.pos_terminal_id,'enabled':row.enabled}


@router.get('/cases/{case_id}/online-payments',dependencies=[Depends(require_permission('invoices','view'))])
def payments(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=core.case(db,p,case_id)
    return svc.public_status(db,row)['payments']


@router.post('/cases/{case_id}/online-payments/{intent_id}/post',dependencies=[Depends(require_permission('repair','approve')),Depends(require_permission('checks_bank','create'))])
def account(case_id:UUID,intent_id:UUID,data:VersionIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=core.case(db,p,case_id,lock=True);core.check_version(row,data.version)
    intent=db.query(RepairPaymentIntent).filter_by(case_id=case_id,id=intent_id).with_for_update().one_or_none()
    if intent is None: raise HTTPException(404,'درخواست پرداخت این پرونده پیدا نشد.')
    svc.post_receipt(db,row,intent)
    return {'status':intent.status,'receipt_id':intent.receipt_id}


@public_router.post('/payments',status_code=201)
def start(data:RepairPortalPaymentIn,request:Request,db:Session=Depends(get_db)):
    row,token=authorized(db,request,lock=True)
    intent=portal.once(db,row,token,request,'payment',data.model_dump(mode='json'),lambda:svc.start(db,row,token,data),RepairPaymentIntent)
    return {'id':intent.id,'status':intent.status,'redirect_url':intent.redirect_url if intent.status=='pending' else None}


@callback_router.api_route('/callback/{tenant_id}/{intent_id}',methods=['GET','POST'],response_class=HTMLResponse)
async def callback(tenant_id:UUID,intent_id:UUID,request:Request,db:Session=Depends(get_db)):
    if db.get(Tenant,tenant_id) is None: raise HTTPException(404,'درخواست پرداخت پیدا نشد.')
    # پرداخت در جریان، پس از انقضای لینک یا غیرفعال شدن ماژول نیز باید قابل verify باشد.
    bind_session_tenant(db,tenant_id);apply_tenant_to_transaction(db,tenant_id)
    intent=db.query(RepairPaymentIntent).filter_by(id=intent_id).one_or_none()
    if intent is None: raise HTTPException(404,'درخواست پرداخت پیدا نشد.')
    row=db.query(RepairCase).filter_by(id=intent.case_id).with_for_update().populate_existing().one()
    intent=db.query(RepairPaymentIntent).filter_by(id=intent.id).with_for_update().populate_existing().one()
    params=dict(request.query_params)
    if request.method=='POST': params.update({k:str(v) for k,v in (await request.form()).items()})
    svc.verify(db,row,intent,params)
    message=intent.last_result or 'نتیجهٔ پرداخت هنوز تأیید نشده؛ صفحهٔ پیگیری را تازه کنید.'
    return HTMLResponse('<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="referrer" content="no-referrer"><title>نتیجه پرداخت تعمیرگاه</title><body style="font-family:Tahoma;padding:32px"><h1>نتیجه پرداخت تعمیرگاه</h1><p>'+escape(message)+'</p><p>برای مشاهدهٔ مانده، لینک پیگیری اصلی پرونده را دوباره باز کنید.</p></body></html>',headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff'})
