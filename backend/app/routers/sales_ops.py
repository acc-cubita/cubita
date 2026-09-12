"""اندپوینت‌های عملیاتِ ماژولِ فروش.

مجوزها روی ماژولِ `sales` می‌نشینند، جز اعلامیه‌ی بدهکار/بستانکار که سند حسابداری
می‌زند و مثلِ ابطالِ فاکتور مجوزِ سنگین‌تری می‌خواهد.
"""
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import require_permission
from app.models.advanced_inventory import PriceList, PriceListItem
from app.models.inventory import Contact
from app.models.invoices import SalesInvoice
from app.models.sales_ops import (
    CommissionRule,
    CommissionRun,
    CreditDebitNote,
    CustomsDeclaration,
    DiscountItemGroup,
    DiscountItemGroupMember,
    PricingFactor,
    ProductBundle,
    ProductBundleLine,
    SaleType,
)
from app.models.user import User
from app.schemas.sales_ops import (
    CloseInvoicesIn,
    CloseInvoicesOut,
    CommissionPreviewOut,
    CommissionRuleIn,
    CommissionRuleOut,
    CommissionRunIn,
    CommissionRunOut,
    CustomsIn,
    CustomsOut,
    DiscountGroupIn,
    DiscountGroupOut,
    NoteIn,
    NoteOut,
    PriceAnnouncementIn,
    PriceAnnouncementOut,
    PricingFactorIn,
    PricingFactorOut,
    PricingSuggestionOut,
    ProductBundleIn,
    ProductBundleOut,
    SaleTypeIn,
    SaleTypeOut,
    VoidNoteIn,
)
from app.services import sales_ops as svc

router = APIRouter(prefix="/api/sales-ops", tags=["sales-ops"])

_view = require_permission("sales", "view")
_create = require_permission("sales", "create")
_update = require_permission("sales", "update")


def _get_or_404(db: Session, model, obj_id: UUID, label: str):
    obj = db.query(model).filter(model.id == obj_id).first()
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} پیدا نشد")
    return obj


def _assert_name_free(db: Session, model, name: str, label: str, *, skip_id: UUID | None = None) -> None:
    """نامِ تکراری باید ۴۰۹ بدهد، نه ۵۰۰.

    قیدِ یکتای (مستأجر، نام) در دیتابیس هست و کار می‌کند — ولی خطای خامش به کاربر
    «خطای داخلی سرور» نشان می‌داد، که هم ترسناک است هم بی‌فایده. اینجا پیش از درج
    بررسی می‌شود تا پیام بگوید واقعاً چه شده.
    """
    q = db.query(model).filter(model.name == name)
    if skip_id is not None:
        q = q.filter(model.id != skip_id)
    if q.first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{label} با این نام از قبل هست")


# ───────────────────────────── نوعِ فروش ─────────────────────────────


@router.get("/sale-types", response_model=list[SaleTypeOut])
def list_sale_types(db: Session = Depends(get_db), _=Depends(_view)):
    return db.query(SaleType).order_by(SaleType.name).all()


@router.post("/sale-types", response_model=SaleTypeOut, status_code=201)
def create_sale_type(data: SaleTypeIn, db: Session = Depends(get_db), _=Depends(_create)):
    _assert_name_free(db, SaleType, data.name, "نوعِ فروش")
    row = SaleType(**data.model_dump())
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


@router.patch("/sale-types/{type_id}", response_model=SaleTypeOut)
def update_sale_type(
    type_id: UUID, data: SaleTypeIn, db: Session = Depends(get_db), _=Depends(_update)
):
    row = _get_or_404(db, SaleType, type_id, "نوعِ فروش")
    _assert_name_free(db, SaleType, data.name, "نوعِ فروش", skip_id=type_id)
    for k, v in data.model_dump().items():
        setattr(row, k, v)
    db.flush()
    db.refresh(row)
    return row


# ──────────────────────── گروهِ کالای تخفیف ──────────────────────────


def _group_out(g: DiscountItemGroup) -> DiscountGroupOut:
    ids = [m.item_id for m in g.members]
    return DiscountGroupOut(
        id=g.id,
        name=g.name,
        description=g.description,
        is_active=g.is_active,
        item_ids=ids,
        item_count=len(ids),
    )


@router.get("/discount-groups", response_model=list[DiscountGroupOut])
def list_discount_groups(db: Session = Depends(get_db), _=Depends(_view)):
    rows = (
        db.query(DiscountItemGroup)
        .options(selectinload(DiscountItemGroup.members))
        .order_by(DiscountItemGroup.name)
        .all()
    )
    return [_group_out(g) for g in rows]


