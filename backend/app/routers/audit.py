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
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.audit import AuditLog
from app.pagination import Page, PageParams, paginate
from app.schemas.audit import AuditEntryOut, AuditSummaryOut, AuditUsageRow

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


@router.get("/summary", response_model=AuditSummaryOut)
def audit_summary(
    days: int = Query(30, ge=1, le=365, description="بازه‌ی گزارش، از امروز به عقب"),
    db: Session = Depends(get_db),
    _=Depends(require_permission("audit", "view")),
):
    """گزارشِ استفاده از نرم‌افزار: چه کسی، چقدر، روی چه چیزی.

    خلاصه سمتِ سرور جمع می‌شود نه سمتِ کلاینت — دفترِ ردِ حسابرسی صفحه‌بندی‌شده است و
    شمردنِ آن در مرورگر یعنی شمردنِ *یک صفحه*، نه کلِ بازه. عددِ نادرست بدتر از عددِ
    نداشته است.
    """
    since = datetime.combine(date.today() - timedelta(days=days - 1), time.min, tzinfo=timezone.utc)
    base = db.query(AuditLog).filter(AuditLog.at >= since)

    def rows(column) -> list[AuditUsageRow]:
        return [
            AuditUsageRow(key=key or "—", count=count)
            for key, count in (
                base.with_entities(column, func.count(AuditLog.id))
                .group_by(column)
                .order_by(func.count(AuditLog.id).desc())
                .all()
            )
        ]

    by_day = [
        AuditUsageRow(key=str(day.date() if hasattr(day, "date") else day), count=count)
        for day, count in (
            base.with_entities(func.date_trunc("day", AuditLog.at).label("d"), func.count(AuditLog.id))
            .group_by("d")
            .order_by("d")
            .all()
        )
    ]

    return AuditSummaryOut(
        days=days,
        total=base.count(),
        by_actor=rows(AuditLog.actor_email),
        by_action=rows(AuditLog.action),
        by_entity=rows(AuditLog.entity_type),
        by_day=by_day,
    )
