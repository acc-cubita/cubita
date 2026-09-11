from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.inventory import Contact, Item, ItemWarehouse, UnitOfMeasure, StockAdjustment, StockLedger, Warehouse
from app.models.user import User
from decimal import Decimal

from app.models.company import ContactAddress, ContactChannel
from app.services import tafsili
from app.services.onboarding import get_opening_status
from app.pagination import Page, PageParams, paginate
from app.services import items as items_svc
from app.services import units as units_svc
from app.services import warehouses as warehouses_svc
from app.schemas.inventory import (
    ContactAddressIn,
    ContactAddressOut,
    ContactChannelIn,
    ContactChannelOut,
    ContactIn,
    ContactOut,
    CreditStatusOut,
    ItemIn,
    ItemOut,
    ItemWarehouseIn,
    UnitIn,
    UnitOut,
    UnitUpdateIn,
    ItemUpdateIn,
    LowStockRowOut,
    OverStockRowOut,
    StockAdjustmentIn,
    StockAdjustmentOut,
    StockLevelOut,
    WarehouseIn,
    WarehouseOut,
    WarehouseStockPositionOut,
    WarehouseUpdateIn,
)
from app.services.credit import get_credit_status
from app.services.inventory import post_stock_adjustment

router = APIRouter(tags=["inventory"])


@router.get("/api/warehouses", response_model=list[WarehouseOut])
def list_warehouses(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "view"))):
    """فهرستِ انبارها با کد و عنوانِ حسابِ معینشان (§۲۹)."""
    return [
        warehouses_svc.row(db, w) for w in db.query(Warehouse).order_by(Warehouse.code).all()
    ]


@router.post("/api/warehouses", response_model=WarehouseOut, status_code=201)
def create_warehouse(
    data: WarehouseIn, db: Session = Depends(get_db), _=Depends(require_permission("inventory", "create"))
):
    """**ساختِ انبار رویدادِ مالی نیست (§۳۲).**

    نه سندی می‌زند، نه موجودی می‌سازد، نه حسابِ تازه‌ای در چارت درست می‌کند
    (§۱۲) — فقط به حسابی که از قبل هست اشاره می‌کند.
    """
    warehouses_svc.assert_postable_account(db, data.gl_account_id)
    warehouse = Warehouse(**data.model_dump())
    db.add(warehouse)
    db.flush()
    db.refresh(warehouse)
    return warehouses_svc.row(db, warehouse)


@router.patch("/api/warehouses/{warehouse_id}", response_model=WarehouseOut)
def update_warehouse(
    warehouse_id: UUID,
    data: WarehouseUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    """ویرایشِ مشخصات/نگاشت/فعال‌بودنِ انبار. کد ثابت می‌ماند (روی حرکاتِ انبار نشسته).

    **تغییرِ عنوان و مسئول و آدرس هیچ حرکتِ انباری را عوض نمی‌کند (§۳۵ §۳۶)** —
    اسناد به `warehouse_id` وصل‌اند نه به نام.

    **و تغییرِ نگاشتِ حساب، سندهای گذشته را بازنویسی نمی‌کند (§۳۴).** حساب در
    لحظه‌ی ثبت روی ردیفِ سند می‌نشیند و سند تغییرناپذیر است؛ پس گذشته همان‌طور
    می‌ماند که بود و فقط ثبت‌های آینده نگاشتِ تازه را می‌گیرند.
    """
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "انبار یافت نشد")
    changes = data.model_dump(exclude_unset=True)
    if "gl_account_id" in changes:
        warehouses_svc.assert_postable_account(db, changes["gl_account_id"])
    #: §۱۷ — کالا در انبارِ غیرفعال گیر می‌افتد: نه خارج می‌شود نه وارد.
    if changes.get("is_active") is False and warehouse.is_active:
        warehouses_svc.assert_can_deactivate(db, warehouse)
    for key, value in changes.items():
        setattr(warehouse, key, value)
    db.flush()
    db.refresh(warehouse)
    return warehouses_svc.row(db, warehouse)


