"""مرکز هزینه/پروژه — درخت، گاردهای یکپارچگی، و تحلیلِ سودِ هر مرکز.

سه قاعده‌ای که این ماژول تضمین می‌کند:

1. **درخت هرگز حلقه نمی‌زند.** هر بار که پدرِ یک مرکز عوض می‌شود، زنجیره‌ی اجدادش
   پیموده می‌شود؛ حلقه یعنی جمعِ تجمیعیِ بی‌پایان و قفل‌شدنِ گزارش.
2. **حذف هرگز تاریخ را نمی‌شکند.** مرکزی که سند خورده یا زیرشاخه دارد پاک نمی‌شود؛
   راهِ درست «غیرفعال» است تا از فرم‌ها برود ولی در گزارش بماند.
3. **عدد فقط یک‌بار شمرده می‌شود.** سند همیشه به مرکزِ برگ برچسب می‌خورد و رقمِ
   مرکزِ مادر از جمعِ زیرشاخه‌ها (`rollup_*`) درمی‌آید، نه از ستونی جدا.
"""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.budgeting import BudgetLine
from app.models.cost_center import CostCenter
from app.models.invoices import PurchaseInvoice, SalesInvoice
from app.models.user import User
from app.schemas.cost_center import CostCenterIn
from app.services.reports import _signed_balance

#: بیشترین تعداد ردیفِ دفتر که یک‌جا برگردانده می‌شود — سقفِ صفحه، نه کلِ دفتر.
LEDGER_MAX_LIMIT = 200
#: تعدادِ ماه‌های روندِ تحلیل (شمسی).
TREND_MONTHS = 12


# ── درخت ─────────────────────────────────────────────────────────────────────


def _index(db: Session) -> tuple[dict[UUID, CostCenter], dict[UUID | None, list[UUID]]]:
    """همه‌ی مراکز را یک‌بار می‌خواند و نگاشتِ شناسه→مرکز و پدر→فرزندان می‌سازد."""
    centers = db.query(CostCenter).order_by(CostCenter.code, CostCenter.name).all()
    by_id = {c.id: c for c in centers}
    children: dict[UUID | None, list[UUID]] = {}
    for c in centers:
        # پدرِ ناموجود (بازمانده‌ی داده‌ی قدیمی) مثلِ ریشه رفتار می‌کند تا هیچ مرکزی
        # از درخت گم نشود.
        parent = c.parent_id if c.parent_id in by_id else None
        children.setdefault(parent, []).append(c.id)
    return by_id, children


def _depth_and_path(center_id: UUID, by_id: dict[UUID, CostCenter]) -> tuple[int, str]:
    """عمق و مسیرِ خوانا («شعبه تهران / پروژه الف») را از زنجیره‌ی اجداد می‌سازد."""
    names: list[str] = []
    seen: set[UUID] = set()
    cur: UUID | None = center_id
    while cur is not None and cur in by_id and cur not in seen:
        seen.add(cur)
        names.append(by_id[cur].name)
        cur = by_id[cur].parent_id
    names.reverse()
    return max(0, len(names) - 1), " / ".join(names)


def _descendants(root: UUID, children: dict[UUID | None, list[UUID]]) -> set[UUID]:
    """خودِ مرکز به‌علاوه‌ی همه‌ی زیرشاخه‌ها. گاردِ `seen` از حلقه‌ی احتمالی می‌گذرد."""
    out: set[UUID] = set()
    stack = [root]
    while stack:
        node = stack.pop()
        if node in out:
            continue
        out.add(node)
        stack.extend(children.get(node, []))
    return out


def _sorted_tree(children: dict[UUID | None, list[UUID]], by_id: dict[UUID, CostCenter]) -> list[UUID]:
    """ترتیبِ پیمایشِ عمق‌اول: هر مرکز بلافاصله پیش از زیرشاخه‌هایش."""
    order: list[UUID] = []
    seen: set[UUID] = set()

    def walk(parent: UUID | None) -> None:
        for cid in children.get(parent, []):
            if cid in seen:  # گاردِ حلقه
                continue
            seen.add(cid)
            order.append(cid)
            walk(cid)

    walk(None)
    # هر مرکزی که به‌خاطرِ حلقه از پیمایش جا مانده در انتها می‌آید تا فهرست کامل بماند.
    order.extend(cid for cid in by_id if cid not in seen)
    return order


