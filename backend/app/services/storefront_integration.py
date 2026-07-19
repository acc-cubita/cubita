"""اتصال به سایت فروشگاهی (ipnetcity.ir / پروژه‌ی D:\\camera).

طبق پلن تأییدشده: حسابداری منبع حقیقت موجودی/قیمت است (push)، و سفارش‌های ثبت‌شده روی سایت
به‌صورت فاکتور فروش وارد حسابداری می‌شوند (pull). این ماژول به هیچ کد سمت سایت فروشگاهی نیاز ندارد؛
فقط از اندپوینت‌های عمومی/ادمین موجود آن (GET /api/products/{id}، PUT /api/admin/products/{id}،
GET /api/admin/orders، POST /api/auth/login) استفاده می‌کند. هر sync دوباره با ایمیل/رمز لاگین می‌کند
تا نیازی به نگهداری توکن بلندمدت نباشد.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.inventory import Item, Warehouse
from app.models.invoices import SalesInvoice
from app.models.user import User
from app.schemas.invoices import SalesInvoiceIn, SalesInvoiceLineIn
from app.services.inventory import get_total_stock_qty, post_sales_invoice

# فقط همین فیلدها را PUT /api/admin/products/{id} می‌پذیرد (ProductIn روی main.py سایت)؛
# بقیه‌ی فیلدهای برگشتی از GET (id, sold, rating, slug, ...) باید قبل از PUT حذف شوند.
_PRODUCT_IN_FIELDS = (
    "title", "brand", "cat", "subcategory", "price", "orig", "discount",
    "stock", "images", "specs", "description", "is_flash", "is_new", "out_of_stock",
)

ONLINE_WAREHOUSE_CODE = "ONLINE"


class StorefrontConfigError(Exception):
    """تنظیمات اتصال به سایت فروشگاهی کامل نیست (در .env)."""


class StorefrontClient:
    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self._client = httpx.Client(base_url=self.base_url, timeout=20.0)
        self._token: str | None = None

    def _ensure_token(self) -> str:
        if self._token is None:
            res = self._client.post("/api/auth/login", json={"email": self.email, "password": self.password})
            res.raise_for_status()
            self._token = res.json()["access_token"]
        return self._token

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._ensure_token()}"}

    def get_product(self, product_id: int) -> dict:
        res = self._client.get(f"/api/products/{product_id}")
        res.raise_for_status()
        return res.json()

    def update_product_stock_price(self, product_id: int, stock: int, price: Decimal, out_of_stock: bool) -> dict:
        current = self.get_product(product_id)
        body = {k: current[k] for k in _PRODUCT_IN_FIELDS if k in current}
        body["stock"] = stock
        body["out_of_stock"] = out_of_stock
        if price > 0:
            body["price"] = float(price)
        res = self._client.put(f"/api/admin/products/{product_id}", json=body, headers=self._auth_headers())
        res.raise_for_status()
        return res.json()

    def list_orders(self, page: int, per_page: int = 50) -> dict:
        res = self._client.get(
            "/api/admin/orders", params={"page": page, "per_page": per_page}, headers=self._auth_headers()
        )
        res.raise_for_status()
        return res.json()

    def close(self) -> None:
        self._client.close()


def _build_client() -> StorefrontClient:
    settings = get_settings()
    if not (settings.storefront_api_base_url and settings.storefront_admin_email and settings.storefront_admin_password):
        raise StorefrontConfigError(
            "STOREFRONT_API_BASE_URL / STOREFRONT_ADMIN_EMAIL / STOREFRONT_ADMIN_PASSWORD در .env تنظیم نشده‌اند"
        )
    return StorefrontClient(
        settings.storefront_api_base_url, settings.storefront_admin_email, settings.storefront_admin_password
    )


@dataclass
class PushResult:
    pushed: list[str] = field(default_factory=list)  # item sku هایی که موفق push شدند
    failed: list[dict] = field(default_factory=list)  # [{"sku":.., "error":..}]


def push_stock_and_price(db: Session, client: StorefrontClient | None = None) -> PushResult:
    owns_client = client is None
    client = client or _build_client()
    result = PushResult()
    try:
        items = (
            db.query(Item)
            .filter(Item.storefront_product_id.isnot(None), Item.is_service.is_(False), Item.is_active.is_(True))
            .all()
        )
        for item in items:
            try:
                total_qty = get_total_stock_qty(db, item.id)
                stock_to_push = max(0, int(total_qty))
                client.update_product_stock_price(
                    item.storefront_product_id, stock_to_push, Decimal(item.sales_price), stock_to_push <= 0
                )
                result.pushed.append(item.sku)
            except httpx.HTTPError as err:
                result.failed.append({"sku": item.sku, "error": str(err)})
        return result
    finally:
        if owns_client:
            client.close()


@dataclass
class PullResult:
    imported: list[int] = field(default_factory=list)  # شناسه‌ی سفارش‌های روی سایت که وارد شدند
    skipped: list[dict] = field(default_factory=list)  # [{"order_id":.., "reason":..}]


def _get_online_warehouse(db: Session) -> Warehouse | None:
    return db.query(Warehouse).filter(Warehouse.code == ONLINE_WAREHOUSE_CODE).first()


def pull_new_orders(
    db: Session, user: User, client: StorefrontClient | None = None, max_pages: int = 5, per_page: int = 50
) -> PullResult:
    owns_client = client is None
    client = client or _build_client()
    result = PullResult()
    try:
        warehouse = _get_online_warehouse(db)
        if warehouse is None:
            result.skipped.append({"order_id": None, "reason": f"انبار «{ONLINE_WAREHOUSE_CODE}» یافت نشد؛ seed را اجرا کنید"})
            return result

        already_imported = {
            row[0] for row in db.query(SalesInvoice.source_order_id).filter(SalesInvoice.source_order_id.isnot(None)).all()
        }

        items_by_storefront_id = {
            item.storefront_product_id: item
            for item in db.query(Item).filter(Item.storefront_product_id.isnot(None)).all()
        }

        for page in range(1, max_pages + 1):
            page_data = client.list_orders(page, per_page)
            orders = page_data.get("items", [])
            if not orders:
                break

            for order in orders:
                order_id = order["id"]
                if order_id in already_imported:
                    continue

                lines: list[SalesInvoiceLineIn] = []
                unmapped: list[int] = []
                for line in order.get("items", []):
                    item = items_by_storefront_id.get(line["product_id"])
                    if item is None:
                        unmapped.append(line["product_id"])
                        continue
                    lines.append(
                        SalesInvoiceLineIn(item_id=item.id, qty=Decimal(str(line["qty"])), unit_price=Decimal(str(line["price"])))
                    )

                if unmapped:
                    result.skipped.append(
                        {"order_id": order_id, "reason": f"کالای بدون نگاشت storefront_product_id: {unmapped}"}
                    )
                    continue
                if not lines:
                    result.skipped.append({"order_id": order_id, "reason": "سفارش بدون ردیف کالا"})
                    continue

                try:
                    invoice_date = date.fromisoformat((order.get("created_at") or "")[:10])
                except ValueError:
                    invoice_date = date.today()

                # هر سفارش داخل savepoint خودش وارد می‌شود تا یک سفارش خراب فقط خودش
                # برگردد. قبلاً اینجا db.rollback() بود؛ حالا که کل درخواست یک تراکنش
                # است، rollback کامل سفارش‌های موفقِ همین اجرا را هم پاک می‌کرد.
                try:
                    with db.begin_nested():
                        post_sales_invoice(
                            db,
                            SalesInvoiceIn(
                                invoice_date=invoice_date,
                                warehouse_id=warehouse.id,
                                contact_id=None,
                                description=f"سفارش آنلاین #{order_id} (کد رهگیری {order.get('tracking_code', '')})",
                                lines=lines,
                                source_order_id=order_id,
                            ),
                            user,
                        )
                    result.imported.append(order_id)
                    already_imported.add(order_id)
                except Exception as err:  # noqa: BLE001 - می‌خواهیم یک سفارش خراب بقیه‌ی sync را متوقف نکند
                    result.skipped.append({"order_id": order_id, "reason": str(err)})

            if len(orders) < per_page:
                break

        return result
    finally:
        if owns_client:
            client.close()


def sync_all(db: Session, user: User) -> dict:
    client = _build_client()
    try:
        pull_result = pull_new_orders(db, user, client=client)
        push_result = push_stock_and_price(db, client=client)
        return {
            "orders_imported": pull_result.imported,
            "orders_skipped": pull_result.skipped,
            "items_pushed": push_result.pushed,
            "items_push_failed": push_result.failed,
        }
    finally:
        client.close()
