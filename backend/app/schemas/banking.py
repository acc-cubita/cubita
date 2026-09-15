from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class BankAccountIn(BaseModel):
    name: str
    name2: str = ""
    bank_name: str = ""
    branch_name: str = ""
    account_number: str = ""
    account_type: str = ""
    #: سه شناسه‌ی جدا (§۷) — هیچ‌کدام جای دیگری به کار نمی‌رود.
    card_number: str = ""
    iban: str = ""
    #: بُعدی که مانده‌ی این حساب را از بقیه جدا می‌کند. خالی فقط برای حسابِ اول.
    analytic_id: UUID | None = None
    gl_account_id: UUID | None = None  # اگر خالی باشد، حساب پیش‌فرض «۱۱۰۲ بانک» استفاده می‌شود
    currency_code: str = "IRR"
    opening_date: date | None = None
    holder_name: str = ""
    holder_name2: str = ""
    blocked_amount: Decimal = Decimal(0)
    cheque_print_format: str = ""

    @model_validator(mode="after")
    def _name_not_blank(self) -> "BankAccountIn":
        if not self.name.strip():
            raise ValueError("نام حساب نمی‌تواند خالی باشد")
        return self


class BankAccountUpdateIn(BaseModel):
    """ویرایشِ حساب بانکی — فقط فیلدهای ارسال‌شده تغییر می‌کنند.

    `gl_account_id` عمداً اینجا نیست: روی اسنادِ ثبت‌شده نشسته و عوض کردنش یعنی
    مانده‌ی گذشته از جای دیگری خوانده شود. `analytic_id` هست ولی سرویس اگر حساب
    سابقه داشته باشد ردش می‌کند (§۳۱).
    """

    name: str | None = None
    name2: str | None = None
    bank_name: str | None = None
    branch_name: str | None = None
    account_number: str | None = None
    account_type: str | None = None
    card_number: str | None = None
    iban: str | None = None
    analytic_id: UUID | None = None
    currency_code: str | None = None
    opening_date: date | None = None
    holder_name: str | None = None
    holder_name2: str | None = None
    blocked_amount: Decimal | None = None
    cheque_print_format: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _name_not_blank(self) -> "BankAccountUpdateIn":
        if self.name is not None and not self.name.strip():
            raise ValueError("نام حساب نمی‌تواند خالی باشد")
        return self


class BankAccountOut(BaseModel):
    id: UUID
    name: str
    name2: str = ""
    bank_name: str
    branch_name: str = ""
    account_number: str
    account_type: str = ""
    card_number: str = ""
    iban: str
    analytic_id: UUID | None = None
    #: کد و نامِ تفصیلی برای نمایش — از رابطه‌ی eager می‌آید، نه کوئریِ جدا.
    analytic_code: str | None = None
    analytic_name: str | None = None
    gl_account_id: UUID
    currency_code: str = "IRR"
    opening_date: date | None = None
    holder_name: str = ""
    holder_name2: str = ""
    #: **ذخیره‌شده** — واقعیتی که بانک اعلام می‌کند، نه حاصلِ تراکنش‌ها (§۱۸).
    blocked_amount: Decimal = Decimal(0)
    cheque_print_format: str = ""
    is_active: bool
    #: هر سه **مشتق‌اند** و هیچ‌کدام ستون نیستند. `available` = مانده − بلوکه.
    opening_balance: Decimal = Decimal(0)
    balance: Decimal = Decimal(0)
    available_balance: Decimal = Decimal(0)

    model_config = {"from_attributes": True}


class CheckIn(BaseModel):
    type: str
    number: str
    #: شماره‌ی پشتِ برگ — با شماره‌ی چک یکی نیست و در بانک با همین پیگیری می‌شود.
    back_number: str = ""
    #: شناسه‌ی صیادیِ ۱۶رقمی. یکتاییِ واقعیِ برگ همین است، نه شماره‌ی چک که بینِ
    #: بانک‌ها تکرار می‌شود.
    sayad_id: str = ""
    bank_name: str = ""
    amount: Decimal
    issue_date: date
    due_date: date
    contact_id: UUID | None = None
    description: str = ""
    description2: str = ""
    #: برگِ کدام دسته‌چک است (فقط برای چکِ پرداختنی). NULL = بدونِ دسته.
    checkbook_id: UUID | None = None

    # ── هویتِ برگ — همه اختیاری، پس هیچ فراخوانیِ موجودی نمی‌شکند ──
    #: کد صیادی، **جدا از شماره‌ی چک**. شانزده رقم.
    sayad_id: str = ""
    back_number: str = ""
    branch_name: str = ""
    branch_code: str = ""
    #: شماره‌حسابِ صادرکننده، نه ما.
    account_number: str = ""
    #: صاحبِ چک — چکِ شخصِ ثالث با طرف‌حسابِ ما یکی نیست.
    owner_name: str = ""

    @model_validator(mode="after")
    def validate_check(self) -> "CheckIn":
        if self.type not in ("receivable", "payable"):
            raise ValueError("نوع چک باید receivable یا payable باشد")
        if self.amount <= 0:
            raise ValueError("مبلغ چک باید بزرگ‌تر از صفر باشد")
        self.sayad_id = self.sayad_id.strip()
        if self.sayad_id and not self.sayad_id.isdigit():
            raise ValueError("کد صیادی فقط رقم است")
        if self.sayad_id and len(self.sayad_id) != 16:
            raise ValueError("کد صیادی ۱۶ رقم است")
        return self