@router.post("/discount-groups", response_model=DiscountGroupOut, status_code=201)
def create_discount_group(data: DiscountGroupIn, db: Session = Depends(get_db), _=Depends(_create)):
    _assert_name_free(db, DiscountItemGroup, data.name, "گروهِ کالا")
    g = DiscountItemGroup(name=data.name, description=data.description, is_active=data.is_active)
    g.members = [DiscountItemGroupMember(item_id=i) for i in dict.fromkeys(data.item_ids)]
    db.add(g)
    db.flush()
    db.refresh(g)
    return _group_out(g)


@router.patch("/discount-groups/{group_id}", response_model=DiscountGroupOut)
def update_discount_group(
    group_id: UUID, data: DiscountGroupIn, db: Session = Depends(get_db), _=Depends(_update)
):
    g = _get_or_404(db, DiscountItemGroup, group_id, "گروهِ کالا")
    _assert_name_free(db, DiscountItemGroup, data.name, "گروهِ کالا", skip_id=group_id)
    g.name, g.description, g.is_active = data.name, data.description, data.is_active
    # اعضا کاملاً جایگزین می‌شوند: «این گروه دقیقاً این کالاهاست»، نه «این‌ها را هم
    # اضافه کن» — وگرنه حذفِ یک عضو از رابط ممکن نمی‌شد.
    g.members.clear()
    db.flush()
    g.members = [DiscountItemGroupMember(item_id=i) for i in dict.fromkeys(data.item_ids)]
    db.flush()
    db.refresh(g)
    return _group_out(g)


# ─────────────────── تخفیف و عاملِ افزاینده (یک جدول) ────────────────


@router.get("/pricing-factors", response_model=list[PricingFactorOut])
def list_pricing_factors(
    kind: str | None = Query(None, description="discount | markup"),
    db: Session = Depends(get_db),
    _=Depends(_view),
):
    q = db.query(PricingFactor)
    if kind in ("discount", "markup"):
        q = q.filter(PricingFactor.kind == kind)
    return q.order_by(PricingFactor.kind, PricingFactor.name).all()


@router.post("/pricing-factors", response_model=PricingFactorOut, status_code=201)
def create_pricing_factor(data: PricingFactorIn, db: Session = Depends(get_db), _=Depends(_create)):
    _assert_scope(data)
    row = PricingFactor(**data.model_dump())
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


@router.patch("/pricing-factors/{factor_id}", response_model=PricingFactorOut)
def update_pricing_factor(
    factor_id: UUID, data: PricingFactorIn, db: Session = Depends(get_db), _=Depends(_update)
):
    _assert_scope(data)
    row = _get_or_404(db, PricingFactor, factor_id, "عاملِ قیمت")
    for k, v in data.model_dump().items():
        setattr(row, k, v)
    db.flush()
    db.refresh(row)
    return row


def _assert_scope(data: PricingFactorIn) -> None:
    """دامنه بدونِ هدفش بی‌معنی است و بی‌صدا روی «همه» می‌افتد."""
    if data.scope == "item" and data.item_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای دامنه‌ی «کالا» باید کالا انتخاب شود")
    if data.scope == "group" and data.group_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای دامنه‌ی «گروه» باید گروه انتخاب شود")
    if data.valid_from and data.valid_to and data.valid_from > data.valid_to:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تاریخِ شروع بعد از پایان است")


# ───────────────────────── اعلامیه‌ی قیمت ──────────────────────────


def _price_out(pl: PriceList, lines: list[PriceListItem]) -> PriceAnnouncementOut:
    return PriceAnnouncementOut(
        id=pl.id,
        name=pl.name,
        effective_from=pl.effective_from,
        notes=pl.notes,
        is_active=pl.is_active,
        line_count=len(lines),
        lines=[{"item_id": str(l.item_id), "price": l.price} for l in lines],
    )


@router.get("/price-announcements", response_model=list[PriceAnnouncementOut])
def list_price_announcements(db: Session = Depends(get_db), _=Depends(_view)):
    rows = (
        db.query(PriceList)
        .options(selectinload(PriceList.items))
        .order_by(PriceList.effective_from.desc())
        .all()
    )
    return [_price_out(p, p.items) for p in rows]


@router.post("/price-announcements", response_model=PriceAnnouncementOut, status_code=201)
def create_price_announcement(
    data: PriceAnnouncementIn, db: Session = Depends(get_db), user: User = Depends(_create)
):
    _assert_name_free(db, PriceList, data.name, "اعلامیه‌ی قیمت")
    pl = PriceList(
        name=data.name,
        effective_from=data.effective_from,
        notes=data.notes,
        is_active=data.is_active,
        created_by_id=user.id,
    )
    pl.items = [PriceListItem(item_id=l.item_id, price=l.price) for l in data.lines]
    db.add(pl)
    db.flush()
    db.refresh(pl)
    return _price_out(pl, pl.items)


