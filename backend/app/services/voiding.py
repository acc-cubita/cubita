"""ابطال سند — با ثبت معکوس، نه با حذف.

بزرگ‌ترین شکاف کارکردی سیستم تا امروز: هیچ راهی برای تصحیح فاکتور اشتباه وجود
نداشت. نه ابطال، نه ویرایش، نه حتی حذف. اولین حسابداری که شماره را اشتباه می‌زد
تنها راهش دست بردن مستقیم در پایگاه‌داده بود.

**اصل حاکم: هرگز حذف نکن.** دفتر باید نشان دهد چه اتفاقی افتاد و بعد چطور اصلاح
شد. سند اصلی سر جایش می‌ماند، یک سند معکوس ثبت می‌شود، و هر دو در دفتر روزنامه
دیده می‌شوند. جمعشان صفر است و همین ردِ حسابرسی است — چیزی که حذف کردن از بین
می‌برد و برای نرم‌افزار حسابداری قابل قبول نیست.

سه اثری که باید برگردند و ترتیبشان مهم است:
  ۱. اثر حسابداری  → سند معکوس با بدهکار/بستانکار جابه‌جا‌شده
  ۲. اثر انبار     → ردیف‌های جبرانی در دفتر موجودی (append-only حفظ می‌شود)
  ۳. بهای تمام‌شده → بازمحاسبه‌ی میانگین موزون با بازپخش دفتر
"""
from datetime import date as date_
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalLine
from app.models.advanced_inventory import StockBatch
from app.models.counters import DOC_JOURNAL_ENTRY
from app.models.inventory import Item, StockAdjustment, StockLedger
from app.models.invoices import PurchaseInvoice, SalesInvoice, WarehouseIssue
from app.models.returns import PurchaseReturn, SalesReturn
from app.models.user import User
from app.services import valuation
from app.services.common import number_lines
from app.services.inventory import lock_items
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open

#: منشأ ردیف‌های جبرانی دفتر موجودی. جدا از منشأ اصلی نگه داشته می‌شود تا در
#: گزارش کاردکس معلوم باشد این حرکت، اصلاح است نه یک خرید/فروش تازه.
VOID_SOURCE = valuation.VOID_SOURCE


def _reverse_lines(entry: JournalEntry) -> list[JournalLine]:
    """همان ردیف‌ها با بدهکار و بستانکار جابه‌جا‌شده.

    مبالغ عیناً کپی می‌شوند و دوباره محاسبه نمی‌شوند: سند معکوس باید *دقیقاً* اثر
    سند اصلی را خنثی کند. اگر مبلغ از روی داده‌ی امروز دوباره محاسبه می‌شد — مثلاً
    از روی average_cost فعلی — و آن داده از زمان ثبت عوض شده بود، معکوس با اصل
    برابر نمی‌شد و یک اختلاف دائمی در دفتر می‌ماند.
    """
    return [
        JournalLine(
            account_id=line.account_id,
            # ابعادِ ردیف هم عیناً منتقل می‌شوند: اگر معکوس بدونِ مرکز/تفصیلی/ارز ثبت
            # شود، گزارشِ همان بُعد یک‌طرفه می‌ماند — هزینه‌ی پروژه برمی‌گردد ولی
            # مانده‌ی ارزیِ حساب نه.
            cost_center_id=line.cost_center_id,
            analytic_id=line.analytic_id,
            debit=line.credit,
            credit=line.debit,
            description=f"برگشت: {line.description}",
            currency_code=line.currency_code,
            fx_amount=line.fx_amount,
            fx_rate=line.fx_rate,
            # پیگیری هم منتقل می‌شود: سندِ برگشتی باید با همان ارجاع پیدا شود که
            # سندِ اصلی. اگر نمی‌رفت، جستجوی «شماره‌ی حواله» فقط نصفِ ماجرا را
            # می‌آورد و مانده‌ی صفرشده نامرئی می‌ماند.
            tracking_no=line.tracking_no,
            tracking_date=line.tracking_date,
        )
        for line in entry.lines
    ]


def reverse_journal_entry(
    db: Session, entry: JournalEntry, *, void_date: date_, user: User, description: str
) -> JournalEntry:
    reversal = JournalEntry(
        number=next_document_number(db, DOC_JOURNAL_ENTRY),
        entry_date=void_date,
        description=description,
        source_type=f"void_{entry.source_type}",
        source_id=entry.source_id,
        reverses_entry_id=entry.id,
        created_by_id=user.id,
        lines=number_lines(_reverse_lines(entry)),
    )
    db.add(reversal)
    db.flush()
    return reversal


