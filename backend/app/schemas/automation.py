from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LetterIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    kind: Literal["incoming", "outgoing", "internal"]
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(default="", max_length=50000)
    sender: str = Field(default="", max_length=200)
    addressee: str = Field(default="", max_length=200)
    external_number: str = Field(default="", max_length=100)
    external_date: date | None = None
    letter_date: date
    due_date: date | None = None
    priority: Literal["normal", "urgent"] = "normal"


class VersionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)


class LetterUpdate(LetterIn):
    version: int = Field(ge=1)


class ReferralIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    recipients: list[UUID] = Field(min_length=1, max_length=20)
    instruction: str = Field(min_length=1, max_length=4000)
    due_date: date | None = None


class CompletionIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    response: str = Field(min_length=1, max_length=10000)
