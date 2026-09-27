"""آزمون واقعی 0187؛ فقط در اسکیمای یک‌بارمصرف، هرگز روی public.

از backend اجرا شود: venv/Scripts/python.exe -m scripts.probe_office_automation
"""
import os
import re
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config import get_settings


def main():
    schema = "probe_office_" + uuid4().hex
    assert re.fullmatch(r"probe_office_[0-9a-f]{32}", schema)
    base = make_url(get_settings().database_url)
    engine = create_engine(base)
    with engine.connect() as conn:
        before = conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    probe_url = base.update_query_dict({"options": f"-csearch_path={schema}"})
    probe = create_engine(probe_url)
    env = {**os.environ, "DATABASE_URL": probe_url.render_as_string(hide_password=False), "PYTHONIOENCODING": "utf-8"}

    def migrate(action, revision):
        run = subprocess.run([sys.executable, "-m", "alembic", action, revision], env=env,
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        if run.returncode:
            raise RuntimeError(run.stderr[-6000:])
        print(f"{action} {revision}: OK", flush=True)

    try:
        with probe.connect() as conn:
            assert conn.execute(text("SELECT current_schema()")).scalar_one() == schema
        migrate("upgrade", "0186")
        tenant_ids = [uuid4(), uuid4()]
        with probe.begin() as conn:
            for tid in tenant_ids:
                conn.execute(text("INSERT INTO tenants (id,name,slug,status) VALUES (:id,'probe',:slug,'active')"), {"id": tid, "slug": str(tid)})
        migrate("upgrade", "0187")
        with probe.connect() as conn:
            for tid in tenant_ids:
                conn.execute(text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tid)})
                counters = conn.execute(text("SELECT doc_type FROM document_counters WHERE doc_type LIKE 'office_%'")).scalars().all()
                assert len(counters) == 3, counters
        migrate("downgrade", "0186")
        with probe.connect() as conn:
            assert conn.execute(text("SELECT to_regclass('office_letters')")).scalar_one() is None
        migrate("upgrade", "0187")
        with probe.connect() as conn:
            rows = conn.execute(text("""SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                (SELECT count(*) FROM pg_policy p WHERE p.polrelid=c.oid) policies
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=:schema AND c.relname IN
                ('office_letters','office_referrals','office_attachments','office_events')"""), {"schema": schema}).all()
            assert len(rows) == 4 and all(r[1] and r[2] and r[3] == 1 for r in rows), rows
            assert conn.execute(text("SELECT count(*) FROM pg_trigger WHERE tgrelid='office_events'::regclass AND tgname='office_events_no_update_delete'")).scalar_one() == 1
            assert conn.execute(text("SELECT data_type FROM information_schema.columns WHERE table_schema=:schema AND table_name='office_letters' AND column_name='number'"), {"schema": schema}).scalar_one() == "bigint"
            print("Four tables: ENABLE + FORCE RLS + tenant policies; append-only trigger; bigint: OK", flush=True)
    finally:
        probe.dispose()
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            after = conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
            assert after == before, (before, after)
        engine.dispose()
        print(f"Disposable schema removed; public.alembic_version unchanged ({before})", flush=True)


if __name__ == "__main__":
    main()
