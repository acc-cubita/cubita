from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.accounting import ACCOUNT_NATURES, ACCOUNT_TYPES, ENTRY_STATUSES


class AccountOut(BaseModel):
    id: UUID
    code: str
    name: str
    #: عنوانِ دوم (معمولاً انگلیسی). خالی = ندارد.
    name2: str = ""
    type: str
    #: ماهیتِ *صریح*؛ NULL یعنی از نوعِ حساب مشتق می‌شود.
    nature: str | None = None
    #: ماهیتِ *مؤثر* — همان چیزی که گزارش با آن می‌سنجد. همیشه پر است، پس رابط
    #: لازم نیست منطقِ مشتق‌شدن را تکرار کند.
    effective_nature: str = "any"
    is_group: bool
    is_active: bool
    #: صورتِ مالی — `balance_sheet` یا `income_statement`. **مشتق از `type` است، نه
    #: ستون**: ذخیره‌کردنش دو منبعِ حقیقت می‌ساخت که می‌توانند با هم نخوانند.
    statement_type: str = "balance_sheet"
    #: ویژگی‌های حساب — شش پرچمِ فرمِ ویرایش. معنای هرکدام در مدل مستند است.
    nature_control: bool = False
    is_fx: bool = False
    fx_revaluable: bool = False
    accepts_tafsili: bool = False
    has_tracking: bool = False
    in_management_reports: bool = True
    parent_id: UUID | None
    #: نقشِ سیستمی (cash، inventory، …) — اگر پرشده باشد، حسابِ سیستمی است و
    #: نه قابلِ حذف است نه غیرفعال‌سازی. برای حساب‌های معمولی NULL.
    system_role: str | None = None

    model_config = {"from_attributes": True}


class AccountTraitsIn(BaseModel):
    """ویژگی‌های حساب — مشترک بینِ ساخت و ویرایش.

    قیدِ «تسعیر پذیر فقط روی ارزی» این‌جا *سنجیده نمی‌شود*، چون در ویرایش هر دو
    فیلد اختیاری‌اند و ممکن است فقط یکی بیاید؛ داوریِ درست به مقدارِ فعلیِ حساب
    نیاز دارد و آن فقط در روتر در دسترس است.
    """

    #: کنترلِ ماهیت طی دوره — رصدِ این حساب در گزارشِ خلافِ ماهیت.
    nature_control: bool = False
    #: ارزی — فیلدهای ارزِ ردیفِ سند را باز می‌کند.
    is_fx: bool = False
    #: تسعیرپذیر — فقط روی حسابِ ارزی. خاموش‌بودنش روی حسابِ ارزی یعنی «تسعیرش نکن».
    fx_revaluable: bool = False
    #: تفصیلی‌پذیر — ردیفِ سندِ این حساب **باید** تفصیلی داشته باشد. ربطی به
    #: زیرشاخه‌ی درختی ندارد؛ آن کدینگِ چهارسطحی است و قیدِ خودش را دارد.
    accepts_tafsili: bool = False
    #: پیگیری — شماره و تاریخِ پیگیری روی ردیفِ سندِ این حساب.
    has_tracking: bool = False
    #: نمایش در گزارشاتِ مدیریتی. پیش‌فرض روشن.
    in_management_reports: bool = True


