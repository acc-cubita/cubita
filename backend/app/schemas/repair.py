from datetime import date
from typing import Literal
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from app.schemas.item_units import ObservedRatioIn


class RepairInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BranchIn(RepairInput):
    name: str = Field(min_length=1, max_length=120)


class BranchAccessIn(RepairInput):
    user_ids: list[UUID] = Field(max_length=200)


class DeviceTypeIn(BranchIn):
    fields: list[str] = Field(default_factory=list, max_length=40)
    checklist: list[str] = Field(default_factory=list, max_length=40)
    diagnostic_checklist: list[str] = Field(default_factory=list, max_length=40)
    quality_checklist: list[str] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def labels(self):
        for labels in (self.fields, self.checklist, self.diagnostic_checklist, self.quality_checklist):
            if len(set(labels)) != len(labels) or any(not s.strip() or len(s) > 120 for s in labels):
                raise ValueError("عنوان فیلدها باید کوتاه، غیرخالی و غیرتکراری باشد.")
            if any(any(secret in s.casefold() for secret in ("رمز", "password", "passcode")) for s in labels):
                raise ValueError("رمز دستگاه نباید در فیلد عمومی یا چک‌لیست ذخیره شود.")
        return self


class DeviceIn(RepairInput):
    type_id: UUID
    brand: str = Field(default="", max_length=120)
    model: str = Field(min_length=1, max_length=120)
    serial: str = Field(default="", max_length=120)
    imei: str = Field(default="", max_length=30)
    attributes: dict[str, str] = Field(default_factory=dict, max_length=40)


class AdmissionIn(RepairInput):
    contact_id: UUID
    branch_id: UUID
    device_id: UUID | None = None
    device: DeviceIn | None = None
    delivering_name: str = Field(default="", max_length=200)
    delivering_phone: str = Field(default="", max_length=30)
    reported_issue: str = Field(min_length=1, max_length=6000)
    appearance: str = Field(default="", max_length=3000)
    accessories: str = Field(default="", max_length=3000)
    intake_checklist: dict[str, bool] = Field(default_factory=dict, max_length=40)
    priority: Literal["normal", "high", "urgent"] = "normal"
    admission_date: date
    due_date: date | None = None
    storage_location: str = Field(min_length=1, max_length=200)
    terms: str = Field(min_length=1, max_length=6000)
    approval_method: Literal["in_person", "phone", "written"]

    @model_validator(mode="after")
    def admission(self):
        if (self.device_id is None) == (self.device is None):
            raise ValueError("دستگاه موجود یا مشخصات دستگاه تازه را انتخاب کنید.")
        if self.due_date and self.due_date < self.admission_date:
            raise ValueError("موعد نمی‌تواند پیش از پذیرش باشد.")
        return self


class LocationIn(RepairInput):
    version: int = Field(ge=1)
    storage_location: str = Field(min_length=1, max_length=200)


class WorkflowIn(RepairInput):
    version: int = Field(ge=1)
    status: Literal["accepted", "diagnosing", "awaiting_customer", "repairing", "awaiting_part", "testing", "ready", "unrepairable", "cancelled", "delivered", "closed"]
    reason: str = Field(default="", max_length=3000)
    exceptional: bool = False


class AssignmentIn(RepairInput):
    version: int = Field(ge=1)
    user_id: UUID | None
    reason: str = Field(min_length=1, max_length=3000)
    capacity_override: bool = False


class TaskIn(RepairInput):
    version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    internal_note: str = Field(default="", max_length=6000)
    due_date: date | None = None


class TaskStatusIn(RepairInput):
    version: int = Field(ge=1)
    status: Literal["working", "done"]


class FaultIn(RepairInput):
    name: str = Field(min_length=1, max_length=200)
    type_id: UUID | None = None


class DiagnosisIn(RepairInput):
    version: int = Field(ge=1)
    initial_diagnosis: str = Field(default="", max_length=6000)
    final_diagnosis: str = Field(default="", max_length=6000)
    fault_ids: list[UUID] = Field(default_factory=list, max_length=40)
    checklist: dict[str, bool] = Field(default_factory=dict, max_length=40)


