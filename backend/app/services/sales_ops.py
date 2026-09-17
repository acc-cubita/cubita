"""منطقِ عملیاتِ ماژولِ فروش.

سه‌جای این فایل تصمیمِ واقعی دارد و بقیه CRUDِ ساده است:

* `suggest_pricing` — قیمت و تخفیف را *پیشنهاد* می‌دهد، اعمال نمی‌کند.
* `run_commission` — نتیجه را ذخیره می‌کند، نه اینکه هر بار از نو بسازد.
* `post_notice` — تنها چیزی در این ماژول که سند حسابداری می‌زند.
"""
from datetime import date as date_
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.advanced_inventory import PriceList
from app.models.banking import BankAccount
from app.models.cashbox import Cashbox
from app.models.currency import Currency
from app.models.inventory import Contact, Warehouse
from app.services import pricing
from app.models.counters import DOC_CREDIT_DEBIT_NOTE
from app.models.invoices import SalesInvoice
from app.models.sales_ops import (
    CommissionRule,
    CommissionRun,
    CommissionRunLine,
    CreditDebitNote,
    CreditDebitNoteLine,
    DiscountItemGroupMember,
    PricingFactor,
)
from app.models.user import User
from app.services import chart_codes as cc
from app.services import open_items
from app.services.common import get_account, make_journal_entry
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open
from app.services.voiding import guard_no_active_allocations, reverse_journal_entry


# ───────────────────────── ۱) پیشنهادِ قیمت‌گذاری ─────────────────────────


def _active_factors(db: Session, on: date_) -> list[PricingFactor]:
    """عامل‌های فعالِ همان تاریخ. بازه‌ی NULL یعنی بی‌کران از آن سمت."""
    return (
        db.query(PricingFactor)
        .filter(
            PricingFactor.is_active.is_(True),
            or_(PricingFactor.valid_from.is_(None), PricingFactor.valid_from <= on),
            or_(PricingFactor.valid_to.is_(None), PricingFactor.valid_to >= on),
        )
        .all()
    )


def suggest_pricing(
    db: Session,
    item_id: UUID,
    qty: Decimal,
    on: date_ | None = None,
    *,
    sale_type_id: UUID | None = None,
    unit_id: UUID | None = None,
    contact_id: UUID | None = None,
    currency_code: str = "IRR",
) -> dict:
    """قیمت و تخفیفِ پیشنهادی برای یک ردیفِ فاکتور.

    **پیشنهاد است نه حکم.** فرم عدد را می‌گذارد و کاربر می‌تواند عوضش کند، و
    `applied` می‌گوید این عدد از کجا آمده تا کاربر بداند چرا. اجباری‌کردنش یعنی
    گره‌زدنِ مسیرِ ثبتِ حسابداری به موتوری که خطایش سند را وارونه می‌کند.

    ترتیبِ اعمال: قیمتِ پایه از آخرین اعلامیه‌ی قیمتِ اجراشده → عامل‌های افزاینده →
    تخفیف‌ها. افزاینده پیش از تخفیف می‌آید چون تخفیف روی قیمتِ نهایی معنی می‌دهد،
    نه روی قیمتِ پیش از حمل و بسته‌بندی.
    """
    on = on or date_.today()
    qty = Decimal(qty or 0)

    #: قیمت از موتورِ مشترک می‌آید، نه از کوئریِ محلی (§۳۷ §۳۹ §۴۰ §۴۱):
    #: مشخص‌ترین قاعده‌ای که با نوعِ فروش، واحد، گروهِ مشتری و ارزِ این ردیف
    #: می‌خواند. زمینه‌ی خالی همان رفتارِ پیشین را می‌دهد.
    rule = pricing.resolve(
        db,
        item_id,
        on=on,
        sale_type_id=sale_type_id,
        unit_id=unit_id,
        contact_id=contact_id,
        currency_code=currency_code,
    )
    applied: list[dict] = []
    unit_price = Decimal(rule.price) if rule else Decimal(0)
    if rule is not None:
        announcement = db.get(PriceList, rule.price_list_id)
        applied.append(
            {
                "kind": "price_list",
                "name": announcement.name if announcement else "",
                "value": Decimal(rule.price),
            }
        )

    group_ids = {
        g for (g,) in db.query(DiscountItemGroupMember.group_id).filter(
            DiscountItemGroupMember.item_id == item_id
        )
    }

    def matches(f: PricingFactor) -> bool:
        if f.scope == "all":
            return True
        if f.scope == "item":
            return f.item_id == item_id
        return f.group_id in group_ids

    base = unit_price * qty
    markup = Decimal(0)
    for f in (x for x in _active_factors(db, on) if x.kind == "markup" and matches(x)):
        add = (base * Decimal(f.value) / 100) if f.mode == "percent" else (Decimal(f.value) * qty)
        markup += add
        applied.append({"kind": "markup", "name": f.name, "value": add})

    discount = Decimal(0)
    for f in (x for x in _active_factors(db, on) if x.kind == "discount" and matches(x)):
        cut = ((base + markup) * Decimal(f.value) / 100) if f.mode == "percent" else (Decimal(f.value) * qty)
        discount += cut
        applied.append({"kind": "discount", "name": f.name, "value": cut})

    # تخفیف هرگز از مبلغ بیشتر نشود — وگرنه ردیفِ منفی می‌سازد.
    discount = min(discount, base + markup)
    return {
        "unit_price": unit_price,
        "gross": base + markup,
        "discount": discount,
        "net": base + markup - discount,
        "applied": applied,
    }


