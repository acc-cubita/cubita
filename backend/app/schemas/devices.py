from pydantic import BaseModel, field_validator


class DeviceRegisterIn(BaseModel):
    """ثبتِ توکنِ FCMِ اپ موبایل برای دریافتِ اعلانِ Push."""

    fcm_token: str
    platform: str = "android"

    @field_validator("fcm_token")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("توکنِ دستگاه نمی‌تواند خالی باشد")
        return v.strip()
