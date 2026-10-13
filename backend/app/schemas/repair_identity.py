from uuid import UUID
from pydantic import Field
from typing import Literal
from datetime import datetime
from app.schemas.repair import RepairInput, DeviceProfileFields
from app.schemas.repair import VersionIn


class DeviceMergeIn(VersionIn):
    target_device_id: UUID
    target_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=2000)
    evidence: str = Field(min_length=3, max_length=4000)
    source_ownership_id: UUID | None = None
    target_ownership_id: UUID | None = None
    resolved_owner_contact_id: UUID | None = None


class DeviceOwnershipIn(VersionIn):
    contact_id: UUID
    previous_ownership_id: UUID | None = None
    reason: str = Field(min_length=3, max_length=2000)
    evidence: str = Field(min_length=3, max_length=4000)


class WarrantyTransferIn(VersionIn):
    ownership_id: UUID
    device_version: int = Field(ge=1)
    previous_revision: int = Field(ge=0)
    reason: str = Field(min_length=3,max_length=3000)


class TechnicalSummaryContent(RepairInput):
    condition: str = Field(min_length=3, max_length=2000)
    repairs: str = Field(max_length=4000)
    tests: str = Field(max_length=4000)
    care: str = Field(max_length=2000)


class TechnicalSummaryIn(VersionIn):
    device_version: int = Field(ge=1)
    ownership_id: UUID
    previous_revision: int = Field(ge=0)
    content: TechnicalSummaryContent
    reason: str = Field(min_length=3, max_length=2000)
    privacy_reviewed: Literal[True]


class OwnershipClaimIn(VersionIn):
    device_version: int = Field(ge=1)
    contact_id: UUID
    reason: str = Field(min_length=3, max_length=2000)
    evidence: str = Field(min_length=3, max_length=4000)


class OwnershipClaimDecisionIn(VersionIn):
    device_version: int = Field(ge=1)
    previous_ownership_id: UUID | None = None
    decision: Literal['approved','rejected']
    reason: str = Field(min_length=3, max_length=2000)
    evidence: str = Field(min_length=3, max_length=4000)


class RepresentativeIn(VersionIn):
    contact_id: UUID | None = None
    operation: Literal['intake','delivery']
    name: str = Field(min_length=1,max_length=200)
    phone: str = Field(min_length=1,max_length=30)
    evidence: str = Field(min_length=3,max_length=3000)
    expires_at: datetime


class RepresentativeRevokeIn(VersionIn):
    reason: str = Field(min_length=3,max_length=2000)


class DeviceProfileIn(DeviceProfileFields,VersionIn):
    reason: str = Field(min_length=3,max_length=2000)