# ─────────────────────────── ۲) بستنِ فاکتور ────────────────────────────


def close_invoices(
    db: Session,
    user: User,
    *,
    invoice_ids: list[UUID] | None = None,
    date_from: date_ | None = None,
    date_to: date_ | None = None,
) -> dict:
    """فاکتورها را می‌بندد — دسته‌ای یا موردی.

    بستن هیچ اثرِ مالی ندارد؛ فقط فاکتور را از دسترسِ ویرایش و ابطال بیرون می‌برد.
    یک‌طرفه است، به همان دلیلی که «دائم‌کردنِ سند» یک‌طرفه است: «بسته» یعنی
    امضاشده، و برگرداندنش همان چیزی است که این وضعیت باید جلویش را بگیرد.
    """
    query = db.query(SalesInvoice).filter(
        SalesInvoice.closed_at.is_(None), SalesInvoice.voided_at.is_(None)
    )
    if invoice_ids:
        query = query.filter(SalesInvoice.id.in_(invoice_ids))
    if date_from:
        query = query.filter(SalesInvoice.invoice_date >= date_from)
    if date_to:
        query = query.filter(SalesInvoice.invoice_date <= date_to)

    invoices = query.all()
    if not invoices:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فاکتورِ بازی با این شرایط پیدا نشد")

    now = datetime.now(timezone.utc)
    for inv in invoices:
        inv.closed_at = now
        inv.closed_by_id = user.id
    db.flush()
    return {
        "count": len(invoices),
        "first_date": min(i.invoice_date for i in invoices),
        "last_date": max(i.invoice_date for i in invoices),
        "total": sum((Decimal(i.total_amount) for i in invoices), Decimal(0)),
    }


def assert_invoice_open(db: Session, invoice_id: UUID) -> SalesInvoice:
    """گاردِ مشترک: فاکتورِ بسته ویرایش و ابطال نمی‌شود."""
    inv = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id).first()
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور پیدا نشد")
    if inv.closed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "فاکتورِ بسته‌شده تغییر نمی‌کند")
    return inv


# ─────────────────────── ۳) محاسبه و ذخیره‌ی پورسانت ──────────────────────


