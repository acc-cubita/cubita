"""Freeze the additive stage-one identity schema; never import models in migration."""
from pathlib import Path
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects.postgresql import dialect
from app.database import Base
import app.models  # noqa: F401

names = ('repair_device_identity_events', 'repair_intake_evidence', 'repair_confirmations', 'repair_warranty_transfers', 'repair_technical_summaries', 'repair_representative_authorizations')
ddl = []
for name in names:
    table = Base.metadata.tables[name]
    ddl.append(str(CreateTable(table).compile(dialect=dialect())))
    ddl += [str(CreateIndex(index).compile(dialect=dialect())) for index in sorted(table.indexes, key=lambda i: i.name)]
source = '''"""هویت پایدار و سابقهٔ مالکیت؛ بدون حدس‌زدن مالک دستگاه‌های قدیمی."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from app.tenancy import rls_statements
from app.audit import append_only_statements

revision = '0193'
down_revision = '0192'
branch_labels = None
depends_on = None
'''
source += '\nDDL = ' + repr(tuple(ddl)) + '\n'
source += '\nTABLES = ' + repr(names) + '\n'
source += '''

def upgrade():
    op.add_column('repair_devices', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('repair_devices', sa.Column('hardware_revision', sa.String(120), nullable=False, server_default=''))
    op.add_column('repair_devices', sa.Column('industry_identifiers', JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    for name in ('intake_confirmation_policy','delivery_confirmation_policy'):
        op.add_column('repair_branch_settings',sa.Column(name,sa.String(20),nullable=False,server_default='legacy'))
    op.create_unique_constraint('uq_repair_ack_case_id','repair_acknowledgments',['tenant_id','case_id','id'])
    for statement in DDL:
        op.execute(statement)
    for statement in rls_statements(TABLES):
        op.execute(statement)
    for table in TABLES:
        if table != 'repair_confirmations':
            for statement in append_only_statements(table):
                op.execute(statement)


def downgrade():
    for table in reversed(TABLES):
        op.drop_table(table)
    op.drop_constraint('uq_repair_ack_case_id','repair_acknowledgments',type_='unique')
    for name in ('intake_confirmation_policy','delivery_confirmation_policy'):
        op.drop_column('repair_branch_settings',name)
    op.drop_column('repair_devices', 'version')
    op.drop_column('repair_devices', 'industry_identifiers')
    op.drop_column('repair_devices', 'hardware_revision')
'''
Path('alembic/versions/0193_repair_identity.py').write_text(source, encoding='utf-8')
