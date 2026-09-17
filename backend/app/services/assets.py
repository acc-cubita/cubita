from decimal import ROUND_HALF_UP, Decimal
from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.assets import AssetAssignment, AssetDisposal, DepreciationEntry, FixedAsset
from app.models.cost_center import CostCenter
from app.models.inventory import Contact
from app.models.user import User
from app.schemas.assets import AssetAssignmentIn, AssetDisposalIn, FixedAssetIn
from app.services import chart_codes as cc
from app.services.common import get_or_create_account, make_journal_entry
from app.services.period_close import assert_period_open


def _accumulated_depreciation_account(db: Session):
    return get_or_create_account(
        db,
        cc.ACCUMULATED_DEPRECIATION,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.ACCUMULATED_DEPRECIATION],
        name="استهلاک انباشته",
        acc_type="asset",  # کاهنده‌ی دارایی؛ ماندهٔ بستانکار دارد و جمع دارایی‌ها را کم می‌کند
        parent_code="11",
    )


def _fixed_assets_account(db: Session):
    return get_or_create_account(
        db,
        cc.FIXED_ASSETS,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.FIXED_ASSETS],
        name="دارایی‌های ثابت (بهای تمام‌شده)",
        acc_type="asset",
        parent_code="12",
    )


def _disposal_gain_account(db: Session):
    return get_or_create_account(
        db,
        cc.ASSET_DISPOSAL_GAIN,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.ASSET_DISPOSAL_GAIN],
        name="سودِ خروجِ دارایی ثابت",
        acc_type="income",
        parent_code="4",
    )


def _disposal_loss_account(db: Session):
    return get_or_create_account(
        db,
        cc.ASSET_DISPOSAL_LOSS,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.ASSET_DISPOSAL_LOSS],
        name="زیانِ خروجِ دارایی ثابت",
        acc_type="expense",
        parent_code="5",
    )


def _depreciation_expense_account(db: Session):
    return get_or_create_account(
        db,
        cc.DEPRECIATION_EXPENSE,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.DEPRECIATION_EXPENSE],
        name="هزینه استهلاک",
        acc_type="expense",
        parent_code="5",
    )


def _depreciable_base(asset: FixedAsset) -> Decimal:
    return Decimal(asset.cost) - Decimal(asset.salvage_value)


def monthly_depreciation(asset: FixedAsset) -> Decimal:
    """استهلاک ماهانه‌ی خط مستقیم، گردشده به عددِ صحیح (ROUND_HALF_UP)."""
    if asset.useful_life_months <= 0:
        return Decimal(0)
    return (_depreciable_base(asset) / Decimal(asset.useful_life_months)).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def _name_maps(db: Session) -> tuple[dict[UUID, str], dict[UUID, str]]:
    """نامِ طرف‌حساب‌ها و مراکزِ هزینه، یک‌بار — تا `to_out` در فهرست N+1 نزند."""
    contacts = {c.id: c.name for c in db.query(Contact.id, Contact.name).all()}
    centers = {c.id: c.name for c in db.query(CostCenter.id, CostCenter.name).all()}
    return contacts, centers


def to_out(asset: FixedAsset, contacts: dict | None = None, centers: dict | None = None) -> dict:
    base = _depreciable_base(asset)
    accumulated = Decimal(asset.accumulated_depreciation)
    contacts = contacts or {}
    centers = centers or {}
    return {
        "id": asset.id,
        "name": asset.name,
        "category": asset.category,
        "acquired_date": asset.acquired_date,
        "cost": Decimal(asset.cost),
        "salvage_value": Decimal(asset.salvage_value),
        "useful_life_months": asset.useful_life_months,
        "method": asset.method,
        "accumulated_depreciation": accumulated,
        "is_disposed": asset.is_disposed,
        "disposed_date": asset.disposed_date,
        "notes": asset.notes,
        "book_value": Decimal(asset.cost) - accumulated,
        "monthly_depreciation": monthly_depreciation(asset),
        "fully_depreciated": accumulated >= base,
        "custodian_id": asset.custodian_id,
        "custodian_name": contacts.get(asset.custodian_id, ""),
        "location": asset.location,
        "cost_center_id": asset.cost_center_id,
        "cost_center_name": centers.get(asset.cost_center_id, ""),
    }


