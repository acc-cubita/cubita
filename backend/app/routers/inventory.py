from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.inventory import Contact, Item, StockAdjustment, StockLedger, Warehouse
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.inventory import (
    ContactIn,
    ContactOut,
    CreditStatusOut,
    ItemIn,
    ItemOut,
    ItemUpdateIn,
    LowStockRowOut,
    StockAdjustmentIn,
    StockAdjustmentOut,
    StockLevelOut,
    WarehouseIn,
    WarehouseOut,
    WarehouseUpdateIn,
)
from app.services.credit import get_credit_status
from app.services.inventory import post_stock_adjustment

router = APIRouter(tags=["inventory"])


@router.get("/api/warehouses", response_model=list[WarehouseOut])
def list_warehouses(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "view"))):
    return db.query(Warehouse).order_by(Warehouse.code).all()


@router.post("/api/warehouses", response_model=WarehouseOut, status_code=201)
def create_warehouse(
    data: WarehouseIn, db: Session = Depends(get_db), _=Depends(require_permission("inventory", "create"))
):
    warehouse = Warehouse(code=data.code, name=data.name)
    db.add(warehouse)
    db.flush()
    db.refresh(warehouse)
    return warehouse


@router.patch("/api/warehouses/{warehouse_id}", response_model=WarehouseOut)
def update_warehouse(
    warehouse_id: UUID,
    data: WarehouseUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    """ویرایشِ نام/فعال‌بودنِ انبار. کد ثابت می‌ماند (روی حرکاتِ انبار نشسته)."""
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "انبار یافت نشد")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(warehouse, key, value)
    db.flush()
    db.refresh(warehouse)
    return warehouse


@router.get("/api/contacts", response_model=Page[ContactOut])
def list_contacts(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("invoices", "view")),
):
    # نام یکتا نیست، پس id تساوی را می‌شکند. طرف‌حساب‌های سیستمی (مثلِ «فروشِ کارتیِ
    # گذری») از فهرستِ کاربر پنهان می‌مانند.
    query = db.query(Contact).filter(Contact.is_system.is_(False))
    items, next_cursor = paginate(query, [Contact.name, Contact.id], params, descending=False)
    return Page(items=items, next_cursor=next_cursor)


@router.post("/api/contacts", response_model=ContactOut, status_code=201)
def create_contact(
    data: ContactIn, db: Session = Depends(get_db), _=Depends(require_permission("invoices", "create"))
):
    contact = Contact(**data.model_dump())
    db.add(contact)
    db.flush()
    db.refresh(contact)
    return contact


@router.patch("/api/contacts/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: UUID,
    data: ContactIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "update")),
):
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "طرف حساب یافت نشد")
    for field, value in data.model_dump().items():
        setattr(contact, field, value)
    db.flush()
    db.refresh(contact)
    return contact


@router.get("/api/contacts/{contact_id}/credit", response_model=CreditStatusOut)
def contact_credit_status(
    contact_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    return get_credit_status(db, contact_id)


@router.get("/api/items", response_model=Page[ItemOut])
def list_items(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("inventory", "view")),
):
    # sku یکتاست، پس به‌تنهایی کلید امنی است
    items, next_cursor = paginate(db.query(Item), [Item.sku], params, descending=False)
    return Page(items=items, next_cursor=next_cursor)


@router.get("/api/items/by-barcode", response_model=ItemOut)
def item_by_barcode(
    code: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    """جست‌وجوی کالا با بارکد — برای اسکن در صندوقِ فروشگاهی."""
    item = db.query(Item).filter(Item.barcode == code.strip(), Item.is_active.is_(True)).first()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کالایی با این بارکد یافت نشد")
    return item


@router.post("/api/items", response_model=ItemOut, status_code=201)
def create_item(data: ItemIn, db: Session = Depends(get_db), _=Depends(require_permission("inventory", "create"))):
    item = Item(**data.model_dump())
    db.add(item)
    db.flush()
    db.refresh(item)
    return item


@router.patch("/api/items/{item_id}", response_model=ItemOut)
def update_item(
    item_id: UUID,
    data: ItemUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کالا یافت نشد")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.flush()
    db.refresh(item)
    return item


@router.delete("/api/items/{item_id}", status_code=204)
def delete_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "delete")),
):
    """حذفِ کاملِ کالا — فقط اگر در هیچ سند یا موجودی‌ای رد پا نداشته باشد.

    کالایی که در فاکتور، برگشت، پیش‌فاکتور، انبارگردانی، انتقال یا سطحِ موجودی استفاده
    شده نباید پاک شود؛ پاک‌کردنش اسنادِ تاریخی را می‌شکند. به‌جای بررسیِ دستیِ همه‌ی
    جدول‌های ارجاع‌دهنده (که هرکدام جا بیفتد یک نشتی است)، تلاشِ حذف داخل یک SAVEPOINT
    انجام می‌شود: قیدهای کلیدِ خارجیِ پایگاه‌داده مرجعِ حقیقت‌اند. اگر مانع شد، فقط همان
    SAVEPOINT برمی‌گردد (نه کلِ تراکنش و نه زمینه‌ی RLS) و پیامِ روشن داده می‌شود.
    """
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کالا یافت نشد")
    try:
        with db.begin_nested():
            db.delete(item)
            db.flush()
    except IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این کالا در سند یا موجودی استفاده شده و قابلِ حذف نیست؛ به‌جای حذف، آن را «غیرفعال» کنید.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/stock-adjustments", response_model=Page[StockAdjustmentOut])