@router.get("/api/warehouses/{warehouse_id}/stock-positions", response_model=WarehouseStockPositionOut)
def warehouse_stock_positions(
    warehouse_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    """کالاهای دارای موجودیِ غیرصفر در این انبار (§۱۷).

    رابط پیش از غیرفعال‌کردن این را می‌پرسد تا بتواند **قبل** از خطا بگوید چه
    چیزی سرِ راه است.
    """
    positions = warehouses_svc.stock_positions(db, warehouse_id)
    names = {
        i.id: i.name
        for i in db.query(Item).filter(Item.id.in_([p["item_id"] for p in positions])).all()
    } if positions else {}
    return {
        "item_count": len(positions),
        "items": [
            {"item_id": str(p["item_id"]), "item_name": names.get(p["item_id"], "—"), "qty": str(p["qty"])}
            for p in positions
        ],
    }


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


def _assert_company_refs(db: Session, data: ContactIn) -> None:
    """گروه و محلِ انتخاب‌شده باید واقعاً وجود داشته باشند.

    بدونِ این بررسی، شناسه‌ی نامعتبر تا قیدِ کلیدِ خارجی می‌رفت و کاربر به‌جای پیامِ
    روشن یک خطای ۵۰۰ می‌دید. (RLS هم ردیفِ مستأجرِ دیگر را نامرئی می‌کند، پس همین‌جا
    «معتبر نیست» درست‌ترین پاسخ است.)
    """
    from app.models.company import ContactGroup, GeoLocation

    if data.group_id is not None and db.get(ContactGroup, data.group_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "گروهِ انتخاب‌شده معتبر نیست")
    if data.geo_location_id is not None and db.get(GeoLocation, data.geo_location_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "محلِ جغرافیاییِ انتخاب‌شده معتبر نیست")


#: فیلدهایی که ورودی دارد ولی ستونِ `contacts` نیستند — سرویسِ تفصیلی مصرفشان می‌کند.
_TAFSILI_INPUT = ("tafsili_code", "tafsili_title", "tafsili_title2")


def _contact_out(contact: Contact) -> dict:
    """طرف‌حساب + کد و عنوانِ تفصیلی‌اش، خوانده از خودِ تفصیلی.

    کد و عنوان روی طرف‌حساب *ذخیره نمی‌شوند*؛ هر بار از `analytic_accounts` خوانده
    می‌شوند تا اگر کسی تفصیلی را از صفحه‌ی «تفصیلی سایر» عوض کرد، این‌جا هم همان
    دیده شود. دو نمای یک داده نمی‌سازیم.
    """
    row = {c.name: getattr(contact, c.name) for c in Contact.__table__.columns}
    analytic = contact.analytic
    row["tafsili_code"] = analytic.code if analytic else None
    row["tafsili_title"] = analytic.name if analytic else None
    row["tafsili_title2"] = analytic.name2 if analytic else ""
    return row


@router.get("/api/contacts/tafsili-requirement", response_model=dict)
def contact_tafsili_requirement(
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    """آیا فرمِ طرف حساب باید کدِ تفصیلی بخواهد — و کدِ پیشنهادی چیست.

    از سطحِ اجبارِ تفصیلی (تنظیمات ← شخصی‌سازی) می‌آید: `required` در «اجباری»،
    `optional` در «ترکیبی»، `hidden` در «شناور».
    """
    requirement = tafsili.contact_tafsili_requirement(db)
    return {
        "requirement": requirement,
        "mode": tafsili.get_mode(db),
        "suggested_code": (
            tafsili.suggest_contact_tafsili_code(db) if requirement != "hidden" else None
        ),
    }


@router.get("/api/contacts/tafsili-title-taken", response_model=dict)
def contact_tafsili_title_taken(
    title: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    """آیا این عنوانِ تفصیلی از قبل هست؟ — فرم با آن قرمز می‌کند، نه اینکه رد کند.

    عنوانِ تکراری واقعاً ممکن است (دو نفر هم‌نام)، ولی کاربر باید بداند تا چیزی
    به آن اضافه کند؛ وگرنه در فهرستِ تفصیلی دو ردیفِ یکسان می‌ماند.
    """
    return {"taken": tafsili.tafsili_title_taken(db, title)}


#: چهار فیلدِ مانده‌ی اول دوره — قفل روی همین‌هاست، نه روی کلِ طرف‌حساب.
_OPENING_FIELDS = ("opening_ar_amount", "opening_ar_side", "opening_ap_amount", "opening_ap_side")


def _assert_opening_unlocked(
    db: Session,
    data: ContactIn,
    current: Contact | None = None,
    *,
    given: set[str] | None = None,
) -> None:
    """مانده‌ی اول دوره پس از ثبتِ سندِ افتتاحیه قفل است.

    بدونِ این قفل، عددِ روی طرف‌حساب و ردیفی که در سندِ افتتاحیه نشسته از هم جدا
    می‌افتند و دو گزارش دو حقیقتِ متفاوت می‌گویند. اصلاحِ مانده پس از افتتاحیه کارِ
    سندِ اصلاحی است، نه ویرایشِ بی‌صدای یک فیلد.

    `given` فیلدهایی است که واقعاً در درخواست آمده‌اند. در ویرایشِ جزئی، فیلدی که
    نیامده یعنی «دست نزن» نه «صفر کن»، پس مقدارِ فعلی مبنا می‌ماند — وگرنه ویرایشِ
    یک شماره‌تلفن، طرف‌حسابی را که مانده‌ی افتتاحیه دارد ۴۰۹ می‌کرد.
    """

    def wanted_of(name: str):
        if given is None or name in given or current is None:
            return getattr(data, name)
        return getattr(current, name)

    wanted = tuple(wanted_of(name) for name in _OPENING_FIELDS)
    if current is not None:
        now = (
            Decimal(current.opening_ar_amount), current.opening_ar_side,
            Decimal(current.opening_ap_amount), current.opening_ap_side,
        )
        if (Decimal(wanted[0]), wanted[1], Decimal(wanted[2]), wanted[3]) == now:
            return
    elif not wanted[0] and not wanted[2]:
        return

    if get_opening_status(db)["exists"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "سندِ افتتاحیه ثبت شده و مانده‌ی اول دوره دیگر تغییر نمی‌کند؛ "
            "اصلاحش با سندِ حسابداری انجام می‌شود.",
        )


@router.post("/api/contacts", response_model=ContactOut, status_code=201)
def create_contact(
    data: ContactIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    _assert_company_refs(db, data)
    _assert_opening_unlocked(db, data)
    fields = data.model_dump()
    analytic = tafsili.resolve_contact_analytic(
        db,
        user,
        code=fields.pop("tafsili_code"),
        title=fields.pop("tafsili_title"),
        title2=fields.pop("tafsili_title2"),
        fallback_title=data.name,
    )
    contact = Contact(**fields, analytic_id=analytic.id if analytic else None)
    db.add(contact)
    db.flush()
    db.refresh(contact)
    return _contact_out(contact)


@router.patch("/api/contacts/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: UUID,
    data: ContactIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "update")),
):
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "طرف حساب یافت نشد")
    _assert_company_refs(db, data)
    #: **ویرایشِ جزئی، نه جایگزینیِ کامل.** فرمِ ساده‌ی «طرف حساب»ِ ماژولِ فروش فقط
    #: یک مشت فیلدِ پایه می‌فرستد؛ با `model_dump()`ِ کامل، هر چیزی که نفرستاده بود
    #: به پیش‌فرضِ اسکیما برمی‌گشت — نقشِ واسطه و سهامدار پاک، مانده‌ی اول دوره صفر،
    #: مشخصاتِ شخصی خالی. PATCH یعنی «همین‌ها را عوض کن»، نه «بقیه را دور بریز».
    fields = data.model_dump(exclude_unset=True)
    given = set(fields)
    _assert_opening_unlocked(db, data, contact, given=given)
    analytic = tafsili.resolve_contact_analytic(
        db,
        user,
        code=fields.pop("tafsili_code", None),
        title=fields.pop("tafsili_title", None),
        title2=fields.pop("tafsili_title2", None),
        #: نامِ طرف‌حساب فقط وقتی جایگزینِ عنوانِ تفصیلی می‌شود که کاربر خودِ عنوان را
        #: فرستاده و خالی گذاشته باشد. وگرنه عنوانی که دستی انتخاب شده بود با هر
        #: ویرایشِ ساده‌ی نام بازنویسی می‌شد.
        fallback_title=data.name if "tafsili_title" in given else "",
        existing_id=contact.analytic_id,
    )
    for field, value in fields.items():
        setattr(contact, field, value)
    #: تفصیلیِ موجود هرگز این‌جا برداشته نمی‌شود — فقط جایگزین می‌شود. عوض‌کردنِ
    #: سطحِ اجبار نباید داده‌ای را که قبلاً ثبت شده پاک کند.
    if analytic is not None:
        contact.analytic_id = analytic.id
    db.flush()
    db.refresh(contact)
    return _contact_out(contact)


@router.get("/api/contacts/{contact_id}/channels", response_model=list[ContactChannelOut])
def list_contact_channels(
    contact_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    #: تلفن‌ها و نشانی‌های *اضافه*. اصلی روی خودِ طرف‌حساب است و این‌جا نمی‌آید.
    return (
        db.query(ContactChannel)
        .filter(ContactChannel.contact_id == contact_id)
        .order_by(ContactChannel.kind, ContactChannel.label)
        .all()
    )


@router.post("/api/contacts/{contact_id}/channels", response_model=ContactChannelOut, status_code=201)
def add_contact_channel(
    contact_id: UUID,
    data: ContactChannelIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "update")),
):
    if db.get(Contact, contact_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "طرف حساب یافت نشد")
    row = ContactChannel(contact_id=contact_id, **data.model_dump())
    db.add(row)
    db.flush()
    if row.is_primary:
        _demote_other_primaries(db, ContactChannel, contact_id, keep_id=row.id)
    db.flush()
    db.refresh(row)
    return row