def _out_with_names(db: Session, asset: FixedAsset) -> dict:
    contacts, centers = _name_maps(db)
    return to_out(asset, contacts, centers)


def list_assets(db: Session, *, include_disposed: bool = True) -> list[dict]:
    q = db.query(FixedAsset)
    if not include_disposed:
        q = q.filter(FixedAsset.is_disposed.is_(False))
    assets = q.order_by(FixedAsset.acquired_date.desc(), FixedAsset.created_at.desc()).all()
    contacts, centers = _name_maps(db)
    return [to_out(a, contacts, centers) for a in assets]


def get_asset(db: Session, asset_id: UUID) -> FixedAsset:
    asset = db.get(FixedAsset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دارایی پیدا نشد")
    return asset


def create_asset(db: Session, data: FixedAssetIn, user: User) -> dict:
    asset = FixedAsset(
        name=data.name.strip(),
        category=data.category.strip(),
        acquired_date=data.acquired_date,
        cost=data.cost,
        salvage_value=data.salvage_value,
        useful_life_months=data.useful_life_months,
        notes=data.notes,
        created_by_id=user.id,
    )
    db.add(asset)
    db.flush()

    # سندِ خریدِ دارایی: بدهکارِ «داراییِ ثابت»، بستانکارِ حسابِ تأمین (بانک/صندوق/پرداختنی).
    # بدونِ این سند، دارایی در دفترِ کل نمی‌نشست و پس از اجرای استهلاک، «استهلاکِ انباشته»
    # بدونِ اصلِ دارایی می‌ماند و خالصِ دارایی‌های ثابت در ترازنامه منفی می‌شد. اگر حسابِ
    # تأمین انتخاب نشود (دارایی از قبل در دفاتر است یا آورده)، سندی زده نمی‌شود.
    if data.funding_account_id is not None and Decimal(data.cost) > 0:
        funding = db.get(Account, data.funding_account_id)
        if funding is None or funding.is_group:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "حسابِ تأمینِ مالیِ خرید نامعتبر است")
        assert_period_open(db, data.acquired_date)
        make_journal_entry(
            db,
            data.acquired_date,
            f"خریدِ داراییِ ثابت: {asset.name}",
            "asset_acquisition",
            user,
            [
                JournalLine(account_id=_fixed_assets_account(db).id, debit=data.cost, credit=0, description="بهای تمام‌شده‌ی دارایی"),
                JournalLine(account_id=funding.id, debit=0, credit=data.cost, description=f"بابت خریدِ {asset.name}"),
            ],
        )

    db.commit()
    db.refresh(asset)
    return _out_with_names(db, asset)


def update_asset(db: Session, asset_id: UUID, data: FixedAssetIn) -> dict:
    asset = get_asset(db, asset_id)
    # مبنای مالیِ گذشته دست‌نخورده می‌ماند: اگر قبلاً استهلاک خورده، تغییرِ بهای
    # تمام‌شده نباید از استهلاکِ ثبت‌شده کمتر شود، وگرنه ارزش دفتری بی‌معنا می‌شود.
    if Decimal(data.cost) - Decimal(data.salvage_value) < Decimal(asset.accumulated_depreciation):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "مبنای استهلاکِ جدید از استهلاکِ انباشته‌ی ثبت‌شده کمتر است؛ اول اسناد استهلاک را بررسی کنید.",
        )
    asset.name = data.name.strip()
    asset.category = data.category.strip()
    asset.acquired_date = data.acquired_date
    asset.cost = data.cost
    asset.salvage_value = data.salvage_value
    asset.useful_life_months = data.useful_life_months
    asset.notes = data.notes
    db.commit()
    db.refresh(asset)
    return _out_with_names(db, asset)


