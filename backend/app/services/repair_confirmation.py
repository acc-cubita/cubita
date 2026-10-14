"""Codes are purpose/document bound; development SMS simulation is never success."""
import hashlib
import hmac
import json
import secrets
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from app.config import get_settings
from app.models.inventory import Contact
from app.models.repair_completion import RepairConfirmation
from app.services import repair as core,repair_completion,repair_finance
from app.services.sms import normalize_phone


def now():
    return datetime.now(timezone.utc)


def required(db,row,kind):
    meta=repair_completion.metadata(db,row)
    return bool(meta and meta.settings_snapshot.get(kind+'_confirmation_policy')=='otp')


def digest(value):
    secret=get_settings().jwt_secret
    if len(secret)<32:
        raise HTTPException(503,'کلید امن سرور برای تأیید تعمیرگاه تنظیم نشده؛ مدیر سرور تنظیمات را کامل کند.')
    return hmac.new(secret.encode(),('repair-confirmation-v1:'+value).encode(),hashlib.sha256).hexdigest()


def code_digest(row,code):
    return digest('|'.join(map(str,[row.tenant_id,row.case_id,row.id,row.kind,row.recipient_phone,row.document_hash,code])))


def send_code(phone,code):
    # Do not call the legacy sender's development fallback: it logs raw codes.
    from app.services import sms
    settings=get_settings()
    if not settings.repair_otp_enabled or not settings.melipayamak_api_key or not settings.melipayamak_otp_pattern_id:
        return False
    return sms.send_verification_code(phone,code)


def snapshot(db,p,row,data):
    phone=normalize_phone(data.recipient_phone)
    if not phone:
        raise HTTPException(422,'شمارهٔ همراه معتبر گیرنده را وارد کنید.')
    if data.recipient_contact_id:
        person=db.query(Contact).filter_by(tenant_id=p.tenant_id,id=data.recipient_contact_id,is_active=True,is_system=False).one_or_none()
        if person is None:
            raise HTTPException(422,'گیرنده را از اشخاص فعال همین شرکت انتخاب کنید.')
    revision,document=repair_completion.document(db,row,'intake')
    body={'kind':data.kind,'recipient_name':data.recipient_name,'recipient_phone':phone,
          'recipient_contact_id':str(data.recipient_contact_id) if data.recipient_contact_id else None,
          'authority_evidence':data.authority_evidence,'intake_revision':revision,'intake_document':document}
    if data.representation_id:
        from app.services.repair_representation import validate
        validate(db,row,data.representation_id,data.kind,data.recipient_name,phone,data.recipient_contact_id)
        body['representation_id']=str(data.representation_id)
    if data.kind=='delivery':
        delivery=data.delivery
        if delivery.receiver_name!=data.recipient_name or normalize_phone(delivery.receiver_phone)!=phone:
            raise HTTPException(422,'گیرندهٔ تأیید باید همان گیرندهٔ سند تحویل باشد.')
        repair_finance.validate_delivery(db,p,row,delivery)
        body.update(delivery=delivery.model_dump(mode='json',exclude={'version','confirmation_id'}),work_version=row.work_version,
                    financial=jsonable_encoder(repair_finance.financial(db,row)))
    return body


