"""صف تراکنشی؛ ارسال بیرون تراکنش درخواست و هرگز با موفقیت شبیه‌سازی‌شده."""
from datetime import date, datetime, timedelta, timezone
from string import Formatter
from fastapi import HTTPException
from app.config import get_settings
from app.models.repair import RepairCase, RepairMessageTemplate, RepairNotification, RepairNotificationAttempt
from app.models.tenant import Tenant
from app.services import repair as core, sms
from app.services.modules import is_module_visible
from app.tenant_context import tenant_scope

FIELDS = {'number','customer','device','status','due_date','company','branch'}
KINDS = {'admission','approval','due','ready'}


def configured():
    settings = get_settings()
    return bool(settings.melipayamak_api_key and settings.melipayamak_sender)


def validate_body(body):
    try:
        for _, field, spec, conversion in Formatter().parse(body):
            if field is not None and (field not in FIELDS or spec or conversion):
                raise ValueError()
    except ValueError:
        raise HTTPException(422,'متغیر پیام معتبر نیست؛ فقط number، customer، device، status، due_date، company و branch مجازند.')


def save_template(db,p,data):
    validate_body(data.body)
    # قفل شرکت، ایجاد همزمان نسخهٔ اول یا الگوی عمومی را نیز سری می‌کند.
    db.query(Tenant).filter_by(id=p.tenant_id).with_for_update().one()
    if data.branch_id: core.branch(db,p,data.branch_id)
    scope=str(data.branch_id) if data.branch_id else 'company'
    old=db.query(RepairMessageTemplate).filter_by(scope=scope,kind=data.kind).order_by(RepairMessageTemplate.version.desc()).first()
    row=RepairMessageTemplate(**data.model_dump(),scope=scope,version=old.version+1 if old else 1,created_by_id=p.user.id)
    db.add(row);db.flush()
    return row


def template(db,row,kind):
    branch=db.query(RepairMessageTemplate).filter_by(scope=str(row.branch_id),kind=kind).order_by(RepairMessageTemplate.version.desc()).first()
    chosen=branch or db.query(RepairMessageTemplate).filter_by(scope='company',kind=kind).order_by(RepairMessageTemplate.version.desc()).first()
    return chosen if chosen and chosen.enabled else None


def enqueue(db,row,kind,marker,*,strict=False):
    chosen=template(db,row,kind)
    if chosen is None:
        if strict: raise HTTPException(409,'الگوی فعال این اعلان تنظیم نشده؛ ابتدا الگوی شرکت یا شعبه را ثبت کنید.')
        return None
    key=f'{row.id}:{kind}:{marker}'
    existing=db.query(RepairNotification).filter_by(dedupe_key=key).first()
    if existing: return existing
    from app.models.repair import RepairBranch
    from app.services.printing import format_jalali
    tenant=db.get(Tenant,row.tenant_id)
    branch=db.get(RepairBranch,row.branch_id)
    values={'number':str(row.number).translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹')),
            'customer':row.owner_snapshot.get('name',''),'device':row.device_snapshot.get('model',''),
            'status':core.STATE_LABELS[row.status], 'due_date':format_jalali(row.due_date) if row.due_date else 'تعیین نشده',
            'company':tenant.name,'branch':branch.name}
    body=chosen.body.format_map(values)
    too_long=len(body)>2000
    if too_long and strict: raise HTTPException(422,'متن نهایی اعلان طولانی است؛ الگو را کوتاه‌تر کنید.')
    phone=sms.normalize_phone(row.owner_snapshot.get('phone'))
    available=configured() and phone is not None and not too_long
    message=RepairNotification(case_id=row.id,kind=kind,dedupe_key=key,template_id=chosen.id,
        recipient=phone or '',body=body,status='queued' if available else 'unavailable',
        last_result='' if available else ('متن نهایی طولانی است؛ الگو را کوتاه و اعلان تازه ثبت کنید.' if too_long else 'شمارهٔ موبایل مشتری معتبر نیست.' if phone is None else 'سرویس واقعی پیامک تنظیم نشده است.'))
    db.add(message);db.flush()
    return message


def from_event(db,row,action):
    kind={'admitted':'admission','estimate_created':'approval'}.get(action)
    if action=='status_changed' and row.status=='ready': kind='ready'
    if kind: enqueue(db,row,kind,str(row.version))


