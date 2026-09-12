from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.banking import BankAccount, Check
from app.models.inventory import Contact, Item, StockLedger
from app.models.invoices import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
)
from app.models.returns import PurchaseReturn, SalesReturn, SalesReturnLine
from app.models.treasury import TreasuryTransaction
from app.jalali import jalali_to_gregorian, persian_year_end, persian_year_start
from app.services import chart_codes as cc

AGING_KINDS = ("receivable", "payable")

#: فصل‌های شمسی → ماهِ شروع و برچسب. ۰ = کلِ سال.
QUARTER_START_MONTH = {1: 1, 2: 4, 3: 7, 4: 10}
QUARTER_LABELS = {0: "کل سال", 1: "بهار", 2: "تابستان", 3: "پاییز", 4: "زمستان"}

CREDIT_NORMAL_TYPES = ("liability", "equity", "income")

#: نقش‌های حسابِ نقد و شبه‌نقد — پایه‌ی صورت جریان وجوه نقد.
CASH_ROLES = (cc.CASH, cc.BANK, cc.PETTY_CASH)
#: حساب‌های دارایی ثابت — طبقه‌بندیِ «سرمایه‌گذاری» حتی اگر مشتری کدشان را عوض کرده باشد.
FIXED_ASSET_ROLES = (cc.FIXED_ASSETS, cc.ACCUMULATED_DEPRECIATION)


def get_sales_summary(db: Session) -> dict:
    """شاخص‌های فروش را در پایگاه‌داده جمع می‌زند تا کلاینت مجبور نباشد کلِ تاریخچه را
    دانلود کند (که کند است و در کسب‌وکارِ واقعی از سقفِ صفحه‌بندی فراتر می‌رود).

    فقط فاکتورهای باطل‌نشده. سود ناخالص = خالص − بهای تمام‌شده؛ مالیات درآمد نیست و
    در سود نمی‌آید.
    """
    count, net, tax, additions, duties, rounding, cost = (
        db.query(
            func.count(SalesInvoice.id),
            func.coalesce(func.sum(SalesInvoice.total_amount), 0),
            func.coalesce(func.sum(SalesInvoice.tax_amount), 0),
            func.coalesce(func.sum(SalesInvoice.total_additions), 0),
            func.coalesce(func.sum(SalesInvoice.total_duties), 0),
            func.coalesce(func.sum(SalesInvoice.rounding), 0),
            func.coalesce(func.sum(SalesInvoice.total_cost), 0),
        )
        .filter(SalesInvoice.voided_at.is_(None))
        .one()
    )

    cutoff = date.today() - timedelta(days=30)
    last30 = (
        db.query(func.coalesce(func.sum(
            SalesInvoice.total_amount + SalesInvoice.tax_amount + SalesInvoice.total_additions
            + SalesInvoice.total_duties + SalesInvoice.rounding
        ), 0))
        .filter(SalesInvoice.voided_at.is_(None), SalesInvoice.invoice_date >= cutoff)
        .scalar()
    )

    net, tax, cost = Decimal(net), Decimal(tax), Decimal(cost)
    with_tax = net + tax + Decimal(additions) + Decimal(duties) + Decimal(rounding)
    profit = net - cost
    margin = (profit / net * 100) if net > 0 else Decimal(0)
    avg = (with_tax / count) if count else Decimal(0)
    return {
        "invoice_count": int(count),
        "total_net": net,
        "total_tax": tax,
        "total_with_tax": with_tax,
        "total_cost": cost,
        "gross_profit": profit,
        "margin_pct": margin.quantize(Decimal("0.01")),
        "last_30_with_tax": Decimal(last30),
        "avg_invoice": avg.quantize(Decimal(1)),
    }


def get_purchase_summary(db: Session) -> dict:
    """شاخص‌های خرید را در پایگاه‌داده جمع می‌زند (قرینه‌ی get_sales_summary، بدون سود)."""
    count, net, tax = (
        db.query(
            func.count(PurchaseInvoice.id),
            func.coalesce(func.sum(PurchaseInvoice.total_amount), 0),
            func.coalesce(func.sum(PurchaseInvoice.tax_amount), 0),
        )
        .filter(PurchaseInvoice.voided_at.is_(None))
        .one()
    )

    cutoff = date.today() - timedelta(days=30)
    last30 = (
        db.query(func.coalesce(func.sum(PurchaseInvoice.total_amount + PurchaseInvoice.tax_amount), 0))
        .filter(PurchaseInvoice.voided_at.is_(None), PurchaseInvoice.invoice_date >= cutoff)
        .scalar()
    )

    net, tax = Decimal(net), Decimal(tax)
    with_tax = net + tax
    avg = (with_tax / count) if count else Decimal(0)
    return {
        "invoice_count": int(count),
        "total_net": net,
        "total_tax": tax,
        "total_with_tax": with_tax,
        "last_30_with_tax": Decimal(last30),
        "avg_invoice": avg.quantize(Decimal(1)),
    }


def get_vat_report(db: Session, date_from: date | None, date_to: date | None) -> dict:
    """جمعِ خالص و مالیاتِ فاکتورهای فروش (خروجی) و خرید (ورودی) در بازه.

    فقط فاکتورهای باطل‌نشده حساب می‌شوند؛ فاکتور باطل اثری در بدهیِ مالیاتی ندارد.
    """

    def sums(model, date_col, voidable: bool) -> tuple[Decimal, Decimal]:
        query = db.query(
            func.coalesce(func.sum(model.total_amount), 0),
            func.coalesce(func.sum(model.tax_amount), 0),
        )
        # برگشت‌ها ستون ابطال ندارند (خودشان سندِ اصلاحی‌اند)، پس این فیلتر فقط
        # برای فاکتورها معنا دارد.
        if voidable:
            query = query.filter(model.voided_at.is_(None))
        if date_from is not None:
            query = query.filter(date_col >= date_from)
        if date_to is not None:
            query = query.filter(date_col <= date_to)
        net, tax = query.one()
        return Decimal(net), Decimal(tax)

    def split(invoice_model, line_model, date_col) -> dict:
        """پایه‌ی مالیاتی را به چهار سطل تفکیک می‌کند: مشمول/معاف × کالا/خدمت.

        **از ردیف‌ها جمع می‌شود نه سربرگ**، و این دقیق است چون تخفیفِ سطحِ فاکتور
        از قبل بینِ ردیف‌ها تسهیم شده (`invoices.py`): خالصِ ردیف =
        `qty×price − discount`، و جمعشان همان `total_amount` است. پس تفکیک بدونِ
        تسهیمِ نسبی درست درمی‌آید — تستِ `test_the_four_buckets_sum_to_the_total`
        همین برابری را قفل می‌کند.

        `vat_status` از **ردیف** خوانده می‌شود نه از کالا: وضعیتِ لحظه‌ی معامله،
        نه وضعیتِ امروز. `is_service` برعکس از کالا می‌آید — کالا/خدمت بودن
        واقعیتی فیزیکی است، نه طبقه‌بندیِ قانونی که با قانون عوض شود.
        """
        price_col = (
            line_model.unit_price if hasattr(line_model, "unit_price") else line_model.unit_cost
        )
        net = func.coalesce(func.sum(line_model.qty * price_col - line_model.discount), 0)
        query = (
            db.query(line_model.vat_status, Item.is_service, net)
            .join(invoice_model, line_model.invoice_id == invoice_model.id)
            .join(Item, line_model.item_id == Item.id)
            .filter(invoice_model.voided_at.is_(None))
        )
        if date_from is not None:
            query = query.filter(date_col >= date_from)
        if date_to is not None:
            query = query.filter(date_col <= date_to)

        out = {
            "taxable_goods": Decimal(0),
            "taxable_services": Decimal(0),
            "exempt_goods": Decimal(0),
            "exempt_services": Decimal(0),
        }
        for status, is_service, amount in query.group_by(line_model.vat_status, Item.is_service):
            prefix = "exempt" if status == "exempt" else "taxable"
            suffix = "services" if is_service else "goods"
            out[f"{prefix}_{suffix}"] += Decimal(amount)
        return out

    def mixed_invoices(invoice_model, line_model, date_col) -> list[dict]:
        """فاکتورهایی که ردیفِ معاف و مشمول را با هم دارند و نرخِ سربرگشان غیرصفر است.

        این‌ها **روی ردیفِ معاف هم مالیات گرفته‌اند**، چون مالیات یک نرخ روی کلِ
        فاکتور است (`compute_tax(total_amount, tax_rate)`).

        **گزارش است نه گارد:** فاکتورِ ثبت‌شده ویرایش نمی‌شود و مسدودکردنِ گزارش
        هیچ‌چیز را درست نمی‌کند؛ چیزی که کمک می‌کند این است که حسابدار بداند.
        """
        exempt_net = func.coalesce(
            func.sum(
                case(
                    (
                        line_model.vat_status == "exempt",
                        line_model.qty
                        * (
                            line_model.unit_price
                            if hasattr(line_model, "unit_price")
                            else line_model.unit_cost
                        )
                        - line_model.discount,
                    ),
                    else_=0,
                )
            ),
            0,
        )
        query = (
            db.query(
                invoice_model.id,
                invoice_model.number,
                date_col,
                invoice_model.tax_amount,
                func.count(func.distinct(line_model.vat_status)),
                exempt_net,
            )
            .join(line_model, line_model.invoice_id == invoice_model.id)
            .filter(invoice_model.voided_at.is_(None), invoice_model.tax_rate > 0)
        )
        if date_from is not None:
            query = query.filter(date_col >= date_from)
        if date_to is not None:
            query = query.filter(date_col <= date_to)
        rows = query.group_by(invoice_model.id, invoice_model.number, date_col, invoice_model.tax_amount).having(
            func.count(func.distinct(line_model.vat_status)) > 1
        ).all()
        return [
            {
                "invoice_id": iid,
                "number": number,
                "invoice_date": idate,
                "tax_amount": Decimal(tax),
                "exempt_net": Decimal(ex_net),
            }
            for iid, number, idate, tax, _kinds, ex_net in rows
        ]

    sales_net, output_vat = sums(SalesInvoice, SalesInvoice.invoice_date, True)
    purchase_net, input_vat = sums(PurchaseInvoice, PurchaseInvoice.invoice_date, True)
    sales_ret_net, sales_ret_vat = sums(SalesReturn, SalesReturn.return_date, False)
    purchase_ret_net, purchase_ret_vat = sums(PurchaseReturn, PurchaseReturn.return_date, False)

    # کالایی که برگشت خورده نه فروش است نه خرید؛ پس هم از پایه و هم از مالیات کم
    # می‌شود. رقمِ اظهارنامه باید همان چیزی باشد که واقعاً در دفاتر مانده.
    return {
        "date_from": date_from,
        "date_to": date_to,
        "sales_net": sales_net - sales_ret_net,
        "output_vat": output_vat - sales_ret_vat,
        "purchase_net": purchase_net - purchase_ret_net,
        "input_vat": input_vat - purchase_ret_vat,
        "net_vat": (output_vat - sales_ret_vat) - (input_vat - purchase_ret_vat),
        "sales_returns_net": sales_ret_net,
        "sales_returns_vat": sales_ret_vat,
        "purchase_returns_net": purchase_ret_net,
        "purchase_returns_vat": purchase_ret_vat,
        #: تفکیکِ پایه — جوابِ «چقدر فروشِ معاف داشته‌ایم؟». برگشت‌ها در این تفکیک
        #: نمی‌آیند: ارقامِ بالا خالصِ پس از برگشت‌اند و این‌ها *ترکیبِ* فروشِ دوره را
        #: نشان می‌دهند. یکی‌کردنشان دو معنا را در یک عدد قاطی می‌کرد.
        "sales_breakdown": split(SalesInvoice, SalesInvoiceLine, SalesInvoice.invoice_date),
        "purchase_breakdown": split(
            PurchaseInvoice, PurchaseInvoiceLine, PurchaseInvoice.invoice_date
        ),
        "mixed_sales_invoices": mixed_invoices(
            SalesInvoice, SalesInvoiceLine, SalesInvoice.invoice_date
        ),
        "mixed_purchase_invoices": mixed_invoices(
            PurchaseInvoice, PurchaseInvoiceLine, PurchaseInvoice.invoice_date
        ),
    }