@router.delete("/api/contacts/{contact_id}/channels/{channel_id}", status_code=204)
def delete_contact_channel(
    contact_id: UUID,
    channel_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "update")),
):
    row = db.get(ContactChannel, channel_id)
    if row is None or row.contact_id != contact_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کانال یافت نشد")
    db.delete(row)
    db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _demote_other_primaries(db: Session, model, contact_id: UUID, keep_id: UUID | None = None) -> None:
    """«اصلی» در هر طرف‌حساب فقط یکی است.

    به‌جای رد کردنِ ردیفِ دوم، ردیفِ قبلی از اصلی‌بودن درمی‌آید — چون نیتِ کاربری که
    «اصلی» را روی شماره‌ی تازه می‌زند روشن است و مجبورکردنش به برداشتنِ دستیِ تیکِ
    قبلی فقط یک مرحله‌ی اضافه است.
    """
    query = db.query(model).filter(model.contact_id == contact_id, model.is_primary.is_(True))
    if keep_id is not None:
        query = query.filter(model.id != keep_id)
    for row in query:
        row.is_primary = False


@router.get("/api/contacts/{contact_id}/addresses", response_model=list[ContactAddressOut])
def list_contact_addresses(
    contact_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    return (
        db.query(ContactAddress)
        .filter(ContactAddress.contact_id == contact_id)
        .order_by(ContactAddress.is_primary.desc(), ContactAddress.address_type)
        .all()
    )


@router.post("/api/contacts/{contact_id}/addresses", response_model=ContactAddressOut, status_code=201)
def add_contact_address(
    contact_id: UUID,
    data: ContactAddressIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "update")),
):
    if db.get(Contact, contact_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "طرف حساب یافت نشد")
    row = ContactAddress(contact_id=contact_id, **data.model_dump())
    db.add(row)
    db.flush()
    if row.is_primary:
        _demote_other_primaries(db, ContactAddress, contact_id, keep_id=row.id)
    db.flush()
    db.refresh(row)
    return row


