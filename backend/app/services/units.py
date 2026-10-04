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
from uuid import UUID, uuid4

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


def exact_quantity(value: Decimal | str | int) -> Decimal:
    """Reject input that cannot be stored unchanged in Numeric(24, 8)."""
    result = exact_decimal(value)
    if result.copy_abs() >= QUANTITY_LIMIT:
        raise ValueError("مقدار واردشده از ظرفیت ذخیره‌سازی بیشتر است")
    if (Fraction(result) * 100000000).denominator != 1:
        raise ValueError("مقدار واردشده حداکثر هشت رقم اعشار دارد؛ مقدار را اصلاح کنید")
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
    observed_from_qty: Decimal | None = None
    observed_to_qty: Decimal | None = None
    observed_from_unit_id: UUID | None = None
    observed_to_unit_id: UUID | None = None


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
    rounding_adjustment: Decimal = Decimal(0)

    def snapshot(self) -> dict:
        def ratio_row(ratio):
            return {"numerator": str(ratio.numerator), "denominator": str(ratio.denominator)}
        return {
            "schema_version": 1, "source_qty": format(self.source_qty, "f"),
            "source_unit_id": str(self.source_unit_id), "target_qty": format(self.target_qty, "f"),
            "target_unit_id": str(self.target_unit_id), **ratio_row(self.ratio),
            "source_unit_name": self.source_unit_name, "target_unit_name": self.target_unit_name,
            "rounding": "ROUND_HALF_UP", "scale": 8,
            "rounding_adjustment": format(self.rounding_adjustment, "f"),
            "path": [{"rule_id": str(step.rule_id), "version": step.version,
                      "from_unit_id": str(step.from_unit_id), "to_unit_id": str(step.to_unit_id),
                      "source": step.source, **ratio_row(step.ratio),
                      **({"observation": {"from_qty": format(step.observed_from_qty, "f"),
                          "to_qty": format(step.observed_to_qty, "f"),
                          "from_unit_id": str(step.observed_from_unit_id),
                          "to_unit_id": str(step.observed_to_unit_id)}}
                         if step.observed_from_qty is not None else {})} for step in self.path],
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
            observation = None
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
            measured = ((exact_decimal(observation.from_qty), exact_decimal(observation.to_qty),
                rule.from_unit_id, rule.to_unit_id) if observation is not None else (None, None, None, None))
            self.edges[rule.from_unit_id].append(ConversionStep(rule.id, rule.version, rule.from_unit_id, rule.to_unit_id, ratio, source, *measured))
            self.edges[rule.to_unit_id].append(ConversionStep(rule.id, rule.version, rule.to_unit_id, rule.from_unit_id, 1 / ratio, source, *measured))
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
        qty = exact_quantity(qty)
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
    original = conversion_from_snapshot(snapshot)
    return historical_return_conversion(original, entered_qty, original.source_unit_id,
        returned_base=returned_base, returned_in_source=Fraction(exact_decimal(returned_entered))).target_qty


def conversion_from_snapshot(snapshot: dict, *, source_unit_id: UUID | None = None,
                             target_unit_id: UUID | None = None) -> QuantityConversion:
    source = UUID(snapshot["source_unit_id"]) if snapshot.get("source_unit_id") else source_unit_id
    target = UUID(snapshot["target_unit_id"]) if snapshot.get("target_unit_id") else target_unit_id
    if source is None or target is None:
        raise ValueError("هویت واحد تاریخی مشخص نیست؛ برگشت را با واحد پایهٔ سند اصلی ثبت کنید")
    ratio = Fraction(int(snapshot["numerator"]), int(snapshot["denominator"]))
    steps = tuple(ConversionStep(UUID(step["rule_id"]), int(step["version"]),
        UUID(step["from_unit_id"]), UUID(step["to_unit_id"]),
        Fraction(int(step["numerator"]), int(step["denominator"])), step["source"],
        exact_decimal(step["observation"]["from_qty"]) if step.get("observation") else None,
        exact_decimal(step["observation"]["to_qty"]) if step.get("observation") else None,
        UUID(step["observation"]["from_unit_id"]) if step.get("observation") else None,
        UUID(step["observation"]["to_unit_id"]) if step.get("observation") else None)
        for step in snapshot.get("path", []))
    return QuantityConversion(exact_decimal(snapshot["source_qty"]), source,
        exact_decimal(snapshot["target_qty"]), target, ratio, steps,
        snapshot.get("source_unit_name", ""), snapshot.get("target_unit_name", ""),
        exact_decimal(snapshot.get("rounding_adjustment", "0")))


def historical_return_conversion(original: QuantityConversion, qty: Decimal, unit_id: UUID | None, *,
                                 returned_base: Decimal = Decimal(0),
                                 returned_in_source: Fraction = Fraction(0)) -> QuantityConversion:
    qty = exact_quantity(qty)
    source = unit_id or original.target_unit_id
    used_base = exact_decimal(returned_base)
    if used_base < 0 or returned_in_source < 0 or original.source_qty <= 0 or original.target_qty <= 0 or original.ratio <= 0:
        raise ValueError("مقادیر تاریخی برگشت نامعتبرند؛ سند اصلی را بررسی کنید")
    remaining_base = original.target_qty - used_base
    if qty <= 0 or remaining_base <= 0:
        raise ValueError("مقدار برگشت باید مثبت و کمتر از باقیماندهٔ سند اصلی باشد")
    if source == original.target_unit_id:
        target = qty
        ratio, path = Fraction(1), ()
        name = original.target_unit_name
    elif source == original.source_unit_id:
        remaining_source = Fraction(original.source_qty) - returned_in_source
        if remaining_source <= 0:
            raise ValueError("مقدار واردشدهٔ سند اصلی قبلاً کامل برگشت داده شده است")
        last_source = rounded_quantity(remaining_source)
        if qty > last_source:
            raise ValueError("مقدار برگشت از باقیماندهٔ واحد واردشدهٔ سند اصلی بیشتر است")
        # The final slice closes base rounding exactly, including mixed-unit returns.
        target = remaining_base if qty == last_source else rounded_quantity(Fraction(qty) * original.ratio)
        ratio, path = original.ratio, original.path
        name = original.source_unit_name
    else:
        raise ValueError("این واحد در تبدیل تاریخی سند اصلی نیست؛ واحد واردشده یا پایهٔ همان سند را انتخاب کنید")
    if target <= 0 or target > remaining_base:
        raise ValueError("مقدار پایهٔ برگشت از باقیماندهٔ سند اصلی بیشتر است")
    return QuantityConversion(qty, source, target, original.target_unit_id, ratio, path,
                              name, original.target_unit_name, target - rounded_quantity(Fraction(qty) * ratio))


def document_conversion(db: Session, line, item: Item) -> QuantityConversion:
    """Read frozen document conversion; legacy quantities are already base quantities."""
    snapshot = getattr(line, "unit_conversion_snapshot", None)
    if snapshot and snapshot.get("source_unit_id") and snapshot.get("target_unit_id"):
        return conversion_from_snapshot(snapshot)
    # Legacy input is unknown. Do not apply a live secondary-unit factor to it.
    base_id = getattr(line, "base_unit_id", None) or item.primary_unit_id
    if base_id is None:
        base_id = get_or_create(db, getattr(line, "unit_snapshot", "") or item.unit).id
    qty = exact_decimal(getattr(line, "base_qty", None) or line.qty)
    name = getattr(line, "unit_snapshot", "") or item.unit
    return QuantityConversion(qty, base_id, qty, base_id, Fraction(1), (), name, name)


def remaining_entered_quantity(line, movements) -> Decimal:
    """Display the same entered-unit remainder that a frozen partial posting accepts."""
    snapshot = getattr(line, "unit_conversion_snapshot", None) or {}
    ratio = Fraction(int(snapshot.get("numerator", "1")), int(snapshot.get("denominator", "1")))
    source_id = getattr(line, "entered_unit_id", None)
    quantity = getattr(line, "entered_qty", None)
    quantity = line.qty if quantity is None else quantity
    consumed = sum((Fraction(move.entered_qty)
        if move.entered_unit_id == source_id and move.entered_qty is not None
        else Fraction(getattr(move, "base_qty", None) if getattr(move, "base_qty", None) is not None
                      else move.qty) / ratio for move in movements), Fraction(0))
    remaining = Fraction(quantity) - consumed
    return rounded_quantity(remaining) if remaining > 0 else Decimal(0)


def record_batch_observations(db: Session, batch, conversion: QuantityConversion, user) -> None:
    """Keep original observed pairs on the physical batch, without a rounded factor."""
    from app.models.item_units import BatchUnitConversion
    existing = {r.rule_id: r for r in db.query(BatchUnitConversion).filter_by(
        tenant_id=batch.tenant_id, item_id=batch.item_id, batch_id=batch.id).all()}
    for step in conversion.path:
        if step.observed_from_qty is None:
            continue
        previous = existing.get(step.rule_id)
        if previous is not None:
            if ObservedRatio(previous.from_qty, previous.to_qty).fraction() != ObservedRatio(
                step.observed_from_qty, step.observed_to_qty).fraction():
                raise HTTPException(409, "این بار نسبت واقعی متفاوتی دارد؛ مقادیر ناهمگون را در یک بار ادغام نکنید")
            continue
        db.add(BatchUnitConversion(tenant_id=batch.tenant_id, item_id=batch.item_id, batch_id=batch.id,
            rule_id=step.rule_id, from_qty=step.observed_from_qty, to_qty=step.observed_to_qty,
            approved_by_id=user.id))
    db.flush()


class OperationUnitRegistry:
    """Fresh, tenant-scoped configuration held only by one posting transaction."""

    def __init__(self, db: Session, items: Iterable[Item], *, batch_ids: Iterable[UUID] = ()):
        from app.models.item_units import ItemUnit, ItemUnitConversion, BatchUnitConversion
        from app.models.advanced_inventory import StockBatch
        from app.tenant_context import require_session_tenant
        self.db = db
        self.tenant_id = require_session_tenant(db)
        requested = {item.id for item in items}
        self.items = {item.id: item for item in db.query(Item).filter(
            Item.id.in_(requested), Item.tenant_id == self.tenant_id).order_by(Item.id)
            .populate_existing().with_for_update().all()}
        if set(self.items) != requested:
            raise HTTPException(400, "کالای عملیات به شرکت جاری تعلق ندارد")

        def memberships():
            return db.query(ItemUnit, UnitOfMeasure).join(UnitOfMeasure,
                UnitOfMeasure.id == ItemUnit.unit_id).filter(
                ItemUnit.item_id.in_(requested), ItemUnit.tenant_id == self.tenant_id).all()

        rows = memberships()
        registered = {row.item_id for row, _unit in rows}
        missing = requested - registered
        for item_id in sorted(missing, key=str):
            configure_legacy(db, self.items[item_id])
        if missing:
            rows = memberships()
        self.allowed = {item_id: {} for item_id in requested}
        self.names = {}
        for row, unit in rows:
            self.names[unit.id] = unit.name
            if row.is_active and unit.is_active:
                self.allowed[row.item_id][row.unit_id] = row
        self.rules = {item_id: [] for item_id in requested}
        for rule in db.query(ItemUnitConversion).filter(
            ItemUnitConversion.item_id.in_(requested),
            ItemUnitConversion.tenant_id == self.tenant_id,
            ItemUnitConversion.is_active.is_(True)).all():
            allowed = self.allowed[rule.item_id]
            if rule.from_unit_id in allowed and rule.to_unit_id in allowed:
                self.rules[rule.item_id].append(ConversionRule(rule.id, rule.from_unit_id,
                    rule.to_unit_id, rule.mode, rule.factor, rule.version))
        batch_ids = set(batch_ids)
        self.batches = {}
        self.observations = {}
        if batch_ids:
            self.batches = {batch.id: batch for batch in db.query(StockBatch).filter(
                StockBatch.id.in_(batch_ids), StockBatch.tenant_id == self.tenant_id).all()}
            for row in db.query(BatchUnitConversion).filter(
                BatchUnitConversion.batch_id.in_(batch_ids),
                BatchUnitConversion.tenant_id == self.tenant_id).all():
                self.observations.setdefault(row.batch_id, {})[row.rule_id] = ObservedRatio(row.from_qty, row.to_qty)
        self.transaction = db.get_transaction()

    def assert_current(self, db: Session, item: Item) -> None:
        from app.tenant_context import require_session_tenant
        if (db is not self.db or db.get_transaction() is not self.transaction
                or require_session_tenant(db) != self.tenant_id
                or item.id not in self.items or item.tenant_id != self.tenant_id):
            raise HTTPException(400, "پیکربندی واحد باید در همین عملیات و شرکت بارگذاری شود")

    def graph(self, db: Session, item: Item, batch_id, transaction_overrides):
        self.assert_current(db, item)
        if batch_id is not None:
            batch = self.batches.get(batch_id)
            if batch is None or batch.item_id != item.id:
                raise HTTPException(400, "بار انتخاب‌شده به همین کالا و شرکت تعلق ندارد")
        allowed = self.allowed[item.id]
        try:
            return ConversionGraph(allowed, self.rules[item.id],
                batch_overrides=self.observations.get(batch_id, {}),
                transaction_overrides=transaction_overrides), allowed
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc


def item_graph(db: Session, item: Item, *, batch_id: UUID | None = None,
               registry: OperationUnitRegistry | None = None,
               transaction_overrides: Mapping[UUID, ObservedRatio] | None = None) -> tuple[ConversionGraph, dict]:
    """RLS-scoped configuration; posting holds the same item lock as editors."""
    if registry is not None:
        return registry.graph(db, item, batch_id, transaction_overrides)
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
                          registry: OperationUnitRegistry | None = None,
                          transaction_overrides: Mapping[UUID, ObservedRatio] | None = None) -> QuantityConversion:
    graph, allowed = item_graph(db, item, batch_id=batch_id, registry=registry, transaction_overrides=transaction_overrides)
    source = unit_id or item.primary_unit_id
    if context not in ("purchase", "sale", "inventory", "production"):
        raise HTTPException(400, "زمینهٔ تبدیل واحد نامعتبر است")
    row = allowed.get(source)
    if row is None or not getattr(row, context + "_allowed"):
        unit = resolve(db, source) if registry is None and source is not None else None
        name = registry.names.get(source, "نامشخص") if registry else unit.name if unit is not None else "نامشخص"
        raise HTTPException(400, f"واحد «{name}» برای این عملیاتِ «{item.name}» مجاز نیست؛ واحد مجاز کالا را انتخاب کنید")
    try:
        result = graph.convert(qty, source, item.primary_unit_id, decimal_allowed=row.decimal_allowed)
        base = allowed.get(item.primary_unit_id)
        if base is None or not base.inventory_allowed:
            raise ValueError("واحد پایهٔ کالا برای انبار فعال نیست")
        if not base.decimal_allowed and result.target_qty != result.target_qty.to_integral_value():
            raise ValueError("مقدار تبدیل‌شدهٔ واحد پایه باید عدد صحیح باشد؛ مقدار یا نسبت را اصلاح کنید")
        return replace(result, source_unit_name=registry.names[source] if registry else resolve(db, source).name,
                       target_unit_name=registry.names[item.primary_unit_id] if registry else resolve(db, item.primary_unit_id).name)
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


