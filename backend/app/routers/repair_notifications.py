from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal, get_principal, require_module, require_permission
from app.models.repair import RepairEstimate, RepairMessageTemplate, RepairNotification, RepairNotificationAttempt
from app.schemas.repair import RepairTemplateIn, RepairNotifyIn, RepairRetryIn, VersionIn
from app.services import repair as core, repair_notifications as svc
from app.routers.repair_operations import once

router=APIRouter(prefix='/api/repair',tags=['repair'],dependencies=[Depends(require_module('repair')),Depends(require_permission('repair','view'))])


def message(db,case_id,rid,*,lock=False):
    query=db.query(RepairNotification).filter_by(case_id=case_id,id=rid)
    row=query.with_for_update().populate_existing().one_or_none() if lock else query.one_or_none()
    if row is None: raise HTTPException(404,'اعلان مربوط به این پرونده پیدا نشد.')
    return row


@router.get('/message-templates',dependencies=[Depends(require_permission('repair','approve'))])
def templates(db:Session=Depends(get_db)):
    return [core.out(t) for t in db.query(RepairMessageTemplate).order_by(RepairMessageTemplate.created_at.desc()).limit(200).all()]


@router.post('/message-templates',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def save_template(data:RepairTemplateIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return core.out(svc.save_template(db,p,data))


@router.get('/cases/{case_id}/notifications')
def notifications(case_id:UUID,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    rows=db.query(RepairNotification).filter_by(case_id=case_id).order_by(RepairNotification.created_at.desc(),RepairNotification.id).limit(200).all()
    attempts=db.query(RepairNotificationAttempt).filter(RepairNotificationAttempt.notification_id.in_([r.id for r in rows])).order_by(RepairNotificationAttempt.number).all() if rows else []
    return {'sms_available':svc.configured(),'messages':[{**core.out(r),'attempts':[core.out(a) for a in attempts if a.notification_id==r.id]} for r in rows]}


@router.post('/cases/{case_id}/notifications',status_code=201,dependencies=[Depends(require_permission('repair','update'))])
def queue(case_id:UUID,data:RepairNotifyIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    core.case(db,p,case_id)
    def run():
        row=core.case(db,p,case_id,lock=True);core.check_version(row,data.version)
        if data.kind=='ready' and row.status!='ready': raise HTTPException(409,'دستگاه هنوز آمادهٔ تحویل نیست؛ پیام آماده بودن ارسال نمی‌شود.')
        if data.kind=='approval' and not db.query(RepairEstimate).filter_by(case_id=row.id).first():
            raise HTTPException(409,'برای درخواست تأیید، ابتدا برآورد ثبت کنید.')
        result=svc.enqueue(db,row,data.kind,'manual:'+str(row.version),strict=True)
        core.event(db,p,row,'notification_queued',{'notification_id':str(result.id),'kind':data.kind})
        return result
    return core.out(once(db,request,p,'repair.notification:'+str(case_id),data,run,lambda rid:message(db,case_id,rid)))


@router.post('/cases/{case_id}/notifications/{notification_id}/retry',dependencies=[Depends(require_permission('repair','approve'))])
def retry(case_id:UUID,notification_id:UUID,data:RepairRetryIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=core.case(db,p,case_id,lock=True)
    return core.out(svc.retry(db,p,row,message(db,case_id,notification_id,lock=True),data))


@router.post('/cases/{case_id}/notifications/{notification_id}/cancel',dependencies=[Depends(require_permission('repair','approve'))])
def cancel(case_id:UUID,notification_id:UUID,data:VersionIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=core.case(db,p,case_id,lock=True);core.check_version(row,data.version)
    notice=db.query(RepairNotification).filter_by(case_id=case_id,id=notification_id).with_for_update().one_or_none()
    if notice is None: raise HTTPException(404,'اعلان مربوط به پرونده پیدا نشد.')
    if notice.status not in {'queued','unavailable'}: raise HTTPException(409,'ارسال شروع‌شده یا نامعلوم قابل لغو قطعی نیست؛ نتیجه را بررسی کنید.')
    notice.status='cancelled';notice.last_result='کاربر ارسال صف‌شده را لغو کرد.'
    core.event(db,p,row,'notification_cancelled',{'notification_id':str(notice.id)})
    return core.out(notice)
