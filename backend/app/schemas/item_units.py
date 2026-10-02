from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator


class ItemUnitIn(BaseModel):
    unit_id: UUID
    purchase_allowed: bool = True
    sale_allowed: bool = True
    inventory_allowed: bool = True
    production_allowed: bool = True
    decimal_allowed: bool = True
    is_active: bool = True


class ItemUnitPatch(BaseModel):
    purchase_allowed: bool | None = None
    sale_allowed: bool | None = None
    inventory_allowed: bool | None = None
    production_allowed: bool | None = None
    decimal_allowed: bool | None = None
    is_active: bool | None = None


class ConversionRuleIn(BaseModel):
    from_unit_id: UUID
    to_unit_id: UUID
    mode: Literal['fixed', 'variable'] = 'fixed'
    factor: Decimal | None = Field(default=None, max_digits=30, decimal_places=12, gt=0)

    @field_validator('factor', mode='before')
    @classmethod
    def exact_factor(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError('ضریب تبدیل را به صورت رشتهٔ عددی ارسال کنید')
        return value

    @model_validator(mode='after')
    def valid_rule(self):
        if self.from_unit_id == self.to_unit_id:
            raise ValueError('تبدیل واحد به خودش قاعدهٔ جدا ندارد')
        if (self.mode == 'fixed') != (self.factor is not None):
            raise ValueError('نسبت ثابت ضریب می‌خواهد و نسبت متغیر ضریب ثابت ندارد')
        return self


class ObservedRatioIn(BaseModel):
    rule_id: UUID
    from_qty: Decimal = Field(gt=0, max_digits=24, decimal_places=8)
    to_qty: Decimal = Field(gt=0, max_digits=24, decimal_places=8)

    @field_validator('from_qty', 'to_qty', mode='before')
    @classmethod
    def exact_quantities(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError('مقدار واقعی را به صورت رشتهٔ عددی ارسال کنید')
        return value


class ConvertQuantityIn(BaseModel):
    qty: Decimal = Field(max_digits=24, decimal_places=8)
    unit_id: UUID
    context: Literal['purchase', 'sale', 'inventory', 'production'] = 'inventory'
    batch_id: UUID | None = None
    observations: list[ObservedRatioIn] = Field(default_factory=list, max_length=100)

    @field_validator('qty', mode='before')
    @classmethod
    def exact_quantity(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError('مقدار را به صورت رشتهٔ عددی ارسال کنید')
        return value

    @model_validator(mode='after')
    def unique_observations(self):
        if len({row.rule_id for row in self.observations}) != len(self.observations):
            raise ValueError('نسبت واقعی یک قاعده دوبار وارد شده است')
        return self