class AccountCreateIn(AccountTraitsIn):
    """ساختِ حسابِ تازه در چارت — زیرِ یک سرفصل یا در ریشه."""

    code: str
    name: str
    name2: str = ""
    type: str
    #: خالی بگذارید تا از نوعِ حساب مشتق شود — حالتِ درست برای تقریباً همه‌ی حساب‌ها.
    nature: str | None = None
    is_group: bool = False
    parent_id: UUID | None = None

    @field_validator("code", "name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("این فیلد نمی‌تواند خالی باشد")
        return v.strip()

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in ACCOUNT_TYPES:
            raise ValueError("نوعِ حساب نامعتبر است")
        return v

    @field_validator("nature")
    @classmethod
    def _valid_nature(cls, v: str | None) -> str | None:
        #: رشته‌ی خالی از فرم می‌آید و همان «مشتق از نوع» است، نه مقدارِ نامعتبر.
        if not v:
            return None
        if v not in ACCOUNT_NATURES:
            raise ValueError("ماهیتِ حساب نامعتبر است")
        return v


class AccountUpdateIn(BaseModel):
    """ویرایشِ حساب — نام، عنوانِ دوم، ماهیت و فعال‌بودن. کد/نوع/سرفصل پس از ساخت
    ثابت‌اند (روی اسناد و گزارش‌ها نشسته‌اند).

    ماهیت برخلافِ آن‌ها هر وقت قابلِ تغییر است: چیزی را بازنویسی نمی‌کند، فقط
    معیارِ گزارش را عوض می‌کند."""

    name: str | None = None
    name2: str | None = None
    nature: str | None = None
    is_active: bool | None = None
    #: ویژگی‌های حساب — همه اختیاری. `exclude_unset` در روتر یعنی فیلدِ نیامده
    #: دست‌نخورده می‌ماند، پس فرم می‌تواند فقط همان تیکی را بفرستد که عوض شده.
    nature_control: bool | None = None
    is_fx: bool | None = None
    fx_revaluable: bool | None = None
    accepts_tafsili: bool | None = None
    has_tracking: bool | None = None
    in_management_reports: bool | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("نام حساب نمی‌تواند خالی باشد")
        return v.strip()

    @field_validator("nature")
    @classmethod
    def _valid_nature(cls, v: str | None) -> str | None:
        if not v:
            return None
        if v not in ACCOUNT_NATURES:
            raise ValueError("ماهیتِ حساب نامعتبر است")
        return v


class JournalLineIn(BaseModel):
    account_id: UUID
    debit: Decimal = Decimal(0)
    credit: Decimal = Decimal(0)
    description: str = ""
    #: بُعدِ ارزی و تفصیلیِ سایر — هر دو اختیاری. بدهکار/بستانکارِ بالا همیشه ریالی
    #: است؛ این‌ها فقط *مبنای* آن عدد را نگه می‌دارند تا تسعیر و گزارشِ تحلیلی
    #: بعداً بتوانند رویشان تکیه کنند.
    currency_code: str | None = None
    fx_amount: Decimal | None = None
    fx_rate: Decimal | None = None
    analytic_id: UUID | None = None
    #: پیگیری — فقط برای حسابی که `has_tracking` دارد؛ وگرنه روتر ردش می‌کند تا
    #: داده‌ی پیگیری بی‌صدا دور ریخته نشود.
    tracking_no: str | None = Field(default=None, max_length=50)
    tracking_date: date | None = None

    @field_validator("tracking_no")
    @classmethod
    def _clean_tracking_no(cls, v: str | None) -> str | None:
        #: مثلِ `sub_number`: رشته‌ی خالیِ فرم همان «ندارد» است، نه مقدار.
        return (v or "").strip() or None

    @model_validator(mode="after")
    def _fx_is_all_or_nothing(self) -> "JournalLineIn":
        """سه‌گانه‌ی ارزی یا کامل است یا اصلاً نیست.

        ردیفِ نیمه‌کاره بی‌صدا خراب می‌شود، نه با خطا:

        * بدونِ `fx_rate`، نرخِ **لحظه‌ی ثبت** برای همیشه گم می‌شود. مبلغِ ریالیِ
          ردیف همان می‌ماند ولی دیگر معلوم نیست از کدام نرخ آمده، و حسابرسی و
          بازسازیِ تسعیر ناممکن می‌شود.
        * بدونِ `fx_amount`، ردیف از فیلترِ `fx_revaluation_preview` بیرون می‌افتد
          و تسعیرِ پایانِ دوره کمتر از واقعیت درمی‌آید — بی‌آنکه جایی خطایی بیاید.
        * بدونِ `currency_code` معلوم نیست عدد به کدام ارز است.

        پس یا هر سه، یا هیچ‌کدام. مبلغِ ریالی (بدهکار/بستانکار) جدا و همیشه لازم
        است؛ این سه فقط *مبنای* آن عددند.
        """
        parts = {
            "ارز": self.currency_code,
            "مبلغِ ارزی": self.fx_amount,
            "نرخ": self.fx_rate,
        }
        given = [name for name, value in parts.items() if value is not None]
        if given and len(given) != len(parts):
            missing = [name for name, value in parts.items() if value is None]
            raise ValueError(
                f"ردیفِ ارزی ناقص است: «{'، '.join(given)}» آمده ولی "
                f"«{'، '.join(missing)}» نه. هر سه با هم لازم‌اند."
            )
        if self.fx_rate is not None and self.fx_rate <= 0:
            raise ValueError("نرخِ ارز باید بزرگ‌تر از صفر باشد")
        return self


class JournalEntryIn(BaseModel):
    entry_date: date
    description: str = ""
    #: مرکز هزینه/پروژه‌ی سند؛ به همه‌ی ردیف‌هایش منتقل می‌شود. None = بدون مرکز.
    cost_center_id: UUID | None = None
    #: تفصیلیِ سایرِ سند — مثلِ مرکزِ هزینه به ردیف‌ها ارث می‌رسد، مگر خودِ ردیف
    #: تفصیلیِ صریح داشته باشد.
    analytic_id: UUID | None = None
    #: سندِ تازه به‌صورتِ پیش‌فرض *موقت* ثبت می‌شود تا در کارتابل بازبینی شود.
    #: `permanent` یعنی همان لحظه قطعی — برای دفترداری که بازبینی نمی‌خواهد.
    status: str = "temporary"
    #: شماره فرعی — ارجاعِ آزادِ کاربر (شماره‌ی سند در سیستمِ قبلی، شماره‌ی پرونده،
    #: کدِ دسته). عطف اینجا گرفته نمی‌شود: آن را فقط سرور می‌دهد.
    sub_number: str | None = Field(default=None, max_length=30)
    lines: list[JournalLineIn]

    @field_validator("sub_number")
    @classmethod
    def _clean_sub_number(cls, v: str | None) -> str | None:
        #: رشته‌ی خالی و فاصله‌ی تنها همان «خالی» است. بدونِ این، فیلدِ دست‌نخورده‌ی
        #: فرم به‌صورتِ "" ذخیره می‌شد و جستجو و «دارد/ندارد» را به هم می‌ریخت.
        cleaned = (v or "").strip()
        return cleaned or None

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        if v not in ENTRY_STATUSES:
            raise ValueError("وضعیتِ سند نامعتبر است")
        return v

    @model_validator(mode="after")
    def validate_balance(self) -> "JournalEntryIn":
        if len(self.lines) < 2:
            raise ValueError("سند حسابداری باید حداقل دو ردیف داشته باشد")
        total_debit = sum(line.debit for line in self.lines)
        total_credit = sum(line.credit for line in self.lines)
        if total_debit != total_credit:
            raise ValueError(f"سند متوازن نیست: بدهکار={total_debit} بستانکار={total_credit}")
        if total_debit == 0:
            raise ValueError("مجموع سند نمی‌تواند صفر باشد")
        return self


class SubNumberIn(BaseModel):
    """تنها فیلدی از سند که بعد از ثبت هم قابلِ اصلاح است."""

    sub_number: str | None = Field(default=None, max_length=30)

    @field_validator("sub_number")
    @classmethod
    def _clean(cls, v: str | None) -> str | None:
        cleaned = (v or "").strip()
        return cleaned or None


class JournalLineOut(BaseModel):
    id: UUID
    account_id: UUID
    cost_center_id: UUID | None = None
    analytic_id: UUID | None = None
    debit: Decimal
    credit: Decimal
    description: str
    currency_code: str | None = None
    fx_amount: Decimal | None = None
    fx_rate: Decimal | None = None
    tracking_no: str | None = None
    tracking_date: date | None = None

    model_config = {"from_attributes": True}


class EntrySourceOut(BaseModel):
    """عملیاتی که این سند از آن آمده — مشتق، نه ذخیره‌شده.

    `id` و `number` فقط وقتی می‌آیند که منبع **یکتا** باشد. حقوق و دستمزد یک سند
    برای کلِ دوره می‌زند و همه‌ی فیش‌ها به همان اشاره می‌کنند؛ آن‌جا فقط `count`
    معنا دارد و نشان‌دادنِ یکی از فیش‌ها غلط توصیف می‌کند.
    """

    source_type: str
    #: نامِ کلاسِ مدلِ منبع — برای رابط و اشکال‌زدایی، نه برای منطق.
    model: str
    count: int
    id: UUID | None = None
    number: str | None = None


class JournalEntryOut(BaseModel):
    id: UUID
    number: int | None
    #: شماره عطف — سرور لحظه‌ی ثبت می‌دهد و هیچ عملیاتی عوضش نمی‌کند. فقط سندهای
    #: پیش از مهاجرتِ ۰۰۸۵ که هنوز پر نشده‌اند می‌توانند NULL باشند.
    atf_number: int | None = None
    #: شماره فرعی — ارجاعِ آزادِ کاربر. NULL = خالی.
    sub_number: str | None = None
    entry_date: date
    description: str
    source_type: str
    #: هویتِ عملیاتِ منبع. `None` یعنی سند عملیاتِ بیرونی ندارد — دستی، تسعیر،
    #: اختتامیه. از `journal_entry_id`ِ خودِ ماژول‌ها مشتق می‌شود، نه از ستونی روی
    #: سند؛ توضیحش در `services/entry_source.py`.
    source: EntrySourceOut | None = None
    #: موقت/دائم — «دائم» یعنی بازبینی‌شده و بیرون از دسترسِ ادغام و بازشماره‌گذاری.
    status: str = "temporary"
    finalized_at: datetime | None = None
    #: مهرِ ابطال (اگر باطل شده) و ارجاع به سندی که این سند معکوسِ آن است — برای
    #: نمایشِ وضعیت در دفتر روزنامه (سندِ باطل و سندِ برگشتیِ متناظر).
    voided_at: datetime | None = None
    reverses_entry_id: UUID | None = None
    lines: list[JournalLineOut]

    model_config = {"from_attributes": True}

