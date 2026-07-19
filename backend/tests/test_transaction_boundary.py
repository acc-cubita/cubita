"""مرز تراکنش درخواست.

این تست‌ها عمداً از fixture `db` استفاده **نمی‌کنند**. آن fixture هر تست را در یک
تراکنش بیرونی می‌پیچد و در پایان rollback می‌کند، پس ذاتاً نمی‌تواند نشان دهد که
commit واقعی کِی اتفاق می‌افتد. اینجا با session واقعی کار می‌کنیم و خودمان پاک‌سازی
می‌کنیم، وگرنه چیزی را که ادعا می‌کنیم نسنجیده‌ایم.

قرارداد: هر درخواست یک تراکنش است. اگر هندلر موفق بود commit می‌شود، و اگر هر خطایی
داد — چه HTTPException چه خطای غیرمنتظره — کل درخواست برمی‌گردد. این پیش‌نیاز سخت
RLS در فاز بعد است، چون `SET LOCAL` به مرز تراکنش گره خورده.
"""
import uuid

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.inventory import Contact


@pytest.fixture
def probe_app():
    """اپ کوچک با همان get_db واقعی، برای سنجیدن خودِ مرز تراکنش."""
    app = FastAPI()

    @app.post("/ok/{name}")
    def ok(name: str, db: Session = Depends(get_db)):
        db.add(Contact(name=name, type="customer"))
        db.flush()
        return {"name": name}

    @app.post("/http-error/{name}")
    def http_error(name: str, db: Session = Depends(get_db)):
        db.add(Contact(name=name, type="customer"))
        db.flush()
        raise HTTPException(400, "خطای کسب‌وکار بعد از نوشتن")

    @app.post("/crash/{name}")
    def crash(name: str, db: Session = Depends(get_db)):
        db.add(Contact(name=name, type="customer"))
        db.flush()
        raise RuntimeError("خطای غیرمنتظره بعد از نوشتن")

    return app


@pytest.fixture
def probe(probe_app, _schema):
    return TestClient(probe_app, raise_server_exceptions=False)


def exists(name: str) -> bool:
    """با session کاملاً جدا می‌خواند تا واقعاً وضعیت پایدار را ببیند."""
    session = SessionLocal()
    try:
        return session.query(Contact).filter(Contact.name == name).first() is not None
    finally:
        session.close()


def cleanup(name: str) -> None:
    session = SessionLocal()
    try:
        session.query(Contact).filter(Contact.name == name).delete()
        session.commit()
    finally:
        session.close()


def test_successful_request_is_committed(probe):
    name = f"تست-موفق-{uuid.uuid4().hex[:8]}"
    try:
        assert probe.post(f"/ok/{name}").status_code == 200
        assert exists(name), "درخواست موفق باید commit شود"
    finally:
        cleanup(name)


def test_business_error_rolls_back_the_whole_request(probe):
    """مهم‌ترین حالت: HTTPException بعد از نوشتن نباید نیمه‌کاره باقی بگذارد.

    اگر این بشکند، هر اعتبارسنجی‌ای که بعد از یک db.add اجرا شود می‌تواند داده‌ی
    یتیم جا بگذارد — مثلاً سند حسابداری ساخته شود ولی فاکتورش نه.
    """
    name = f"تست-خطا-{uuid.uuid4().hex[:8]}"
    try:
        assert probe.post(f"/http-error/{name}").status_code == 400
        assert not exists(name), "خطای کسب‌وکار باید کل تراکنش را برگرداند"
    finally:
        cleanup(name)


def test_unexpected_error_rolls_back_the_whole_request(probe):
    name = f"تست-کرش-{uuid.uuid4().hex[:8]}"
    try:
        assert probe.post(f"/crash/{name}").status_code == 500
        assert not exists(name), "خطای غیرمنتظره باید کل تراکنش را برگرداند"
    finally:
        cleanup(name)
