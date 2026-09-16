"""گزارش‌های تولید — انحرافِ مصرفِ مواد و کاردکسِ خطِ تولید.

هر دو گزارش **مشتق‌اند، نه ذخیره‌شده**: از همان حواله‌ها و رسیدهایی خوانده
می‌شوند که `services/manufacturing.py` ساخته (`production_plan_id` رویشان).
جدولِ گزارشیِ جدا ساخته نشد، چون هر جدولِ گزارشیِ موازی روزی از سندِ اصلی
واگرا می‌شود و کسی نمی‌فهمد کدام درست است.

**سندِ باطل‌شده در هیچ‌کدام شمرده نمی‌شود** (`voided_at IS NULL`): ابطال یعنی آن
حرکت هرگز نبوده، و انحرافی که از حواله‌ی باطل ساخته شود انحرافِ دروغ است.
"""
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.inventory import Item
from app.models.invoices import (
    WarehouseIssue,
    WarehouseIssueLine,
    WarehouseReceipt,
    WarehouseReceiptLine,
)
from app.models.manufacturing import Bom, ProductionPlan


def _plan_rows(db: Session, plan_id: UUID | None) -> list[ProductionPlan]:
    query = db.query(ProductionPlan)
    if plan_id is not None:
        query = query.filter(ProductionPlan.id == plan_id)
    return query.order_by(ProductionPlan.number.desc()).all()


def material_variance(db: Session, *, plan_id: UUID | None = None) -> list[dict]:
    """انحرافِ مصرفِ مواد — «چقدر باید مصرف می‌شد» در برابرِ «چقدر واقعاً رفت».

    **مبنای استاندارد، مقدارِ تولیدشده است نه مقدارِ برنامه.** انحراف یعنی
    «برای همین محصولی که واقعاً درآمد، چقدر بیشتر/کمتر مواد رفت»؛ اگر مبنا
    برنامه بود، هر سفارشِ نیمه‌تمام یک «صرفه‌جوییِ» دروغین نشان می‌داد.

    پس سفارشی که مواد گرفته ولی هنوز محصولی تحویل نداده، طبیعتاً انحرافِ مثبت
    دارد — آن مواد هنوز روی خطِ تولید است. ستونِ «تولیدشده» همین را پیدا می‌کند.
    """
    plans = _plan_rows(db, plan_id)
    if not plans:
        return []
    plan_ids = [p.id for p in plans]

    #: مصرفِ واقعی: جمعِ ردیف‌های همه‌ی حواله‌های *معتبرِ* هر سفارش.
    actual_rows = (
        db.query(
            WarehouseIssue.production_plan_id.label("plan_id"),
            WarehouseIssueLine.item_id.label("item_id"),
            func.sum(WarehouseIssueLine.qty).label("qty"),
            func.sum(WarehouseIssueLine.qty * WarehouseIssueLine.unit_cost).label("cost"),
        )
        .join(WarehouseIssueLine, WarehouseIssueLine.issue_id == WarehouseIssue.id)
        .filter(
            WarehouseIssue.production_plan_id.in_(plan_ids),
            WarehouseIssue.voided_at.is_(None),
        )
        .group_by(WarehouseIssue.production_plan_id, WarehouseIssueLine.item_id)
        .all()
    )
    actual: dict[tuple[UUID, UUID], tuple[Decimal, Decimal]] = {
        (r.plan_id, r.item_id): (Decimal(r.qty or 0), Decimal(r.cost or 0)) for r in actual_rows
    }

    boms = {b.id: b for b in db.query(Bom).filter(Bom.id.in_({p.bom_id for p in plans})).all()}
    item_ids = {item_id for (_, item_id) in actual}
    for bom in boms.values():
        item_ids |= {line.component_item_id for line in bom.lines}
    names = {i.id: i.name for i in db.query(Item).filter(Item.id.in_(item_ids)).all()} if item_ids else {}

    rows: list[dict] = []
    for plan in plans:
        bom = boms.get(plan.bom_id)
        produced = Decimal(plan.qty_produced)
        batches = produced / Decimal(bom.yield_qty) if bom and Decimal(bom.yield_qty) else Decimal(0)

        standard: dict[UUID, Decimal] = {}
        if bom:
            for line in bom.lines:
                standard[line.component_item_id] = (
                    standard.get(line.component_item_id, Decimal(0)) + Decimal(line.qty) * batches
                )

        #: اجزایی که یا استاندارد دارند یا واقعاً مصرف شده‌اند — مصرفِ یک کالای
        #: خارج از فرمول هم باید دیده شود، نه اینکه از گزارش بیفتد.
        components = set(standard) | {item_id for (pid, item_id) in actual if pid == plan.id}
        for item_id in components:
            std_qty = standard.get(item_id, Decimal(0))
            act_qty, act_cost = actual.get((plan.id, item_id), (Decimal(0), Decimal(0)))
            rows.append(
                {
                    "plan_id": plan.id,
                    "plan_number": plan.number,
                    "plan_status": plan.status,
                    "finished_item_id": plan.finished_item_id,
                    "finished_item_name": names.get(plan.finished_item_id, ""),
                    "component_item_id": item_id,
                    "component_item_name": names.get(item_id, ""),
                    "qty_produced": produced,
                    "standard_qty": std_qty,
                    "actual_qty": act_qty,
                    "variance_qty": act_qty - std_qty,
                    "actual_cost": act_cost,
                }
            )
    return rows


