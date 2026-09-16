"""تولید — تحویلِ مواد به تولید و رسیدِ محصول از تولید، اسنادِ واقعیِ انبار.

فازِ ۱ «سفارش» را از «سند» جدا کرد ولی خودِ سند هنوز یک حرکتِ داخلیِ
`StockLedger` بود، نه حوالهٔ خروج/رسیدِ واقعی که کاربر خواسته بود. این مهاجرت
دو ستون اضافه می‌کند تا `services/manufacturing.py` بتواند از موتورهای
موجودِ `warehouse_issues`/`warehouse_receipts` استفاده کند، به‌جای ساختنِ
موتورِ سوم:

* `warehouse_issues.production_plan_id` — حواله‌ی «تحویل به تولید» را به
  سفارشِ مبنا وصل می‌کند (نوعِ تازه‌ی `production` در `ISSUE_TYPES`).
* `warehouse_receipts.production_plan_id` — رسیدِ محصول را همان‌طور. نوعِ
  `production` در `RECEIPT_TYPES` از قبل بود (بدونِ استفاده) و حسابداریِ
  درستش را هم داشت (`_direct_credit_account` → کالای در جریان ساخت).
* `production_plans.material_cost_issued` — جمعِ بهای حواله‌های موادِ متصل؛
  مبنای بهای رسیدِ محصول پیش از افزودنِ دستمزد/سربار.

هر دو جدولِ `warehouse_issues`/`warehouse_receipts` ردیفِ واقعی دارند — افزودنِ
ستونی با FKِ درون‌خطی باید زیرِ `rls_disabled` برود، وگرنه اعتبارسنجیِ خودکارِ
Postgres روی PG14 به سیاستِ RLS می‌خورد و با
`invalid input syntax for type uuid: ""` می‌شکند (همان باگِ مستندِ `0156`/`0157`).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled

revision: str = "0161"
down_revision: Union[str, None] = "0160"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: عیناً `ISSUE_TYPES` در `app/models/invoices.py` — «انتقال بین انبار» موتورِ
#: خودش را دارد (`stock_transfers`) و هرگز در این ستون نمی‌نشیند.
_OLD_ISSUE_TYPES = ("sale", "consumption", "other")
_NEW_ISSUE_TYPES = ("sale", "consumption", "production", "other")


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column(
        "production_plans",
        sa.Column("material_cost_issued", sa.Numeric(18, 0), server_default="0", nullable=False),
    )

    with rls_disabled(conn, ["warehouse_issues", "production_plans"]):
        op.add_column(
            "warehouse_issues",
            sa.Column("production_plan_id", UUID(as_uuid=True), sa.ForeignKey("production_plans.id"), nullable=True),
        )
    op.create_index("ix_warehouse_issues_production_plan_id", "warehouse_issues", ["production_plan_id"])

    with rls_disabled(conn, ["warehouse_receipts", "production_plans"]):
        op.add_column(
            "warehouse_receipts",
            sa.Column("production_plan_id", UUID(as_uuid=True), sa.ForeignKey("production_plans.id"), nullable=True),
        )
    op.create_index("ix_warehouse_receipts_production_plan_id", "warehouse_receipts", ["production_plan_id"])

    #: نوعِ تازهٔ `production` را به قیدِ چکِ نوعِ خروج اضافه می‌کند — بدونش
    #: `_JOURNAL_TEXT`/سرویس این نوع را می‌شناسد ولی خودِ INSERT ردِ Postgres می‌خورد.
    op.drop_constraint("ck_warehouse_issues_type", "warehouse_issues", type_="check")
    op.create_check_constraint("ck_warehouse_issues_type", "warehouse_issues", f"issue_type IN {_NEW_ISSUE_TYPES}")


def downgrade() -> None:
    op.drop_constraint("ck_warehouse_issues_type", "warehouse_issues", type_="check")
    op.create_check_constraint("ck_warehouse_issues_type", "warehouse_issues", f"issue_type IN {_OLD_ISSUE_TYPES}")

    op.drop_index("ix_warehouse_receipts_production_plan_id", table_name="warehouse_receipts")
    op.drop_column("warehouse_receipts", "production_plan_id")

    op.drop_index("ix_warehouse_issues_production_plan_id", table_name="warehouse_issues")
    op.drop_column("warehouse_issues", "production_plan_id")

    op.drop_column("production_plans", "material_cost_issued")
