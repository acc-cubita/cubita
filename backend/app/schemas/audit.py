from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    at: datetime
    actor_email: str
    action: str
    entity_type: str
    entity_id: UUID
    summary: str
    changes: dict | None = None
    request_id: str | None = None