def _assert_parent_ok(db: Session, center_id: UUID | None, parent_id: UUID | None) -> None:
    """پدرِ انتخابی باید وجود داشته باشد و از نوادگانِ خودِ مرکز نباشد."""
    if parent_id is None:
        return
    if center_id is not None and parent_id == center_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "یک مرکز نمی‌تواند زیرمجموعه‌ی خودش باشد")
    if db.get(CostCenter, parent_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مرکزِ بالادستی معتبر نیست")
    if center_id is None:
        return
    _by_id, children = _index(db)
    if parent_id in _descendants(center_id, children):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "مرکزِ بالادستی نمی‌تواند یکی از زیرمجموعه‌های همین مرکز باشد",
        )


def _to_out(
    center: CostCenter, by_id: dict[UUID, CostCenter], children: dict[UUID | None, list[UUID]]
) -> dict:
    depth, path = _depth_and_path(center.id, by_id)
    return {
        "id": center.id,
        "code": center.code,
        "name": center.name,
        "kind": center.kind,
        "parent_id": center.parent_id,
        "manager": center.manager,
        "start_date": center.start_date,
        "end_date": center.end_date,
        "is_active": center.is_active,
        "notes": center.notes,
        "depth": depth,
        "path": path,
        "child_count": len(children.get(center.id, [])),
    }


# ── CRUD ─────────────────────────────────────────────────────────────────────


def list_cost_centers(db: Session, *, include_inactive: bool = True) -> list[dict]:
    """فهرست به ترتیبِ درخت — هر مرکز درست پیش از زیرشاخه‌هایش.

    فیلترِ «فقط فعال» *بعد* از ساختِ درخت اعمال می‌شود تا عمق و مسیرِ یک مرکزِ فعال
    که پدرش غیرفعال است درست بماند.
    """
    by_id, children = _index(db)
    rows = [_to_out(by_id[cid], by_id, children) for cid in _sorted_tree(children, by_id)]
    if not include_inactive:
        rows = [r for r in rows if by_id[r["id"]].is_active]
    return rows


def get_cost_center(db: Session, cost_center_id: UUID) -> CostCenter:
    center = db.get(CostCenter, cost_center_id)
    if center is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مرکز هزینه پیدا نشد")
    return center


def get_cost_center_out(db: Session, cost_center_id: UUID) -> dict:
    center = get_cost_center(db, cost_center_id)
    by_id, children = _index(db)
    return _to_out(center, by_id, children)


def resolve_cost_center_id(
    db: Session, cost_center_id: UUID | None, *, current: UUID | None = None
) -> UUID | None:
    """اعتبارِ برچسبِ مرکز را می‌سنجد؛ برای برچسب‌زدنِ فاکتور/سند استفاده می‌شود.

    None (بدون برچسب) مجاز است. اگر شناسه‌ای داده شد ولی به مرکزی نرسید، خطای ۴۰۰
    برمی‌گرداند تا سند با ارجاعِ نامعتبر (که RLS هم آن را نمی‌بیند) ثبت نشود.

    **مرکزِ غیرفعال برای برچسبِ تازه رد می‌شود.** تا امروز «غیرفعال» فقط یک فیلترِ
    سمتِ کلاینت بود و سرور هر مرکزی را می‌پذیرفت — یعنی فرمی که فیلتر نمی‌کرد
    (فرمِ قراردادِ حقوق) بی‌صدا مرکزِ بسته را برچسب می‌زد.

    `current` همان مقداری است که از قبل روی رکورد نشسته. اگر کاربر عوضش نکرده،
    گارد نمی‌گیرد: وگرنه ویرایشِ عنوانِ یک قالبِ قدیمی به‌خاطرِ مرکزی که سالِ پیش
    بسته شده ناممکن می‌شد — و سابقه باید بماند، این قاعده‌ی خودِ ماژول است.

    **معافیتِ آفلاین ندارد و لازم هم ندارد** (برخلافِ سقفِ اعتبار): صفِ آفلاین
    ردیفِ ناموفق را نگه می‌دارد و دوباره می‌فرستد، پس فاکتور از بین نمی‌رود —
    منتظر می‌ماند تا مرکز دوباره فعال شود یا کاربر مرکزِ دیگری بگذارد.
    """
    if cost_center_id is None:
        return None
    center = db.get(CostCenter, cost_center_id)
    if center is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مرکز هزینه‌ی انتخاب‌شده معتبر نیست")
    if not center.is_active and cost_center_id != current:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"مرکزِ «{center.name}» غیرفعال است و به سندِ تازه برچسب نمی‌خورد؛ "
            "مرکزِ دیگری انتخاب کنید یا آن را دوباره فعال کنید.",
        )
    return cost_center_id


