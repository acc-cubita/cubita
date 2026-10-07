"""Freeze only additive repair tables absent from the released 0190 migration."""
import ast
from pathlib import Path
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects.postgresql import dialect
from app.database import Base
import app.models  # noqa: F401

previous=ast.parse(Path('alembic/versions/0190_repair_admission.py').read_text(encoding='utf-8'))
names=next(ast.literal_eval(n.value) for n in previous.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TABLES' for t in n.targets))
tables=[t for t in Base.metadata.sorted_tables if t.name.startswith('repair_') and t.name not in names]
ddl=[]
for table in tables:
    ddl.append(str(CreateTable(table).compile(dialect=dialect())))
    ddl.extend(str(CreateIndex(i).compile(dialect=dialect())) for i in sorted(table.indexes,key=lambda i:i.name))
source='''"""تکمیل تعمیرگاه؛ جدول‌های افزایشی، بدون بازنویسی اسناد تاریخی."""
from alembic import op
from app.tenancy import rls_statements

revision = "0191"
down_revision = "0190"
branch_labels = None
depends_on = None
'''
source+='\nTABLES = '+repr(tuple(t.name for t in tables))+'\nDDL = '+repr(tuple(ddl))+'\n'
source+='''

def upgrade():
    for statement in DDL:
        op.execute(statement)
    for statement in rls_statements(TABLES):
        op.execute(statement)


def downgrade():
    for table in reversed(TABLES):
        op.drop_table(table)
'''
Path('alembic/versions/0191_repair_completion.py').write_text(source,encoding='utf-8')