def _voided_sources(db: Session) -> set:
    """کلیدِ (نوع، شناسه) هر سندی که باطل شده.

    فهرستِ اسنادِ ابطال‌پذیر و دلیلِ هر ردیفش حالا در `valuation` است: بازپخشِ
    میانگین، گاردِ خطِ زمان و گزارشِ ارزش هر سه همان را می‌خوانند. دو فهرستِ موازی
    دقیقاً همان‌جایی است که سندِ تازه در یکی ثبت می‌شد و در دیگری نه.
    """
    return valuation.voided_sources(db)


def recompute_average_cost(db: Session, item: Item) -> None:
    """میانگین موزون را با بازپخشِ دفتر، **طوری که انگار اسناد باطل هرگز نبودند**، می‌سازد.

    **چرا بازپخش و نه فرمول معکوس:** میانگین موزون تجمعی است و اثر یک خرید را
    نمی‌شود با فرمول از آن «کم کرد»، چون خریدهای بعدی روی همان میانگین سوار شده‌اند.
    هر معکوس‌سازی جبری خطا انباشته می‌کند و بهای تمام‌شده برای همیشه کمی غلط می‌ماند
    بدون اینکه کسی بفهمد.

    **چرا حرکاتِ اسناد باطل حذف می‌شوند و نه اینکه ردیف جبرانی بازپخش شود:** ردیف
    جبرانیِ ابطالِ یک *خرید* یک خروج است، و خروج در میانگین موزون هیچ اثری ندارد.
    پس بازپخشِ ساده، میانگین را روی همان عدد آلوده نگه می‌داشت. تعریف درست این است
    که «میانگین باید همانی باشد که اگر آن سند اصلاً ثبت نشده بود می‌شد» — و آن
    یعنی حذفِ خودِ حرکت از بازپخش، نه جبرانش.

    این تفاوت با تست گرفته می‌شود: خرید ۱۰@۱۰۰۰ سپس ۱۰@۲۰۰۰ میانگین را ۱۵۰۰
    می‌کند؛ ابطال خرید دوم باید ۱۰۰۰ بدهد، و بازپخشِ ساده ۱۵۰۰ می‌داد.

    ترتیب **(تاریخِ سند، seq)** است (فصلِ «قیمت‌گذاری اسناد انبار»): شناسه UUID
    تصادفی است و `seq` به‌تنها ترتیبِ *ثبت* است نه ترتیبِ *زمان* — سندِ پیش‌تاریخ با
    `seq` بعد از اسنادی می‌نشست که در زمان پیش از آن‌ها بوده. تعریفِ کامل و قاعده‌ی
    هر نوع حرکت (از جمله برگشت از خرید که با بهای خودش بیرون می‌رود) در `valuation`
    است؛ این تابع همان را صدا می‌زند تا دو تعریف از میانگین وجود نداشته باشد.
    """
    valuation.recompute(db, item)


def _compensating_moves(db: Session, source_type: str, source_id: UUID, void_date: date_) -> list[StockLedger]:
    """برای هر حرکت انبارِ سند، یک حرکت قرینه می‌سازد."""
    original = (
        db.query(StockLedger)
        .filter(StockLedger.source_type == source_type, StockLedger.source_id == source_id)
        .all()
    )
    return [
        StockLedger(
            item_id=move.item_id,
            warehouse_id=move.warehouse_id,
            qty=-Decimal(move.qty),
            unit_cost=move.unit_cost,
            entry_date=void_date,
            source_type=VOID_SOURCE,
            source_id=source_id,
            #: **برچسبِ بار با حرکتِ قرینه می‌آید.** بی این، ابطال موجودی را از
            #: بارش جدا می‌کرد: عددِ کالا درست برمی‌گشت ولی مانده‌ی بار همان‌جا
            #: می‌ماند — و چون هیچ خطایی نمی‌داد، تا اولین گزارشِ مغایرت کسی
            #: خبردار نمی‌شد.
            batch_id=move.batch_id,
            source_line_id=move.source_line_id,
        )
        for move in original
    ]


def _guard_not_already_voided(document) -> None:
    if document.is_voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "این سند قبلاً باطل شده است")