def _assert_code_free(db: Session, code: str, *, exclude_id: UUID | None = None) -> None:
    """کدِ تکراری را با پیامِ روشن رد می‌کند، پیش از اینکه ایندکس خطای خام بدهد.

    ایندکسِ `uq_cost_centers_tenant_code` قیدِ واقعی است و این تابع جایش را
    نمی‌گیرد — فقط ترجمه‌اش می‌کند. کدِ خالی بررسی نمی‌شود چون اختیاری است و
    ایندکس هم آن را کنار گذاشته.
    """
    code = code.strip()
    if not code:
        return
    query = db.query(CostCenter.id, CostCenter.name).filter(CostCenter.code == code)
    if exclude_id is not None:
        query = query.filter(CostCenter.id != exclude_id)
    clash = query.first()
    if clash is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"کدِ «{code}» قبلاً برای مرکزِ «{clash[1]}» به کار رفته؛ کدِ دیگری بگذارید.",
        )


def create_cost_center(db: Session, data: CostCenterIn, user: User) -> dict:
    _assert_parent_ok(db, None, data.parent_id)
    _assert_code_free(db, data.code)
    center = CostCenter(
        code=data.code.strip(),
        name=data.name.strip(),
        kind=data.kind,
        parent_id=data.parent_id,
        manager=data.manager.strip(),
        start_date=data.start_date,
        end_date=data.end_date,
        is_active=data.is_active,
        notes=data.notes,
        created_by_id=user.id,
    )
    db.add(center)
    db.commit()
    db.refresh(center)
    return get_cost_center_out(db, center.id)


def update_cost_center(db: Session, cost_center_id: UUID, data: CostCenterIn) -> dict:
    center = get_cost_center(db, cost_center_id)
    _assert_parent_ok(db, cost_center_id, data.parent_id)
    _assert_code_free(db, data.code, exclude_id=cost_center_id)
    center.code = data.code.strip()
    center.name = data.name.strip()
    center.kind = data.kind
    center.parent_id = data.parent_id
    center.manager = data.manager.strip()
    center.start_date = data.start_date
    center.end_date = data.end_date
    center.is_active = data.is_active
    center.notes = data.notes
    db.commit()
    db.refresh(center)
    return get_cost_center_out(db, center.id)


