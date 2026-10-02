"""واحدِ سنجش به‌عنوان داده‌ی پایه، و **تنها** موتورِ تبدیلِ واحد.

§۲۱ صریح است: «موتورِ تبدیل باید بینِ خرید، فروش، انبار و صندوق مشترک باشد؛ هر
فرم خودش تبدیل انجام ندهد.» پس تبدیل یک تابع دارد و فقط همین‌جا زندگی می‌کند.

---

INV-02 نسبت ثابت را از گراف همان کالا و نسبت متغیر را از مشاهدهٔ واقعی
بچ یا معامله می‌خواند. بدون مشاهدهٔ واقعی، تبدیل متغیر خطای روشن دارد.
ورودی سازگاری `to_primary` نیز همین موتور را صدا می‌زند.

**و واحد موجودی نیست (§۱۶).** داشتنِ واحد به هیچ قلمی رفتارِ انباری نمی‌دهد؛
«۵ ساعت مشاوره» واحد دارد و موجودی ندارد.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction
from typing import Iterable, Mapping
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.inventory import CONVERSION_MODES, Item, UnitOfMeasure

QUANTITY_SCALE = Decimal("0.00000001")
QUANTITY_LIMIT = Decimal("10000000000000000")


def exact_decimal(value: Decimal | str | int) -> Decimal:
    """Quantity contracts never pass through binary floating point."""
    if isinstance(value, (float, bool)):
        raise ValueError("مقدار تبدیل باید Decimal یا رشتهٔ عددی باشد")
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("مقدار تبدیل باید عدد متناهی باشد")
    return result


def rounded_quantity(value: Fraction | Decimal) -> Decimal:
    ratio = value if isinstance(value, Fraction) else Fraction(exact_decimal(value))
    with localcontext() as ctx:
        ctx.prec = max(50, len(str(abs(ratio.numerator))) + len(str(ratio.denominator)) + 16)
        result = (Decimal(ratio.numerator) / Decimal(ratio.denominator)).quantize(QUANTITY_SCALE, rounding=ROUND_HALF_UP)
    if abs(result) >= QUANTITY_LIMIT:
        raise ValueError("مقدار تبدیل از ظرفیت ذخیره‌سازی بیشتر است")
    if ratio and not result:
        raise ValueError("مقدار تبدیل پس از گردکردن صفر می‌شود")
    return result


@dataclass(frozen=True)
class ConversionRule:
    id: UUID
    from_unit_id: UUID
    to_unit_id: UUID
    mode: str = "fixed"
    factor: Decimal | None = None
    version: int = 1


@dataclass(frozen=True)
class ObservedRatio:
    """Two observed quantities preserve exact ratios such as 150/36."""
    from_qty: Decimal
    to_qty: Decimal

    def fraction(self) -> Fraction:
        source, target = exact_decimal(self.from_qty), exact_decimal(self.to_qty)
        if source <= 0 or target <= 0:
            raise ValueError("هر دو مقدار واقعی نسبت باید مثبت باشند")
        return Fraction(target) / Fraction(source)


@dataclass(frozen=True)
class ConversionStep:
    rule_id: UUID
    version: int
    from_unit_id: UUID
    to_unit_id: UUID
    ratio: Fraction
    source: str


@dataclass(frozen=True)
class QuantityConversion:
    source_qty: Decimal
    source_unit_id: UUID
    target_qty: Decimal
    target_unit_id: UUID
    ratio: Fraction
    path: tuple[ConversionStep, ...]
    source_unit_name: str = ""
    target_unit_name: str = ""

    def snapshot(self) -> dict:
        def ratio_row(ratio):
            return {"numerator": str(ratio.numerator), "denominator": str(ratio.denominator)}
        return {
            "schema_version": 1, "source_qty": str(self.source_qty),
            "source_unit_id": str(self.source_unit_id), "target_qty": str(self.target_qty),
            "target_unit_id": str(self.target_unit_id), **ratio_row(self.ratio),
            "source_unit_name": self.source_unit_name, "target_unit_name": self.target_unit_name,
            "rounding": "ROUND_HALF_UP", "scale": 8,
            "path": [{"rule_id": str(step.rule_id), "version": step.version,
                      "from_unit_id": str(step.from_unit_id), "to_unit_id": str(step.to_unit_id),
                      "source": step.source, **ratio_row(step.ratio)} for step in self.path],
        }


class ConversionGraph:
    """Exact bidirectional graph with deterministic, consistent paths.

    A graph belongs to one item and one operation. No global cache or current
    rule is consulted by a historical reversal. Missing variable observations
    remove that edge; they never become a guessed factor of one.
    """
    def __init__(self, unit_ids: Iterable[UUID], rules: Iterable[ConversionRule], *,
                 batch_overrides: Mapping[UUID, ObservedRatio] | None = None,
                 transaction_overrides: Mapping[UUID, ObservedRatio] | None = None):
        self.units = frozenset(unit_ids)
        self.edges: dict[UUID, list[ConversionStep]] = {unit: [] for unit in self.units}
        batch = batch_overrides or {}
        transaction = transaction_overrides or {}
        rules = tuple(rules)
        by_id = {rule.id: rule for rule in rules}
        if len(by_id) != len(rules):
            raise ValueError("شناسهٔ قاعدهٔ تبدیل تکراری است")
        for key in set(batch) | set(transaction):
            if key not in by_id or by_id[key].mode != "variable":
                raise ValueError("نسبت واقعی فقط برای قاعدهٔ متغیر همین کالا مجاز است")
        for rule in rules:
            if rule.from_unit_id not in self.units or rule.to_unit_id not in self.units:
                raise ValueError("دو سر تبدیل باید از واحدهای مجاز همان کالا باشند")
            if rule.from_unit_id == rule.to_unit_id:
                raise ValueError("قاعدهٔ تبدیل واحد به خودش ذخیره نمی‌شود")
            if rule.version < 1 or rule.mode not in CONVERSION_MODES:
                raise ValueError("نسخه یا نوع قاعدهٔ تبدیل نامعتبر است")
            if rule.mode == "fixed":
                if rule.factor is None or exact_decimal(rule.factor) <= 0:
                    raise ValueError("ضریب ثابت باید مثبت باشد")
                ratio, source = Fraction(exact_decimal(rule.factor)), "item"
            else:
                if rule.factor is not None:
                    raise ValueError("قاعدهٔ متغیر ضریب ثابت ندارد")
                observation = transaction.get(rule.id) or batch.get(rule.id)
                if observation is None:
                    continue
                ratio = observation.fraction()
                source = "transaction" if rule.id in transaction else "batch"
            self.edges[rule.from_unit_id].append(ConversionStep(rule.id, rule.version, rule.from_unit_id, rule.to_unit_id, ratio, source))
            self.edges[rule.to_unit_id].append(ConversionStep(rule.id, rule.version, rule.to_unit_id, rule.from_unit_id, 1 / ratio, source))
        for edges in self.edges.values():
            edges.sort(key=lambda step: (str(step.to_unit_id), str(step.rule_id)))
        self._validate()

    def _validate(self) -> None:
        potentials: dict[UUID, Fraction] = {}
        for root in sorted(self.units, key=str):
            if root in potentials:
                continue
            potentials[root] = Fraction(1)
            queue = deque([root])
            while queue:
                unit = queue.popleft()
                for edge in self.edges[unit]:
                    expected = potentials[unit] * edge.ratio
                    previous = potentials.get(edge.to_unit_id)
                    if previous is not None and previous != expected:
                        raise ValueError("چرخه یا مسیرهای تبدیل نسبت‌های ناسازگار دارند")
                    if previous is None:
                        potentials[edge.to_unit_id] = expected
                        queue.append(edge.to_unit_id)

    def convert(self, qty: Decimal, source: UUID, target: UUID, *, decimal_allowed: bool = True) -> QuantityConversion:
        qty = exact_decimal(qty)
        if source not in self.units or target not in self.units:
            raise ValueError("واحد انتخاب‌شده برای این کالا مجاز نیست")
        if not decimal_allowed and qty != qty.to_integral_value():
            raise ValueError("مقدار اعشاری برای واحد انتخاب‌شده مجاز نیست")
        queue = deque([(source, Fraction(1), ())])
        seen = {source}
        while queue:
            unit, ratio, path = queue.popleft()
            if unit == target:
                return QuantityConversion(qty, source, rounded_quantity(Fraction(qty) * ratio), target, ratio, path)
            for edge in self.edges[unit]:
                if edge.to_unit_id not in seen:
                    seen.add(edge.to_unit_id)
                    queue.append((edge.to_unit_id, ratio * edge.ratio, (*path, edge)))
        raise ValueError("تبدیل معتبر یافت نشد؛ برای نسبت متغیر مقدار واقعی وارد کنید")


def historical_return_quantity(snapshot: dict, entered_qty: Decimal, *, returned_entered: Decimal = Decimal(0),
                               returned_base: Decimal = Decimal(0)) -> Decimal:
    """Final partial return closes the original rounded quantity exactly."""
    qty, used, used_base = map(exact_decimal, (entered_qty, returned_entered, returned_base))
    original, original_base = map(exact_decimal, (snapshot["source_qty"], snapshot["target_qty"]))
    if original <= 0 or qty <= 0 or used < 0 or used_base < 0 or used + qty > original or used_base > original_base:
        raise ValueError("مقدار برگشت از مقدار باقیماندهٔ سند اصلی بیشتر است")
    if qty + used == original:
        result = original_base - used_base
    else:
        ratio = Fraction(int(snapshot["numerator"]), int(snapshot["denominator"]))
        result = rounded_quantity(Fraction(qty) * ratio)
    if result <= 0 or used_base + result > original_base:
        raise ValueError("مقدار پایهٔ برگشت از باقیماندهٔ سند اصلی بیشتر است")
    return result


def item_graph(db: Session, item: Item, *, batch_id: UUID | None = None,
               transaction_overrides: Mapping[UUID, ObservedRatio] | None = None) -> tuple[ConversionGraph, dict]:
    """RLS-scoped configuration; posting holds the same item lock as editors."""
    from app.models.item_units import ItemUnit, ItemUnitConversion, BatchUnitConversion
    from app.models.advanced_inventory import StockBatch
    db.query(Item).filter(Item.id == item.id).with_for_update().one()
    rows = db.query(ItemUnit, UnitOfMeasure).join(UnitOfMeasure, UnitOfMeasure.id == ItemUnit.unit_id).filter(
        ItemUnit.item_id == item.id, ItemUnit.tenant_id == item.tenant_id,
        ItemUnit.is_active.is_(True), UnitOfMeasure.is_active.is_(True)).all()
    allowed = {row.unit_id: row for row, unit in rows}
    rules = db.query(ItemUnitConversion).filter(ItemUnitConversion.item_id == item.id,
        ItemUnitConversion.tenant_id == item.tenant_id, ItemUnitConversion.is_active.is_(True)).all()
    observations = {}
    if batch_id is not None:
        batch = db.get(StockBatch, batch_id)
        if batch is None or batch.item_id != item.id or batch.tenant_id != item.tenant_id:
            raise HTTPException(400, "بار انتخاب‌شده به همین کالا و شرکت تعلق ندارد")
        observations = {row.rule_id: ObservedRatio(row.from_qty, row.to_qty) for row in db.query(BatchUnitConversion).filter(
            BatchUnitConversion.batch_id == batch_id, BatchUnitConversion.item_id == item.id,
            BatchUnitConversion.tenant_id == item.tenant_id).all()}
    configured = [ConversionRule(rule.id, rule.from_unit_id, rule.to_unit_id, rule.mode, rule.factor, rule.version)
                  for rule in rules if rule.from_unit_id in allowed and rule.to_unit_id in allowed]
    try:
        return ConversionGraph(allowed, configured, batch_overrides=observations,
                               transaction_overrides=transaction_overrides), allowed
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def convert_item_quantity(db: Session, item: Item, qty: Decimal, unit_id: UUID | None, *,
                          context: str = "inventory", batch_id: UUID | None = None,
                          transaction_overrides: Mapping[UUID, ObservedRatio] | None = None) -> QuantityConversion:
    graph, allowed = item_graph(db, item, batch_id=batch_id, transaction_overrides=transaction_overrides)
    source = unit_id or item.primary_unit_id
    if context not in ("purchase", "sale", "inventory", "production"):
        raise HTTPException(400, "زمینهٔ تبدیل واحد نامعتبر است")
    row = allowed.get(source)
    if row is None or not getattr(row, context + "_allowed"):
        unit = resolve(db, source) if source is not None else None
        name = unit.name if unit is not None else "نامشخص"
        raise HTTPException(400, f"واحد «{name}» برای این عملیاتِ «{item.name}» مجاز نیست؛ واحد مجاز کالا را انتخاب کنید")
    try:
        result = graph.convert(qty, source, item.primary_unit_id, decimal_allowed=row.decimal_allowed)
        base = allowed.get(item.primary_unit_id)
        if base is None or not base.inventory_allowed:
            raise ValueError("واحد پایهٔ کالا برای انبار فعال نیست")
        if not base.decimal_allowed and result.target_qty != result.target_qty.to_integral_value():
            raise ValueError("مقدار تبدیل‌شدهٔ واحد پایه باید عدد صحیح باشد؛ مقدار یا نسبت را اصلاح کنید")
        return replace(result, source_unit_name=resolve(db, source).name,
                       target_unit_name=resolve(db, item.primary_unit_id).name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def assert_base_change_allowed(db: Session, item: Item, proposed: UUID | None) -> None:
    if proposed == item.primary_unit_id:
        return
    if proposed is None:
        raise HTTPException(400, "واحد پایهٔ کالا نمی‌تواند خالی باشد")
    # A zero net balance still has history. Inspect references, not SUM(stock).
    from app.database import Base
    from sqlalchemy import select
    configuration = {"item_units", "item_unit_conversions", "batch_unit_conversions",
                     "item_warehouses", "item_attribute_values"}
    for table in Base.metadata.sorted_tables:
        if table.name in configuration or "tenant_id" not in table.c:
            continue
        columns = {fk.parent for fk in table.foreign_keys if fk.column.table.name == "items"}
        for column in columns:
            if db.execute(select(column).where(column == item.id, table.c.tenant_id == item.tenant_id).limit(1)).first():
                raise HTTPException(409, "این کالا سابقهٔ عملیاتی دارد و واحد پایه‌اش قابل تغییر نیست؛ کالای تازه تعریف کنید")


def configure_legacy(db: Session, item: Item, *, old_secondary: UUID | None = None, old_primary: UUID | None = None) -> None:
    """Translate the old two-unit editor into the one new registry."""
    from app.models.item_units import ItemUnit, ItemUnitConversion
    assert_conversion(item)
    if item.primary_unit_id is None:
        item.primary_unit_id = get_or_create(db, item.unit or "عدد").id
        db.flush()
    for unit_id in (item.primary_unit_id, item.secondary_unit_id):
        if unit_id is None:
            continue
        assert_usable(db, unit_id)
        row = db.query(ItemUnit).filter_by(tenant_id=item.tenant_id, item_id=item.id, unit_id=unit_id).first()
        if row is None:
            db.add(ItemUnit(tenant_id=item.tenant_id, item_id=item.id, unit_id=unit_id))
    db.flush()
    if old_secondary is not None and (old_secondary != item.secondary_unit_id or (old_primary is not None and old_primary != item.primary_unit_id)):
        old = db.query(ItemUnitConversion).filter_by(tenant_id=item.tenant_id, item_id=item.id,
            from_unit_id=old_secondary, to_unit_id=old_primary or item.primary_unit_id).first()
        if old is not None:
            old.is_active = False
            old.version += 1
    if item.secondary_unit_id is not None:
        rule = db.query(ItemUnitConversion).filter_by(tenant_id=item.tenant_id, item_id=item.id,
            from_unit_id=item.secondary_unit_id, to_unit_id=item.primary_unit_id).first()
        factor = Decimal(str(item.conversion_factor)) if item.conversion_mode == "fixed" else None
        if rule is None:
            db.add(ItemUnitConversion(tenant_id=item.tenant_id, item_id=item.id,
                from_unit_id=item.secondary_unit_id, to_unit_id=item.primary_unit_id,
                mode=item.conversion_mode, factor=factor))
        else:
            if rule.mode != item.conversion_mode or rule.factor != factor or not rule.is_active:
                rule.version += 1
            rule.mode, rule.factor, rule.is_active = item.conversion_mode, factor, True
    db.flush()
    item_graph(db, item)


def configure_item_unit(db: Session, item: Item, data) -> dict:
    from app.models.item_units import ItemUnit
    db.query(Item).filter_by(id=item.id).with_for_update().one()
    assert_usable(db, data.unit_id)
    row = db.query(ItemUnit).filter_by(tenant_id=item.tenant_id, item_id=item.id, unit_id=data.unit_id).first()
    if row is not None:
        raise HTTPException(409, "این واحد قبلاً برای کالا تعریف شده است")
    if data.unit_id == item.primary_unit_id and (not data.is_active or not data.inventory_allowed):
        raise HTTPException(400, "واحد پایهٔ کالا باید برای انبار فعال بماند")
    row = ItemUnit(tenant_id=item.tenant_id, item_id=item.id, **data.model_dump())
    db.add(row); db.flush()
    return item_unit_row(db, item, row)


def item_unit_row(db: Session, item: Item, row) -> dict:
    return {"unit_id": row.unit_id, "unit_name": resolve(db, row.unit_id).name,
            "is_base": row.unit_id == item.primary_unit_id,
            **{key: getattr(row, key) for key in ("purchase_allowed", "sale_allowed", "inventory_allowed",
                                                "production_allowed", "decimal_allowed", "is_active")}}


def update_item_unit(db: Session, item: Item, unit_id: UUID, data) -> dict:
    from app.models.item_units import ItemUnit
    db.query(Item).filter_by(id=item.id).with_for_update().one()
    row = db.query(ItemUnit).filter_by(tenant_id=item.tenant_id, item_id=item.id, unit_id=unit_id).first()
    if row is None:
        raise HTTPException(404, "واحد کالا یافت نشد")
    fields = data.model_dump(exclude_unset=True, exclude_none=True)
    if unit_id == item.primary_unit_id and (fields.get("is_active") is False or fields.get("inventory_allowed") is False):
        raise HTTPException(400, "واحد پایهٔ کالا باید برای انبار فعال بماند")
    for key, value in fields.items():
        setattr(row, key, value)
    db.flush()
    return item_unit_row(db, item, row)


def configure_rule(db: Session, item: Item, data, *, rule_id: UUID | None = None) -> dict:
    with db.begin_nested():
        return _configure_rule(db, item, data, rule_id=rule_id)


def _configure_rule(db: Session, item: Item, data, *, rule_id: UUID | None = None) -> dict:
    from app.models.item_units import ItemUnit, ItemUnitConversion, BatchUnitConversion
    db.query(Item).filter_by(id=item.id).with_for_update().one()
    allowed = {row.unit_id for row in db.query(ItemUnit).filter_by(tenant_id=item.tenant_id, item_id=item.id, is_active=True)}
    if not {data.from_unit_id, data.to_unit_id} <= allowed:
        raise HTTPException(400, "دو سر تبدیل باید از واحدهای فعال همین کالا باشند")
    for unit_id in (data.from_unit_id, data.to_unit_id):
        assert_usable(db, unit_id)
    if rule_id is None:
        duplicate = db.query(ItemUnitConversion.id).filter_by(tenant_id=item.tenant_id, item_id=item.id,
            from_unit_id=data.from_unit_id, to_unit_id=data.to_unit_id).first()
        if duplicate:
            raise HTTPException(409, "قاعدهٔ این دو واحد وجود دارد؛ همان قاعده را ویرایش کنید")
        row = ItemUnitConversion(tenant_id=item.tenant_id, item_id=item.id, **data.model_dump())
        db.add(row)
    else:
        row = db.query(ItemUnitConversion).filter_by(id=rule_id, tenant_id=item.tenant_id, item_id=item.id).first()
        if row is None:
            raise HTTPException(404, "قاعدهٔ تبدیل یافت نشد")
        if row.from_unit_id != data.from_unit_id or row.to_unit_id != data.to_unit_id or row.mode != data.mode:
            raise HTTPException(409, "هویت دو سر و نوع قاعده ثابت است؛ قاعدهٔ تازه بسازید")
        row.factor = data.factor
        row.version += 1
        row.is_active = True
    db.flush()
    item_graph(db, item)
    batch_ids = db.query(BatchUnitConversion.batch_id).filter_by(tenant_id=item.tenant_id, item_id=item.id).distinct().all()
    for (batch_id,) in batch_ids:
        item_graph(db, item, batch_id=batch_id)
    if row.from_unit_id == item.secondary_unit_id and row.to_unit_id == item.primary_unit_id:
        item.conversion_mode = row.mode
        item.conversion_factor = row.factor if row.factor is not None else Decimal(0)
    db.flush()
    return rule_row(row)


def rule_row(row) -> dict:
    result = {key: getattr(row, key) for key in ("id", "from_unit_id", "to_unit_id", "mode", "version", "is_active")}
    result["factor"] = str(row.factor) if row.factor is not None else None
    return result


def deactivate_rule(db: Session, item: Item, rule_id: UUID) -> None:
    from app.models.item_units import ItemUnitConversion
    db.query(Item).filter_by(id=item.id).with_for_update().one()
    row = db.query(ItemUnitConversion).filter_by(id=rule_id, tenant_id=item.tenant_id, item_id=item.id).first()
    if row is None:
        raise HTTPException(404, "قاعدهٔ تبدیل یافت نشد")
    row.is_active = False
    row.version += 1
    db.flush()


def configure_batch_ratio(db: Session, item: Item, batch_id: UUID, data, user_id: UUID) -> dict:
    with db.begin_nested():
        return _configure_batch_ratio(db, item, batch_id, data, user_id)


def _configure_batch_ratio(db: Session, item: Item, batch_id: UUID, data, user_id: UUID) -> dict:
    from app.models.item_units import BatchUnitConversion, ItemUnitConversion
    item_graph(db, item, batch_id=batch_id)
    rule = db.query(ItemUnitConversion).filter_by(id=data.rule_id, tenant_id=item.tenant_id,
        item_id=item.id, is_active=True).first()
    if rule is None or rule.mode != "variable":
        raise HTTPException(400, "نسبت بار فقط برای قاعدهٔ متغیر فعال همین کالا مجاز است")
    row = db.query(BatchUnitConversion).filter_by(tenant_id=item.tenant_id, batch_id=batch_id, rule_id=data.rule_id).first()
    if row is None:
        row = BatchUnitConversion(tenant_id=item.tenant_id, item_id=item.id, batch_id=batch_id, **data.model_dump(), approved_by_id=user_id)
        db.add(row)
    else:
        row.from_qty, row.to_qty, row.approved_by_id = data.from_qty, data.to_qty, user_id
    db.flush()
    item_graph(db, item, batch_id=batch_id)
    return {"rule_id": row.rule_id, "from_qty": str(row.from_qty), "to_qty": str(row.to_qty)}


def resolve(db: Session, unit_id: UUID) -> UnitOfMeasure:
    # Requery through RLS: identity-map entries may belong to an earlier tenant scope.
    unit = db.query(UnitOfMeasure).filter(UnitOfMeasure.id == unit_id).one_or_none()
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "واحد سنجش یافت نشد")
    return unit


def get_or_create(db: Session, name: str) -> UnitOfMeasure:
    """واحد را با نامش پیدا می‌کند و اگر نبود می‌سازد.

    برای مسیرهایی که واحد را هنوز به‌صورتِ نوشتار می‌دهند (ورودِ گروهیِ کالا،
    بازار، بازیابیِ پشتیبان). این **نشتِ متنِ آزاد را می‌بندد**: هر نوشتاری که از
    بیرون می‌آید یک ردیفِ واحد می‌شود، نه یک رشته‌ی سرگردان روی کالا.
    """
    name = (name or "").strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نامِ واحد نمی‌تواند خالی باشد")
    unit = db.query(UnitOfMeasure).filter(UnitOfMeasure.name == name).first()
    if unit is None:
        unit = UnitOfMeasure(name=name)
        db.add(unit)
        db.flush()
    return unit


def assert_usable(db: Session, unit_id: UUID | None) -> UnitOfMeasure | None:
    """واحدِ غیرفعال در تعریفِ تازه انتخاب نمی‌شود.

    کالاهایی که از قبل رویش نشسته‌اند دست نمی‌خورند — غیرفعال‌کردن گذشته را پاک
    نمی‌کند، فقط جلوی انتخابِ تازه را می‌گیرد.
    """
    if unit_id is None:
        return None
    unit = resolve(db, unit_id)
    if not unit.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"واحدِ «{unit.name}» غیرفعال است و انتخاب نمی‌شود.",
        )
    return unit


def assert_can_deactivate(db: Session, unit: UnitOfMeasure) -> None:
    """واحدی که هنوز روی کالایی نشسته بی‌صدا غیرفعال نمی‌شود.

    مثلِ انبار: پیام تعداد را می‌گوید، چون «عملیات ناموفق» کاربر را می‌فرستد
    دنبالِ چیزی که خودمان می‌دانیم.
    """
    from app.models.item_units import ItemUnit
    registered = db.query(ItemUnit.item_id).filter(ItemUnit.unit_id == unit.id, ItemUnit.is_active.is_(True))
    used = db.query(Item.id).filter(
        (Item.primary_unit_id == unit.id) | (Item.secondary_unit_id == unit.id) | Item.id.in_(registered)
    ).count()
    if used:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"واحدِ «{unit.name}» روی {used:,} قلم کالا نشسته و غیرفعال نمی‌شود. "
            "اول واحدِ آن کالاها را عوض کنید.",
        )


def sync_item_unit(db: Session, item: Item) -> None:
    """`Item.unit` را با نامِ واحدِ اصلی هم‌گام می‌کند.

    **این تنها جایی است که آن ستون نوشته می‌شود.** از این پس `unit` پرتوِ نامِ
    واحدِ اصلی است نه منبعِ حقیقت؛ نگه‌داشتنش عمدی است چون ردیفِ فاکتور، بسته‌ی
    مؤدیان، بازار و فروشگاه همه آن را می‌خوانند و شکستنشان چیزی درست‌تر نمی‌کرد.
    """
    if item.primary_unit_id is None:
        return
    unit = db.get(UnitOfMeasure, item.primary_unit_id)
    if unit is not None:
        item.unit = unit.name


def assert_conversion(item: Item) -> None:
    """نسبتِ تبدیل باید با واحدِ فرعی بخواند (§۲۰ §۲۱ §۲۲)."""
    if item.conversion_mode not in CONVERSION_MODES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نحوه‌ی تبدیلِ واحد نامعتبر است")
    if item.secondary_unit_id is None:
        return
    if item.secondary_unit_id == item.primary_unit_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "واحدِ فرعی نمی‌تواند همان واحدِ اصلی باشد"
        )
    if item.conversion_mode == "fixed" and Decimal(item.conversion_factor or 0) <= 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "برای نسبتِ ثابت باید بگویید هر واحدِ فرعی چند واحدِ اصلی است (مثلاً ۱ کارتن = ۲۴ عدد).",
        )


def to_primary(db: Session, item: Item, qty: Decimal, unit_id: UUID | None) -> Decimal:
    """Compatibility entry point delegates to the exact graph, never a second formula."""
    from app.models.item_units import ItemUnit
    if not db.query(ItemUnit.id).filter_by(item_id=item.id, tenant_id=item.tenant_id).first():
        configure_legacy(db, item)
    return convert_item_quantity(db, item, qty, unit_id).target_qty


def row(db: Session, item: Item) -> dict:
    """بخشِ واحدهای ردیفِ فهرستِ کالا (§۴۸)."""
    primary = db.get(UnitOfMeasure, item.primary_unit_id) if item.primary_unit_id else None
    secondary = db.get(UnitOfMeasure, item.secondary_unit_id) if item.secondary_unit_id else None
    return {
        "primary_unit_id": item.primary_unit_id,
        "primary_unit_name": primary.name if primary else item.unit,
        "secondary_unit_id": item.secondary_unit_id,
        "secondary_unit_name": secondary.name if secondary else "",
    }