def initialize_pending_items(db: Session) -> None:
    """Give every new ORM item a base membership before its first INSERT.

    This is called by the existing tenant before-flush hook. It never flushes,
    and resolves all requested names in one query for imports and catalog pulls.
    """
    from app.models.item_units import ItemUnit, ItemUnitConversion
    pending = [item for item in db.new if isinstance(item, Item)]
    if not pending:
        return
    from app.tenant_context import require_session_tenant
    tenant_id = require_session_tenant(db)
    units_by_name = {}
    units_by_id = {}
    for unit in db.new:
        if isinstance(unit, UnitOfMeasure):
            unit.id = unit.id or uuid4()
            unit.tenant_id = unit.tenant_id or tenant_id
            units_by_name[(unit.tenant_id, unit.name)] = unit
            units_by_id[unit.id] = unit
    names = {(item.unit or "عدد").strip() or "عدد" for item in pending if item.primary_unit_id is None}
    ids = {uid for item in pending for uid in (item.primary_unit_id, item.secondary_unit_id) if uid}
    with db.no_autoflush:
        for unit in db.query(UnitOfMeasure).filter(UnitOfMeasure.tenant_id == tenant_id,
            (UnitOfMeasure.name.in_(names)) | (UnitOfMeasure.id.in_(ids))).all():
            units_by_name[(unit.tenant_id, unit.name)] = unit
            units_by_id[unit.id] = unit
    memberships = {(row.tenant_id or tenant_id, row.item_id, row.unit_id)
        for row in db.new if isinstance(row, ItemUnit)}
    member_rows = {(row.item_id, row.unit_id): row for row in db.new if isinstance(row, ItemUnit)}
    rules = {(row.item_id, row.from_unit_id, row.to_unit_id)
        for row in db.new if isinstance(row, ItemUnitConversion)}
    for item in pending:
        item.id = item.id or uuid4()
        item.tenant_id = item.tenant_id or tenant_id
        if item.tenant_id != tenant_id:
            raise HTTPException(400, "کالای جدید به شرکت جاری تعلق ندارد")
        if item.primary_unit_id is None:
            name = (item.unit or "عدد").strip() or "عدد"
            unit = units_by_name.get((tenant_id, name))
            if unit is None:
                unit = UnitOfMeasure(id=uuid4(), tenant_id=tenant_id, name=name)
                db.add(unit); units_by_name[(tenant_id, name)] = unit; units_by_id[unit.id] = unit
            item.primary_unit_id = unit.id
        primary = units_by_id.get(item.primary_unit_id)
        if primary is not None and primary.tenant_id == tenant_id:
            item.primary_unit = primary
            item.unit = primary.name
        for unit_id in (item.primary_unit_id, item.secondary_unit_id):
            key = (tenant_id, item.id, unit_id)
            if unit_id and key not in memberships:
                member = ItemUnit(tenant_id=tenant_id, item_id=item.id, unit_id=unit_id, item=item)
                if unit_id in units_by_id:
                    member.unit = units_by_id[unit_id]
                db.add(member)
                member_rows[(item.id, unit_id)] = member
                memberships.add(key)
        if item.secondary_unit_id is not None and item.secondary_unit_id != item.primary_unit_id:
            mode = item.conversion_mode or "fixed"
            factor = exact_decimal(item.conversion_factor or 0) if mode == "fixed" else None
            key = (item.id, item.secondary_unit_id, item.primary_unit_id)
            if key not in rules and (mode == "variable" or (factor is not None and factor > 0)):
                db.add(ItemUnitConversion(tenant_id=tenant_id, item_id=item.id,
                    from_unit_id=item.secondary_unit_id, to_unit_id=item.primary_unit_id,
                    mode=mode, factor=factor,
                    from_membership=member_rows[(item.id, item.secondary_unit_id)],
                    to_membership=member_rows[(item.id, item.primary_unit_id)]))
                rules.add(key)


