"""مرورِ انبار از زاویه‌های دیگر — تأمین‌کننده، مشتری، و هدفِ حرکت.

**این ماژول دفترِ دومی نمی‌سازد.** هیچ مانده‌ای ذخیره نمی‌کند و هیچ ارزشی را از
نو حساب نمی‌کند: همان `valuation.replay` را صدا می‌زند که کاردکس و مرورِ موجودی
هم از آن می‌خوانند، و فقط **کلیدِ جمع‌زدن** را عوض می‌کند.

    حرکتِ دفترِ موجودی
            ↓
    valuation.replay  ← تنها جایی که مقدار و ارزش معنا پیدا می‌کنند
            ↓
    این‌جا: فقط گروه‌بندی

پس اگر عددی این‌جا با کاردکس نخواند، یکی از آن دو باگ دارد — نه اینکه «دو
تعریف» داشته باشیم.

## سه بُعد، و اینکه هرکدام از کجا می‌آید

* **تأمین‌کننده / مشتری** — حرکت خودش طرف حساب ندارد؛ سندِ مبدأ دارد. پس از
  `(source_type, source_id)` به سند می‌رویم و طرف حسابش را برمی‌داریم. طرف حساب
  روی حرکت **کپی نمی‌شود**: کپی یعنی دو حقیقت، و اولین تغییرِ سند آن دو را از هم
  دور می‌کند.
* **هدف** — «این حرکت چه بود؟» فروش، خرید، مصرف، تولید، انبارگردانی، انتقال…
  این از `source_type` مشتق می‌شود، نه از یک ستونِ تازه.

## مقدار و ارزش یک تازگی ندارند

مقدار همیشه تازه است (از دفتر)، ولی ارزش می‌تواند منقضی باشد. هر ردیف
`stale_count` خودش را می‌آورد تا گزارشِ مبلغی بتواند بگوید «این عدد هنوز
بازمحاسبه نشده» — به‌جای اینکه عددِ کهنه را حقیقتِ امروز جا بزند.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.inventory import Contact
from app.services import valuation

#: بُعدهایی که این گزارش می‌شناسد. `purpose` از `source_type` مشتق می‌شود و دو
#: تای دیگر از طرف حسابِ سندِ مبدأ.
DIMENSIONS = ("supplier", "customer", "purpose")
DIMENSION_LABELS = {
    "supplier": "تأمین‌کننده",
    "customer": "مشتری",
    "purpose": "هدف حرکت",
}

#: **کدام منشأ طرف حسابِ کدام سمت است.** ورودِ خرید از تأمین‌کننده می‌آید و
#: برگشتش به همان تأمین‌کننده برمی‌گردد؛ خروجِ فروش به مشتری می‌رود و برگشتش از
#: همان مشتری. حرکت‌هایی که طرفِ بیرونی ندارند (تولید، انبارگردانی، انتقال،
#: تعدیل) در این دو بُعد اصلاً نمی‌آیند — نه اینکه زیرِ «نامشخص» جمع شوند.
SUPPLIER_SOURCES = frozenset({"purchase_invoice", "warehouse_receipt", "purchase_return"})
CUSTOMER_SOURCES = frozenset({"sales_invoice", "warehouse_issue", "sales_return", "warehouse_issue_return"})

#: هدفِ هر منشأ — همان برچسب‌های موتورِ ارزش‌گذاری، بی بازتعریف.
PURPOSE_LABELS = dict(valuation.SOURCE_LABELS)


@dataclass
class Bucket:
    """یک ردیفِ گزارش — کلیدش هرچه باشد، اندازه‌هایش یکی است."""

    key: str
    label: str
    in_qty: Decimal = Decimal(0)
    out_qty: Decimal = Decimal(0)
    in_value: Decimal = Decimal(0)
    out_value: Decimal = Decimal(0)
    #: چند حرکت ارزش‌گذاریِ منقضی دارد — «این مبلغ هنوز بازمحاسبه نشده».
    stale_count: int = 0
    items: set = field(default_factory=set)

    @property
    def net_qty(self) -> Decimal:
        return self.in_qty - self.out_qty

    @property
    def net_value(self) -> Decimal:
        return self.in_value - self.out_value


def _contact_by_source(db: Session, keys: set[tuple[str, UUID]]) -> dict[tuple[str, UUID], UUID]:
    """طرف حسابِ هر سندِ مبدأ — یک پرس‌وجو به‌ازای هر نوعِ سند، نه یکی به‌ازای هر حرکت.

    **طرف حساب همیشه روی خودِ سندِ انبار نیست.** خروجِ انبارِ فروش `receiver_id`
    دارد (تحویل‌گیرنده، که می‌تواند راننده باشد) و مشتریِ واقعی روی **فاکتورِ
    فروش** نشسته. برگشت از فروش هم طرف حسابش را از فاکتورِ مبدأ می‌گیرد. پس هر
    نوعِ سند مسیرِ خودش را دارد و یک `getattr(model, "contact_id")`ِ عمومی
    جوابِ غلط می‌دهد — سکوت‌وار، چون فقط ردیف‌ها ناپدید می‌شوند.
    """
    from app.models.invoices import PurchaseInvoice, SalesInvoice, WarehouseIssue, WarehouseReceipt
    from app.models.returns import PurchaseReturn, SalesReturn

    by_type: dict[str, set[UUID]] = defaultdict(set)
    for source_type, source_id in keys:
        if source_id is not None:
            by_type[source_type].add(source_id)

    out: dict[tuple[str, UUID], UUID] = {}

    def direct(source_type: str, model, column) -> None:
        ids = by_type.get(source_type)
        if not ids:
            return
        for doc_id, contact_id in db.query(model.id, column).filter(model.id.in_(ids)).all():
            if contact_id is not None:
                out[(source_type, doc_id)] = contact_id

    direct("purchase_invoice", PurchaseInvoice, PurchaseInvoice.contact_id)
    direct("sales_invoice", SalesInvoice, SalesInvoice.contact_id)
    direct("warehouse_receipt", WarehouseReceipt, WarehouseReceipt.contact_id)

    #: برگشت از خرید هم طرف حسابش را از فاکتورِ مبدأ می‌گیرد؛ `receiver_id`
    #: تحویل‌گیرنده است نه تأمین‌کننده.
    ids = by_type.get("purchase_return")
    if ids:
        rows = (
            db.query(PurchaseReturn.id, PurchaseInvoice.contact_id, PurchaseReturn.receiver_id)
            .outerjoin(PurchaseInvoice, PurchaseInvoice.id == PurchaseReturn.purchase_invoice_id)
            .filter(PurchaseReturn.id.in_(ids))
            .all()
        )
        for doc_id, invoice_contact, receiver in rows:
            contact_id = invoice_contact or receiver
            if contact_id is not None:
                out[("purchase_return", doc_id)] = contact_id

    #: برگشت از فروش طرف حسابش را از فاکتورِ مبدأ می‌گیرد.
    ids = by_type.get("sales_return")
    if ids:
        rows = (
            db.query(SalesReturn.id, SalesInvoice.contact_id)
            .join(SalesInvoice, SalesInvoice.id == SalesReturn.sales_invoice_id)
            .filter(SalesReturn.id.in_(ids))
            .all()
        )
        for doc_id, contact_id in rows:
            if contact_id is not None:
                out[("sales_return", doc_id)] = contact_id

    #: خروجِ انبار: مشتریِ فاکتور اول، و اگر خروجِ مستقل بود تحویل‌گیرنده‌اش.
    ids = by_type.get("warehouse_issue")
    if ids:
        rows = (
            db.query(WarehouseIssue.id, SalesInvoice.contact_id, WarehouseIssue.receiver_id)
            .outerjoin(SalesInvoice, SalesInvoice.id == WarehouseIssue.sales_invoice_id)
            .filter(WarehouseIssue.id.in_(ids))
            .all()
        )
        for doc_id, invoice_contact, receiver in rows:
            contact_id = invoice_contact or receiver
            if contact_id is not None:
                out[("warehouse_issue", doc_id)] = contact_id

    return out


def breakdown(
    db: Session,
    *,
    dimension: str,
    date_from: date | None = None,
    date_to: date | None = None,
    warehouse_id: UUID | None = None,
) -> dict:
    """گردشِ انبار در یک بازه، گروه‌شده بر یک بُعد.

    برخلافِ مرورِ موجودی، این گزارش **مانده‌ی اول و پایان ندارد** و عمداً ندارد:
    «ماندهٔ اولِ یک تأمین‌کننده» معنایی ندارد. آنچه معنا دارد گردشِ همان بازه است —
    چقدر از او گرفتیم، چقدر برگشت خورد، خالص چقدر.
    """
    if dimension not in DIMENSIONS:
        raise ValueError(f"بُعدِ ناشناخته: {dimension}")

    voided = valuation.voided_sources(db)
    rows = valuation._rows(db, until=date_to)
    origin = valuation._origin_types(rows)
    valued = valuation.replay(rows, voided)

    #: فقط حرکت‌هایی که در بازه‌اند و به بُعد ربط دارند — طرف حساب یک‌جا خوانده
    #: می‌شود، نه به‌ازای هر ردیف.
    relevant = []
    for move in valued:
        row = move.row
        if warehouse_id is not None and row.warehouse_id != warehouse_id:
            continue
        if date_from is not None and row.entry_date < date_from:
            continue
        if move.voided:
            continue
        kind = (
            origin.get(row.source_id, row.source_type)
            if row.source_type == valuation.VOID_SOURCE
            else row.source_type
        )
        relevant.append((move, kind))

    contacts: dict[tuple[str, UUID], UUID] = {}
    names: dict[UUID, str] = {}
    if dimension in ("supplier", "customer"):
        wanted = SUPPLIER_SOURCES if dimension == "supplier" else CUSTOMER_SOURCES
        contacts = _contact_by_source(db, {(k, m.row.source_id) for m, k in relevant if k in wanted})
        if contacts:
            names = {
                cid: name
                for cid, name in db.query(Contact.id, Contact.name)
                .filter(Contact.id.in_(set(contacts.values())))
                .all()
            }

    buckets: dict[str, Bucket] = {}
    for move, kind in relevant:
        row = move.row
        if dimension == "purpose":
            key, label = kind, PURPOSE_LABELS.get(kind, kind)
        else:
            wanted = SUPPLIER_SOURCES if dimension == "supplier" else CUSTOMER_SOURCES
            if kind not in wanted:
                continue
            contact_id = contacts.get((kind, row.source_id))
            #: سندِ بی‌طرف‌حساب (رسیدِ مستقیمِ بی تحویل‌دهنده) در این بُعد جایی
            #: ندارد — جمع‌کردنش زیرِ «نامشخص» یک ردیفِ بی‌معنا می‌سازد.
            if contact_id is None:
                continue
            key, label = str(contact_id), names.get(contact_id, "—")

        bucket = buckets.setdefault(key, Bucket(key=key, label=label))
        qty = move.qty
        if qty > 0:
            bucket.in_qty += qty
            bucket.in_value += move.value
        else:
            bucket.out_qty += -qty
            bucket.out_value += -move.value
        bucket.stale_count += 1 if move.stale else 0
        bucket.items.add(row.item_id)

    ordered = sorted(buckets.values(), key=lambda b: (-abs(b.net_qty), b.label))
    return {
        "dimension": dimension,
        "dimension_label": DIMENSION_LABELS[dimension],
        "date_from": date_from,
        "date_to": date_to,
        "warehouse_id": warehouse_id,
        "rows": [
            {
                "key": b.key,
                "label": b.label,
                "item_count": len(b.items),
                "in_qty": b.in_qty,
                "out_qty": b.out_qty,
                "net_qty": b.net_qty,
                "in_value": valuation.rial(b.in_value),
                "out_value": valuation.rial(b.out_value),
                "net_value": valuation.rial(b.net_value),
                "stale_count": b.stale_count,
            }
            for b in ordered
        ],
        "total_in_qty": sum((b.in_qty for b in ordered), Decimal(0)),
        "total_out_qty": sum((b.out_qty for b in ordered), Decimal(0)),
        "total_in_value": valuation.rial(sum((b.in_value for b in ordered), Decimal(0))),
        "total_out_value": valuation.rial(sum((b.out_value for b in ordered), Decimal(0))),
        "stale_count": sum(b.stale_count for b in ordered),
    }
