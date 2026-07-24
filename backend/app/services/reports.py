from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.banking import BankAccount
from app.models.cost_center import CostCenter
from app.models.inventory import Contact
from app.models.invoices import PurchaseInvoice, SalesInvoice
from app.models.returns import PurchaseReturn, SalesReturn
from app.models.treasury import TreasuryTransaction
from app.services import chart_codes as cc

AGING_KINDS = ("receivable", "payable")

CREDIT_NORMAL_TYPES = ("liability", "equity", "income")

#: نقش‌های حسابِ نقد و شبه‌نقد — پایه‌ی صورت جریان وجوه نقد.
CASH_ROLES = (cc.CASH, cc.BANK, cc.PETTY_CASH)
#: حساب‌های دارایی ثابت — طبقه‌بندیِ «سرمایه‌گذاری» حتی اگر مشتری کدشان را عوض کرده باشد.
FIXED_ASSET_ROLES = (cc.FIXED_ASSETS, cc.ACCUMULATED_DEPRECIATION)


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
    }


def _signed_balance(account_type: str, total_debit: Decimal, total_credit: Decimal) -> Decimal:
    if account_type in CREDIT_NORMAL_TYPES:
        return total_credit - total_debit
    return total_debit - total_credit


def get_general_ledger(
    db: Session, account_id: UUID, date_from: date | None, date_to: date | None
) -> dict:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب یافت نشد")

    query = db.query(JournalLine, JournalEntry).join(JournalEntry, JournalLine.entry_id == JournalEntry.id).filter(
        JournalLine.account_id == account_id
    )

    opening_balance = Decimal(0)
    if date_from is not None:
        opening_rows = query.filter(JournalEntry.entry_date < date_from).all()
        opening_debit = sum((r[0].debit for r in opening_rows), Decimal(0))
        opening_credit = sum((r[0].credit for r in opening_rows), Decimal(0))
        opening_balance = _signed_balance(account.type, opening_debit, opening_credit)
        query = query.filter(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        query = query.filter(JournalEntry.entry_date <= date_to)

    rows = query.order_by(JournalEntry.entry_date, JournalEntry.number).all()

    running = opening_balance
    lines = []
    for line, entry in rows:
        delta = _signed_balance(account.type, line.debit, line.credit)
        running += delta
        lines.append(
            {
                "entry_id": entry.id,
                "entry_number": entry.number,
                "entry_date": entry.entry_date,
                "description": line.description or entry.description,
                "debit": line.debit,
                "credit": line.credit,
                "balance": running,
            }
        )

    return {
        "account_id": account.id,
        "account_code": account.code,
        "account_name": account.name,
        "opening_balance": opening_balance,
        "lines": lines,
        "closing_balance": running,
    }


def _leaf_account_totals(
    db: Session, date_from: date | None, date_to: date | None, types: tuple[str, ...] | None = None
) -> list[tuple[Account, Decimal, Decimal]]:
    query = (
        db.query(Account, func.coalesce(func.sum(JournalLine.debit), 0), func.coalesce(func.sum(JournalLine.credit), 0))
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .filter(Account.is_group.is_(False))
    )
    if types is not None:
        query = query.filter(Account.type.in_(types))
    if date_from is not None:
        query = query.filter(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        query = query.filter(JournalEntry.entry_date <= date_to)
    query = query.group_by(Account.id)

    return [(acc, Decimal(debit), Decimal(credit)) for acc, debit, credit in query.all()]


def get_trial_balance(db: Session, date_from: date | None, date_to: date | None) -> list[dict]:
    rows = _leaf_account_totals(db, date_from, date_to)
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


def get_cost_center_report(db: Session, date_from: date | None, date_to: date | None) -> dict:
    """سود و زیان به تفکیک مرکز هزینه/پروژه، از ردیف‌های برچسب‌خورده‌ی سند.

    فقط حساب‌های درآمد و هزینه شمرده می‌شوند (سود = درآمد − هزینه). سطرِ `cost_center_id`
    برابر NULL یعنی سندهای برچسب‌نخورده — عمداً نمایش داده می‌شود تا معلوم باشد چه
    بخشی از فعالیت هنوز به هیچ پروژه‌ای نسبت داده نشده.
    """
    query = (
        db.query(
            JournalLine.cost_center_id,
            Account.type,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .filter(Account.type.in_(("income", "expense")))
    )
    if date_from is not None:
        query = query.filter(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        query = query.filter(JournalEntry.entry_date <= date_to)
    query = query.group_by(JournalLine.cost_center_id, Account.type)

    centers: dict[UUID | None, dict[str, Decimal]] = {}
    for cost_center_id, account_type, debit, credit in query.all():
        signed = _signed_balance(account_type, Decimal(debit), Decimal(credit))
        bucket = centers.setdefault(cost_center_id, {"income": Decimal(0), "expense": Decimal(0)})
        bucket["income" if account_type == "income" else "expense"] += signed

    names = {c.id: c for c in db.query(CostCenter).all()}
    rows = []
    for cost_center_id, vals in centers.items():
        center = names.get(cost_center_id)
        rows.append(
            {
                "cost_center_id": cost_center_id,
                "cost_center_code": center.code if center else "",
                "cost_center_name": center.name if center else "بدون مرکز هزینه",
                "income": vals["income"],
                "expense": vals["expense"],
                "profit": vals["income"] - vals["expense"],
            }
        )

    # مراکزِ دارای برچسب اول، بعد سطرِ «بدون مرکز» (None) در انتها
    rows.sort(key=lambda r: (r["cost_center_id"] is None, r["cost_center_code"], r["cost_center_name"]))
    total_income = sum((r["income"] for r in rows), Decimal(0))
    total_expense = sum((r["expense"] for r in rows), Decimal(0))
    return {
        "date_from": date_from,
        "date_to": date_to,
        "rows": rows,
        "total_income": total_income,
        "total_expense": total_expense,
        "total_profit": total_income - total_expense,
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

    # جمعِ تسویه‌ی هر شخص = دریافت/پرداخت + برگشت‌ها (هر دو مانده را کم می‌کنند)
    pool: dict = {}
    settlements = (
        db.query(TreasuryTransaction.contact_id, func.coalesce(func.sum(TreasuryTransaction.amount), 0))
        .filter(TreasuryTransaction.type == settle_type, TreasuryTransaction.transaction_date <= as_of)
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
