"""اجرای واقعی مهاجرت فقط روی PostgreSQL آزمایشی جدا؛ نام schema تصادفی است."""
import os
import subprocess
import sys
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.database import Base
import app.models  # noqa: F401


def main():
    base = make_url(os.environ['REPAIR_PROBE_DATABASE_URL'])
    if base.host != '127.0.0.1' or base.port != 55438:
        raise RuntimeError('Repair probe requires isolated test PostgreSQL on 127.0.0.1:55438')
    engine = create_engine(base)
    schema = 'probe_repair_' + uuid4().hex
    def public_version(conn):
        return conn.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one() if conn.execute(text("SELECT to_regclass('public.alembic_version')")).scalar_one() else None
    with engine.begin() as conn:
        before = public_version(conn)
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = base.update_query_dict({'options': '-csearch_path=' + schema})
    probe = create_engine(url)
    env = {**os.environ, 'DATABASE_URL': url.render_as_string(hide_password=False), 'ZARINPAL_SANDBOX':'true', 'PYTHONIOENCODING':'utf-8'}
    def migrate(action, revision):
        result = subprocess.run([sys.executable, '-m','alembic',action,revision], env=env, capture_output=True, text=True, encoding='utf-8', timeout=600)
        if result.returncode:
            raise RuntimeError(result.stderr[-5000:])
        print(action, revision, 'OK', flush=True)
    try:
        migrate('upgrade', '0189')
        ids = [uuid4(),uuid4()]
        with probe.begin() as conn:
            for tid in ids:
                conn.execute(text("INSERT INTO tenants(id,name,slug,status) VALUES(:id,'repair-probe',:slug,'active')"), {'id':tid,'slug':str(tid)})
        migrate('upgrade','0190')
        with probe.connect() as conn:
            for tid in ids:
                conn.execute(text("SELECT set_config('app.tenant_id',:id,true)"), {'id':str(tid)})
                assert conn.execute(text("SELECT last_number FROM document_counters WHERE doc_type='repair_admission'")).scalar_one() == 0
            rows = conn.execute(text("SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,(SELECT count(*) FROM pg_policy p WHERE p.polrelid=c.oid) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=:schema AND c.relname LIKE 'repair_%' AND c.relkind='r'"), {'schema':schema}).all()
            assert len(rows) == len([t for t in Base.metadata.tables if t.startswith('repair_')]) and all(r[1] and r[2] and r[3] == 1 for r in rows), rows
        migrate('downgrade','0189')
        with probe.connect() as conn:
            assert conn.execute(text("SELECT to_regclass('repair_cases')")).scalar_one() is None
        migrate('upgrade','0190')
        print(f'{len(rows)} tables FORCE RLS, existing-tenant counters, downgrade and re-upgrade: OK', flush=True)
    finally:
        probe.dispose()
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            assert public_version(conn) == before
        engine.dispose()
        print('Disposable schema removed; public version unchanged', flush=True)


if __name__ == '__main__':
    main()