class EstimateLineIn(RepairInput):
    kind: Literal["labor", "part", "extra"]
    title: str = Field(min_length=1, max_length=200)
    item_id: UUID | None = None
    qty: Decimal = Field(gt=0, le=100000000, decimal_places=8, allow_inf_nan=False)
    unit_price: Decimal = Field(ge=0, le=99999999999999999, decimal_places=0, allow_inf_nan=False)


class EstimateOptionIn(RepairInput):
    title: str = Field(min_length=1, max_length=200)
    lines: list[EstimateLineIn] = Field(min_length=1, max_length=100)


class EstimateIn(RepairInput):
    version: int = Field(ge=1)
    options: list[EstimateOptionIn] = Field(min_length=1, max_length=10)
    valid_until: date
    duration_days: int = Field(ge=0, le=3650)
    customer_ceiling: Decimal | None = Field(default=None, ge=0, le=99999999999999999, decimal_places=0, allow_inf_nan=False)


class EstimateDecisionIn(RepairInput):
    version: int = Field(ge=1)
    decision: Literal["approved", "rejected"]
    option_index: int | None = Field(default=None, ge=0, le=9)
    method: Literal["in_person", "phone", "written"]
    customer_name: str = Field(min_length=1, max_length=200)
    reason: str = Field(default="", max_length=3000)
    authorized_ceiling: Decimal | None = Field(default=None, ge=0, le=99999999999999999, decimal_places=0, allow_inf_nan=False)


class FeePolicyIn(RepairInput):
    diagnostic_fee: Decimal = Field(ge=0, le=99999999999999999, decimal_places=0, allow_inf_nan=False)
    cancellation_fee: Decimal = Field(ge=0, le=99999999999999999, decimal_places=0, allow_inf_nan=False)
    discount_ceiling: Decimal = Field(default=Decimal(0), ge=0, le=99999999999999999, decimal_places=0, allow_inf_nan=False)


class PartIn(RepairInput):
    version: int = Field(ge=1)
    owner: Literal["company", "customer"] = "company"
    item_id: UUID | None = None
    title: str = Field(default="", max_length=200)
    qty: Decimal = Field(gt=0, le=100000000, decimal_places=8, allow_inf_nan=False)
    unit_id: UUID | None = None
    customer_unit: str = Field(default="عدد", min_length=1, max_length=50)
    observations: list[ObservedRatioIn] = Field(default_factory=list, max_length=100)
    unit_price: Decimal = Field(default=Decimal(0), ge=0, le=99999999999999999, decimal_places=0, allow_inf_nan=False)
    charge_to_customer: bool = True
    source_warehouse_id: UUID | None = None
    work_warehouse_id: UUID | None = None
    batch_id: UUID | None = None
    substitute_for_id: UUID | None = None
    compatibility_reason: str = Field(default="", max_length=3000)


class PartActionIn(RepairInput):
    version: int = Field(ge=1)
    action: Literal["reserve", "dispatch", "release", "consume", "return_unused", "return_consumed", "waste", "supplier_return"]
    on: date
    qty: Decimal | None = Field(default=None, gt=0, le=100000000, decimal_places=8, allow_inf_nan=False)
    reason: str = Field(default="", max_length=3000)
    serials: list[str] = Field(default_factory=list, max_length=200)
    source_movement_id: UUID | None = None
    return_condition: Literal["sellable", "damaged", "expired", "quarantine"] = "sellable"
    purchase_invoice_id: UUID | None = None
    purchase_invoice_line_id: UUID | None = None