def preview_commission(db: Session, date_from: date_, date_to: date_) -> dict:
    """پورسانتِ هر فروشنده در بازه — بدونِ ذخیره.

    فاکتورِ باطل حساب نمی‌شود؛ فاکتورِ بی‌فروشنده هم همین‌طور (پورسانت‌بگیری ندارد).
    """
    if date_from > date_to:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تاریخِ شروع بعد از پایان است")

    rules = {r.salesperson_id: r for r in db.query(CommissionRule).filter(CommissionRule.is_active.is_(True))}
    if not rules:
        return {"date_from": date_from, "date_to": date_to, "total_amount": Decimal(0), "rows": []}

    agg = (
        db.query(
            SalesInvoice.salesperson_id,
            func.count(SalesInvoice.id),
            func.coalesce(func.sum(SalesInvoice.total_amount), 0),
            func.coalesce(func.sum(SalesInvoice.total_amount - SalesInvoice.total_cost), 0),
        )
        .filter(
            SalesInvoice.voided_at.is_(None),
            SalesInvoice.salesperson_id.isnot(None),
            SalesInvoice.invoice_date >= date_from,
            SalesInvoice.invoice_date <= date_to,
        )
        .group_by(SalesInvoice.salesperson_id)
        .all()
    )

    names = {u.id: u.name or u.email for u in db.query(User).all()}
    rows = []
    for person_id, count, net, profit in agg:
        rule = rules.get(person_id)
        if rule is None:
            continue  # فروشنده‌ای که قاعده‌ی پورسانت ندارد
        base = Decimal(profit if rule.basis == "profit" else net)
        # سودِ منفی پورسانتِ منفی نمی‌سازد؛ صفر می‌شود.
        base = max(base, Decimal(0))
        amount = (base * Decimal(rule.rate) / 100).quantize(Decimal(1))
        rows.append(
            {
                "salesperson_id": person_id,
                "salesperson_name": names.get(person_id, "—"),
                "invoice_count": int(count),
                "base_amount": base,
                "rate": Decimal(rule.rate),
                "basis": rule.basis,
                "amount": amount,
            }
        )
    rows.sort(key=lambda r: -r["amount"])
    return {
        "date_from": date_from,
        "date_to": date_to,
        "total_amount": sum((r["amount"] for r in rows), Decimal(0)),
        "rows": rows,
    }


def run_commission(db: Session, user: User, date_from: date_, date_to: date_, note: str = "") -> CommissionRun:
    """همان محاسبه، ولی ذخیره‌شده.

    چرا ذخیره و نه محاسبه‌ی هر بار: پورسانت مبنای پرداخت است. اگر زنده محاسبه شود،
    ابطالِ یک فاکتورِ قدیمی عددی را که ماهِ پیش پرداخت شده بی‌خبر عوض می‌کند و دیگر
    معلوم نیست چه چیزی پرداخت شده بود.
    """
    preview = preview_commission(db, date_from, date_to)
    if not preview["rows"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "در این بازه پورسانتی محاسبه نشد")

    run = CommissionRun(
        date_from=date_from,
        date_to=date_to,
        total_amount=preview["total_amount"],
        note=note,
        created_by_id=user.id,
        lines=[
            CommissionRunLine(
                salesperson_id=r["salesperson_id"],
                invoice_count=r["invoice_count"],
                base_amount=r["base_amount"],
                rate=r["rate"],
                basis=r["basis"],
                amount=r["amount"],
            )
            for r in preview["rows"]
        ],
    )
    db.add(run)
    db.flush()
    db.refresh(run)
    return run


# ─────────────────── ۴) اعلامیه‌ی بدهکار/بستانکار (سنددار) ────────────────

#: نقش‌هایی که **موتورِ دیگری** صاحبشان است و اعلامیه نباید مستقیم رویشان بنشیند.
#:
#: اعلامیه فقط مانده را جابه‌جا می‌کند — نه پول، نه کالا، نه مالیات (§۲۸–§۳۰). اگر
#: سمتی از آن «صندوق» باشد، پولی در دفتر جابه‌جا شده که هیچ تراکنشِ خزانه‌ای پشتش
#: نیست و مانده‌ی صندوق از گردشِ صندوق جدا می‌افتد؛ اگر «موجودی کالا» باشد، دفتر از
#: کاردکس؛ اگر مالیات، دفتر از اظهارنامه. هیچ ترازی هم خبر نمی‌دهد، چون سند متوازن
#: است. تا این گارد، سرویس هر معینِ قابلِ ثبتی را می‌پذیرفت و فقط فرم جلویش را
#: می‌گرفت — ولی فرم تنها راهِ رسیدن به این سرویس نیست.
ENGINE_OWNED_ROLES: frozenset[str] = frozenset(
    {
        # خزانه
        cc.CASH,
        cc.BANK,
        cc.PETTY_CASH,
        cc.CHECKS_RECEIVABLE,
        cc.CHECKS_PAYABLE,
        cc.POS_CLEARING,
        cc.CHECKS_IN_COLLECTION,
        # انبار
        cc.INVENTORY,
        cc.GOODS_IN_TRANSIT,
        # مالیات
        cc.VAT_PAYABLE,
        cc.VAT_RECEIVABLE,
        cc.WITHHOLDING_TAX_PAYABLE,
        cc.CONTRACT_INSURANCE_PAYABLE,
        cc.INSURANCE_TAX_PAYABLE,
        # حساب‌های واسطِ پایانِ سال
        cc.CLOSING_ACCOUNT,
        cc.OPENING_ACCOUNT,
    }
)

