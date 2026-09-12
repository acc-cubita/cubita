"""مرور جامع طرف حساب — یک نمای خواندنی روی حقیقتی که از قبل هست.

**این‌جا دفترِ تازه‌ای ساخته نمی‌شود.** مانده‌ی طرف حساب جایی ذخیره نمی‌شود و
هیچ ستونی نیست که بشود دستی درستش کرد؛ هر عددِ این فایل از ردیف‌های دفتر مشتق
می‌شود.

و دلیلش یک باگِ واقعی است. تا امروز سه جا مانده‌ی یک طرف حساب را حساب می‌کردند و
هر سه فرمولِ خودشان را داشتند:

* `credit.customer_outstanding` — فاکتور با **اضافات، عوارض و رند**، منهای دریافت و برگشت
* `reports.contact_balance` — فاکتور فقط با مالیات
* `reports.get_contact_statement` — همان فرمولِ ناقص

از مهاجرتِ ۰۱۲۵ که ستون‌های اضافات و عوارض آمدند، این سه از هم جدا افتادند:
سندِ حسابداری ۱۵٬۰۰۰ بدهکار می‌کرد، بنرِ سقفِ اعتبار ۱۵٬۰۰۰ می‌گفت، و کارتِ حساب
۱۰٬۰۰۰. هیچ تستی هم نگرفتش، چون هیچ‌کدام مقابلِ **دفتر** گذاشته نشده بودند.

پس این فایل یک موتور دارد و آن موتور `open_items` است — که اثرِ هر سند را از
`debit - credit`ِ واقعیِ همان سند در دفتر می‌گیرد. نتیجه‌اش این است که افزودنِ
ستونِ تازه به فاکتور دیگر **نمی‌تواند** این گزارش را بی‌صدا از دفتر جدا کند:
ستونِ تازه یا در سند می‌نشیند و دیده می‌شود، یا نمی‌نشیند و اصلاً وجود ندارد.

سه دانه‌بندی (grain) این‌جا هست و عمداً از هم جدا می‌مانند — قاطی‌کردنشان یعنی
یک مبلغ چند بار شمرده شود:

    ۱. **نقش‌ها**   — یک ردیف برای هر نقشِ طرف حساب (مشتری، تأمین‌کننده)
    ۲. **رویدادها** — یک ردیف برای هر سند
    ۳. **اقلام**    — یک ردیف برای هر ردیفِ سند / ابزارِ خزانه / ردیفِ دفتر

و یک مرزِ سخت: **نقش‌ها با هم تهاتر نمی‌شوند.** طلبِ ما از کسی و بدهیِ ما به او
دو عددِ جدا می‌مانند؛ صاف‌کردنشان یک رویدادِ اقتصادیِ صریح می‌خواهد — همان
«اعلامیه بدهکار/بستانکار». گزارش جمعشان را *نشان* می‌دهد، ولی در دفتر کاری
نمی‌کند.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.analytic import AnalyticAccount
from app.models.banking import Check
from app.models.inventory import Contact, Item
from app.models.invoices import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
)
from app.models.returns import PurchaseReturn, PurchaseReturnLine, SalesReturn, SalesReturnLine
from app.models.sales_ops import CreditDebitNote, CreditDebitNoteLine
from app.services import chart_codes as cc
from app.services import open_items as oi

#: نقشِ هر معینِ طرف مقابل. کلید **نقشِ حساب** است نه کدش — همان قاعده‌ای که
#: هرجای دیگرِ کوبیتا هم دارد، تا تغییرِ شماره‌گذاریِ چارت این‌جا را نشکند.
ROLE_BY_ACCOUNT_ROLE = {
    cc.ACCOUNTS_RECEIVABLE: "customer",
    cc.ACCOUNTS_PAYABLE: "supplier",
}

ROLE_LABELS = {"customer": "مشتری", "supplier": "تأمین‌کننده"}

#: ترتیبِ رویدادهای **هم‌روز**. مانده‌ی در حالِ اجرا بدونِ ترتیبِ قطعی عددِ
#: قابلِ اتکایی نیست؛ و `created_at` هم ترتیبِ مالی نیست — سندی که امروز ثبت
#: شده می‌تواند تاریخِ مؤثرش دیروز باشد. شماره‌ی **سندِ حسابداری** بهترین
#: شکننده‌ی تساوی است چون بی‌شکاف و به ترتیبِ ثبت است.
_TIE_BREAK = ("document_date", "entry_number", "source_type", "source_id")


def _role_accounts(db: Session) -> list[tuple[str, Account]]:
    """(نقش، معین) برای هر حسابِ طرف مقابل — از `open_items`، نه از فهرستِ دوم."""
    out = []
    for account in oi.counterparty_accounts(db):
        role = ROLE_BY_ACCOUNT_ROLE.get(account.system_role)
        if role is not None:
            out.append((role, account))
    return out


def _sort_key(row: dict) -> tuple:
    return (
        row["document_date"],
        row["entry_number"] if row["entry_number"] is not None else 0,
        row["source_type"],
        str(row["source_id"]),
    )


def _signed(row: dict) -> Decimal:
    """اثرِ علامت‌دارِ یک رویداد. علامت از **سمتِ واقعیِ دفتر** می‌آید، نه از نامِ سند."""
    amount = Decimal(row["document_amount"])
    return amount if row["side"] == "debit" else -amount


# ───────────────────────── دانه‌بندیِ ۱: نقش‌ها ─────────────────────────


def _contact_ledger_net(db: Session, account_id: UUID, contact: Contact, as_of: date | None) -> Decimal | None:
    """ماندهٔ خامِ این طرف حساب روی این معین، مستقیم از دفتر.

    فقط وقتی ممکن است که طرف حساب **تفصیلی** داشته باشد؛ بدونِ تفصیلی، ردیفِ دفتر
    به هیچ شخصی قابلِ نسبت‌دادن نیست و `None` برمی‌گردد. این «نمی‌دانم» صادقانه
    است و نباید با صفر یکی گرفته شود.
    """
    if contact.analytic_id is None:
        return None
    query = (
        db.query(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .filter(
            JournalLine.account_id == account_id,
            JournalLine.analytic_id == contact.analytic_id,
            JournalEntry.voided_at.is_(None),
        )
    )
    if as_of is not None:
        query = query.filter(JournalEntry.entry_date <= as_of)
    return Decimal(query.scalar() or 0)


def _uncleared_cheques(db: Session, contact_id: UUID, as_of: date | None) -> Decimal:
    """چک‌های دریافتیِ **هنوز وصول‌نشده‌ی** این مشتری.

    کوبیتا همان لحظه‌ی دریافتِ چک، مطالبات را بستانکار می‌کند — یعنی مانده‌ی دفتری
    از قبل چک را «پول» حساب کرده. این عدد می‌گوید چه‌قدر از آن مانده هنوز به
    وصول نرسیده، تا کاربر بتواند هر دو را ببیند.

    **این یک ستونِ نمایشی است، نه حالتِ دیگری از دفتر.** هیچ‌چیز در دفتر عوض
    نمی‌شود؛ فقط کنارِ مانده نوشته می‌شود که چه‌قدرش هنوز در راه است.
    """
    query = db.query(func.coalesce(func.sum(Check.amount), 0)).filter(
        Check.contact_id == contact_id,
        Check.type == "receivable",
        #: وصول‌شده و خرج‌شده دیگر «در راه» نیستند؛ برگشتی هم سندِ احیا خورده و
        #: اثرش در دفتر خنثی است.
        Check.status.in_(("in_hand", "deposited")),
        Check.voided_at.is_(None),
    )
    if as_of is not None:
        query = query.filter(Check.issue_date <= as_of)
    return Decimal(query.scalar() or 0)


def role_positions(db: Session, contact_id: UUID, *, as_of: date | None = None) -> list[dict]:
    """مانده‌ی این طرف حساب، **نقش به نقش**.

    یک عددِ خالص کافی نیست: همان شرکت می‌تواند هم مشتری باشد هم تأمین‌کننده، و
    «۲۵۰ میلیون طلب» با «۳۰۰ میلیون طلب و ۵۰ میلیون بدهی» دو وضعیتِ متفاوتِ
    تجاری‌اند که یک عدد هر دو را یکی نشان می‌دهد.

    کنارِ هر نقش، **مانده‌ی دفتری** هم می‌آید تا تطبیق ممکن باشد؛ اختلافشان
    (`unattributed`) یعنی گردشی روی آن معین هست که سندِ شناخته‌شده‌ای پشتش نیست —
    سندِ دستی یا ماندهٔ اول دوره. عدد پنهان نمی‌شود، نشان داده می‌شود.
    """
    contact = db.get(Contact, contact_id)
    if contact is None:
        return []

    rows = []
    for role, account in _role_accounts(db):
        items = oi.open_items(
            db, account_id=account.id, contact_id=contact_id, as_of=as_of, only_open=False
        )
        debit = sum((Decimal(i["document_amount"]) for i in items if i["side"] == "debit"), Decimal(0))
        credit = sum((Decimal(i["document_amount"]) for i in items if i["side"] == "credit"), Decimal(0))
        open_debit = sum(
            (Decimal(i["remaining_amount"]) for i in items if i["side"] == "debit" and i["remaining_amount"] > 0),
            Decimal(0),
        )
        open_credit = sum(
            (Decimal(i["remaining_amount"]) for i in items if i["side"] == "credit" and i["remaining_amount"] > 0),
            Decimal(0),
        )
        ledger = _contact_ledger_net(db, account.id, contact, as_of)
        net = debit - credit
        rows.append(
            {
                "role": role,
                "role_label": ROLE_LABELS[role],
                "account_id": account.id,
                "account_code": account.code,
                "account_name": account.name,
                "debit_total": debit,
                "credit_total": credit,
                "net": net,
                #: مانده‌ی **قابلِ تسویه**: همان مانده منهای آنچه تخصیص خورده.
                #: با `net` یکی نیست و نباید یکی گرفته شود (§۵۳).
                "open_net": open_debit - open_credit,
                "ledger_net": ledger,
                "unattributed": None if ledger is None else ledger - net,
                "document_count": len(items),
            }
        )
    return rows


def position_summary(db: Session, contact_id: UUID, *, as_of: date | None = None) -> dict:
    """خلاصه‌ی یک طرف حساب: نقش‌هایش، جمعشان، و چکِ در راه.

    `total_net` **مشتق** است و ذخیره نمی‌شود. و هیچ تهاتری هم انجام نمی‌دهد:
    اگر یکی هم‌زمان ۱۰۰ طلب و ۷۰ بدهی داشته باشد، این‌جا هر سه عدد دیده می‌شوند
    (۱۰۰، ۷۰− و ۳۰) — نه اینکه دفتر به ۳۰ و صفر بازنویسی شود. صاف‌کردنِ واقعی
    یک «اعلامیه بدهکار/بستانکار» می‌خواهد.
    """
    contact = db.get(Contact, contact_id)
    positions = role_positions(db, contact_id, as_of=as_of)
    uncleared = _uncleared_cheques(db, contact_id, as_of) if contact else Decimal(0)
    total = sum((row["net"] for row in positions), Decimal(0))
    return {
        "contact_id": contact_id,
        "contact_name": contact.name if contact else "—",
        "contact_type": contact.type if contact else "",
        "has_analytic": bool(contact and contact.analytic_id),
        "positions": positions,
        "total_net": total,
        "open_net": sum((row["open_net"] for row in positions), Decimal(0)),
        #: چکِ دریافتیِ وصول‌نشده — ستونِ کنارِ مانده، نه حالتِ دیگری از آن.
        "uncleared_cheques": uncleared,
        "net_without_uncleared_cheques": total + uncleared,
    }


# ───────────────────────── دانه‌بندیِ ۲: رویدادها ─────────────────────────


def events(
    db: Session,
    contact_id: UUID,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    role: str | None = None,
) -> list[dict]:
    """خطِ زمانیِ رویدادهای این طرف حساب، در همه‌ی نقش‌ها، با مانده‌ی در حالِ اجرا.

    فاکتور و دریافت و اعلامیه کنارِ هم می‌نشینند، ولی **یکی نمی‌شوند**: هر ردیف
    `source_type` و `source_id`ِ خودش را نگه می‌دارد تا بشود تا خودِ سند پایین
    رفت. هیچ‌جا شرحِ متنی برای تشخیصِ منبع خوانده نمی‌شود.

    سندِ حسابداریِ هر رویداد ردیفِ **جدا** نمی‌گیرد — شماره‌اش روی همان ردیف
    می‌نشیند. اگر جدا می‌شد، فاکتور و سندش دو اثرِ اقتصادیِ مستقل به نظر می‌رسیدند
    و مانده دو برابر می‌شد.

    مانده‌ی در حالِ اجرا از **کلِ تاریخ** شروع می‌شود و بعد بازه بریده می‌شود،
    وگرنه ردیفِ اولِ بازه از صفر شروع می‌کرد و همه‌ی اعدادِ بعدی غلط می‌شدند.
    """
    rows: list[dict] = []
    for role_key, account in _role_accounts(db):
        if role is not None and role != role_key:
            continue
        for item in oi.open_items(
            db, account_id=account.id, contact_id=contact_id, as_of=None, only_open=False
        ):
            rows.append(
                {
                    **item,
                    "role": role_key,
                    "role_label": ROLE_LABELS[role_key],
                    "account_id": account.id,
                    "account_code": account.code,
                    "account_name": account.name,
                    "status_label": oi.STATUS_LABELS[item["status"]],
                }
            )

    rows.sort(key=_sort_key)

    running = Decimal(0)
    out = []
    for row in rows:
        running += _signed(row)
        row["running_balance"] = running
        if date_from is not None and row["document_date"] < date_from:
            continue
        if date_to is not None and row["document_date"] > date_to:
            continue
        out.append(row)
    return out


# ───────────────────────── دانه‌بندیِ ۳: اقلام ─────────────────────────

#: اقلامِ یک سند همه از یک جنس نیستند و نباید زورکی به شکلِ «ردیفِ کالا» درآیند
#: (§۳۵). هر قلم نوعِ خودش را اعلام می‌کند و رابط از روی همان می‌فهمد کدام ستون
#: برایش معنی دارد.
LINE_KIND_PRODUCT = "product"
LINE_KIND_JOURNAL = "journal"
LINE_KIND_ADJUSTMENT = "adjustment"


def _product_lines(db: Session, source_type: str, source_id: UUID) -> list[dict] | None:
    """ردیف‌های کالا/خدمتِ سند، اگر داشته باشد."""
    mapping = {
        "sales_invoice": (SalesInvoiceLine, SalesInvoiceLine.invoice_id),
        "purchase_invoice": (PurchaseInvoiceLine, PurchaseInvoiceLine.invoice_id),
        "sales_return": (SalesReturnLine, SalesReturnLine.return_id),
        "purchase_return": (PurchaseReturnLine, PurchaseReturnLine.return_id),
    }
    if source_type not in mapping:
        return None
    model, fk = mapping[source_type]
    rows = db.query(model).filter(fk == source_id).all()
    names = {
        i.id: (i.sku, i.name)
        for i in db.query(Item).filter(Item.id.in_([r.item_id for r in rows] or [None])).all()
    }
    out = []
    for seq, r in enumerate(rows, start=1):
        code, name = names.get(r.item_id, ("", "—"))
        qty = Decimal(getattr(r, "qty", 0) or 0)
        unit = Decimal(getattr(r, "unit_price", None) or getattr(r, "unit_cost", 0) or 0)
        discount = Decimal(getattr(r, "discount", 0) or 0)
        out.append(
            {
                "kind": LINE_KIND_PRODUCT,
                "seq": seq,
                "code": code,
                "title": name,
                "description": "",
                "quantity": qty,
                "unit_price": unit,
                #: فیِ خالص بعد از تخفیفِ ردیف. وقتی تعداد صفر باشد بی‌معنی است و
                #: `None` می‌ماند — عددِ ساختگی بدتر از نبودِ عدد است.
                "net_unit_price": ((qty * unit - discount) / qty) if qty else None,
                "debit": None,
                "credit": None,
            }
        )
    return out


def _journal_lines(db: Session, entry_id: UUID) -> list[dict]:
    """ردیف‌های سندِ حسابداری — ابزارهای خزانه هم همین‌جا دیده می‌شوند.

    دریافتِ صد میلیونی که نصفش نقد و نصفش چک بوده، در دفتر **دو ردیف** دارد؛ پس
    «این صد میلیون از چه ابزارهایی تشکیل شده؟» جوابش همین‌جاست، بدونِ اینکه
    کوبیتا کپیِ دومی از ابزارها نگه دارد.
    """
    rows = (
        db.query(JournalLine, Account.code, Account.name, AnalyticAccount.name)
        .join(Account, Account.id == JournalLine.account_id)
        .outerjoin(AnalyticAccount, AnalyticAccount.id == JournalLine.analytic_id)
        .filter(JournalLine.entry_id == entry_id)
        .order_by(JournalLine.seq)
        .all()
    )
    return [
        {
            "kind": LINE_KIND_JOURNAL,
            "seq": line.seq,
            "code": code,
            "title": name,
            "description": line.description or (analytic or ""),
            "quantity": None,
            "unit_price": None,
            "net_unit_price": None,
            "debit": Decimal(line.debit),
            "credit": Decimal(line.credit),
        }
        for line, code, name, analytic in rows
    ]


def _notice_lines(db: Session, note_id: UUID) -> list[dict]:
    """ردیف‌های اعلامیه — هر کدام یک جفتِ بدهکار/بستانکار."""
    rows = db.query(CreditDebitNoteLine).filter(CreditDebitNoteLine.note_id == note_id).all()
    accounts = {a.id: (a.code, a.name) for a in db.query(Account).all()}
    names = {c.id: c.name for c in db.query(Contact).all()}
    out = []
    for r in rows:
        for side, contact_id_, account_id_ in (
            ("debit", r.debit_contact_id, r.debit_account_id),
            ("credit", r.credit_contact_id, r.credit_account_id),
        ):
            code, name = accounts.get(account_id_, ("", "—"))
            who = names.get(contact_id_, "") if contact_id_ else ""
            out.append(
                {
                    "kind": LINE_KIND_ADJUSTMENT,
                    "seq": r.seq,
                    "code": code,
                    "title": name,
                    "description": " — ".join(x for x in (who, r.description) if x),
                    "quantity": None,
                    "unit_price": None,
                    "net_unit_price": None,
                    "debit": Decimal(r.amount) if side == "debit" else Decimal(0),
                    "credit": Decimal(r.amount) if side == "credit" else Decimal(0),
                }
            )
    return out


#: سندهایی که خودشان ردیفِ تجاری دارند و سربرگشان `journal_entry_id` دارد.
_ENTRY_OWNER = {
    "sales_invoice": SalesInvoice,
    "purchase_invoice": PurchaseInvoice,
    "sales_return": SalesReturn,
    "purchase_return": PurchaseReturn,
    "credit_debit_note": CreditDebitNote,
}


def event_lines(db: Session, source_type: str, source_id: UUID) -> dict:
    """اقلامِ یک رویداد — نوع‌آگاه، و همیشه با ردیف‌های دفترش.

    یک سند می‌تواند هر دو را داشته باشد: ردیف‌های کالا (که «چه چیزی فروخته شد»
    را می‌گویند) و ردیف‌های دفتر (که «چه اثری گذاشت» را). گزارش هر دو را می‌دهد
    و برچسبشان می‌زند؛ **جمعِ هر دو با هم اثرِ اقتصادی نیست** — اثر همان ردیف‌های
    دفتر است.
    """
    model = _ENTRY_OWNER.get(source_type)
    entry_id = None
    if model is not None:
        row = db.get(model, source_id)
        entry_id = row.journal_entry_id if row is not None else None
    else:
        #: رسید، پرداخت، تراکنشِ خزانه و رخدادِ چک هرکدام ستونِ سندِ خودشان را
        #: دارند؛ از رجیستریِ `open_items` خوانده می‌شود تا فهرستِ دومی نسازیم.
        kind = oi.SETTLEABLE.get(source_type)
        if kind is not None:
            row = db.get(kind.model, source_id)
            entry_id = getattr(row, "journal_entry_id", None) if row is not None else None

    lines: list[dict] = []
    products = _product_lines(db, source_type, source_id)
    if products:
        lines.extend(products)
    if source_type == "credit_debit_note":
        lines.extend(_notice_lines(db, source_id))
    if entry_id is not None:
        lines.extend(_journal_lines(db, entry_id))

    return {
        "source_type": source_type,
        "source_id": source_id,
        "label": oi.SETTLEABLE[source_type].label if source_type in oi.SETTLEABLE else source_type,
        "journal_entry_id": entry_id,
        "lines": lines,
    }