def _guard_no_active_returns(db: Session, document, source_type: str) -> None:
    """ابطالِ فاکتوری که برگشت خورده را می‌بندد.

    ابطال، خودش کلِ فاکتور را معکوس می‌کند؛ اگر برگشتی هم روی همان فاکتور ثبت شده
    باشد، همان فروش/خرید **دوبار** برمی‌گردد و ماندهٔ صندوق/فروش (یا خرید) منفیِ
    بی‌معنا می‌شود. کاربر باید اول سندِ برگشت را برگرداند، بعد فاکتور را باطل کند.

    **فقط برگشتِ فعال می‌بندد.** تا پیش از مهاجرتِ ۰۱۲۱ برگشت اصلاً ابطال نداشت،
    پس این گارد کاری را می‌خواست که هیچ راهی برایش نبود: یک برگشتِ اشتباهی
    فاکتورش را **برای همیشه** قفل می‌کرد. حالا ابطالِ برگشت قفل را باز می‌کند.
    """
    if source_type == "sales_invoice":
        has_return = (
            db.query(SalesReturn.id)
            .filter(SalesReturn.sales_invoice_id == document.id, SalesReturn.voided_at.is_(None))
            .first()
        )
        kind = "برگشت از فروش"
    elif source_type == "purchase_invoice":
        has_return = (
            db.query(PurchaseReturn.id)
            .filter(
                PurchaseReturn.purchase_invoice_id == document.id,
                PurchaseReturn.voided_at.is_(None),
            )
            .first()
        )
        kind = "برگشت از خرید"
    else:
        return
    if has_return is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"این فاکتور «{kind}» دارد؛ ابطال، فروش را دوباره برمی‌گرداند. "
            "اول سندِ برگشت را باطل کنید، سپس فاکتور را باطل کنید.",
        )


def guard_no_active_allocations(db: Session, source_type: str, source_id: UUID, label: str) -> None:
    """ابطالِ سندی که در تسویه‌ای تخصیص خورده را می‌بندد (§۴۱).

    تسویه سندِ حسابداری نمی‌زند، پس اگر این سند بی‌سروصدا باطل شود هیچ ترازی به‌هم
    نمی‌خورد تا خطا را لو بدهد: تخصیص روی سندی می‌ماند که دیگر مانده‌ای ندارد و
    «تسویه‌شده»ی طرف حساب برای همیشه از واقعیت جلو می‌افتد.

    راهِ درست برای کاربر همان چیزی است که پیام می‌گوید: اول تسویه را برگرداند
    (که فقط رابطه را آزاد می‌کند و هیچ سندی را حذف نمی‌کند)، بعد این را باطل کند.
    """
    from app.services.open_items import active_allocation_total

    allocated = active_allocation_total(db, source_type, source_id)
    if allocated > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"این {label} در «تسویه حساب طرف مقابل» تخصیص خورده است. "
            "اول تسویه‌های مربوط را برگردانید، سپس سند را باطل کنید.",
        )


def _guard_stock_stays_valid(db: Session, moves: list[StockLedger]) -> None:
    """ابطالی که موجودی را منفی کند رد می‌شود.

    این وقتی پیش می‌آید که فاکتور خریدی باطل شود که کالایش قبلاً فروخته شده. اجازه
    دادنش یعنی دفتر موجودی عددی منفی نشان دهد که هیچ معنای فیزیکی ندارد و
    بهای تمام‌شده‌ی فروش‌های بعدی را هم خراب می‌کند.

    راه درست برای کاربر این است که اول فاکتور فروش را باطل کند و بعد خرید را —
    و پیام خطا همین را می‌گوید، چون «عملیات ناموفق» بدون توضیح، کاربر را گیر
    می‌اندازد.
    """
    from app.services.inventory import get_stock_qty

    for move in moves:
        if Decimal(move.qty) >= 0:
            continue
        available = get_stock_qty(db, move.item_id, move.warehouse_id)
        if available + Decimal(move.qty) < 0:
            item = db.get(Item, move.item_id)
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"ابطال این سند موجودی «{item.name if item else move.item_id}» را منفی می‌کند "
                f"(موجودی فعلی: {available}). احتمالاً این کالا بعداً فروخته شده؛ "
                "اول فاکتور فروش مربوطه را باطل کنید.",
            )


