"""ارزها و نرخِ برابری — داده‌ی مرجعِ لایه‌ی چندارزی.

پایه (ریال) ضمنی است و اینجا ثبت نمی‌شود؛ فقط ارزهای خارجی و نرخِشان نگه داشته
می‌شوند تا فرمِ فاکتور نرخِ روز را پیشنهاد دهد. هیچ‌کدام سند حسابداری نمی‌سازند.
"""
from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.currency import Currency, ExchangeRate
from app.models.user import User
from app.schemas.currency import CurrencyIn, ExchangeRateIn


def list_currencies(db: Session) -> list[Currency]:
    return db.query(Currency).order_by(Currency.code).all()


def create_currency(db: Session, data: CurrencyIn, user: User) -> Currency:
    if db.query(Currency).filter(Currency.code == data.code).first() is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"ارز «{data.code}» قبلاً تعریف شده")
    currency = Currency(code=data.code, name=data.name, symbol=data.symbol, created_by_id=user.id)
    db.add(currency)
    db.flush()
    db.refresh(currency)
    return currency


def delete_currency(db: Session, currency_id: UUID) -> None:
    currency = db.get(Currency, currency_id)
    if currency is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ارز یافت نشد")
    # نرخ‌های همین ارز هم پاک می‌شوند (سوابقِ نرخ بدونِ ارز بی‌معنا است).
    db.query(ExchangeRate).filter(ExchangeRate.currency_code == currency.code).delete()
    db.delete(currency)
    db.flush()


def list_rates(db: Session, currency_code: str | None = None) -> list[ExchangeRate]:
    q = db.query(ExchangeRate)
    if currency_code:
        q = q.filter(ExchangeRate.currency_code == currency_code.upper())
    return q.order_by(ExchangeRate.rate_date.desc(), ExchangeRate.currency_code).all()


def upsert_rate(db: Session, data: ExchangeRateIn, user: User) -> ExchangeRate:
    if db.query(Currency).filter(Currency.code == data.currency_code).first() is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"ارز «{data.currency_code}» تعریف نشده")
    existing = (
        db.query(ExchangeRate)
        .filter(ExchangeRate.currency_code == data.currency_code, ExchangeRate.rate_date == data.rate_date)
        .first()
    )
    if existing is not None:
        existing.rate = data.rate  # همان روز = به‌روزرسانی، نه ردیف تازه
        db.flush()
        db.refresh(existing)
        return existing
    rate = ExchangeRate(
        currency_code=data.currency_code, rate_date=data.rate_date, rate=data.rate, created_by_id=user.id
    )
    db.add(rate)
    db.flush()
    db.refresh(rate)
    return rate


def latest_rate(db: Session, currency_code: str, as_of: date | None = None) -> ExchangeRate | None:
    """آخرین نرخِ ثبت‌شده تا تاریخِ `as_of` (پیش‌فرض: امروز)."""
    as_of = as_of or date.today()
    return (
        db.query(ExchangeRate)
        .filter(ExchangeRate.currency_code == currency_code.upper(), ExchangeRate.rate_date <= as_of)
        .order_by(ExchangeRate.rate_date.desc())
        .first()
    )


def get_latest(db: Session, currency_code: str) -> dict:
    rate = latest_rate(db, currency_code)
    return {
        "currency_code": currency_code.upper(),
        "rate": rate.rate if rate else None,
        "rate_date": rate.rate_date if rate else None,
    }