def _seasonal_range(year: int, quarter: int) -> tuple[date, date]:
    """بازه‌ی میلادیِ یک فصلِ شمسی (۱..۴) یا کلِ سال (۰)."""
    if quarter == 0:
        return persian_year_start(year), persian_year_end(year)
    start_month = QUARTER_START_MONTH[quarter]
    date_from = jalali_to_gregorian(year, start_month, 1)
    if quarter == 4:
        date_to = persian_year_end(year)
    else:
        date_to = jalali_to_gregorian(year, start_month + 3, 1) - timedelta(days=1)
    return date_from, date_to


#: طولِ شناسه‌ی هویتی به تفکیکِ نوعِ شخص — کدِ ملیِ حقیقی ۱۰ رقم، شناسه‌ی ملیِ
#: حقوقی ۱۱ رقم. کامنتِ `Contact.national_id` همین را می‌گوید ولی هیچ‌جا سنجیده
#: نمی‌شد؛ کدِ ۱۰رقمی روی شخصِ حقوقی *پُر* به‌نظر می‌رسد و سرِ آپلود رد می‌شود.
NATIONAL_ID_LENGTH = {"real": 10, "legal": 11}


def _seasonal_issues(contact) -> list[str]:
    """چه چیزی از هویتِ مالیاتیِ این طرف‌حساب کم یا بدشکل است.

    **کدِ ماشین‌خوان برمی‌گرداند، نه متنِ فارسی.** برچسب کارِ رابط است (کنارِ
    `ENTITY_LABEL`)، و کد اجازه می‌دهد بعداً بدونِ شکستنِ چیزی فیلتر و شمارش شود.

    **گزارش است، نه گارد**: خروجی هرگز مسدود نمی‌شود. کاری که این‌جا می‌شود فقط
    این است که حسابدار *پیش از* آپلود بداند کدام ردیف رد خواهد شد، نه بعدش.
    """
    issues: list[str] = []
    if not (contact.national_id or "").strip():
        issues.append("national_id_missing")
    else:
        expected = NATIONAL_ID_LENGTH.get(contact.entity_type)
        if expected is not None and len(contact.national_id.strip()) != expected:
            issues.append("national_id_length")
    if not (contact.economic_code or "").strip():
        issues.append("economic_code_missing")
    if not (contact.postal_code or "").strip():
        issues.append("postal_code_missing")
    return issues


def get_seasonal_report(db: Session, year: int, quarter: int) -> dict:
    """گزارشِ معاملاتِ فصلی (ماده ۱۶۹ ق.م.م): تجمیعِ خرید و فروشِ یک فصلِ شمسی به
    تفکیکِ طرف حساب. فاکتورهای باطل حساب نمی‌شوند؛ برگشت‌ها (از روی فاکتورِ اصلی) از
    مبلغِ همان طرف حساب کسر می‌شوند تا رقمِ سامانه دقیقاً چیزی باشد که در دفاتر مانده.
    فاکتورهای بدونِ طرف حساب (فروشِ نقدی/خرده) در یک ردیفِ تجمیعیِ «معاملاتِ خرد» جمع می‌شوند.
    """
    if quarter not in (0, 1, 2, 3, 4):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فصل باید بین ۰ تا ۴ باشد")
    date_from, date_to = _seasonal_range(year, quarter)

    def build_section(invoice_model, date_col, return_model, return_date_col, return_fk) -> dict:
        acc: dict[UUID | None, dict] = {}

        def bucket(cid: UUID | None) -> dict:
            return acc.setdefault(
                cid, {"count": 0, "net": Decimal(0), "discount": Decimal(0), "vat": Decimal(0)}
            )

        inv_rows = (
            db.query(
                invoice_model.contact_id,
                func.count(invoice_model.id),
                func.coalesce(func.sum(invoice_model.total_amount), 0),
                func.coalesce(func.sum(invoice_model.total_discount), 0),
                func.coalesce(func.sum(invoice_model.tax_amount), 0),
            )
            .filter(
                invoice_model.voided_at.is_(None),
                date_col >= date_from,
                date_col <= date_to,
            )
            .group_by(invoice_model.contact_id)
            .all()
        )
        for cid, cnt, net, disc, vat in inv_rows:
            b = bucket(cid)
            b["count"] += cnt
            b["net"] += Decimal(net)
            b["discount"] += Decimal(disc)
            b["vat"] += Decimal(vat)

        # برگشت‌ها: از طریقِ فاکتورِ اصلی به طرف حساب نسبت داده و از خالص/مالیات کم می‌شوند.
        ret_rows = (
            db.query(
                invoice_model.contact_id,
                func.coalesce(func.sum(return_model.total_amount), 0),
                func.coalesce(func.sum(return_model.tax_amount), 0),
            )
            .join(invoice_model, return_fk == invoice_model.id)
            .filter(
                invoice_model.voided_at.is_(None),
                return_date_col >= date_from,
                return_date_col <= date_to,
            )
            .group_by(invoice_model.contact_id)
            .all()
        )
        for cid, ret_net, ret_vat in ret_rows:
            b = bucket(cid)
            b["net"] -= Decimal(ret_net)
            b["vat"] -= Decimal(ret_vat)

        # هویتِ طرف‌حساب‌ها را یک‌جا واکشی کن.
        contact_ids = [cid for cid in acc if cid is not None]
        contacts = {c.id: c for c in db.query(Contact).filter(Contact.id.in_(contact_ids))} if contact_ids else {}

        rows = []
        for cid, b in acc.items():
            net = b["net"]
            gross = net + b["discount"]
            vat = b["vat"]
            if cid is None:
                rows.append({
                    "contact_id": None,
                    "contact_name": "معاملاتِ خرد (بدون طرف حساب)",
                    "entity_type": "aggregate",
                    "national_id": None,
                    "economic_code": None,
                    "postal_code": None,
                    "invoice_count": b["count"],
                    "gross": gross,
                    "discount": b["discount"],
                    "net": net,
                    "vat": vat,
                    "total": net + vat,
                    #: **این ردیف هرگز ایراد نمی‌گیرد.** طرف‌حساب نیست؛ سطلِ فروشِ
                    #: نقدی/خرده است و اصلاً هویتِ مالیاتی ندارد که کم داشته باشد.
                    #: بدونِ این کامنت، دفعه‌ی بعد کسی «درستش» می‌کند.
                    "issues": [],
                })
            else:
                c = contacts.get(cid)
                rows.append({
                    "contact_id": cid,
                    "contact_name": c.name if c else "—",
                    "entity_type": c.entity_type if c else "real",
                    "national_id": c.national_id if c else None,
                    "economic_code": c.economic_code if c else None,
                    "postal_code": c.postal_code if c else None,
                    "invoice_count": b["count"],
                    "gross": gross,
                    "discount": b["discount"],
                    "net": net,
                    "vat": vat,
                    "total": net + vat,
                    "issues": _seasonal_issues(c) if c else [],
                })

        # بزرگ‌ترین معامله‌ها بالا؛ ردیفِ تجمیعیِ خرد ته.
        #
        # ردیف‌های ناقص عمداً بالا کشیده *نمی‌شوند*: ترتیبِ مبلغ همان چیزی است که
        # حسابدار برای خواندنِ گزارش می‌خواهد. پیداکردنشان کارِ فیلترِ «فقط ناقص‌ها»
        # در رابط است، نه به‌هم‌ریختنِ ترتیبِ اصلی.
        rows.sort(key=lambda r: (r["contact_id"] is None, -r["net"]))
        return {
            "rows": rows,
            "ready_count": sum(1 for r in rows if not r["issues"]),
            "incomplete_count": sum(1 for r in rows if r["issues"]),
            "total_gross": sum((r["gross"] for r in rows), Decimal(0)),
            "total_discount": sum((r["discount"] for r in rows), Decimal(0)),
            "total_net": sum((r["net"] for r in rows), Decimal(0)),
            "total_vat": sum((r["vat"] for r in rows), Decimal(0)),
            "total_total": sum((r["total"] for r in rows), Decimal(0)),
        }

    sales = build_section(
        SalesInvoice, SalesInvoice.invoice_date, SalesReturn, SalesReturn.return_date,
        SalesReturn.sales_invoice_id,
    )
    purchases = build_section(
        PurchaseInvoice, PurchaseInvoice.invoice_date, PurchaseReturn, PurchaseReturn.return_date,
        PurchaseReturn.purchase_invoice_id,
    )
    return {
        "year": year,
        "quarter": quarter,
        "quarter_label": QUARTER_LABELS[quarter],
        "date_from": date_from,
        "date_to": date_to,
        "sales": sales,
        "purchases": purchases,
    }


