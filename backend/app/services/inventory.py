from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.counters import DOC_JOURNAL_ENTRY, DOC_PURCHASE_INVOICE, DOC_SALES_INVOICE
from app.services import tafsili
from app.services.numbering import next_document_number
from app.models.accounting import JournalEntry, JournalLine
from app.models.advanced_inventory import StockBatch
from app.models.inventory import Contact, Item, StockAdjustment, StockLedger
from app.models.invoices import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
)
from app.models.user import User
from app.schemas.inventory import StockAdjustmentIn
from app.schemas.invoices import PurchaseInvoiceIn, SalesInvoiceIn
from app.services import chart_codes as cc
from app.services import warehouses
from app.services.common import get_account as _get_account
from app.services.common import get_or_create_account
from app.services.common import number_lines
from app.services.cost_centers import resolve_cost_center_id
from app.services.credit import assert_within_credit_limit
from app.services.period_close import assert_period_open


def vat_payable_account(db: Session):
    return get_or_create_account(
        db,
        cc.VAT_PAYABLE,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.VAT_PAYABLE],
        name="مالیات بر ارزش افزوده پرداختنی",
        acc_type="liability",
        parent_code="21",
    )


def vat_receivable_account(db: Session):
    return get_or_create_account(
        db,
        cc.VAT_RECEIVABLE,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.VAT_RECEIVABLE],
        name="مالیات بر ارزش افزوده / اعتبار مالیاتی",
        acc_type="asset",
        parent_code="11",
    )


def sales_rounding_account(db: Session):
    """حسابِ تعدیلِ گِرد کردنِ فروش — on-demand (مثل حساب‌های مالیات) تا برای
    کسب‌وکارهای قدیمی هم خودکار فراهم شود."""
    return get_or_create_account(
        db,
        cc.SALES_ROUNDING,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.SALES_ROUNDING],
        name="تعدیلِ گِرد کردن فروش",
        acc_type="income",
        parent_code="41",
    )


def _allocate_discount(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """تسهیمِ یک تخفیفِ کل میان ردیف‌ها به‌نسبتِ خالصِ هر ردیف.

    مبالغ صحیحِ ریال‌اند؛ با روشِ «بیشترین باقی‌مانده» جمعِ سهم‌ها *دقیقاً* برابرِ کل
    می‌شود (نه یک ریال کم، نه زیاد). چون total ≤ Σweights تضمین شده، سهمِ هر ردیف از
    خالصِ همان ردیف بیشتر نمی‌شود.
    """
    n = len(weights)
    s = sum(weights)
    if total <= 0 or s <= 0:
        return [Decimal(0)] * n
    raw = [total * w / s for w in weights]
    shares = [r.to_integral_value(rounding=ROUND_FLOOR) for r in raw]
    remainder = int(total - sum(shares))
    # باقی‌مانده (کمتر از تعداد ردیف‌ها) را به ردیف‌هایی با بزرگ‌ترین کسر بده
    order = sorted(range(n), key=lambda i: raw[i] - shares[i], reverse=True)
    for i in order[:remainder]:
        shares[i] += 1
    return shares


def compute_tax(net: Decimal, rate: Decimal) -> Decimal:
    """مبلغ مالیات = خالص × نرخ٪، گردشده به عددِ صحیحِ ریال/تومان (ROUND_HALF_UP)."""
    if rate is None or rate <= 0:
        return Decimal(0)
    return (net * rate / Decimal(100)).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def resolve_broker(db: Session, broker_id: UUID | None, net: Decimal) -> tuple[UUID | None, Decimal]:
    """واسطه را اعتبارسنجی می‌کند و کارمزدش را **در همین لحظه قفل می‌کند**.

    مبنا `net` است — خالصِ پس از تخفیف و پیش از مالیات. همان مبنایی که قاعده‌ی
    پورسانتِ فروشنده با `basis="revenue"` به‌کار می‌برد، تا دو جای برنامه یک چیز را
    دو جور حساب نکنند. مالیات وارد مبنا نمی‌شود چون پولِ دولت است نه فروشِ ما.

    برگرداندنِ مبلغ به‌جای نگه‌داشتنِ نرخ عمدی است: `contacts.commission_rate` نرخِ
    امروز است و فردا عوض می‌شود؛ کارمزدِ این فروش همین‌جا قطعی شده.
    """
    if broker_id is None:
        return None, Decimal(0)

    broker = db.get(Contact, broker_id)
    if broker is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "واسطه‌ی انتخاب‌شده پیدا نشد")
    #: بدونِ این، هر طرف‌حسابی می‌توانست واسطه شود و تیکِ «واسط» تزئینی می‌شد.
    if not broker.is_broker:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"«{broker.name}» نقشِ واسط ندارد — در فرمِ طرف حساب تیکِ «واسط» را بزنید.",
        )

    rate = Decimal(broker.commission_rate or 0)
    if rate <= 0:
        return broker.id, Decimal(0)
    commission = (max(net, Decimal(0)) * rate / Decimal(100)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return broker.id, commission


def resolve_salesperson_id(db: Session, salesperson_id: UUID | None) -> UUID | None:
    """فروشنده‌ی فاکتور را اعتبارسنجی می‌کند — مبنای محاسبه‌ی پورسانت.

    فروشنده **کاربرِ سامانه** است نه طرف‌حساب (تصمیمِ صریحِ `CommissionRule`)، پس
    باید عضوِ همین کسب‌وکار باشد. `memberships` جدولِ سراسری و بی‌RLS است، پس
    فیلترِ `tenant_id` این‌جا صریح می‌آید — بدونِ آن هر کاربری از هر کسب‌وکارِ
    دیگری روی فاکتور می‌نشست.
    """
    if salesperson_id is None:
        return None
    from app.models.tenant import Membership
    from app.tenant_context import session_tenant

    member = (
        db.query(Membership.id)
        .filter(
            Membership.user_id == salesperson_id,
            Membership.tenant_id == session_tenant(db),
        )
        .first()
    )
    if member is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "فروشنده‌ی انتخاب‌شده کاربرِ این کسب‌وکار نیست.",
        )
    return salesperson_id


