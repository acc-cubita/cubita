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
from app.models.counters import DOC_JOURNAL_ENTRY
from app.models.inventory import Item, StockLedger
from app.models.invoices import PurchaseInvoice, SalesInvoice, WarehouseReceipt
from app.models.returns import PurchaseReturn, SalesReturn
from app.models.user import User
from app.services.common import number_lines
from app.services.inventory import lock_items
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open

#: منشأ ردیف‌های جبرانی دفتر موجودی. جدا از منشأ اصلی نگه داشته می‌شود تا در
#: گزارش کاردکس معلوم باشد این حرکت، اصلاح است نه یک خرید/فروش تازه.
VOID_SOURCE = "void"


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
    """کلیدِ (نوع، شناسه) هر سندی که باطل شده."""
    voided = set()
    for model, source_type in (
        (SalesInvoice, "sales_invoice"),
        (PurchaseInvoice, "purchase_invoice"),
        (WarehouseReceipt, "warehouse_receipt"),
    ):
        for (doc_id,) in db.query(model.id).filter(model.voided_at.isnot(None)).all():
            voided.add((source_type, doc_id))
    return voided


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

    ترتیب با `seq` گرفته می‌شود و نه با شناسه یا تاریخ: شناسه UUID تصادفی است و
    تاریخ فقط روز را دارد. با ترتیب غیرقطعی، همین تابع می‌توانست هر بار عدد
    متفاوتی بدهد — که در اجرای کامل تست‌ها دقیقاً همین اتفاق افتاد.
    """
    ignored = _voided_sources(db)

    moves = (
        db.query(StockLedger)
        .filter(StockLedger.item_id == item.id)
        .order_by(StockLedger.seq)
        .all()
    )

    qty = Decimal(0)
    average = Decimal(0)
    for move in moves:
        if move.source_type == VOID_SOURCE:
            continue  # ردیف جبرانی؛ خودِ حرکتِ اصلی پایین‌تر نادیده گرفته می‌شود
        if (move.source_type, move.source_id) in ignored:
            continue  # سندش باطل شده — انگار هرگز نبوده

        move_qty = Decimal(move.qty)
        if move_qty > 0:
            new_qty = qty + move_qty
            if new_qty > 0:
                average = ((qty * average) + (move_qty * Decimal(move.unit_cost))) / new_qty
            qty = new_qty
        else:
            # خروج، میانگین را عوض نمی‌کند — فقط مقدار را کم می‌کند.
            qty += move_qty

    item.average_cost = average


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
    """
    if source_type == "sales_invoice":
        has_return = db.query(SalesReturn.id).filter(SalesReturn.sales_invoice_id == document.id).first()
        kind = "برگشت از فروش"
    elif source_type == "purchase_invoice":
        has_return = db.query(PurchaseReturn.id).filter(PurchaseReturn.purchase_invoice_id == document.id).first()
        kind = "برگشت از خرید"
    else:
        return
    if has_return is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"این فاکتور «{kind}» دارد؛ ابطال، فروش را دوباره برمی‌گرداند. "
            "اول سندِ برگشت را حذف/برگردانید، سپس فاکتور را باطل کنید.",
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
    effective_date = void_date or document.invoice_date
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

    for item_id in affected_items:
        item = db.get(Item, item_id)
        if item is not None:
            recompute_average_cost(db, item)

    db.flush()
    return reversal


def void_sales_invoice(
    db: Session, invoice_id: UUID, *, reason: str, user: User, void_date: date_ | None = None
) -> JournalEntry:
    invoice = db.get(SalesInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور فروش یافت نشد")
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
