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


#: **ثبتِ رویدادهای حسابرسی — این import عارضه‌ی جانبی دارد و عمدی است.**
#:
#: `app.audit` با `@event.listens_for(Session, "before_flush")` خودش را روی
#: *هر* نشستِ SQLAlchemy می‌نشاند. تا امروز هیچ‌کس صریح import‌اش نمی‌کرد؛ در
#: اپِ وب اتفاقی از راهِ `app.deps` می‌آمد چون هر router به آن وابسته است.
#:
#: یعنی پوششِ حسابرسی به یک زنجیره‌ی importِ **ناخواسته** بند بود: هر اسکریپت،
#: cron یا کارِ پس‌زمینه‌ای که `SessionLocal` بگیرد و آن زنجیره را نداشته باشد،
#: روی مدلِ حسابرسی‌شده می‌نویسد و ردش **بی‌صدا** گم می‌شود — نه خطایی، نه
#: هشداری. این یک بار واقعاً اتفاق افتاد: لغوِ یک جلسه‌ی انبارگردانی از یک
#: اسکریپتِ سرور، بدونِ هیچ ردی در `audit_log`.
#:
#: این‌جا می‌نشیند چون هرکس روی دیتابیس می‌نویسد از همین ماژول `SessionLocal`
#: می‌گیرد. **انتهای فایل** هم اجباری است نه سلیقه: `app.audit` به
#: `app.models.audit` وابسته است و آن به `Base`ِ همین فایل — پس تا `Base`
#: تعریف نشده باشد، این import حلقه‌ی نیمه‌ساخته می‌دهد.
from app import audit as _audit  # noqa: E402,F401  (ثبتِ listener، نه استفاده از نام)
