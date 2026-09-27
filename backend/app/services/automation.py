"""مرزِ دسترسیِ نامه در یک جا: نامه، سابقه و فایل همگی از همین در می‌گذرند."""
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.deps import Principal
from app.models.automation import OfficeAttachment, OfficeEvent, OfficeLetter, OfficeReferral
from app.models.tenant import Membership
from app.models.user import User
from app.schemas.automation import ReferralIn
from app.services.numbering import next_document_number

MAX_FILE = 5 * 1024 * 1024
MAX_TOTAL = 20 * 1024 * 1024
KINDS = {"incoming": "وارده", "outgoing": "صادره", "internal": "داخلی"}


def now():
    return datetime.now(timezone.utc)


def is_manager(p: Principal) -> bool:
    return p.has_permission("automation", "approve")


def visible_query(db: Session, p: Principal):
    query = db.query(OfficeLetter).filter(OfficeLetter.tenant_id == p.tenant_id)
    if not is_manager(p):
        participation = db.query(OfficeReferral.id).filter(
            OfficeReferral.tenant_id == p.tenant_id,
            OfficeReferral.letter_id == OfficeLetter.id,
            or_(OfficeReferral.to_user_id == p.user.id, OfficeReferral.from_user_id == p.user.id),
        ).exists()
        query = query.filter(or_(OfficeLetter.created_by_id == p.user.id, participation))
    return query


def letter(db: Session, p: Principal, letter_id: UUID, *, lock=False):
    query = visible_query(db, p).filter(OfficeLetter.id == letter_id)
    if lock:
        query = query.with_for_update().populate_existing()
    row = query.first()
    if row is None:
        raise HTTPException(404, "نامه یافت نشد یا دسترسی به آن ندارید.")
    return row


def assert_editor(row, p):
    if row.created_by_id != p.user.id and not is_manager(p):
        raise HTTPException(403, "ویرایش و بایگانی فقط برای ثبت‌کننده یا مسئول دبیرخانه مجاز است.")


def assert_draft(row, p):
    assert_editor(row, p)
    if row.status != "draft":
        raise HTTPException(409, "نامه ثبت قطعی شده؛ متن و پیوست‌های آن قابل تغییر نیستند.")


def check_version(row, version):
    if row.version != version:
        raise HTTPException(409, "نامه هم‌زمان تغییر کرده است؛ آن را دوباره باز کنید.")


def event(db, p, row, action, description=""):
    db.add(OfficeEvent(letter_id=row.id, actor_id=p.user.id, action=action, description=description))


def create(db, p, data):
    row = OfficeLetter(**data.model_dump(exclude={"sender"}), sender=p.user.name, created_by_id=p.user.id)
    db.add(row)
    db.flush()
    event(db, p, row, "created", "پیش‌نویس ساخته شد.")
    db.flush()
    return row


def update(db, p, letter_id, data):
    row = letter(db, p, letter_id, lock=True)
    assert_draft(row, p)
    check_version(row, data.version)
    # نام فرستنده عکسِ حسابِ سازنده است، نه متنِ دلخواهِ ویرایشگرِ پیش‌نویس.
    for key, value in data.model_dump(exclude={"version", "sender"}).items():
        setattr(row, key, value)
    row.version += 1
    event(db, p, row, "edited", "پیش‌نویس ویرایش شد.")
    db.flush()
    return row


def register(db, p, letter_id, version):
    row = letter(db, p, letter_id, lock=True)
    assert_editor(row, p)
    # تکرارِ همان درخواست شمارهٔ دوم نمی‌گیرد.
    if row.status != "draft":
        return row
    check_version(row, version)
    row.number = next_document_number(db, f"office_{row.kind}")
    row.status = "registered"
    row.registered_at = now()
    row.version += 1
    event(db, p, row, "registered", f"نامهٔ {KINDS[row.kind]} شمارهٔ {row.number} ثبت قطعی شد.")
    db.flush()
    return row


def recipients(db, p):
    memberships = db.query(Membership).join(User).filter(
        Membership.tenant_id == p.tenant_id, Membership.status == "active", User.active.is_(True),
        or_(Membership.expires_at.is_(None), Membership.expires_at > now()),
    ).order_by(User.name, User.id).all()
    # عنوانِ نقش برای جست‌وجوی «مدیر» لازم است؛ ایمیل و تلفن در دفتر همکاران نیست.
    return [{"id": m.user_id, "name": m.user.name, "role_name": m.role.name} for m in memberships
            if m.role.key not in {"demo", "auditor"}]


