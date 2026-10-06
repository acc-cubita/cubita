"""Freeze phase-one DDL, rather than importing mutable ORM models from a migration."""
from pathlib import Path
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.dialects import postgresql
from app.database import Base
import app.models  # noqa: F401

tables = [t for t in Base.metadata.sorted_tables if t.name.startswith("repair_")]
ddl = []
for t in tables:
    ddl.append(str(CreateTable(t).compile(dialect=postgresql.dialect())))
    ddl.extend(str(CreateIndex(i).compile(dialect=postgresql.dialect())) for i in sorted(t.indexes, key=lambda i: i.name))
source = '''"""پذیرش دستگاه امانی؛ هیچ حرکت انبار یا سند مالی ایجاد نمی‌کند.

DDL ثابت است. فقط شمارندهٔ پذیرش برای مستأجرهای موجود تکمیل می‌شود؛
دادهٔ مشتری و کالا دست‌نخورده می‌ماند. downgrade دادهٔ تعمیرگاه را حذف می‌کند.
"""
from alembic import op
import sqlalchemy as sa
from app.migration_utils import rls_disabled
from app.tenancy import rls_statements

revision = "0190"
down_revision = "0189"
branch_labels = None
depends_on = None
'''
source += '\nTABLES = ' + repr(tuple(t.name for t in tables)) + '\nDDL = ' + repr(tuple(ddl)) + '\n'
source += '''

def upgrade():
    op.create_unique_constraint("uq_contacts_tenant_id", "contacts", ["tenant_id", "id"])
    for statement in DDL:
        op.execute(statement)
    for statement in rls_statements(TABLES):
        op.execute(statement)
    conn = op.get_bind()
    with rls_disabled(conn, ("document_counters",)):
        conn.execute(sa.text("INSERT INTO document_counters (id,tenant_id,doc_type,last_number) SELECT gen_random_uuid(),id,'repair_admission',0 FROM tenants ON CONFLICT (tenant_id,doc_type) DO NOTHING"))


def downgrade():
    for table in reversed(TABLES):
        op.drop_table(table)
    op.drop_constraint("uq_contacts_tenant_id", "contacts", type_="unique")
    with rls_disabled(op.get_bind(), ("document_counters",)):
        op.execute("DELETE FROM document_counters WHERE doc_type='repair_admission'")
'''
Path('alembic/versions/0190_repair_admission.py').write_text(source, encoding='utf-8')
