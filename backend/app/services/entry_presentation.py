"""برچسب‌های خواندنیِ سند؛ بدون نوشتن، گردکردن یا تغییر ترتیب ردیف‌ها."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry
from app.models.analytic import AnalyticAccount
from app.models.cost_center import CostCenter
from app.models.user import User
from app.schemas.accounting import JournalEntryOut


def resolve_creator_names(db: Session, entries: list[JournalEntry]) -> dict[UUID, str]:
    """نامِ فعلیِ ثبت‌کننده را برای اسنادِ مجازِ همین صفحه، با یک خواندن برگردان.

    هویت از created_by_id ذخیره‌شده می‌آید، نه کاربرِ فعلی یا نقشِ قابل‌تغییرش.
    JOIN با خودِ سند و قیدِ مستأجر مانعِ خواندنِ کاربر با شناسهٔ دلخواه می‌شود.
    """
    if not entries:
        return {}
    tenant_id = entries[0].tenant_id
    entry_ids = {entry.id for entry in entries}
    return {
        entry_id: name for entry_id, name in db.execute(
            select(JournalEntry.id, User.name)
            .join(User, User.id == JournalEntry.created_by_id)
            .where(JournalEntry.tenant_id == tenant_id, JournalEntry.id.in_(entry_ids))
        )
    }


def fill_line_labels(db: Session, entry: JournalEntry, out: JournalEntryOut) -> None:
    """حداکثر سه خواندنِ دسته‌ای؛ حتی حساب غیرفعال در تاریخچه نام دارد.

    RLS معمولِ درخواست برقرار است و tenantِ سند هم صریحاً شرط می‌شود. نام‌ها
    وضعیت فعلی چارت‌اند؛ ارقام، هویت و ترتیب سند عیناً همان خروجی قبلی‌اند.
    """
    dimensions = (
        (Account, "account"),
        (AnalyticAccount, "analytic"),
        (CostCenter, "cost_center"),
    )
    for model, prefix in dimensions:
        ids: set[UUID] = {
            ident for line in out.lines
            if (ident := getattr(line, f"{prefix}_id")) is not None
        }
        if not ids:
            continue
        labels = {
            ident: (code, name) for ident, code, name in db.execute(
                select(model.id, model.code, model.name).where(
                    model.tenant_id == entry.tenant_id, model.id.in_(ids),
                )
            )
        }
        for line in out.lines:
            label = labels.get(getattr(line, f"{prefix}_id"))
            if label is not None:
                setattr(line, f"{prefix}_code", label[0])
                setattr(line, f"{prefix}_name", label[1])