DISPOSAL_TYPE_LABELS = {"sale": "فروش", "scrap": "اسقاط/داغی", "donation": "اهدا"}


def dispose_asset(db: Session, asset_id: UUID, data: AssetDisposalIn, user: User) -> dict:
    """خروجِ دارایی از دفاتر — با سندِ واقعی، نه فقط یک پرچم.

    تا پیش از این، «واگذاری» فقط `is_disposed` را روشن می‌کرد: دارایی از چرخه‌ی
    استهلاک بیرون می‌آمد ولی **بهای تمام‌شده‌اش تا ابد در ترازنامه می‌ماند** و
    استهلاکِ انباشته‌اش هم کنارش. یعنی ترازنامه دارایی‌ای را نشان می‌داد که دیگر
    وجود نداشت. سند این را درست می‌کند:

        بدهکار: استهلاک انباشته      (پاک‌کردنِ کاهنده‌ی دارایی)
        بدهکار: حسابِ دریافتِ وجه     (مبلغِ فروش، اگر باشد)
        بستانکار: دارایی ثابت         (بهای تمام‌شده — دارایی از دفتر خارج می‌شود)
        و مابه‌التفاوت: بستانکارِ «سودِ خروج» یا بدهکارِ «زیانِ خروج»

    اسقاط و اهدا حالتِ خاص نیستند؛ فقط مبلغِ دریافتی‌شان صفر است، پس کلِ ارزشِ
    دفتری زیان می‌شود.
    """
    asset = get_asset(db, asset_id)
    if asset.is_disposed:
        raise HTTPException(status.HTTP_409_CONFLICT, "این دارایی قبلاً خارج شده است")
    if data.disposal_date < asset.acquired_date:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "تاریخِ خروج نمی‌تواند پیش از تاریخِ تحصیلِ دارایی باشد",
        )

    proceeds = Decimal(data.proceeds)
    settlement = None
    if proceeds > 0:
        settlement = db.get(Account, data.settlement_account_id)
        if settlement is None or settlement.is_group:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "حسابِ دریافتِ وجه نامعتبر است")
    if data.buyer_id is not None and db.get(Contact, data.buyer_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "خریدار یافت نشد")

    cost = Decimal(asset.cost)
    accumulated = Decimal(asset.accumulated_depreciation)
    book_value = cost - accumulated
    gain_loss = proceeds - book_value

    lines: list[JournalLine] = []
    if accumulated > 0:
        lines.append(
            JournalLine(
                account_id=_accumulated_depreciation_account(db).id,
                debit=accumulated,
                credit=0,
                description="حذفِ استهلاکِ انباشته‌ی دارایی خارج‌شده",
            )
        )
    if proceeds > 0 and settlement is not None:
        lines.append(
            JournalLine(
                account_id=settlement.id,
                debit=proceeds,
                credit=0,
                description=f"دریافتِ بابتِ {DISPOSAL_TYPE_LABELS[data.disposal_type]}ِ {asset.name}",
            )
        )
    if cost > 0:
        lines.append(
            JournalLine(
                account_id=_fixed_assets_account(db).id,
                debit=0,
                credit=cost,
                description=f"خروجِ داراییِ ثابت: {asset.name}",
            )
        )
    if gain_loss > 0:
        lines.append(
            JournalLine(
                account_id=_disposal_gain_account(db).id,
                debit=0,
                credit=gain_loss,
                description=f"سودِ خروجِ {asset.name}",
            )
        )
    elif gain_loss < 0:
        lines.append(
            JournalLine(
                account_id=_disposal_loss_account(db).id,
                debit=-gain_loss,
                credit=0,
                description=f"زیانِ خروجِ {asset.name}",
            )
        )

    #: داراییِ بها-صفر و بی‌استهلاک و بی‌عوض سندی ندارد — سندِ بی‌ردیف نمی‌سازیم.
    #: رکوردِ خروج همچنان ثبت می‌شود تا در گزارش دیده شود.
    entry = None
    if lines:
        assert_period_open(db, data.disposal_date)
        entry = make_journal_entry(
            db,
            data.disposal_date,
            f"خروجِ داراییِ ثابت ({DISPOSAL_TYPE_LABELS[data.disposal_type]}): {asset.name}",
            "asset_disposal",
            user,
            lines,
        )

    db.add(
        AssetDisposal(
            asset_id=asset.id,
            disposal_type=data.disposal_type,
            disposal_date=data.disposal_date,
            proceeds=proceeds,
            settlement_account_id=settlement.id if settlement is not None else None,
            buyer_id=data.buyer_id,
            cost_at_disposal=cost,
            accumulated_at_disposal=accumulated,
            book_value=book_value,
            gain_loss=gain_loss,
            journal_entry_id=entry.id if entry is not None else None,
            notes=data.notes.strip(),
            created_by_id=user.id,
        )
    )
    asset.is_disposed = True
    asset.disposed_date = data.disposal_date
    db.commit()
    db.refresh(asset)
    return _out_with_names(db, asset)