@router.delete("/api/contacts/{contact_id}/addresses/{address_id}", status_code=204)
def delete_contact_address(
    contact_id: UUID,
    address_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "update")),
):
    row = db.get(ContactAddress, address_id)
    if row is None or row.contact_id != contact_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "نشانی یافت نشد")
    db.delete(row)
    db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/contacts/{contact_id}/credit", response_model=CreditStatusOut)
def contact_credit_status(
    contact_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    return get_credit_status(db, contact_id)


def _item_out(db: Session, item: Item, default_account=None) -> dict:
    """ردیفِ کالا + نگاشتِ حسابِ هزینه، واحدها و انبارهای مرتبط."""
    links = items_svc.warehouse_rows(db, item)
    return {
        **ItemOut.model_validate(item).model_dump(),
        **items_svc.row(db, item, default_account=default_account),
        **units_svc.row(db, item),
        "warehouses": links,
        "default_warehouse_id": next(
            (link["warehouse_id"] for link in links if link["is_default"]), None
        ),
    }


def _apply_units(db: Session, item: Item, fields: dict) -> None:
    """واحدها را حل و اعتبارسنجی می‌کند و `Item.unit` را هم‌گام نگه می‌دارد.

    اگر `primary_unit_id` نیامده باشد، از نوشتارِ `unit` ساخته/پیدا می‌شود —
    این‌طور مسیرهای قدیمی (ورودِ گروهی، بازار، بازیابیِ پشتیبان) نمی‌شکنند و
    متنِ آزاد هم دیگر سرگردان نمی‌ماند (§۱۹).
    """
    if item.primary_unit_id is None:
        item.primary_unit_id = units_svc.get_or_create(db, item.unit).id
    elif "primary_unit_id" in fields:
        units_svc.assert_usable(db, item.primary_unit_id)
    if fields.get("secondary_unit_id") is not None:
        units_svc.assert_usable(db, item.secondary_unit_id)
    units_svc.assert_conversion(item)
    units_svc.sync_item_unit(db, item)


# ──────────────────────────── واحدهای سنجش (§۱۷–§۲۳) ────────────────────────────
#
# تا امروز واحد یک `String(20)`ِ آزاد روی کالا بود، پس «کیلوگرم» و «كيلوگرم» دو
# واحدِ متفاوت بودند و نگاشتِ کدِ واحدِ مؤدیان — که روی نوشتار کلید می‌خورد —
# برای هر املا جدا لازم می‌شد.


def _unit_out(db: Session, unit: UnitOfMeasure) -> dict:
    used = (
        db.query(Item.id)
        .filter((Item.primary_unit_id == unit.id) | (Item.secondary_unit_id == unit.id))
        .count()
    )
    return {**UnitOut.model_validate(unit).model_dump(), "item_count": used}


@router.get("/api/units", response_model=list[UnitOut])
def list_units(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "view"))):
    units = db.query(UnitOfMeasure).order_by(UnitOfMeasure.name).all()
    return [_unit_out(db, unit) for unit in units]


