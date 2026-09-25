"""فرمِ «تماس برای خرید»ِ سایتِ cubita.ir — ثبتِ عمومیِ درخواست.

پلن‌های قیمت‌دار از سایت برداشته شدند؛ خریدارِ هر چهار محصول فرمی پر می‌کند و کارشناسِ فروش در
`admin.cubita.ir` (`admin_sales.py`) پیگیری‌اش می‌کند.

**چرا احراز هویت نمی‌خواهد:** فرستنده هنوز مشتری نیست. **ولی درِ باز نیست:** سقفِ نرخِ IP
(`limit_sales_inquiry`)، سقفِ اندازه‌ی هر میدان، و یک میدانِ تله (`website`) که انسان نمی‌بیندش و
ربات پرش می‌کند — درخواستِ ربات بی‌صدا «پذیرفته» می‌شود ولی نوشته نمی‌شود، تا ربات چیزی یاد نگیرد.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.sales_inquiry import SALES_PRODUCTS, SalesInquiry
from app.rate_limit import limit_sales_inquiry

router = APIRouter(prefix="/api/sales-inquiries", tags=["sales-inquiries"])

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_phone(raw: str) -> str:
    """ارقامِ فارسی/عربی به لاتین و فقط رقم و «+» — «۰۹۱۲ ۱۲۳ ۴۵۶۷» همان «09121234567» است."""
    return re.sub(r"[^\d+]", "", raw.translate(_FA_DIGITS))


class SalesInquiryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    company: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=32)
    email: str = Field(default="", max_length=200)
    product: str
    seats: int | None = Field(default=None, ge=1, le=100_000)
    message: str = Field(default="", max_length=2000)
    #: تله‌ی ربات — در فرم پنهان است؛ انسان خالی‌اش می‌گذارد.
    website: str = Field(default="", max_length=200)

    @field_validator("product")
    @classmethod
    def _product(cls, v: str) -> str:
        if v not in SALES_PRODUCTS:
            raise ValueError("محصولِ انتخاب‌شده معتبر نیست")
        return v


class SalesInquiryAck(BaseModel):
    ok: bool = True


@router.post("", response_model=SalesInquiryAck, status_code=201, dependencies=[Depends(limit_sales_inquiry)])
def create_inquiry(data: SalesInquiryIn, db: Session = Depends(get_db)) -> SalesInquiryAck:
    if data.website.strip():
        return SalesInquiryAck()
    name = data.name.strip()
    phone = normalize_phone(data.phone)
    email = data.email.strip().lower()
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "نامِ خود را بنویسید")
    if not phone and not email:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "شماره‌ی تماس یا ایمیل لازم است تا با شما تماس بگیریم")
    if phone and not (8 <= len(phone.lstrip("+")) <= 15):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "شماره‌ی تماس درست نیست")
    if email and not _EMAIL.match(email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "نشانیِ ایمیل درست نیست")
    db.add(
        SalesInquiry(
            name=name,
            company=data.company.strip(),
            phone=phone,
            email=email,
            product=data.product,
            seats=data.seats,
            message=data.message.strip(),
        )
    )
    db.flush()
    return SalesInquiryAck()
