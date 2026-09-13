"""اندپوینت‌های عملیاتِ ماژولِ فروش.

مجوزها روی ماژولِ `sales` می‌نشینند، جز اعلامیه‌ی بدهکار/بستانکار که مالِ دو ماژول
است و سند حسابداری می‌زند — مجوزش کنارِ خودش توضیح داده شده.
"""
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import exists, or_
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import require_permission
from app.models.accounting import Account, JournalEntry
from app.models.advanced_inventory import PriceList, PriceListItem
from app.models.inventory import Contact
from app.models.invoices import SalesInvoice
from app.models.sales_ops import (
    CommissionRule,
    CommissionRun,
    CreditDebitNote,
    CreditDebitNoteLine,
    CustomsDeclaration,
    DiscountItemGroup,
    DiscountItemGroupMember,
    PricingFactor,
    ProductBundle,
    ProductBundleLine,
    SaleType,
)
from app.models.user import User
from app.schemas.advanced_inventory import PriceListItemOut, ResolvedPriceOut
from app.schemas.sales_ops import (
    BulkPriceIn,
    BulkPriceOut,
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
    NoteAccountOut,
    NoteDraftOut,
    NoteIn,
    NoteLineOut,
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
from app.pagination import Page, PageParams, paginate
from app.services import pricing
from app.services import sales_ops as svc
from app.services.idempotency import idempotent

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
    #: ردیف‌ها با **کلِ زمینه‌شان** بیرون می‌روند، نه فقط کالا و قیمت. تا امروز
    #: این‌جا `{item_id, price}` بود، پس صفحه‌ی اعلامیه هرگز نمی‌توانست نشان دهد
    #: که یک ردیف مالِ کدام نوعِ فروش است — و در ذخیره‌ی بعدی همان زمینه گم می‌شد.
    return PriceAnnouncementOut(
        id=pl.id,
        name=pl.name,
        effective_from=pl.effective_from,
        notes=pl.notes,
        is_active=pl.is_active,
        line_count=len(lines),
        lines=[PriceListItemOut.model_validate(l) for l in lines],
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
    #: **هر ستونِ ماتریس منتقل می‌شود، نه فقط کالا و قیمت.** تا امروز این‌جا
    #: `PriceListItem(item_id=…, price=…)` بود، یعنی صفحه‌ی «اعلامیه قیمت» فقط
    #: می‌توانست قاعده‌ی بی‌زمینه بسازد — و شاهدِ مرکزیِ فصل (یک کالا، سه نوعِ
    #: فروش، سه قیمت) از هیچ‌جای محصول قابلِ ورود نبود.
    pl.items = [PriceListItem(**line.model_dump()) for line in data.lines]
    db.add(pl)
    db.flush()
    db.refresh(pl)
    return _price_out(pl, pl.items)


@router.post("/price-announcements/{list_id}/bulk-price", response_model=BulkPriceOut)
def bulk_price_change(
    list_id: UUID,
    data: BulkPriceIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(_update),
):
    """«تغییر فی» — تغییرِ گروهیِ قیمتِ ردیف‌های یک اعلامیه (§۴۲–§۴۸).

    **چرا این یکی حتماً باید یکتا باشد (§۴۵ §۴۶ §۹۴).** «۲۰٪ اضافه کن» برخلافِ
    یک ذخیره‌ی معمولی *جابه‌جاکننده* است، نه *نشاننده*: اگر پاسخ گم شود و
    کلاینت دوباره بفرستد، ۱۰۰ که به ۱۲۰ رفته بود به ۱۴۴ می‌رود — و هیچ‌کس
    متوجه نمی‌شود، چون هر دو اجرا «موفق» بوده‌اند. پس همان `idempotent(...)`ِ
    فاکتور این‌جا هم می‌نشیند و اجرای دوم فقط پاسخِ اول را پس می‌دهد.
    """
    result = idempotent(
        db,
        request,
        user,
        operation="bulk_price_change",
        payload=data,
        run=lambda: pricing.bulk_change(
            db,
            list_id,
            mode=data.mode,
            value=data.value,
            rounding=data.rounding,
            rule_ids=data.rule_ids or None,
            item_ids=data.item_ids or None,
            sale_type_id=data.sale_type_id,
            currency_code=data.currency_code,
        ),
        replay=lambda rid: pricing.BulkResult(id=rid, changed=0, replayed=True),
    )
    return BulkPriceOut(
        announcement_id=result.id, changed=result.changed, replayed=result.replayed
    )


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

#: **مجوزِ اعلامیه مالِ دو ماژول است، نه فروش.** سند هم از مسیرِ فروش صادر می‌شود و
#: هم از مسیرِ خرید (§۶)، و ماژولِ مجوزِ `sales` اصلاً در رجیستریِ مجوزها نیست — یعنی
#: تا امروز هیچ‌کس جز مالک نمی‌توانست اعلامیه بزند، حتی حسابدار. `invoices` («فاکتور
#: فروش و خرید») و `accounting` هر دو معنی دارند: یکی کارِ طرف مقابل است، دیگری سند.
_notes_view = require_permission(("invoices", "accounting"), "view")
_notes_create = require_permission(("invoices", "accounting"), "create")
#: ابطال اثرِ حسابداری دارد و «اصلاحِ معمولی» نیست (§۵۹) — همان مجوزی که ابطالِ
#: برگشت از فروش و خرید می‌خواهد.
_notes_void = require_permission("accounting", "delete")

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _notes_out(db: Session, notes: list[CreditDebitNote]) -> list[NoteOut]:
    """خروجیِ چند اعلامیه با **یک** کوئری برای هر نوعِ نام، نه یکی برای هر ردیف.

    تا امروز هر درخواست کلِ طرف‌حساب‌ها و کلِ چارت را می‌کشید تا چند نام را پیدا کند.
    """
    contact_ids: set[UUID] = set()
    account_ids: set[UUID] = set()
    user_ids: set[UUID] = set()
    entry_ids: set[UUID] = set()
    for n in notes:
        if n.contact_id:
            contact_ids.add(n.contact_id)
        if n.voided_by_id:
            user_ids.add(n.voided_by_id)
        if n.journal_entry_id:
            entry_ids.add(n.journal_entry_id)
        for r in n.lines:
            contact_ids.update(x for x in (r.debit_contact_id, r.credit_contact_id) if x)
            account_ids.update((r.debit_account_id, r.credit_account_id))

    names = dict(db.query(Contact.id, Contact.name).filter(Contact.id.in_(contact_ids)).all()) if contact_ids else {}
    accounts = (
        {a.id: (a.code, a.name) for a in db.query(Account).filter(Account.id.in_(account_ids)).all()}
        if account_ids
        else {}
    )
    users = dict(db.query(User.id, User.name).filter(User.id.in_(user_ids)).all()) if user_ids else {}
    entries = (
        {e.id: e for e in db.query(JournalEntry).filter(JournalEntry.id.in_(entry_ids)).all()} if entry_ids else {}
    )
    #: سندِ معکوس با `reverses_entry_id` پیدا می‌شود — همان پیوندی که دفتر روزنامه
    #: می‌خواند. اعلامیه‌ای که پیش از مهاجرتِ ۰۱۳۶ باطل شده این پیوند را ندارد.
    reversals = (
        {
            e.reverses_entry_id: e
            for e in db.query(JournalEntry).filter(JournalEntry.reverses_entry_id.in_(entry_ids)).all()
        }
        if entry_ids
        else {}
    )

    def who(cid: UUID | None) -> str:
        return names.get(cid, "—") if cid is not None else "—"

    def acc(aid: UUID) -> tuple[str, str]:
        return accounts.get(aid, ("", "—"))

    out = []
    for n in notes:
        entry = entries.get(n.journal_entry_id) if n.journal_entry_id else None
        reversal = reversals.get(n.journal_entry_id) if n.journal_entry_id else None
        out.append(
            NoteOut(
                id=n.id,
                number=n.number,
                note_date=n.note_date,
                amount=n.amount,
                base_amount=n.base_amount,
                reason=n.reason,
                currency_code=n.currency_code,
                exchange_rate=n.exchange_rate,
                lines=[
                    NoteLineOut(
                        id=r.id,
                        seq=r.seq,
                        debit_contact_id=r.debit_contact_id,
                        debit_contact_name=who(r.debit_contact_id),
                        debit_account_id=r.debit_account_id,
                        debit_account_code=acc(r.debit_account_id)[0],
                        debit_account_name=acc(r.debit_account_id)[1],
                        credit_contact_id=r.credit_contact_id,
                        credit_contact_name=who(r.credit_contact_id),
                        credit_account_id=r.credit_account_id,
                        credit_account_code=acc(r.credit_account_id)[0],
                        credit_account_name=acc(r.credit_account_id)[1],
                        amount=r.amount,
                        base_amount=r.base_amount,
                        description=r.description,
                    )
                    for r in n.lines
                ],
                invoice_id=n.invoice_id,
                journal_entry_id=n.journal_entry_id,
                journal_entry_number=entry.number if entry else None,
                journal_entry_date=entry.entry_date if entry else None,
                voided_at=n.voided_at,
                voided_by_name=users.get(n.voided_by_id) if n.voided_by_id else None,
                void_reason=n.void_reason or "",
                void_entry_id=reversal.id if reversal else None,
                void_entry_number=reversal.number if reversal else None,
                void_entry_date=reversal.entry_date if reversal else None,
                kind=n.kind,
                contact_id=n.contact_id,
                contact_name=who(n.contact_id),
            )
        )
    return out


def _note_out(db: Session, n: CreditDebitNote) -> NoteOut:
    return _notes_out(db, [n])[0]


@router.get("/notes", response_model=Page[NoteOut])
def list_notes(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    contact_id: UUID | None = Query(None, description="طرف حسابی که در هر سمتِ هر ردیفی آمده باشد"),
    status_filter: str = Query("all", alias="status", pattern="^(all|active|voided)$"),
    q: str | None = Query(None, max_length=100, description="شماره‌ی اعلامیه یا بخشی از شرح"),
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
    _=Depends(_notes_view),
):
    """دفترِ اعلامیه‌ها — **فیلتر سمتِ سرور** و صفحه‌بندیِ keyset.

    تا امروز این اندپوینت کلِ اعلامیه‌ها را یک‌جا برمی‌گرداند و رابط بازه و طرف حساب
    را در مرورگر می‌برید؛ با اولین کسب‌وکارِ چندساله از کار می‌افتاد.
    """
    query = db.query(CreditDebitNote).options(selectinload(CreditDebitNote.lines))
    if date_from is not None:
        query = query.filter(CreditDebitNote.note_date >= date_from)
    if date_to is not None:
        query = query.filter(CreditDebitNote.note_date <= date_to)
    if status_filter == "active":
        query = query.filter(CreditDebitNote.voided_at.is_(None))
    elif status_filter == "voided":
        query = query.filter(CreditDebitNote.voided_at.isnot(None))
    if contact_id is not None:
        in_lines = (
            exists()
            .where(CreditDebitNoteLine.note_id == CreditDebitNote.id)
            .where(
                or_(
                    CreditDebitNoteLine.debit_contact_id == contact_id,
                    CreditDebitNoteLine.credit_contact_id == contact_id,
                )
            )
        )
        #: `contact_id`ِ سربرگ فقط برای اعلامیه‌های تک‌سمتیِ پیش از ۰۱۲۷ پر است.
        query = query.filter(or_(in_lines, CreditDebitNote.contact_id == contact_id))
    if q and q.strip():
        term = q.strip().translate(_FA_DIGITS)
        if term.isdigit():
            query = query.filter(CreditDebitNote.number == int(term))
        else:
            query = query.filter(CreditDebitNote.reason.ilike(f"%{term}%"))

    rows, next_cursor = paginate(
        query, [CreditDebitNote.note_date, CreditDebitNote.number, CreditDebitNote.id], page
    )
    return Page(items=_notes_out(db, rows), next_cursor=next_cursor)


@router.get("/notes/accounts", response_model=list[NoteAccountOut])
def note_accounts(
    scope: str = Query("counterparty", pattern="^(counterparty|other)$"),
    db: Session = Depends(get_db),
    _=Depends(_notes_view),
):
    """معین‌هایی که یک سمتِ اعلامیه می‌تواند رویشان بنشیند.

    `counterparty` — سمتی که طرف حساب دارد: دریافتنی و پرداختنیِ تجاری.
    `other` — سمتِ بی‌طرف‌حساب: هر معینِ قابلِ ثبت جز آن دو و جز حساب‌های خزانه،
    انبار و مالیات. همان قاعده‌ای که سرویس هنگامِ صدور اعمال می‌کند؛ فرم فقط
    گزینه‌ی ممنوع را از اول نشان نمی‌دهد.

    فرم از این می‌خواند تا **کد و عنوان** را کنارِ هم نشان دهد؛ کدِ تنها، انتخابِ
    اشتباهِ حساب را آسان می‌کند.
    """
    rows = svc.counterparty_accounts(db) if scope == "counterparty" else svc.other_accounts(db)
    return [NoteAccountOut(id=a.id, code=a.code, name=a.name, system_role=a.system_role) for a in rows]


@router.post("/notes", response_model=NoteOut, status_code=201)
def create_note(
    data: NoteIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(_notes_create),
):
    """ثبتِ اعلامیه با کلیدِ یکتاسازی.

    ثبتِ دوباره‌ی این سند یعنی تعدیلِ مانده دو بار — بی‌صداترین خطای ممکن، چون هر
    دو سند تراز و معتبرند و هیچ گزارشی خبر نمی‌دهد (§۴۶).
    """

    def _run() -> NoteOut:
        note = svc.post_notice(
            db,
            user,
            note_date=data.note_date,
            lines=data.lines,
            description=data.reason,
            currency_code=data.currency_code,
            exchange_rate=Decimal(data.exchange_rate),
        )
        return _note_out(db, note)

    return idempotent(
        db,
        request,
        user,
        operation="create_credit_debit_note",
        payload=data,
        run=_run,
        #: پاسخِ اجرای اول از خودِ سند بازساخته می‌شود، نه از یک کپیِ ذخیره‌شده.
        replay=lambda note_id: _note_out(db, db.get(CreditDebitNote, note_id)),
    )


@router.get("/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: UUID, db: Session = Depends(get_db), _=Depends(_notes_view)):
    """یک اعلامیه — مقصدِ drill-down از کارتِ حساب و از سندِ حسابداری (§۲۳)."""
    note = db.get(CreditDebitNote, note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اعلامیه پیدا نشد")
    return _note_out(db, note)


@router.get("/notes/{note_id}/duplicate-draft", response_model=NoteDraftOut)
def duplicate_note_draft(note_id: UUID, db: Session = Depends(get_db), _=Depends(_notes_view)):
    """پیش‌نویسِ «رونوشت» — چیزی نمی‌نویسد، پس تکرارش هم چیزی نمی‌سازد (§۶۵)."""
    return svc.duplicate_note_draft(db, note_id)


@router.post("/notes/{note_id}/void", response_model=NoteOut)
def void_note(
    note_id: UUID,
    data: VoidNoteIn,
    db: Session = Depends(get_db),
    user: User = Depends(_notes_void),
):
    return _note_out(db, svc.void_note(db, user, note_id, data.reason, data.void_date))


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


@router.get("/pricing/resolve", response_model=ResolvedPriceOut | None)
def pricing_resolve(
    item_id: UUID,
    on: date | None = None,
    sale_type_id: UUID | None = None,
    unit_id: UUID | None = None,
    contact_id: UUID | None = None,
    currency_code: str = "IRR",
    db: Session = Depends(get_db),
    _=Depends(_view),
):
    """فیِ مصوبِ این کالا در این زمینه، و **چرا** (§۲۱ §۹۱).

    **تنها موتورِ قیمت (§۵۴ §۹۲).** تا پیش از این فصل، فرمِ فاکتور و صندوق هرکدام
    نگاشتِ `item_id → price`ِ خودشان را از `contact.default_price_list_id`
    می‌ساختند — بی‌اعتنا به تاریخِ اجرا، فعال‌بودن، و هر چهار بُعدِ زمینه. یعنی
    فرم یک عدد پر می‌کرد و `assert_within_policy` با قاعده‌ی **دیگری** اعتبارش را
    می‌سنجید. حالا هر دو از همین‌جا می‌آیند.

    `null` یعنی هیچ قاعده‌ای با این زمینه نخواند — که سیاستی هم برای نقض‌شدن
    نیست (§۵۸). کلاینت در آن حالت به قیمتِ پایه‌ی کالا برمی‌گردد، همان رفتارِ
    امروز.
    """
    return pricing.resolve_detail(
        db,
        item_id,
        on=on,
        sale_type_id=sale_type_id,
        unit_id=unit_id,
        contact_id=contact_id,
        currency_code=currency_code,
    )
