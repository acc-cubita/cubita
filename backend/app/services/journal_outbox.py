"""پیش از ویرایش صف، گم‌شدن پاسخ ثبت با ردشدن خود سند اشتباه نشود."""
from sqlalchemy.orm import Session, selectinload

from app.models.accounting import JournalEntry
from app.models.idempotency import IdempotencyKey
from app.schemas.accounting import JournalEntryIn

OPERATION = "journal-entry"


def outbox_status(db: Session, key: str, payload: JournalEntryIn) -> dict:
    record = db.query(IdempotencyKey).filter(IdempotencyKey.key == key).one_or_none()
    if record is not None:
        entry = db.get(JournalEntry, record.resource_id) if record.resource_id else None
        if record.operation != OPERATION or entry is None:
            return {"state": "ambiguous"}
        return {"state": "synced", "server_id": str(entry.id), "server_number": entry.number}

    # نسخه‌های قدیمی کلید را ذخیره نمی‌کردند. سند مشابه را خودکار به این صف نسبت
    # نمی‌دهیم: دو سند یکسان ممکن است هر دو عمدی باشند؛ فقط ویرایش ناامن را متوقف می‌کنیم.
    candidates = db.query(JournalEntry).options(selectinload(JournalEntry.lines)).filter(
        JournalEntry.entry_date == payload.entry_date,
        JournalEntry.description == payload.description,
        JournalEntry.source_type == "manual",
        # دو سند یکسان با دو کلیدِ شناخته‌شده می‌توانند عمدی باشند. ابهام فقط
        # دربارهٔ سندی است که نسخهٔ قدیمی هیچ کلیدی برایش ذخیره نکرده است.
        ~db.query(IdempotencyKey.id).filter(
            IdempotencyKey.operation == OPERATION,
            IdempotencyKey.resource_id == JournalEntry.id,
        ).exists(),
    )
    wanted = [(
        line.account_id, line.debit, line.credit, line.description,
        line.analytic_id or payload.analytic_id, line.cost_center_id or payload.cost_center_id,
        line.currency_code, line.fx_amount, line.fx_rate, line.tracking_no, line.tracking_date,
    ) for line in payload.lines]
    for entry in candidates:
        stored = [(
            line.account_id, line.debit, line.credit, line.description,
            line.analytic_id, line.cost_center_id, line.currency_code,
            line.fx_amount, line.fx_rate, line.tracking_no, line.tracking_date,
        ) for line in sorted(entry.lines, key=lambda line: line.seq)]
        if wanted == stored:
            return {"state": "ambiguous"}
    return {"state": "editable"}