def resolve_sale_type_id(db: Session, sale_type_id: UUID | None) -> UUID | None:
    """نوعِ فروش را اعتبارسنجی می‌کند (نقدی، اعتباری، صادراتی…).

    نوعِ **غیرفعال** به فاکتورِ تازه نمی‌خورد — همان قاعده‌ای که مرکز هزینه دارد و
    به همان دلیل: «غیرفعال» باید در سرور معنا داشته باشد وگرنه فقط یک فیلترِ
    سمتِ کلاینت است. فاکتور ویرایش نمی‌شود (ابطال و صدورِ تازه می‌شود)، پس
    برخلافِ `resolve_cost_center_id` به راهِ فرارِ `current` نیازی نیست.
    """
    if sale_type_id is None:
        return None
    from app.models.sales_ops import SaleType

    sale_type = db.get(SaleType, sale_type_id)
    if sale_type is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوعِ فروشِ انتخاب‌شده معتبر نیست")
    if not sale_type.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"نوعِ فروشِ «{sale_type.name}» غیرفعال است؛ نوعِ دیگری انتخاب کنید.",
        )
    return sale_type_id


def get_stock_qty(db: Session, item_id: UUID, warehouse_id: UUID) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(StockLedger.qty), 0))
        .filter(StockLedger.item_id == item_id, StockLedger.warehouse_id == warehouse_id)
        .scalar()
    )
    return Decimal(total)


def get_total_stock_qty(db: Session, item_id: UUID) -> Decimal:
    total = db.query(func.coalesce(func.sum(StockLedger.qty), 0)).filter(StockLedger.item_id == item_id).scalar()
    return Decimal(total)


