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


class OnsiteActionIn(VersionIn):
    description: str=Field(min_length=1,max_length=3000)
    result: str=Field(min_length=1,max_length=6000)


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


class OnsiteApprovalIn(RepairInput):
    version: int=Field(ge=1)
    action_version: int=Field(ge=1)
    approver_name: str=Field(min_length=1,max_length=200)
    strokes: list[list[tuple[Decimal,Decimal]]]=Field(min_length=1,max_length=100)

    @model_validator(mode='after')
    def points(self):
        return AcknowledgmentIn.points(self)


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


class ServiceProfileIn(RepairInput):
    previous_revision: int = Field(default=0,ge=0)
    service_id: UUID
    suggested_charge: Decimal = Field(ge=0,le=99999999999999999,decimal_places=0,allow_inf_nan=False)
    estimated_minutes: int = Field(ge=0,le=525600)
    enabled: bool = True


class ProtocolMetric(RepairInput):
    key: str = Field(pattern=r'^[a-z0-9_]{1,40}$')
    title: str = Field(min_length=1,max_length=200)
    unit: str = Field(min_length=1,max_length=40)
    minimum: Decimal | None = Field(default=None,ge=-1000000000000,le=1000000000000,decimal_places=6,allow_inf_nan=False)
    maximum: Decimal | None = Field(default=None,ge=-1000000000000,le=1000000000000,decimal_places=6,allow_inf_nan=False)
    required: bool = True

    @model_validator(mode='after')
    def bounds(self):
        if self.minimum is not None and self.maximum is not None and self.minimum>self.maximum:
            raise ValueError('حد پایین اندازه‌گیری نباید از حد بالا بیشتر باشد.')
        return self


class TypeProtocolIn(RepairInput):
    previous_revision: int = Field(default=0,ge=0)
    type_id: UUID
    metrics: list[ProtocolMetric] = Field(default_factory=list,max_length=40)
    checklist: list[str] = Field(default_factory=list,max_length=40)
    requires_supervisor_review: bool = False

    @model_validator(mode='after')
    def unique(self):
        if len({m.key for m in self.metrics})!=len(self.metrics) or len(set(self.checklist))!=len(self.checklist):
            raise ValueError('اندازه‌گیری و چک‌لیست تکراری مجاز نیست.')
        if any(not c or len(c)>200 for c in self.checklist): raise ValueError('عنوان چک‌لیست معتبر و کوتاه بنویسید.')
        return self


class MeasurementIn(RepairInput):
    key: str = Field(pattern=r'^[a-z0-9_]{1,40}$')
    value: Decimal = Field(ge=-1000000000000,le=1000000000000,decimal_places=6,allow_inf_nan=False)


class DiagnosticRecordIn(VersionIn):
    protocol_id: UUID | None = None
    measurements: list[MeasurementIn] = Field(default_factory=list,max_length=40)
    checklist: dict[str,bool] = Field(default_factory=dict,max_length=40)
    root_cause: str = Field(min_length=1,max_length=6000)
    test_failure_reason: str = Field(default='',max_length=6000)

    @model_validator(mode='after')
    def unique(self):
        if len({m.key for m in self.measurements})!=len(self.measurements): raise ValueError('هر اندازه‌گیری فقط یک‌بار در این نسخه ثبت شود.')
        return self


class SupervisorReviewIn(VersionIn):
    diagnostic_id: UUID
    approved: bool
    reason: str = Field(default='',max_length=6000)

    @model_validator(mode='after')
    def rejection(self):
        if not self.approved and not self.reason: raise ValueError('رد بازبینی دلیل لازم دارد.')
        return self


class PauseStartIn(VersionIn):
    reason: str = Field(min_length=1,max_length=3000)


class PauseEndIn(VersionIn):
    pause_version: int = Field(ge=1)
    end_reason: str = Field(min_length=1,max_length=3000)


class DeadlineProposalIn(VersionIn):
    new_due_date: date
    estimate_id: UUID | None = None
    reason: str = Field(min_length=1,max_length=3000)


class DeadlineDecisionIn(VersionIn):
    agreement_version: int = Field(ge=1)
    decision: Literal['accepted','rejected']
    customer_name: str = Field(min_length=1,max_length=200)
    method: Literal['in_person','phone','written']
    reason: str = Field(min_length=1,max_length=3000)


class KnowledgeIn(RepairInput):
    family_id: UUID | None = None
    previous_revision: int = Field(default=0,ge=0)
    type_id: UUID
    title: str = Field(min_length=1,max_length=200)
    symptoms: str = Field(min_length=1,max_length=6000)
    root_cause: str = Field(min_length=1,max_length=6000)
    solution: str = Field(min_length=1,max_length=10000)

    @model_validator(mode='after')
    def privacy(self):
        import re
        content='\n'.join((self.title,self.symptoms,self.root_cause,self.solution)).translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789'))
        if re.search(r'(?<!\d)(?:\+98|0098|0)?9\d{9}(?!\d)|[^\s@]+@[^\s@]+\.[^\s@]+|(?:رمز|password|pin)\s*[:=]\s*\S+',content,re.IGNORECASE):
            raise ValueError('شماره تماس، ایمیل یا رمز دستگاه در دانش تعمیرات ذخیره نمی‌شود؛ فقط توضیح فنی بنویسید.')
        return self