class WorkIn(RepairInput):
    version: int = Field(ge=1)
    technician_id: UUID
    time_session_id: UUID | None = None
    collaborators: list[UUID] = Field(default_factory=list, max_length=30)
    service_id: UUID | None = None
    description: str = Field(min_length=1, max_length=6000)
    internal_result: str = Field(default="", max_length=6000)
    customer_result: str = Field(default="", max_length=6000)
    work_minutes: int = Field(ge=0, le=525600)
    started_at: str | None = Field(default=None, max_length=40)
    completed_at: str | None = Field(default=None, max_length=40)
    charge_amount: Decimal = Field(default=Decimal(0), ge=0, le=99999999999999999, decimal_places=0, allow_inf_nan=False)


class QualityIn(RepairInput):
    version: int = Field(ge=1)
    passed: bool
    checklist: dict[str, bool] = Field(default_factory=dict, max_length=40)
    result: str = Field(min_length=1, max_length=6000)


class OutsourceIn(RepairInput):
    version: int = Field(ge=1)
    vendor_id: UUID
    description: str = Field(min_length=1, max_length=6000)
    expected_cost: Decimal = Field(ge=0, le=99999999999999999, decimal_places=0, allow_inf_nan=False)
    due_date: date


class OutsourceReturnIn(RepairInput):
    version: int = Field(ge=1)
    result: str = Field(min_length=1, max_length=6000)
    purchase_invoice_id: UUID | None = None


class RemovedPartIn(RepairInput):
    version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    disposition: Literal["retained", "returned_customer", "scrapped_with_consent"]
    authorization_method: Literal["in_person", "phone", "written"]
    customer_name: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=3000)


class DeviceSecretIn(RepairInput):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    version: int = Field(ge=1)
    secret: SecretStr = Field(min_length=1, max_length=200)
    expires_days: int = Field(ge=1, le=30)


class SecretRevealIn(RepairInput):
    reason: str = Field(min_length=1, max_length=3000)


class VersionIn(RepairInput):
    version: int = Field(ge=1)


class PurchaseRequestIn(RepairInput):
    version: int = Field(ge=1)
    due_date: date
    reason: str = Field(min_length=1, max_length=3000)


class PurchaseRequestUpdateIn(RepairInput):
    version: int = Field(ge=1)
    status: Literal["ordered", "received", "cancelled"]
    purchase_invoice_id: UUID | None = None


class RepairInvoiceIn(VersionIn):
    on: date
    discount: Decimal = Field(default=Decimal(0), ge=0, le=99999999999999999, decimal_places=0, allow_inf_nan=False)
    discount_reason: str = Field(default='', max_length=3000)
    tax_rate: Decimal = Field(default=Decimal(0), ge=0, le=100, decimal_places=4, allow_inf_nan=False)


class RepairCashIn(VersionIn):
    on: date
    amount: Decimal = Field(gt=0, le=99999999999999999, decimal_places=0, allow_inf_nan=False)
    method: Literal['cash','transfer','card'] = 'cash'
    cashbox_id: UUID | None = None
    bank_account_id: UUID | None = None
    pos_terminal_id: UUID | None = None
    reference_no: str = Field(default='',max_length=120)
    reason: str = Field(min_length=1,max_length=3000)


class RepairDocumentLinkIn(VersionIn):
    document_type: Literal['sales_invoice','receipt','payment','sales_return']
    document_id: UUID
    reason: str = Field(min_length=1,max_length=3000)


class RepairDeliveryIn(VersionIn):
    receiver_name: str = Field(min_length=1,max_length=200)
    receiver_phone: str = Field(min_length=1,max_length=30)
    authorization: str = Field(min_length=1,max_length=3000)
    accessories: str = Field(min_length=1,max_length=3000)
    care_instructions: str = Field(default='',max_length=6000)
    credit_reason: str = Field(default='',max_length=3000)
    approval_method: Literal['in_person','written'] = 'in_person'
    checklist: dict[str,bool] = Field(default_factory=dict,max_length=40)


class RepairCorrectionIn(VersionIn):
    on: date
    reason: str = Field(min_length=1,max_length=3000)


class RepairTemplateIn(RepairInput):
    branch_id: UUID | None = None
    kind: Literal['admission','approval','due','ready']
    body: str = Field(min_length=1,max_length=1000)
    enabled: bool = True


