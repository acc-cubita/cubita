"""نوعِ حسابِ بازار روی مستأجر (standard | distributor | retailer)

Revision ID: 0058
Revises: 0057

بازارِ عمده‌فروشیِ درون‌پلتفرمی دو نوعِ حسابِ انحصاری دارد: «پخش‌کننده» و «فروشگاه».
این ستون نوع را نگه می‌دارد؛ پیش‌فرض standard تا همه‌ی حساب‌های موجود بی‌تغییر بمانند.
راز نیست و در MeOut به فرانت می‌رسد تا ماژول‌های بازار گیت شوند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0058"
down_revision: Union[str, None] = "0057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("kind", sa.String(20), nullable=False, server_default="standard"),
    )


def downgrade() -> None:
    op.drop_column("tenants", "kind")