def normalize_backup_item_units(tables: dict) -> dict:
    """Normalize pre-registry backup items before any existing data is deleted."""
    result = dict(tables)
    items = [dict(row) for row in tables.get("items", [])]
    unit_rows = [dict(row) for row in tables.get("units_of_measure", [])]
    members = [dict(row) for row in tables.get("item_units", [])]
    rules = [dict(row) for row in tables.get("item_unit_conversions", [])]
    by_id = {str(row["id"]): row for row in unit_rows}
    by_name = {(str(row.get("tenant_id", "")), row["name"]): row for row in unit_rows}
    member_keys = {(str(row["item_id"]), str(row["unit_id"])): row for row in members}
    rule_keys = {(str(row["item_id"]), str(row["from_unit_id"]), str(row["to_unit_id"])) for row in rules}
    for item in items:
        tenant = str(item.get("tenant_id", ""))
        if not item.get("primary_unit_id"):
            name = (item.get("unit") or "عدد").strip() or "عدد"
            unit = by_name.get((tenant, name))
            if unit is None:
                unit = {"id": str(uuid4()), "tenant_id": item.get("tenant_id"), "name": name}
                unit_rows.append(unit); by_name[(tenant, name)] = unit; by_id[unit["id"]] = unit
            item["primary_unit_id"] = unit["id"]
        primary = by_id.get(str(item["primary_unit_id"]))
        if primary is None or str(primary.get("tenant_id", "")) != tenant:
            raise HTTPException(400, "واحد پایهٔ کالا در پشتیبان معتبر نیست")
        item["unit"] = primary["name"]
        if item.get("secondary_unit_id") == item["primary_unit_id"]:
            raise HTTPException(400, "واحد پایه و فرعی پشتیبان یکسان‌اند")
        for uid in (item["primary_unit_id"], item.get("secondary_unit_id")):
            if uid is None:
                continue
            unit = by_id.get(str(uid))
            if unit is None or str(unit.get("tenant_id", "")) != tenant:
                raise HTTPException(400, "واحد کالا در پشتیبان به همان شرکت تعلق ندارد")
            key = (str(item["id"]), str(uid))
            member = member_keys.get(key)
            if member is None:
                member = {"id": str(uuid4()), "tenant_id": item.get("tenant_id"),
                    "item_id": item["id"], "unit_id": uid}
                members.append(member); member_keys[key] = member
            if uid == item["primary_unit_id"] and (member.get("is_active") is False or
                member.get("inventory_allowed") is False or unit.get("is_active") is False):
                raise HTTPException(400, "واحد پایهٔ پشتیبان باید برای موجودی فعال باشد")
        secondary = item.get("secondary_unit_id")
        key = (str(item["id"]), str(secondary), str(item["primary_unit_id"]))
        if secondary and key not in rule_keys:
            mode = item.get("conversion_mode") or "fixed"
            try:
                factor = exact_decimal(str(item.get("conversion_factor") or 0)) if mode == "fixed" else None
            except (ValueError, ArithmeticError) as exc:
                raise HTTPException(400, "نسبت تبدیل قدیمی پشتیبان معتبر نیست") from exc
            if mode not in ("fixed", "variable") or (mode == "fixed" and factor <= 0):
                raise HTTPException(400, "نسبت تبدیل قدیمی پشتیبان معتبر نیست")
            rules.append({"id": str(uuid4()), "tenant_id": item.get("tenant_id"), "item_id": item["id"],
                "from_unit_id": secondary, "to_unit_id": item["primary_unit_id"], "mode": mode,
                "factor": str(factor) if factor is not None else None})
            rule_keys.add(key)
    if items:
        result.update(items=items, units_of_measure=unit_rows, item_units=members, item_unit_conversions=rules)
    return result


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
    result["factor"] = format(row.factor, "f") if row.factor is not None else None
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
    return {"rule_id": row.rule_id, "from_qty": format(row.from_qty, "f"), "to_qty": format(row.to_qty, "f")}


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


