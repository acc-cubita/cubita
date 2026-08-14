from uuid import UUID

from pydantic import BaseModel, model_validator

from app.models.pos_terminal import POS_TRANSPORTS


class PosTerminalIn(BaseModel):
    label: str = ""
    psp: str = ""
    transport: str = "simulator"
    host: str = ""
    port: int = 0
    com_port: str = ""
    bank_account_id: UUID | None = None
    is_active: bool = True
    is_default: bool = False

    @model_validator(mode="after")
    def validate_fields(self) -> "PosTerminalIn":
        if self.transport not in POS_TRANSPORTS:
            raise ValueError(f"روشِ اتصال باید یکی از {POS_TRANSPORTS} باشد")
        if self.transport == "network" and not (self.host or "").strip():
            raise ValueError("برای اتصالِ تحت‌شبکه، آدرسِ host الزامی است")
        if not (0 <= self.port <= 65535):
            raise ValueError("شماره‌ی پورت نامعتبر است")
        return self


class PosTerminalOut(BaseModel):
    id: UUID
    label: str
    psp: str
    transport: str
    host: str
    port: int
    com_port: str
    bank_account_id: UUID | None
    is_active: bool
    is_default: bool

    model_config = {"from_attributes": True}
