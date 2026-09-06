"""نشانی‌های چندگانه‌ی طرف حساب، نقشِ سهامدار، و مشخصاتِ شخصی

Revision ID: 0092
Revises: 0091

## چرا `contact_addresses` جدا از `contact_channels`

در ۰۰۹۱ یک جدول برای تلفن و نشانی ساخته شد، به این گمان که شکلشان یکی است. فرمِ
واقعیِ سپیدار نشان داد که نیست: تلفن سه فیلد دارد (نوع، شماره، اصلی) و نشانی شانزده
— شهر، کد پستی، عرض و طولِ جغرافیایی، کد و عنوانِ مسیر، کد و عنوانِ منطقه، کد شعبه.
ریختنِ هر دو در یک جدول یعنی سیزده ستونِ همیشه‌خالی برای هر شماره‌ی تلفن.

پس `contact_channels` می‌ماند برای **تلفن و ایمیل**، و نشانی جدولِ خودش را می‌گیرد.

## کد مسیر = زون

`route_code` همان «زون»ِ مشتری است که قرار بود بشود تعریفش کرد. فعلاً فیلدِ متنی است
چون هنوز موجودیتِ «زون» نداریم؛ **وقتی ساخته شد، این باید کلیدِ خارجی شود**، نه اینکه
یک فهرستِ متنیِ موازی کنارش بماند.

## شهر: کلیدِ خارجی، نه متن

سپیدار «شهر» را متن می‌گیرد، ولی کوبیتا از قبل درختِ `geo_locations` را دارد. متن‌گرفتن
یعنی «تهران» و «تهران » و «طهران» سه شهرِ متفاوت شوند و هیچ گزارشِ منطقه‌ای درست درنیاید.

## مشخصاتِ شخصی روی طرف‌حساب، نه روی کارمند

جنسیت، وضعیت تأهل، تعداد فرزند و تحصیلات واقعیت‌های **شخص**اند نه شغلش؛ چه کارمند
باشد چه مشتری درست‌اند. اگر روی `employees` می‌نشستند، مشتریِ غیرکارمند هیچ‌وقت
نمی‌توانست داشته باشدشان. واقعیت‌های *استخدام* (حکم، تاریخ استخدام، شماره حساب) سرِ
جایشان در ماژولِ حقوق و دستمزد می‌مانند و `contacts.employee_id` پلِ این دو است.

## سهامدار

نقشِ چهارم، کنارِ مشتری/تأمین‌کننده/واسطه. مثلِ `is_broker` پرچمِ مستقل است نه مقدارِ
تازه‌ی `type`، به همان دلیل: ده‌ها فیلتر و گزارش روی (customer, supplier, both) تکیه دارند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0092"
down_revision: Union[str, None] = "0091"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── نشانی‌های چندگانه ─────────────────────────────────────────────────────
    op.create_table(
        "contact_addresses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "contact_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False,
        ),
        #: رسمی | محل فعالیت | ارسال صورتحساب | ارسال کالا | انبار | منزل | پستی
        sa.Column("address_type", sa.String(length=20), nullable=False, server_default="official"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "geo_location_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("geo_locations.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("title", sa.String(length=150), nullable=False, server_default=""),
        sa.Column("address", sa.Text(), nullable=False, server_default=""),
        sa.Column("address2", sa.Text(), nullable=False, server_default=""),
        sa.Column("postal_code", sa.String(length=20), nullable=False, server_default=""),
        #: مختصات — برای مسیریابیِ مأمورِ ارسال. NULL = ثبت‌نشده.
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        #: «زون»ِ توزیع. وقتی موجودیتِ زون ساخته شد، این باید کلیدِ خارجی شود.
        sa.Column("route_code", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("route_title", sa.String(length=150), nullable=False, server_default=""),
        sa.Column("route_title2", sa.String(length=150), nullable=False, server_default=""),
        sa.Column("region_code", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("region_title", sa.String(length=150), nullable=False, server_default=""),
        sa.Column("region_title2", sa.String(length=150), nullable=False, server_default=""),
        sa.Column("branch_code", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "address_type IN ('official', 'business', 'billing', 'shipping', 'warehouse', 'home', 'postal')",
            name="ck_contact_addresses_type",
        ),
    )
    op.create_index(
        "ix_contact_addresses_tenant_contact", "contact_addresses", ["tenant_id", "contact_id"]
    )
    conn.execute(sa.text("ALTER TABLE contact_addresses ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE contact_addresses FORCE ROW LEVEL SECURITY"))
    conn.execute(
        sa.text(f"DROP POLICY IF EXISTS {policy_name('contact_addresses')} ON contact_addresses")
    )
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name('contact_addresses')} ON contact_addresses "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
    )

    # ── تلفن: نوع و «اصلی» ────────────────────────────────────────────────────
    op.add_column(
        "contact_channels",
        sa.Column("channel_type", sa.String(length=20), nullable=False, server_default="other"),
    )
    op.add_column(
        "contact_channels",
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # ── افرادِ مرتبط: عنوانِ دوم ───────────────────────────────────────────────
    for column in ("name2", "role2"):
        op.add_column(
            "related_persons",
            sa.Column(column, sa.String(length=200), nullable=False, server_default=""),
        )

    # ── مشخصاتِ شخصی و نقشِ چهارم ─────────────────────────────────────────────
    for column in (
        sa.Column("gender", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("marital_status", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("marital_status_date", sa.Date(), nullable=True),
        sa.Column("children_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dependents_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("education_level", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("education_field", sa.String(length=150), nullable=False, server_default=""),
        sa.Column("is_employee", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_shareholder", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("share_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
    ):
        op.add_column("contacts", column)

    op.create_check_constraint(
        "ck_contacts_person", "contacts",
        "children_count >= 0 AND dependents_count >= 0 "
        "AND share_percent >= 0 AND share_percent <= 100 "
        "AND gender IN ('', 'male', 'female') "
        "AND marital_status IN ('', 'single', 'married', 'divorced', 'widowed')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_contacts_person", "contacts", type_="check")
    for column in (
        "share_percent", "is_shareholder", "is_employee", "education_field", "education_level",
        "dependents_count", "children_count", "marital_status_date", "marital_status", "gender",
    ):
        op.drop_column("contacts", column)
    for column in ("role2", "name2"):
        op.drop_column("related_persons", column)
    op.drop_column("contact_channels", "is_primary")
    op.drop_column("contact_channels", "channel_type")
    op.drop_index("ix_contact_addresses_tenant_contact", table_name="contact_addresses")
    op.drop_table("contact_addresses")