class KnowledgeApprovalIn(VersionIn):
    privacy_confirmed: Literal[True]


class PartAssessmentIn(VersionIn):
    previous_revision: int = Field(default=0,ge=0)
    quality: Literal['new','refurbished','used','rejected']
    compatibility: str = Field(min_length=1,max_length=3000)
    test_result: str = Field(min_length=1,max_length=3000)
    expected_supply_date: date | None = None
    purchase_invoice_id: UUID | None = None
    purchase_line_id: UUID | None = None
    warranty_until: date | None = None
    warranty_terms: str = Field(default='',max_length=3000)


class SupplierClaimIn(VersionIn):
    assessment_id: UUID
    reason: str = Field(min_length=1,max_length=3000)


class SupplierClaimResolutionIn(VersionIn):
    claim_version: int = Field(ge=1)
    status: Literal['accepted','rejected','replaced','refunded']
    response: str = Field(min_length=1,max_length=3000)
    purchase_return_id: UUID | None = None
    replacement_part_id: UUID | None = None


class HarvestOutputIn(RepairInput):
    item_id: UUID
    qty: Decimal = Field(gt=0,le=999999999,decimal_places=8,allow_inf_nan=False)
    unit_id: UUID | None = None
    percent: Decimal = Field(gt=0,le=100,decimal_places=6,allow_inf_nan=False)
    serials: list[str] = Field(default_factory=list,max_length=100)


class HarvestIn(RepairInput):
    item_id: UUID
    on: date
    source_warehouse_id: UUID
    output_warehouse_id: UUID
    unit_id: UUID | None = None
    qty: Decimal = Field(default=Decimal(1),gt=0,le=999999999,decimal_places=8,allow_inf_nan=False)
    batch_id: UUID | None = None
    serials: list[str] = Field(default_factory=list,max_length=1)
    outputs: list[HarvestOutputIn] = Field(min_length=1,max_length=40)
    waste_percent: Decimal = Field(ge=0,le=100,decimal_places=6,allow_inf_nan=False)
    waste_account_id: UUID | None = None
    reason: str = Field(min_length=1,max_length=3000)

    @model_validator(mode='after')
    def shares(self):
        if self.waste_percent and not self.waste_account_id: raise ValueError('حساب هزینهٔ ضایعات را مشخص کنید.')
        if sum((r.percent for r in self.outputs),self.waste_percent)!=Decimal(100): raise ValueError('جمع درصد قطعات و ضایعات باید دقیقاً ۱۰۰٪ باشد.')
        if len({r.item_id for r in self.outputs})!=len(self.outputs): raise ValueError('هر قطعهٔ خروجی را یک‌بار تعریف کنید.')
        if any(len(set(r.serials))!=len(r.serials) or any(not s.strip() or len(s)>120 for s in r.serials) for r in self.outputs): raise ValueError('سریال خروجی معتبر و غیرتکراری وارد کنید.')
        return self


class HarvestVoidIn(VersionIn):
    on: date
    reason: str = Field(min_length=1,max_length=3000)


class ParticipationShareIn(RepairInput):
    technician_id: UUID
    percent: Decimal = Field(gt=0,le=100,decimal_places=6,allow_inf_nan=False)


class ParticipationIn(VersionIn):
    previous_revision: int = Field(default=0,ge=0)
    shares: list[ParticipationShareIn] = Field(min_length=1,max_length=50)
    reason: str = Field(min_length=1,max_length=3000)

    @model_validator(mode='after')
    def total(self):
        if sum((s.percent for s in self.shares),Decimal(0))!=100 or len({s.technician_id for s in self.shares})!=len(self.shares):
            raise ValueError('سهم‌های یکتا باید دقیقاً جمع ۱۰۰٪ داشته باشند.')
        return self


class CustomerFollowupIn(VersionIn):
    message_id: UUID | None = None
    previous_id: UUID | None = None
    kind: Literal['call','reply','complaint']
    body: str = Field(min_length=1,max_length=6000)
    customer_name: str = Field(min_length=1,max_length=200)
    direction: Literal['incoming','outgoing','internal']
    complaint_stage: Literal['none','received','investigating','awaiting_customer','resolved','closed'] = 'none'
    responsible_id: UUID | None = None

    @model_validator(mode='after')
    def complaint(self):
        if self.kind=='complaint' and (self.complaint_stage=='none' or not self.responsible_id): raise ValueError('شکایت به مرحلهٔ رسیدگی و مسئول مشخص نیاز دارد.')
        if self.kind!='complaint' and self.complaint_stage!='none': raise ValueError('مرحلهٔ رسیدگی فقط برای شکایت است.')
        return self


class NotificationPolicyIn(RepairInput):
    previous_revision: int = Field(default=0,ge=0)
    events: list[Literal['admission','approval','due','ready','uncollected']] = Field(default_factory=lambda:['admission','approval','due','ready'])
    overdue_days: int = Field(default=0,ge=0,le=365)
    uncollected_days: int = Field(default=7,ge=1,le=365)
    repeat_days: int = Field(default=1,ge=1,le=365)

    @model_validator(mode='after')
    def unique(self):
        if len(set(self.events))!=len(self.events): raise ValueError('رویداد اعلان تکراری است.')
        return self