#: §۳۷ — آنچه رونوشت هرگز با خودش نمی‌برد. هرکدام هویتِ همان سند است.
NOTE_NEVER_DUPLICATED = ("شماره", "تاریخ", "سند حسابداری", "ابطال", "کلید یکتاسازی")


def _assert_currency_known(db: Session, code: str, rate: Decimal) -> None:
    """از موتورِ ارزِ خودِ کوبیتا استفاده کن، موتورِ دومِ اعلامیه نساز (§۲۵)."""
    if code == "IRR":
        if rate != 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "نرخ ارز پایه (ریال) باید یک باشد")
        return
    if db.query(Currency.id).filter(Currency.code == code).first() is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"ارز «{code}» در موتورِ ارزِ کوبیتا تعریف نشده است")


def _base(amount: Decimal, rate: Decimal) -> Decimal:
    """معادلِ ریالیِ یک مبلغ — همان قراردادِ رسید و اعلامیه پرداخت.

    `مبلغ × نرخ`، گرد به ریالِ کامل با نیم به بالا. **ردیف‌به‌ردیف** گرد می‌شود، نه
    روی جمع: هر ردیف دو سمتِ سند را با همین عدد می‌سازد، پس جمعِ دفتر دقیقاً جمعِ
    همین اعداد است و هیچ ردیفِ «اختلافِ گرد کردن»ی لازم نمی‌شود.
    """
    return (Decimal(amount) * Decimal(rate)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def counterparty_accounts(db: Session) -> list[Account]:
    """معین‌هایی که سمتِ **دارای طرف حساب** رویشان می‌نشیند.

    همان فهرستی که تسویه استفاده می‌کند — دریافتنی و پرداختنیِ تجاری، پیداشده با
    `system_role` نه با کد یا نام. دو جا نساختنش عمدی است: اگر روزی حسابِ سومی به
    این دامنه اضافه شود، هر دو با هم می‌فهمند.
    """
    return open_items.counterparty_accounts(db)


def engine_owned_account_ids(db: Session) -> set[UUID]:
    """شناسه‌ی معین‌هایی که خزانه، انبار یا مالیات نگهشان می‌دارد.

    نقش کافی نیست: حسابِ بانکی و صندوق و انبار هرکدام می‌توانند به معینی **بی‌نقش**
    نگاشته شوند (`gl_account_id`)، و آن معین همان‌قدر مالِ موتورِ خودش است.
    """
    ids: set[UUID] = {
        row.id for row in db.query(Account.id).filter(Account.system_role.in_(ENGINE_OWNED_ROLES)).all()
    }
    for column in (BankAccount.gl_account_id, Cashbox.gl_account_id, Warehouse.gl_account_id):
        ids.update(value for (value,) in db.query(column).filter(column.isnot(None)).distinct().all())
    return ids


def other_accounts(db: Session) -> list[Account]:
    """معین‌هایی که سمتِ **بی‌طرف‌حساب** می‌تواند رویشان بنشیند.

    هر معینِ فعال و قابلِ ثبت، جز حساب‌های طرف مقابل (که بدونِ طرف حساب مانده‌ای
    می‌سازند که به هیچ‌کس تعلق ندارد) و حساب‌هایی که موتورِ دیگری صاحبشان است.
    """
    blocked = engine_owned_account_ids(db) | {a.id for a in counterparty_accounts(db)}
    rows = (
        db.query(Account)
        .filter(Account.is_group.is_(False), Account.is_active.is_(True))
        .order_by(Account.code)
        .all()
    )
    return [a for a in rows if a.id not in blocked]


def default_account_for(db: Session, contact: Contact) -> Account:
    """معینِ پیش‌فرضِ یک طرف حساب، از روی **نقشش**.

    مشتری روی دریافتنی می‌نشیند و تأمین‌کننده روی پرداختنی — و همین است که وقتی
    کاربر نوعِ یک سمت را از «مشتری» به «تأمین‌کننده» عوض می‌کند، حسابِ پیشنهادی
    هم عوض می‌شود.

    **پیش‌فرض، قفل نیست.** طرف‌حسابی که هر دو نقش را دارد از دریافتنی شروع
    می‌کند و کاربر می‌تواند پرداختنی را بردارد؛ شاهدی در دست نداریم که این حساب
    تغییرناپذیر باشد، و حدس‌زدنش یعنی بستنِ کاری که کسب‌وکار لازم دارد.

    **واسطه/سهامدار/کارمندِ خالص هم پرداختنی می‌گیرند.** تا پیش از مهاجرتِ ۰۱۶۴
    این به‌طورِ اتفاقی درست کار می‌کرد، چون فرم آن‌ها را «تأمین‌کننده» ثبت می‌کرد.
    حالا نقششان درست ثبت می‌شود، پس این‌جا باید صریح باشد وگرنه پورسانتِ واسطه
    روی حساب‌های **دریافتنی** می‌نشیند — طلبی که وجود ندارد.
    """
    role = cc.ACCOUNTS_RECEIVABLE if contact.is_receivable_party else (
        cc.ACCOUNTS_PAYABLE if contact.is_payable_party else cc.ACCOUNTS_RECEIVABLE)
    return get_account(db, role)


def _assert_role_matches(db: Session, contact: Contact, account: Account, side: str) -> None:
    """نقشِ طرف حساب باید با معینی که انتخاب شده بخواند.

    تأمین‌کننده‌ای که روی «حساب‌های دریافتنی» بنشیند، طلبی می‌سازد که وجود ندارد.
    این گارد همان چیزی است که فرم هم اعمالش می‌کند؛ ولی فرم تنها راهِ رسیدن به
    این سرویس نیست.
    """
    payable = get_account(db, cc.ACCOUNTS_PAYABLE)
    receivable = get_account(db, cc.ACCOUNTS_RECEIVABLE)
    label = "بدهکار" if side == "debit" else "بستانکار"
    if account.id == payable.id and not contact.is_payable_party:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"سمتِ {label}: «{contact.name}» نه تأمین‌کننده است نه واسطه/سهامدار/کارمند، "
            "پس روی حساب‌های پرداختنی نمی‌نشیند.",
        )
    if account.id == receivable.id and not contact.is_receivable_party:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"سمتِ {label}: «{contact.name}» مشتری نیست، پس روی حساب‌های دریافتنی نمی‌نشیند.",
        )


