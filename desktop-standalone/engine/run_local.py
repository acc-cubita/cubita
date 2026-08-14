"""نقطه‌ی ورودِ سرورِ محلی — Electron این را به‌عنوانِ سایدکار اسپاون می‌کند.

اسکیمای محلی را آماده می‌کند (create_all + seedِ اکانتِ پیش‌فرض در صورتِ خالی بودن)،
سپس FastAPI را روی `127.0.0.1:<PORT>` بالا می‌آورد. Electron `DATABASE_URL` (مسیرِ فایل در
پوشه‌ی دیتای کاربر) و `PORT` را از طریقِ محیط تنظیم می‌کند.

اجرا (دستی برای تست):  PORT=8799 python run_local.py
"""
import os

import uvicorn

from app.local_bootstrap import ensure_local_ready


def main() -> None:
    ensure_local_ready()
    port = int(os.environ.get("PORT", "8799"))
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
