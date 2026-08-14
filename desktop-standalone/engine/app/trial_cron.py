"""ورودیِ کرونِ چرخه‌ی عمرِ آزمایشی — روزی یک بار اجرا می‌شود.

    /opt/<app>/venv/bin/python -m app.trial_cron

یک تراکنش: همه‌ی حساب‌های آزمایشی را پردازش می‌کند (یادآوری + حذف) و commit می‌کند.
خلاصه را چاپ می‌کند تا در لاگِ systemd/journalctl دیده شود.
"""
from app.database import SessionLocal
from app.services.trial_lifecycle import process_trials


def main() -> None:
    db = SessionLocal()
    try:
        result = process_trials(db)
        db.commit()
        print(f"trial-lifecycle: {result}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
