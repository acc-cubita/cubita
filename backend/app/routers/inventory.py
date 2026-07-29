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
    StockAdjustmentIn,
    StockAdjustmentOut,
    StockLevelOut,
    WarehouseIn,
    WarehouseOut,
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


@router.get("/api/contacts", response_model=Page[ContactOut])
def list_contacts(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("invoices", "view")),
):
    # نام یکتا نیست، پس id تساوی را می‌شکند
    items, next_cursor = paginate(db.query(Contact), [Contact.name, Contact.id], params, descending=False)
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
    rows = (
        db.query(
            Item.id.label("item_id"),
            Item.sku.label("item_sku"),
            Item.name.label("item_name"),
            Warehouse.id.label("warehouse_id"),
            Warehouse.name.label("warehouse_name"),
            func.sum(StockLedger.qty).label("qty"),
        )
        .join(StockLedger, StockLedger.item_id == Item.id)
        .join(Warehouse, Warehouse.id == StockLedger.warehouse_id)
        .group_by(Item.id, Item.sku, Item.name, Warehouse.id, Warehouse.name)
        .having(func.sum(StockLedger.qty) != 0)
    ).all()
    return [StockLevelOut.model_validate(row, from_attributes=True) for row in rows]