@router.post("/api/units", response_model=UnitOut, status_code=201)
def create_unit(
    data: UnitIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "create")),
):
    if db.query(UnitOfMeasure).filter(UnitOfMeasure.name == data.name).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"واحدِ «{data.name}» از قبل تعریف شده است.")
    unit = UnitOfMeasure(**data.model_dump())
    db.add(unit)
    db.flush()
    db.refresh(unit)
    return _unit_out(db, unit)


@router.patch("/api/units/{unit_id}", response_model=UnitOut)
def update_unit(
    unit_id: UUID,
    data: UnitUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    unit = units_svc.resolve(db, unit_id)
    fields = data.model_dump(exclude_unset=True)
    if "name" in fields:
        clash = (
            db.query(UnitOfMeasure)
            .filter(UnitOfMeasure.name == fields["name"], UnitOfMeasure.id != unit.id)
            .first()
        )
        if clash is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"واحدِ «{fields['name']}» از قبل تعریف شده است."
            )
    if fields.get("is_active") is False:
        units_svc.assert_can_deactivate(db, unit)
    for key, value in fields.items():
        setattr(unit, key, value)
    db.flush()
    #: تغییرِ نامِ واحد باید روی کالاهایی که رویش نشسته‌اند هم دیده شود — وگرنه
    #: `Item.unit` و واحدِ واقعی از هم جدا می‌افتند و بسته‌ی مؤدیان نامِ قدیمی را
    #: می‌فرستد.
    if "name" in fields:
        for item in db.query(Item).filter(Item.primary_unit_id == unit.id).all():
            item.unit = unit.name
        db.flush()
    db.refresh(unit)
    return _unit_out(db, unit)