def delete_cost_center(db: Session, cost_center_id: UUID) -> None:
    center = get_cost_center(db, cost_center_id)
    # زیرشاخه‌دار را نمی‌شود برداشت: RESTRICTِ دیتابیس هم جلویش را می‌گیرد ولی خطایش
    # برای کاربر بی‌معناست، پس اینجا صریح و فارسی گفته می‌شود.
    if db.query(CostCenter.id).filter(CostCenter.parent_id == cost_center_id).first() is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "این مرکز زیرمجموعه دارد؛ اول زیرمجموعه‌ها را جابه‌جا یا حذف کنید.",
        )
    # اگر سندی (ردیفِ سند یا فاکتور) به این مرکز برچسب خورده، حذف تاریخ را می‌شکند؛
    # به‌جایش باید «غیرفعال» شود تا از فرم‌ها حذف ولی در گزارش‌ها بماند.
    referenced = (
        db.query(JournalLine.id).filter(JournalLine.cost_center_id == cost_center_id).first()
        or db.query(SalesInvoice.id).filter(SalesInvoice.cost_center_id == cost_center_id).first()
        or db.query(PurchaseInvoice.id).filter(PurchaseInvoice.cost_center_id == cost_center_id).first()
    )
    if referenced is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "این مرکز در اسناد استفاده شده و حذف نمی‌شود؛ به‌جایش آن را «غیرفعال» کنید.",
        )
    db.delete(center)
    db.commit()


# ── ارقام ────────────────────────────────────────────────────────────────────


def _zero() -> dict[str, Decimal]:
    return {"income": Decimal(0), "expense": Decimal(0)}


