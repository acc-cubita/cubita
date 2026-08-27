"""موجودیت‌های «شرکت»: گروهِ طرف‌حساب، محلِ جغرافیایی، فردِ مرتبط

Revision ID: 0078
Revises: 0077

سه جدولِ مستأجرمحور با RLS، به‌علاوه‌ی دو ستونِ *اختیاریِ* ارجاع روی `contacts`.

بدونِ بک‌فیل و بدونِ NOT NULL: طرف‌حساب‌های موجود بی‌گروه و بی‌محل می‌مانند و هیچ
فرم یا گزارشی با ارتقا نمی‌شکند. دسته‌بندی از لحظه‌ای معنا پیدا می‌کند که خودِ کاربر
اولین گروه/محل را بسازد.

`geo_locations.parent_id` عمداً `RESTRICT` است نه `CASCADE`: حذفِ «تهران» نباید
بی‌صدا همه‌ی مناطقش را ببرد. در مقابل `related_persons.contact_id` همان‌قدر عمداً
`CASCADE` است — فردِ مرتبط بدونِ طرف‌حسابش معنایی ندارد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0078"
down_revision: Union[str, None] = "0077"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("contact_groups", "geo_locations", "related_persons")


def _tenant_cols() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def _enable_rls(conn, table: str) -> None:
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    # FORCE اجباری است: بدونِ آن مالکِ جدول از سیاست رد می‌شود و اپ همان مالک است.
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
        "contact_groups",
        *_tenant_cols(),
        sa.Column("code", sa.String(30), nullable=False, server_default=""),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
    )

    op.create_table(
        "geo_locations",
        *_tenant_cols(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, server_default="city"),
        sa.Column("code", sa.String(30), nullable=False, server_default=""),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("geo_locations.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('country', 'province', 'city', 'district')", name="ck_geo_locations_kind"
        ),
    )
    op.create_index("ix_geo_locations_tenant_parent", "geo_locations", ["tenant_id", "parent_id"])

    op.create_table(
        "related_persons",
        *_tenant_cols(),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(120), nullable=False, server_default=""),
        sa.Column("phone", sa.String(30), nullable=False, server_default=""),
        sa.Column("email", sa.String(150), nullable=False, server_default=""),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
    )
    op.create_index("ix_related_persons_tenant_contact", "related_persons", ["tenant_id", "contact_id"])

    # ارجاع‌های اختیاری روی طرف‌حساب — بدونِ بک‌فیل، پس هیچ ردیفی نامعتبر نمی‌شود.
    op.add_column(
        "contacts",
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contact_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "contacts",
        sa.Column(
            "geo_location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("geo_locations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    conn = op.get_bind()
    for table in TABLES:
        _enable_rls(conn, table)


def downgrade() -> None:
    op.drop_column("contacts", "geo_location_id")
    op.drop_column("contacts", "group_id")
    op.drop_index("ix_related_persons_tenant_contact", table_name="related_persons")
    op.drop_table("related_persons")
    op.drop_index("ix_geo_locations_tenant_parent", table_name="geo_locations")
    op.drop_table("geo_locations")
    op.drop_table("contact_groups")
