"""حسابِ آزمایشیِ ۱۴روزه (trial)

Revision ID: 0051
Revises: 0050

دو ستون روی `tenants`، بدونِ جدولِ تازه:
- `is_trial` — آیا این مستأجر یک حسابِ آزمایشیِ رایگان است. server_default='false' تا
  هیچ مشتریِ واقعیِ موجود به‌اشتباه آزمایشی نشود؛ فقط ثبت‌نامِ تازه True می‌گیرد و
  خریدِ پلن دوباره False می‌کند.
- `trial_reminder_sent_at` — لحظه‌ی ارسالِ یادآوریِ «نزدیکِ انقضا»؛ تا کرونِ روزانه
  دوباره‌کاری نکند و هر حساب فقط یک بار یادآوری بگیرد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0051"
down_revision: Union[str, None] = "0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("is_trial", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("tenants", sa.Column("trial_reminder_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "trial_reminder_sent_at")
    op.drop_column("tenants", "is_trial")