def retry(db,p,row,message,data):
    core.check_version(row,data.version)
    if message.status not in {'uncertain','unavailable'}:
        raise HTTPException(409,'فقط ارسال نامعلوم یا در دسترس نبودن سرویس قابل تلاش دوباره است.')
    if message.status=='uncertain' and not data.acknowledge_duplicate_risk:
        raise HTTPException(422,'ممکن است حامل پیام قبلی را پذیرفته باشد؛ خطر پیام تکراری را صریحاً تأیید کنید.')
    if not configured(): raise HTTPException(503,'سرویس واقعی پیامک هنوز تنظیم نشده؛ هیچ ارسالی انجام نشد.')
    if len(message.body)>2000: raise HTTPException(422,'متن قبلی طولانی است؛ الگو را کوتاه و اعلان تازه ثبت کنید.')
    phone=sms.normalize_phone(row.owner_snapshot.get('phone'))
    if not phone: raise HTTPException(422,'شمارهٔ موبایل صاحب پرونده معتبر نیست؛ اطلاعات پذیرش را بررسی کنید.')
    message.recipient=phone;message.status='queued';message.claimed_at=None;message.last_result='تلاش دوباره با تأیید کاربر در صف قرار گرفت.'
    core.event(db,p,row,'notification_retry',{'notification_id':str(message.id),'reason':data.reason,'duplicate_risk':data.acknowledge_duplicate_risk})
    return message


def process_one(session_factory,tenant_id,*,sender=None):
    """یک تلاش واقعی. commit پیش از I/O مانع ارسالِ رکوردِ rollback‌شده می‌شود.

    حامل API یکتاسازی ندارد؛ قطع فرایند حین ارسال «نامعلوم» است، نه retry خودکار.
    sender فقط برای آزمون تزریق می‌شود؛ CLI همیشه حامل واقعی را فراخوانی می‌کند.
    """
    now=datetime.now(timezone.utc)
    with session_factory() as db, tenant_scope(db,tenant_id):
        tenant=db.get(Tenant,tenant_id)
        if not tenant or tenant.status!='active' or not is_module_visible(tenant,'repair'): return False
        stale=db.query(RepairNotification).filter(RepairNotification.status=='sending',RepairNotification.claimed_at<now-timedelta(minutes=5)).with_for_update(skip_locked=True).all()
        for old in stale:
            old.status='uncertain';old.last_result='فرایند ارسال قطع شد؛ نتیجهٔ حامل نامعلوم است و ارسال خودکار تکرار نمی‌شود.'
            attempt=db.query(RepairNotificationAttempt).filter_by(notification_id=old.id,number=old.attempt_count).one()
            attempt.outcome='uncertain';attempt.result=old.last_result;attempt.finished_at=now
        message=db.query(RepairNotification).filter_by(status='queued').order_by(RepairNotification.created_at,RepairNotification.id).with_for_update(skip_locked=True).first()
        if message is None: db.commit();return False
        if not configured():
            message.status='unavailable';message.last_result='سرویس واقعی پیامک تنظیم نشده است.';db.commit();return True
        message.status='sending';message.claimed_at=now;message.attempt_count+=1
        attempt=RepairNotificationAttempt(notification_id=message.id,number=message.attempt_count,outcome='sending',result='تلاش شروع شد.')
        db.add(attempt);db.flush()
        message_id,attempt_id,phone,body=message.id,attempt.id,message.recipient,message.body
        db.commit()
    # هیچ استثنا/URL حامل یا متن محرمانه در جدول نتیجه و لاگ ذخیره نمی‌شود.
    try: accepted=bool((sender or sms.send_text)(phone,body))
    except Exception: accepted=False
    with session_factory() as db, tenant_scope(db,tenant_id):
        message=db.query(RepairNotification).filter_by(id=message_id).with_for_update().one()
        attempt=db.get(RepairNotificationAttempt,attempt_id)
        outcome='accepted' if accepted else 'uncertain'
        result='حامل پیام را پذیرفت؛ تحویل به گوشی تأیید نشده است.' if accepted else 'پذیرش حامل تأیید نشد؛ برای جلوگیری از تکرار، بررسی و تلاش دستی لازم است.'
        # نتیجهٔ دیررس تلاش قدیمی، وضعیت retry تأییدشدهٔ تازه را بازنویسی نمی‌کند.
        if message.attempt_count==attempt.number and message.status in {'sending','uncertain'}:
            message.status=outcome;message.last_result=result
        attempt.outcome=outcome;attempt.result=result;attempt.finished_at=datetime.now(timezone.utc)
        db.commit()
    return True


def enqueue_due(db,tenant_id):
    rows=db.query(RepairCase).filter(RepairCase.due_date<=date.today(),RepairCase.status.notin_(['cancelled','delivered','closed','ready'])).order_by(RepairCase.id).with_for_update().all()
    for row in rows: enqueue(db,row,'due',date.today().isoformat())
    return len(rows)
