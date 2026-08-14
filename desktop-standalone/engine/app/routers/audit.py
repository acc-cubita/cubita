"""خواندن دفتر ردِ حسابرسی.

**فقط خواندن — عمداً هیچ مسیر نوشتنی نیست.** رکوردها را رویداد flush می‌سازد، نه
یک اندپوینت. اگر راهی برای نوشتن دستی وجود داشت، همان راه برای ساختن رکورد جعلی هم
کار می‌کرد و دفتری که بشود در آن رکورد ساخت به‌اندازه‌ی دفتری که بشود ویرایشش کرد
بی‌ارزش است.

**مجوز `audit`:** ماژول تازه‌ای است و فقط «مالک» آن را دارد، چون تنها نقشی است که
wildcard دارد. این یعنی حسابدار و انباردار نمی‌بینند چه کسی چه کاری کرده — که درست
است: رد حسابرسی ابزار نظارت است، و کسی که زیر نظارت است نباید بتواند ببیند چه چیزی
از او ثبت شده.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.audit import AuditLog
from app.pagination import Page, PageParams, paginate
from app.schemas.audit import AuditEntryOut

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=Page[AuditEntryOut])
def list_audit_entries(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    action: str | None = Query(None, description="فیلتر بر اساس نوع رویداد، مثلاً void"),
    entity_type: str | None = Query(None),
    entity_id: UUID | None = Query(None, description="ردِ کاملِ یک سند مشخص"),
    _=Depends(require_permission("audit", "view")),
):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)

    # id به‌عنوان شکننده‌ی تساوی: دو رویداد در یک تراکنش زمان یکسان می‌گیرند و
    # بدون کلید دوم، ردیف‌های هم‌زمان سر مرز صفحه گم می‌شوند.
    items, next_cursor = paginate(query, [AuditLog.at, AuditLog.id], params, descending=True)
    return Page(items=items, next_cursor=next_cursor)