def list_disposals(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    disposal_type: str | None = None,
) -> list[dict]:
    """گزارشِ خروج و فروشِ دارایی — هر ردیف با ارزشِ دفتری و سود/زیانِ همان لحظه."""
    query = db.query(AssetDisposal)
    if date_from is not None:
        query = query.filter(AssetDisposal.disposal_date >= date_from)
    if date_to is not None:
        query = query.filter(AssetDisposal.disposal_date <= date_to)
    if disposal_type:
        query = query.filter(AssetDisposal.disposal_type == disposal_type)
    rows = query.order_by(AssetDisposal.disposal_date.desc(), AssetDisposal.created_at.desc()).all()

    contacts, _ = _name_maps(db)
    assets = {a.id: (a.name, a.category) for a in db.query(FixedAsset.id, FixedAsset.name, FixedAsset.category).all()}
    account_ids = {r.settlement_account_id for r in rows if r.settlement_account_id}
    accounts = (
        {a.id: a.name for a in db.query(Account.id, Account.name).filter(Account.id.in_(account_ids)).all()}
        if account_ids
        else {}
    )
    entry_ids = {r.journal_entry_id for r in rows if r.journal_entry_id}
    numbers = (
        {e.id: e.number for e in db.query(JournalEntry.id, JournalEntry.number).filter(JournalEntry.id.in_(entry_ids)).all()}
        if entry_ids
        else {}
    )

    return [
        {
            "id": r.id,
            "asset_id": r.asset_id,
            "asset_name": assets.get(r.asset_id, ("", ""))[0],
            "asset_category": assets.get(r.asset_id, ("", ""))[1],
            "disposal_type": r.disposal_type,
            "disposal_date": r.disposal_date,
            "proceeds": Decimal(r.proceeds),
            "settlement_account_id": r.settlement_account_id,
            "settlement_account_name": accounts.get(r.settlement_account_id, ""),
            "buyer_id": r.buyer_id,
            "buyer_name": contacts.get(r.buyer_id, ""),
            "cost_at_disposal": Decimal(r.cost_at_disposal),
            "accumulated_at_disposal": Decimal(r.accumulated_at_disposal),
            "book_value": Decimal(r.book_value),
            "gain_loss": Decimal(r.gain_loss),
            "journal_entry_id": r.journal_entry_id,
            "journal_entry_number": numbers.get(r.journal_entry_id),
            "notes": r.notes,
        }
        for r in rows
    ]


# ── تحویل/استقرار و جابه‌جایی ───────────────────────────