def _apply_void(
    db: Session,
    document,
    *,
    source_type: str,
    label: str,
    void_date: date_ | None,
    reason: str,
    user: User,
) -> JournalEntry:
    """مسیر مشترک ابطال برای هر سندی که سند حسابداری و اثر انبار دارد."""
    _guard_not_already_voided(document)
    _guard_no_active_returns(db, document, source_type)
    guard_no_active_allocations(db, source_type, document.id, label)

    # تاریخ ابطال پیش‌فرض همان تاریخ سند است، ولی اگر آن دوره بسته شده باشد کاربر
    # باید تاریخی در دوره‌ی باز بدهد. گارد روی تاریخِ *معکوس* اجرا می‌شود نه تاریخ
    # سند اصلی — چون چیزی که الان نوشته می‌شود همان است.
    #
    # فاکتور `invoice_date` دارد و برگشت `return_date`؛ همین یک دسترسی کافی بود
    # تا کلِ این مسیر برای برگشت هم بازاستفاده شود و ابطالِ دوم نوشته نشود.
    effective_date = void_date or getattr(document, "invoice_date", None) or document.return_date
    assert_period_open(db, effective_date)

    entry = db.get(JournalEntry, document.journal_entry_id) if document.journal_entry_id else None
    if entry is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "این سند، سند حسابداری متناظر ندارد و قابل ابطال نیست"
        )

    moves = _compensating_moves(db, source_type, document.id, effective_date)
    affected_items = sorted({m.item_id for m in moves})
    # قفل قبل از خواندن موجودی و قبل از بازمحاسبه‌ی میانگین: بدون آن، ابطال و یک
    # فاکتور هم‌زمان می‌توانند محاسبه‌ی یکدیگر را بازنویسی کنند.
    lock_items(db, affected_items)
    _guard_stock_stays_valid(db, moves)
    #: گاردِ بالا موجودیِ امروز را می‌بیند؛ این یکی خطِ زمان را — خروجی که بعد از این
    #: ورود و به پشتوانه‌ی آن رفته، با ابطال بی‌پشتوانه نشود.
    valuation.guard_void(db, (source_type,), document.id)

    reversal = reverse_journal_entry(
        db,
        entry,
        void_date=effective_date,
        user=user,
        description=f"ابطال {label} شماره {document.number}"
        + (f" — {reason}" if reason.strip() else ""),
    )

    for move in moves:
        db.add(move)

    # ترتیب اهمیت دارد: علامتِ ابطال باید **قبل از** بازمحاسبه بنشیند، چون
    # recompute_average_cost حرکاتِ اسنادِ باطل را کنار می‌گذارد و اگر هنوز باطل
    # علامت نخورده باشد، همان سندی که داریم باطلش می‌کنیم در محاسبه می‌ماند و
    # میانگین روی عدد آلوده باقی می‌ماند.
    document.voided_at = datetime.now(timezone.utc)
    document.voided_by_id = user.id
    document.void_reason = reason.strip()
    db.flush()

    valuation.settle_void(db, affected_items)
    return reversal