@router.delete("/api/units/{unit_id}", status_code=204)
def delete_unit(
    unit_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "delete")),
):
    """§۴۹ — واحدِ استفاده‌نشده حذف می‌شود؛ استفاده‌شده غیرفعال.

    مثلِ کالا، مرجعِ حقیقت قیدهای کلیدِ خارجیِ پایگاه‌داده‌اند نه شمارشِ دستی.
    """
    unit = units_svc.resolve(db, unit_id)
    try:
        with db.begin_nested():
            db.delete(unit)
            db.flush()
    except IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"واحدِ «{unit.name}» روی کالایی نشسته و حذف نمی‌شود؛ به‌جای حذف، غیرفعالش کنید.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/items", response_model=Page[ItemOut])
def list_items(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("inventory", "view")),
):
    # sku یکتاست، پس به‌تنهایی کلید امنی است
    items, next_cursor = paginate(db.query(Item), [Item.sku], params, descending=False)
    #: حسابِ پیش‌فرض یک‌بار برای کلِ صفحه حل می‌شود، نه یک‌بار برای هر ردیف.
    default_account = items_svc.default_expense_account_or_none(db)
    return Page(
        items=[_item_out(db, item, default_account) for item in items],
        next_cursor=next_cursor,
    )


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


def _assert_sku_free(db: Session, sku: str, exclude_id: UUID | None = None) -> None:
    """§۴ — کد قابلِ اصلاح است، ولی دو کالا نباید یک کد بگیرند.

    بازتابِ نرمِ `uq_items_tenant_sku`، تا کاربر پیامِ فارسی ببیند نه خطای خامِ
    یکتاییِ پایگاه‌داده. ایندکس همچنان پشتیبانِ نهایی است.
    """
    q = db.query(Item.id, Item.name).filter(Item.sku == sku)
    if exclude_id is not None:
        q = q.filter(Item.id != exclude_id)
    dup = q.first()
    if dup is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"کدِ «{sku}» قبلاً برای کالای «{dup.name}» ثبت شده است.",
        )


def _assert_barcode_free(db: Session, barcode: str | None, exclude_id: UUID | None = None) -> None:
    """اگر بارکد پرشده باشد و کالای دیگری همان را داشته باشد، خطای روشن می‌دهد.

    بازتابِ نرمِ ایندکسِ یکتای `uq_items_tenant_barcode` — تا کاربر به‌جای خطای خامِ
    یکتاییِ پایگاه‌داده پیامِ فارسیِ روشن ببیند. ایندکس همچنان پشتیبانِ نهایی است.
    """
    if not barcode:
        return
    q = db.query(Item.id, Item.name).filter(Item.barcode == barcode)
    if exclude_id is not None:
        q = q.filter(Item.id != exclude_id)
    dup = q.first()
    if dup is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"این بارکد قبلاً برای کالای «{dup.name}» ثبت شده است؛ هر بارکد فقط برای یک کالا مجاز است.",
        )


