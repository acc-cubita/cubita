from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

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
