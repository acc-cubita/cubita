"""فعال‌سازیِ شماره‌ی موبایل با کدِ پیامکی

Revision ID: 0050
Revises: 0049

دو ستونِ کوچک، بدونِ جدولِ تازه:
- `users.phone_verified_at` — لحظه‌ی تأییدِ شماره؛ NULL یعنی تأییدنشده. با هر تغییرِ
  شماره دوباره NULL می‌شود (در کدِ اپ)، پس همیشه یعنی «همین شماره تأیید شده».
- `auth_tokens.attempts` — شمارنده‌ی تلاشِ ناموفق روی کدهای کوتاهِ عددی. کدِ ۶رقمی
  حدس‌زدنی است، پس بعد از چند تلاشِ غلط باید قفل شود؛ توکنِ ۲۵۶بیتیِ بازیابیِ رمز به
  این نیاز ندارد ولی ستون مشترک است و server_default='0' آن ردیف‌ها را دست‌نخورده می‌گذارد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0050"
down_revision: Union[str, None] = "0049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "auth_tokens",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("auth_tokens", "attempts")
    op.drop_column("users", "phone_verified_at")