def list_stock_adjustments(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("inventory", "view")),
):
    items, next_cursor = paginate(
        db.query(StockAdjustment), [StockAdjustment.adjustment_date, StockAdjustment.id], params
    )
    return Page(items=items, next_cursor=next_cursor)


@router.post("/api/stock-adjustments", response_model=StockAdjustmentOut, status_code=201)
def create_stock_adjustment(
    data: StockAdjustmentIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    return post_stock_adjustment(db, data, user)


@router.get("/api/stock", response_model=list[StockLevelOut])
def current_stock(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "view"))):
    """موجودیِ زنده به تفکیکِ کالا/انبار، همراه با بهای میانگین و ارزشِ ریالیِ هر ردیف.

    ارزش = موجودی × `average_cost`ِ کالا — همان مبنایی که حسابِ «موجودی کالا» با آن
    نگه‌داری می‌شود، پس جمعِ ارزش‌ها با ماندهٔ آن حساب هم‌خوان است.
    """
    rows = (
        db.query(
            Item.id.label("item_id"),
            Item.sku.label("item_sku"),
            Item.name.label("item_name"),
            Item.average_cost.label("unit_cost"),
            Warehouse.id.label("warehouse_id"),
            Warehouse.name.label("warehouse_name"),
            func.sum(StockLedger.qty).label("qty"),
        )
        .join(StockLedger, StockLedger.item_id == Item.id)
        .join(Warehouse, Warehouse.id == StockLedger.warehouse_id)
        .group_by(Item.id, Item.sku, Item.name, Item.average_cost, Warehouse.id, Warehouse.name)
        .having(func.sum(StockLedger.qty) != 0)
    ).all()
    out: list[StockLevelOut] = []
    for r in rows:
        qty = r.qty or 0
        unit_cost = r.unit_cost or 0
        out.append(
            StockLevelOut(
                item_id=r.item_id,
                item_sku=r.item_sku,
                item_name=r.item_name,
                warehouse_id=r.warehouse_id,
                warehouse_name=r.warehouse_name,
                qty=qty,
                unit_cost=unit_cost,
                stock_value=qty * unit_cost,
            )
        )
    return out


@router.get("/api/stock/low", response_model=list[LowStockRowOut])
def low_stock(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "view"))):
    """کالاهایی که موجودیِ کلشان به/زیرِ نقطه‌ی سفارش رسیده — برای هشدارِ سفارشِ مجدد.

    موجودی روی همه‌ی انبارها جمع می‌شود (نقطه‌ی سفارش خصیصه‌ی کالاست، نه انبار). فقط
    کالاهای فعالِ غیرخدماتی با `reorder_point > 0` سنجیده می‌شوند.
    """
    on_hand = dict(
        db.query(StockLedger.item_id, func.coalesce(func.sum(StockLedger.qty), 0))
        .group_by(StockLedger.item_id)
        .all()
    )
    items = (
        db.query(Item)
        .filter(Item.is_service.is_(False), Item.is_active.is_(True), Item.reorder_point > 0)
        .all()
    )
    from decimal import Decimal

    rows: list[LowStockRowOut] = []
    for item in items:
        qty = Decimal(on_hand.get(item.id, 0))
        reorder = Decimal(item.reorder_point)
        if qty <= reorder:
            rows.append(
                LowStockRowOut(
                    item_id=item.id,
                    sku=item.sku,
                    name=item.name,
                    unit=item.unit,
                    qty_on_hand=qty,
                    reorder_point=reorder,
                    shortfall=max(reorder - qty, Decimal(0)),
                )
            )
    # بحرانی‌ترین اول: بیشترین کمبود بالاتر
    rows.sort(key=lambda r: r.shortfall, reverse=True)
    return rows