def lock_items(db: Session, item_ids) -> None:
    """ردیف کالاها را تا پایان تراکنش قفل می‌کند.

    قفل روی «کالا» است و نه روی دفتر موجودی، چون دفتر append-only است: قفل کردن
    ردیف‌های موجود جلوی INSERT ردیف جدید توسط تراکنش دیگر را نمی‌گیرد. ردیف کالا
    تنها نقطه‌ی مشترکی است که همه‌ی عملیات آن کالا از آن رد می‌شوند، و همین قفل
    هم‌زمان read-modify-write روی average_cost را هم امن می‌کند.

    ORDER BY لازم است نه تزئینی: بدون ترتیب قطعی، دو فاکتور هم‌زمان روی کالاهای
    مشترک می‌توانند آن‌ها را به ترتیب معکوس قفل کنند و deadlock بدهند.

    این فقط وقتی معنا دارد که تراکنش تا لحظه‌ی نوشتن باز بماند — که مرز تراکنشِ
    سطح درخواست در get_db آن را تضمین می‌کند.
    """
    ids = sorted(set(item_ids))
    if not ids:
        return
    db.query(Item.id).filter(Item.id.in_(ids)).order_by(Item.id).with_for_update().all()


def post_sales_invoice(
    db: Session, data: SalesInvoiceIn, user: User, *, enforce_credit: bool = True
) -> SalesInvoice:
    """فاکتورِ فروش را ثبت می‌کند.

    `enforce_credit=False` فقط برای همگام‌سازیِ فاکتورِ **آفلاین** است: آن فروش
    قبلاً انجام شده و کالایش رفته؛ ردّش سرِ همگام‌سازی یعنی نابودکردنِ کارِ
    فروشنده. شرحِ کامل در [گاردِ اعتبار](credit.py).
    """
    assert_period_open(db, data.invoice_date)
    #: §۱۵ — انبارِ غیرفعال در ثبتِ تازه انتخاب نمی‌شود. تا امروز این پرچم فقط در
    #: رسیدِ انبارِ خرید سنجیده می‌شد، پس «غیرفعال» یک برچسبِ نیمه‌کاره بود.
    warehouses.assert_usable(db, data.warehouse_id, action="فاکتور فروش")

    items_by_id = {item.id: item for item in db.query(Item).filter(Item.id.in_([l.item_id for l in data.lines])).all()}

    # مقدار درخواستی هر کالا باید بین ردیف‌ها جمع شود، نه ردیف‌به‌ردیف سنجیده شود:
    # وگرنه فاکتوری با دو ردیف ۶تایی از یک کالا در برابر موجودی ۱۰ پاس می‌شد، چون هر
    # ردیف جدا با همان ۱۰ مقایسه می‌شد. این تک‌نخی هم رخ می‌داد و نیازی به همزمانی نداشت.
    requested_by_item: dict[UUID, Decimal] = {}
    for line in data.lines:
        item = items_by_id.get(line.item_id)
        if item is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کالا با شناسه {line.item_id} یافت نشد")
        if not item.is_service:
            requested_by_item[line.item_id] = requested_by_item.get(line.item_id, Decimal(0)) + line.qty

    # قفل قبل از خواندن موجودی: وگرنه دو فاکتور موازی هر دو همان موجودی را می‌خوانند،
    # هر دو پاس می‌شوند و موجودی منفی می‌شود — یعنی کالایی فروخته می‌شود که وجود ندارد.
    lock_items(db, requested_by_item.keys())

    for item_id, requested in requested_by_item.items():
        available = get_stock_qty(db, item_id, data.warehouse_id)
        if available < requested:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"موجودی «{items_by_id[item_id].name}» کافی نیست (موجود: {available}, درخواستی: {requested})",
            )

    number = next_document_number(db, DOC_SALES_INVOICE)

    # تخفیفِ کلِ فاکتور به‌نسبتِ خالصِ هر ردیف بینِ ردیف‌ها تسهیم می‌شود، پس درآمد،
    # پایه‌ی مالیات، بهای برگشت و بسته‌ی مؤدیان همگی خودکار درست می‌مانند — بدونِ نیاز
    # به منطقِ جدا در آن مسیرها.
    base_nets = [max((line.qty * line.unit_price) - Decimal(line.discount or 0), Decimal(0)) for line in data.lines]
    gross_net = sum(base_nets, Decimal(0))
    invoice_discount = Decimal(data.invoice_discount or 0)
    if invoice_discount > gross_net:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "تخفیفِ کلِ فاکتور نمی‌تواند از جمعِ خالصِ فاکتور بیشتر باشد"
        )
    allocated = _allocate_discount(invoice_discount, base_nets)

    total_amount = Decimal(0)
    total_discount = Decimal(0)
    total_cost = Decimal(0)
    invoice_lines: list[SalesInvoiceLine] = []
    stock_moves: list[StockLedger] = []

    for idx, line in enumerate(data.lines):
        item = items_by_id[line.item_id]
        unit_cost = item.average_cost if not item.is_service else Decimal(0)
        # تخفیفِ مؤثرِ ردیف = تخفیفِ خودِ ردیف + سهمِ تسهیم‌شده‌ی تخفیفِ کلِ فاکتور
        line_discount = Decimal(line.discount or 0) + allocated[idx]
        # خالصِ ردیف = ناخالص − تخفیف. جمعِ همین‌ها می‌شود total_amount، یعنی درآمد و
        # پایه‌ی مالیات هر دو «پس از تخفیف»اند.
        total_amount += (line.qty * line.unit_price) - line_discount
        total_discount += line_discount
        total_cost += line.qty * unit_cost
        invoice_lines.append(
            SalesInvoiceLine(
                item_id=line.item_id,
                qty=line.qty,
                unit_price=line.unit_price,
                discount=line_discount,
                unit_cost=unit_cost,
                description=line.description,
                #: وضعیتِ مالیاتی **در لحظه‌ی فروش** قفل می‌شود. اگر گزارش بعداً از
                #: خودِ کالا می‌خواند، معاف‌شدنِ امسالِ کالا فروشِ پارسال را هم معاف
                #: نشان می‌داد. همان دلیلی که `tax_amount` کنارِ `tax_rate` می‌نشیند.
                vat_status=item.vat_status,
            )
        )
        if not item.is_service:
            stock_moves.append(
                StockLedger(
                    item_id=line.item_id,
                    warehouse_id=data.warehouse_id,
                    qty=-line.qty,
                    unit_cost=unit_cost,
                    entry_date=data.invoice_date,
                    source_type="sales_invoice",
                )
            )

    tax_amount = compute_tax(total_amount, data.tax_rate)
    # گِرد کردن: تعدیلِ مبلغِ نهایی پس از مالیات. مبلغِ قابل‌پرداخت نباید منفی شود.
    rounding = Decimal(data.rounding or 0)
    if total_amount + tax_amount + rounding < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "گِرد کردن نمی‌تواند مبلغِ قابل‌پرداخت را منفی کند")

    #: گاردِ سقفِ اعتبار این‌جاست نه بالاتر، چون به مبلغِ نهایی (پس از تخفیف، مالیات
    #: و گِرد) نیاز دارد — همان عددی که واقعاً به حسابِ دریافتنی می‌نشیند.
    assert_within_credit_limit(
        db, data.contact_id, total_amount + tax_amount + rounding, enforce=enforce_credit
    )

    broker_id, broker_commission = resolve_broker(db, data.broker_id, total_amount)
    salesperson_id = resolve_salesperson_id(db, data.salesperson_id)
    sale_type_id = resolve_sale_type_id(db, data.sale_type_id)

    cost_center_id = resolve_cost_center_id(db, data.cost_center_id)
    receivable_or_cash = _get_account(db, cc.ACCOUNTS_RECEIVABLE) if data.contact_id else _get_account(db, cc.CASH)
    journal_lines = [
        JournalLine(
            account_id=receivable_or_cash.id,
            debit=total_amount + tax_amount + rounding,  # مشتری خالص + مالیات ± گِرد را می‌پردازد
            credit=0,
            description="بابت فروش کالا/خدمت",
        ),
        JournalLine(
            account_id=_get_account(db, cc.SALES_REVENUE).id,
            debit=0,
            credit=total_amount,
            description="بابت فروش کالا/خدمت",
        ),
    ]
    if tax_amount > 0:
        journal_lines.append(
            JournalLine(
                account_id=vat_payable_account(db).id,
                debit=0,
                credit=tax_amount,
                description="مالیات بر ارزش افزوده فروش",
            )
        )
    if rounding != 0:
        # رند به بالا (rounding>0) درآمدِ ناچیز است → بستانکار؛ رند به پایین بدهکار.
        journal_lines.append(
            JournalLine(
                account_id=sales_rounding_account(db).id,
                debit=(-rounding if rounding < 0 else Decimal(0)),
                credit=(rounding if rounding > 0 else Decimal(0)),
                description="گِرد کردنِ مبلغِ فاکتور",
            )
        )
    if total_cost > 0:
        journal_lines.append(
            JournalLine(
                account_id=_get_account(db, cc.COGS).id,
                debit=total_cost,
                credit=0,
                description="بهای تمام‌شده کالای فروش‌رفته",
            )
        )
        journal_lines.append(
            JournalLine(
                #: معینِ **همان انبار** (§۹). اگر انبار نگاشتِ خودش را نداشته
                #: باشد، همان حسابِ پیش‌فرض برمی‌گردد — یعنی رفتارِ پیشین.
                account_id=warehouses.inventory_account_id(db, data.warehouse_id),
                debit=0,
                credit=total_cost,
                description="کسر از موجودی کالا بابت فروش",
            )
        )

    if cost_center_id is not None:
        for line in journal_lines:
            line.cost_center_id = cost_center_id

    entry_number = next_document_number(db, DOC_JOURNAL_ENTRY)
    journal_entry = JournalEntry(
        number=entry_number,
        entry_date=data.invoice_date,
        description=f"فاکتور فروش شماره {number}",
        source_type="sales_invoice",
        created_by_id=user.id,
        lines=number_lines(journal_lines),
    )
    tafsili.assert_entry_has_tafsili(db, journal_entry)
    db.add(journal_entry)
    db.flush()

    invoice = SalesInvoice(
        number=number,
        invoice_date=data.invoice_date,
        contact_id=data.contact_id,
        cost_center_id=cost_center_id,
        warehouse_id=data.warehouse_id,
        description=data.description,
        total_amount=total_amount,
        total_discount=total_discount,
        invoice_discount=invoice_discount,
        rounding=rounding,
        total_cost=total_cost,
        tax_rate=data.tax_rate,
        tax_amount=tax_amount,
        currency_code=(data.currency_code or None),
        exchange_rate=data.exchange_rate,
        journal_entry_id=journal_entry.id,
        source_order_id=data.source_order_id,
        broker_id=broker_id,
        broker_commission=broker_commission,
        salesperson_id=salesperson_id,
        sale_type_id=sale_type_id,
        created_by_id=user.id,
        lines=invoice_lines,
    )
    db.add(invoice)
    # flush اجباری است و تزئینی نیست: شناسه‌ی کلید اصلی با default=uuid4 در لحظه‌ی
    # INSERT ساخته می‌شود، نه موقع ساختن شیء. بدون این خط، مقدارِ خوانده‌شده None
    # است و حرکت انبار بی‌صدا بدون منشأ ذخیره می‌شود — کاردکس و ابطال هر دو می‌شکنند.
    db.flush()
    for move in stock_moves:
        move.source_id = invoice.id
        db.add(move)

    # کسبِ خودکارِ امتیازِ وفاداری — فقط اگر مشتری دارد و در تنظیماتِ CRM فعال باشد.
    # عمداً بی‌اثر بر مسیرِ اصلیِ فروش است (تابع خودش بی‌صدا رد می‌شود اگر غیرفعال باشد).
    from app.services import crm as crm_service

    crm_service.award_purchase_points(
        db, data.contact_id, total_amount + tax_amount + rounding, data.invoice_date, user
    )

    db.flush()
    db.refresh(invoice)
    return invoice