#: منشأهایی که سندِ *دوره‌ای* می‌سازند، نه رویدادِ کسب‌وکار: افتتاحیه، اختتامیه و
#: بستنِ سود و زیان. حسابدار گاهی می‌خواهد «گردشِ عملیاتیِ دوره» را بدونِ این‌ها
#: ببیند و گاهی مانده‌ی واقعیِ دفتر را با آن‌ها؛ پس ورودشان باید صریح باشد نه ثابت.
SYSTEM_SOURCE_TYPES = frozenset(
    {"opening", "opening_balance", "opening_entry", "closing_entry", "period_close"}
)


@dataclass(frozen=True)
class ReportFilters:
    """دامنه‌ی محاسبه‌ی هر گزارشِ حسابداری — **یک مجموعه برای هر سه خانواده**.

    تراز و مرور حساب و دفتر باید با یک فیلتر یک عدد بدهند؛ راهش این است که هر سه
    از همین یک شیء بخوانند، نه اینکه هرکدام فیلترهای خودش را داشته باشد.

    **پیش‌فرضِ هر میدان «چیزی عوض نمی‌شود» است.** ساختِ `ReportFilters()` خالی باید
    دقیقاً همان چیزی بدهد که پیش از وجودِ این کلاس برمی‌گشت — یک تست همین را قفل
    می‌کند.
    """

    date_from: date | None = None
    date_to: date | None = None
    #: محدوده‌ی **شماره‌ی سند**، نه شناسه. حسابدار با شماره کار می‌کند.
    entry_from: int | None = None
    entry_to: int | None = None
    #: `temporary` یا `permanent`؛ `None` یعنی هر دو. سندِ موقت هنوز رسمی نیست و
    #: گزارشِ رسمی نباید بی‌دلیل با آن یکی گرفته شود.
    status: str | None = None
    source_type: str | None = None
    cost_center_id: UUID | None = None
    analytic_id: UUID | None = None
    #: افتتاحیه/اختتامیه/بستنِ سود و زیان وارد محاسبه شوند؟
    include_system_entries: bool = True


def _cost_center_scope(db: Session, center_id: UUID) -> set[UUID]:
    """مرکز و همه‌ی زیرمجموعه‌هایش — گزارشِ «شعبه تهران» باید پروژه‌های زیرش را هم بیاورد."""
    from app.services.cost_centers import _descendants, _index

    _by_id, children = _index(db)
    return _descendants(center_id, children)


def apply_report_filters(db: Session, query, filters: ReportFilters):
    """شرط‌های سطحِ سند و ردیف را به یک کوئری اضافه می‌کند — **بدونِ تاریخ**.

    تاریخ عمداً اینجا نیست. `get_balances` بازه را دو تکه می‌کند (گردشِ *پیش از*
    دوره و گردشِ *داخلِ* دوره) و اگر تاریخ همین‌جا اعمال می‌شد، تکه‌ی افتتاحیه هم
    فیلترِ بازه می‌خورد و همیشه صفر می‌شد. هر فراخوان تاریخِ خودش را می‌گذارد.

    کوئری باید از قبل به `JournalEntry` و `JournalLine` join شده باشد.
    """
    if filters.entry_from is not None:
        query = query.filter(JournalEntry.number >= filters.entry_from)
    if filters.entry_to is not None:
        query = query.filter(JournalEntry.number <= filters.entry_to)
    if filters.status in ("temporary", "permanent"):
        query = query.filter(JournalEntry.status == filters.status)
    if filters.source_type:
        query = query.filter(JournalEntry.source_type == filters.source_type)
    if not filters.include_system_entries:
        # `notin_` روی ستونِ NULL‌پذیر ردیفِ NULL را هم می‌اندازد، پس صریح نگه‌داشته
        # می‌شود: سندی که منشأ ندارد سندِ دوره‌ای هم نیست.
        query = query.filter(
            or_(
                JournalEntry.source_type.is_(None),
                JournalEntry.source_type.notin_(tuple(SYSTEM_SOURCE_TYPES)),
            )
        )
    if filters.cost_center_id is not None:
        query = query.filter(JournalLine.cost_center_id.in_(_cost_center_scope(db, filters.cost_center_id)))
    if filters.analytic_id is not None:
        query = query.filter(JournalLine.analytic_id == filters.analytic_id)
    return query


def _signed_balance(account_type: str, total_debit: Decimal, total_credit: Decimal) -> Decimal:
    if account_type in CREDIT_NORMAL_TYPES:
        return total_credit - total_debit
    return total_debit - total_credit


