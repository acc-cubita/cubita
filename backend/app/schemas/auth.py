from uuid import UUID

from pydantic import BaseModel, EmailStr


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: UUID
    name: str
    email: str
    role_key: str
    role_name: str
    permissions: dict

    model_config = {"from_attributes": True}
