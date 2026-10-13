import hashlib
import json
from fastapi import HTTPException
from app.models.repair import RepairAttachment
from app.models.repair_completion import RepairIntakeEvidence
from app.services import repair as core
from app.services.repair_completion import metadata, ENDED


def current(db, row):
    return db.query(RepairIntakeEvidence).filter_by(tenant_id=row.tenant_id, case_id=row.id).order_by(RepairIntakeEvidence.revision.desc()).first()


def save(db, p, row, data):
    core.check_version(row, data.version)
    if row.status in ENDED:
        raise HTTPException(409, 'پذیرش نهایی‌شده قابل تغییر نیست؛ از مسیر مراجعهٔ مجدد استفاده کنید.')
    previous = current(db, row)
    if data.previous_revision != (previous.revision if previous else 0):
        raise HTTPException(409, 'نسخهٔ تصاویر یا آزمون‌ها تغییر کرده؛ آخرین نسخه را دریافت کنید.')
    images = []
    for image in data.images:
        attachment = db.query(RepairAttachment).filter_by(tenant_id=p.tenant_id, case_id=row.id, id=image.attachment_id).one_or_none()
        if attachment is None or attachment.content_type not in ('image/jpeg', 'image/png'):
            raise HTTPException(422, 'تصویر باید پیوست JPEG یا PNG همین پرونده باشد؛ ابتدا تصویر را بارگذاری کنید.')
        images.append({**image.model_dump(mode='json'), 'sha256': attachment.sha256})
    snapshot = {'device': row.device_snapshot, 'accessories': [a.model_dump() for a in data.accessories],
                'tests': [t.model_dump() for t in data.tests], 'images': images}
    result = RepairIntakeEvidence(case_id=row.id, revision=data.previous_revision + 1, snapshot=snapshot,
        document_hash=hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        reason=data.reason, recorded_by_id=p.user.id)
    db.add(result)
    metadata(db, row, create=True).receipt_revision += 1
    core.event(db, p, row, 'intake_evidence_recorded', {'revision': result.revision, 'document_hash': result.document_hash, 'reason': data.reason})
    db.flush()
    return result
