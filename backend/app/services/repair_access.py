"""رمز دستگاه هرگز از تابع عمومی detail/receipt عبور نمی‌کند؛ بدون کلید، ذخیره ممنوع است."""
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from app import secrets_at_rest
from app.models.repair import RepairDeviceSecret, RepairEvent
from app.services import repair as core


def available():
    return secrets_at_rest.is_encrypted(secrets_at_rest.encrypt('capability-probe'))


def purge_expired(db, *, limit=200):
    """Bounded tenant-scoped cleanup, independent of reads and module visibility."""
    if not 1 <= limit <= 200:
        raise ValueError('limit must be between 1 and 200')
    rows = db.query(RepairDeviceSecret).filter(RepairDeviceSecret.expires_at <= datetime.now(timezone.utc)).order_by(RepairDeviceSecret.expires_at, RepairDeviceSecret.id).with_for_update(skip_locked=True).limit(limit).all()
    for secret in rows:
        db.add(RepairEvent(case_id=secret.case_id, actor_id=secret.created_by_id, action='device_secret_expired', detail={'automatic': True}))
        db.delete(secret)
    db.flush()
    return len(rows)


def expire(db,p,row):
    secret = db.query(RepairDeviceSecret).filter_by(case_id=row.id).first()
    if secret and secret.expires_at <= datetime.now(timezone.utc):
        db.delete(secret)
        db.add(RepairEvent(case_id=row.id,actor_id=p.user.id,action='device_secret_expired',detail={}))
        db.flush()
        return None
    return secret


def set_secret(db,p,row,data):
    core.check_version(row,data.version);core.editable_case(row)
    if row.status == 'ready': raise HTTPException(409,'پس از پایان نیاز تعمیر، رمز دستگاه نگهداری نمی‌شود.')
    ciphertext = secrets_at_rest.encrypt(data.secret.get_secret_value())
    if not ciphertext or not secrets_at_rest.is_encrypted(ciphertext):
        raise HTTPException(503,'کلید حفاظت اطلاعات روی سرور تنظیم نشده؛ رمز دستگاه ذخیره نشد. مدیر سرور باید SECRETS_KEY را تنظیم کند.')
    secret = db.query(RepairDeviceSecret).filter_by(case_id=row.id).first()
    if secret is None:
        secret = RepairDeviceSecret(case_id=row.id,created_by_id=p.user.id)
        db.add(secret)
    secret.ciphertext = ciphertext
    secret.expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_days)
    core.event(db,p,row,'device_secret_set',{'expires_days':data.expires_days})
    return {'stored':True,'expires_at':secret.expires_at}


def reveal(db,p,row,data):
    secret = expire(db,p,row)
    if secret is None: raise HTTPException(404,'رمز دستگاه وجود ندارد یا مهلت نگهداری آن تمام شده است.')
    try: value = secrets_at_rest.decrypt(secret.ciphertext)
    except secrets_at_rest.SecretUnreadable: raise HTTPException(503,'رمز با کلید فعلی سرور باز نمی‌شود؛ مدیر سرور باید کلید حفاظت را بررسی کند.')
    db.add(RepairEvent(case_id=row.id,actor_id=p.user.id,action='device_secret_viewed',detail={'reason':data.reason}))
    db.flush()
    return {'secret':value,'expires_at':secret.expires_at}


def clear(db,p,row,data):
    core.check_version(row,data.version)
    db.query(RepairDeviceSecret).filter_by(case_id=row.id).delete(synchronize_session=False)
    core.event(db,p,row,'device_secret_deleted',{})
    return {'deleted':True}
