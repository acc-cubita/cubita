from typing import Literal
from uuid import UUID
from pydantic import Field, SecretStr, field_validator, model_validator
from fastapi import HTTPException
from app.schemas.repair import VersionIn, RepairDeliveryIn
from app.schemas.repair_completion import AcknowledgmentIn


class ConfirmationRequestIn(VersionIn):
    kind: Literal['intake','delivery']
    recipient_name: str = Field(min_length=1,max_length=200)
    recipient_phone: str = Field(min_length=1,max_length=30)
    recipient_contact_id: UUID | None = None
    representation_id: UUID | None = None
    authority_evidence: str = Field(min_length=3,max_length=3000)
    delivery: RepairDeliveryIn | None = None

    @model_validator(mode='after')
    def operation(self):
        if (self.kind=='delivery') != (self.delivery is not None):
            raise ValueError('برای تأیید تحویل، نسخهٔ کامل اطلاعات تحویل را بفرستید.')
        return self


class ConfirmationVerifyIn(VersionIn):
    code: SecretStr

    @field_validator('code',mode='before')
    @classmethod
    def six_digits(cls,value):
        if not isinstance(value,(str,SecretStr)):
            raise HTTPException(422,'کد شش‌رقمی را وارد کنید.')
        raw=(value.get_secret_value() if isinstance(value,SecretStr) else value).translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789'))
        if len(raw)!=6 or not raw.isascii() or not raw.isdigit():
            # ValidationError includes the rejected input; never echo a secret.
            raise HTTPException(422,'کد شش‌رقمی را وارد کنید.')
        return SecretStr(raw)


class ConfirmationOverrideIn(ConfirmationRequestIn):
    acknowledgment: AcknowledgmentIn
    expected_document_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    override_reason: str = Field(min_length=3,max_length=3000)