def _leg(
    db: Session,
    *,
    contact_id: UUID | None,
    account_id: UUID | None,
    side: str,
    counterparty_ids: set[UUID],
    engine_ids: set[UUID],
) -> tuple[Contact | None, Account]:
    """یک سمتِ ردیف را اعتبارسنجی و حل می‌کند: (طرف حساب یا هیچ، معین).

    طرف حساب اختیاری است و معین نه. اگر معین نیامده باشد از نقشِ طرف حساب حل
    می‌شود؛ و اگر نه طرف حساب آمده باشد نه معین، سمت اصلاً تعریف‌نشده است.

    **دو سمت، دو قاعده:**

    * سمتی که طرف حساب دارد فقط روی **دریافتنی یا پرداختنی** می‌نشیند. تفصیلیِ
      شخص روی هر معینِ دیگری هم می‌نشست، ولی کارتِ حساب و اقلامِ باز فقط همین دو
      معین را می‌خوانند — پس تعدیل بی‌صدا از صورت‌حسابِ همان کسی غایب می‌شد که
      سند برایش ساخته شده.
    * سمتی که طرف حساب ندارد روی هر معینی می‌نشیند **جز** همان دو (مانده‌ای بی‌صاحب)
      و جز حساب‌هایی که خزانه، انبار یا مالیات صاحبشان است.
    """
    label = "بدهکار" if side == "debit" else "بستانکار"
    contact: Contact | None = None
    if contact_id is not None:
        contact = db.get(Contact, contact_id)
        if contact is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"طرف حسابِ سمتِ {label} پیدا نشد")
        if not contact.is_active:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"سمتِ {label}: «{contact.name}» غیرفعال است"
            )

    if account_id is None:
        if contact is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"سمتِ {label} نه طرف حساب دارد نه حساب معین"
            )
        account = default_account_for(db, contact)
    else:
        account = db.get(Account, account_id)
        if account is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"حسابِ سمتِ {label} پیدا نشد")

    if account.is_group:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"سمتِ {label}: «{account.name}» سرفصل است و سند مستقیم نمی‌پذیرد"
        )
    if not account.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"سمتِ {label}: «{account.name}» غیرفعال است")

    if contact is not None:
        if account.id not in counterparty_ids:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"سمتِ {label}: «{contact.name}» فقط روی حساب‌های دریافتنی یا پرداختنی می‌نشیند؛ "
                f"«{account.name}» حسابِ طرف مقابل نیست و این تعدیل در کارتِ حسابش دیده نمی‌شد.",
            )
        _assert_role_matches(db, contact, account, side)
    else:
        if account.id in counterparty_ids:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"سمتِ {label}: «{account.name}» حسابِ طرف مقابل است؛ بدونِ طرف حساب مانده‌ای می‌سازد "
                "که به هیچ‌کس تعلق ندارد. طرف حساب را انتخاب کنید.",
            )
        if account.id in engine_ids:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"سمتِ {label}: «{account.name}» را خزانه، انبار یا مالیات نگه می‌دارد. اعلامیه فقط "
                "مانده جابه‌جا می‌کند — برای پول رسید یا اعلامیه پرداخت، و برای کالا سندِ انبار بزنید.",
            )
    return contact, account


