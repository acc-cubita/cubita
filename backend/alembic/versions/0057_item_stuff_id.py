"""شناسه‌ی کالا/خدمتِ مالیاتی (sstid) روی کالا + پیش‌فرضِ کسب‌وکار روی تنظیماتِ مؤدیان

Revision ID: 0057
Revises: 0056

سامانه مؤدیان برای هر ردیفِ صورتحساب یک «شناسه کالا/خدمت»ِ رسمیِ ۱۳رقمی (`^\\d{13}$`)
می‌خواهد. تا امروز `sstid` از `sku` پر می‌شد که الگو را رد می‌کرد. این مهاجرت دو ستون
اضافه می‌کند:
- `items.tax_stuff_id`: کدِ رسمیِ همان کالا (per-item).
- `moadian_settings.default_stuff_id`: کدِ پیش‌فرضِ کسب‌وکار که وقتی کالایی کدِ خودش را
  ندارد جایش می‌نشیند (مناسبِ کسب‌وکارِ تک‌محصولی/خدماتی).
هر دو رشته‌ی ساده‌اند (راز نیستند) و پیش‌فرض خالی، پس روی ردیف‌های موجود بی‌خطرند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0057"
down_revision: Union[str, None] = "0056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "items",
        sa.Column("tax_stuff_id", sa.String(20), nullable=False, server_default=""),
    )
    op.add_column(
        "moadian_settings",
        sa.Column("default_stuff_id", sa.String(20), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("moadian_settings", "default_stuff_id")
    op.drop_column("items", "tax_stuff_id")