def convert_transaction(db: Session, item: Item, qty: Decimal, unit_id: UUID | None = None, *,
                        context: str = "inventory", batch_id: UUID | None = None,
                        registry: OperationUnitRegistry | None = None,
                        observations=()) -> QuantityConversion:
    """One posting entry point for legacy-created items and explicit observations."""
    from app.models.item_units import ItemUnit
    if registry is None:
        db.query(Item).filter(Item.id == item.id).with_for_update().one()
        if not db.query(ItemUnit.id).filter_by(item_id=item.id, tenant_id=item.tenant_id).first():
            configure_legacy(db, item)
    else:
        registry.assert_current(db, item)
    overrides = {row.rule_id: ObservedRatio(row.from_qty, row.to_qty) for row in observations}
    if len(overrides) != len(observations):
        raise HTTPException(400, "برای یک قاعده دو نسبت واقعی نفرستید؛ نسبت درست را انتخاب کنید")
    return convert_item_quantity(db, item, qty, unit_id, context=context,
                                 batch_id=batch_id, registry=registry, transaction_overrides=overrides)


def scale_document_conversion(original: QuantityConversion, scale: Fraction) -> QuantityConversion:
    """Scale a frozen recipe/output while retaining its historical conversion path."""
    if scale <= 0:
        raise ValueError("مقیاس تولید باید مثبت باشد")
    source = rounded_quantity(Fraction(original.source_qty) * scale)
    target = rounded_quantity(Fraction(original.target_qty) * scale)
    return replace(original, source_qty=source, target_qty=target,
        rounding_adjustment=target - rounded_quantity(Fraction(source) * original.ratio))