def descendant_account_ids(db: Session, root_id: UUID) -> set[UUID]:
    """شناسه‌ی حساب و همه‌ی نوادگانش — پایه‌ی هر گزارشی که یک سرفصل را جمع می‌زند.

    یک بار کلِ (id, parent_id) خوانده می‌شود و درخت در حافظه پیموده می‌شود؛ کوئریِ
    بازگشتی برای چارتی که چند صد ردیف است صرف نمی‌کند. `seen` حلقه را می‌شکند تا
    داده‌ی خرابِ درخت به‌جای پاسخ، پردازش را قفل نکند.
    """
    children: dict[UUID | None, list[UUID]] = {}
    for aid, pid in db.query(Account.id, Account.parent_id).all():
        children.setdefault(pid, []).append(aid)
    seen: set[UUID] = set()
    stack = [root_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(children.get(current, []))
    return seen


def get_general_ledger(
    db: Session,
    account_id: UUID | None,
    date_from: date | None = None,
    date_to: date | None = None,
    filters: ReportFilters | None = None,
) -> dict:
    """گردشِ یک حساب با مانده‌ی در حال اجرا — **شاملِ هر چه زیرش هست**.

    برای حسابِ برگ همان دفترِ معینِ همیشگی است. برای سرفصل (حسابِ کل) گردشِ همه‌ی
    زیرحساب‌هایش را به‌ترتیبِ تاریخ در یک دفتر می‌آورد — همان «دفتر کل».

    **دوباره‌شماری ممکن نیست:** `routers/accounts.py` اجازه نمی‌دهد حسابی هم ردیفِ
    مستقیم داشته باشد هم فرزند. پس هر حساب یا برگ است یا سرفصل، و جمعِ زیرشاخه
    هیچ مبلغی را دو بار نمی‌شمارد.

    `account_id = None` با `filters.analytic_id` یعنی **دفترِ تفصیلی**: گردشِ یک
    تفصیلی در همه‌ی حساب‌ها. ماهیتِ مانده آن‌وقت از خودِ حسابِ هر ردیف می‌آید، چون
    حسابِ واحدی در کار نیست.

    `filters` همان شیئی است که تراز و مرور حساب هم می‌گیرند؛ با یک فیلتر، هر سه
    باید یک عدد بدهند.

    سندِ باطل و معکوسش هر دو می‌مانند — مثلِ دفترِ روزنامه، به همان دلیل: دفتر باید
    نشان دهد اشتباه رخ داد و بعد اصلاح شد.
    """
    filters = filters or ReportFilters()
    account = None
    if account_id is not None:
        account = db.get(Account, account_id)
        if account is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب یافت نشد")
    elif filters.analytic_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای دفتر باید حساب یا تفصیلی انتخاب شود")

    query = (
        db.query(JournalLine, JournalEntry, Account)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
    )
    if account is not None:
        #: حسابِ سطحِ آخر نواده ندارد، پس خواندنِ کلِ چارت برای پیمودنِ درخت
        #: هزینه‌ی بی‌جاست — و دفترِ معین همان حالتی است که تقریباً همیشه باز
        #: می‌شود. برای سرفصل مسیرِ کاملِ درخت سرِ جایش می‌ماند.
        scope = {account.id} if not account.is_group else descendant_account_ids(db, account.id)
        query = query.filter(JournalLine.account_id.in_(scope))
    query = apply_report_filters(db, query, filters)

    def sign(line_account: Account, debit, credit) -> Decimal:
        #: ماهیت از حسابِ *خودِ ردیف* می‌آید وقتی حسابِ واحدی انتخاب نشده — یعنی در
        #: دفترِ تفصیلی که ردیف‌هایش می‌توانند از حساب‌های مختلف باشند.
        return _signed_balance((account or line_account).type, Decimal(debit), Decimal(credit))

    opening_balance = Decimal(0)
    if date_from is not None:
        for line, _entry, line_account in query.filter(JournalEntry.entry_date < date_from).all():
            opening_balance += sign(line_account, line.debit, line.credit)
        query = query.filter(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        query = query.filter(JournalEntry.entry_date <= date_to)

    #: `seq` و `id` ترتیبِ درونِ سند را قطعی می‌کنند؛ بدونشان دو ردیفِ یک سند در
    #: دفترِ کل هر بار جای هم عوض می‌شدند و مانده‌ی در حال اجرا ناپایدار می‌شد.
    rows = query.order_by(
        JournalEntry.entry_date, JournalEntry.number, JournalLine.seq, JournalLine.id
    ).all()

    running = opening_balance
    lines = []
    #: جمعِ ارزی به تفکیکِ ارز — «۱۰۰۰ دلار» با «۵۰۰ یورو» جمع‌شدنی نیست.
    fx_totals: dict[str, Decimal] = {}
    for line, entry, line_account in rows:
        running += sign(line_account, line.debit, line.credit)
        if line.currency_code and line.fx_amount is not None:
            fx = fx_totals.get(line.currency_code, Decimal(0))
            #: ارزی هم مثلِ ریالی علامت می‌گیرد: بدهکار مثبت، بستانکار منفی.
            fx_totals[line.currency_code] = fx + (
                Decimal(line.fx_amount) if Decimal(line.debit) > 0 else -Decimal(line.fx_amount)
            )
        lines.append(
            {
                "line_id": line.id,
                "entry_id": entry.id,
                "entry_number": entry.number,
                "entry_date": entry.entry_date,
                #: وضعیت و منشأ روی هر ردیف می‌آیند تا کاربر بدون بازکردنِ سند
                #: بفهمد این گردش موقت است یا دائم و از کجا آمده.
                "entry_status": entry.status,
                "source_type": entry.source_type,
                #: حسابِ خودِ ردیف، نه حسابی که کاربر انتخاب کرده. در دفترِ معین این
                #: دو یکی‌اند؛ در دفترِ کل همین ستون می‌گوید مبلغ از کدام زیرحساب آمد.
                "account_code": line_account.code,
                "account_name": line_account.name,
                "description": line.description or entry.description,
                "debit": line.debit,
                "credit": line.credit,
                "balance": running,
                #: ارز و پیگیری از قبل روی ردیف بودند و هیچ گزارشی نشانشان نمی‌داد.
                "currency_code": line.currency_code,
                "fx_amount": line.fx_amount,
                "fx_rate": line.fx_rate,
                "tracking_no": line.tracking_no,
                "tracking_date": line.tracking_date,
            }
        )

    return {
        "account_id": account.id if account else None,
        "account_code": account.code if account else None,
        "account_name": account.name if account else None,
        "opening_balance": opening_balance,
        "lines": lines,
        "closing_balance": running,
        "fx_totals": [{"currency_code": code, "amount": amount} for code, amount in sorted(fx_totals.items())],
    }


def _leaf_account_totals(
    db: Session,
    date_from: date | None,
    date_to: date | None,
    types: tuple[str, ...] | None = None,
    cost_center_ids: set[UUID] | None = None,
) -> list[tuple[Account, Decimal, Decimal]]:
    query = (
        db.query(Account, func.coalesce(func.sum(JournalLine.debit), 0), func.coalesce(func.sum(JournalLine.credit), 0))
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .filter(Account.is_group.is_(False))
    )
    if types is not None:
        query = query.filter(Account.type.in_(types))
    if cost_center_ids is not None:
        query = query.filter(JournalLine.cost_center_id.in_(cost_center_ids))
    if date_from is not None:
        query = query.filter(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        query = query.filter(JournalEntry.entry_date <= date_to)
    query = query.group_by(Account.id)

    return [(acc, Decimal(debit), Decimal(credit)) for acc, debit, credit in query.all()]


def get_trial_balance(
    db: Session,
    date_from: date | None,
    date_to: date | None,
    management_only: bool = False,
) -> list[dict]:
    """تراز آزمایشی.

    `management_only` تیکِ «نمایش در گزارشات مدیریتی» را به کار می‌گیرد: حساب‌های
    واسط و انتظامی برای مدیریت نویز‌اند ولی از دفتر حذف نمی‌شوند. پیش‌فرض خاموش
    است، پس ترازِ کامل — که مبنای کنترلِ توازن است — دست‌نخورده می‌ماند؛ صافی فقط
    وقتی اعمال می‌شود که گزارش‌گیرنده خودش خواسته باشد.
    """
    rows = _leaf_account_totals(db, date_from, date_to)
    if management_only:
        rows = [r for r in rows if r[0].in_management_reports]
    result = [
        {
            "account_id": acc.id,
            "account_code": acc.code,
            "account_name": acc.name,
            "account_type": acc.type,
            "total_debit": debit,
            "total_credit": credit,
            "balance": _signed_balance(acc.type, debit, credit),
        }
        for acc, debit, credit in rows
    ]
    return sorted(result, key=lambda r: r["account_code"])


def get_nature_violations(
    db: Session,
    date_from: date | None,
    date_to: date | None,
    controlled_only: bool = False,
) -> list[dict]:
    """حساب‌هایی که مانده‌شان خلافِ ماهیتشان است.

    **گزارش است، نه گارد.** خلافِ ماهیت شدن گاهی واقعاً درست است — اضافه‌برداشتِ
    بانکی، پیش‌دریافتِ مشتری روی حسابِ دریافتنی — پس مسدود کردنِ ثبت یعنی جلوگیری
    از ضبطِ رویدادی که اتفاق افتاده. کاری که این‌جا می‌شود فقط نشان دادن است تا
    حسابدار خودش قضاوت کند.

    مانده‌ی خام (بدهکار منهای بستانکار) مبناست، نه `_signed_balance` که علامت را بر
    اساسِ *نوع* برمی‌گرداند: ماهیت می‌تواند صریحاً خلافِ نوع ست شده باشد و آن‌وقت
    علامتِ نوع‌محور نتیجه را وارونه می‌کرد.

    `controlled_only` تیکِ «کنترل ماهیت طی دوره» را به کار می‌گیرد: در چارتِ بزرگ،
    خواندنِ فهرستی که همه‌ی حساب‌ها را می‌سنجد عملاً ممکن نیست و حسابدار فقط چند
    حسابِ حساس را رصد می‌کند. پیش‌فرض خاموش است تا این پرچمِ تازه گزارشِ موجود را
    بی‌صدا خالی نکند — محدود کردن باید خواسته‌ی صریحِ کاربر باشد.
    """
    result = []
    for acc, debit, credit in _leaf_account_totals(db, date_from, date_to):
        if controlled_only and not acc.nature_control:
            continue
        nature = acc.effective_nature
        if nature == "any":
            continue
        raw = debit - credit
        if raw == 0:
            continue
        if (nature == "debit" and raw > 0) or (nature == "credit" and raw < 0):
            continue
        result.append(
            {
                "account_id": acc.id,
                "account_code": acc.code,
                "account_name": acc.name,
                "account_type": acc.type,
                "nature": nature,
                #: صریح یا مشتق‌شده — تا کاربر بداند این معیار را خودش گذاشته یا پیش‌فرض است.
                "nature_is_explicit": acc.nature is not None,
                #: تیکِ «کنترل ماهیت طی دوره» — حتی وقتی گزارش محدود نشده، ستون
                #: نشان می‌دهد کدام حساب زیرِ رصدِ کاربر است.
                "nature_control": acc.nature_control,
                "total_debit": debit,
                "total_credit": credit,
                "balance": abs(raw),
                "balance_side": "debit" if raw > 0 else "credit",
            }
        )
    return sorted(result, key=lambda r: r["account_code"])


def get_income_statement(db: Session, date_from: date | None, date_to: date | None) -> dict:
    rows = _leaf_account_totals(db, date_from, date_to, types=("income", "expense"))
    income = sorted(
        (
            {"account_id": a.id, "account_code": a.code, "account_name": a.name, "balance": _signed_balance(a.type, d, c)}
            for a, d, c in rows
            if a.type == "income"
        ),
        key=lambda r: r["account_code"],
    )
    expenses = sorted(
        (
            {"account_id": a.id, "account_code": a.code, "account_name": a.name, "balance": _signed_balance(a.type, d, c)}
            for a, d, c in rows
            if a.type == "expense"
        ),
        key=lambda r: r["account_code"],
    )
    total_income = sum((r["balance"] for r in income), Decimal(0))
    total_expenses = sum((r["balance"] for r in expenses), Decimal(0))
    return {
        "date_from": date_from,
        "date_to": date_to,
        "income": income,
        "expenses": expenses,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": total_income - total_expenses,
    }


def get_balance_sheet(db: Session, as_of: date) -> dict:
    income_statement = get_income_statement(db, None, as_of)
    current_period_profit = income_statement["net_profit"]

    rows = _leaf_account_totals(db, None, as_of, types=("asset", "liability", "equity"))
    by_type: dict[str, list[dict]] = {"asset": [], "liability": [], "equity": []}
    for acc, debit, credit in rows:
        by_type[acc.type].append(
            {
                "account_id": acc.id,
                "account_code": acc.code,
                "account_name": acc.name,
                "balance": _signed_balance(acc.type, debit, credit),
            }
        )
    for key in by_type:
        by_type[key].sort(key=lambda r: r["account_code"])

    total_assets = sum((r["balance"] for r in by_type["asset"]), Decimal(0))
    total_liabilities = sum((r["balance"] for r in by_type["liability"]), Decimal(0))
    total_equity = sum((r["balance"] for r in by_type["equity"]), Decimal(0))

    return {
        "as_of": as_of,
        "assets": by_type["asset"],
        "liabilities": by_type["liability"],
        "equity": by_type["equity"],
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "current_period_profit": current_period_profit,
    }


def _cash_account_ids(db: Session) -> set[UUID]:
    """همه‌ی حساب‌هایی که «نقد» محسوب می‌شوند: صندوق/بانک/تنخواه به‌علاوه‌ی حساب
    دفترکلِ هر حساب بانکیِ تعریف‌شده (که ممکن است حساب معینِ جدا و بدون system_role باشد).
    """
    ids = {row[0] for row in db.query(Account.id).filter(Account.system_role.in_(CASH_ROLES)).all()}
    ids |= {gl for (gl,) in db.query(BankAccount.gl_account_id).distinct().all() if gl is not None}
    return ids


def _cash_flow_category(account: Account) -> str:
    """طرفِ غیرنقدِ یک سند را به یکی از سه فعالیتِ صورت جریان وجوه نقد نسبت می‌دهد.

    - سرمایه‌گذاری: دارایی‌های غیرجاری (گروه ۱۲) و دارایی ثابت — خرید/فروشِ دارایی.
    - تأمین مالی: حقوق صاحبان سرمایه (آورده/برداشتِ مالک) و بدهی‌های بلندمدت (گروه ۲۲،
      اگر مشتری تعریف کند).
    - عملیاتی: بقیه — درآمد، هزینه، و اقلامِ سرمایه در گردش (دریافتنی/پرداختنی، موجودی،
      مالیات و ...).
    """
    code = account.code or ""
    if account.system_role in FIXED_ASSET_ROLES or (account.type == "asset" and code.startswith("12")):
        return "investing"
    if account.type == "equity" or (account.type == "liability" and code.startswith("22")):
        return "financing"
    return "operating"


def _cash_balance(db: Session, cash_ids: set[UUID], *, upto: date | None, inclusive: bool) -> Decimal:
    """ماندهٔ جمعِ حساب‌های نقد تا یک تاریخ. همه دارایی‌اند، پس مانده = بدهکار − بستانکار."""
    if not cash_ids:
        return Decimal(0)
    query = (
        db.query(func.coalesce(func.sum(JournalLine.debit), 0), func.coalesce(func.sum(JournalLine.credit), 0))
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .filter(JournalLine.account_id.in_(cash_ids))
    )
    if upto is not None:
        query = query.filter(JournalEntry.entry_date <= upto if inclusive else JournalEntry.entry_date < upto)
    debit, credit = query.one()
    return Decimal(debit) - Decimal(credit)


def get_cash_flow(db: Session, date_from: date | None, date_to: date | None) -> dict:
    """صورت جریان وجوه نقد به روشِ مستقیم، مستقیم از دفتر.

    برای هر سندی که دستِ‌کم یک خطِ نقد دارد، تغییرِ نقد برابرِ جمعِ (بستانکار−بدهکار)ِ
    خطوطِ غیرنقدِ همان سند است (چون سند تراز است). هر خطِ غیرنقد به فعالیتِ خودش نسبت
    داده می‌شود. جمعِ سه فعالیت باید دقیقاً با تغییرِ ماندهٔ نقد در دوره برابر شود —
    این خودش صحتِ گزارش را تضمین می‌کند.
    """
    cash_ids = _cash_account_ids(db)
    opening_cash = _cash_balance(db, cash_ids, upto=date_from, inclusive=False) if date_from else Decimal(0)

    entry_query = (
        db.query(JournalEntry.id)
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .filter(JournalLine.account_id.in_(cash_ids))
    )
    if date_from is not None:
        entry_query = entry_query.filter(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        entry_query = entry_query.filter(JournalEntry.entry_date <= date_to)
    entry_ids = [row[0] for row in entry_query.distinct().all()]

    buckets: dict[str, dict[UUID, Decimal]] = {"operating": {}, "investing": {}, "financing": {}}
    info: dict[UUID, Account] = {}
    if entry_ids:
        rows = (
            db.query(JournalLine, Account)
            .join(Account, JournalLine.account_id == Account.id)
            .filter(JournalLine.entry_id.in_(entry_ids))
            .all()
        )
        for line, account in rows:
            if account.id in cash_ids:
                continue  # طرفِ نقد خودش جریان نیست؛ فقط علتش شمرده می‌شود
            contribution = Decimal(line.credit) - Decimal(line.debit)
            if contribution == 0:
                continue
            category = _cash_flow_category(account)
            buckets[category][account.id] = buckets[category].get(account.id, Decimal(0)) + contribution
            info[account.id] = account

    def rows_for(category: str) -> list[dict]:
        return sorted(
            (
                {"account_id": aid, "account_code": info[aid].code, "account_name": info[aid].name, "amount": amount}
                for aid, amount in buckets[category].items()
                if amount != 0
            ),
            key=lambda r: r["account_code"],
        )

    operating = rows_for("operating")
    investing = rows_for("investing")
    financing = rows_for("financing")
    net_operating = sum((r["amount"] for r in operating), Decimal(0))
    net_investing = sum((r["amount"] for r in investing), Decimal(0))
    net_financing = sum((r["amount"] for r in financing), Decimal(0))
    net_change = net_operating + net_investing + net_financing

    return {
        "date_from": date_from,
        "date_to": date_to,
        "opening_cash": opening_cash,
        "operating": operating,
        "investing": investing,
        "financing": financing,
        "net_operating": net_operating,
        "net_investing": net_investing,
        "net_financing": net_financing,
        "net_change": net_change,
        "closing_cash": opening_cash + net_change,
    }


#: برچسبِ فارسیِ منشأ هر حرکتِ انبار — همان مقادیری که سرویس‌ها می‌نویسند.
STOCK_SOURCE_LABELS = {
    "purchase_invoice": "فاکتور خرید",
    "sales_invoice": "فاکتور فروش",
    "warehouse_receipt": "رسید انبار خرید",
    "warehouse_issue": "خروج انبار فروش",
    "purchase_return": "برگشت از خرید",
    "sales_return": "برگشت از فروش",
    "adjustment": "تعدیل انبار",
    "transfer_in": "انتقال (ورود)",
    "transfer_out": "انتقال (خروج)",
    "opening": "موجودی اول دوره",
}


def get_kardex(
    db: Session,
    item_id: UUID,
    warehouse_id: UUID | None,
    date_from: date | None,
    date_to: date | None,
) -> dict:
    """کاردکس یک کالا — هر ورود/خروج با موجودیِ در حال اجرا.

    ترتیب بر اساس `seq` است نه تاریخ: `entry_date` فقط روز را دارد و چند حرکت در یک
    روز ترتیبِ مشخصی نمی‌گیرند، در حالی که موجودیِ در حال اجرا به ترتیب وابسته است.
    """
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کالا یافت نشد")

    def base():
        query = db.query(StockLedger).filter(StockLedger.item_id == item_id)
        if warehouse_id is not None:
            query = query.filter(StockLedger.warehouse_id == warehouse_id)
        return query

    opening = Decimal(0)
    if date_from is not None:
        opening_rows = base().filter(StockLedger.entry_date < date_from).all()
        opening = sum((Decimal(r.qty) for r in opening_rows), Decimal(0))

    query = base()
    if date_from is not None:
        query = query.filter(StockLedger.entry_date >= date_from)
    if date_to is not None:
        query = query.filter(StockLedger.entry_date <= date_to)

    running = opening
    total_in = Decimal(0)
    total_out = Decimal(0)
    lines = []
    for move in query.order_by(StockLedger.seq).all():
        qty = Decimal(move.qty)
        running += qty
        qty_in = qty if qty > 0 else Decimal(0)
        qty_out = -qty if qty < 0 else Decimal(0)
        total_in += qty_in
        total_out += qty_out
        lines.append(
            {
                "entry_date": move.entry_date,
                "source_type": move.source_type,
                "source_label": STOCK_SOURCE_LABELS.get(move.source_type, move.source_type),
                "qty_in": qty_in,
                "qty_out": qty_out,
                "unit_cost": Decimal(move.unit_cost),
                "balance_qty": running,
            }
        )

    return {
        "item_id": item.id,
        "item_sku": item.sku,
        "item_name": item.name,
        "unit": item.unit,
        "warehouse_id": warehouse_id,
        "date_from": date_from,
        "date_to": date_to,
        "opening_qty": opening,
        "lines": lines,
        "total_in": total_in,
        "total_out": total_out,
        "closing_qty": running,
    }


def get_sales_dashboard(db: Session, months: int = 12) -> dict:
    """تحلیل فروش برای داشبورد: روند ماهانه‌ی فروش/خرید، پرفروش‌ترین کالاها و بهترین مشتریان.

    ماه‌ها **شمسی** سطل‌بندی می‌شوند نه میلادی — چون یک ماه میلادی روی دو ماه شمسی
    می‌افتد و برچسبِ ماهِ اشتباه، روندِ فروش را برای کاربر ایرانی بی‌معنا می‌کند.
    فقط فاکتورهای باطل‌نشده و در بازه‌ی همان ماه‌ها حساب می‌شوند.
    """
    from app.services.printing import gregorian_to_jalali

    months = max(1, min(months, 36))
    today = date.today()
    cy, cm, _ = gregorian_to_jalali(today)

    # سطل‌های (سال، ماه) شمسی، از قدیمی به جدید
    buckets: list[tuple[int, int]] = []
    jy, jm = cy, cm
    for _ in range(months):
        buckets.append((jy, jm))
        jm -= 1
        if jm == 0:
            jm = 12
            jy -= 1
    buckets.reverse()
    index_of = {ym: i for i, ym in enumerate(buckets)}

    # کفِ درشت برای کوئری تا کلِ تاریخ خوانده نشود؛ سطل‌بندیِ دقیق در پایتون است.
    lower = today - timedelta(days=months * 31 + 31)

    # فروش/خرید **خالص** = فاکتورهای باطل‌نشده منهای برگشت‌ها. بدون کسرِ برگشت،
    # نمودار ناخالص و بیش‌ازواقع می‌شد. برگشتِ فاکتورِ باطل‌شده کنار گذاشته می‌شود
    # (join روی voided_at IS NULL) چون فروشِ آن فاکتور اصلاً شمرده نشده.
    sales = [Decimal(0)] * months
    purchases = [Decimal(0)] * months
    for inv_date, amount in (
        db.query(SalesInvoice.invoice_date, SalesInvoice.total_amount)
        .filter(SalesInvoice.voided_at.is_(None), SalesInvoice.invoice_date >= lower)
        .all()
    ):
        i = index_of.get(gregorian_to_jalali(inv_date)[:2])
        if i is not None:
            sales[i] += Decimal(amount)
    for ret_date, amount in (
        db.query(SalesReturn.return_date, SalesReturn.total_amount)
        .join(SalesInvoice, SalesReturn.sales_invoice_id == SalesInvoice.id)
        .filter(SalesInvoice.voided_at.is_(None), SalesReturn.return_date >= lower)
        .all()
    ):
        i = index_of.get(gregorian_to_jalali(ret_date)[:2])
        if i is not None:
            sales[i] -= Decimal(amount)
    for inv_date, amount in (
        db.query(PurchaseInvoice.invoice_date, PurchaseInvoice.total_amount)
        .filter(PurchaseInvoice.voided_at.is_(None), PurchaseInvoice.invoice_date >= lower)
        .all()
    ):
        i = index_of.get(gregorian_to_jalali(inv_date)[:2])
        if i is not None:
            purchases[i] += Decimal(amount)
    for ret_date, amount in (
        db.query(PurchaseReturn.return_date, PurchaseReturn.total_amount)
        .join(PurchaseInvoice, PurchaseReturn.purchase_invoice_id == PurchaseInvoice.id)
        .filter(PurchaseInvoice.voided_at.is_(None), PurchaseReturn.return_date >= lower)
        .all()
    ):
        i = index_of.get(gregorian_to_jalali(ret_date)[:2])
        if i is not None:
            purchases[i] -= Decimal(amount)

    monthly = [
        {"jy": jy, "jm": jm, "sales": sales[i], "purchases": purchases[i]}
        for i, (jy, jm) in enumerate(buckets)
    ]

    # پرفروش‌ترین کالاها بر اساس درآمدِ خالص (فروش منهای برگشت)، در همان بازه
    line_revenue = SalesInvoiceLine.qty * SalesInvoiceLine.unit_price - SalesInvoiceLine.discount
    item_agg: dict[UUID, dict] = {}
    for item_id, name, qty, revenue in (
        db.query(
            Item.id,
            Item.name,
            func.coalesce(func.sum(SalesInvoiceLine.qty), 0),
            func.coalesce(func.sum(line_revenue), 0),
        )
        .join(SalesInvoiceLine, SalesInvoiceLine.item_id == Item.id)
        .join(SalesInvoice, SalesInvoiceLine.invoice_id == SalesInvoice.id)
        .filter(SalesInvoice.voided_at.is_(None), SalesInvoice.invoice_date >= lower)
        .group_by(Item.id, Item.name)
        .all()
    ):
        item_agg[item_id] = {"item_id": item_id, "name": name, "qty": Decimal(qty), "revenue": Decimal(revenue)}
    ret_line_revenue = SalesReturnLine.qty * SalesReturnLine.unit_price
    for item_id, qty, revenue in (
        db.query(
            SalesReturnLine.item_id,
            func.coalesce(func.sum(SalesReturnLine.qty), 0),
            func.coalesce(func.sum(ret_line_revenue), 0),
        )
        .join(SalesReturn, SalesReturnLine.return_id == SalesReturn.id)
        .join(SalesInvoice, SalesReturn.sales_invoice_id == SalesInvoice.id)
        .filter(SalesInvoice.voided_at.is_(None), SalesReturn.return_date >= lower)
        .group_by(SalesReturnLine.item_id)
        .all()
    ):
        agg = item_agg.get(item_id)
        if agg is not None:
            agg["qty"] -= Decimal(qty)
            agg["revenue"] -= Decimal(revenue)
    top_items = sorted(
        (a for a in item_agg.values() if a["revenue"] > 0),
        key=lambda a: a["revenue"],
        reverse=True,
    )[:5]

    # بهترین مشتریان بر اساس جمعِ خالصِ فروش (فروش منهای برگشت، فقط شخص‌دار)
    cust_agg: dict[UUID, dict] = {}
    for contact_id, name, total in (
        db.query(Contact.id, Contact.name, func.coalesce(func.sum(SalesInvoice.total_amount), 0))
        .join(SalesInvoice, SalesInvoice.contact_id == Contact.id)
        .filter(SalesInvoice.voided_at.is_(None), SalesInvoice.invoice_date >= lower)
        .group_by(Contact.id, Contact.name)
        .all()
    ):
        cust_agg[contact_id] = {"contact_id": contact_id, "name": name, "total": Decimal(total)}
    for contact_id, total in (
        db.query(SalesInvoice.contact_id, func.coalesce(func.sum(SalesReturn.total_amount), 0))
        .join(SalesReturn, SalesReturn.sales_invoice_id == SalesInvoice.id)
        .filter(SalesInvoice.voided_at.is_(None), SalesReturn.return_date >= lower)
        .group_by(SalesInvoice.contact_id)
        .all()
    ):
        agg = cust_agg.get(contact_id)
        if agg is not None:
            agg["total"] -= Decimal(total)
    top_customers = sorted(
        (a for a in cust_agg.values() if a["total"] > 0),
        key=lambda a: a["total"],
        reverse=True,
    )[:5]

    return {"months": months, "monthly": monthly, "top_items": top_items, "top_customers": top_customers}


def get_inventory_report(db: Session, warehouse_id: UUID | None, as_of: date | None) -> dict:
    """ارزش‌گذاری موجودی: موجودیِ هر کالا × بهای میانگین موزون.

    موجودیِ فعلی از جمعِ حرکاتِ دفترِ موجودی می‌آید و ارزش با `average_cost`ِ روزِ
    کالا حساب می‌شود — همان روشی که حسابِ «موجودی کالا» در دفتر با آن نگه‌داری
    می‌شود، پس جمعِ این گزارش باید با ماندهٔ آن حساب بخواند. کالاهای خدماتی و اقلامِ
    با موجودیِ صفر نمایش داده نمی‌شوند.
    """
    qty_query = db.query(
        StockLedger.item_id, func.coalesce(func.sum(StockLedger.qty), 0)
    )
    if warehouse_id is not None:
        qty_query = qty_query.filter(StockLedger.warehouse_id == warehouse_id)
    if as_of is not None:
        qty_query = qty_query.filter(StockLedger.entry_date <= as_of)
    qty_by_item = {item_id: Decimal(qty) for item_id, qty in qty_query.group_by(StockLedger.item_id).all()}

    items = {i.id: i for i in db.query(Item).filter(Item.is_service.is_(False)).all()}

    rows = []
    for item_id, qty in qty_by_item.items():
        item = items.get(item_id)
        if item is None or qty == 0:
            continue
        unit_cost = Decimal(item.average_cost)
        rows.append(
            {
                "item_id": item.id,
                "sku": item.sku,
                "name": item.name,
                "unit": item.unit,
                "category": item.category,
                "qty_on_hand": qty,
                "unit_cost": unit_cost,
                "stock_value": qty * unit_cost,
            }
        )

    rows.sort(key=lambda r: r["stock_value"], reverse=True)  # بیشترین ارزش اول
    return {
        "as_of": as_of,
        "rows": rows,
        "total_value": sum((r["stock_value"] for r in rows), Decimal(0)),
        "item_count": len(rows),
    }


#: ترتیبِ نمایشِ رویدادهای هم‌تاریخ در کارت حساب — اول اسناد، بعد برگشت، بعد وجه.
_STATEMENT_KIND_ORDER = {
    "sales_invoice": 1,
    "purchase_invoice": 1,
    "sales_return": 2,
    "purchase_return": 2,
    "receipt": 3,
    "payment": 3,
    "check_in": 4,
    "check_out": 4,
}


def contact_balance(db: Session, contact_id: UUID) -> Decimal:
    """ماندهٔ خالصِ طرف‌حساب: مثبت = شخص به ما بدهکار است (طلبِ ما).

    همان قراردادِ علامتِ کارتِ حساب: فروش/برگشتِ‌خرید/پرداختِ‌ما بدهکار، و
    خرید/برگشتِ‌فروش/دریافت بستانکار. اسنادِ باطل‌شده کنار می‌روند. برای محافظ‌های
    اقساط استفاده می‌شود تا دریافتی که دریافتنی را منفی می‌کند گرفته شود.
    """
    def s(q) -> Decimal:
        return Decimal(q.scalar() or 0)

    bal = Decimal(0)
    bal += s(
        db.query(func.coalesce(func.sum(SalesInvoice.total_amount + SalesInvoice.tax_amount), 0))
        .filter(SalesInvoice.contact_id == contact_id, SalesInvoice.voided_at.is_(None))
    )
    bal -= s(
        db.query(func.coalesce(func.sum(SalesReturn.total_amount + SalesReturn.tax_amount), 0))
        .join(SalesInvoice, SalesReturn.sales_invoice_id == SalesInvoice.id)
        .filter(SalesInvoice.contact_id == contact_id, SalesInvoice.voided_at.is_(None))
    )
    bal -= s(
        db.query(func.coalesce(func.sum(PurchaseInvoice.total_amount + PurchaseInvoice.tax_amount), 0))
        .filter(PurchaseInvoice.contact_id == contact_id, PurchaseInvoice.voided_at.is_(None))
    )
    bal += s(
        db.query(func.coalesce(func.sum(PurchaseReturn.total_amount + PurchaseReturn.tax_amount), 0))
        .join(PurchaseInvoice, PurchaseReturn.purchase_invoice_id == PurchaseInvoice.id)
        .filter(PurchaseInvoice.contact_id == contact_id, PurchaseInvoice.voided_at.is_(None))
    )
    bal -= s(
        db.query(func.coalesce(func.sum(TreasuryTransaction.amount), 0))
        .filter(TreasuryTransaction.contact_id == contact_id, TreasuryTransaction.type == "receipt", TreasuryTransaction.voided_at.is_(None))
    )
    bal += s(
        db.query(func.coalesce(func.sum(TreasuryTransaction.amount), 0))
        .filter(TreasuryTransaction.contact_id == contact_id, TreasuryTransaction.type == "payment", TreasuryTransaction.voided_at.is_(None))
    )
    # چکِ دریافتنیِ غیربرگشتی: مطالباتِ مشتری را کم می‌کند — درست مثلِ دریافتِ نقدی، چون
    # همان لحظه‌ی ثبت، سندِ حسابداری «حساب‌های دریافتنی» را بستانکار کرده. چکِ برگشتی کنار
    # می‌رود، چون سندِ برگشت همان دریافتنی را دوباره بدهکار (احیا) می‌کند و اثرش خنثی است.
    bal -= s(
        db.query(func.coalesce(func.sum(Check.amount), 0)).filter(
            Check.contact_id == contact_id, Check.type == "receivable", Check.status != "bounced", Check.voided_at.is_(None)
        )
    )
    # چکِ پرداختنیِ غیربرگشتی: بدهیِ ما به تأمین‌کننده را کم می‌کند — مثلِ پرداختِ نقدی.
    bal += s(
        db.query(func.coalesce(func.sum(Check.amount), 0)).filter(
            Check.contact_id == contact_id, Check.type == "payable", Check.status != "bounced", Check.voided_at.is_(None)
        )
    )
    return bal


def get_contact_statement(
    db: Session, contact_id: UUID, date_from: date | None, date_to: date | None
) -> dict:
    """کارت حساب یک طرف‌حساب — همه‌ی رویدادهایش با ماندهٔ در حال اجرا.

    قرارداد علامت از دیدِ کسب‌وکار است: بدهکار یعنی طلبِ ما از شخص بیشتر می‌شود
    (فروش به او، پرداختِ ما به او، برگشتِ خریدِ ما)، بستانکار یعنی کمتر می‌شود
    (دریافت از او، برگشتِ فروشِ او، خریدِ ما از او). ماندهٔ مثبت = شخص به ما بدهکار
    است؛ منفی = ما به او. اسنادِ باطل‌شده کنار گذاشته می‌شوند.
    """
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "طرف حساب یافت نشد")

    events: list[dict] = []

    def add(txn_date, kind, number, description, debit, credit):
        events.append(
            {
                "txn_date": txn_date,
                "kind": kind,
                "number": number,
                "description": description,
                "debit": Decimal(debit),
                "credit": Decimal(credit),
            }
        )

    # مانده‌ی اول دوره — پیش از هر رویدادِ دیگری.
    #
    # بدونِ این، عددی که کاربر در فرمِ طرف‌حساب وارد کرده در سندِ افتتاحیه می‌نشست
    # ولی در کارتِ حسابِ خودِ آن شخص دیده نمی‌شد؛ یعنی همان گزارشی که برای آن ثبت
    # شده بود، نشانش نمی‌داد. تاریخش تاریخِ سندِ افتتاحیه است تا در بازه‌ها درست
    # بیفتد و در «ماندهٔ اول دوره»ی گزارش هم لحاظ شود.
    opening_entry_date = db.query(func.min(JournalEntry.entry_date)).filter(
        JournalEntry.source_type == "opening", JournalEntry.voided_at.is_(None)
    ).scalar()
    if opening_entry_date is not None:
        for amount, side, label in (
            (contact.opening_ar_amount, contact.opening_ar_side, "مانده اول دوره (دریافتنی)"),
            (contact.opening_ap_amount, contact.opening_ap_side, "مانده اول دوره (پرداختنی)"),
        ):
            amount = Decimal(amount or 0)
            if amount > 0:
                add(
                    opening_entry_date, "opening", None, label,
                    amount if side == "debit" else 0,
                    amount if side == "credit" else 0,
                )

    # فروش به این شخص (بدهکار)
    for number, inv_date, total, tax in db.query(
        SalesInvoice.number, SalesInvoice.invoice_date, SalesInvoice.total_amount, SalesInvoice.tax_amount
    ).filter(SalesInvoice.contact_id == contact_id, SalesInvoice.voided_at.is_(None)).all():
        add(inv_date, "sales_invoice", number, "فاکتور فروش", Decimal(total) + Decimal(tax), 0)

    # برگشت از فروشِ این شخص (بستانکار)
    for number, r_date, total, tax in (
        db.query(SalesReturn.number, SalesReturn.return_date, SalesReturn.total_amount, SalesReturn.tax_amount)
        .join(SalesInvoice, SalesReturn.sales_invoice_id == SalesInvoice.id)
        .filter(SalesInvoice.contact_id == contact_id, SalesInvoice.voided_at.is_(None))
        .all()
    ):
        add(r_date, "sales_return", number, "برگشت از فروش", 0, Decimal(total) + Decimal(tax))

    # خرید از این شخص (بستانکار — ما به او بدهکار می‌شویم)
    for number, inv_date, total, tax in db.query(
        PurchaseInvoice.number, PurchaseInvoice.invoice_date, PurchaseInvoice.total_amount, PurchaseInvoice.tax_amount
    ).filter(PurchaseInvoice.contact_id == contact_id, PurchaseInvoice.voided_at.is_(None)).all():
        add(inv_date, "purchase_invoice", number, "فاکتور خرید", 0, Decimal(total) + Decimal(tax))

    # برگشت از خرید به این شخص (بدهکار)
    for number, r_date, total, tax in (
        db.query(PurchaseReturn.number, PurchaseReturn.return_date, PurchaseReturn.total_amount, PurchaseReturn.tax_amount)
        .join(PurchaseInvoice, PurchaseReturn.purchase_invoice_id == PurchaseInvoice.id)
        .filter(PurchaseInvoice.contact_id == contact_id, PurchaseInvoice.voided_at.is_(None))
        .all()
    ):
        add(r_date, "purchase_return", number, "برگشت از خرید", Decimal(total) + Decimal(tax), 0)

    # دریافت/پرداختِ خزانه
    for t_type, t_date, amount in db.query(
        TreasuryTransaction.type, TreasuryTransaction.transaction_date, TreasuryTransaction.amount
    ).filter(TreasuryTransaction.contact_id == contact_id, TreasuryTransaction.voided_at.is_(None)).all():
        if t_type == "receipt":
            add(t_date, "receipt", None, "دریافت وجه", 0, Decimal(amount))  # شخص پرداخت کرد
        else:
            add(t_date, "payment", None, "پرداخت وجه", Decimal(amount), 0)  # ما پرداخت کردیم

    # چک‌های وصل‌شده به این شخص (برگشتی احیا شده و در مانده خنثی است، پس نمایش نمی‌دهیم).
    # دریافتنی مطالبات را کم می‌کند (بستانکار)؛ پرداختنی بدهیِ ما را کم می‌کند (بدهکار).
    for c_type, c_number, c_date, c_amount in db.query(
        Check.type, Check.number, Check.issue_date, Check.amount
    ).filter(Check.contact_id == contact_id, Check.status != "bounced", Check.voided_at.is_(None)).all():
        if c_type == "receivable":
            add(c_date, "check_in", c_number, "چک دریافتنی", 0, Decimal(c_amount))
        else:
            add(c_date, "check_out", c_number, "چک پرداختنی", Decimal(c_amount), 0)

    events.sort(key=lambda e: (e["txn_date"], _STATEMENT_KIND_ORDER.get(e["kind"], 99)))

    opening = sum(
        (e["debit"] - e["credit"] for e in events if date_from is not None and e["txn_date"] < date_from),
        Decimal(0),
    )
    running = opening
    total_debit = Decimal(0)
    total_credit = Decimal(0)
    lines = []
    for e in events:
        if date_from is not None and e["txn_date"] < date_from:
            continue
        if date_to is not None and e["txn_date"] > date_to:
            continue
        running += e["debit"] - e["credit"]
        total_debit += e["debit"]
        total_credit += e["credit"]
        lines.append({**e, "balance": running})

    return {
        "contact_id": contact.id,
        "contact_name": contact.name,
        "date_from": date_from,
        "date_to": date_to,
        "opening_balance": opening,
        "lines": lines,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "closing_balance": running,
    }


def get_aging(db: Session, kind: str, as_of: date | None) -> dict:
    """تحلیل سنیِ مطالبات (receivable) یا بدهی‌ها (payable) به تفکیک شخص و بازه‌ی سنی.

    مانده‌ی هر شخص = فاکتورهای اعتباریِ باطل‌نشده منهای تسویه‌ها (دریافت/پرداخت) و
    برگشت‌ها. چون تسویه در این سیستم در سطحِ شخص ثبت می‌شود نه فاکتور‌به‌فاکتور، مبلغِ
    تسویه به روشِ FIFO روی قدیمی‌ترین فاکتورها اعمال می‌شود؛ باقیمانده‌ی هر فاکتور بر
    اساس سنِ آن (نسبت به `as_of`) در یکی از چهار سطل می‌نشیند. اسنادِ دستیِ بدونِ
    شخص در این گزارش نمی‌آیند — این گزارش «چه کسی چقدر بدهکار است» را می‌گوید.
    """
    if kind not in AGING_KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوع گزارش سنی نامعتبر است")
    as_of = as_of or date.today()

    if kind == "receivable":
        Invoice, Return, return_fk, settle_type = SalesInvoice, SalesReturn, SalesReturn.sales_invoice_id, "receipt"
    else:
        Invoice, Return, return_fk, settle_type = PurchaseInvoice, PurchaseReturn, PurchaseReturn.purchase_invoice_id, "payment"

    invoices = (
        db.query(Invoice.contact_id, Invoice.invoice_date, Invoice.total_amount, Invoice.tax_amount)
        .filter(Invoice.contact_id.isnot(None), Invoice.voided_at.is_(None), Invoice.invoice_date <= as_of)
        .all()
    )

    # مانده‌ی اول دوره مثلِ یک «فاکتور» با تاریخِ سندِ افتتاحیه وارد می‌شود.
    #
    # بدونش، طلبی که از پیش از شروعِ کار با سیستم مانده بود در تحلیلِ سنی اصلاً
    # دیده نمی‌شد — یعنی قدیمی‌ترین و معمولاً پرخطرترین بخشِ مطالبات. تاریخِ
    # افتتاحیه مبناست، پس به‌درستی در سطلِ سنیِ خودش می‌افتد نه در «جاری».
    opening_date = db.query(func.min(JournalEntry.entry_date)).filter(
        JournalEntry.source_type == "opening", JournalEntry.voided_at.is_(None)
    ).scalar()
    if opening_date is not None and opening_date <= as_of:
        amount_col = Contact.opening_ar_amount if kind == "receivable" else Contact.opening_ap_amount
        side_col = Contact.opening_ar_side if kind == "receivable" else Contact.opening_ap_side
        #: فقط ماندهٔ همان سمتی که این گزارش می‌سنجد. مانده‌ی خلافِ سمت (پیش‌دریافت)
        #: بدهی نیست و آوردنش رقم را وارونه می‌کرد.
        wanted_side = "debit" if kind == "receivable" else "credit"
        for contact_id, amount in (
            db.query(Contact.id, amount_col)
            .filter(amount_col > 0, side_col == wanted_side)
            .all()
        ):
            invoices.append((contact_id, opening_date, Decimal(amount), Decimal(0)))

    # جمعِ تسویه‌ی هر شخص = دریافت/پرداخت + برگشت‌ها (هر دو مانده را کم می‌کنند)
    pool: dict = {}
    settlements = (
        db.query(TreasuryTransaction.contact_id, func.coalesce(func.sum(TreasuryTransaction.amount), 0))
        .filter(
            TreasuryTransaction.type == settle_type,
            TreasuryTransaction.transaction_date <= as_of,
            TreasuryTransaction.voided_at.is_(None),
        )
        .group_by(TreasuryTransaction.contact_id)
        .all()
    )
    for contact_id, amount in settlements:
        pool[contact_id] = pool.get(contact_id, Decimal(0)) + Decimal(amount)

    returns = (
        db.query(Invoice.contact_id, func.coalesce(func.sum(Return.total_amount + Return.tax_amount), 0))
        .join(Invoice, return_fk == Invoice.id)
        .filter(Invoice.contact_id.isnot(None), Invoice.voided_at.is_(None), Return.return_date <= as_of)
        .group_by(Invoice.contact_id)
        .all()
    )
    for contact_id, amount in returns:
        pool[contact_id] = pool.get(contact_id, Decimal(0)) + Decimal(amount)

    # چکِ غیربرگشتی هم تسویه است: چکِ دریافتنی مطالبات را کم می‌کند، چکِ پرداختنی بدهی را.
    check_type = "receivable" if kind == "receivable" else "payable"
    checks = (
        db.query(Check.contact_id, func.coalesce(func.sum(Check.amount), 0))
        .filter(
            Check.type == check_type,
            Check.status != "bounced",
            Check.voided_at.is_(None),
            Check.contact_id.isnot(None),
            Check.issue_date <= as_of,
        )
        .group_by(Check.contact_id)
        .all()
    )
    for contact_id, amount in checks:
        pool[contact_id] = pool.get(contact_id, Decimal(0)) + Decimal(amount)

    by_contact: dict = {}
    for contact_id, inv_date, total, tax in invoices:
        by_contact.setdefault(contact_id, []).append((inv_date, Decimal(total) + Decimal(tax)))

    names = {c.id: c.name for c in db.query(Contact).all()}

    rows = []
    for contact_id, inv_list in by_contact.items():
        inv_list.sort(key=lambda t: t[0])  # قدیمی‌ترین اول — تسویه اول به همان می‌خورد
        remaining = pool.get(contact_id, Decimal(0))
        bucket = {"current": Decimal(0), "d31_60": Decimal(0), "d61_90": Decimal(0), "over_90": Decimal(0)}
        for inv_date, amount in inv_list:
            paid = min(remaining, amount)
            remaining -= paid
            unpaid = amount - paid
            if unpaid <= 0:
                continue
            age = (as_of - inv_date).days
            if age <= 30:
                bucket["current"] += unpaid
            elif age <= 60:
                bucket["d31_60"] += unpaid
            elif age <= 90:
                bucket["d61_90"] += unpaid
            else:
                bucket["over_90"] += unpaid
        total = bucket["current"] + bucket["d31_60"] + bucket["d61_90"] + bucket["over_90"]
        if total <= 0:
            continue
        rows.append(
            {
                "contact_id": contact_id,
                "contact_name": names.get(contact_id, "—"),
                "current": bucket["current"],
                "d31_60": bucket["d31_60"],
                "d61_90": bucket["d61_90"],
                "over_90": bucket["over_90"],
                "total": total,
            }
        )

    rows.sort(key=lambda r: r["total"], reverse=True)
    return {
        "as_of": as_of,
        "kind": kind,
        "rows": rows,
        "total_current": sum((r["current"] for r in rows), Decimal(0)),
        "total_31_60": sum((r["d31_60"] for r in rows), Decimal(0)),
        "total_61_90": sum((r["d61_90"] for r in rows), Decimal(0)),
        "total_over_90": sum((r["over_90"] for r in rows), Decimal(0)),
        "grand_total": sum((r["total"] for r in rows), Decimal(0)),
    }
