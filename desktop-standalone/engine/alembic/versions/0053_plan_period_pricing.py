"""قیمت‌گذاریِ چنددوره‌ای پلن‌ها (ماهانه/شش‌ماهه/سالانه)

Revision ID: 0053
Revises: 0052

- `plans.prices` (JSONB) — نگاشتِ دوره→قیمت، مثلِ `{"monthly":..,"semiannual":..,"yearly":..}`.
  ستونِ `price_toman` به‌عنوانِ قیمتِ پیش‌فرض (سالانه) می‌ماند تا خواننده‌های قدیمی نشکنند.
- `purchases.billing_period` — دوره‌ای که مشتری هنگامِ خرید انتخاب کرده؛ طولِ اشتراک از همین
  خوانده می‌شود نه از پیش‌فرضِ پلن (وگرنه خریدِ ماهانه یک سال اعتبار می‌گرفت).

بک‌فیل: برای پلن‌های موجود `prices = {"yearly": price_toman}` تا پیش از به‌روزرسانیِ دستیِ
مقادیرِ تازه هم پاسخِ /api/plans معتبر بماند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0053"
down_revision: Union[str, None] = "0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("prices", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        "purchases",
        sa.Column("billing_period", sa.String(length=20), nullable=False, server_default="yearly"),
    )
    # بک‌فیل: قیمتِ سالانه‌ی فعلی را داخلِ نگاشت بگذار تا هیچ پلنی prices خالی نداشته باشد.
    op.execute(
        "UPDATE plans SET prices = jsonb_build_object('yearly', price_toman::text) WHERE prices IS NULL"
    )


def downgrade() -> None:
    op.drop_column("purchases", "billing_period")
    op.drop_column("plans", "prices")
