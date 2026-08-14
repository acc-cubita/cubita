"""صفحه‌بندی keyset (نه offset).

چرا keyset: لیست‌های حسابداری ذاتاً زمان‌مرتب‌اند و کاربر معمولاً از تازه‌ترین به
قدیمی‌تر می‌رود. offset هرچه عمیق‌تر می‌رود کندتر می‌شود چون پایگاه‌داده باید ردیف‌های
رد‌شده را هم بخواند، و اگر همزمان سندی ثبت شود ردیف‌ها بین صفحه‌ها جابه‌جا می‌شوند و
کاربر یک سند را دوبار می‌بیند یا اصلاً نمی‌بیند. keyset هر دو مشکل را ندارد.

کرسر مقدارِ کلیدهای مرتب‌سازی آخرین ردیف صفحه است، base64 شده. عمداً مبهم است تا
کلاینت به ساختارش وابسته نشود و بعداً بتوانیم کلید مرتب‌سازی را عوض کنیم.
"""
import base64
import binascii
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Generic, Sequence, TypeVar
from uuid import UUID

from fastapi import HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import bindparam, tuple_

T = TypeVar("T")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class Page(BaseModel, Generic[T]):
    """پوشش استاندارد پاسخ لیستی.

    next_cursor برابر None یعنی صفحه‌ی آخر. عمداً total برنمی‌گردانیم: شمارش کل روی
    جدولی که مدام رشد می‌کند خودش همان کوئری گرانی است که با صفحه‌بندی می‌خواستیم
    از آن فرار کنیم. اگر جایی واقعاً لازم شد، اندپوینت شمارش جدا اضافه می‌شود.
    """

    items: list[T]
    next_cursor: str | None = None


class PageParams:
    """پارامترهای مشترک صفحه‌بندی برای اندپوینت‌های لیستی."""

    def __init__(
        self,
        limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="تعداد ردیف در هر صفحه"),
        cursor: str | None = Query(None, description="کرسر صفحه‌ی بعد؛ از next_cursor پاسخ قبلی"),
    ):
        self.limit = limit
        self.cursor = cursor


def _jsonable(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    return value


def encode_cursor(values: Sequence) -> str:
    payload = json.dumps([_jsonable(v) for v in values], separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> list:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        values = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کرسر صفحه‌بندی نامعتبر است") from exc
    if not isinstance(values, list):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کرسر صفحه‌بندی نامعتبر است")
    return values


def paginate(query, sort_attrs: Sequence, params: PageParams, *, descending: bool = True) -> tuple[list, str | None]:
    """یک صفحه به‌علاوه‌ی کرسر بعدی برمی‌گرداند.

    sort_attrs باید ستون‌های مدل باشند (مثل JournalEntry.entry_date) و ترکیبشان باید
    یکتا باشد، وگرنه ردیف‌های هم‌کلید بین صفحه‌ها گم می‌شوند. معمولاً یعنی ستون تاریخ
    به‌علاوه‌ی شماره‌ی سند یا id.

    همه‌ی کلیدها یک جهت دارند؛ مقایسه‌ی tuple در SQL فقط با جهت یکسان معنا می‌دهد.
    """
    if params.cursor:
        values = decode_cursor(params.cursor)
        if len(values) != len(sort_attrs):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "کرسر صفحه‌بندی با این لیست سازگار نیست")
        binds = tuple_(
            *[
                bindparam(f"_cursor_{i}", value=value, type_=attr.expression.type)
                for i, (attr, value) in enumerate(zip(sort_attrs, values))
            ]
        )
        key = tuple_(*[attr.expression for attr in sort_attrs])
        query = query.filter(key < binds if descending else key > binds)

    order = [attr.desc() if descending else attr.asc() for attr in sort_attrs]
    rows = query.order_by(*order).limit(params.limit + 1).all()

    if len(rows) <= params.limit:
        return rows, None

    rows = rows[: params.limit]
    last = rows[-1]
    return rows, encode_cursor([getattr(last, attr.key) for attr in sort_attrs])