class CheckOut(BaseModel):
    id: UUID
    type: str
    number: str
    back_number: str = ""
    sayad_id: str = ""
    bank_name: str
    amount: Decimal
    issue_date: date
    due_date: date
    status: str
    description: str
    description2: str = ""
    contact_id: UUID | None
    contact_name: str | None = None
    bank_account_id: UUID | None
    checkbook_id: UUID | None = None
    receipt_id: UUID | None = None
    #: چکی که با اعلامیه‌ی پرداخت صادر یا خرج شده — راهِ رفتن به همان سند (§۱۵).
    payment_id: UUID | None = None
    branch_name: str = ""
    branch_code: str = ""
    account_number: str = ""
    owner_name: str = ""
    voided_at: datetime | None = None
    #: صندوقی که چک در آن نقد شد — فقط برای وضعیتِ `cashed`.
    cashbox_id: UUID | None = None
    #: **«الان کجاست؟» (§۲۰).** مشتق از وضعیت و پیوندها، نه ستونِ ذخیره‌شده.
    holder_kind: str = "none"
    holder_label: str = ""
    holder_id: UUID | None = None

    model_config = {"from_attributes": True}


class CheckStatusUpdateIn(BaseModel):
    status: str
    bank_account_id: UUID | None = None
    #: برای «نقد کردن». خالی = صندوقِ پیش‌فرض.
    cashbox_id: UUID | None = None
    #: طرفِ مقابلِ همین عملیات — که لزوماً صاحبِ چک نیست (گیرنده‌ی چکِ خرج‌شده).
    contact_id: UUID | None = None
    #: تاریخِ عملیات. خالی = سررسیدِ چک، همان پیش‌فرضِ پیشین.
    event_date: date | None = None
    note: str = ""


class BankDepositWithdrawIn(BaseModel):
    bank_account_id: UUID
    transaction_date: date
    amount: Decimal  # مثبت = واریز، منفی = برداشت
    counter_account_id: UUID
    description: str = ""

    @model_validator(mode="after")
    def validate_amount(self) -> "BankDepositWithdrawIn":
        if self.amount == 0:
            raise ValueError("مبلغ نمی‌تواند صفر باشد")
        return self


class BankTransactionOut(BaseModel):
    id: UUID
    bank_account_id: UUID
    transaction_date: date
    amount: Decimal
    description: str
    is_reconciled: bool
    source_type: str

    model_config = {"from_attributes": True}


class BankStatementLineIn(BaseModel):
    line_date: date
    amount: Decimal
    description: str = ""
    #: شماره‌ی مرجع/پیگیریِ بانک، اگر فایل داشته باشد. با آمدنش وارداتِ دوباره
    #: واقعاً بی‌اثر می‌شود؛ بی آن، تشخیصِ تکرار به شمارشِ ردیف‌های هم‌شکل
    #: برمی‌گردد که ضعیف‌تر است ولی از هیچ بهتر.
    external_ref: str | None = None


class BankStatementImportIn(BaseModel):
    lines: list[BankStatementLineIn]

    @model_validator(mode="after")
    def validate_lines(self) -> "BankStatementImportIn":
        if not self.lines:
            raise ValueError("حداقل یک ردیف صورت‌حساب لازم است")
        return self


class BankStatementLineOut(BaseModel):
    id: UUID
    bank_account_id: UUID
    line_date: date
    amount: Decimal
    description: str
    external_ref: str | None
    matched_transaction_id: UUID | None

    model_config = {"from_attributes": True}


class MatchStatementLineIn(BaseModel):
    bank_transaction_id: UUID


class ReconciliationSummaryOut(BaseModel):
    statement_total: Decimal
    matched_count: int
    unmatched_statement_lines: list[BankStatementLineOut]
    unreconciled_system_transactions: list[BankTransactionOut]


class PettyCashFundIn(BaseModel):
    name: str
    #: تنخواه‌دار **طرف حساب** است نه کاربر — ممکن است حسابِ ورود نداشته باشد.
    custodian_contact_id: UUID | None = None
    location: str = ""
    #: ۰ = بی‌سقف. هشدار است نه گارد.
    spending_limit: Decimal = Decimal(0)
    is_active: bool = True
    notes: str = ""

    @model_validator(mode="after")
    def _valid(self) -> "PettyCashFundIn":
        if not self.name.strip():
            raise ValueError("نامِ صندوق تنخواه الزامی است")
        if self.spending_limit < 0:
            raise ValueError("سقفِ هزینه نمی‌تواند منفی باشد")
        return self


