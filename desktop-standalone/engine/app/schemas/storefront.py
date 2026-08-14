from pydantic import BaseModel


class StorefrontSettingsIn(BaseModel):
    base_url: str = ""
    admin_email: str = ""
    #: خالی هنگام به‌روزرسانی یعنی «رمزِ فعلی را نگه دار» (تا رمز با ارسالِ فرم پاک نشود).
    admin_password: str = ""
    cutover_order_id: int = 0
    is_active: bool = False


class StorefrontSettingsOut(BaseModel):
    base_url: str
    admin_email: str
    #: رمز هرگز برنمی‌گردد؛ فقط اینکه ست شده یا نه.
    has_password: bool
    cutover_order_id: int
    is_active: bool
