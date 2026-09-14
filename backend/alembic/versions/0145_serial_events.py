"""سریال یک بن‌بست بود — دفترِ رویدادش ساخته می‌شود.

Revision ID: 0145
Revises: 0144

**پروب.** کالای سریالی خریده شد (۳ عدد)، سریال‌ها دستی ثبت شدند، بعد ۲ عدد
فروخته شد:

    SN-1  status=ok  batch=…
    SN-2  status=ok  batch=…
    SN-3  status=ok  batch=…

**هیچ سریالی لمس نشد.** فاکتور فروش سریالی نخواست و مصرفی ثبت نکرد. و ستون‌های
`stock_batch_serials` فقط این‌ها بودند: `batch_id`, `serial`, `status`, `notes`
— هیچ ستونی برای سند. سریال به بچ وصل است و بچ فقط به سندِ **ورود**.

پس پرسشِ «SN-1 کجاست؟» یا «به چه کسی فروخته شد؟» جوابی نداشت، و جوابِ سیستم تا
ابد «در بچِ P1-1» می‌ماند — حتی پس از فروش.

و `Item.is_serial_tracked` **جز در گاردِ تغییرِ خودش هیچ‌جا خوانده نمی‌شد**؛
پرچمی بود که چیزی را روشن نمی‌کرد.

## `serial_events` — دفتر، نه موقعیت

    serial_events(serial_id, event_type, source_type, source_id, entry_date, …)

**چرا دفترِ رویداد و نه یک ستونِ `current_warehouse_id`.** موقعیتِ فعلی با هر
حرکت بازنویسی می‌شود و تاریخچه را می‌بلعد؛ همان اشتباهی که کوبیتا در موجودی
نکرده (مانده از دفتر مشتق می‌شود) و این‌جا هم نباید بکند. موقعیتِ فعلی از
**آخرین رویداد** مشتق می‌شود.

## backfill

برای هر سریالِ موجود یک رویدادِ `receipt` ساخته می‌شود، با سندِ مبدأِ **خودِ
بچ** (`stock_batches.source_type` / `source_id`) و تاریخِ دریافتش. پس آنچه امروز
می‌دانیم از دست نمی‌رود؛ فقط از این پس ادامه پیدا می‌کند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0145"
down_revision: Union[str, None] = "0144"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "serial_events"
EVENT_TYPES = ("receipt", "issue", "return_in", "return_out", "adjust")


def _enable_rls(table: str) -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name(table)} ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
    )


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "serial_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stock_batch_serials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False, server_default=""),
        sa.Column("source_id", UUID(as_uuid=True), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "event_type IN " + str(EVENT_TYPES), name="ck_serial_events_type"
        ),
    )
    op.create_index("ix_serial_events_tenant_id", TABLE, ["tenant_id"])
    op.create_index("ix_serial_events_serial_id", TABLE, ["serial_id"])
    #: پرسشِ طبیعیِ جست‌وجوی سریال وارونه است: «کدام سریال‌ها روی این سند بودند؟»
    op.create_index("ix_serial_events_source", TABLE, ["tenant_id", "source_type", "source_id"])
    _enable_rls(TABLE)

    #: **یک سریال روی یک سند بیش از یک بار رویداد نمی‌گیرد.** بی این، تلاشِ
    #: دوباره‌ی شبکه دو رویدادِ اقتصادی می‌ساخت و «کجاست؟» دو جواب پیدا می‌کرد.
    #: `tenant_id` در ایندکس هست وگرنه سندِ یک مستأجر ردیفِ مستأجرِ دیگر را
    #: مسدود می‌کرد — و `test_migration_drift` هم همین را می‌گیرد.
    op.create_index(
        "uq_serial_events_serial_source",
        TABLE,
        ["tenant_id", "serial_id", "source_type", "source_id"],
        unique=True,
        postgresql_where=sa.text("source_id IS NOT NULL"),
    )

    #: backfill — آنچه امروز می‌دانیم از دست نمی‌رود: هر سریالِ موجود یک رویدادِ
    #: ورود می‌گیرد با سندِ مبدأِ بچِ خودش.
    conn = op.get_bind()
    with rls_disabled(conn, (TABLE, "stock_batch_serials", "stock_batches")):
        conn.execute(
            sa.text(
                f"INSERT INTO {TABLE} "
                "(id, tenant_id, serial_id, event_type, source_type, source_id, entry_date, notes) "
                "SELECT gen_random_uuid(), s.tenant_id, s.id, 'receipt', "
                "       COALESCE(b.source_type, ''), b.source_id, "
                "       COALESCE(b.received_date, CURRENT_DATE), '' "
                "FROM stock_batch_serials s JOIN stock_batches b ON b.id = s.batch_id"
            )
        )


def downgrade() -> None:
    """کلِ تاریخچه‌ی سریال می‌رود.

    رویدادِ ورودِ backfill‌شده بازساختنی است (از بچ)، ولی رویدادهای خروج و برگشت
    **جای دیگری ذخیره نشده‌اند** و برنمی‌گردند. این پُرافت‌ترین `downgrade`ِ این
    مخزن است و عمداً صریح نوشته شده.
    """
    op.drop_table(TABLE)
