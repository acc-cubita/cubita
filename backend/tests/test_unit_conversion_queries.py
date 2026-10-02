"""Benchmark a 1,000-line operation, including distinct item registries."""
from decimal import Decimal
from time import perf_counter

from sqlalchemy import event
import pytest
from fastapi import HTTPException
from uuid import uuid4
from app.tenant_context import tenant_scope

from app.models.inventory import Item
from app.models.item_units import ItemUnit, ItemUnitConversion
from app.services import units


def _registries(db, count=1000):
    piece = units.get_or_create(db, 'عدد')
    carton = units.get_or_create(db, 'کارتن')
    items = [Item(sku=f'PERF-{index}', name=f'کالای {index}', unit='عدد', primary_unit_id=piece.id,
        secondary_unit_id=carton.id, conversion_factor=Decimal('24')) for index in range(count)]
    db.add_all(items); db.flush()
    for item in items:
        db.add_all([ItemUnit(tenant_id=item.tenant_id, item_id=item.id, unit_id=unit.id)
            for unit in (piece, carton)])
    db.flush()
    db.add_all([ItemUnitConversion(tenant_id=item.tenant_id, item_id=item.id,
        from_unit_id=carton.id, to_unit_id=piece.id, factor=Decimal('24')) for item in items])
    db.flush()
    return items, carton


def _measure(db, operation):
    queries = 0
    def count(_conn, _cursor, statement, _parameters, _context, _executemany):
        nonlocal queries
        if statement.lstrip().upper().startswith('SELECT'):
            queries += 1
    engine = db.get_bind()
    event.listen(engine, 'before_cursor_execute', count)
    start = perf_counter()
    try:
        results = operation()
    finally:
        elapsed = perf_counter() - start
        event.remove(engine, 'before_cursor_execute', count)
    assert len(results) == 1000 and all(r.target_qty == Decimal('29.62962936') for r in results)
    return queries, elapsed


def test_operation_query_baseline(db):
    items, carton = _registries(db)
    queries, elapsed = _measure(db, lambda: [units.convert_item_quantity(db, item,
        Decimal('1.23456789'), carton.id, context='sale') for item in items])
    print(f'unit-baseline: lines=1000 SELECTs={queries} seconds={elapsed:.3f}')


def test_operation_registry_has_bounded_queries(db):
    items, carton = _registries(db)
    def convert():
        registry = units.OperationUnitRegistry(db, items)
        return [units.convert_transaction(db, item, Decimal('1.23456789'), carton.id,
            context='sale', registry=registry) for item in items]
    queries, elapsed = _measure(db, convert)
    assert queries == 3
    print(f'unit-preloaded: lines=1000 SELECTs={queries} seconds={elapsed:.3f}')


def test_operation_registry_rejects_changed_tenant_and_transaction(db):
    items, carton = _registries(db, count=1)
    registry = units.OperationUnitRegistry(db, items)
    with tenant_scope(db, uuid4()):
        with pytest.raises(HTTPException, match='همین عملیات'):
            units.convert_transaction(db, items[0], Decimal(1), carton.id, registry=registry)
    db.commit()
    with pytest.raises(HTTPException, match='همین عملیات'):
        units.convert_transaction(db, items[0], Decimal(1), carton.id, registry=registry)


def test_next_operation_loads_new_rule_version(db):
    items, carton = _registries(db, count=1)
    first = units.OperationUnitRegistry(db, items)
    old = units.convert_transaction(db, items[0], Decimal(1), carton.id, registry=first)
    rule = db.query(ItemUnitConversion).filter_by(item_id=items[0].id).one()
    rule.factor, rule.version = Decimal(30), 2
    db.flush()
    second = units.OperationUnitRegistry(db, items)
    new = units.convert_transaction(db, items[0], Decimal(1), carton.id, registry=second)
    assert old.target_qty == 24 and old.path[0].version == 1
    assert new.target_qty == 30 and new.path[0].version == 2
