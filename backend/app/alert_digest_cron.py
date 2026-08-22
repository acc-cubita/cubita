"""ورودیِ کرونِ دایجستِ هشدارها — روزی یک بار (صبح) اجرا می‌شود.

    /opt/<app>/venv/bin/python -m app.alert_digest_cron

برای هر مستأجرِ دارای اپ، هشدارهای «نیازِ رسیدگی» را می‌سنجد و یک Push خلاصه
می‌فرستد. خواندنی است؛ چیزی commit نمی‌شود. خلاصه را برای journalctl چاپ می‌کند.
"""
from app.database import SessionLocal
from app.services.alert_digest import send_daily_digests


def main() -> None:
    db = SessionLocal()
    try:
        result = send_daily_digests(db)
        db.rollback()  # خواندنی — تراکنش را تمیز ببند
        print(f"alert-digest: {result}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