def _cid(contact: Contact | None) -> UUID | None:
    return contact.id if contact is not None else None


def _analytic_of(contact: Contact | None) -> UUID | None:
    """تفصیلیِ طرف حساب — یا هیچ، برای سمتی که طرف حساب ندارد.

    بدونِ این، سندِ اعلامیه در دفترِ تفصیلیِ همان شخص دیده نمی‌شود؛ یعنی سندی که
    *فقط* برای جابه‌جاکردنِ مانده‌ی او ساخته شده، در حسابِ او نمی‌نشیند.
    """
    return contact.analytic_id if contact is not None else None


def post_notice(
    db: Session,
    user: User,
    *,
    note_date: date_,
    lines: list,
    description: str = "",
    currency_code: str = "IRR",
    exchange_rate: Decimal | float = 1,
) -> CreditDebitNote:
    """اعلامیه را با ردیف‌هایش ثبت و **یک** سند برایش می‌زند.

    هر ردیف یک جفتِ کامل است: سمتِ بدهکار (طرف حساب + معین) و سمتِ بستانکار، با
    یک مبلغِ مشترک. پس ردیف ذاتاً تراز است و سند هم — بی‌آنکه کسی جمعِ دو سمت را
    جداگانه نگه دارد.

    **ثبت یعنی سند، در همان تراکنش.** حالتِ «ذخیره‌شده ولی سندنخورده» عمداً وجود
    ندارد و اندپوینتِ جدایی برای «صدورِ سند» هم نیست؛ پس سندِ دوم برای یک اعلامیه
    از ساختار ناممکن است، نه از یک گارد (§۱۹ §۲۰). قطعی‌شدنِ حسابداری همان
    «موقت/دائم»ِ خودِ سندِ حسابداری است.

    **ردیف‌ها به ترتیب به دفتر می‌روند:** ردیفِ شماره‌ی `k`ِ اعلامیه ردیف‌های `2k-1`
    (بدهکار) و `2k` (بستانکار)ِ سند می‌شود — ردیابیِ ردیف‌به‌ردیف از همین ترتیب
    مشتق است و ستونِ دومی لازم ندارد (§۱۷).

    **یک تراکنش برای کلِ سند.** ردیفِ دومی که رد شود، ردیفِ اول را هم با خودش
    می‌برد؛ سندی که نیمی از ردیف‌هایش در دفتر نشسته باشد بدتر از سندی است که
    اصلاً ثبت نشده.

    این سند **فقط** مانده‌ی حسابداری را جابه‌جا می‌کند: نه پولی حرکت می‌کند، نه
    کالایی، نه مالیاتی محاسبه می‌شود، و **نه هیچ فاکتوری تسویه‌شده می‌شود**.
    """
    if not lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "اعلامیه باید دستِ‌کم یک ردیف داشته باشد")
    assert_period_open(db, note_date)

    rate = Decimal(exchange_rate)
    if rate <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نرخِ ارز باید بزرگ‌تر از صفر باشد")
    _assert_currency_known(db, currency_code, rate)

    counterparty_ids = {a.id for a in counterparty_accounts(db)}
    engine_ids = engine_owned_account_ids(db)

    total = Decimal(0)
    base_total = Decimal(0)
    resolved: list[dict] = []
    for seq, line in enumerate(lines, start=1):
        amount = Decimal(getattr(line, "amount"))
        if amount <= 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"مبلغِ ردیفِ {seq} باید بزرگ‌تر از صفر باشد")
        #: ستونِ مبلغ مثلِ رسید و اعلامیه پرداخت اعشار ندارد. پذیرفتنِ ۱۲٫۵ یعنی
        #: پایگاه‌داده بی‌صدا ۱۳ ذخیره کند در حالی که سند با ۱۲٫۵ × نرخ خورده.
        if amount != amount.to_integral_value():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"مبلغِ ردیفِ {seq} باید عددِ صحیح باشد (بدونِ اعشار)"
            )
        base = _base(amount, rate)
        if base <= 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"معادلِ ریالیِ ردیفِ {seq} صفر می‌شود؛ نرخِ ارز را بررسی کنید"
            )
        debit_contact, debit_account = _leg(
            db,
            contact_id=getattr(line, "debit_contact_id", None),
            account_id=getattr(line, "debit_account_id", None),
            side="debit",
            counterparty_ids=counterparty_ids,
            engine_ids=engine_ids,
        )
        credit_contact, credit_account = _leg(
            db,
            contact_id=getattr(line, "credit_contact_id", None),
            account_id=getattr(line, "credit_account_id", None),
            side="credit",
            counterparty_ids=counterparty_ids,
            engine_ids=engine_ids,
        )
        #: دو سمتِ یکسان یعنی سندی که هیچ‌چیز را جابه‌جا نمی‌کند. قیدِ دیتابیس هم
        #: همین را می‌گوید؛ این‌جا پیامِ قابلِ فهم می‌دهیم به‌جای خطای درایور.
        if debit_account.id == credit_account.id and _cid(debit_contact) == _cid(credit_contact):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"ردیفِ {seq}: دو سمت یکی‌اند و این سند هیچ ماند‌ه‌ای را جابه‌جا نمی‌کند",
            )
        total += amount
        base_total += base
        resolved.append(
            {
                "seq": seq,
                "amount": amount,
                "base": base,
                "description": (getattr(line, "description", "") or "").strip(),
                "debit_contact": debit_contact,
                "debit_account": debit_account,
                "credit_contact": credit_contact,
                "credit_account": credit_account,
            }
        )

    number = next_document_number(db, DOC_CREDIT_DEBIT_NOTE)
    head = f"اعلامیه‌ی بدهکار/بستانکار شماره {number}" + (f" — {description}" if description else "")
    if currency_code != "IRR":
        #: نرخ در شرحِ سند هم می‌نشیند تا سندِ حسابداری بدونِ بازکردنِ اعلامیه
        #: توضیح‌پذیر باشد: «چرا ۵۰ میلیون؟» — «۱۰۰ دلار به نرخِ ۵۰۰ هزار».
        head += f" ({total} {currency_code} به نرخ {rate.normalize()})"

    journal_lines: list[JournalLine] = []
    for row in resolved:
        text = row["description"] or head
        journal_lines.append(
            JournalLine(
                account_id=row["debit_account"].id,
                analytic_id=_analytic_of(row["debit_contact"]),
                debit=row["base"],
                credit=0,
                description=text,
            )
        )
        journal_lines.append(
            JournalLine(
                account_id=row["credit_account"].id,
                analytic_id=_analytic_of(row["credit_contact"]),
                debit=0,
                credit=row["base"],
                description=text,
            )
        )

    entry = make_journal_entry(db, note_date, head, "credit_debit_note", user, journal_lines)
    note = CreditDebitNote(
        number=number,
        note_date=note_date,
        amount=total,
        base_amount=base_total,
        reason=description,
        currency_code=currency_code,
        exchange_rate=rate,
        journal_entry_id=entry.id,
        created_by_id=user.id,
        lines=[
            CreditDebitNoteLine(
                seq=row["seq"],
                amount=row["amount"],
                base_amount=row["base"],
                description=row["description"],
                debit_contact_id=_cid(row["debit_contact"]),
                debit_account_id=row["debit_account"].id,
                credit_contact_id=_cid(row["credit_contact"]),
                credit_account_id=row["credit_account"].id,
            )
            for row in resolved
        ],
    )
    db.add(note)
    db.flush()
    db.refresh(note)
    return note