def post_purchase_invoice(db: Session, data: PurchaseInvoiceIn, user: User) -> PurchaseInvoice:
    assert_period_open(db, data.invoice_date)
    warehouses.assert_usable(db, data.warehouse_id, action="فاکتور خرید")

    if data.warehouse_id is None and data.contact_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "انتخاب تأمین‌کننده برای فاکتور خرید الزامی است")
    if data.warehouse_id is None and data.contact_id is not None:
        supplier = db.get(Contact, data.contact_id)
        if supplier is None or supplier.type not in ("supplier", "both"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "طرف حساب انتخاب‌شده تأمین‌کننده نیست")

    items_by_id = {item.id: item for item in db.query(Item).filter(Item.id.in_([l.item_id for l in data.lines])).all()}
    for line in data.lines:
        if line.item_id not in items_by_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کالا با شناسه {line.item_id} یافت نشد")

    # average_cost پایین‌تر read-modify-write می‌شود؛ بدون قفل، دو خرید هم‌زمان یکی
    # محاسبه‌ی دیگری را بازنویسی می‌کند و بهای تمام‌شده برای همیشه غلط می‌ماند.
    lock_items(db, [line.item_id for line in data.lines])

    number = next_document_number(db, DOC_PURCHASE_INVOICE)

    # تخفیفِ کلِ فاکتور به‌نسبتِ خالصِ هر ردیف تسهیم می‌شود، پس ارزش‌گذاریِ موجودی،
    # پایه‌ی مالیات و بهای برگشت همگی خودکار درست می‌مانند.
    base_nets = [
        max(
            (line.qty * line.unit_cost)
            - Decimal(line.discount or 0)
            + Decimal(line.addition or 0)
            + Decimal(line.duty_amount or 0),
            Decimal(0),
        )
        for line in data.lines
    ]
    gross_net = sum(base_nets, Decimal(0))
    invoice_discount = Decimal(data.invoice_discount or 0)
    if invoice_discount > gross_net:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "تخفیفِ کلِ فاکتور نمی‌تواند از جمعِ خالصِ فاکتور بیشتر باشد"
        )
    allocated = _allocate_discount(invoice_discount, base_nets)
    allocated_additions = _allocate_discount(Decimal(data.invoice_addition or 0), base_nets)
    allocated_duties = _allocate_discount(Decimal(data.duty_amount or 0), base_nets)

    total_amount = Decimal(0)
    total_discount = Decimal(0)
    total_additions = Decimal(0)
    total_duties = Decimal(0)
    invoice_lines: list[PurchaseInvoiceLine] = []
    stock_moves: list[StockLedger] = []
    # هر ردیفِ کالا یک «بارِ ورودی» جدا می‌سازد تا کسری/معیوب قابلِ ردیابی به همان بار باشد.
    batch_seeds: list[dict] = []

    for idx, line in enumerate(data.lines):
        item = items_by_id[line.item_id]
        line_discount = Decimal(line.discount or 0) + allocated[idx]
        line_addition = Decimal(line.addition or 0) + allocated_additions[idx]
        line_duty = Decimal(line.duty_amount or 0) + allocated_duties[idx]
        line_net = (line.qty * line.unit_cost) - line_discount + line_addition + line_duty
        # بهای واقعیِ تمام‌شده‌ی هر واحد پس از تخفیف. موجودی باید به همین ارزش‌گذاری
        # شود، وگرنه انبار گران‌تر از چیزی که پول داده‌ایم در دفاتر می‌نشیند و سودِ
        # فروشِ بعدی کمتر از واقع گزارش می‌شود.
        effective_unit_cost = (line_net / line.qty) if line.qty else Decimal(0)
        total_amount += line_net
        total_discount += line_discount
        invoice_lines.append(
            PurchaseInvoiceLine(
                item_id=line.item_id,
                qty=line.qty,
                unit_cost=line.unit_cost,  # قیمتِ فهرستِ تأمین‌کننده، همان‌طور که در فاکتورش هست
                discount=line_discount,
                addition=line_addition,
                duty_amount=line_duty,
                description=line.description,
                vat_status=item.vat_status,  # قفل در لحظه‌ی خرید — مثلِ فروش
                item_code_snapshot=item.sku,
                item_name_snapshot=item.name,
                unit_snapshot=item.unit,
                tax_rate_snapshot=data.tax_rate,
            )
        )
        total_additions += line_addition
        total_duties += line_duty
        # warehouse_id فقط مسیر سازگاریِ ثبت‌های قدیمی است. فاکتورهای جدید بدون آن
        # هیچ حرکت فیزیکی ندارند و بعداً از WarehouseReceipt وارد می‌شوند.
        if data.warehouse_id is not None and not item.is_service:
            existing_qty = get_total_stock_qty(db, item.id)
            new_qty = existing_qty + line.qty
            if new_qty > 0:
                item.average_cost = ((existing_qty * item.average_cost) + line_net) / new_qty
            stock_moves.append(
                StockLedger(
                    item_id=line.item_id,
                    warehouse_id=data.warehouse_id,
                    qty=line.qty,
                    unit_cost=effective_unit_cost,
                    entry_date=data.invoice_date,
                    source_type="purchase_invoice",
                )
            )
            batch_seeds.append(
                {
                    "item_id": line.item_id,
                    "qty": Decimal(line.qty),
                    "unit_cost": effective_unit_cost.quantize(Decimal(1)),
                    "idx": idx + 1,
                }
            )

    tax_amount = compute_tax(total_amount, data.tax_rate)
    taxable_weights = [
        Decimal(line.qty) * Decimal(line.unit_cost)
        - Decimal(line.discount)
        + Decimal(line.addition)
        + Decimal(line.duty_amount)
        for line in invoice_lines
    ]
    for line, share in zip(invoice_lines, _allocate_discount(tax_amount, taxable_weights), strict=True):
        line.tax_amount_snapshot = share
    cost_center_id = resolve_cost_center_id(db, data.cost_center_id)
    payable_or_cash = _get_account(db, cc.ACCOUNTS_PAYABLE) if data.contact_id else _get_account(db, cc.CASH)
    journal_lines = [
        JournalLine(
            account_id=warehouses.inventory_account_id(db, data.warehouse_id),
            debit=total_amount,
            credit=0,
            description="بابت خرید کالا",
        ),
    ]
    if tax_amount > 0:
        journal_lines.append(
            JournalLine(
                account_id=vat_receivable_account(db).id,
                debit=tax_amount,
                credit=0,
                description="مالیات بر ارزش افزوده خرید (اعتبار مالیاتی)",
            )
        )
    journal_lines.append(
        JournalLine(
            account_id=payable_or_cash.id,
            debit=0,
            credit=total_amount + tax_amount,  # به تأمین‌کننده خالص + مالیات پرداخت می‌شود
            description="بابت خرید کالا",
        )
    )

    if cost_center_id is not None:
        for line in journal_lines:
            line.cost_center_id = cost_center_id

    entry_number = next_document_number(db, DOC_JOURNAL_ENTRY)
    journal_entry = JournalEntry(
        number=entry_number,
        entry_date=data.invoice_date,
        description=f"فاکتور خرید شماره {number}",
        source_type="purchase_invoice",
        created_by_id=user.id,
        lines=number_lines(journal_lines),
    )
    tafsili.assert_entry_has_tafsili(db, journal_entry)
    db.add(journal_entry)
    db.flush()

    invoice = PurchaseInvoice(
        number=number,
        invoice_date=data.invoice_date,
        contact_id=data.contact_id,
        supplier_invoice_number=data.supplier_invoice_number.strip(),
        cost_center_id=cost_center_id,
        warehouse_id=data.warehouse_id,
        description=data.description,
        description2=data.description2,
        total_amount=total_amount,
        total_discount=total_discount,
        invoice_discount=invoice_discount,
        total_additions=total_additions,
        total_duties=total_duties,
        tax_rate=data.tax_rate,
        tax_amount=tax_amount,
        currency_code=(data.currency_code or None),
        exchange_rate=data.exchange_rate,
        journal_entry_id=journal_entry.id,
        created_by_id=user.id,
        lines=invoice_lines,
    )
    db.add(invoice)
    # flush اجباری است و تزئینی نیست: شناسه‌ی کلید اصلی با default=uuid4 در لحظه‌ی
    # INSERT ساخته می‌شود، نه موقع ساختن شیء. بدون این خط، مقدارِ خوانده‌شده None
    # است و حرکت انبار بی‌صدا بدون منشأ ذخیره می‌شود — کاردکس و ابطال هر دو می‌شکنند.
    db.flush()
    for move in stock_moves:
        move.source_id = invoice.id
        db.add(move)

    # یک بارِ ورودی به‌ازای هر ردیفِ کالا (نه خدمت). شماره‌ی بار خودکار = P{شماره‌فاکتور}-{ردیف}؛
    # اپراتور بعداً می‌تواند سریالِ کارتن و کسری/معیوب را روی همین بار ثبت کند.
    for seed in batch_seeds:
        db.add(
            StockBatch(
                item_id=seed["item_id"],
                warehouse_id=data.warehouse_id,
                batch_number=f"P{number}-{seed['idx']}",
                qty=seed["qty"],
                received_qty=seed["qty"],
                unit_cost=seed["unit_cost"],
                source_type="purchase_invoice",
                source_id=invoice.id,
                received_date=data.invoice_date,
                created_by_id=user.id,
            )
        )

    db.flush()
    db.refresh(invoice)
    return invoice