def _assign(db: Session, asset_id: UUID, data: AssetAssignmentIn, user: User, *, kind: str) -> dict:
    """هسته‌ی مشترکِ «تحویل» و «جابه‌جایی» — فقط `kind` فرق می‌کند.

    مبدأ از وضعیتِ *فعلیِ* دارایی برداشته می‌شود، نه از ورودیِ کاربر: تنها منبعِ
    درستِ «از کجا» همان چیزی است که تا این لحظه در سیستم نشسته.
    """
    asset = get_asset(db, asset_id)
    if asset.is_disposed:
        raise HTTPException(status.HTTP_409_CONFLICT, "این دارایی واگذار شده و جابه‌جا نمی‌شود")
    if data.to_custodian_id is not None and db.get(Contact, data.to_custodian_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تحویل‌گیرنده یافت نشد")
    if data.to_cost_center_id is not None and db.get(CostCenter, data.to_cost_center_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مرکزِ هزینه یافت نشد")
    if data.assignment_date < asset.acquired_date:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "تاریخِ تحویل نمی‌تواند پیش از تاریخِ تحصیلِ دارایی باشد",
        )

    row = AssetAssignment(
        asset_id=asset.id,
        kind=kind,
        assignment_date=data.assignment_date,
        to_custodian_id=data.to_custodian_id,
        to_location=data.to_location.strip(),
        to_cost_center_id=data.to_cost_center_id,
        from_custodian_id=asset.custodian_id,
        from_location=asset.location,
        from_cost_center_id=asset.cost_center_id,
        notes=data.notes.strip(),
        created_by_id=user.id,
    )
    db.add(row)

    #: وضعیتِ امروزِ دارایی آینه‌ی همین ردیف می‌شود. فیلدی که خالی آمده دست‌نخورده
    #: می‌ماند — «جابه‌جاییِ محل» نباید جمعدار را پاک کند.
    if data.to_custodian_id is not None:
        asset.custodian_id = data.to_custodian_id
    if data.to_location.strip():
        asset.location = data.to_location.strip()
    if data.to_cost_center_id is not None:
        asset.cost_center_id = data.to_cost_center_id

    db.commit()
    db.refresh(asset)
    return _out_with_names(db, asset)


def place_asset(db: Session, asset_id: UUID, data: AssetAssignmentIn, user: User) -> dict:
    """تحویل/استقرارِ اولیه — ورودِ دارایی به مجموعه و تخصیصش به شخص/محل."""
    return _assign(db, asset_id, data, user, kind="placement")


def transfer_asset(db: Session, asset_id: UUID, data: AssetAssignmentIn, user: User) -> dict:
    """جابه‌جایی — انتقالِ دارایی بینِ جمعداران، محل‌ها یا مراکزِ هزینه."""
    return _assign(db, asset_id, data, user, kind="transfer")


def list_assignments(db: Session, *, asset_id: UUID | None = None) -> list[dict]:
    query = db.query(AssetAssignment)
    if asset_id is not None:
        query = query.filter(AssetAssignment.asset_id == asset_id)
    rows = query.order_by(
        AssetAssignment.assignment_date.desc(), AssetAssignment.created_at.desc()
    ).all()
    contacts, centers = _name_maps(db)
    assets = {a.id: a.name for a in db.query(FixedAsset.id, FixedAsset.name).all()}
    return [
        {
            "id": r.id,
            "asset_id": r.asset_id,
            "asset_name": assets.get(r.asset_id, ""),
            "kind": r.kind,
            "assignment_date": r.assignment_date,
            "to_custodian_id": r.to_custodian_id,
            "to_custodian_name": contacts.get(r.to_custodian_id, ""),
            "to_location": r.to_location,
            "to_cost_center_id": r.to_cost_center_id,
            "to_cost_center_name": centers.get(r.to_cost_center_id, ""),
            "from_custodian_id": r.from_custodian_id,
            "from_custodian_name": contacts.get(r.from_custodian_id, ""),
            "from_location": r.from_location,
            "from_cost_center_id": r.from_cost_center_id,
            "from_cost_center_name": centers.get(r.from_cost_center_id, ""),
            "notes": r.notes,
        }
        for r in rows
    ]


def delete_asset(db: Session, asset_id: UUID) -> None:
    asset = get_asset(db, asset_id)
    if asset.depreciation_entries:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "این دارایی سندِ استهلاک دارد و حذف نمی‌شود؛ به‌جایش آن را «واگذارشده» علامت بزنید.",
        )
    db.delete(asset)
    db.commit()