def production_kardex(
    db: Session,
    *,
    plan_id: UUID | None = None,
    item_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """کاردکسِ خطِ تولید — هر حرکتی که به «کالای در جریان ساخت» وارد یا از آن خارج شد.

    ورودِ خطِ تولید = حواله‌ی مواد (از انبار بیرون، به خط داخل)؛ خروجِ خطِ تولید =
    رسیدِ محصول (از خط بیرون، به انبار داخل). همان دو سندِ واقعی، از دو سمت.
    """
    issues = (
        db.query(
            WarehouseIssue.issue_date.label("doc_date"),
            WarehouseIssue.number.label("doc_number"),
            WarehouseIssue.production_plan_id.label("plan_id"),
            WarehouseIssueLine.item_id.label("item_id"),
            WarehouseIssueLine.qty.label("qty"),
            WarehouseIssueLine.unit_cost.label("unit_cost"),
        )
        .join(WarehouseIssueLine, WarehouseIssueLine.issue_id == WarehouseIssue.id)
        .filter(
            WarehouseIssue.production_plan_id.isnot(None),
            WarehouseIssue.voided_at.is_(None),
        )
    )
    receipts = (
        db.query(
            WarehouseReceipt.receipt_date.label("doc_date"),
            WarehouseReceipt.number.label("doc_number"),
            WarehouseReceipt.production_plan_id.label("plan_id"),
            WarehouseReceiptLine.item_id.label("item_id"),
            WarehouseReceiptLine.qty.label("qty"),
            WarehouseReceiptLine.unit_cost.label("unit_cost"),
        )
        .join(WarehouseReceiptLine, WarehouseReceiptLine.receipt_id == WarehouseReceipt.id)
        .filter(
            WarehouseReceipt.production_plan_id.isnot(None),
            WarehouseReceipt.voided_at.is_(None),
        )
    )
    if plan_id is not None:
        issues = issues.filter(WarehouseIssue.production_plan_id == plan_id)
        receipts = receipts.filter(WarehouseReceipt.production_plan_id == plan_id)
    if item_id is not None:
        issues = issues.filter(WarehouseIssueLine.item_id == item_id)
        receipts = receipts.filter(WarehouseReceiptLine.item_id == item_id)
    if date_from is not None:
        issues = issues.filter(WarehouseIssue.issue_date >= date_from)
        receipts = receipts.filter(WarehouseReceipt.receipt_date >= date_from)
    if date_to is not None:
        issues = issues.filter(WarehouseIssue.issue_date <= date_to)
        receipts = receipts.filter(WarehouseReceipt.receipt_date <= date_to)

    raw = [("issue", r) for r in issues.all()] + [("receipt", r) for r in receipts.all()]
    plan_numbers = {p.id: p.number for p in db.query(ProductionPlan).all()}
    item_ids = {r.item_id for _, r in raw}
    names = {i.id: i.name for i in db.query(Item).filter(Item.id.in_(item_ids)).all()} if item_ids else {}

    rows = [
        {
            "kind": kind,
            "doc_date": r.doc_date,
            "doc_number": r.doc_number,
            "plan_id": r.plan_id,
            "plan_number": plan_numbers.get(r.plan_id, 0),
            "item_id": r.item_id,
            "item_name": names.get(r.item_id, ""),
            #: ورودِ خط و خروجِ خط در دو ستونِ جدا — یک ستونِ علامت‌دار در گزارشِ
            #: فارسی خوانده نمی‌شود و جمعِ ستونی هم نمی‌دهد.
            "qty_in": Decimal(r.qty) if kind == "issue" else Decimal(0),
            "qty_out": Decimal(r.qty) if kind == "receipt" else Decimal(0),
            "unit_cost": Decimal(r.unit_cost or 0),
            "amount": (Decimal(r.qty) * Decimal(r.unit_cost or 0)).quantize(Decimal(1)),
        }
        for kind, r in raw
    ]
    rows.sort(key=lambda x: (x["doc_date"], x["doc_number"] or 0))
    return rows


def cost_breakdown(db: Session, *, plan_id: UUID | None = None) -> list[dict]:
    """گزارشِ قیمتِ تمام‌شده — سه جزء از هم تفکیک‌شده، نه یک جمعِ مبهم.

    هر سه عدد Snapshotِ خودِ سفارش‌اند (`material_cost_issued`،
    `labor_cost_applied`، `overhead_cost_applied`)، پس گزارش همان چیزی را
    می‌گوید که واقعاً ثبت شده — نه بازمحاسبه‌ای با نرخ‌های امروز.
    """
    plans = _plan_rows(db, plan_id)
    names = (
        {i.id: i.name for i in db.query(Item).filter(Item.id.in_({p.finished_item_id for p in plans})).all()}
        if plans
        else {}
    )
    rows = []
    for plan in plans:
        material = Decimal(plan.material_cost_issued)
        labor = Decimal(plan.labor_cost_applied)
        overhead = Decimal(plan.overhead_cost_applied)
        total = material + labor + overhead
        produced = Decimal(plan.qty_produced)
        rows.append(
            {
                "plan_id": plan.id,
                "plan_number": plan.number,
                "plan_status": plan.status,
                "finished_item_id": plan.finished_item_id,
                "finished_item_name": names.get(plan.finished_item_id, ""),
                "qty_planned": Decimal(plan.qty_planned),
                "qty_produced": produced,
                "material_cost": material,
                "labor_cost": labor,
                "overhead_cost": overhead,
                "total_cost": total,
                "unit_cost": (total / produced).quantize(Decimal(1)) if produced else Decimal(0),
            }
        )
    return rows