def post_stock_adjustment(db: Session, data: StockAdjustmentIn, user: User) -> StockAdjustment:
    assert_period_open(db, data.adjustment_date)
    warehouses.assert_usable(db, data.warehouse_id, action="تعدیل موجودی")

    item = db.get(Item, data.item_id)
    if item is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کالا یافت نشد")
    if item.is_service:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "خدمت موجودی ندارد که تعدیل شود")

    if data.qty_diff < 0:
        available = get_stock_qty(db, data.item_id, data.warehouse_id)
        if available < abs(data.qty_diff):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"موجودی «{item.name}» برای این میزان کسری کافی نیست (موجود: {available})",
            )

    unit_cost = item.average_cost
    amount = abs(data.qty_diff) * unit_cost

    # کسری: بدهکار حساب مغایرت انبار (هزینه)، بستانکار موجودی کالا. اضافی: برعکس (کاهش هزینه‌ی مغایرت).
    #: سمتِ موجودی از معینِ همان انبار می‌آید؛ سمتِ مغایرت حسابِ هزینه‌ای است و
    #: به انبار ربطی ندارد.
    inventory_account_id = warehouses.inventory_account_id(db, data.warehouse_id)
    adjustment_account_id = _get_account(db, cc.INVENTORY_ADJUSTMENT).id
    if data.qty_diff < 0:
        debit_id, credit_id = adjustment_account_id, inventory_account_id
    else:
        debit_id, credit_id = inventory_account_id, adjustment_account_id

    journal_entry = None
    if amount > 0:
        entry_number = next_document_number(db, DOC_JOURNAL_ENTRY)
        journal_entry = JournalEntry(
            number=entry_number,
            entry_date=data.adjustment_date,
            description=f"تعدیل موجودی «{item.name}»: {data.reason}".strip(),
            source_type="stock_adjustment",
            created_by_id=user.id,
            lines=number_lines([
                JournalLine(account_id=debit_id, debit=amount, credit=0),
                JournalLine(account_id=credit_id, debit=0, credit=amount),
            ]),
        )
        tafsili.assert_entry_has_tafsili(db, journal_entry)
        db.add(journal_entry)
        db.flush()

    adjustment = StockAdjustment(
        item_id=data.item_id,
        warehouse_id=data.warehouse_id,
        qty_diff=data.qty_diff,
        unit_cost=unit_cost,
        reason=data.reason,
        adjustment_date=data.adjustment_date,
        journal_entry_id=journal_entry.id if journal_entry else None,
        created_by_id=user.id,
    )
    db.add(adjustment)
    db.add(
        StockLedger(
            item_id=data.item_id,
            warehouse_id=data.warehouse_id,
            qty=data.qty_diff,
            unit_cost=unit_cost,
            entry_date=data.adjustment_date,
            source_type="adjustment",
        )
    )
    db.flush()
    db.refresh(adjustment)
    return adjustment
