from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# نسخه‌ی محلیِ دسکتاپ روی SQLite اجرا می‌شود (تک‌کاربر، بدونِ Postgres/چندمستأجری).
# اتصال و نوع‌ها را برای SQLite تنظیم می‌کنیم؛ در حالتِ Postgres رفتارِ قبلی دست‌نخورده می‌ماند.
_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    # نوع‌های خاصِ Postgres را روی SQLite رندر کن (JSONB→JSON). UUID خودش کار می‌کند.
    from app import sqlite_compat  # noqa: F401

    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _rec) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()
else:
    engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    """یک درخواست = یک تراکنش.

    سرویس‌ها فقط flush می‌کنند و تصمیم commit/rollback اینجا گرفته می‌شود. قبلاً هر
    سرویس خودش commit می‌کرد (۳۸ نقطه) بدون هیچ rollbackی، پس خطایی که بعد از یک
    commit میانی رخ می‌داد داده‌ی نیمه‌کاره جا می‌گذاشت — مثلاً سند حسابداری ثبت‌شده
    بدون فاکتور متناظرش.

    این علاوه بر درستی، پیش‌نیاز فاز بعد است: RLS مقدار مستأجر را با SET LOCAL
    می‌گیرد که به تراکنش گره خورده، و commit وسط سرویس آن را از بین می‌برد.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