def send(db, p, letter_id, data):
    row = letter(db, p, letter_id, lock=True)
    assert_draft(row, p)
    check_version(row, data.version)
    recipient = next((r for r in recipients(db, p) if r["id"] == data.recipient_id), None)
    if recipient is None:
        raise HTTPException(400, "گیرنده باید کاربر فعال همین کسب‌وکار باشد؛ فهرست را تازه‌سازی کنید.")
    # نام برای چاپ snapshot می‌شود؛ شناسهٔ واقعی در ارجاع می‌ماند. ثبت و ارجاع
    # در یک تراکنش‌اند تا شمارهٔ قطعی بدونِ گیرنده جا نماند.
    row.addressee = recipient["name"]
    db.flush()
    register(db, p, letter_id, data.version)
    return refer(db, p, letter_id, ReferralIn(
        recipients=[data.recipient_id], instruction=data.instruction, due_date=row.due_date,
    ))


def refer(db, p, letter_id, data):
    row = letter(db, p, letter_id, lock=True)
    if row.status != "registered":
        raise HTTPException(409, "فقط نامهٔ ثبت‌شده و بایگانی‌نشده قابل ارجاع است.")
    ids = set(data.recipients)
    allowed = {r["id"] for r in recipients(db, p)}
    if not ids <= allowed:
        raise HTTPException(400, "گیرنده باید کاربر فعال همین کسب‌وکار باشد؛ فهرست را تازه‌سازی کنید.")
    pending = db.query(OfficeReferral.id).filter(
        OfficeReferral.letter_id == row.id, OfficeReferral.to_user_id.in_(ids),
        OfficeReferral.completed_at.is_(None),
    ).first()
    if pending:
        raise HTTPException(409, "یکی از گیرندگان از قبل ارجاع باز دارد؛ ابتدا آن ارجاع را پیگیری کنید.")
    for user_id in sorted(ids, key=str):
        db.add(OfficeReferral(letter_id=row.id, from_user_id=p.user.id, to_user_id=user_id,
                              instruction=data.instruction, due_date=data.due_date))
    event(db, p, row, "referred", f"ارجاع به {len(ids)} نفر؛ {data.instruction}")
    db.flush()
    return row


def mark_read(db, p, letter_id):
    row = letter(db, p, letter_id, lock=True)
    refs = db.query(OfficeReferral).filter(OfficeReferral.letter_id == row.id,
        OfficeReferral.to_user_id == p.user.id, OfficeReferral.read_at.is_(None)).all()
    for ref in refs:
        ref.read_at = now()
    if refs:
        event(db, p, row, "read", "گیرنده نامه را مشاهده کرد.")
    db.flush()
    return row


def complete(db, p, referral_id, data):
    ref = db.query(OfficeReferral).filter(OfficeReferral.id == referral_id,
        OfficeReferral.tenant_id == p.tenant_id, OfficeReferral.to_user_id == p.user.id).first()
    if not ref:
        raise HTTPException(404, "ارجاعی برای اقدام شما یافت نشد.")
    row = letter(db, p, ref.letter_id, lock=True)
    db.refresh(ref)
    if row.status != "registered":
        raise HTTPException(409, "نامه بایگانی شده و اقدام تازه نمی‌پذیرد.")
    if ref.completed_at:
        if ref.response == data.response:
            return row
        raise HTTPException(409, "پاسخ این ارجاع قبلاً ثبت شده و قابل بازنویسی نیست.")
    ref.completed_at = now()
    ref.read_at = ref.read_at or ref.completed_at
    ref.response = data.response
    event(db, p, row, "completed", data.response)
    db.flush()
    return row


def archive(db, p, letter_id, version):
    row = letter(db, p, letter_id, lock=True)
    assert_editor(row, p)
    check_version(row, version)
    if row.status != "registered":
        raise HTTPException(409, "فقط نامهٔ ثبت‌شده را می‌توان بایگانی کرد.")
    if db.query(OfficeReferral.id).filter(OfficeReferral.letter_id == row.id,
                                          OfficeReferral.completed_at.is_(None)).first():
        raise HTTPException(409, "نامه ارجاعِ انجام‌نشده دارد؛ ابتدا پاسخ ارجاع‌ها را ثبت کنید.")
    row.status = "archived"
    row.version += 1
    event(db, p, row, "archived", "نامه بایگانی شد؛ متن و سابقه باقی می‌مانند.")
    db.flush()
    return row


