"""ردیابیِ بارِ ورودی: پرچمِ کالا، وضعیتِ بار، و موقعیتِ داخلِ انبار

Revision ID: 0172
Revises: 0171

## چه چیزی اضافه می‌شود

**جدولِ تازه `warehouse_locations`** — قفسه/راهرو/طبقه‌ی داخلِ یک انبار
(«A-02-04»). تا امروز کوبیتا هیچ مفهومی از محلِ قرارگیری نداشت: انبار بود و
تمام. جمع‌آوری بدونِ محل یعنی انباردار باید حفظ باشد کجا گذاشته.

**روی `items` دو ستون:**

* `is_batch_tracked` — پیش‌فرض `false`، یعنی **همه‌ی کالاهای موجود دقیقاً مثلِ
  دیروز کار می‌کنند**.
* `minimum_sellable_shelf_life_days` — حداقلِ عمرِ مفیدِ لازم برای فروش (§۲۹).

**روی `stock_batches` وضعیت — سه ستونِ عمود بر هم، نه یک `status`:**

فصل ۱۲ وضعیت خواسته بود (`draft`، `qc_pending`، `near_expiry`، `depleted`، …)
ولی خودش هم گفته «نباید فقط به status تکیه شود». دلیلش همین است: آن ۱۲ تا سه
واقعیتِ **مستقل** را در یک ستون فشرده می‌کنند و فشرده‌سازی داده از دست می‌دهد —
باری می‌تواند هم‌زمان در انتظارِ QC **و** فراخوان‌شده باشد.

| ستون | مقادیر | پیش‌فرض |
|---|---|---|
| `qc_status` | `passed` `pending` `failed` | `passed` |
| `hold_status` | `none` `blocked` `recalled` | `none` |
| `is_closed` | بولی | `false` |

پیش‌فرضِ `qc_status = passed` عمدی است: هر بارِ موجود امروز قابلِ استفاده است، و
کسب‌وکاری که فرایندِ QC ندارد هرگز این فیلد را نمی‌بیند. اگر `pending` می‌گذاشتیم،
یک مهاجرت کلِ موجودیِ همه را غیرقابلِ فروش می‌کرد.

`draft`/`received` و `partially_reserved`/`near_expiry`/`expired`/`depleted`
**ذخیره نمی‌شوند** — از عدد و تاریخ مشتق‌اند و API هر ۱۲ تا را برمی‌گرداند.
ستونی که بتواند با واقعیت اختلاف پیدا کند، بالاخره پیدا می‌کند.

**و چند ستونِ شناسنامه‌ای:** `supplier_batch_code` (شماره‌ی بارِ تأمین‌کننده،
که با شماره‌ی داخلیِ ما یکی نیست)، `supplier_id`، `location_id`، و
`parent_batch_id` برای بارِ آینه‌ی انتقال.

## چرا `parent_batch_id`

`stock_batches` به `(کالا، انبار)` بسته است. انتقالِ بینِ انبار بی این ستون بار
را **گم می‌کند**: از مبدأ کم می‌شود و در مقصد بی‌بچ ظاهر می‌شود. در ۳۶ بندِ
درخواست اصلاً حرفی از انتقال نبود، ولی اولین چیزی است که در تولید می‌شکند. بارِ
مقصد کپیِ بارِ مبدأ است و `parent_batch_id` می‌گوید از کجا آمده.

## چرا `rls_disabled` این‌جا لازم است

`stock_batches` ردیف دارد و سه ستونِ تازه‌اش کلیدِ خارجیِ درون‌خطی دارند
(`contacts`، `warehouse_locations`، خودِ `stock_batches`). اسکنِ اعتبارسنجیِ
Postgres مشمولِ سیاستِ RLS است و روی PG14 — همان که تولید دارد — می‌ترکد.
شرحِ کامل در `app/migration_utils.py`. ستون‌های `items` کلیدِ خارجی ندارند، پس
از این گارد بیرون‌اند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0172"
down_revision: Union[str, None] = "0171"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

QC_STATUSES = ("passed", "pending", "failed")
HOLD_STATUSES = ("none", "blocked", "recalled")


def _enable_rls(table: str) -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
    conn.execute(sa.text(
        f"CREATE POLICY {policy_name(table)} ON {table} "
        "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
    ))


def upgrade() -> None:
    conn = op.get_bind()

    op.create_table(
        "warehouse_locations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "warehouse_id",
            UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), server_default="", nullable=False),
        sa.Column("aisle", sa.String(20), server_default="", nullable=False),
        sa.Column("rack", sa.String(20), server_default="", nullable=False),
        sa.Column("level", sa.String(20), server_default="", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        #: کد در **همان انبار** یکتاست، نه در کلِ کسب‌وکار: «A-01» می‌تواند در دو
        #: انبار وجود داشته باشد و همین هم طبیعی است.
        sa.UniqueConstraint("tenant_id", "warehouse_id", "code", name="uq_warehouse_locations_code"),
    )
    _enable_rls("warehouse_locations")

    #: بی کلیدِ خارجی، پس بیرونِ گاردِ RLS.
    op.add_column(
        "items",
        sa.Column("is_batch_tracked", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "items",
        sa.Column("minimum_sellable_shelf_life_days", sa.Integer(), nullable=True),
    )

    with rls_disabled(conn, ["stock_batches", "contacts", "warehouse_locations"]):
        op.add_column(
            "stock_batches",
            sa.Column("qc_status", sa.String(20), server_default="passed", nullable=False),
        )
        op.add_column(
            "stock_batches",
            sa.Column("hold_status", sa.String(20), server_default="none", nullable=False),
        )
        op.add_column("stock_batches", sa.Column("hold_reason", sa.Text(), server_default="", nullable=False))
        op.add_column("stock_batches", sa.Column("held_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(
            "stock_batches",
            sa.Column("held_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
        op.add_column(
            "stock_batches",
            sa.Column("is_closed", sa.Boolean(), server_default="false", nullable=False),
        )
        op.add_column("stock_batches", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(
            "stock_batches",
            sa.Column("supplier_batch_code", sa.String(80), server_default="", nullable=False),
        )
        op.add_column(
            "stock_batches",
            sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True),
        )
        op.add_column(
            "stock_batches",
            sa.Column(
                "location_id",
                UUID(as_uuid=True),
                sa.ForeignKey("warehouse_locations.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.add_column(
            "stock_batches",
            sa.Column("parent_batch_id", UUID(as_uuid=True), sa.ForeignKey("stock_batches.id"), nullable=True),
        )

    op.create_check_constraint("ck_stock_batches_qc_status", "stock_batches", f"qc_status IN {QC_STATUSES}")
    op.create_check_constraint("ck_stock_batches_hold_status", "stock_batches", f"hold_status IN {HOLD_STATUSES}")
    #: FEFO همیشه «بارهای قابلِ فروشِ این کالا در این انبار، به ترتیبِ انقضا» را
    #: می‌خواهد — همین ایندکس دقیقاً همان است.
    op.create_index(
        "ix_stock_batches_fefo",
        "stock_batches",
        ["tenant_id", "item_id", "warehouse_id", "expiry_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_stock_batches_fefo", table_name="stock_batches")
    op.drop_constraint("ck_stock_batches_hold_status", "stock_batches", type_="check")
    op.drop_constraint("ck_stock_batches_qc_status", "stock_batches", type_="check")
    for column in (
        "parent_batch_id",
        "location_id",
        "supplier_id",
        "supplier_batch_code",
        "closed_at",
        "is_closed",
        "held_by_id",
        "held_at",
        "hold_reason",
        "hold_status",
        "qc_status",
    ):
        op.drop_column("stock_batches", column)
    op.drop_column("items", "minimum_sellable_shelf_life_days")
    op.drop_column("items", "is_batch_tracked")
    op.drop_table("warehouse_locations")