class PettyCashFundPatch(PettyCashFundIn):
    """ویرایشِ جزئی — تعویضِ تنخواه‌دار نباید بقیه‌ی پرونده را بازنویسی کند."""

    name: str | None = None

    @model_validator(mode="after")
    def _valid(self) -> "PettyCashFundPatch":
        if "name" in self.model_fields_set and not (self.name or "").strip():
            raise ValueError("نامِ صندوق تنخواه نمی‌تواند خالی باشد")
        if self.spending_limit < 0:
            raise ValueError("سقفِ هزینه نمی‌تواند منفی باشد")
        return self


class PettyCashFundOut(BaseModel):
    id: UUID
    name: str
    custodian_contact_id: UUID | None
    location: str
    spending_limit: Decimal
    is_active: bool
    notes: str

    model_config = {"from_attributes": True}


class PettyCashChargeIn(BaseModel):
    transaction_date: date
    amount: Decimal
    source_account_id: UUID
    description: str = ""
    #: کدام صندوق. تهی = صندوقِ پیش‌فرض (تنها صندوقِ فعال)، تا رابطِ مستقر نشکند.
    fund_id: UUID | None = None
    evidence_ref: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "PettyCashChargeIn":
        if self.amount <= 0:
            raise ValueError("مبلغ باید بزرگ‌تر از صفر باشد")
        return self


class PettyCashExpenseIn(BaseModel):
    transaction_date: date
    amount: Decimal
    expense_account_id: UUID
    description: str = ""
    fund_id: UUID | None = None
    evidence_ref: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "PettyCashExpenseIn":
        if self.amount <= 0:
            raise ValueError("مبلغ باید بزرگ‌تر از صفر باشد")
        return self


class PettyCashReturnIn(BaseModel):
    """استردادِ ماندهٔ تنخواه — مسیری که تا امروز وجود نداشت.

    `destination_account_id` جایی است که پول برمی‌گردد (صندوق یا بانک). این
    **بازگشتِ وجه** است نه هزینه؛ تا امروز تنها راهش ثبتِ یک «هزینه»ی جعلی بود
    که دفتر آن را هزینه می‌دید.
    """

    transaction_date: date
    amount: Decimal
    destination_account_id: UUID
    description: str = ""
    fund_id: UUID | None = None
    evidence_ref: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "PettyCashReturnIn":
        if self.amount <= 0:
            raise ValueError("مبلغ باید بزرگ‌تر از صفر باشد")
        return self


class PettyCashTransactionOut(BaseModel):
    id: UUID
    type: str
    transaction_date: date
    amount: Decimal
    description: str
    counter_account_id: UUID
    fund_id: UUID | None
    evidence_ref: str

    model_config = {"from_attributes": True}


class CheckbookIn(BaseModel):
    bank_account_id: UUID
    #: سریِ روی جلد (صیاد یا شماره‌ی داخلیِ بانک). اختیاری.
    serial: str = ""
    first_number: str
    last_number: str
    #: اگر ۰ بماند و شماره‌ها عددی باشند، خودِ سرور حساب می‌کند.
    leaf_count: int = 0
    issue_date: date | None = None
    description: str = ""
    #: خالی یعنی «از حسابِ بانکی ارث ببر». موتورِ چاپ جداست و هنوز وجود ندارد.
    cheque_print_format: str = ""


class CheckbookUpdateIn(BaseModel):
    """ویرایشِ دسته — همه‌ی فیلدها اختیاری.

    `exclude_unset` در سرویس یعنی «هرچه نفرستادی دست نمی‌خورد». شِمای کاملِ اجباری
    اینجا همان اشکالی را می‌ساخت که در کارت‌خوان دیدیم: ویرایشِ توضیحاتِ یک دسته‌ی
    بسته، بی‌صدا بازش می‌کرد.
    """

    bank_account_id: UUID | None = None
    serial: str | None = None
    first_number: str | None = None
    last_number: str | None = None
    leaf_count: int | None = None
    issue_date: date | None = None
    description: str | None = None
    cheque_print_format: str | None = None
    is_active: bool | None = None


class CheckbookLeafOut(BaseModel):
    """یک برگِ خرج‌شده و چکی که از آن درآمد — ناوبریِ برعکسِ دسته ← برگ ← چک."""

    number: str
    check_id: UUID
    status: str
    amount: Decimal
    issue_date: date
    due_date: date
    contact_name: str | None = None


class CheckbookOut(BaseModel):
    id: UUID
    bank_account_id: UUID
    bank_account_name: str
    serial: str
    first_number: str
    last_number: str
    leaf_count: int
    #: چند برگ خرج شده و چند تا مانده — از روی چک‌های وصل‌شده شمرده می‌شود.
    used_count: int
    remaining_count: int
    issue_date: date | None
    description: str
    is_active: bool
    cheque_print_format: str = ""