# ────────────────────────── بسته‌ی محصول ───────────────────────────


def _bundle_out(b: ProductBundle) -> ProductBundleOut:
    return ProductBundleOut(
        id=b.id,
        name=b.name,
        bundle_price=b.bundle_price,
        is_active=b.is_active,
        description=b.description,
        lines=[{"item_id": str(l.item_id), "qty": l.qty} for l in b.lines],
    )


@router.get("/bundles", response_model=list[ProductBundleOut])
def list_bundles(db: Session = Depends(get_db), _=Depends(_view)):
    rows = db.query(ProductBundle).options(selectinload(ProductBundle.lines)).order_by(ProductBundle.name).all()
    return [_bundle_out(b) for b in rows]


@router.post("/bundles", response_model=ProductBundleOut, status_code=201)
def create_bundle(data: ProductBundleIn, db: Session = Depends(get_db), _=Depends(_create)):
    if not data.lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "بسته باید دستِ‌کم یک کالا داشته باشد")
    _assert_name_free(db, ProductBundle, data.name, "بسته")
    b = ProductBundle(
        name=data.name,
        bundle_price=data.bundle_price,
        is_active=data.is_active,
        description=data.description,
    )
    b.lines = [ProductBundleLine(item_id=l.item_id, qty=l.qty) for l in data.lines]
    db.add(b)
    db.flush()
    db.refresh(b)
    return _bundle_out(b)


# ──────────────────────────── پورسانت ────────────────────────────


def _person_names(db: Session) -> dict[UUID, str]:
    return {u.id: (u.name or u.email) for u in db.query(User).all()}


@router.get("/commission-rules", response_model=list[CommissionRuleOut])
def list_commission_rules(db: Session = Depends(get_db), _=Depends(_view)):
    names = _person_names(db)
    return [
        CommissionRuleOut(
            id=r.id,
            salesperson_id=r.salesperson_id,
            salesperson_name=names.get(r.salesperson_id, "—"),
            rate=r.rate,
            basis=r.basis,
            is_active=r.is_active,
            description=r.description,
        )
        for r in db.query(CommissionRule).all()
    ]


@router.post("/commission-rules", response_model=CommissionRuleOut, status_code=201)
def create_commission_rule(data: CommissionRuleIn, db: Session = Depends(get_db), _=Depends(_create)):
    exists = (
        db.query(CommissionRule).filter(CommissionRule.salesperson_id == data.salesperson_id).first()
    )
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "برای این فروشنده قاعده‌ی پورسانت ثبت شده است")
    row = CommissionRule(**data.model_dump())
    db.add(row)
    db.flush()
    db.refresh(row)
    return CommissionRuleOut(
        id=row.id,
        salesperson_id=row.salesperson_id,
        salesperson_name=_person_names(db).get(row.salesperson_id, "—"),
        rate=row.rate,
        basis=row.basis,
        is_active=row.is_active,
        description=row.description,
    )


@router.get("/commission/preview", response_model=CommissionPreviewOut)
def commission_preview(
    date_from: date, date_to: date, db: Session = Depends(get_db), _=Depends(_view)
):
    return svc.preview_commission(db, date_from, date_to)


@router.post("/commission/runs", response_model=CommissionRunOut, status_code=201)
def create_commission_run(
    data: CommissionRunIn, db: Session = Depends(get_db), user: User = Depends(_create)
):
    run = svc.run_commission(db, user, data.date_from, data.date_to, data.note)
    return _run_out(db, run)


@router.get("/commission/runs", response_model=list[CommissionRunOut])
def list_commission_runs(db: Session = Depends(get_db), _=Depends(_view)):
    rows = (
        db.query(CommissionRun)
        .options(selectinload(CommissionRun.lines))
        .order_by(CommissionRun.created_at.desc())
        .all()
    )
    return [_run_out(db, r) for r in rows]


def _run_out(db: Session, run: CommissionRun) -> CommissionRunOut:
    names = _person_names(db)
    return CommissionRunOut(
        id=run.id,
        date_from=run.date_from,
        date_to=run.date_to,
        total_amount=run.total_amount,
        note=run.note,
        created_at=run.created_at,
        rows=[
            {
                "salesperson_id": l.salesperson_id,
                "salesperson_name": names.get(l.salesperson_id, "—"),
                "invoice_count": l.invoice_count,
                "base_amount": l.base_amount,
                "rate": l.rate,
                "basis": l.basis,
                "amount": l.amount,
            }
            for l in run.lines
        ],
    )


# ────────────────────── اظهارنامه‌ی گمرکی ───────────────────────


