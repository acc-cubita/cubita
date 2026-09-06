"""چند تلفن/نشانی برای طرف حساب، و مانده‌ی اول دوره‌اش

Revision ID: 0091
Revises: 0090

دو چیزی که فرمِ «تعریف طرف حساب» داشت و ما نداشتیم.

## چند تلفن و نشانی — `contact_channels`

تب‌های «تلفن» و «نشانی» در سپیدار فهرست‌اند، نه یک فیلد. یک جدول برای هر دو، با
`kind`، چون ساختارشان یکی است (برچسب + مقدار + یکی که اصلی است) و دو جدولِ همسان
فقط دو مسیرِ نگهداری می‌سازد.

**`contacts.phone` و `contacts.address` سرِ جایشان می‌مانند و «اصلی» هستند.** این
عمدی است: ده‌ها جا (فاکتور، صورت‌حساب، پیامک، گزارشِ فصلی) مستقیم آن‌ها را
می‌خوانند و تبدیلشان به کوئریِ جدولِ فرزند یعنی تغییر در همه‌ی آن‌ها. پس این جدول
فقط شماره‌ها و نشانی‌های **اضافه** را نگه می‌دارد — نه کپیِ اصلی. دو نمای یک داده
ساخته نمی‌شود چون هیچ ردیفی این‌جا همان مقدارِ روی طرف‌حساب نیست.

## مانده‌ی اول دوره

روی خودِ طرف‌حساب می‌نشیند، دقیقاً مثلِ «موجودیِ اول دوره»ی کالا که روی `items`
می‌نشیند و `create_opening_entry` از آن هم حرکتِ انبار می‌سازد هم ردیفِ سند. همان
الگو: عدد این‌جاست، و سندِ افتتاحیه از رویش ساخته می‌شود.

دو مبلغِ جدا (به‌عنوانِ مشتری و به‌عنوانِ تأمین‌کننده) چون در کوبیتا حسابِ دریافتنی و
پرداختنی دو حسابِ متفاوت‌اند و یک طرف‌حساب می‌تواند هم‌زمان هر دو باشد. سمت
(`_side`) جداست چون مانده‌ی خلافِ انتظار واقعاً پیش می‌آید — پیش‌دریافت از مشتری،
پیش‌پرداخت به تأمین‌کننده.

**پس از ثبتِ سندِ افتتاحیه قفل می‌شوند.** بدونِ این قفل، عددِ روی طرف‌حساب و ردیفِ
سند از هم جدا می‌افتادند و گزارش دو حقیقتِ متفاوت می‌گفت.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0091"
down_revision: Union[str, None] = "0090"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    op.create_table(
        "contact_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "contact_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("kind", sa.String(length=10), nullable=False),
        #: برچسبِ آزادِ کاربر: «دفتر مرکزی»، «انبار»، «همراهِ مدیر».
        sa.Column("label", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.CheckConstraint("kind IN ('phone', 'address', 'email')", name="ck_contact_channels_kind"),
    )
    op.create_index(
        "ix_contact_channels_tenant_contact", "contact_channels", ["tenant_id", "contact_id"]
    )

    # جدولِ تازه‌ی مستأجرمحور باید همان‌جا سیاستِ RLS بگیرد، وگرنه داده‌ی یک
    # کسب‌وکار برای بقیه دیده می‌شود. `FORCE` لازم است چون مالکِ جدول هم مستثنا
    # نیست. تستِ introspection نبودنِ `tenant_id` را می‌گیرد ولی نبودِ سیاست را نه.
    conn.execute(sa.text("ALTER TABLE contact_channels ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE contact_channels FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name('contact_channels')} ON contact_channels"))
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name('contact_channels')} ON contact_channels "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
    )

    for column in (
        sa.Column("opening_ar_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("opening_ar_side", sa.String(length=6), nullable=False, server_default="debit"),
        sa.Column("opening_ap_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("opening_ap_side", sa.String(length=6), nullable=False, server_default="credit"),
    ):
        op.add_column("contacts", column)

    op.create_check_constraint(
        "ck_contacts_opening", "contacts",
        "opening_ar_amount >= 0 AND opening_ap_amount >= 0 "
        "AND opening_ar_side IN ('debit', 'credit') "
        "AND opening_ap_side IN ('debit', 'credit')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_contacts_opening", "contacts", type_="check")
    for name in ("opening_ap_side", "opening_ap_amount", "opening_ar_side", "opening_ar_amount"):
        op.drop_column("contacts", name)
    op.drop_index("ix_contact_channels_tenant_contact", table_name="contact_channels")
    op.drop_table("contact_channels")
