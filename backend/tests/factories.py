"""سازنده‌های داده‌ی تست.

عمداً ساده و صریح نگه داشته شده — تست حسابداری باید بتواند دقیقاً بگوید چه چیزی
ثبت شده، پس هیچ مقدار تصادفی پنهانی اینجا نیست مگر جایی که صراحتاً خواسته شود.
"""
import itertools
from decimal import Decimal

from app.models.inventory import Contact, Item, Warehouse

_seq = itertools.count(1)


def make_item(
    db,
    *,
    sku: str | None = None,
    name: str = "کالای تست",
    sales_price: Decimal | int = 1_000_000,
    average_cost: Decimal | int = 0,
    is_service: bool = False,
) -> Item:
    item = Item(
        sku=sku or f"TEST-{next(_seq):05d}",
        name=name,
        sales_price=Decimal(sales_price),
        average_cost=Decimal(average_cost),
        is_service=is_service,
    )
    db.add(item)
    db.flush()
    return item


def make_contact(db, *, name: str = "طرف‌حساب تست", type_: str = "customer") -> Contact:
    contact = Contact(name=name, type=type_)
    db.add(contact)
    db.flush()
    return contact


def main_warehouse(db) -> Warehouse:
    """انبار اصلی که seed می‌سازد."""
    return db.query(Warehouse).filter(Warehouse.code == "MAIN").one()


def other_warehouse(db) -> Warehouse:
    """انبار آنلاین که seed می‌سازد — برای تست‌های چندانباری."""
    return db.query(Warehouse).filter(Warehouse.code == "ONLINE").one()
