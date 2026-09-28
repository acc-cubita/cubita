from uuid import UUID

from pydantic import BaseModel

from app.schemas.accounting import JournalEntryIn


class JournalOutboxCheckIn(BaseModel):
    local_id: UUID
    payload: JournalEntryIn
