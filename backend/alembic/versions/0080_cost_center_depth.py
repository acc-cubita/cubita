"""مرکز هزینه: درخت، نوع، سرپرست، بازه — و بودجه‌ی مرکزمحور

Revision ID: 0080
Revises: 0079

مرکزِ هزینه تا امروز یک برچسبِ تخت بود: کد و نام و یک تیکِ فعال. سه چیز کم داشت که
بدونشان «سنجشِ سود به تفکیک» در عمل جواب نمی‌دهد:

* **درخت** — «شعبه‌ی تهران» جمعِ پروژه‌هایش است. بدونِ `parent_id` یا باید مرکزِ
  مادر را دستی جمع بزنی یا اسناد را دوبار برچسب بزنی؛ هر دو غلط از آب درمی‌آید.
  `RESTRICT` است نه `CASCADE`: حذفِ شعبه نباید بی‌صدا پروژه‌هایش را ببرد.
* **نوع** — پروژه و شعبه و دپارتمان سه بُعدِ متفاوتند و در یک فهرستِ درهم گم می‌شوند.
* **بازه و سرپرست** — پروژه شروع و پایان و صاحب دارد؛ اینها امروز در «توضیحات»
  می‌نشینند و هیچ گزارشی نمی‌تواند رویشان تکیه کند.

و ستونِ `budget_lines.cost_center_id`: بودجه از قبل وجود داشت ولی فقط سراسری بود.
به‌جای ساختِ جدولِ دومِ «بودجه‌ی مرکز» — که یعنی دو منبعِ حقیقت برای یک مفهوم —
همان ردیفِ بودجه یک بُعدِ اختیاریِ مرکز می‌گیرد. `NULL` یعنی بودجه‌ی کلِ کسب‌وکار،
دقیقاً همان معنایی که ردیف‌های امروز دارند، پس هیچ داده‌ای مهاجرت نمی‌خواهد.

قیدِ یکتای قبلی (مستأجر، حساب، دوره) با دو ایندکسِ *جزئی* جایگزین می‌شود، چون در
پستگرس `NULL` با `NULL` برابر نیست و یک قیدِ ساده روی ستونِ nullable جلوی ردیفِ
تکراریِ سراسری را نمی‌گرفت.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0080"
down_revision: Union[str, None] = "0079"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

KINDS = "('project', 'branch', 'department', 'product', 'contract', 'other')"


def upgrade() -> None:
    op.add_column(
        "cost_centers",
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cost_centers.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column("cost_centers", sa.Column("kind", sa.String(20), nullable=False, server_default="project"))
    op.add_column("cost_centers", sa.Column("manager", sa.String(200), nullable=False, server_default=""))
    op.add_column("cost_centers", sa.Column("start_date", sa.Date, nullable=True))
    op.add_column("cost_centers", sa.Column("end_date", sa.Date, nullable=True))
    op.create_check_constraint("ck_cost_centers_kind", "cost_centers", f"kind IN {KINDS}")
    op.create_index("ix_cost_centers_tenant_parent", "cost_centers", ["tenant_id", "parent_id"])

    op.add_column(
        "budget_lines",
        sa.Column(
            "cost_center_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cost_centers.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.drop_constraint("uq_budget_account_period", "budget_lines", type_="unique")
    # دو ایندکسِ جزئی به‌جای یک قیدِ یکتا: یکی برای بودجه‌ی سراسری (مرکز NULL) و یکی
    # برای بودجه‌ی هر مرکز. بدونِ شکستنِ قید به دو تکه، ردیف‌های سراسریِ تکراری
    # می‌توانستند کنار هم بنشینند و در گزارش دوبار جمع شوند.
    op.execute(
        "CREATE UNIQUE INDEX uq_budget_account_period_global ON budget_lines "
        "(tenant_id, account_id, period_date) WHERE cost_center_id IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_budget_account_period_center ON budget_lines "
        "(tenant_id, account_id, period_date, cost_center_id) WHERE cost_center_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_budget_account_period_center")
    op.execute("DROP INDEX IF EXISTS uq_budget_account_period_global")
    op.drop_column("budget_lines", "cost_center_id")
    op.create_unique_constraint(
        "uq_budget_account_period", "budget_lines", ["tenant_id", "account_id", "period_date"]
    )
    op.drop_index("ix_cost_centers_tenant_parent", table_name="cost_centers")
    op.drop_constraint("ck_cost_centers_kind", "cost_centers", type_="check")
    op.drop_column("cost_centers", "end_date")
    op.drop_column("cost_centers", "start_date")
    op.drop_column("cost_centers", "manager")
    op.drop_column("cost_centers", "kind")
    op.drop_column("cost_centers", "parent_id")
