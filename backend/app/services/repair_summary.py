"""Approved technical text only; no serialization of a former owner's case."""
from types import SimpleNamespace
from fastapi import HTTPException
from app.models.inventory import Contact
from app.models.repair_completion import RepairTechnicalSummary
from app.services import repair as core, repair_identity as identity

FIELDS = ('condition', 'repairs', 'tests', 'care')


def context(db, p, row, *, lock=False):
    main = identity.canonical(db, p, identity.device(db, p, row.device_id))
    main = identity.device(db, p, main.id, lock=lock)
    if identity.canonical(db, p, main).id != main.id:
        raise HTTPException(409, 'هویت دستگاه تغییر کرده؛ پیش‌نمایش را دوباره دریافت کنید.')
    owner = identity.latest(db, p, main.id, 'ownership')
    previous = db.query(RepairTechnicalSummary).filter_by(tenant_id=p.tenant_id, case_id=row.id).order_by(RepairTechnicalSummary.revision.desc()).first()
    return main, owner, previous


def preview(db, p, row):
    main, owner, previous = context(db, p, row)
    contact = db.query(Contact).filter_by(tenant_id=p.tenant_id, id=owner.contact_id).one_or_none() if owner else None
    return {'device_version':main.version, 'ownership_id':owner.id if owner else None,
            'recipient_name':contact.name if contact else '', 'previous_revision':previous.revision if previous else 0}


def approve(db, p, row, data):
    core.check_version(row, data.version)
    main, owner, previous = context(db, p, row, lock=True)
    core.check_version(main, data.device_version)
    if owner is None or owner.id != data.ownership_id or (previous.revision if previous else 0) != data.previous_revision:
        raise HTTPException(409, 'مالکیت یا نسخهٔ خلاصه تغییر کرده؛ پیش‌نمایش تازه لازم است.')
    summary = RepairTechnicalSummary(case_id=row.id, device_id=main.id, ownership_id=owner.id,
        contact_id=owner.contact_id, revision=data.previous_revision+1, content=data.content.model_dump(),
        reason=data.reason, approved_by_id=p.user.id)
    db.add(summary); db.flush()
    core.event(db, p, row, 'technical_summary_approved', {'summary_id':str(summary.id), 'revision':summary.revision})
    return summary


def public(summary):
    return {'id':summary.id, 'revision':summary.revision, 'approved_at':summary.created_at,
            'content':{key:summary.content.get(key, '') for key in FIELDS}}


def for_recipient(db, row):
    # A portal token is scoped to its own case/contact, not to a serial number.
    p = SimpleNamespace(tenant_id=row.tenant_id)
    main = identity.canonical(db, p, identity.device(db, p, row.device_id))
    owner = identity.latest(db, p, main.id, 'ownership')
    if owner is None or owner.contact_id != row.contact_id:
        return []
    # An ownership decision is never reused after a merge or a later transfer.
    rows = db.query(RepairTechnicalSummary).filter_by(tenant_id=row.tenant_id, device_id=main.id,
        ownership_id=owner.id, contact_id=row.contact_id).distinct(RepairTechnicalSummary.case_id).order_by(
        RepairTechnicalSummary.case_id, RepairTechnicalSummary.revision.desc()).limit(200).all()
    return [public(item) for item in rows]