@router.get("/customs", response_model=list[CustomsOut])
def list_customs(db: Session = Depends(get_db), _=Depends(_view)):
    rows = db.query(CustomsDeclaration).order_by(CustomsDeclaration.declaration_date.desc()).all()
    numbers = {
        i.id: i.number for i in db.query(SalesInvoice.id, SalesInvoice.number).all()
    } if rows else {}
    return [
        CustomsOut(
            **{c: getattr(r, c) for c in (
                "id", "declaration_no", "declaration_date", "customs_office", "hs_code",
                "destination_country", "declared_value", "currency_code", "invoice_id", "description",
            )},
            invoice_number=numbers.get(r.invoice_id),
        )
        for r in rows
    ]


@router.post("/customs", response_model=CustomsOut, status_code=201)
def create_customs(data: CustomsIn, db: Session = Depends(get_db), _=Depends(_create)):
    dup = (
        db.query(CustomsDeclaration)
        .filter(CustomsDeclaration.declaration_no == data.declaration_no)
        .first()
    )
    if dup is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "اظهارنامه‌ای با این شماره ثبت شده است")
    row = CustomsDeclaration(**data.model_dump())
    db.add(row)
    db.flush()
    db.refresh(row)
    return CustomsOut.model_validate(row)


# ─────────────── اعلامیه‌ی بدهکار / بستانکار (سنددار) ───────────────


def _note_out(db: Session, n: CreditDebitNote, names: dict[UUID, str] | None = None) -> NoteOut:
    names = names if names is not None else {c.id: c.name for c in db.query(Contact).all()}
    return NoteOut(
        id=n.id,
        number=n.number,
        kind=n.kind,
        note_date=n.note_date,
        contact_id=n.contact_id,
        contact_name=names.get(n.contact_id, "—"),
        amount=n.amount,
        reason=n.reason,
        invoice_id=n.invoice_id,
        journal_entry_id=n.journal_entry_id,
        voided_at=n.voided_at,
    )


@router.get("/notes", response_model=list[NoteOut])
def list_notes(
    kind: str | None = Query(None, description="debit | credit"),
    db: Session = Depends(get_db),
    _=Depends(_view),
):
    q = db.query(CreditDebitNote)
    if kind in ("debit", "credit"):
        q = q.filter(CreditDebitNote.kind == kind)
    rows = q.order_by(CreditDebitNote.note_date.desc(), CreditDebitNote.number.desc()).all()
    names = {c.id: c.name for c in db.query(Contact).all()}
    return [_note_out(db, n, names) for n in rows]


@router.post("/notes", response_model=NoteOut, status_code=201)
def create_note(data: NoteIn, db: Session = Depends(get_db), user: User = Depends(_create)):
    note = svc.post_note(
        db,
        user,
        kind=data.kind,
        note_date=data.note_date,
        contact_id=data.contact_id,
        amount=Decimal(data.amount),
        reason=data.reason,
        invoice_id=data.invoice_id,
    )
    return _note_out(db, note)


@router.post("/notes/{note_id}/void", response_model=NoteOut)
def void_note(
    note_id: UUID,
    data: VoidNoteIn,
    db: Session = Depends(get_db),
    #: ابطال اثرِ حسابداری دارد — مثلِ ابطالِ فاکتور مجوزِ delete می‌خواهد.
    user: User = Depends(require_permission("sales", "delete")),
):
    return _note_out(db, svc.void_note(db, user, note_id, data.reason))


# ─────────────────────────── بستنِ فاکتور ─────────────────────────


@router.post("/invoices/close", response_model=CloseInvoicesOut)
def close_invoices(
    data: CloseInvoicesIn, db: Session = Depends(get_db), user: User = Depends(_update)
):
    return svc.close_invoices(
        db,
        user,
        invoice_ids=data.invoice_ids or None,
        date_from=data.date_from,
        date_to=data.date_to,
    )


# ────────────────────── پیشنهادِ قیمت‌گذاری ───────────────────────


@router.get("/pricing/suggest", response_model=PricingSuggestionOut)
def pricing_suggest(
    item_id: UUID,
    qty: Decimal = Query(default=Decimal(1), gt=0),
    on: date | None = None,
    #: زمینه‌ی قیمت (§۳۹ §۴۰ §۴۱). همه اختیاری‌اند و نفرستادنشان همان رفتارِ
    #: پیشین را می‌دهد — قاعده‌ی «هر زمینه‌ای».
    sale_type_id: UUID | None = None,
    unit_id: UUID | None = None,
    contact_id: UUID | None = None,
    currency_code: str = "IRR",
    db: Session = Depends(get_db),
    _=Depends(_view),
):
    return svc.suggest_pricing(
        db,
        item_id,
        qty,
        on,
        sale_type_id=sale_type_id,
        unit_id=unit_id,
        contact_id=contact_id,
        currency_code=currency_code,
    )