def snapshot_fields(conversion: QuantityConversion, *, commercial: bool = False) -> dict:
    snapshot = conversion.snapshot()
    snapshot["source"] = "transaction"
    result = {"entered_qty": conversion.source_qty, "entered_unit_id": conversion.source_unit_id,
              "base_unit_id": conversion.target_unit_id, "unit_conversion_snapshot": snapshot}
    if commercial:
        result["base_qty"] = conversion.target_qty
    return result


def movement_snapshot_fields(conversion: QuantityConversion, signed_base_qty: Decimal) -> dict:
    signed = exact_decimal(signed_base_qty)
    if abs(signed) == abs(conversion.target_qty):
        direction = signed / conversion.target_qty
        moved = replace(conversion, source_qty=conversion.source_qty * direction, target_qty=signed,
                        rounding_adjustment=conversion.rounding_adjustment * direction)
    else:
        # A split stores exact base quantity, with its whole document conversion as provenance.
        moved = QuantityConversion(signed, conversion.target_unit_id, signed, conversion.target_unit_id,
            Fraction(1), (), conversion.target_unit_name, conversion.target_unit_name)
    result = snapshot_fields(moved)
    if abs(signed) != abs(conversion.target_qty):
        result["unit_conversion_snapshot"]["document_conversion"] = conversion.snapshot()
        result["unit_conversion_snapshot"]["source"] = "allocated_base"
    return result


def negated_snapshot_fields(move) -> dict:
    from copy import deepcopy
    snapshot = deepcopy(move.unit_conversion_snapshot)
    if snapshot is not None:
        for key in ("source_qty", "target_qty", "rounding_adjustment"):
            if snapshot.get(key) is not None:
                snapshot[key] = format(-exact_decimal(snapshot[key]), "f")
        snapshot["source"] = "void"
    return {"entered_qty": -move.entered_qty if move.entered_qty is not None else None,
            "entered_unit_id": move.entered_unit_id, "base_unit_id": move.base_unit_id,
            "unit_conversion_snapshot": snapshot}


def to_primary(db: Session, item: Item, qty: Decimal, unit_id: UUID | None) -> Decimal:
    """Compatibility entry point delegates to the exact graph, never a second formula."""
    return convert_transaction(db, item, qty, unit_id).target_qty


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