def _direct_amounts(
    db: Session, date_from: date | None, date_to: date | None
) -> tuple[dict[UUID | None, dict[str, Decimal]], dict[UUID | None, int]]:
    """گردشِ حساب‌های درآمد/هزینه به تفکیکِ مرکز — پایه‌ی همه‌ی ارقامِ این ماژول."""
    query = (
        db.query(
            JournalLine.cost_center_id,
            Account.type,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
            func.count(func.distinct(JournalLine.entry_id)),
        )
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .filter(Account.type.in_(("income", "expense")))
    )
    if date_from is not None:
        query = query.filter(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        query = query.filter(JournalEntry.entry_date <= date_to)

    amounts: dict[UUID | None, dict[str, Decimal]] = {}
    entries: dict[UUID | None, int] = {}
    for center_id, account_type, debit, credit, entry_count in query.group_by(
        JournalLine.cost_center_id, Account.type
    ).all():
        signed = _signed_balance(account_type, Decimal(debit), Decimal(credit))
        bucket = amounts.setdefault(center_id, _zero())
        bucket["income" if account_type == "income" else "expense"] += signed
        # شمارشِ سند برای هر نوعِ حساب جدا برمی‌گردد؛ بیشینه نزدیک‌ترین تخمینِ بی‌خطر
        # به «تعدادِ سندِ متمایز» است، بی‌آنکه کوئریِ دومی لازم شود.
        entries[center_id] = max(entries.get(center_id, 0), int(entry_count))
    return amounts, entries


def _budgets(
    db: Session, date_from: date | None, date_to: date | None
) -> dict[UUID | None, dict[str, Decimal]]:
    """بودجه‌ی هر مرکز در همان بازه، تفکیک‌شده به درآمد و هزینه."""
    query = db.query(
        BudgetLine.cost_center_id,
        Account.type,
        func.coalesce(func.sum(BudgetLine.amount), 0),
    ).join(Account, BudgetLine.account_id == Account.id)
    if date_from is not None:
        query = query.filter(BudgetLine.period_date >= date_from)
    if date_to is not None:
        query = query.filter(BudgetLine.period_date <= date_to)

    out: dict[UUID | None, dict[str, Decimal]] = {}
    for center_id, account_type, amount in query.group_by(
        BudgetLine.cost_center_id, Account.type
    ).all():
        if account_type not in ("income", "expense"):
            continue
        out.setdefault(center_id, _zero())[account_type] += Decimal(amount)
    return out


def _pct(part: Decimal, whole: Decimal) -> Decimal:
    if whole == 0:
        return Decimal(0)
    return (part / whole * Decimal(100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def get_report(db: Session, date_from: date | None, date_to: date | None) -> dict:
    """سود و زیان به تفکیکِ مرکز — با تجمیعِ درختی و مقایسه با بودجه.

    هر مرکز دو جفت عدد دارد: `income/expense` که فقط ردیف‌های برچسب‌خورده به خودش
    است، و `rollup_*` که زیرشاخه‌ها را هم می‌گیرد. **جمعِ کل از ارقامِ مستقیم گرفته
    می‌شود نه تجمیعی**، وگرنه هر مرکزِ میانی یک‌بار اضافه شمرده می‌شد.

    سطرِ `cost_center_id` برابر NULL یعنی سندهای برچسب‌نخورده — عمداً نمایش داده
    می‌شود تا معلوم باشد چه بخشی از فعالیت هنوز به هیچ مرکزی نسبت داده نشده.
    """
    amounts, entries = _direct_amounts(db, date_from, date_to)
    budgets = _budgets(db, date_from, date_to)
    by_id, children = _index(db)

    rows: list[dict] = []
    for cid in _sorted_tree(children, by_id):
        center = by_id[cid]
        family = _descendants(cid, children)
        direct = amounts.get(cid, _zero())
        roll_income = sum((amounts.get(f, _zero())["income"] for f in family), Decimal(0))
        roll_expense = sum((amounts.get(f, _zero())["expense"] for f in family), Decimal(0))
        budget_income = sum((budgets.get(f, _zero())["income"] for f in family), Decimal(0))
        budget_expense = sum((budgets.get(f, _zero())["expense"] for f in family), Decimal(0))
        has_budget = any(f in budgets for f in family)
        depth, path = _depth_and_path(cid, by_id)
        rows.append(
            {
                "cost_center_id": cid,
                "cost_center_code": center.code,
                "cost_center_name": center.name,
                "kind": center.kind,
                "parent_id": center.parent_id if center.parent_id in by_id else None,
                "depth": depth,
                "path": path,
                "is_active": center.is_active,
                "income": direct["income"],
                "expense": direct["expense"],
                "profit": direct["income"] - direct["expense"],
                "rollup_income": roll_income,
                "rollup_expense": roll_expense,
                "rollup_profit": roll_income - roll_expense,
                "budget_income": budget_income,
                "budget_expense": budget_expense,
                "profit_variance": (
                    (roll_income - roll_expense) - (budget_income - budget_expense)
                    if has_budget
                    else None
                ),
                "entry_count": entries.get(cid, 0),
            }
        )

    untagged = amounts.get(None)
    if untagged is not None:
        rows.append(
            {
                "cost_center_id": None,
                "cost_center_code": "",
                "cost_center_name": "بدون مرکز هزینه",
                "kind": "other",
                "parent_id": None,
                "depth": 0,
                "path": "بدون مرکز هزینه",
                "is_active": True,
                "income": untagged["income"],
                "expense": untagged["expense"],
                "profit": untagged["income"] - untagged["expense"],
                "rollup_income": untagged["income"],
                "rollup_expense": untagged["expense"],
                "rollup_profit": untagged["income"] - untagged["expense"],
                "budget_income": Decimal(0),
                "budget_expense": Decimal(0),
                "profit_variance": None,
                "entry_count": entries.get(None, 0),
            }
        )

    total_income = sum((v["income"] for v in amounts.values()), Decimal(0))
    total_expense = sum((v["expense"] for v in amounts.values()), Decimal(0))
    gross = total_income + total_expense
    untagged_gross = (untagged["income"] + untagged["expense"]) if untagged else Decimal(0)
    return {
        "date_from": date_from,
        "date_to": date_to,
        "rows": rows,
        "total_income": total_income,
        "total_expense": total_expense,
        "total_profit": total_income - total_expense,
        "untagged_share_pct": _pct(untagged_gross, gross),
    }


# ── تحلیلِ یک مرکز ────────────────────────────────────────────────────────────


def _breakdown(
    db: Session, ids: set[UUID], date_from: date | None, date_to: date | None
) -> dict[str, list[dict]]:
    """گردشِ هر حساب درونِ مرکز — «هزینه کجا رفت» که رقمِ کل هرگز نمی‌گوید."""
    query = (
        db.query(
            Account,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .filter(Account.type.in_(("income", "expense")), JournalLine.cost_center_id.in_(ids))
    )
    if date_from is not None:
        query = query.filter(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        query = query.filter(JournalEntry.entry_date <= date_to)

    buckets: dict[str, list[dict]] = {"income": [], "expense": []}
    for account, debit, credit in query.group_by(Account.id).all():
        buckets[account.type].append(
            {
                "account_id": account.id,
                "account_code": account.code,
                "account_name": account.name,
                "account_type": account.type,
                "amount": _signed_balance(account.type, Decimal(debit), Decimal(credit)),
                "share_pct": Decimal(0),
            }
        )
    for rows in buckets.values():
        total = sum((r["amount"] for r in rows), Decimal(0))
        for r in rows:
            r["share_pct"] = _pct(r["amount"], total)
        rows.sort(key=lambda r: r["amount"], reverse=True)
    return buckets


def _monthly(db: Session, ids: set[UUID], anchor: date) -> list[dict]:
    """روندِ ۱۲ ماهه — سطل‌ها **شمسی**اند نه میلادی.

    یک ماهِ میلادی روی دو ماهِ شمسی می‌افتد؛ برچسبِ ماهِ اشتباه روند را برای کاربرِ
    ایرانی بی‌معنا می‌کند. برچسب با رقمِ لاتین برمی‌گردد و ارقامِ فارسی در UI ساخته
    می‌شود، تا همان یک تابعِ محلی‌سازیِ کلاینت همه‌جا مرجع بماند.
    """
    from app.services.printing import gregorian_to_jalali

    jy, jm, _ = gregorian_to_jalali(anchor)
    buckets: list[tuple[int, int]] = []
    for _ in range(TREND_MONTHS):
        buckets.append((jy, jm))
        jm -= 1
        if jm == 0:
            jm = 12
            jy -= 1
    buckets.reverse()
    index_of = {ym: i for i, ym in enumerate(buckets)}

    # کفِ درشت برای کوئری تا کلِ تاریخ خوانده نشود؛ سطل‌بندیِ دقیق در پایتون است.
    lower = anchor - timedelta(days=TREND_MONTHS * 31 + 31)
    income = [Decimal(0)] * TREND_MONTHS
    expense = [Decimal(0)] * TREND_MONTHS
    rows = (
        db.query(JournalEntry.entry_date, Account.type, JournalLine.debit, JournalLine.credit)
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .filter(
            Account.type.in_(("income", "expense")),
            JournalLine.cost_center_id.in_(ids),
            JournalEntry.entry_date >= lower,
            JournalEntry.entry_date <= anchor,
        )
        .all()
    )
    for entry_date, account_type, debit, credit in rows:
        i = index_of.get(gregorian_to_jalali(entry_date)[:2])
        if i is None:
            continue
        signed = _signed_balance(account_type, Decimal(debit), Decimal(credit))
        if account_type == "income":
            income[i] += signed
        else:
            expense[i] += signed

    return [
        {
            "label": f"{y}/{m:02d}",
            "income": income[i],
            "expense": expense[i],
            "profit": income[i] - expense[i],
        }
        for i, (y, m) in enumerate(buckets)
    ]


def _elapsed_pct(center: CostCenter) -> Decimal | None:
    """چند درصد از بازه‌ی پروژه گذشته — کنارِ درصدِ مصرفِ بودجه معنا پیدا می‌کند."""
    if center.start_date is None or center.end_date is None:
        return None
    total = (center.end_date - center.start_date).days
    if total <= 0:
        return Decimal(100)
    gone = (date.today() - center.start_date).days
    return _pct(Decimal(max(0, min(gone, total))), Decimal(total))


def get_analysis(
    db: Session,
    center_id: UUID,
    date_from: date | None,
    date_to: date | None,
    *,
    include_children: bool = True,
) -> dict:
    """پرونده‌ی کاملِ یک مرکز: ارقام، بودجه، ترکیبِ حساب‌ها، روند، و زیرشاخه‌ها."""
    center = get_cost_center(db, center_id)
    by_id, children = _index(db)
    ids = _descendants(center_id, children) if include_children else {center_id}
    amounts, entries = _direct_amounts(db, date_from, date_to)
    budgets = _budgets(db, date_from, date_to)

    income = sum((amounts.get(i, _zero())["income"] for i in ids), Decimal(0))
    expense = sum((amounts.get(i, _zero())["expense"] for i in ids), Decimal(0))
    budget_income = sum((budgets.get(i, _zero())["income"] for i in ids), Decimal(0))
    budget_expense = sum((budgets.get(i, _zero())["expense"] for i in ids), Decimal(0))
    has_budget = any(i in budgets for i in ids)
    profit = income - expense

    span = (
        db.query(func.min(JournalEntry.entry_date), func.max(JournalEntry.entry_date))
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .filter(JournalLine.cost_center_id.in_(ids))
        .one()
    )
    breakdown = _breakdown(db, ids, date_from, date_to)

    child_rows = []
    for cid in children.get(center_id, []):
        family = _descendants(cid, children)
        c_income = sum((amounts.get(f, _zero())["income"] for f in family), Decimal(0))
        c_expense = sum((amounts.get(f, _zero())["expense"] for f in family), Decimal(0))
        child = by_id[cid]
        child_rows.append(
            {
                "id": child.id,
                "code": child.code,
                "name": child.name,
                "kind": child.kind,
                "is_active": child.is_active,
                "income": c_income,
                "expense": c_expense,
                "profit": c_income - c_expense,
            }
        )

    return {
        "center": _to_out(center, by_id, children),
        "date_from": date_from,
        "date_to": date_to,
        "include_children": include_children,
        "income": income,
        "expense": expense,
        "profit": profit,
        "margin_pct": _pct(profit, income) if income > 0 else None,
        "budget_income": budget_income,
        "budget_expense": budget_expense,
        "budget_profit": budget_income - budget_expense,
        "profit_variance": profit - (budget_income - budget_expense) if has_budget else None,
        "has_budget": has_budget,
        "entry_count": sum(entries.get(i, 0) for i in ids),
        "first_entry_date": span[0],
        "last_entry_date": span[1],
        "elapsed_pct": _elapsed_pct(center),
        "income_accounts": breakdown["income"],
        "expense_accounts": breakdown["expense"],
        "monthly": _monthly(db, ids, date_to or date.today()),
        "children": child_rows,
    }


def get_ledger(
    db: Session,
    center_id: UUID,
    date_from: date | None,
    date_to: date | None,
    *,
    include_children: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """ریزِ ردیف‌های سندِ برچسب‌خورده — سندی که پشتِ رقمِ گزارش نشسته.

    فقط ردیف‌های درآمد/هزینه، چون همان‌ها در سودِ مرکز شمرده می‌شوند؛ نشان‌دادنِ
    ردیفِ نقد/بانکِ همان سند فقط عددهای گزارش را زیر سؤال می‌برد.
    """
    get_cost_center(db, center_id)
    by_id, children = _index(db)
    ids = _descendants(center_id, children) if include_children else {center_id}
    query = (
        db.query(JournalLine, JournalEntry, Account)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .filter(Account.type.in_(("income", "expense")), JournalLine.cost_center_id.in_(ids))
    )
    if date_from is not None:
        query = query.filter(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        query = query.filter(JournalEntry.entry_date <= date_to)
    rows = (
        query.order_by(JournalEntry.entry_date.desc(), JournalEntry.number.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, LEDGER_MAX_LIMIT)))
        .all()
    )
    return [
        {
            "line_id": line.id,
            "entry_id": entry.id,
            "entry_number": entry.number,
            "entry_date": entry.entry_date,
            "description": line.description or entry.description,
            "source_type": entry.source_type,
            "account_code": account.code,
            "account_name": account.name,
            "account_type": account.type,
            "debit": Decimal(line.debit),
            "credit": Decimal(line.credit),
            "cost_center_id": line.cost_center_id,
            "cost_center_name": by_id[line.cost_center_id].name if line.cost_center_id in by_id else "",
        }
        for line, entry, account in rows
    ]
