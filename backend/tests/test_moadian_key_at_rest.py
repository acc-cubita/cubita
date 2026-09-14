"""کلیدِ امضای مؤدیان در حالتِ سکون.

**آنچه بررسی نشان داد.** `moadian_settings.private_key_pem` متنِ خام بود. سه
دفاع داشت و هر سه واقعی‌اند — از API برنمی‌گشت، در لاگ نمی‌آمد، و RLS جدایش
می‌کرد — ولی هیچ‌کدام **یک نسخه‌ی پشتیبان** را پوشش نمی‌دادند. یک `pg_dump`
یعنی کلیدِ امضای همه‌ی کسب‌وکارها در دستِ کسی که آن فایل را دارد.

و یک دامِ ظریف در راهِ حل: افزودنِ `MoadianSettings` به حسابرسی **بدونِ**
`SECRET_FIELDS` اوضاع را بدتر می‌کرد، چون `_changed_fields` مقدارِ قبل و بعدِ هر
ستون را در `audit_log` می‌نویسد — یعنی همان رازی که رمزش کردیم، در جدولی دیگر
به شکلِ JSON لو می‌رفت.
"""
from decimal import Decimal

import pytest

from app.audit import SECRET_FIELDS, audited_models
from app.models.audit import AuditLog
from app.models.moadian import MoadianSettings
from app import secrets_at_rest

PLAIN = "-----BEGIN PRIVATE KEY-----\nMIIFakeProbeKeyMaterial\n-----END PRIVATE KEY-----"
KEY = "unit-test-secrets-key-long-enough-for-the-guard-01"


@pytest.fixture
def with_key(monkeypatch):
    """`SECRETS_KEY` را برای این تست روشن می‌کند و کشِ تنظیمات را پاک."""
    from app.config import get_settings

    monkeypatch.setenv("SECRETS_KEY", KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ─────────── ۱) رمزگذاری ───────────


def test_the_key_is_not_readable_in_the_stored_column(db, with_key):
    """**باگی که بسته شد.** ستون دیگر متنِ خام ندارد."""
    row = MoadianSettings(memory_id="AB1234", private_key_pem=PLAIN)
    db.add(row)
    db.flush()
    assert row.private_key_stored.startswith(secrets_at_rest.PREFIX)
    assert "BEGIN PRIVATE KEY" not in row.private_key_stored
    #: و همان شیء کلیدِ باز را می‌دهد — مصرف‌کننده‌ها عوض نمی‌شوند.
    assert row.private_key_pem == PLAIN


def test_a_raw_sql_read_sees_only_ciphertext(db, with_key):
    """همان چیزی که `pg_dump` می‌بیند."""
    from sqlalchemy import text

    row = MoadianSettings(memory_id="CD5678", private_key_pem=PLAIN)
    db.add(row)
    db.flush()
    stored = db.execute(
        text("SELECT private_key_pem FROM moadian_settings WHERE id = :i"), {"i": row.id}
    ).scalar_one()
    assert "BEGIN PRIVATE KEY" not in stored, "*** متنِ خام در دیتابیس است ***"


def test_encryption_is_idempotent(db, with_key):
    """ذخیره‌ی دوباره‌ی همان شیء نباید دو بار رمز کند."""
    row = MoadianSettings(memory_id="EF9012", private_key_pem=PLAIN)
    db.add(row)
    db.flush()
    once = row.private_key_stored
    row.private_key_stored = secrets_at_rest.encrypt(once)
    assert row.private_key_stored == once
    assert row.private_key_pem == PLAIN


def test_without_a_key_the_value_stays_plain_and_still_reads(db):
    """**رفتارِ دیروز پیش‌فرض است.** نبودِ `SECRETS_KEY` ذخیره را نمی‌شکند."""
    from app.config import get_settings

    get_settings.cache_clear()
    row = MoadianSettings(memory_id="GH3456", private_key_pem=PLAIN)
    db.add(row)
    db.flush()
    assert row.private_key_stored == PLAIN
    assert row.private_key_pem == PLAIN