class RepairNotifyIn(VersionIn):
    kind: Literal['admission','approval','due','ready']


class RepairRetryIn(VersionIn):
    reason: str = Field(min_length=1,max_length=3000)
    acknowledge_duplicate_risk: bool = False


class RepairPortalTokenIn(VersionIn):
    expires_days: int = Field(ge=1,le=30)


class RepairPortalDecisionIn(RepairInput):
    version: int = Field(ge=1)
    estimate_id: UUID
    decision: Literal['approved','rejected']
    option_index: int | None = Field(default=None,ge=0,le=9)
    customer_name: str = Field(min_length=1,max_length=200)
    reason: str = Field(default='',max_length=3000)


class RepairCustomerMessageIn(RepairInput):
    kind: Literal['comment','complaint','survey']
    name: str = Field(min_length=1,max_length=200)
    body: str = Field(min_length=1,max_length=3000)
    rating: int | None = Field(default=None,ge=1,le=5)


class RepairAttachmentVisibilityIn(VersionIn):
    customer_visible: bool


class RepairOnlineSettingsIn(RepairInput):
    gateway_id: UUID
    pos_terminal_id: UUID
    enabled: bool


class RepairPortalPaymentIn(VersionIn):
    amount_rial: Decimal = Field(gt=0,le=99999999999999999,decimal_places=0,allow_inf_nan=False)


class WarrantyIn(RepairInput):
    version: int = Field(ge=1)
    scope: Literal['service','part']
    source_id: UUID
    title: str = Field(min_length=1, max_length=200)
    valid_from: date
    valid_until: date
    terms: str = Field(min_length=1, max_length=6000)
    exclusions: str = Field(default='', max_length=6000)

    @model_validator(mode='after')
    def dates(self):
        if self.valid_until < self.valid_from:
            raise ValueError('پایان ضمانت نمی‌تواند پیش از شروع آن باشد.')
        return self


class WarrantyClaimIn(RepairInput):
    warranty_id: UUID
    admission: AdmissionIn
    classification: Literal['repeat_fault','new_fault']
    responsibility: Literal['company','technician','vendor','customer']
    cost_policy: Literal['covered','customer','responsible']
    reason: str = Field(min_length=1, max_length=6000)


class FeeRuleIn(RepairInput):
    technician_id: UUID
    mode: Literal['fixed_case','percent_labor','per_operation']
    value: Decimal = Field(ge=0,le=99999999999999,decimal_places=4,allow_inf_nan=False)
    payee_id: UUID
    service_id: UUID
    enabled: bool = True
    reason: str = Field(min_length=1,max_length=3000)

    @model_validator(mode='after')
    def value_limit(self):
        if self.mode=='percent_labor' and self.value>100:
            raise ValueError('درصد سهم نمی‌تواند بیش از صد باشد.')
        if self.mode!='percent_labor' and self.value!=self.value.to_integral_value():
            raise ValueError('مبلغ سهم باید ریال صحیح باشد.')
        return self


class FeeDraftIn(VersionIn):
    technician_id: UUID


class FeeApproveIn(VersionIn):
    on: date


class ServiceRequestIn(RepairInput):
    branch_id: UUID
    contact_id: UUID
    type_id: UUID
    device_description: str = Field(min_length=1,max_length=500)
    reported_issue: str = Field(min_length=1,max_length=6000)
    address: str = Field(min_length=1,max_length=3000)
    coordinator_name: str = Field(min_length=1,max_length=200)
    coordinator_phone: str = Field(min_length=1,max_length=30)


class TechnicianSkillsIn(RepairInput):
    type_ids: list[UUID] = Field(max_length=100)


class AppointmentIn(VersionIn):
    technician_id: UUID
    starts_at: str = Field(max_length=50)
    ends_at: str = Field(max_length=50)


class AppointmentStatusIn(VersionIn):
    status: Literal['dispatched','onsite','completed','cancelled']
    result: str = Field(min_length=1,max_length=6000)


