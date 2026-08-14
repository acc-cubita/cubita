"""راه‌اندازیِ محلی — نسخه‌ی دسکتاپ روی SQLite (بدونِ alembic).

روی هر اجرا امن است (idempotent): اگر جدول‌ها نباشند می‌سازد (`create_all`، چون روی SQLite
مهاجرت‌های Postgres/RLS اجرا نمی‌شوند)، و اگر هیچ کاربری نباشد یک اکانتِ محلیِ پیش‌فرض
seed می‌کند (مستأجرِ واحد + مالک + چارتِ حساب + انبار + شمارنده‌ها). Electron این را
پیش از بالا آوردنِ سرورِ FastAPI صدا می‌زند.

اکانتِ پیش‌فرضِ محلی با متغیرهای محیطی قابلِ تنظیم است (`LOCAL_OWNER_EMAIL/PASSWORD`).
دامنه باید واقعی باشد (نه `.local`)، چون فرمِ ورود ایمیل را با EmailStr می‌سنجد.
"""
import os

import app.models  # noqa: F401  — ثبتِ همه‌ی مدل‌ها تا metadata کامل باشد
from app.database import Base, SessionLocal, engine
from app.models.user import User
from app.seed import seed

DEFAULT_EMAIL = os.environ.get("LOCAL_OWNER_EMAIL", "owner@hesabdari.ir")
DEFAULT_PASSWORD = os.environ.get("LOCAL_OWNER_PASSWORD", "owner")


def ensure_local_ready() -> None:
    """اسکیمای محلی را می‌سازد و در صورتِ خالی بودن، اکانتِ پیش‌فرض را seed می‌کند."""
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        has_user = db.query(User).first() is not None
    finally:
        db.close()
    if not has_user:
        seed(DEFAULT_EMAIL, DEFAULT_PASSWORD)


if __name__ == "__main__":
    ensure_local_ready()
    print(f"local bootstrap done (owner: {DEFAULT_EMAIL})")