def test_a_legacy_plaintext_row_still_reads_with_a_key_configured(db, with_key):
    """داده‌ی مهاجرت‌نشده نباید بشکند."""
    row = MoadianSettings(memory_id="IJ7890")
    row.private_key_stored = PLAIN  # مستقیم، بدونِ setter — شکلِ پیش از ۰۱۴۸
    db.add(row)
    db.flush()
    assert row.private_key_pem == PLAIN


def test_a_wrong_key_raises_loudly_instead_of_returning_empty(db, with_key, monkeypatch):
    """«کلید نیست» و «کلید خوانده نشد» دو چیزند؛ قاطی‌کردنشان گمراه‌کننده است."""
    from app.config import get_settings

    row = MoadianSettings(memory_id="KL1111", private_key_pem=PLAIN)
    db.add(row)
    db.flush()
    ciphertext = row.private_key_stored

    monkeypatch.setenv("SECRETS_KEY", "a-completely-different-key-0000000000000000")
    get_settings.cache_clear()
    other = MoadianSettings(memory_id="MN2222")
    other.private_key_stored = ciphertext
    with pytest.raises(secrets_at_rest.SecretUnreadable):
        other.private_key_pem


# ─────────── ۲) حسابرسی — و دامش ───────────


def test_moadian_settings_is_audited(db):
    assert MoadianSettings in audited_models()


def test_the_audit_trail_never_records_the_key_itself(db, client, with_key):
    """**گاردِ همان دام.** رد می‌ماند، راز نه."""
    before = db.query(AuditLog).count()
    res = client.put(
        "/api/moadian/settings",
        json={
            "memory_id": "OP3333",
            "economic_code": "1234",
            "national_id": "5678",
            "private_key_pem": PLAIN,
        },
    )
    assert res.status_code in (200, 201), res.text

    logs = db.query(AuditLog).all()
    assert len(logs) > before, "تغییرِ اعتبارنامه ردی نگذاشت"
    blob = "".join(str(log.changes or "") for log in logs)
    assert "BEGIN PRIVATE KEY" not in blob, "*** کلید در جدولِ حسابرسی لو رفت ***"
    assert PLAIN not in blob


def test_secret_fields_all_exist_on_the_model(db):
    """اگر ستونی تغییرِ نام بدهد، گارد نباید بی‌صدا رد شود.

    `_changed_fields` روی **خاصیتِ ORM** می‌چرخد نه نامِ ستون — و کلیدِ مؤدیان
    ستونش `private_key_pem` است ولی خاصیتش `private_key_stored`.
    """
    from sqlalchemy import inspect

    keys = {a.key for a in inspect(MoadianSettings).column_attrs}
    assert SECRET_FIELDS <= keys, f"نامِ نادرست در SECRET_FIELDS: {SECRET_FIELDS - keys}"


# ─────────── ۳) مسیرِ API ───────────


def test_the_settings_endpoint_never_returns_the_key(db, client, with_key):
    client.put(
        "/api/moadian/settings",
        json={"memory_id": "QR4444", "economic_code": "1", "national_id": "2",
              "private_key_pem": PLAIN},
    )
    body = client.get("/api/moadian/settings").json()
    assert body["has_private_key"] is True
    assert "private_key_pem" not in body
    assert PLAIN not in str(body)


def test_has_private_key_survives_a_lost_secrets_key(db, client, with_key, monkeypatch):
    """**صفحه‌ی تنظیمات باید باز شود، حتی وقتی کلید خوانده نمی‌شود.**

    وگرنه دقیقاً وقتی کاربر باید کلیدِ تازه آپلود کند، صفحه ۵۰۰ می‌دهد.
    """
    from app.config import get_settings

    client.put(
        "/api/moadian/settings",
        json={"memory_id": "ST5555", "economic_code": "1", "national_id": "2",
              "private_key_pem": PLAIN},
    )
    monkeypatch.delenv("SECRETS_KEY", raising=False)
    get_settings.cache_clear()

    res = client.get("/api/moadian/settings")
    assert res.status_code == 200, res.text
    assert res.json()["has_private_key"] is True
