"""بازار — طرف‌حسابِ خودکارِ دو سمت روی اتصال (برای دی‌داپِ سفارش‌های پیاپی)

Revision ID: 0060
Revises: 0059

دو ستونِ nullable روی `marketplace_connections`: شناسه‌ی طرف‌حسابِ «مشتری» در دفترِ
پخش‌کننده و «تأمین‌کننده» در دفترِ فروشگاه. FK نیستند (میان‌مستأجری‌اند و در تأییدِ سفارش
دوباره اعتبارسنجی می‌شوند)، فقط برای این‌که سفارش‌های بعدیِ همان رابطه روی یک طرف‌حساب جمع شوند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0060"
down_revision: Union[str, None] = "0059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("marketplace_connections", sa.Column("distributor_customer_contact_id", UUID, nullable=True))
    op.add_column("marketplace_connections", sa.Column("retailer_supplier_contact_id", UUID, nullable=True))


def downgrade() -> None:
    op.drop_column("marketplace_connections", "retailer_supplier_contact_id")
    op.drop_column("marketplace_connections", "distributor_customer_contact_id")
