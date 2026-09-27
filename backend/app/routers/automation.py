from datetime import date
from html import escape
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal, require_module, require_permission
from app.models.automation import OfficeLetter, OfficeReferral
from app.pagination import PageParams, paginate
from app.schemas.automation import CompletionIn, LetterIn, LetterUpdate, ReferralIn, SendIn, VersionIn
from app.services import automation as svc
from app.services import entitlements


def office_access(db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    # ارجاع به عضوِ فاقد مجوزِ عمومی هم خواندنی است؛ محدوده را visible_query
    # می‌بندد، ولی گیتِ اشتراک/مجوز (از جمله آزمایشیِ منقضی) همچنان لازم است.
    entitlements.enforce(db, p.membership.tenant, ("view",))


router = APIRouter(prefix="/api/automation", tags=["automation"],
                   dependencies=[Depends(require_module("automation")), Depends(office_access)])


@router.get("/recipients", dependencies=[Depends(require_permission("automation", ("create", "update")))])
def recipients(db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.recipients(db, p)


@router.get("/letters")
def list_letters(
    box: Literal["inbox", "sent", "drafts", "all", "archive"] = "inbox",
    kind: Literal["incoming", "outgoing", "internal"] | None = None,
    q: str = Query("", max_length=300), unread: bool = False, overdue: bool = False,
    date_from: date | None = None, date_to: date | None = None,
    params: PageParams = Depends(), db: Session = Depends(get_db), p: Principal = Depends(get_principal),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(400, "تاریخ شروع باید پیش از پایان بازه باشد.")
    query = svc.visible_query(db, p)
    own_ref = db.query(OfficeReferral.id).filter(OfficeReferral.letter_id == OfficeLetter.id,
        OfficeReferral.tenant_id == p.tenant_id, OfficeReferral.to_user_id == p.user.id)
    if box == "inbox":
        query = query.filter(own_ref.exists(), OfficeLetter.status == "registered")
    elif box == "sent":
        sent_ref = db.query(OfficeReferral.id).filter(OfficeReferral.letter_id == OfficeLetter.id,
            OfficeReferral.tenant_id == p.tenant_id, OfficeReferral.from_user_id == p.user.id)
        query = query.filter(sent_ref.exists())
    elif box == "drafts":
        query = query.filter(OfficeLetter.created_by_id == p.user.id, OfficeLetter.status == "draft")
    elif box == "archive":
        query = query.filter(OfficeLetter.status == "archived")
    if kind:
        query = query.filter(OfficeLetter.kind == kind)
    if q.strip():
        term = f"%{q.strip()}%"
        clauses = [OfficeLetter.subject.ilike(term), OfficeLetter.sender.ilike(term),
                   OfficeLetter.addressee.ilike(term), OfficeLetter.external_number.ilike(term)]
        if q.strip().isdecimal() and int(q.strip()) <= 9223372036854775807:
            clauses.append(OfficeLetter.number == int(q.strip()))
        query = query.filter(or_(*clauses))
    if date_from:
        query = query.filter(OfficeLetter.letter_date >= date_from)
    if date_to:
        query = query.filter(OfficeLetter.letter_date <= date_to)
    if unread:
        query = query.filter(own_ref.filter(OfficeReferral.read_at.is_(None)).exists())
    if overdue:
        query = query.filter(OfficeLetter.status == "registered", own_ref.filter(
            OfficeReferral.completed_at.is_(None),
            func.coalesce(OfficeReferral.due_date, OfficeLetter.due_date) < date.today()).exists())
    rows, cursor = paginate(query, [OfficeLetter.created_at, OfficeLetter.id], params)
    # فقط ارجاع‌های همین صفحه خوانده می‌شوند؛ فهرست هر نامه یک کوئری تازه نمی‌زند.
    unread_ids = {r[0] for r in db.query(OfficeReferral.letter_id).filter(
        OfficeReferral.letter_id.in_([r.id for r in rows]), OfficeReferral.to_user_id == p.user.id,
        OfficeReferral.read_at.is_(None)).all()}
    return {"items": [{**svc.summary(r), "unread": r.id in unread_ids} for r in rows], "next_cursor": cursor}


@router.post("/letters", status_code=201, dependencies=[Depends(require_permission("automation", "create"))])
def create(data: LetterIn, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.detail(db, p, svc.create(db, p, data))


@router.get("/letters/{letter_id}")
def get(letter_id: UUID, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.detail(db, p, svc.letter(db, p, letter_id))


@router.put("/letters/{letter_id}", dependencies=[Depends(require_permission("automation", "update"))])
def update(letter_id: UUID, data: LetterUpdate, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.detail(db, p, svc.update(db, p, letter_id, data))


@router.post("/letters/{letter_id}/register", dependencies=[Depends(require_permission("automation", "update"))])
def register(letter_id: UUID, data: VersionIn, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.detail(db, p, svc.register(db, p, letter_id, data.version))


@router.post("/letters/{letter_id}/refer", dependencies=[Depends(require_permission("automation", "update"))])
def refer(letter_id: UUID, data: ReferralIn, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.detail(db, p, svc.refer(db, p, letter_id, data))


@router.post("/letters/{letter_id}/send", dependencies=[Depends(require_permission("automation", "update"))])
def send(letter_id: UUID, data: SendIn, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.detail(db, p, svc.send(db, p, letter_id, data))


@router.post("/letters/{letter_id}/read")
def read(letter_id: UUID, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.detail(db, p, svc.mark_read(db, p, letter_id))


@router.post("/referrals/{referral_id}/complete")
def complete(referral_id: UUID, data: CompletionIn, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    entitlements.enforce(db, p.membership.tenant, ("update",))
    return svc.detail(db, p, svc.complete(db, p, referral_id, data))


@router.post("/letters/{letter_id}/archive", dependencies=[Depends(require_permission("automation", "update"))])
def archive(letter_id: UUID, data: VersionIn, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.detail(db, p, svc.archive(db, p, letter_id, data.version))


@router.post("/letters/{letter_id}/attachments", dependencies=[Depends(require_permission("automation", "update"))])
async def upload(letter_id: UUID, request: Request, filename: str = Query(min_length=1, max_length=200),
                 db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    svc.assert_draft(svc.letter(db, p, letter_id), p)
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > svc.MAX_FILE:
            raise HTTPException(413, "اندازهٔ پیوست نباید بیشتر از ۵ مگابایت باشد.")
        content.extend(chunk)
    return svc.detail(db, p, svc.attach(db, p, letter_id, filename, bytes(content)))


@router.delete("/attachments/{attachment_id}", dependencies=[Depends(require_permission("automation", "update"))])
def remove(attachment_id: UUID, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.detail(db, p, svc.remove_attachment(db, p, attachment_id))


@router.get("/attachments/{attachment_id}")
def download(attachment_id: UUID, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    item, _ = svc.attachment(db, p, attachment_id)
    return Response(item.content, media_type=item.content_type, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(item.filename, safe='')}",
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox",
    })


@router.get("/letters/{letter_id}/print", response_class=HTMLResponse)
def print_letter(letter_id: UUID, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    row = svc.letter(db, p, letter_id)
    # متنِ کاربر HTML نیست؛ چاپ نباید راهی برای اجرای اسکریپت از متنِ نامه باشد.
    number = str(row.number) if row.number else "پیش‌نویس — فاقد شمارهٔ قطعی"
    fa = lambda value: str(value).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    from app.services.printing import format_jalali
    html = f"""<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8">
    <title>{escape(row.subject)}</title><style>body{{font-family:Tahoma,sans-serif;margin:2cm;line-height:2}}
    article{{white-space:pre-wrap;overflow-wrap:anywhere}}h1{{font-size:20px}}</style>
    <h1>{escape(p.membership.tenant.name)}</h1><p>نامهٔ {svc.KINDS[row.kind]} — شماره: {escape(fa(number))}
    — تاریخ: {escape(format_jalali(row.letter_date))}</p><p>از: {escape(row.sender)}<br>به: {escape(row.addressee)}</p>
    <h2>{escape(row.subject)}</h2><article>{escape(row.body)}</article></html>"""
    return HTMLResponse(html, headers={"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})