class ServiceRequestAdmissionIn(VersionIn):
    admission: AdmissionIn


class CustodyTransferIn(VersionIn):
    to_branch_id: UUID
    destination_location: str = Field(min_length=1,max_length=200)
    carrier_name: str = Field(min_length=1,max_length=200)
    carrier_phone: str = Field(default='',max_length=30)
    reason: str = Field(min_length=1,max_length=3000)


class CustodyLegIn(VersionIn):
    carrier_name: str = Field(min_length=1,max_length=200)
    carrier_phone: str = Field(default='',max_length=30)
    location: str = Field(min_length=1,max_length=200)
    confirmation: str = Field(min_length=1,max_length=3000)


class CustodyReceiveIn(VersionIn):
    receiver_name: str = Field(min_length=1,max_length=200)
    confirmation: str = Field(min_length=1,max_length=3000)
    return_to_source: bool = False


class LoanIn(VersionIn):
    asset_id: UUID
    serial: str = Field(default='',max_length=120)
    receiver_name: str = Field(min_length=1,max_length=200)
    authorization: str = Field(min_length=1,max_length=3000)
    accessories: str = Field(min_length=1,max_length=3000)
    condition_out: str = Field(min_length=1,max_length=3000)
    due_date: date
    return_custodian_id: UUID
    return_location: str = Field(min_length=1,max_length=200)


class LoanReturnIn(VersionIn):
    condition_in: str = Field(min_length=1,max_length=3000)
    confirmation: str = Field(min_length=1,max_length=3000)


class MaintenanceContractIn(RepairInput):
    code: str = Field(min_length=1,max_length=120)
    contact_id: UUID
    title: str = Field(min_length=1,max_length=200)
    valid_from: date
    valid_until: date
    terms: str = Field(min_length=1,max_length=6000)
    address: str = Field(min_length=1,max_length=3000)
    coordinator_name: str = Field(min_length=1,max_length=200)
    coordinator_phone: str = Field(min_length=1,max_length=30)
    covers_labor: bool = True
    covers_parts: bool = False
    visit_quota: int | None = Field(default=None,ge=1,le=100000)
    minute_quota: int | None = Field(default=None,ge=1,le=100000000)
    value_quota_rial: Decimal | None = Field(default=None,gt=0,le=99999999999999999,decimal_places=0,allow_inf_nan=False)
    response_hours: int = Field(ge=1,le=87600)
    completion_hours: int = Field(ge=1,le=87600)
    enabled: bool = True
    device_ids: list[UUID] = Field(min_length=1,max_length=200)

    @model_validator(mode='after')
    def period(self):
        if self.valid_until<self.valid_from or self.completion_hours<self.response_hours:
            raise ValueError('بازه قرارداد و مهلت پاسخ/انجام معتبر نیست.')
        return self


class ContractCaseIn(VersionIn):
    contract_id: UUID
    service_date: date
    allocated_minutes: int = Field(ge=0,le=1000000)
    covered_value_rial: Decimal = Field(ge=0,le=99999999999999999,decimal_places=0,allow_inf_nan=False)


class OutsideCoverageIn(VersionIn):
    estimate_id: UUID
    reason: str = Field(min_length=1,max_length=3000)


class MaintenancePlanIn(RepairInput):
    contract_id: UUID
    device_id: UUID
    branch_id: UUID
    title: str = Field(min_length=1,max_length=200)
    interval_days: int = Field(ge=1,le=3650)
    next_due: date
    allocated_minutes: int = Field(ge=0,le=1000000)
    covered_value_rial: Decimal = Field(ge=0,le=99999999999999999,decimal_places=0,allow_inf_nan=False)


class MaintenanceCompleteIn(RepairInput):
    result: str = Field(min_length=1,max_length=6000)


class ConsolidatedBillIn(RepairInput):
    title: str = Field(min_length=1,max_length=200)
    on: date
    case_ids: list[UUID] = Field(min_length=1,max_length=50)