def run_depreciation(db: Session, period_date: date, user: User) -> dict:
    """استهلاکِ همه‌ی دارایی‌های واجدِ شرایط را برای این دوره ثبت می‌کند.

    قاعده‌ها: دارایی واگذارشده مستهلک نمی‌شود؛ داراییِ کاملاً مستهلک‌شده نه؛ دارایی‌ای
    که هنوز خریداری نشده (acquired_date بعد از دوره) نه؛ و دوره‌ای که قبلاً برای یک
    دارایی ثبت شده دوباره ثبت نمی‌شود (قیدِ یکتا). همه‌ی استهلاکِ دوره در یک سند
    واحد جمع می‌شود: بدهکارِ «هزینه استهلاک»، بستانکارِ «استهلاک انباشته».
    """
    assets = (
        db.query(FixedAsset)
        .filter(FixedAsset.is_disposed.is_(False), FixedAsset.acquired_date <= period_date)
        .all()
    )
    already = {
        e.asset_id
        for e in db.query(DepreciationEntry.asset_id).filter(DepreciationEntry.period_date == period_date).all()
    }

    pending: list[tuple[FixedAsset, Decimal]] = []
    for asset in assets:
        if asset.id in already:
            continue
        base = _depreciable_base(asset)
        accumulated = Decimal(asset.accumulated_depreciation)
        remaining = base - accumulated
        if remaining <= 0:
            continue
        amount = min(monthly_depreciation(asset), remaining)  # دوره‌ی آخر ممکن است کمتر باشد
        if amount <= 0:
            continue
        pending.append((asset, amount))

    if not pending:
        return {
            "period_date": period_date,
            "asset_count": 0,
            "total_amount": Decimal(0),
            "journal_entry_id": None,
            "journal_entry_number": None,
        }

    total = sum((amt for _, amt in pending), Decimal(0))
    entry = make_journal_entry(
        db,
        period_date,
        f"استهلاک دوره ({len(pending)} دارایی)",
        "depreciation",
        user,
        [
            JournalLine(account_id=_depreciation_expense_account(db).id, debit=total, credit=0, description="هزینه استهلاک دوره"),
            JournalLine(account_id=_accumulated_depreciation_account(db).id, debit=0, credit=total, description="استهلاک انباشته دوره"),
        ],
    )

    for asset, amount in pending:
        asset.accumulated_depreciation = Decimal(asset.accumulated_depreciation) + amount
        db.add(
            DepreciationEntry(
                asset_id=asset.id,
                period_date=period_date,
                amount=amount,
                journal_entry_id=entry.id,
                created_by_id=user.id,
            )
        )
    db.commit()
    return {
        "period_date": period_date,
        "asset_count": len(pending),
        "total_amount": total,
        "journal_entry_id": entry.id,
        "journal_entry_number": entry.number,
    }


def list_depreciation_entries(db: Session) -> list[dict]:
    rows = (
        db.query(DepreciationEntry)
        .order_by(DepreciationEntry.period_date.desc(), DepreciationEntry.created_at.desc())
        .all()
    )
    return [
        {
            "id": e.id,
            "asset_id": e.asset_id,
            "asset_name": e.asset.name,
            "period_date": e.period_date,
            "amount": Decimal(e.amount),
            "journal_entry_id": e.journal_entry_id,
        }
        for e in rows
    ]
