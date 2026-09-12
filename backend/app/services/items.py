"""کالا و خدمت به‌عنوان داده‌ی پایه — حسابِ هزینه، نرخِ مالیات، و مرزهای رفتاری.

**یک هویت، رفتارِ وابسته به نوع (§۴۶ §۴۷).** کوبیتا از روزِ اول یک جدولِ `items`
داشت و خرید و فروش و انبار و صندوق همه از همان می‌خواندند؛ آن اصلِ اصلیِ فصل از
قبل رعایت شده بود. ولی *رفتار* یکی مانده بود، و این‌جا همان‌جاست که از هم جدا
می‌شوند.

---

**نقصی که این فایل می‌بندد.** `post_purchase_invoice` کلِ مبلغِ فاکتور را بدهکارِ
«موجودی کالا» می‌کرد — چه کالا بود چه خدمت. خریدِ ده ساعت مشاوره‌ی حقوقی یعنی:

* ترازنامه ۵۰ میلیون دارایی نشان می‌داد که **وجود نداشت** و هرگز هم خارج نمی‌شد؛
* گزارشِ انبار صفر می‌گفت، چون از `stock_ledger` مشتق می‌شود و خدمت حرکت ندارد؛
* هزینه **هیچ‌وقت** به سود و زیان نمی‌رسید، پس سود به همان اندازه بیش‌ازواقع بود؛
* و هیچ ترازی به‌هم نمی‌خورد که خبر بدهد — سند متوازن بود.

§۱۶ همین است: «فاکتورِ خریدِ خدمت می‌تواند اثرِ مالی داشته باشد، ولی نباید صرفاً
به‌خاطرِ داشتنِ واحد وارد موجودی شود.»
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import Account
from app.models.inventory import (
    Item,
    ItemAttribute,
    ItemAttributeValue,
    ItemGroup,
    ItemWarehouse,
    StockLedger,
    Warehouse,
)
from app.services import chart_codes as cc
from app.services.common import assert_postable_account as assert_postable
from app.services.common import get_or_create_account


def service_expense_account(db: Session) -> Account:
    """حسابِ پیش‌فرضِ «هزینه خرید خدمات».

    `get_or_create` است نه `get`: این نقش بعد از استقرارِ کسب‌وکارهای موجود اضافه
    شده و چارتِ هیچ‌کدامشان آن را ندارد. اولین خریدِ خدمت خودش می‌سازدش — همان
    الگوی «چک‌های واگذارشده به بانک» و حساب‌های ارزش افزوده.
    """
    return get_or_create_account(
        db,
        cc.SERVICE_EXPENSE,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.SERVICE_EXPENSE],
        name="هزینه خرید خدمات",
        acc_type="expense",
        parent_code="5",
    )


def purchase_account_id(db: Session, item: Item, *, inventory_account_id: UUID) -> UUID:
    """حسابی که بهای خریدِ این قلم رویش می‌نشیند (§۱۵ §۱۶).

    **کالا → موجودیِ همان انبار. خدمت → حسابِ هزینه.** این تنها جایی است که این
    دو راه از هم جدا می‌شوند؛ بقیه‌ی موتورِ خرید یکی می‌ماند.

    نگاشتِ اختصاصیِ کالا مقدم است و خالی‌بودنش یعنی پیش‌فرضِ نقش — همان قاعده‌ای
    که معینِ انبار دارد. حساب هیچ‌جا با کد یا نام پیدا نمی‌شود.
    """
    if not item.is_service:
        return inventory_account_id
    if item.expense_account_id is not None:
        return item.expense_account_id
    return service_expense_account(db).id


def assert_expense_account(db: Session, account_id: UUID | None) -> None:
    """معینِ هزینه‌ی کالا باید حسابی باشد که سند می‌پذیرد و نقشِ ماژولِ دیگری نباشد."""
    assert_postable(db, account_id, allow_role=cc.SERVICE_EXPENSE, subject="کالا/خدمت")


def effective_tax_rate(item: Item, invoice_rate: Decimal, *, side: str) -> Decimal:
    """نرخی که واقعاً روی این ردیف می‌نشیند (§۱۳ §۱۴).

    سه لایه، به همین ترتیب:

    ۱. **معاف؟** صفر. معافیت مفهومی جدا از نرخ است — §۱۳ می‌گوید وضعیتِ مالیاتیِ
       خرید و فروش الزاماً یکی نیست، پس هر سمت پرچمِ خودش را دارد.
    ۲. **کالا نرخِ خودش را دارد؟** همان.
    ۳. وگرنه نرخِ سرِ فاکتور — یعنی **رفتارِ امروزِ کوبیتا**. نرخِ کالا برای همه‌ی
       کالاهای موجود صفر است، پس افزودنِ این لایه هیچ فاکتوری را تکان نمی‌دهد.

    آنچه در فاکتور می‌ماند `tax_rate_snapshot`ِ ردیف است، نه این تابع (§۱۴).
    """
    status_ = item.purchase_vat_status if side == "purchase" else item.vat_status
    if status_ == "exempt":
        return Decimal(0)
    own = Decimal(item.tax_rate or 0)
    return own if own > 0 else Decimal(invoice_rate or 0)


def assert_sellable(db: Session, items: list[Item]) -> None:
    """§۷ §۵۳ — هرچه در انبار داریم فروختنی نیست.

    موادِ اولیه و موادِ بسته‌بندی موجودی دارند و گردش می‌کنند، ولی در فاکتورِ
    فروش و صندوق نباید انتخاب شوند. تا امروز این تفکیک اصلاً وجود نداشت.
    """
    blocked = [i.name for i in items if not i.is_sellable]
    if blocked:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"«{'»، «'.join(blocked)}» قابلِ فروش علامت نخورده و در فروش انتخاب نمی‌شود. "
            "اگر باید فروخته شود، در تعریفِ کالا «قابل فروش» را روشن کنید.",
        )


def has_stock_history(db: Session, item_id: UUID) -> bool:
    return db.query(StockLedger.id).filter(StockLedger.item_id == item_id).first() is not None


def assert_serial_toggle_allowed(db: Session, item: Item, new_value: bool) -> None:
    """§۹ — «ثبت سریالی» را وسطِ گردشِ کالا نمی‌شود عوض کرد.

    کالایی که سال‌ها بی‌سریال گردش کرده، موجودیِ امروزش سریال ندارد. روشن‌کردنِ
    این پرچم یعنی از فردا هر ورود سریال می‌خواهد در حالی که موجودیِ قبلی‌اش
    ناشناس است — و خاموش‌کردنش یعنی سریال‌های ثبت‌شده بی‌معنا شوند.

    فصل می‌گوید این تغییر باید **کنترل‌شده** باشد؛ سمتِ سرور جایی برای «تأیید
    می‌کنم» نیست، پس یا اجازه می‌دهیم یا نه. راهِ برگشت هست: کالای تازه بسازید.
    """
    if new_value == item.is_serial_tracked:
        return
    if has_stock_history(db, item.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"«{item.name}» گردشِ انباری دارد و «ثبت سریالی»‌اش عوض نمی‌شود؛ "
            "موجودیِ ثبت‌شده سریال ندارد و تغییرِ این تنظیم ردیابی را مبهم می‌کند. "
            "برای شروعِ ردیابیِ سریالی، کالای تازه تعریف کنید.",
        )


def row(db: Session, item: Item, *, default_account: Account | None = None) -> dict:
    """بخشِ «معینِ هزینه»ی ردیفِ فهرست (§۴۸).

    برای **کالا** خالی می‌ماند: بهای خرید به موجودیِ انبار می‌نشیند، نه به حسابِ
    هزینه — نشان‌دادنش کاربر را به اشتباه می‌انداخت.

    `default_account` برای فهرست است: حسابِ پیش‌فرض یک‌بار برای کلِ صفحه حل
    می‌شود، نه یک‌بار برای هر ردیف.
    """
    account = db.get(Account, item.expense_account_id) if item.expense_account_id else None
    is_default = account is None
    if item.is_service and account is None:
        account = default_account if default_account is not None else service_expense_account(db)
    if not item.is_service and item.expense_account_id is None:
        account = None
    return {
        "expense_account_id": item.expense_account_id,
        "expense_account_code": account.code if account else "",
        "expense_account_name": account.name if account else "",
        "expense_account_is_default": is_default,
    }


def default_expense_account_or_none(db: Session) -> Account | None:
    """حسابِ پیش‌فرضِ هزینه‌ی خدمت، **بدونِ ساختنش**.

    فهرستِ کالاها نباید عارضه‌ی جانبی داشته باشد: بازکردنِ صفحه‌ی کالاها نباید
    در چارتِ کسب‌وکاری که هنوز هیچ خدمتی نخریده حساب بسازد.
    """
    return db.query(Account).filter(Account.system_role == cc.SERVICE_EXPENSE).first()


# ───────────────────── انبارهای مرتبط و کنترلِ موجودی (§۲۴–§۳۳) ─────────────────────


def allowed_warehouse_ids(db: Session, item_id: UUID) -> set[UUID]:
    """انبارهایی که این کالا صریحاً در آن‌ها مجاز است.

    **مجموعه‌ی خالی یعنی «همه‌ی انبارها»** و نه «هیچ انباری» — یعنی رفتارِ امروزِ
    کوبیتا. تفسیرِ دیگرش هر کالای موجودی را یک‌شبه غیرقابل‌استفاده می‌کرد.
    """
    rows = db.query(ItemWarehouse.warehouse_id).filter(ItemWarehouse.item_id == item_id).all()
    return {warehouse_id for (warehouse_id,) in rows}


def default_warehouse_id(db: Session, item_id: UUID) -> UUID | None:
    """انبارِ پیش‌فرضِ کالا — **پیشنهادِ فرم، نه مالکیت** (§۳۲).

    `None` یعنی پیش‌فرضی انتخاب نشده، نه اینکه کالا جایی ندارد.
    """
    row = (
        db.query(ItemWarehouse.warehouse_id)
        .filter(ItemWarehouse.item_id == item_id, ItemWarehouse.is_default.is_(True))
        .first()
    )
    return row[0] if row else None


def assert_warehouse_allowed(db: Session, item: Item, warehouse_id: UUID | None) -> None:
    """§۲۹ — کالا فقط به انبارهای مرتبطش وارد می‌شود.

    سه استثنا، و هر سه عمدی:

    **فهرستِ خالی.** یعنی «همه‌ی انبارها» — رفتارِ امروز، پس هیچ کالای موجودی
    نمی‌شکند.

    **خدمت.** اصلاً وارد انبار نمی‌شود؛ محدودکردنش بی‌معناست (§۱۶).

    **انباری که کالا در آن موجودی دارد.** §۳۳ می‌گوید حذفِ رابطه نباید گذشته را
    پاک کند — و اگر خروج را هم ببندیم، کالا در انباری گیر می‌افتد که نه واردش
    می‌شود نه خارج. همان «سرگردانیِ موجودی» که فصلِ انبار منعش می‌کند.
    """
    if warehouse_id is None or item.is_service:
        return
    allowed = allowed_warehouse_ids(db, item.id)
    if not allowed or warehouse_id in allowed:
        return
    on_hand = (
        db.query(func.coalesce(func.sum(StockLedger.qty), 0))
        .filter(StockLedger.item_id == item.id, StockLedger.warehouse_id == warehouse_id)
        .scalar()
    )
    if Decimal(on_hand or 0) != 0:
        return
    warehouse = db.get(Warehouse, warehouse_id)
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        f"«{item.name}» در انبارِ «{warehouse.name if warehouse else warehouse_id}» مجاز نیست. "
        "اگر باید آن‌جا نگهداری شود، در تعریفِ کالا این انبار را به «انبارهای مرتبط» اضافه کنید.",
    )


def stock_limits(db: Session, item: Item, warehouse_id: UUID | None) -> tuple[Decimal, Decimal]:
    """حداقل و حداکثرِ مؤثر برای این کالا در این انبار (§۲۸).

    ردیفِ انبار اگر عددی داشته باشد مقدم است؛ وگرنه عددِ خودِ کالا — که سراسری
    است و همان رفتارِ `reorder_point`ِ امروز را دارد. فصل هیچ‌کدام را تحمیل
    نمی‌کند، پس هر دو لایه هست و هیچ‌کدام اجباری نیست.
    """
    item_min, item_max = Decimal(item.min_stock or 0), Decimal(item.max_stock or 0)
    if warehouse_id is None:
        return item_min, item_max
    row = (
        db.query(ItemWarehouse.min_stock, ItemWarehouse.max_stock)
        .filter(ItemWarehouse.item_id == item.id, ItemWarehouse.warehouse_id == warehouse_id)
        .first()
    )
    if row is None:
        return item_min, item_max
    row_min, row_max = row
    return (
        Decimal(row_min) if row_min is not None else item_min,
        Decimal(row_max) if row_max is not None else item_max,
    )


def set_warehouses(db: Session, item: Item, links: list[dict]) -> None:
    """فهرستِ انبارهای مرتبط را جایگزین می‌کند.

    **حذفِ یک انبار از فهرست هیچ حرکتِ انباری‌ای را پاک نمی‌کند (§۳۳).** این
    جدول فقط درباره‌ی *آینده* حرف می‌زند؛ کاردکس و موجودی جای دیگری زندگی
    می‌کنند و دست‌نخورده می‌مانند.
    """
    wanted = {}
    for link in links:
        warehouse_id = link.get("warehouse_id")
        if warehouse_id is None:
            continue
        if db.get(Warehouse, warehouse_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "انبار یافت نشد")
        wanted[warehouse_id] = link

    defaults = [link for link in wanted.values() if link.get("is_default")]
    if len(defaults) > 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "فقط یک انبار می‌تواند پیش‌فرض باشد"
        )

    existing = {row.warehouse_id: row for row in db.query(ItemWarehouse).filter(ItemWarehouse.item_id == item.id).all()}

    #: اول پیش‌فرض‌ها برداشته می‌شوند، بعد نشانده — وگرنه ایندکسِ یکتای «یک
    #: پیش‌فرض برای هر کالا» وسطِ جابه‌جایی می‌شکند.
    for row in existing.values():
        row.is_default = False
    db.flush()

    for warehouse_id, row in existing.items():
        if warehouse_id not in wanted:
            db.delete(row)

    for warehouse_id, link in wanted.items():
        row = existing.get(warehouse_id)
        if row is None:
            row = ItemWarehouse(item_id=item.id, warehouse_id=warehouse_id)
            db.add(row)
        row.is_default = bool(link.get("is_default"))
        row.min_stock = link.get("min_stock")
        row.max_stock = link.get("max_stock")
    db.flush()


def warehouse_rows(db: Session, item: Item) -> list[dict]:
    rows = (
        db.query(ItemWarehouse, Warehouse)
        .join(Warehouse, Warehouse.id == ItemWarehouse.warehouse_id)
        .filter(ItemWarehouse.item_id == item.id)
        .order_by(Warehouse.code)
        .all()
    )
    return [
        {
            "warehouse_id": link.warehouse_id,
            "warehouse_code": warehouse.code,
            "warehouse_name": warehouse.name,
            "is_default": link.is_default,
            "min_stock": link.min_stock,
            "max_stock": link.max_stock,
        }
        for link, warehouse in rows
    ]


# ───────────────────── گروه‌بندی و مشخصات (§۳۴–§۳۶) ─────────────────────


def sync_item_category(db: Session, item: Item) -> None:
    """`Item.category` را با نامِ گروه هم‌گام می‌کند.

    **تنها جای نوشتنِ آن ستون.** از این پس `category` پرتوِ نامِ گروه است، نه
    منبعِ حقیقت — نگه‌داشتنش عمدی است چون فروشگاه، گزارش‌ها و ورودِ گروهی همه
    آن را می‌خوانند.
    """
    if item.group_id is None:
        return
    group = db.get(ItemGroup, item.group_id)
    if group is not None:
        item.category = group.name


def group_get_or_create(db: Session, name: str) -> ItemGroup:
    """گروه را با نامش پیدا می‌کند و اگر نبود می‌سازد.

    برای مسیرهایی که هنوز دسته را به‌صورتِ نوشتار می‌دهند (ورودِ گروهی، بازار،
    بازیابیِ پشتیبان) — همان قاعده‌ای که واحد دارد: هر نوشتاری که از بیرون
    می‌آید یک رکورد می‌شود، نه یک رشته‌ی سرگردان.
    """
    name = (name or "").strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نامِ گروه نمی‌تواند خالی باشد")
    group = db.query(ItemGroup).filter(ItemGroup.name == name).first()
    if group is None:
        group = ItemGroup(name=name)
        db.add(group)
        db.flush()
    return group


def assert_group_usable(db: Session, group_id: UUID | None) -> None:
    if group_id is None:
        return
    group = db.get(ItemGroup, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "گروهِ کالا یافت نشد")
    if not group.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"گروهِ «{group.name}» بسته است و در تعریفِ تازه انتخاب نمی‌شود.",
        )


def set_attributes(db: Session, item: Item, values: list[dict]) -> None:
    """مقدارِ مشخصه‌های کالا را جایگزین می‌کند (§۳۵).

    مقدارِ خالی یعنی «این مشخصه را ندارد» و ردیفش پاک می‌شود — نگه‌داشتنِ ردیفِ
    تهی یعنی فهرستِ مشخصات پر از خطوطِ بی‌معنا شود.
    """
    wanted = {}
    for row in values:
        attribute_id = row.get("attribute_id")
        if attribute_id is None:
            continue
        if db.get(ItemAttribute, attribute_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "مشخصه یافت نشد")
        wanted[attribute_id] = (row.get("value") or "").strip()

    existing = {
        row.attribute_id: row
        for row in db.query(ItemAttributeValue).filter(ItemAttributeValue.item_id == item.id).all()
    }
    for attribute_id, row in existing.items():
        if attribute_id not in wanted or not wanted[attribute_id]:
            db.delete(row)
    for attribute_id, value in wanted.items():
        if not value:
            continue
        row = existing.get(attribute_id)
        if row is None:
            row = ItemAttributeValue(item_id=item.id, attribute_id=attribute_id)
            db.add(row)
        row.value = value
    db.flush()


def attribute_rows(db: Session, item: Item) -> list[dict]:
    rows = (
        db.query(ItemAttributeValue, ItemAttribute)
        .join(ItemAttribute, ItemAttribute.id == ItemAttributeValue.attribute_id)
        .filter(ItemAttributeValue.item_id == item.id)
        .order_by(ItemAttribute.name)
        .all()
    )
    return [
        {
            "attribute_id": value.attribute_id,
            "attribute_name": attribute.name,
            "value": value.value,
        }
        for value, attribute in rows
    ]