@router.post("/api/items", response_model=ItemOut, status_code=201)
def create_item(data: ItemIn, db: Session = Depends(get_db), _=Depends(require_permission("inventory", "create"))):
    _assert_barcode_free(db, data.barcode)
    #: §۱۵ — حسابِ نگاشت باید سند بپذیرد و نقشِ ماژولِ دیگری نباشد؛ وگرنه دو
    #: موتور روی یک حساب می‌نویسند با دو معنی.
    items_svc.assert_expense_account(db, data.expense_account_id)
    fields = data.model_dump()
    links = fields.pop("warehouses", [])
    item = Item(**fields)
    db.add(item)
    db.flush()
    items_svc.set_warehouses(db, item, links)
    _apply_units(db, item, fields)
    db.flush()
    db.refresh(item)
    return _item_out(db, item)


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
    fields = data.model_dump(exclude_unset=True)
    if "barcode" in fields:
        _assert_barcode_free(db, fields["barcode"], exclude_id=item.id)
    if "sku" in fields:
        _assert_sku_free(db, fields["sku"], exclude_id=item.id)
    if "expense_account_id" in fields:
        items_svc.assert_expense_account(db, fields["expense_account_id"])
    if "is_serial_tracked" in fields:
        #: §۹ — این ویژگی ساختاری است؛ عوض‌کردنش پس از گردشِ انباری موجودیِ
        #: قدیمی را مبهم می‌کند.
        items_svc.assert_serial_toggle_allowed(db, item, fields["is_serial_tracked"])
    #: `None` یعنی «دست نزن»؛ فهرستِ خالی یعنی «همه‌ی انبارها» (§۲۹).
    links = fields.pop("warehouses", None)
    for key, value in fields.items():
        setattr(item, key, value)
    if links is not None:
        items_svc.set_warehouses(db, item, links)
    _apply_units(db, item, fields)
    db.flush()
    db.refresh(item)
    return _item_out(db, item)


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
    #: §۲۵ — حداقلِ موجودی هم مثلِ نقطه‌ی سفارش سیگنال می‌سازد. دو آستانه‌ی جدا
    #: هستند و `trigger` می‌گوید کدام‌یک این ردیف را آورده؛ یکی‌کردنشان یعنی
    #: کاربر نفهمد چرا هشدار گرفته.
    items = (
        db.query(Item)
        .filter(
            Item.is_service.is_(False),
            Item.is_active.is_(True),
            (Item.reorder_point > 0) | (Item.min_stock > 0),
        )
        .all()
    )
    from decimal import Decimal

    rows: list[LowStockRowOut] = []
    for item in items:
        qty = Decimal(on_hand.get(item.id, 0))
        reorder = Decimal(item.reorder_point or 0)
        minimum = Decimal(item.min_stock or 0)
        threshold, trigger = (
            (reorder, "reorder") if reorder >= minimum else (minimum, "min")
        )
        if threshold > 0 and qty <= threshold:
            rows.append(
                LowStockRowOut(
                    item_id=item.id,
                    sku=item.sku,
                    name=item.name,
                    unit=item.unit,
                    qty_on_hand=qty,
                    reorder_point=reorder,
                    min_stock=minimum,
                    trigger=trigger,
                    shortfall=max(threshold - qty, Decimal(0)),
                )
            )
    # بحرانی‌ترین اول: بیشترین کمبود بالاتر
    rows.sort(key=lambda r: r.shortfall, reverse=True)
    return rows


@router.get("/api/stock/over", response_model=list[OverStockRowOut])
def over_stock(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "view"))):
    """§۲۶ — کالاهایی که موجودیشان از حداکثر گذشته.

    **سدِ تراکنش نیست.** حداکثرِ موجودی جلوی ورودِ کالا را نمی‌گیرد؛ فصل صریح
    است که این داده‌ی برنامه‌ریزی است، نه قاعده‌ی مسدودکننده. این فهرست فقط
    می‌گوید کجا مازاد داریم.
    """
    from decimal import Decimal

    on_hand = dict(
        db.query(StockLedger.item_id, func.coalesce(func.sum(StockLedger.qty), 0))
        .group_by(StockLedger.item_id)
        .all()
    )
    items = (
        db.query(Item)
        .filter(Item.is_service.is_(False), Item.is_active.is_(True), Item.max_stock > 0)
        .all()
    )
    rows: list[OverStockRowOut] = []
    for item in items:
        qty = Decimal(on_hand.get(item.id, 0))
        maximum = Decimal(item.max_stock)
        if qty > maximum:
            rows.append(
                OverStockRowOut(
                    item_id=item.id,
                    sku=item.sku,
                    name=item.name,
                    unit=item.unit,
                    qty_on_hand=qty,
                    max_stock=maximum,
                    excess=qty - maximum,
                )
            )
    rows.sort(key=lambda r: r.excess, reverse=True)
    return rows
