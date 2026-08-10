"""ستونِ گواهیِ امضا (x5c) روی تنظیماتِ مؤدیان

Revision ID: 0056
Revises: 0055

پروتکلِ نسخه‌ی دومِ سامانه مؤدیان (RC_TICS.IS_v1.6) علاوه بر کلید خصوصی، به خودِ
گواهیِ X.509 هم نیاز دارد تا در هدرِ `x5c` بسته‌های JWS/توکن قرار گیرد. این ستون
گواهیِ PEM را نگه می‌دارد؛ مثلِ کلید خصوصی راز نیست ولی کنارِ آن ذخیره می‌شود.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0056"
down_revision: Union[str, None] = "0055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "moadian_settings",
        sa.Column("certificate_pem", sa.Text, nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("moadian_settings", "certificate_pem")
