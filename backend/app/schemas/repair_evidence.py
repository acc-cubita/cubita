from typing import Literal
from uuid import UUID
from pydantic import Field, model_validator
from app.schemas.repair import RepairInput, VersionIn


class Accessory(RepairInput):
    title: str = Field(min_length=1, max_length=200)
    quantity: int = Field(ge=1, le=10000)
    condition: str = Field(min_length=1, max_length=500)


class InitialTest(RepairInput):
    title: str = Field(min_length=1, max_length=200)
    result: Literal['healthy', 'faulty', 'not_tested', 'not_applicable']
    reason: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def untested_reason(self):
        if self.result == 'not_tested' and not self.reason:
            raise ValueError('برای آزمون انجام‌نشده دلیل بنویسید.')
        return self


class ImageMark(RepairInput):
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)
    category: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    severity: Literal['minor', 'moderate', 'severe', 'unspecified'] = 'unspecified'


class IntakeImage(RepairInput):
    attachment_id: UUID
    view: str = Field(min_length=1, max_length=120)
    phase: Literal['intake', 'delivery'] = 'intake'
    marks: list[ImageMark] = Field(default_factory=list, max_length=100)


class IntakeEvidenceIn(VersionIn):
    previous_revision: int = Field(ge=0)
    reason: str = Field(min_length=3, max_length=2000)
    accessories: list[Accessory] = Field(default_factory=list, max_length=100)
    tests: list[InitialTest] = Field(default_factory=list, max_length=100)
    images: list[IntakeImage] = Field(default_factory=list, max_length=50)

    @model_validator(mode='after')
    def unique_entries(self):
        for entries in ([a.title for a in self.accessories], [t.title for t in self.tests], [i.attachment_id for i in self.images]):
            if len(entries) != len(set(entries)):
                raise ValueError('ردیف تکراری را حذف کنید؛ برای لوازم تعداد را تغییر دهید.')
        return self
