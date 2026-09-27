"""دبیرخانه و ارجاع: نامه و فایل زیر RLS، سابقه فقط‌افزودنی.

محتوای فایل در پایگاه‌داده است تا پشتیبان/بازیابی فعلی آن را از قلم نیندازد.
شمارنده‌های تازه روی مستأجرهای موجود افزوده می‌شوند؛ دادهٔ مالی عوض نمی‌شود.
برگشت این مهاجرت همهٔ مکاتبات و پیوست‌های این ماژول را حذف می‌کند.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.audit import append_only_statements
from app.migration_utils import rls_disabled
from app.tenancy import rls_statements

revision = "0187"
down_revision = "0186"
branch_labels = None
depends_on = None

TABLES = ("office_letters", "office_referrals", "office_attachments", "office_events")


def common(*, updated=True):
    columns = [sa.Column("id", UUID(as_uuid=True), primary_key=True),
               sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
               sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]
    if updated:
        columns.append(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    return columns


def user(name, **kwargs):
    return sa.Column(name, UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, **kwargs)


def parent():
    return sa.Column("letter_id", UUID(as_uuid=True), sa.ForeignKey("office_letters.id"), nullable=False, index=True)


def upgrade():
    op.create_table("office_letters", *common(),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("number", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sender", sa.String(200), nullable=False),
        sa.Column("addressee", sa.String(200), nullable=False),
        sa.Column("external_number", sa.String(100), nullable=False),
        sa.Column("external_date", sa.Date(), nullable=True),
        sa.Column("letter_date", sa.Date(), nullable=False, index=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("priority", sa.String(16), nullable=False),
        user("created_by_id", index=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tenant_id", "kind", "number", name="uq_office_letter_number"),
        sa.CheckConstraint("kind IN ('incoming','outgoing','internal')", name="ck_office_letter_kind"),
        sa.CheckConstraint("status IN ('draft','registered','archived')", name="ck_office_letter_status"),
        sa.CheckConstraint("priority IN ('normal','urgent')", name="ck_office_letter_priority"),
    )
    op.create_table("office_referrals", *common(), parent(), user("from_user_id"), user("to_user_id", index=True),
        sa.Column("instruction", sa.Text(), nullable=False), sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True), sa.Column("response", sa.Text(), nullable=False))
    op.create_table("office_attachments", *common(), parent(),
        sa.Column("filename", sa.String(200), nullable=False), sa.Column("content_type", sa.String(60), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False), sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False), user("uploaded_by_id"))
    op.create_table("office_events", *common(updated=False), parent(), user("actor_id"),
        sa.Column("action", sa.String(40), nullable=False), sa.Column("description", sa.Text(), nullable=False))
    for statement in rls_statements(TABLES) + append_only_statements("office_events"):
        op.execute(sa.text(statement))
    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        for kind in ("incoming", "outgoing", "internal"):
            conn.execute(sa.text("""INSERT INTO document_counters
                (id, tenant_id, doc_type, last_number, created_at, updated_at)
                SELECT gen_random_uuid(), id, :type, 0, now(), now() FROM tenants
                ON CONFLICT (tenant_id, doc_type) DO NOTHING"""), {"type": f"office_{kind}"})


def downgrade():
    with rls_disabled(op.get_bind(), ["document_counters"]):
        op.execute("DELETE FROM document_counters WHERE doc_type IN ('office_incoming','office_outgoing','office_internal')")
    for table in reversed(TABLES):
        op.drop_table(table)
