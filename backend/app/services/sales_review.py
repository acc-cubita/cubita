"""مرور فروش — چند نما روی یک حقیقت، بدونِ اینکه یک مبلغ دو بار شمرده شود.

**دفترِ تازه‌ای ساخته نمی‌شود.** هر عددِ این فایل از اسنادِ موجود می‌آید: فاکتور
فروش، برگشت از فروش، خروجِ انبار، پیش‌فاکتور، و دفترِ موجودی.

خطرِ اصلیِ این فصل ریاضی است نه معماری. یک فاکتورِ ۱۰۰٬۰۰۰ با سه ردیف، اگر
سربرگ به ردیف‌ها پیوست شود و بعد جمع بزنیم، می‌شود **۳۰۰٬۰۰۰**. و ردیفی که از
دو انبار خارج شده، اگر به خروج‌هایش پیوست شود مبلغش **دو برابر** می‌شود. پس
قاعده‌ی این فایل یک جمله است:

    هر جریانِ واقعیت، **پیش از** اتصال، در دانه‌بندیِ خودش تجمیع می‌شود.

چهار جریان داریم و هر چهار روی «ردیفِ فاکتور فروش» می‌نشینند — که ریزترین
دانه‌بندیِ مشترکِ فروش است:

    فروشِ تجاری      ← ردیفِ فاکتور، یک ردیف برای هر ردیف
    برگشتِ تجاری     ← جمعِ ردیف‌های برگشت، گروه‌شده روی ردیفِ فاکتور
    تحققِ فیزیکی     ← جمعِ ردیف‌های خروجِ انبار، گروه‌شده روی ردیفِ فاکتور
    پیشرفتِ پیش‌فاکتور ← جمعِ فاکتورشده/خارج‌شده، گروه‌شده روی ردیفِ پیش‌فاکتور

و بعد نماها روی این‌ها ساخته می‌شوند. هیچ نمایی از نمای دیگری ساخته نمی‌شود.

**مرزی که این گزارش نشان می‌دهد و نمی‌پوشاند:** «فروخته‌شده» و «خارج‌شده» دو
عددِ مستقل‌اند. از مهاجرتِ ۰۱۲۵ فاکتور دیگر خودش موجودی کم نمی‌کند، پس این دو
می‌توانند فرق کنند — و همان اختلاف، مفیدترین چیزی است که این گزارش می‌گوید.

**آنچه این‌جا ساخته نمی‌شود، چون کوبیتا منبعش را ندارد:**

* *موجودیِ قابلِ فروش* — `Item.is_sellable` یک پرچمِ بولی است («اجازه‌ی فروش
  دارد»)، نه مقدار. موتورِ رزرو/تخصیص وجود ندارد و ساختنِ فرمولش از خودمان یعنی
  عددی که هیچ‌کس تعریفش نکرده.
* *برگشتِ فیزیکیِ خروجِ انبار* — چنین سندی نیست. در کوبیتا خودِ برگشت از فروش
  موجودی را برمی‌گرداند، پس مدلِ چهارمقداری این‌جا سه مقدار دارد.
* *پورسانتِ هر فاکتور* — `CommissionRunLine` تجمیعیِ هر فروشنده در یک دوره است
  و به فاکتور قابلِ نسبت‌دادن نیست. محاسبه‌ی دوباره‌اش در گزارش یعنی دو فرمول.
* *درخواستِ فروش* و *ردیابی به‌عنوان بُعدِ ردیفِ فروش* — مدلی به این نام‌ها
  وجود ندارد.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company import ContactGroup
from app.models.inventory import Contact, Item, StockLedger, UnitOfMeasure, Warehouse
from app.models.invoices import (
    SalesInvoice,
    SalesInvoiceLine,
    WarehouseIssue,
    WarehouseIssueLine,
)
from app.models.quotations import SalesQuotation, SalesQuotationLine
from app.models.returns import SalesReturn, SalesReturnLine
from app.models.sales_ops import SaleType

#: **همه‌ی معیارهای پولیِ این گزارش از عکسِ لحظه‌ی ثبت می‌آیند**، نه از قواعدِ
#: امروز. اگر فردا قیمتِ اعلامیه یا نرخِ مالیات عوض شود، فروشِ پارسال همان چیزی
#: می‌ماند که بود — چون `tax_amount_snapshot` و `unit_price` روی خودِ ردیف
#: نشسته‌اند و گزارش هیچ‌وقت قاعده‌ی امروز را دوباره اعمال نمی‌کند.


@dataclass(frozen=True)
class Scope:
    """دامنه‌ی گزارش.

    **تاریخِ هر جریان، تاریخِ خودِ آن سند است** — فاکتور با تاریخِ فاکتور، خروج با
    تاریخِ خروج، برگشت با تاریخِ برگشت. فیلترکردنِ همه با یک ستون، عددی می‌ساخت
    که هیچ سندی پشتش نیست: خروجی که سه روز بعد از فاکتور انجام شده، در بازه‌ی
    فاکتور نیست ولی به آن فاکتور تعلق دارد.

    پس بازه روی **فاکتور** اعمال می‌شود (لنگرِ تجاریِ گزارش) و جریان‌های دیگر
    از همان فاکتورها دنبال می‌شوند، هر تاریخی که داشته باشند. این یک انتخابِ
    صریح است تا «فروشِ این ماه و هرچه از آن تحقق یافته» معنی داشته باشد.
    """

    date_from: date | None = None
    date_to: date | None = None
    contact_id: UUID | None = None
    item_id: UUID | None = None
    sale_type_id: UUID | None = None
    warehouse_id: UUID | None = None
    include_voided: bool = False


def _invoice_filter(scope: Scope):
    clauses = []
    if not scope.include_voided:
        clauses.append(SalesInvoice.voided_at.is_(None))
    if scope.date_from is not None:
        clauses.append(SalesInvoice.invoice_date >= scope.date_from)
    if scope.date_to is not None:
        clauses.append(SalesInvoice.invoice_date <= scope.date_to)
    if scope.contact_id is not None:
        clauses.append(SalesInvoice.contact_id == scope.contact_id)
    if scope.sale_type_id is not None:
        clauses.append(SalesInvoice.sale_type_id == scope.sale_type_id)
    return clauses


# ═══════════════ جریانِ ۱: فروشِ تجاری (دانه‌بندی: ردیفِ فاکتور) ═══════════════


def _sales_lines(db: Session, scope: Scope):
    """ردیف‌های فاکتورِ دامنه — **یک ردیف برای هر ردیف**، بدونِ هیچ اتصالی.

    این پایه‌ی همه‌چیز است و عمداً هیچ پیوستی به برگشت و خروج ندارد؛ آن‌ها
    جداگانه تجمیع و بعد چسبانده می‌شوند.
    """
    query = (
        db.query(
            SalesInvoiceLine.id.label("line_id"),
            SalesInvoiceLine.invoice_id,
            SalesInvoiceLine.item_id,
            SalesInvoiceLine.qty,
            SalesInvoiceLine.unit_price,
            SalesInvoiceLine.discount,
            SalesInvoiceLine.addition,
            SalesInvoiceLine.duty_amount,
            SalesInvoiceLine.tax_amount_snapshot.label("tax_amount"),
            SalesInvoiceLine.unit_cost,
            SalesInvoiceLine.item_code_snapshot,
            SalesInvoiceLine.item_name_snapshot,
            SalesInvoiceLine.unit_snapshot,
            SalesInvoiceLine.source_quotation_line_id,
            SalesInvoice.number.label("invoice_number"),
            SalesInvoice.invoice_date,
            SalesInvoice.contact_id,
            SalesInvoice.sale_type_id,
            SalesInvoice.warehouse_id.label("invoice_warehouse_id"),
            SalesInvoice.salesperson_id,
            SalesInvoice.broker_id,
            SalesInvoice.voided_at,
        )
        .join(SalesInvoice, SalesInvoice.id == SalesInvoiceLine.invoice_id)
        .filter(*_invoice_filter(scope))
    )
    if scope.item_id is not None:
        query = query.filter(SalesInvoiceLine.item_id == scope.item_id)
    return query.all()


# ═══════ جریانِ ۲: برگشتِ تجاری (تجمیع‌شده روی ردیفِ فاکتور) ═══════


def _returned_by_line(db: Session, scope: Scope) -> dict[UUID, tuple[Decimal, Decimal]]:
    """(مقدار، مبلغ)ِ برگشت‌خورده‌ی هر ردیفِ فاکتور.

    **تجمیع پیش از اتصال.** یک ردیفِ فاکتور می‌تواند چند برگشت داشته باشد؛ اگر
    مستقیم پیوست می‌شد، مبلغِ فروشِ همان ردیف به تعدادِ برگشت‌ها تکرار می‌شد.
    """
    rows = (
        db.query(
            SalesReturnLine.sales_invoice_line_id,
            func.coalesce(func.sum(SalesReturnLine.qty), 0),
            func.coalesce(func.sum(SalesReturnLine.qty * SalesReturnLine.unit_price), 0),
        )
        .join(SalesReturn, SalesReturn.id == SalesReturnLine.return_id)
        .join(SalesInvoice, SalesInvoice.id == SalesReturn.sales_invoice_id)
        .filter(
            SalesReturn.voided_at.is_(None),
            SalesReturnLine.sales_invoice_line_id.isnot(None),
            *_invoice_filter(scope),
        )
        .group_by(SalesReturnLine.sales_invoice_line_id)
        .all()
    )
    return {line_id: (Decimal(qty), Decimal(amount)) for line_id, qty, amount in rows}


# ═══════ جریانِ ۳: تحققِ فیزیکی (تجمیع‌شده روی ردیفِ فاکتور) ═══════


def _issued_by_line(db: Session, scope: Scope) -> dict[UUID, Decimal]:
    """مقدارِ واقعاً خارج‌شده‌ی هر ردیفِ فاکتور.

    خروجِ باطل‌شده شمرده نمی‌شود. و این‌جا هم تجمیع پیش از اتصال است: ردیفی که
    از دو انبار رفته، دو ردیفِ خروج دارد و پیوستِ خام مبلغِ فروشش را دو برابر
    می‌کرد.
    """
    query = (
        db.query(
            WarehouseIssueLine.sales_invoice_line_id,
            func.coalesce(func.sum(WarehouseIssueLine.qty), 0),
        )
        .join(WarehouseIssue, WarehouseIssue.id == WarehouseIssueLine.issue_id)
        .join(SalesInvoice, SalesInvoice.id == WarehouseIssue.sales_invoice_id)
        .filter(WarehouseIssue.voided_at.is_(None), *_invoice_filter(scope))
    )
    if scope.warehouse_id is not None:
        query = query.filter(WarehouseIssue.warehouse_id == scope.warehouse_id)
    rows = query.group_by(WarehouseIssueLine.sales_invoice_line_id).all()
    return {line_id: Decimal(qty) for line_id, qty in rows}


def _issued_by_warehouse(db: Session, scope: Scope) -> list[dict]:
    """تحققِ فیزیکی، تجمیع‌شده روی **انبار** — دانه‌بندیِ نمای انبار.

    انبار از خودِ سندِ خروج می‌آید، نه از سربرگِ فاکتور: بعد از مهاجرتِ ۰۱۲۵
    سربرگ می‌تواند انبار نداشته باشد، و یک فاکتور می‌تواند از چند انبار تحقق
    یابد.
    """
    rows = (
        db.query(
            WarehouseIssue.warehouse_id,
            func.count(func.distinct(WarehouseIssue.id)).label("issue_count"),
            func.count(func.distinct(WarehouseIssue.sales_invoice_id)).label("invoice_count"),
            func.coalesce(func.sum(WarehouseIssueLine.qty), 0).label("qty"),
            func.coalesce(
                func.sum(WarehouseIssueLine.qty * WarehouseIssueLine.unit_cost), 0
            ).label("cost"),
        )
        .join(WarehouseIssueLine, WarehouseIssueLine.issue_id == WarehouseIssue.id)
        .join(SalesInvoice, SalesInvoice.id == WarehouseIssue.sales_invoice_id)
        .filter(WarehouseIssue.voided_at.is_(None), *_invoice_filter(scope))
        .group_by(WarehouseIssue.warehouse_id)
        .all()
    )
    names = {w.id: w.name for w in db.query(Warehouse).all()}
    return [
        {
            "warehouse_id": r.warehouse_id,
            "warehouse_name": names.get(r.warehouse_id, "—"),
            "issue_count": int(r.issue_count),
            "invoice_count": int(r.invoice_count),
            "issued_qty": Decimal(r.qty),
            "issued_cost": Decimal(r.cost),
        }
        for r in rows
    ]


# ═══════════════════════════ نماها ═══════════════════════════


def _components(row, returned_amount: Decimal) -> dict:
    """اجزای پولِ یک ردیف — ناخالص، تخفیف، مالیات، عوارض، اضافات، خالص.

    هیچ‌کدام در یک «مبلغِ خالصِ» بی‌توضیح گم نمی‌شوند: کاربر باید بتواند بگوید
    این عدد از چه چیزی ساخته شده.
    """
    gross = Decimal(row.qty) * Decimal(row.unit_price)
    discount = Decimal(row.discount)
    tax = Decimal(row.tax_amount)
    duty = Decimal(row.duty_amount)
    addition = Decimal(row.addition)
    return {
        "gross_amount": gross,
        "discount": discount,
        "tax": tax,
        "duty": duty,
        "addition": addition,
        #: خالصِ تجاری پیش از برگشت — همان چیزی که در فاکتور نشسته.
        "net_amount": gross - discount + tax + duty + addition,
        "return_amount": returned_amount,
        #: فروشِ خالص = خالصِ فاکتور منهای برگشت. برگشت **جدا** هم نگه داشته
        #: می‌شود تا در یک عدد پنهان نشود.
        "net_sales": gross - discount + tax + duty + addition - returned_amount,
    }


def _secondary(item: Item | None, qty: Decimal) -> Decimal | None:
    """مقدار به واحدِ دوم.

    **مقدارِ دومی، فروشِ دومی نیست** — همان مقدار است با واحدِ دیگر. پس هرگز با
    مقدارِ اصلی جمع نمی‌شود. ضریبِ صفر یعنی نسبت تعریف نشده و `None` برمی‌گردد،
    نه صفر.
    """
    if item is None or item.secondary_unit_id is None:
        return None
    factor = Decimal(item.conversion_factor or 0)
    if factor <= 0:
        return None
    return qty / factor


def by_item(db: Session, scope: Scope) -> list[dict]:
    """نمای کالا — فروش، برگشت، و **تحققِ فیزیکی** کنارِ هم.

    این نما دلیلِ اصلیِ وجودِ این فصل است: «۱۰۰ فروختم، ۷۰ فرستادم، ۲۰ برگشت
    خورد» سه عددِ مستقل‌اند و هیچ‌کدام از دیگری قابلِ حدس نیست.
    """
    lines = _sales_lines(db, scope)
    returned = _returned_by_line(db, scope)
    issued = _issued_by_line(db, scope)

    items = {i.id: i for i in db.query(Item).all()}
    units = {u.id: u.name for u in db.query(UnitOfMeasure).all()}

    acc: dict[UUID, dict] = {}
    for row in lines:
        bucket = acc.get(row.item_id)
        if bucket is None:
            item = items.get(row.item_id)
            bucket = acc[row.item_id] = {
                "item_id": row.item_id,
                "item_code": row.item_code_snapshot or (item.sku if item else ""),
                "item_name": row.item_name_snapshot or (item.name if item else "—"),
                "is_service": bool(item.is_service) if item else False,
                "unit_name": row.unit_snapshot
                or (units.get(item.primary_unit_id, "") if item else ""),
                "secondary_unit_name": (
                    units.get(item.secondary_unit_id, "") if item and item.secondary_unit_id else ""
                ),
                "sold_qty": Decimal(0),
                "returned_qty": Decimal(0),
                "issued_qty": Decimal(0),
                "line_count": 0,
                "gross_amount": Decimal(0),
                "discount": Decimal(0),
                "tax": Decimal(0),
                "duty": Decimal(0),
                "addition": Decimal(0),
                "net_amount": Decimal(0),
                "return_amount": Decimal(0),
                "net_sales": Decimal(0),
            }
        ret_qty, ret_amount = returned.get(row.line_id, (Decimal(0), Decimal(0)))
        parts = _components(row, ret_amount)
        bucket["sold_qty"] += Decimal(row.qty)
        bucket["returned_qty"] += ret_qty
        bucket["issued_qty"] += issued.get(row.line_id, Decimal(0))
        bucket["line_count"] += 1
        for key in ("gross_amount", "discount", "tax", "duty", "addition", "net_amount", "return_amount", "net_sales"):
            bucket[key] += parts[key]

    out = []
    for bucket in acc.values():
        item = items.get(bucket["item_id"])
        net_qty = bucket["sold_qty"] - bucket["returned_qty"]
        #: فیِ متوسطِ **تاریخی** — از معاملاتِ واقعی، نه از اعلامیه‌ی قیمتِ امروز.
        #: وزنی است (مبلغ ÷ مقدار) نه میانگینِ سادهٔ فی‌ها، وگرنه یک ردیفِ
        #: یک‌عددی هم‌وزنِ ردیفِ هزارعددی می‌شد.
        bucket["average_unit_price"] = (
            (bucket["gross_amount"] - bucket["discount"]) / bucket["sold_qty"]
            if bucket["sold_qty"]
            else None
        )
        bucket["net_qty"] = net_qty
        #: اختلافِ تجاری و فیزیکی — مفیدترین عددِ این گزارش.
        bucket["unissued_qty"] = bucket["sold_qty"] - bucket["issued_qty"]
        bucket["sold_qty_secondary"] = _secondary(item, bucket["sold_qty"])
        bucket["issued_qty_secondary"] = _secondary(item, bucket["issued_qty"])
        #: موجودیِ انبار از **دفترِ موجودی** می‌آید، نه از فروش منهای برگشت.
        bucket["stock_qty"] = _stock_of(db, bucket["item_id"], scope.warehouse_id)
        out.append(bucket)
    out.sort(key=lambda r: -r["net_sales"])
    return out


def _stock_of(db: Session, item_id: UUID, warehouse_id: UUID | None) -> Decimal:
    query = db.query(func.coalesce(func.sum(StockLedger.qty), 0)).filter(
        StockLedger.item_id == item_id
    )
    if warehouse_id is not None:
        query = query.filter(StockLedger.warehouse_id == warehouse_id)
    return Decimal(query.scalar() or 0)


def by_customer(db: Session, scope: Scope) -> list[dict]:
    """نمای مشتری — فروشِ هر مشتری در همین دامنه.

    این **مانده‌ی طرف حساب نیست.** مانده کارِ «مرور جامع طرف حساب» است و از
    دفتر می‌آید؛ این‌جا فقط فروشِ همین بازه است. دو عددِ متفاوت با دو معنا، و
    یکی‌گرفتنشان همان اشتباهی است که فصل «Credit Policy ≠ Accounting Balance»
    می‌نامدش.
    """
    lines = _sales_lines(db, scope)
    returned = _returned_by_line(db, scope)
    issued = _issued_by_line(db, scope)
    contacts = {c.id: c for c in db.query(Contact).all()}

    acc: dict[UUID | None, dict] = {}
    for row in lines:
        bucket = acc.get(row.contact_id)
        if bucket is None:
            contact = contacts.get(row.contact_id) if row.contact_id else None
            bucket = acc[row.contact_id] = {
                "contact_id": row.contact_id,
                "contact_name": contact.name if contact else "بی‌نام (فروشِ گذری)",
                "contact_type": contact.type if contact else "",
                #: گروه از **مِسترِ امروز** خوانده می‌شود؛ کوبیتا عکسِ گروه را
                #: روی فاکتور ذخیره نمی‌کند. اگر مشتری گروهش عوض شود، فروشِ
                #: گذشته‌اش زیرِ گروهِ تازه دیده می‌شود — و این روی گزارش نوشته
                #: می‌شود تا انتخابِ خاموش نباشد.
                "group_id": contact.group_id if contact else None,
                "credit_limit": Decimal(contact.credit_limit or 0) if contact else Decimal(0),
                "invoice_ids": set(),
                "sold_qty": Decimal(0),
                "returned_qty": Decimal(0),
                "issued_qty": Decimal(0),
                "gross_amount": Decimal(0),
                "discount": Decimal(0),
                "tax": Decimal(0),
                "duty": Decimal(0),
                "addition": Decimal(0),
                "net_amount": Decimal(0),
                "return_amount": Decimal(0),
                "net_sales": Decimal(0),
            }
        ret_qty, ret_amount = returned.get(row.line_id, (Decimal(0), Decimal(0)))
        parts = _components(row, ret_amount)
        bucket["invoice_ids"].add(row.invoice_id)
        bucket["sold_qty"] += Decimal(row.qty)
        bucket["returned_qty"] += ret_qty
        bucket["issued_qty"] += issued.get(row.line_id, Decimal(0))
        for key in ("gross_amount", "discount", "tax", "duty", "addition", "net_amount", "return_amount", "net_sales"):
            bucket[key] += parts[key]

    groups = {g.id: g.name for g in db.query(ContactGroup).all()}
    out = []
    for bucket in acc.values():
        #: **شمارشِ فاکتور از شناسه‌های یکتا**، نه از تعدادِ ردیف‌ها — فاکتورِ
        #: سه‌ردیفی یک فاکتور است.
        bucket["invoice_count"] = len(bucket.pop("invoice_ids"))
        bucket["group_name"] = groups.get(bucket.pop("group_id"), "") or ""
        out.append(bucket)
    out.sort(key=lambda r: -r["net_sales"])
    return out


def by_warehouse(db: Session, scope: Scope) -> list[dict]:
    """نمای انبار — تحققِ فیزیکیِ فروش، انبار به انبار.

    این نما **دفترِ موجودی نیست** و مانده‌ای نگه نمی‌دارد؛ فقط می‌گوید از هر
    انبار چه‌قدر بابتِ فروشِ این بازه خارج شده.
    """
    return _issued_by_warehouse(db, scope)


def documents(db: Session, scope: Scope) -> list[dict]:
    """نمای اسنادِ فروش — **یک ردیف برای هر سند**.

    فاکتور و برگشت هر دو می‌آیند و به یک «معامله‌ی خالص» تبدیل نمی‌شوند: هرکدام
    تاریخِ خودش را دارد و جمعِ خالص در گزارش مشتق می‌شود.

    مبلغِ سربرگ از **تجمیعِ ردیف‌های خودش** می‌آید، نه از پیوستن به ردیف‌ها و
    جمع‌زدنِ سربرگ — که فاکتورِ سه‌ردیفی را سه برابر می‌کرد.
    """
    lines = _sales_lines(db, scope)
    returned = _returned_by_line(db, scope)
    issued = _issued_by_line(db, scope)
    contacts = {c.id: c.name for c in db.query(Contact).all()}
    sale_types = {t.id: t.name for t in db.query(SaleType).all()}

    acc: dict[UUID, dict] = {}
    for row in lines:
        bucket = acc.get(row.invoice_id)
        if bucket is None:
            bucket = acc[row.invoice_id] = {
                "source_type": "sales_invoice",
                "source_id": row.invoice_id,
                "label": "فاکتور فروش",
                "number": row.invoice_number,
                "document_date": row.invoice_date,
                "contact_id": row.contact_id,
                "contact_name": contacts.get(row.contact_id, "—") if row.contact_id else "—",
                "sale_type_name": sale_types.get(row.sale_type_id, "") if row.sale_type_id else "",
                "is_voided": row.voided_at is not None,
                "line_count": 0,
                "sold_qty": Decimal(0),
                "returned_qty": Decimal(0),
                "issued_qty": Decimal(0),
                "gross_amount": Decimal(0),
                "discount": Decimal(0),
                "tax": Decimal(0),
                "duty": Decimal(0),
                "addition": Decimal(0),
                "net_amount": Decimal(0),
                "return_amount": Decimal(0),
                "net_sales": Decimal(0),
            }
        ret_qty, ret_amount = returned.get(row.line_id, (Decimal(0), Decimal(0)))
        parts = _components(row, ret_amount)
        bucket["line_count"] += 1
        bucket["sold_qty"] += Decimal(row.qty)
        bucket["returned_qty"] += ret_qty
        bucket["issued_qty"] += issued.get(row.line_id, Decimal(0))
        for key in ("gross_amount", "discount", "tax", "duty", "addition", "net_amount", "return_amount", "net_sales"):
            bucket[key] += parts[key]

    out = list(acc.values())
    out.sort(key=lambda r: (r["document_date"], r["number"] or 0), reverse=True)
    return out


def lines(db: Session, scope: Scope) -> list[dict]:
    """نمای اقلامِ فروش — **یک ردیف برای هر ردیفِ سند**.

    ریزترین دانه‌بندی، و جایی که هر بُعدِ تحلیلی در دسترس است. درست همان
    داده‌ی نمای اسناد را دارد، ولی **باز**؛ پس جمع‌زدنِ این دو با هم، هر مبلغ
    را دو بار می‌شمارد.
    """
    rows = _sales_lines(db, scope)
    returned = _returned_by_line(db, scope)
    issued = _issued_by_line(db, scope)
    contacts = {c.id: c for c in db.query(Contact).all()}
    sale_types = {t.id: t.name for t in db.query(SaleType).all()}
    items = {i.id: i for i in db.query(Item).all()}
    warehouses = {w.id: w.name for w in db.query(Warehouse).all()}
    #: انبارِ **واقعیِ** هر ردیف: از خروجِ انبار، نه از سربرگِ فاکتور.
    line_warehouses = _warehouses_by_line(db, scope)

    out = []
    for row in rows:
        ret_qty, ret_amount = returned.get(row.line_id, (Decimal(0), Decimal(0)))
        parts = _components(row, ret_amount)
        item = items.get(row.item_id)
        contact = contacts.get(row.contact_id) if row.contact_id else None
        issued_qty = issued.get(row.line_id, Decimal(0))
        out.append(
            {
                "line_id": row.line_id,
                "source_type": "sales_invoice",
                "source_id": row.invoice_id,
                "number": row.invoice_number,
                "document_date": row.invoice_date,
                "contact_id": row.contact_id,
                "contact_name": contact.name if contact else "—",
                "sale_type_name": sale_types.get(row.sale_type_id, "") if row.sale_type_id else "",
                "item_id": row.item_id,
                "item_code": row.item_code_snapshot or (item.sku if item else ""),
                "item_name": row.item_name_snapshot or (item.name if item else "—"),
                "barcode": (item.barcode or "") if item else "",
                "unit_name": row.unit_snapshot,
                "sold_qty": Decimal(row.qty),
                "sold_qty_secondary": _secondary(item, Decimal(row.qty)),
                "returned_qty": ret_qty,
                "issued_qty": issued_qty,
                "unissued_qty": Decimal(row.qty) - issued_qty,
                "unit_price": Decimal(row.unit_price),
                "warehouse_names": [warehouses.get(w, "—") for w in line_warehouses.get(row.line_id, [])],
                "is_voided": row.voided_at is not None,
                **parts,
            }
        )
    out.sort(key=lambda r: (r["document_date"], r["number"] or 0), reverse=True)
    return out


def _warehouses_by_line(db: Session, scope: Scope) -> dict[UUID, list[UUID]]:
    """انبارهایی که هر ردیفِ فاکتور از آن‌ها خارج شده."""
    rows = (
        db.query(WarehouseIssueLine.sales_invoice_line_id, WarehouseIssue.warehouse_id)
        .join(WarehouseIssue, WarehouseIssue.id == WarehouseIssueLine.issue_id)
        .join(SalesInvoice, SalesInvoice.id == WarehouseIssue.sales_invoice_id)
        .filter(WarehouseIssue.voided_at.is_(None), *_invoice_filter(scope))
        .distinct()
        .all()
    )
    out: dict[UUID, list[UUID]] = {}
    for line_id, warehouse_id in rows:
        out.setdefault(line_id, []).append(warehouse_id)
    return out


# ═══════════════════ نمای پیش‌فاکتور ═══════════════════


def preinvoices(db: Session, scope: Scope) -> list[dict]:
    """پیشرفتِ پیش‌فاکتور — پیشنهادشده، فاکتورشده، خارج‌شده.

    سه عددِ مستقل، و هیچ‌کدام ذخیره نمی‌شود: «فاکتورشده» جمعِ تخصیص‌های
    `source_quotation_line_id` است و «خارج‌شده» از خروجِ انبارِ همان فاکتورها
    می‌آید. شمارنده‌ی چهارمی ساخته نمی‌شود که بتواند از این‌ها جدا بیفتد.

    **وضعیتِ سند و پیشرفتِ تحقق دو چیزند**: پیش‌فاکتوری می‌تواند «تأییدشده»
    باشد و هنوز هیچ فاکتوری نخورده باشد.
    """
    #: پیش‌فاکتور ابطال ندارد (نه سند می‌زند نه موجودی)، پس فیلترِ ابطال هم
    #: ندارد — برخلافِ فاکتور و برگشت و خروج.
    clauses: list = []
    if scope.date_from is not None:
        clauses.append(SalesQuotation.quotation_date >= scope.date_from)
    if scope.date_to is not None:
        clauses.append(SalesQuotation.quotation_date <= scope.date_to)
    if scope.contact_id is not None:
        clauses.append(SalesQuotation.contact_id == scope.contact_id)

    quoted = (
        db.query(
            SalesQuotationLine.id.label("line_id"),
            SalesQuotationLine.item_id,
            SalesQuotationLine.qty,
            SalesQuotationLine.unit_price,
            SalesQuotation.id.label("quotation_id"),
            SalesQuotation.number,
            SalesQuotation.quotation_date,
            SalesQuotation.contact_id,
            SalesQuotation.status,
        )
        .join(SalesQuotation, SalesQuotation.id == SalesQuotationLine.quotation_id)
        .filter(*clauses)
        .all()
    )
    if not quoted:
        return []

    #: تجمیعِ تخصیص‌ها **پیش از** اتصال — یک ردیفِ پیش‌فاکتور می‌تواند چند
    #: ردیفِ فاکتور بگیرد.
    invoiced_rows = (
        db.query(
            SalesInvoiceLine.source_quotation_line_id,
            func.coalesce(func.sum(SalesInvoiceLine.qty), 0),
            func.count(SalesInvoiceLine.id),
        )
        .join(SalesInvoice, SalesInvoice.id == SalesInvoiceLine.invoice_id)
        .filter(
            SalesInvoiceLine.source_quotation_line_id.isnot(None),
            SalesInvoice.voided_at.is_(None),
        )
        .group_by(SalesInvoiceLine.source_quotation_line_id)
        .all()
    )
    invoiced = {r[0]: (Decimal(r[1]), int(r[2])) for r in invoiced_rows}

    issued_rows = (
        db.query(
            SalesInvoiceLine.source_quotation_line_id,
            func.coalesce(func.sum(WarehouseIssueLine.qty), 0),
        )
        .join(WarehouseIssueLine, WarehouseIssueLine.sales_invoice_line_id == SalesInvoiceLine.id)
        .join(WarehouseIssue, WarehouseIssue.id == WarehouseIssueLine.issue_id)
        .join(SalesInvoice, SalesInvoice.id == SalesInvoiceLine.invoice_id)
        .filter(
            SalesInvoiceLine.source_quotation_line_id.isnot(None),
            SalesInvoice.voided_at.is_(None),
            WarehouseIssue.voided_at.is_(None),
        )
        .group_by(SalesInvoiceLine.source_quotation_line_id)
        .all()
    )
    issued = {r[0]: Decimal(r[1]) for r in issued_rows}

    contacts = {c.id: c.name for c in db.query(Contact).all()}
    items = {i.id: i for i in db.query(Item).all()}

    out = []
    for row in quoted:
        item = items.get(row.item_id)
        inv_qty, inv_lines = invoiced.get(row.line_id, (Decimal(0), 0))
        iss_qty = issued.get(row.line_id, Decimal(0))
        quoted_qty = Decimal(row.qty)
        out.append(
            {
                "quotation_id": row.quotation_id,
                "line_id": row.line_id,
                "number": row.number,
                "quotation_date": row.quotation_date,
                "contact_id": row.contact_id,
                "contact_name": contacts.get(row.contact_id, "—") if row.contact_id else "—",
                "status": row.status,
                "item_id": row.item_id,
                "item_name": item.name if item else "—",
                "unit_price": Decimal(row.unit_price),
                "quoted_qty": quoted_qty,
                "invoiced_qty": inv_qty,
                "issued_qty": iss_qty,
                "invoice_line_count": inv_lines,
                #: مانده‌ها **مشتق**اند: چیزی که می‌شود فاکتور کرد، و چیزی که
                #: فاکتور شده ولی هنوز نرفته.
                "remaining_invoiceable": quoted_qty - inv_qty,
                "remaining_issueable": inv_qty - iss_qty,
            }
        )
    out.sort(key=lambda r: (r["quotation_date"], r["number"] or 0), reverse=True)
    return out


# ═══════════════════ فاکتورهای ابطالی ═══════════════════


def voided_documents(db: Session, scope: Scope) -> list[dict]:
    """فاکتورهایی که باطل شده‌اند — تاریخ پاک نمی‌شود.

    این‌ها در فروشِ جاری **شمرده نمی‌شوند** (هر نمای دیگر `voided_at IS NULL`
    می‌گذارد) ولی باید دیده شوند: «فاکتوری بود و باطل شد» خودش یک واقعیتِ
    حسابرسی است.
    """
    voided_scope = Scope(
        date_from=scope.date_from,
        date_to=scope.date_to,
        contact_id=scope.contact_id,
        item_id=scope.item_id,
        sale_type_id=scope.sale_type_id,
        include_voided=True,
    )
    rows = documents(db, voided_scope)
    return [row for row in rows if row["is_voided"]]


# ═══════════════════ خلاصه‌ی سرصفحه ═══════════════════


def summary(db: Session, scope: Scope) -> dict:
    """شاخص‌های بازه — از دانه‌بندیِ درست، نه از جمعِ نمایی دیگر."""
    rows = documents(db, scope)
    items = by_item(db, scope)
    return {
        "invoice_count": len(rows),
        "line_count": sum(r["line_count"] for r in rows),
        "gross_amount": sum((r["gross_amount"] for r in rows), Decimal(0)),
        "discount": sum((r["discount"] for r in rows), Decimal(0)),
        "tax": sum((r["tax"] for r in rows), Decimal(0)),
        "return_amount": sum((r["return_amount"] for r in rows), Decimal(0)),
        "net_sales": sum((r["net_sales"] for r in rows), Decimal(0)),
        "sold_qty": sum((r["sold_qty"] for r in rows), Decimal(0)),
        "issued_qty": sum((r["issued_qty"] for r in rows), Decimal(0)),
        #: مقداری که فروخته شده و هنوز از انبار نرفته — عددی که تا امروز
        #: هیچ‌جا دیده نمی‌شد.
        "unissued_qty": sum((r["sold_qty"] - r["issued_qty"] for r in rows), Decimal(0)),
        "item_count": len(items),
    }
