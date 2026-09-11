"""چک و عملیاتش — روترِ مستقل.

پیش از این اندپوینت‌های چک داخلِ `routers/banking.py` بودند، کنارِ حسابِ بانکی و
صورت‌حساب. حالا که چک تاریخچه و عملیاتِ گروهی و فهرستِ عملیات دارد، روترِ خودش را
می‌گیرد — قرینه‌ی `routers/pos_settlements.py`.

**دو نما روی یک دامنه (§۴۱):** `/api/checks` می‌گوید الان چه چک‌هایی داریم و
وضعیتشان چیست؛ `/api/check-operations` می‌گوید چه عملیاتی کِی روی آن‌ها انجام شده.
هر دو از همان `checks` و `check_events` می‌آیند، نه از دو منبعِ موازی.
"""
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.banking import Check
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.banking import CheckIn, CheckOut, CheckStatusUpdateIn
from app.schemas.check_ops import (
    CheckEventOut,
    CheckSummaryOut,
    CheckOperationIn,
    CheckOperationOut,
    CheckOperationRowOut,
)
from app.services import check_ops as svc
from app.services import check_search as search
from app.services.idempotency import idempotent

router = APIRouter(tags=["checks"])


@router.get("/api/checks/summary", response_model=list[CheckSummaryOut])
def checks_summary(
    type: str | None = Query(None, description="receivable | payable"),
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    """شمارش و مبلغِ هر وضعیت (§۳۴).

    **پیش از `/{check_id}` می‌آید**، وگرنه FastAPI رشته‌ی «summary» را شناسه
    می‌گیرد و ۴۲۲ می‌دهد.
    """
    return search.summary(db, type_=type)


@router.get("/api/checks", response_model=Page[CheckOut])
def list_checks(
    q: str | None = Query(None, description="شماره، صیادی، پشت‌نمره، صاحبِ چک، بانک، طرف حساب"),
    type: str | None = Query(None, description="receivable | payable"),
    status: str | None = Query(None),
    due_from: date | None = Query(None),
    due_to: date | None = Query(None),
    amount_min: Decimal | None = Query(None),
    amount_max: Decimal | None = Query(None),
    bank_account_id: UUID | None = Query(None),
    cashbox_id: UUID | None = Query(None),
    contact_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("checks_bank", "view")),
):
    """جستجوی چک — **فیلترها روی سرور** (§۲۲).

    تا امروز این اندپوینت هیچ فیلتری نداشت و کلاینت همه‌ی چک‌ها را می‌گرفت و در
    مرورگر غربال می‌کرد. نتیجه‌اش برای دفترِ بزرگ مگابایت داده بود برای پیدا‌کردنِ
    یک برگ — و «جستجو روی کدِ صیادی» اصلاً ممکن نبود چون فیلترِ کلاینت آن ستون را
    نمی‌دید.
    """
    # id به‌عنوان شکننده‌ی تساوی: تاریخ به‌تنهایی یکتا نیست و ردیف‌های هم‌تاریخ سر مرز صفحه گم می‌شوند
    items, next_cursor = paginate(
        search.search(
            db,
            q=q,
            type_=type,
            status=status,
            due_from=due_from,
            due_to=due_to,
            amount_min=amount_min,
            amount_max=amount_max,
            bank_account_id=bank_account_id,
            cashbox_id=cashbox_id,
            contact_id=contact_id,
        ),
        [Check.due_date, Check.id],
        params,
        descending=False,
    )
    return Page(items=[_with_holder(db, c) for c in items], next_cursor=next_cursor)


def _with_holder(db: Session, check: Check) -> dict:
    """ردیفِ خروجی + «الان کجاست» (§۲۰).

    مشتق می‌شود نه ذخیره: ستونِ جدا یعنی عددی که می‌تواند با وضعیت نخواند.
    """
    holder = search.current_holder(db, check)
    row = CheckOut.model_validate(check).model_dump()
    row.update(holder_kind=holder.kind, holder_label=holder.label, holder_id=holder.id)
    return row


@router.post("/api/checks", response_model=CheckOut, status_code=201)
def create_check(
    data: CheckIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    return idempotent(
        db,
        request,
        user,
        operation="create_check",
        payload=data,
        run=lambda: svc.create_check(db, data, user),
        replay=lambda rid: db.get(Check, rid),
    )


@router.patch("/api/checks/{check_id}/status", response_model=CheckOut)
def update_check_status(
    check_id: UUID,
    data: CheckStatusUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "update")),
):
    """گذرِ وضعیتِ یک چک.

    idempotent است (§۴۸): اگر پاسخ در راه گم شود و کلاینت دوباره بفرستد، گذر
    **نباید** دو بار ثبت شود. بدونش، «وصول» دوباره یک سندِ دومِ کاملِ بانکی
    می‌زد — و چون گذرِ `cleared → cleared` مجاز نیست، در عمل خطای گمراه‌کننده
    می‌داد به‌جای برگرداندنِ همان نتیجه.
    """
    return idempotent(
        db,
        request,
        user,
        operation="update_check_status",
        payload=data,
        run=lambda: svc.update_check_status(
            db,
            check_id,
            data.status,
            data.bank_account_id,
            user,
            cashbox_id=data.cashbox_id,
            contact_id=data.contact_id,
            event_date=data.event_date,
            note=data.note,
        ),
        replay=lambda rid: db.get(Check, rid),
    )


@router.get("/api/checks/{check_id}/timeline", response_model=list[CheckEventOut])
def check_timeline(
    check_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    """تاریخچه‌ی یک چک (§۳۵ §۳۶) — وضعیتِ فعلی به‌تنهایی کافی نیست."""
    return svc.timeline(db, check_id)


@router.get("/api/check-operations", response_model=list[CheckOperationRowOut])
def list_operations(
    operation: str | None = Query(None, description="deposit | collect | dishonor | cash | …"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(200, le=500),
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    """فهرستِ عملیاتِ چک (§۴۰) — نمای دومِ همان دامنه."""
    return svc.list_operations(
        db, operation=operation, date_from=date_from, date_to=date_to, limit=limit
    )


@router.post("/api/check-operations", response_model=CheckOperationOut, status_code=201)
def run_operation(
    data: CheckOperationIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "update")),
):
    """یک عملیات روی چند چک، با نتیجه‌ی جدا برای هر کدام (§۴۴ §۴۵).

    **پاسخِ ۲۰۱ لزوماً یعنی همه رفتند.** `failed` را بخوانید: چکی که واجدِ شرایط
    نبوده با دلیلش آنجاست. «عملیات ناموفق»ِ کلی به کاربر نمی‌گوید کدام و چرا.
    """
    result = idempotent(
        db,
        request,
        user,
        operation="check_bulk_operation",
        payload=data,
        run=lambda: svc.run_operation(
            db,
            user,
            check_ids=data.check_ids,
            new_status=data.status,
            bank_account_id=data.bank_account_id,
            cashbox_id=data.cashbox_id,
            contact_id=data.contact_id,
            event_date=data.event_date,
            note=data.note,
        ),
        #: نتیجه‌ی گروهی رکوردِ یکتا ندارد، پس شناسه‌اش `batch_id` است و بازپخش
        #: از روی همان ساخته می‌شود.
        resource_id=lambda res: res["batch_id"],
        replay=lambda rid: svc.replay_operation(db, rid),
    )
    return result