def document_hash(document):
    return hashlib.sha256(json.dumps(document,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def request(db,p,row,data):
    core.check_version(row,data.version)
    if data.kind=='intake' and row.status in repair_completion.ENDED:
        raise HTTPException(409,'پرونده پایان یافته است؛ تأیید پذیرش تازه برای آن ثبت نمی‌شود.')
    document=snapshot(db,p,row,data)
    at=now()
    recent=db.query(RepairConfirmation).filter(RepairConfirmation.tenant_id==p.tenant_id,
        RepairConfirmation.case_id==row.id,RepairConfirmation.method=='sms',RepairConfirmation.created_at>=at-timedelta(minutes=15)).order_by(RepairConfirmation.created_at.desc()).all()
    if recent and (at-recent[0].created_at).total_seconds()<60:
        raise HTTPException(429,'از درخواست قبلی کمتر از ۶۰ ثانیه گذشته؛ کمی بعد دوباره تلاش کنید.')
    if len(recent)>=3:
        raise HTTPException(429,'سقف سه درخواست در پانزده دقیقه پر شده؛ پس از پایان این بازه تلاش کنید.')
    record=RepairConfirmation(id=uuid4(),tenant_id=p.tenant_id,case_id=row.id,kind=data.kind,
        recipient_name=data.recipient_name,recipient_phone=document['recipient_phone'],recipient_contact_id=data.recipient_contact_id,
        authority_evidence=data.authority_evidence,document_snapshot=document,document_hash=document_hash(document),
        expires_at=at+timedelta(minutes=5),requested_by_id=p.user.id)
    code=f'{secrets.randbelow(1000000):06d}'
    record.code_hash=code_digest(record,code)
    db.add(record);db.flush()
    # Keep failure as a committed result. Throwing here would erase rate-limit history.
    try:
        sent=send_code(record.recipient_phone,code)
    except Exception:
        sent=False
    record.status='sent' if sent else 'failed'
    record.sent_at=at if sent else None
    core.event(db,p,row,'confirmation_requested',{'confirmation_id':str(record.id),'kind':record.kind,'status':record.status,'document_hash':record.document_hash})
    db.flush()
    return record


def get(db,p,case_id,confirmation_id,*,lock=False):
    query=db.query(RepairConfirmation).filter_by(tenant_id=p.tenant_id,case_id=case_id,id=confirmation_id)
    if lock:query=query.with_for_update().populate_existing()
    row=query.one_or_none()
    if row is None:raise HTTPException(404,'درخواست تأیید متعلق به این پرونده پیدا نشد.')
    return row


def public(record):
    state=record.status
    if state in {'sent','verified'} and record.expires_at<=now():state='expired'
    return {'id':record.id,'version':record.version,'kind':record.kind,'method':record.method,'status':state,'attempts_remaining':5-record.attempts,
            'expires_at':record.expires_at.astimezone(timezone.utc),'document_hash':record.document_hash,
            'message':'ارسال انجام نشد؛ تنظیم سرویس واقعی و اعتبار پیامک را بررسی کنید.' if state=='failed' else ''}


def verify(db,p,case_id,confirmation_id,data):
    record=get(db,p,case_id,confirmation_id,lock=True)
    core.check_version(record,data.version)
    if record.status not in {'sent','verified'}:
        return record
    if record.expires_at<=now():
        record.status='expired';record.version+=1;db.flush();return record
    if record.status=='verified':return record
    record.attempts+=1;record.version+=1
    if hmac.compare_digest(record.code_hash,code_digest(record,data.code.get_secret_value())):
        record.status='verified';record.verified_at=now()
    elif record.attempts>=5:
        record.status='locked'
    db.flush()
    return record


def consume_delivery(db,p,row,data):
    from app.schemas.repair_confirmation import ConfirmationRequestIn
    record=get(db,p,row.id,data.confirmation_id,lock=True)
    if record.kind!='delivery' or record.status!='verified' or record.expires_at<=now():
        raise HTTPException(409,'تأیید معتبر تحویل موجود نیست؛ نسخهٔ فعلی و گیرنده را دوباره تأیید کنید.')
    request_data=ConfirmationRequestIn(version=row.version,kind='delivery',recipient_name=record.recipient_name,
        recipient_phone=record.recipient_phone,recipient_contact_id=record.recipient_contact_id,
        authority_evidence=record.authority_evidence,delivery=data,representation_id=record.document_snapshot.get('representation_id'))
    if not hmac.compare_digest(record.document_hash,document_hash(snapshot(db,p,row,request_data))):
        raise HTTPException(409,'سند، گیرنده یا وضعیت مالی تغییر کرده؛ تأیید تازه بگیرید.')
    record.status='consumed';record.consumed_at=now();record.version+=1
    db.flush()


def consume_intake(db,p,row,confirmation_id,data):
    from app.models.repair_completion import RepairAcknowledgment
    from app.schemas.repair_confirmation import ConfirmationRequestIn
    core.check_version(row,data.version)
    record=get(db,p,row.id,confirmation_id,lock=True)
    if record.kind!='intake' or record.status!='verified' or record.expires_at<=now():
        raise HTTPException(409,'تأیید معتبر پذیرش موجود نیست؛ کد تازه درخواست کنید.')
    values=ConfirmationRequestIn(version=row.version,kind='intake',recipient_name=record.recipient_name,
        recipient_phone=record.recipient_phone,recipient_contact_id=record.recipient_contact_id,authority_evidence=record.authority_evidence,
        representation_id=record.document_snapshot.get('representation_id'))
    if record.document_hash!=document_hash(snapshot(db,p,row,values)):
        raise HTTPException(409,'نسخهٔ پذیرش تغییر کرده؛ تأیید تازه لازم است.')
    revision,document=repair_completion.document(db,row,'intake')
    if db.query(RepairAcknowledgment).filter_by(case_id=row.id,kind='intake',document_revision=revision).first():
        raise HTTPException(409,'این نسخه قبلاً تأیید شده است؛ تأیید قبلی بازنویسی نمی‌شود.')
    document={**document,'confirmation':{'method':'sms','id':str(record.id),'document_hash':record.document_hash}}
    acknowledgment=RepairAcknowledgment(case_id=row.id,kind='intake',document_revision=revision,signer_name=record.recipient_name,
        signer_relation='گیرنده مجاز؛ مدرک اختیار در تأیید نسخه‌دار ثبت است',strokes=[],document_snapshot=document,document_hash=document_hash(document),confirmed_by_id=p.user.id)
    db.add(acknowledgment)
    record.status='consumed';record.consumed_at=now();record.version+=1
    core.event(db,p,row,'intake_confirmed_by_sms',{'confirmation_id':str(record.id),'revision':revision})
    db.flush()
    return record


def signature_override(db,p,row,data):
    from app.models.repair_completion import RepairAcknowledgment
    if not p.has_permission('repair_confirmation_override','approve'):
        raise HTTPException(403,'تأیید جایگزین به مجوز مستقل مدیر نیاز دارد.')
    core.check_version(row,data.version)
    if data.kind=='intake' and row.status in repair_completion.ENDED:
        raise HTTPException(409,'برای پروندهٔ پایان‌یافته تأیید پذیرش تازه ثبت نمی‌شود.')
    body=snapshot(db,p,row,data)
    hash_value=document_hash(body)
    if not hmac.compare_digest(hash_value,data.expected_document_hash):
        raise HTTPException(409,'نسخهٔ قابل امضا تغییر کرده؛ پیش‌نمایش را دوباره دریافت کنید.')
    ack=data.acknowledgment
    if ack.kind!=data.kind or ack.version!=data.version or ack.signer_name!=data.recipient_name:
        raise HTTPException(422,'هویت امضاکننده و عملیات باید با نسخهٔ پیش‌نمایش برابر باشد.')
    revision=body['intake_revision'] if data.kind=='intake' else row.version
    if db.query(RepairAcknowledgment).filter_by(case_id=row.id,kind=data.kind,document_revision=revision).first():
        raise HTTPException(409,'این نسخه قبلاً تأیید شده است؛ تأیید قبلی محفوظ می‌ماند.')
    signature=RepairAcknowledgment(case_id=row.id,kind=data.kind,document_revision=revision,
        signer_name=ack.signer_name,signer_relation=ack.signer_relation,strokes=jsonable_encoder(ack.strokes),
        document_snapshot=body,document_hash=hash_value,confirmed_by_id=p.user.id)
    db.add(signature);db.flush()
    at=now()
    record=RepairConfirmation(case_id=row.id,kind=data.kind,method='signature_override',signature_ack_id=signature.id,
        recipient_name=data.recipient_name,recipient_phone=body['recipient_phone'],recipient_contact_id=data.recipient_contact_id,
        authority_evidence=data.authority_evidence,document_snapshot=body,document_hash=hash_value,code_hash='',
        expires_at=at+timedelta(minutes=5),requested_by_id=p.user.id,status='consumed' if data.kind=='intake' else 'verified',
        verified_at=at,consumed_at=at if data.kind=='intake' else None,override_reason=data.override_reason)
    db.add(record);db.flush()
    core.event(db,p,row,'confirmation_override',{'confirmation_id':str(record.id),'kind':record.kind,'reason':data.override_reason,'document_hash':hash_value})
    return record