def void_note(
    db: Session, user: User, note_id: UUID, reason: str, void_date: date_ | None = None
) -> CreditDebitNote:
    """ابطالِ اعلامیه با سندِ معکوس — اصل سرِ جایش می‌ماند.

    **همان مسیرِ ابطالِ بقیه‌ی اسناد** (`reverse_journal_entry`): معکوس از ردیف‌های
    واقعیِ سندِ اصلی ساخته می‌شود، با همان تفصیلی‌ها، `reverses_entry_id` می‌گیرد تا
    دفتر روزنامه جفتِ «اصلی و معکوس» را نشان دهد، و منبعش `void_credit_debit_note`
    است. تا امروز این سند مسیرِ خودش را داشت: معکوس را از بازخواندنِ ردیف‌های
    اعلامیه می‌ساخت، هیچ پیوندی به اصل نداشت، و همیشه امروز تاریخ می‌خورد.

    **قفلِ ردیف پیش از هر بررسی.** بدونِ آن، دو درخواستِ همزمان هر دو «هنوز باطل
    نشده» را می‌دیدند و دو سندِ معکوس می‌زدند — مانده دو بار برمی‌گشت.

    تاریخِ معکوس پیش‌فرض همان تاریخِ اعلامیه است؛ اگر آن دوره بسته باشد، کاربر
    تاریخی در دوره‌ی باز می‌دهد (§۳۶).
    """
    note = (
        db.query(CreditDebitNote).filter(CreditDebitNote.id == note_id).with_for_update().one_or_none()
    )
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اعلامیه پیدا نشد")
    if note.voided_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این اعلامیه قبلاً باطل شده")
    guard_no_active_allocations(db, "credit_debit_note", note.id, "اعلامیه")

    effective_date = void_date or note.note_date
    assert_period_open(db, effective_date)

    entry = db.get(JournalEntry, note.journal_entry_id) if note.journal_entry_id else None
    if entry is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "این اعلامیه سندِ حسابداری ندارد؛ ابطالش چیزی را برنمی‌گرداند"
        )

    clean = reason.strip()
    reverse_journal_entry(
        db,
        entry,
        void_date=effective_date,
        user=user,
        description=f"ابطالِ اعلامیه‌ی بدهکار/بستانکار شماره {note.number}" + (f" — {clean}" if clean else ""),
    )
    note.voided_at = datetime.now(timezone.utc)
    note.voided_by_id = user.id
    note.void_reason = clean
    db.flush()
    return note


