"""واحدِ سنجش یک رشته‌ی آزاد روی کالا بود

Revision ID: 0118
Revises: 0117

## چه چیزی غلط بود

`Item.unit` یک `String(20)`ِ آزاد بود که کاربر هر بار تایپ می‌کرد. یعنی:

* «کیلوگرم» و «كيلوگرم» (با کاف و یای عربی) دو واحدِ متفاوت بودند؛
* نگاشتِ کدِ واحدِ سامانه‌ی مؤدیان — که روی همان **نوشتار** کلید می‌خورد — برای
  هر املا جدا لازم می‌شد؛
* و هیچ جایی نبود که بگوید «یک کارتن چند عدد است».

فصل صریح است (§۱۹): «Unit نباید Text آزاد داخل کالا باشد.»

## چه ساخته می‌شود

`units_of_measure` — و **واحدهای موجود از خودِ داده ساخته می‌شوند**، نه از یک
فهرستِ از پیش نوشته. هر نوشتاری که امروز روی کالاهای یک کسب‌وکار هست، همان
می‌شود یک واحد. پس هیچ کالایی واحدش عوض نمی‌شود و هیچ نگاشتِ مؤدیانی نمی‌شکند.

کسب‌وکاری که هیچ کالایی ندارد، فهرستِ استانداردِ `seed.py` را می‌گیرد.

## `Item.unit` می‌ماند — و چرا

از این پس **پرتوِ** نامِ واحدِ اصلی است، نه منبعِ حقیقت: سرویس هر بار که واحد
عوض شود هم‌گامش می‌کند. حذفش یعنی لمس‌کردنِ ردیفِ فاکتور، بسته‌ی مؤدیان، بازار،
فروشگاه و گزارش‌ها — بی‌آنکه چیزی درست‌تر شود. `unit_snapshot`ِ ردیفِ فاکتور هم
سرِ جایش می‌ماند؛ آن عمداً عکسِ لحظه‌ی معامله است.

## نسبتِ متغیر ساخته نمی‌شود، فقط شناخته می‌شود

§۲۲ می‌گوید مدل باید تفاوتِ نسبتِ ثابت و متغیر را بشناسد، ولی رفتارِ ورودش در
تراکنش را «تا وقتی workflowهای اختصاصی تثبیتش کنند» نهایی نکن. پس ستون هست و
موتورِ تبدیل نسبتِ متغیر را **رد می‌کند** — نه اینکه عددی از خودش دربیاورد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0118"
down_revision: Union[str, None] = "0117"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "units_of_measure"

#: فهرستِ استاندارد — فقط برای کسب‌وکاری که هیچ کالایی ندارد و پس هیچ نوشتاری
#: هم ندارد که از رویش ساخته شود.
STANDARD_UNITS = (
    "عدد", "متر", "متر مربع", "متر مکعب", "سانتی‌متر", "کیلوگرم", "گرم", "تن",
    "لیتر", "بسته", "کارتن", "جعبه", "جفت", "دست", "رول", "طاقه", "شاخه", "عدل", "ساعت",
)


def upgrade() -> None:
    conn = op.get_bind()

    op.create_table(
        TABLE,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column("name", sa.String(20), nullable=False),
        sa.Column("name2", sa.String(50), server_default="", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_units_of_measure_tenant_name"),
    )

    op.add_column(
        "items",
        sa.Column("primary_unit_id", UUID(as_uuid=True), sa.ForeignKey(f"{TABLE}.id"), nullable=True),
    )
    op.add_column(
        "items",
        sa.Column("secondary_unit_id", UUID(as_uuid=True), sa.ForeignKey(f"{TABLE}.id"), nullable=True),
    )
    op.add_column(
        "items", sa.Column("conversion_factor", sa.Numeric(18, 6), server_default="0", nullable=False)
    )
    op.add_column(
        "items", sa.Column("conversion_mode", sa.String(10), server_default="fixed", nullable=False)
    )
    op.add_column("items", sa.Column("unit_weight", sa.Numeric(18, 6), server_default="0", nullable=False))
    op.add_column("items", sa.Column("unit_volume", sa.Numeric(18, 6), server_default="0", nullable=False))

    #: **RLS بعد از افزودنِ کلیدهای خارجی.** درسِ مهاجرتِ ۰۱۰۹: افزودنِ FK به
    #: جدولی که FORCE RLS دارد اسکنِ اعتبارسنجی راه می‌اندازد و آن اسکن
    #: `app.tenant_id` را می‌خواند — که وسطِ مهاجرت وجود ندارد.
    conn.execute(sa.text(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(TABLE)} ON {TABLE}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name(TABLE)} ON {TABLE} "
            "USING (tenant_id = current_setting('app.tenant_id')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)"
        )
    )

    with rls_disabled(conn, [TABLE, "items"]):
        #: واحدها از **خودِ داده** ساخته می‌شوند: هر نوشتاری که امروز روی کالاهای
        #: یک کسب‌وکار هست یک واحد می‌شود. پس هیچ کالایی واحدش عوض نمی‌شود.
        conn.execute(
            sa.text(
                f"""
                INSERT INTO {TABLE} (id, tenant_id, name, name2, is_active)
                SELECT gen_random_uuid(), i.tenant_id, TRIM(i.unit), '', true
                  FROM items i
                 WHERE COALESCE(TRIM(i.unit), '') <> ''
                 GROUP BY i.tenant_id, TRIM(i.unit)
                """
            )
        )

        #: کسب‌وکاری که هیچ کالایی ندارد فهرستِ استاندارد را می‌گیرد — وگرنه
        #: فرمِ کالای جدیدش هیچ واحدی برای انتخاب ندارد.
        conn.execute(
            sa.text(
                f"""
                INSERT INTO {TABLE} (id, tenant_id, name, name2, is_active)
                SELECT gen_random_uuid(), t.id, u.name, '', true
                  FROM tenants t
                 CROSS JOIN unnest(CAST(:names AS text[])) AS u(name)
                 WHERE NOT EXISTS (
                       SELECT 1 FROM {TABLE} x WHERE x.tenant_id = t.id AND x.name = u.name
                 )
                   AND NOT EXISTS (SELECT 1 FROM items i WHERE i.tenant_id = t.id)
                """
            ),
            {"names": list(STANDARD_UNITS)},
        )

        conn.execute(
            sa.text(
                f"""
                UPDATE items i
                   SET primary_unit_id = u.id
                  FROM {TABLE} u
                 WHERE u.tenant_id = i.tenant_id AND u.name = TRIM(i.unit)
                """
            )
        )


def downgrade() -> None:
    for column in (
        "unit_volume",
        "unit_weight",
        "conversion_mode",
        "conversion_factor",
        "secondary_unit_id",
        "primary_unit_id",
    ):
        op.drop_column("items", column)
    op.drop_table(TABLE)
