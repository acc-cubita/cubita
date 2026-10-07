from datetime import date
from decimal import Decimal
from uuid import UUID
from string import Formatter
from pydantic import Field, model_validator
from typing import Literal
from app.schemas.repair import RepairInput, AdmissionIn, DeviceIn, VersionIn


class BranchSettingsIn(RepairInput):
    version: int = Field(default=0, ge=0)
    default_location: str = Field(min_length=1, max_length=200)
    terms: str = Field(min_length=1, max_length=6000)
    code: str = Field(min_length=1, max_length=40)
    number_format: str = Field(default='{branch}-{year}-{number:06d}', max_length=120)

    @model_validator(mode='after')
    def format(self):
        try:
            pieces=list(Formatter().parse(self.number_format))
            if not any(field=='number' for _,field,_,_ in pieces): raise ValueError()
            for _,field,spec,conversion in pieces:
                if field is not None and (field not in {'branch','year','number'} or conversion or spec not in {'','d','04d','05d','06d','07d','08d'} or (field!='number' and spec)):
                    raise ValueError()
        except ValueError:
            raise ValueError('قالب شماره فقط branch، year و number با حداکثر هشت رقم مجاز دارد؛ شماره باید در قالب باشد.')
        return self


class QuickAdmissionIn(AdmissionIn):
    storage_location: str | None = Field(default=None, max_length=200)
    terms: str | None = Field(default=None, max_length=6000)
    approval_method: Literal['in_person','phone','written'] = 'in_person'
    organization_unit: str = Field(default='', max_length=200)
    representative: str = Field(default='', max_length=200)
    representative_contact_id: UUID | None = None
    organization_unit_contact_id: UUID | None = None
    organization_order: str = Field(default='', max_length=120)


class BatchAdmissionIn(RepairInput):
    contact_id: UUID
    admissions: list[QuickAdmissionIn] = Field(min_length=1, max_length=50)

    @model_validator(mode='after')
    def same_customer(self):
        if any(a.contact_id!=self.contact_id for a in self.admissions):
            raise ValueError('دستگاه‌های پذیرش گروهی باید یک مشتری داشته باشند.')
        return self


class IntakeDetailsIn(VersionIn):
    appearance: str | None = Field(default=None, max_length=3000)
    accessories: str | None = Field(default=None, max_length=3000)
    delivering_name: str | None = Field(default=None, max_length=200)
    delivering_phone: str | None = Field(default=None, max_length=30)
    organization_unit: str | None = Field(default=None, max_length=200)
    representative: str | None = Field(default=None, max_length=200)
    representative_contact_id: UUID | None = None
    organization_unit_contact_id: UUID | None = None
    organization_order: str | None = Field(default=None, max_length=120)


class CapacityIn(RepairInput):
    version: int = Field(default=0, ge=0)
    max_active_cases: int | None = Field(default=None, ge=1, le=10000)


class TimeStartIn(VersionIn):
    pass


class TimeActionIn(VersionIn):
    action: Literal['stop','confirm','correct']
    seconds: int | None = Field(default=None,ge=0,le=31536000)
    reason: str = Field(default='',max_length=3000)

    @model_validator(mode='after')
    def confirmation(self):
        if self.action in {'confirm','correct'} and self.seconds is None:
            raise ValueError('زمان نهایی را تأیید کنید.')
        if self.action=='correct' and not self.reason.strip():
            raise ValueError('اصلاح زمان دلیل لازم دارد.')
        return self


class AcknowledgmentIn(VersionIn):
    kind: Literal['intake','delivery']
    signer_name: str = Field(min_length=1, max_length=200)
    signer_relation: str = Field(min_length=1, max_length=200)
    strokes: list[list[tuple[Decimal, Decimal]]] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def points(self):
        count=0
        for stroke in self.strokes:
            if len(stroke)<2: raise ValueError('امضای معتبر حداقل دو نقطه در هر خط دارد.')
            for x,y in stroke:
                if not x.is_finite() or not y.is_finite() or not 0<=x<=1000 or not 0<=y<=400:
                    raise ValueError('مختصات امضا خارج از صفحه است.')
            count+=len(stroke)
        if count>4000: raise ValueError('امضا بیش از حد بزرگ است.')
        return self


class BulkCaseIn(VersionIn):
    case_id: UUID


class BulkOperationIn(RepairInput):
    action: Literal['assign','notify']
    cases: list[BulkCaseIn] = Field(min_length=1,max_length=200)
    technician_id: UUID | None = None
    reason: str = Field(min_length=1,max_length=3000)
    capacity_override: bool = False
    notification_event: Literal['admission','ready','approval'] = 'ready'

    @model_validator(mode='after')
    def unique_cases(self):
        if len({r.case_id for r in self.cases})!=len(self.cases): raise ValueError('پروندهٔ تکراری در عملیات گروهی مجاز نیست.')
        return self
