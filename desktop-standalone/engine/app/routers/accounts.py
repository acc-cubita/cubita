from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.accounting import Account, JournalLine
from app.schemas.accounting import AccountCreateIn, AccountOut, AccountUpdateIn

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
def list_accounts(
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return db.query(Account).order_by(Account.code).all()


@router.post("", response_model=AccountOut, status_code=201)
def create_account(
    data: AccountCreateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "create")),
):
    """ساختِ حسابِ تازه در چارت — زیرِ یک سرفصل یا در ریشه.

    نقشِ سیستمی هرگز از این راه ست نمی‌شود؛ فقط منطقِ ثبتِ خودکار حسابِ نقش‌دار
    می‌سازد. زیرحساب باید نوعش با سرفصلش یکی باشد (زیرحسابِ «دارایی‌ها» خودش دارایی
    است) وگرنه گزارش‌ها ناسازگار می‌شوند.
    """
    if db.query(Account).filter(Account.code == data.code).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "حسابی با این کد از قبل وجود دارد")

    parent = None
    if data.parent_id is not None:
        parent = db.get(Account, data.parent_id)
        if parent is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "سرفصلِ والد یافت نشد")
        if not parent.is_group:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "فقط زیرِ یک سرفصل (گروه) می‌توان حساب ساخت")
        if data.type != parent.type:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوعِ زیرحساب باید با نوعِ سرفصلش یکی باشد")

    account = Account(
        code=data.code,
        name=data.name,
        type=data.type,
        is_group=data.is_group,
        parent_id=data.parent_id,
        system_role=None,  # فقط منطقِ ثبتِ خودکار نقش می‌دهد، نه کاربر
    )
    db.add(account)
    db.flush()
    db.refresh(account)
    return account


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: UUID,
    data: AccountUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "update")),
):
    """تغییرِ نام یا فعال/غیرفعال‌سازیِ حساب. حسابِ سیستمی را نمی‌توان غیرفعال کرد."""
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب یافت نشد")

    if data.is_active is False and account.system_role is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این حسابِ سیستمی است و برای ثبتِ خودکار لازم است؛ نمی‌توان غیرفعالش کرد",
        )

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(account, key, value)
    db.flush()
    db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=204)
def delete_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "delete")),
):
    """حذفِ حساب — فقط اگر سیستمی نباشد، زیرحساب نداشته باشد و در هیچ سندی نیامده باشد.

    حسابی که سند دارد نباید پاک شود (دفتر را می‌شکند)؛ به‌جایش «غیرفعال» شود. قیدهای
    کلیدِ خارجی مرجعِ حقیقت‌اند: تلاشِ حذف داخل SAVEPOINT انجام می‌شود و اگر سند
    مانع شد فقط همان savepoint برمی‌گردد، نه کلِ تراکنش/زمینه‌ی RLS.
    """
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب یافت نشد")
    if account.system_role is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "حسابِ سیستمی قابلِ حذف نیست؛ آن را غیرفعال کنید")
    if db.query(Account).filter(Account.parent_id == account_id).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این سرفصل زیرحساب دارد؛ اول زیرحساب‌ها را جابه‌جا/حذف کنید")
    if db.query(JournalLine).filter(JournalLine.account_id == account_id).first() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این حساب در سند استفاده شده و قابلِ حذف نیست؛ به‌جای حذف، آن را «غیرفعال» کنید",
        )
    try:
        with db.begin_nested():
            db.delete(account)
            db.flush()
    except IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این حساب در جای دیگری استفاده شده و قابلِ حذف نیست؛ آن را «غیرفعال» کنید",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
