"""تولید — تفکیکِ دستمزد و سربارِ نشسته روی هر سفارش.

`0161` بهای مواد را روی سفارش نگه می‌داشت (`material_cost_issued`) ولی دستمزد و
سربارِ گامِ «محاسبه قیمت تمام‌شده» فقط به سندِ حسابداری می‌رفت و **هیچ‌جا به
سفارش گره نمی‌خورد** — یعنی «گزارشِ قیمت تمام‌شده» نمی‌توانست سه جزء (مواد ·
دستمزد · سربار) را از هم تفکیک کند، که دقیقاً کارِ آن گزارش است.

دو ستونِ ساده‌ی جمع‌شونده، هم‌الگوی `material_cost_issued`. هیچ FKای ندارند، پس
`rls_disabled` لازم نیست؛ `server_default` سفارش‌های موجود را صفر می‌گذارد که
درست است (تا امروز هیچ دستمزدی از این مسیر ننشسته).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0162"
down_revision: Union[str, None] = "0161"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "production_plans",
        sa.Column("labor_cost_applied", sa.Numeric(18, 0), server_default="0", nullable=False),
    )
    op.add_column(
        "production_plans",
        sa.Column("overhead_cost_applied", sa.Numeric(18, 0), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("production_plans", "overhead_cost_applied")
    op.drop_column("production_plans", "labor_cost_applied")