def attach(db, p, letter_id, filename, content):
    row = letter(db, p, letter_id, lock=True)
    assert_draft(row, p)
    if not content or len(content) > MAX_FILE:
        raise HTTPException(413, "فایل باید غیرخالی و حداکثر ۵ مگابایت باشد.")
    types = [(b"%PDF-", "application/pdf", (".pdf",)),
             (b"\x89PNG\r\n\x1a\n", "image/png", (".png",)),
             (b"\xff\xd8\xff", "image/jpeg", (".jpg", ".jpeg"))]
    mime = next((mime for magic, mime, suffixes in types
                 if content.startswith(magic) and filename.lower().endswith(suffixes)), None)
    if not mime:
        raise HTTPException(400, "فقط فایل PDF، PNG یا JPEG با پسوند و محتوای مطابق پذیرفته می‌شود.")
    if any(ord(c) < 32 or c in '/\\' for c in filename):
        raise HTTPException(400, "نام فایل نباید مسیر یا نویسهٔ کنترلی داشته باشد.")
    count, size = db.query(func.count(OfficeAttachment.id), func.coalesce(func.sum(OfficeAttachment.size), 0)).filter(
        OfficeAttachment.letter_id == row.id).one()
    if count >= 10 or size + len(content) > MAX_TOTAL:
        raise HTTPException(409, "هر نامه حداکثر ۱۰ پیوست و مجموعاً ۲۰ مگابایت ظرفیت دارد.")
    db.add(OfficeAttachment(letter_id=row.id, filename=filename, content_type=mime, size=len(content),
                           sha256=sha256(content).hexdigest(), content=content, uploaded_by_id=p.user.id))
    row.version += 1
    event(db, p, row, "attached", f"پیوست افزوده شد: {filename}")
    db.flush()
    return row


def attachment(db, p, attachment_id):
    item = db.query(OfficeAttachment).filter(OfficeAttachment.id == attachment_id,
                                             OfficeAttachment.tenant_id == p.tenant_id).first()
    if not item:
        raise HTTPException(404, "پیوست یافت نشد.")
    row = letter(db, p, item.letter_id)
    return item, row


def remove_attachment(db, p, attachment_id):
    item, row = attachment(db, p, attachment_id)
    row = letter(db, p, row.id, lock=True)
    assert_draft(row, p)
    event(db, p, row, "attachment_removed", f"پیوست پیش‌نویس حذف شد: {item.filename}")
    db.delete(item)
    row.version += 1
    db.flush()
    return row


def summary(row):
    return {key: getattr(row, key) for key in (
        "id", "kind", "number", "status", "subject", "sender", "addressee", "external_number",
        "external_date", "letter_date", "due_date", "priority", "created_by_id", "registered_at", "version", "created_at",
    )}


def detail(db, p, row):
    refs = db.query(OfficeReferral).filter(OfficeReferral.letter_id == row.id).order_by(OfficeReferral.created_at).all()
    events = db.query(OfficeEvent).filter(OfficeEvent.letter_id == row.id).order_by(OfficeEvent.created_at, OfficeEvent.id).all()
    ids = {row.created_by_id} | {r.from_user_id for r in refs} | {r.to_user_id for r in refs} | {e.actor_id for e in events}
    names = dict(db.query(User.id, User.name).filter(User.id.in_(ids)).all())
    files = db.query(OfficeAttachment).filter(OfficeAttachment.letter_id == row.id).order_by(OfficeAttachment.created_at).all()
    return {**summary(row), "body": row.body, "creator_name": names.get(row.created_by_id, ""),
        "can_edit": (row.created_by_id == p.user.id or is_manager(p)) and p.has_permission("automation", "update"),
        "referrals": [{**{k: getattr(r, k) for k in ("id", "from_user_id", "to_user_id", "instruction", "due_date", "read_at", "completed_at", "response", "created_at")},
                       "from_name": names.get(r.from_user_id, ""), "to_name": names.get(r.to_user_id, ""),
                       "can_complete": r.to_user_id == p.user.id and r.completed_at is None} for r in refs],
        "events": [{"id": e.id, "action": e.action, "description": e.description,
                    "actor_name": names.get(e.actor_id, ""), "created_at": e.created_at} for e in events],
        "attachments": [{k: getattr(a, k) for k in ("id", "filename", "content_type", "size", "sha256")} for a in files]}
