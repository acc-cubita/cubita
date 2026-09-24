"""راه‌اندازیِ سرورِ «کوبیتا سازمانی» (ENTERPRISE_PLAN.md، M4).

تست‌های واحد بدونِ Postgres اجرا می‌شوند. تستِ یکپارچه (initdb ← نقش‌ها ← همه‌ی مهاجرت‌ها
← سنجشِ RLS با نقشِ برنامه) فقط وقتی اجرا می‌شود که مسیرِ `bin`ِ PostgreSQL داده شود:

    CUBITA_PG_BIN="C:/Program Files/PostgreSQL/17/bin" venv/Scripts/python.exe -m pytest tests/test_onprem.py
"""

import os
import socket
from pathlib import Path

import pytest

from app.onprem import provision as prov
from app.onprem import services as svc


def _layout(tmp_path) -> prov.Layout:
    return prov.Layout(tmp_path / "Cubita")


def test_secrets_are_created_once_and_kept(tmp_path):
    layout = _layout(tmp_path)
    first = prov.load_or_create_secrets(layout)
    assert len(first["secrets_key"]) >= 32 and len(first["jwt_secret"]) >= 32
    # نصبِ دوباره نباید رازها را عوض کند: کلیدِ مؤدیانِ رمزشده و نشست‌ها از دست می‌رفت.
    assert prov.load_or_create_secrets(layout) == first


def test_env_connects_app_as_restricted_role(tmp_path):
    s = prov.load_or_create_secrets(_layout(tmp_path))
    env = prov.render_env(s, 5433, 8420, tmp_path)
    lines = dict(line.split("=", 1) for line in env.splitlines() if line and not line.startswith("#"))
    assert lines["EDITION"] == "enterprise"
    assert lines["ENV"] == "production"
    assert lines["DATABASE_URL"].startswith(f"postgresql+psycopg://{prov.APP_ROLE}:")
    assert lines["MIGRATION_DATABASE_URL"].startswith(f"postgresql+psycopg://{prov.MIGRATE_ROLE}:")
    # برنامه هرگز با superuser یا مالک وصل نمی‌شود — آن‌وقت RLS بی‌صدا خاموش بود.
    assert f"://{prov.SUPERUSER}:" not in lines["DATABASE_URL"]
    assert s["superuser_password"] not in env
    assert lines["LICENSE_DIR"] == str(tmp_path)


def test_env_passes_the_production_guard(tmp_path, monkeypatch):
    """`.env`ِ تولیدشده باید از گاردِ `config._validate` رد شود (JWT قوی، سازمانی)."""
    from app.config import Settings, _validate

    s = prov.load_or_create_secrets(_layout(tmp_path))
    values = dict(
        line.split("=", 1) for line in prov.render_env(s, 5433, 8420).splitlines() if "=" in line and not line.startswith("#")
    )
    _validate(
        Settings(
            edition=values["EDITION"],
            env=values["ENV"],
            zarinpal_sandbox=values["ZARINPAL_SANDBOX"] == "true",
            jwt_secret=values["JWT_SECRET"],
            secrets_key=values["SECRETS_KEY"],
        )
    )


def test_password_with_special_chars_is_url_safe():
    url = prov.db_url("cubita_app", "a/b@c:d%e", 5433)
    assert "a%2Fb%40c%3Ad%25e" in url


def test_refuses_foreign_nonempty_data_dir(tmp_path):
    layout = _layout(tmp_path)
    layout.pgdata.mkdir(parents=True)
    (layout.pgdata / "something.txt").write_text("x")
    with pytest.raises(prov.ProvisionError, match="خالی نیست"):
        prov.init_cluster(tmp_path, layout, "pw", 5433)


def test_acl_uses_sids_not_localized_names(tmp_path):
    cmds = svc.acl_commands(_layout(tmp_path))
    flat = " ".join(" ".join(c) for c in cmds)
    for sid in (svc.SID_SYSTEM, svc.SID_ADMINS, svc.SID_NETWORK_SERVICE):
        assert sid in flat
    assert "Administrators" not in flat


def test_firewall_never_opens_public_profile():
    add = svc.firewall_commands(8420)[1]
    assert "profile=private,domain" in add
    assert not any("public" in a.lower() for a in add)


def test_winsw_config_runs_serve_after_postgres(tmp_path):
    xml = svc.winsw_xml(Path(r"C:\Program Files\Cubita Enterprise\server\cubita-server.exe"), _layout(tmp_path))
    assert "<depend>CubitaPostgres</depend>" in xml
    assert "serve --home" in xml
    assert "<startmode>Automatic</startmode>" in xml


def test_pg_service_runs_as_network_service(tmp_path):
    cmd = svc.pg_register_command(Path("C:/pg/bin"), _layout(tmp_path))
    assert cmd[cmd.index("-U") + 1] == svc.SERVICE_ACCOUNT


PG_BIN = os.environ.get("CUBITA_PG_BIN")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.skipif(not PG_BIN, reason="CUBITA_PG_BIN تنظیم نشده (مسیرِ bin ِ PostgreSQL)")
def test_full_provision_against_real_postgres(tmp_path):
    """کلِ راه‌اندازی روی یک کلاسترِ واقعی، و دوباره — بی‌خطر برای اجرای دوباره."""
    layout = _layout(tmp_path)
    port = _free_port()
    alembic_dir = Path(__file__).resolve().parents[1] / "alembic"
    try:
        first = prov.provision(
            layout=layout, pg_bin=Path(PG_BIN), alembic_dir=alembic_dir, pg_port=port, log=lambda m: None
        )
        assert first.cluster_created
        again = prov.provision(
            layout=layout, pg_bin=Path(PG_BIN), alembic_dir=alembic_dir, pg_port=port,
            keep_running=True, log=lambda m: None,
        )
        assert not again.cluster_created and again.alembic_version == first.alembic_version
        assert prov.verify_isolation(prov.read_env(layout)["DATABASE_URL"]) > 100
    finally:
        if prov.is_running(Path(PG_BIN), layout):
            prov.pg_ctl(Path(PG_BIN), layout, "stop")
