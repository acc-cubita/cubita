"""قیمت‌گذاریِ ورودی‌های بی‌فی — مقدار حالا، بها بعداً.

**چرا لازم است.** رسیدِ انبارِ مستقیم می‌تواند بی فی ثبت شود و این یک حالتِ خطا
نیست، یک واقعیتِ کاری است: کالایی که *خارج از سیستم* تهیه شده — تولیدِ کارگاهی
که اجزایش هیچ‌وقت در کوبیتا ثبت نشده، یا خریدی که سندش هنوز نرسیده. تا امروز
نتیجه‌اش این بود:

    رسیدِ تولید بدون فی → ۱۵ واحد وارد انبار، فی = ۰، سند = هیچ، میانگین = ۰

کالا در انبار بود و ارزشش صفر. و چون رسید **ویرایش نمی‌شود** (فقط ابطال)، هیچ
راهِ برگشتی نبود. وقتی آن ۱۵ واحد فروخته می‌شد بهای فروش‌رفته صفر درمی‌آمد و سود
به اندازه‌ی کلِ فروش باد می‌کرد — بی هیچ هشداری.

**مرزِ عمدی: این ماژول فقط چیزی را قیمت‌گذاری می‌کند که هیچ قیمتی ندارد.**

ردیفی که یک‌بار فی گرفت، از این مسیر عوض نمی‌شود. دلیلش دو چیز است:

۱. تغییرِ بهای یک ورودیِ گذشته کلِ زنجیره‌ی پس از خودش را جابه‌جا می‌کند (میانگین،
   بهای خروج‌ها، بهای فروش‌رفته، سود). راهِ کوبیتا برای این کار از قبل هست و
   صریح است: **ابطال و ثبتِ دوباره**. مسیرِ دومی که بی‌صدا عدد را عوض کند یعنی
   دو رفتار برای یک کار.
۲. با همین مرز، «نسخه‌بندیِ قیمت» و تشخیصِ «تلاشِ دوباره از تغییرِ عمدی» اصلاً
   لازم نمی‌شود: اجرای دوباره‌ی همان فرمان ردیف‌ها را دیگر بی‌فی نمی‌بیند و
   کاری نمی‌کند. یکتاسازی از **شکلِ داده** می‌آید، نه از یک جدولِ نسخه.

**حرکتِ انبار ساخته نمی‌شود.** مقدار قبلاً سرِ رسید وارد شده. این‌جا فقط بهای
همان حرکت پر می‌شود. ساختِ حرکتِ دوم یعنی کالا دو بار وارد انبار شود.

**سند همان سندی است که رسید می‌زد.** از `_direct_journal_lines`ِ خودِ رسید
استفاده می‌شود، نه یک سازنده‌ی دوم — پس طرفِ بستانکار همان است که نوعِ رسید
می‌گوید (تولید → جریانِ ساخت، افتتاحیه → حساب افتتاحیه، خرید → بدهی/نقد).

**مالیات بازمحاسبه نمی‌شود.** اعتبارِ مالیاتی پشتوانه‌ی سندِ فروشنده را می‌خواهد
و این مسیر فروشنده‌ای نمی‌شناسد. بهای کالا پر می‌شود، مالیات صفر می‌ماند.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.audit import record_change
from app.models.advanced_inventory import StockBatch
from app.models.inventory import Item, StockLedger
from app.models.invoices import RECEIPT_TYPE_LABELS, WarehouseReceipt, WarehouseReceiptLine
from app.models.user import User
from app.services import valuation
from app.services.common import make_journal_entry
from app.services.inventory import lock_items
from app.services.period_close import assert_period_open


def _eligible_query(db: Session, *, warehouse_id: UUID, date_from: date, date_to: date):
    """ردیف‌های واجدِ شرایط — و تعریفِ «واجد شرایط» فقط همین‌جاست.

    رسیدِ **مستقیم** (رسیدِ گره‌خورده به فاکتور بهایش را از فاکتور می‌گیرد و اصلاً
    بی‌فی نمی‌ماند)، **باطل‌نشده**، و ردیفی که هنوز هیچ فی نگرفته.
    """
    return (
        db.query(WarehouseReceiptLine, WarehouseReceipt, Item)
        .join(WarehouseReceipt, WarehouseReceiptLine.receipt_id == WarehouseReceipt.id)
        .join(Item, WarehouseReceiptLine.item_id == Item.id)
        .filter(
            WarehouseReceipt.warehouse_id == warehouse_id,
            WarehouseReceipt.receipt_date >= date_from,
            WarehouseReceipt.receipt_date <= date_to,
            WarehouseReceipt.purchase_invoice_id.is_(None),
            WarehouseReceipt.voided_at.is_(None),
            WarehouseReceiptLine.unit_cost == 0,
            WarehouseReceiptLine.qty > 0,
            Item.is_service.is_(False),
        )
    )


def unpriced_outputs(
    db: Session, *, warehouse_id: UUID, date_from: date, date_to: date
) -> list[dict]:
    """ورودی‌های بی‌فیِ یک انبار در یک بازه — **کالا‌محور**، مثلِ فرمِ مرجع.

    یک کالا ممکن است در چند رسید آمده باشد؛ همه‌شان یک ردیف می‌شوند با جمعِ
    مقدار، و شماره‌ی رسیدها کنارش می‌آید تا کاربر بداند فی روی چه چیزی می‌نشیند.
    """
    buckets: dict[UUID, dict] = {}
    for line, receipt, item in _eligible_query(
        db, warehouse_id=warehouse_id, date_from=date_from, date_to=date_to
    ).all():
        bucket = buckets.setdefault(
            item.id,
            {
                "item_id": item.id,
                "sku": item.sku,
                "name": item.name,
                "unit": item.unit,
                "qty": Decimal(0),
                "receipts": [],
            },
        )
        bucket["qty"] += Decimal(line.qty)
        entry = (receipt.number, receipt.receipt_date, receipt.receipt_type)
        if entry not in bucket["receipts"]:
            bucket["receipts"].append(entry)

    rows = sorted(buckets.values(), key=lambda r: (r["sku"] or "", r["name"]))
    for row in rows:
        row["receipts"] = [
            {
                "number": number,
                "receipt_date": on,
                "type_label": RECEIPT_TYPE_LABELS.get(kind, kind),
            }
            for number, on, kind in sorted(row["receipts"])
        ]
    return rows


def _rows_for_journal(db: Session, lines: list[WarehouseReceiptLine]) -> list[dict]:
    """شکلی که `_direct_journal_lines` می‌شناسد — تا سازنده‌ی سند یکی بماند."""
    return [
        {
            "item": db.get(Item, line.item_id),
            "qty": Decimal(line.qty),
            "unit_cost": Decimal(line.unit_cost),
            #: مالیات این‌جا بازمحاسبه نمی‌شود — بالای فایل، بندِ آخر.
            "tax_amount": Decimal(0),
        }
        for line in lines
    ]


def apply_prices(
    db: Session,
    *,
    warehouse_id: UUID,
    date_from: date,
    date_to: date,
    prices: dict[UUID, Decimal],
    user: User,
) -> dict:
    """فی‌های داده‌شده را روی ردیف‌های بی‌فیِ دامنه می‌نشاند.

    کالایی که در `prices` نیامده دست‌نخورده می‌ماند — قیمت‌گذاریِ جزئی مجاز است،
    چون خلافش یعنی کاربر تا وقتی *همه‌ی* اقلام را نداند هیچ‌کدام را نتواند ثبت
    کند.
    """
    from app.services.warehouse_receipts import _direct_journal_lines

    positive = {item_id: Decimal(cost) for item_id, cost in prices.items() if Decimal(cost) > 0}
    if not positive:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "هیچ فی‌ای وارد نشده است")

    #: قفلِ کالاها پیش از خواندنِ ردیف‌ها — همان الگوی هر ثبتی که میانگین را
    #: می‌خواند و می‌نویسد.
    lock_items(db, positive.keys())

    pairs = [
        (line, receipt)
        for line, receipt, _item in _eligible_query(
            db, warehouse_id=warehouse_id, date_from=date_from, date_to=date_to
        ).all()
        if line.item_id in positive
    ]
    if not pairs:
        return {"receipts": 0, "lines": 0, "value": Decimal(0)}

    receipts: dict[UUID, WarehouseReceipt] = {}
    by_receipt: dict[UUID, list[WarehouseReceiptLine]] = defaultdict(list)
    for line, receipt in pairs:
        #: سندِ این رسید به تاریخِ خودش می‌خورد، پس دوره‌اش باید باز باشد.
        assert_period_open(db, receipt.receipt_date)
        receipts[receipt.id] = receipt
        by_receipt[receipt.id].append(line)

    total_value = Decimal(0)

    for receipt_id, lines in by_receipt.items():
        receipt = receipts[receipt_id]
        changes: dict[str, dict] = {}
        for line in lines:
            unit_cost = positive[line.item_id]
            line.unit_cost = unit_cost
            total_value += Decimal(line.qty) * unit_cost
            changes[f"ردیف {line.seq or '؟'} — فی"] = {"from": Decimal(0), "to": unit_cost}

            #: **همان حرکت، نه حرکتِ تازه.** مقدار سرِ رسید وارد شده؛ فقط بهایش
            #: پر می‌شود. ساختِ ردیفِ دوم یعنی کالا دو بار وارد انبار شود.
            move = (
                db.query(StockLedger)
                .filter(
                    StockLedger.item_id == line.item_id,
                    StockLedger.warehouse_id == receipt.warehouse_id,
                    StockLedger.entry_date == receipt.receipt_date,
                    StockLedger.source_type == "warehouse_receipt",
                    StockLedger.source_id == receipt.id,
                    StockLedger.unit_cost == 0,
                )
                .first()
            )
            if move is not None:
                move.unit_cost = unit_cost

            #: بچ هم همان بچِ ساخته‌شده سرِ رسید است. اگر بی‌فی بماند،
            #: ارزش‌گذاریِ بچ‌محور با ارزش‌گذاریِ کالا واگرا می‌شود.
            batch = (
                db.query(StockBatch)
                .filter(
                    StockBatch.source_type == "warehouse_receipt",
                    StockBatch.source_id == receipt.id,
                    StockBatch.item_id == line.item_id,
                    StockBatch.unit_cost == 0,
                )
                .first()
            )
            if batch is not None:
                batch.unit_cost = unit_cost

        db.flush()

        #: سند از سازنده‌ی خودِ رسید می‌آید، پس طرفِ بستانکار همانی است که نوعِ
        #: رسید می‌گوید. رسیدِ بی‌فی سندی نزده بود؛ حالا می‌زند.
        journal_lines = _direct_journal_lines(db, receipt, _rows_for_journal(db, lines))
        if journal_lines and receipt.journal_entry_id is None:
            entry = make_journal_entry(
                db,
                receipt.receipt_date,
                f"قیمت‌گذاری رسید انبار شماره {receipt.number} "
                f"({RECEIPT_TYPE_LABELS.get(receipt.receipt_type, receipt.receipt_type)})",
                "warehouse_receipt",
                user,
                journal_lines,
            )
            receipt.journal_entry_id = entry.id

        record_change(
            db,
            receipt,
            changes,
            f"قیمت‌گذاری {len(lines)} ردیفِ بی‌فی رسید انبار شماره {receipt.number}",
        )

    #: **بازمحاسبه‌ی کامل، نه `settle_posting`.** آن یکی سندِ *تازه* را تسویه
    #: می‌کند و وقتی حرکتی جلوتر نباشد کاری نمی‌کند — چون ثبتِ لحظه‌ای با بازپخش
    #: یکی است. این‌جا **گذشته عوض شده**: حرکتی که با صفر نشسته بود حالا بها
    #: دارد، پس میانگین باید از اول ساخته شود حتی اگر آخرین حرکتِ کالا باشد.
    voided = valuation.voided_sources(db)
    for item_id in {line.item_id for line, _ in pairs}:
        item = db.get(Item, item_id)
        if item is not None:
            valuation.recompute(db, item, voided=voided)
    db.flush()

    return {"receipts": len(by_receipt), "lines": len(pairs), "value": total_value}
