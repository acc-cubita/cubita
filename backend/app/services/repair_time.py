"""Server time survives browser closure; never creates a financial charge."""
from datetime import datetime, timezone
from fastapi import HTTPException
from app.models.tenant import Membership
from app.models.repair_completion import RepairTimeSession, RepairTimeCorrection
from app.services import repair as core
from app.services.repair_completion import ENDED


def view(db,p,session_id,lock=False):
    query=db.query(RepairTimeSession).filter_by(id=session_id)
    session=(query.with_for_update() if lock else query).one_or_none()
    if session is None: raise HTTPException(404,'بازهٔ کار پیدا نشد.')
    core.case(db,p,session.case_id)
    if session.technician_id!=p.user.id: raise HTTPException(403,'زمان نهایی را همان تکنسین تأیید می‌کند.')
    return session


def start(db,p,row,data):
    core.check_version(row,data.version)
    if row.status in ENDED: raise HTTPException(409,'تایمر پروندهٔ پایان‌یافته شروع نمی‌شود.')
    if row.assigned_to_id!=p.user.id and not p.has_permission('repair','approve'):
        raise HTTPException(403,'پرونده به شما تخصیص داده نشده است.')
    db.query(Membership).filter_by(tenant_id=p.tenant_id,user_id=p.user.id).with_for_update().one()
    if db.query(RepairTimeSession.id).filter_by(technician_id=p.user.id,stopped_at=None).first():
        raise HTTPException(409,'ابتدا تایمر فعال خود را متوقف کنید.')
    session=RepairTimeSession(case_id=row.id,technician_id=p.user.id,started_at=datetime.now(timezone.utc))
    db.add(session);db.flush()
    core.event(db,p,row,'time_started',{'session_id':str(session.id)})
    return session


def change(db,p,session_id,data):
    session=view(db,p,session_id,lock=True)
    core.check_version(session,data.version)
    now=datetime.now(timezone.utc)
    if data.action=='stop':
        if session.stopped_at is not None: raise HTTPException(409,'این تایمر قبلاً متوقف شده است.')
        session.stopped_at=now
    else:
        if session.stopped_at is None: raise HTTPException(409,'ابتدا تایمر را متوقف کنید.')
        if data.action=='confirm' and session.confirmed_at is not None: raise HTTPException(409,'زمان قبلاً تأیید شده؛ اصلاح با دلیل ثبت کنید.')
        if data.action=='correct' and session.confirmed_at is None: raise HTTPException(409,'ابتدا زمان نهایی را تأیید کنید.')
        actual=max(0,int((session.stopped_at-session.started_at).total_seconds()))
        if data.seconds!=actual and not data.reason.strip(): raise HTTPException(422,'تفاوت با زمان سرور دلیل لازم دارد.')
        correction=RepairTimeCorrection(session_id=session.id,session_version=session.version+1,old_seconds=session.confirmed_seconds,new_seconds=data.seconds,reason=data.reason,recorded_by_id=p.user.id)
        db.add(correction)
        session.confirmed_seconds=data.seconds;session.confirmed_at=now
    session.version+=1
    db.flush()
    return session


def out(row):
    result=core.out(row)
    result['elapsed_seconds']=max(0,int(((row.stopped_at or datetime.now(timezone.utc))-row.started_at).total_seconds()))
    return result