def void_sales_invoice(
    db: Session, invoice_id: UUID, *, reason: str, user: User, void_date: date_ | None = None
) -> JournalEntry | None:
    invoice = db.get(SalesInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور فروش یافت نشد")
    from app.services.warehouse_issues import detach_direct_issues

    #: خروجِ مستقلی که فاکتور گرفته جدا می‌شود، نه باطل — پیش از آبشارِ پایین.
    detach_direct_issues(db, invoice)
    if invoice.journal_entry_id is None:
        _guard_not_already_voided(invoice)
        _guard_no_active_returns(db, invoice, "sales_invoice")
        invoice.voided_at = datetime.now(timezone.utc)
        invoice.voided_by_id = user.id
        invoice.void_reason = reason.strip()
        db.flush()
        return None
    # سازگاریِ مسیر سرویس قدیمی که فروش فوری را یک‌مرحله‌ای می‌ساخت: اسنادِ خروج
    # همچنان جدا و با معکوس خودشان باطل می‌شوند. مسیر HTTP جدید قبل از رسیدن به
    # این تابع وابستگی فعال را مسدود می‌کند و از کاربر اقدام صریح می‌خواهد.
    active_issues = db.query(WarehouseIssue).filter(
        WarehouseIssue.sales_invoice_id == invoice.id,
        WarehouseIssue.voided_at.is_(None),
    ).all()
    if active_issues:
        from app.services.warehouse_issues import void_warehouse_issue

        for issue in active_issues:
            void_warehouse_issue(
                db, issue.id, reason=reason, user=user,
                void_date=void_date or invoice.invoice_date,
                #: گاردِ برگشتِ خودِ فاکتور در `_apply_void` می‌آید؛ پیامِ همان بماند.
                guard_returns=False,
            )
    return _apply_void(
        db,
        invoice,
        source_type="sales_invoice",
        label="فاکتور فروش",
        void_date=void_date,
        reason=reason,
        user=user,
    )


def void_purchase_invoice(
    db: Session, invoice_id: UUID, *, reason: str, user: User, void_date: date_ | None = None
) -> JournalEntry:
    invoice = db.get(PurchaseInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور خرید یافت نشد")
    return _apply_void(
        db,
        invoice,
        source_type="purchase_invoice",
        label="فاکتور خرید",
        void_date=void_date,
        reason=reason,
        user=user,
    )


def void_sales_return(
    db: Session, return_id: UUID, *, reason: str, user: User, void_date: date_ | None = None
) -> JournalEntry:
    """ابطالِ برگشت از فروش (§۷۱–§۷۸) — از همان مسیرِ مشترک.

    هیچ گاردِ تازه‌ای لازم نشد و این عمدی است: `_apply_void` از قبل ابطالِ دوباره،
    تخصیصِ فعالِ تسویه، منفی‌نشدنِ موجودی، بازبودنِ دوره و بازمحاسبه‌ی میانگین را
    می‌سنجد. تنها چیزی که برگشت اضافه می‌کند این است که ماندهٔ قابلِ برگشتِ
    فاکتور خودبه‌خود برمی‌گردد (§۷۶) — چون مشتق است، نه شمارنده.
    """
    document = db.get(SalesReturn, return_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سند برگشت از فروش یافت نشد")
    if document.stock_mode == "issue_return" and document.voided_at is None:
        #: کالا را «برگشت خروج انبار» برگردانده، نه این سند. برگشتی که همین سند ساخته
        #: همراهش باطل می‌شود؛ برگشتی که کاربر ثبت کرده جلوی ابطال را می‌گیرد.
        from app.services.issue_returns import release_for_sales_return

        release_for_sales_return(db, document, reason=reason, user=user, void_date=void_date)
    return _apply_void(
        db,
        document,
        source_type="sales_return",
        label="برگشت از فروش",
        void_date=void_date,
        reason=reason,
        user=user,
    )


def void_purchase_return(
    db: Session, return_id: UUID, *, reason: str, user: User, void_date: date_ | None = None
) -> JournalEntry:
    """قرینه‌ی `void_sales_return` برای خرید."""
    document = db.get(PurchaseReturn, return_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سند برگشت از خرید یافت نشد")
    return _apply_void(
        db,
        document,
        source_type="purchase_return",
        label="برگشت از خرید",
        void_date=void_date,
        reason=reason,
        user=user,
    )


def void_journal_entry(
    db: Session, entry_id: UUID, *, reason: str, user: User, void_date: date_ | None = None
) -> JournalEntry:
    """ابطال سند دستی.

    فقط سند دستی: سندی که یک فاکتور ساخته باید از راه ابطال خودِ فاکتور برگردد،
    وگرنه فاکتور در ظاهر معتبر می‌ماند در حالی که اثر مالی‌اش برگشته — و انبار
    هم اصلاً برنمی‌گردد.
    """
    entry = db.get(JournalEntry, entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سند یافت نشد")
    _guard_not_already_voided(entry)

    if entry.source_type != "manual":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"این سند را ماژول «{entry.source_type}» ساخته است؛ باید همان سند اصلی را باطل کنید نه سند حسابداری‌اش",
        )
    if entry.reverses_entry_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "سند برگشتی را نمی‌توان دوباره باطل کرد")

    effective_date = void_date or entry.entry_date
    assert_period_open(db, effective_date)

    reversal = reverse_journal_entry(
        db,
        entry,
        void_date=effective_date,
        user=user,
        description=f"ابطال سند شماره {entry.number}" + (f" — {reason}" if reason.strip() else ""),
    )
    entry.voided_at = datetime.now(timezone.utc)
    entry.voided_by_id = user.id
    entry.void_reason = reason.strip()
    db.flush()
    return reversal


def void_stock_adjustment(
    db: Session, adjustment_id: UUID, *, reason: str, user: User, void_date: date_ | None = None
) -> JournalEntry | None:
    """ابطالِ تعدیلِ انبار — سندی که کارش اصلاح است و تا امروز خودش اصلاح نمی‌شد.

    تنها راهِ پیشین، ثبتِ یک تعدیلِ معکوسِ دوم بود. آن کار عدد را درست می‌کرد ولی
    **تاریخچه را دروغ می‌گفت**: کاردکسِ کالا دو تعدیلِ واقعی نشان می‌داد، بی هیچ
    نشانه‌ای که دومی اشتباهِ اولی را می‌پوشاند. ابطال هر دو را اعتراف می‌کند.

    سه تفاوت با `_apply_void` که این تابع را جدا نگه داشت:

    * تعدیل **شماره ندارد** و تاریخش `adjustment_date` است، نه `invoice_date`.
    * تعدیلی که بهای واحدش صفر بوده سندِ حسابداری **ندارد** — و این حالتِ درستی
      است، نه نقص. `_apply_void` آن را ۴۰۹ می‌کند؛ این‌جا فقط حرکتِ انبار برمی‌گردد.
    * تعدیلِ گره‌خورده به یک بار، `stock_batches.qty` را کم کرده؛ ابطال باید همان
      را برگرداند وگرنه باقی‌مانده‌ی بار برای همیشه کم می‌ماند.
    """
    adjustment = (
        db.query(StockAdjustment)
        .filter(StockAdjustment.id == adjustment_id)
        .with_for_update()
        .one_or_none()
    )
    if adjustment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تعدیل موجودی یافت نشد")
    _guard_not_already_voided(adjustment)

    effective_date = void_date or adjustment.adjustment_date
    assert_period_open(db, effective_date)

    moves = _compensating_moves(db, "adjustment", adjustment.id, effective_date)
    if not moves:
        #: حرکتِ انبارِ این تعدیل پیدا نشد. پیش از مهاجرتِ ۰۱۵۸ حرکت‌ها `source_id`
        #: نداشتند؛ اگر پُرکردنِ آن مهاجرت ردیفی را جا گذاشته باشد، ابطال باید
        #: **بایستد**، نه اینکه سندِ حسابداری را برگرداند و دفترِ انبار را دست‌نخورده
        #: بگذارد — آن حالت، مغایرتِ خاموشِ موجودی و حسابداری است.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "حرکتِ انبارِ این تعدیل در دفتر پیدا نشد؛ ابطالش دفترِ انبار و حسابداری را "
            "از هم جدا می‌کرد. لطفاً گزارش کنید.",
        )

    affected_items = sorted({move.item_id for move in moves})
    lock_items(db, affected_items)
    _guard_stock_stays_valid(db, moves)
    #: ابطالِ تعدیلِ *اضافی* موجودی را برمی‌دارد؛ خروجی که به پشتوانه‌ی آن رفته
    #: نباید بی‌پشتوانه شود. (تعدیلِ کسری همیشه بی‌خطر است — برگشتش فقط اضافه می‌کند.)
    valuation.guard_void(db, ("adjustment",), adjustment.id)

    reversal = None
    entry = db.get(JournalEntry, adjustment.journal_entry_id) if adjustment.journal_entry_id else None
    if entry is not None:
        item = db.get(Item, adjustment.item_id)
        reversal = reverse_journal_entry(
            db,
            entry,
            void_date=effective_date,
            user=user,
            description=f"ابطال تعدیل موجودی «{item.name if item else ''}»".strip()
            + (f" — {reason.strip()}" if reason.strip() else ""),
        )

    for move in moves:
        db.add(move)

    if adjustment.batch_id is not None:
        batch = db.get(StockBatch, adjustment.batch_id)
        if batch is not None:
            #: تعدیلِ بار همیشه کسری است (`qty_diff` منفی)، پس برگرداندنش یعنی
            #: افزودنِ همان قدرمطلق به باقی‌مانده‌ی بار.
            batch.qty = Decimal(batch.qty or 0) + abs(Decimal(adjustment.qty_diff))

    #: علامتِ ابطال پیش از بازمحاسبه — همان ترتیبِ `_apply_void`: بازپخشِ میانگین
    #: حرکاتِ سندِ باطل را کنار می‌گذارد و اگر علامت هنوز ننشسته باشد، همین سند در
    #: محاسبه می‌ماند و میانگین آلوده بیرون می‌آید.
    adjustment.voided_at = datetime.now(timezone.utc)
    adjustment.voided_by_id = user.id
    adjustment.void_reason = reason.strip()
    db.flush()

    valuation.settle_void(db, affected_items)
    return reversal