def duplicate_note_draft(db: Session, note_id: UUID) -> dict:
    """پیش‌نویسِ اعلامیه‌ی تازه از روی یکی موجود — **بدونِ نوشتن** در پایگاه‌داده.

    رونوشت سندِ اقتصادیِ **تازه** است (§۳۷): ساختار و مبالغ می‌آیند؛ شماره، تاریخ،
    سند، ابطال و کلیدِ یکتاسازی نه. چون چیزی نمی‌نویسد، تکرارِ درخواست هم چیزی
    نمی‌سازد (§۶۵) — سندِ تازه فقط با «صدور»ِ فرم و کلیدِ یکتاسازیِ خودش ثبت می‌شود.

    حساب‌های ردیف همان‌ها می‌آیند که ثبت شده بودند. اگر یکی از آن‌ها از آن روز
    غیرفعال شده باشد، صدور همان خطای روشن را می‌دهد که فرم برای انتخابِ تازه می‌داد.
    """
    note = db.get(CreditDebitNote, note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اعلامیه پیدا نشد")
    if not note.lines:
        #: اعلامیه‌ی پیش از مهاجرتِ ۰۱۲۷ ردیف ندارد و سمتِ دومش حسابِ فروش بود —
        #: رونوشتش همان خطای قدیمی را دوباره می‌ساخت.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این اعلامیه از شکلِ قدیمیِ تک‌سمتی است و ردیف ندارد؛ اعلامیه‌ی تازه را از نو صادر کنید.",
        )
    return {
        "reason": note.reason,
        "currency_code": note.currency_code,
        "exchange_rate": note.exchange_rate,
        "source_number": note.number,
        "lines": [
            {
                "debit_contact_id": r.debit_contact_id,
                "debit_account_id": r.debit_account_id,
                "credit_contact_id": r.credit_contact_id,
                "credit_account_id": r.credit_account_id,
                "amount": r.amount,
                "description": r.description,
            }
            for r in note.lines
        ],
        "cleared_fields": list(NOTE_NEVER_DUPLICATED),
    }
