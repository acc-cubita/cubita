"""INV-02 numerical contracts; no database or installation is touched."""
from decimal import Decimal, localcontext
from fractions import Fraction
from uuid import UUID, uuid4

import pytest

from app.services.units import ConversionGraph, ConversionRule, ObservedRatio, historical_return_quantity, rounded_quantity


def fixed(a, b, factor, **kwargs):
    return ConversionRule(uuid4(), a, b, factor=Decimal(factor), **kwargs)


def test_frozen_integer_policy_survives_scaling_and_historical_return():
    from fastapi import HTTPException
    from app.services.units import QuantityConversion, convert_frozen_quantity, historical_return_conversion, conversion_from_snapshot
    source, base = uuid4(), uuid4()
    original = QuantityConversion(Decimal(2), source, Decimal(48), base, Fraction(24), (),
                                  "کارتن", "عدد", source_decimal_allowed=False,
                                  target_decimal_allowed=False)
    restored = conversion_from_snapshot(original.snapshot())
    assert convert_frozen_quantity(restored, Decimal(1)).target_qty == 24
    assert historical_return_conversion(restored, Decimal(1), source).target_qty == 24
    for quantity, selected_unit in [(Decimal('0.5'), source), (Decimal('0.5'), base)]:
        with pytest.raises(ValueError):
            historical_return_conversion(restored, quantity, selected_unit)
    with pytest.raises(HTTPException):
        convert_frozen_quantity(restored, Decimal('0.5'))


def test_pallet_carton_pack_piece_and_reverse_are_exact():
    pallet, carton, pack, piece = [UUID(int=i) for i in range(1, 5)]
    graph = ConversionGraph([pallet, carton, pack, piece], [fixed(pallet, carton, 40), fixed(carton, pack, 12), fixed(pack, piece, 6)])
    result = graph.convert(Decimal(1), pallet, piece)
    assert result.target_qty == 2880
    assert len(result.path) == 3
    assert graph.convert(Decimal(2880), piece, pallet).target_qty == 1
    assert graph.convert(Decimal(2), carton, piece).target_qty == 144


def test_reverse_uses_rational_factor_before_rounding():
    carton, piece = uuid4(), uuid4()
    graph = ConversionGraph([carton, piece], [fixed(carton, piece, 24)])
    result = graph.convert(Decimal(1), piece, carton)
    assert result.ratio == Fraction(1, 24)
    assert result.target_qty == Decimal('0.04166667')
    assert result.snapshot()['denominator'] == '24'


def test_actual_purchase_36kg_150m_and_transaction_precedence():
    kg, meter = uuid4(), uuid4()
    rule = ConversionRule(uuid4(), kg, meter, mode='variable')
    graph = ConversionGraph([kg, meter], [rule],
        batch_overrides={rule.id: ObservedRatio(Decimal(1), Decimal('3.8'))},
        transaction_overrides={rule.id: ObservedRatio(Decimal(36), Decimal(150))})
    result = graph.convert(Decimal(36), kg, meter)
    assert result.target_qty == 150
    assert result.ratio == Fraction(25, 6)
    assert result.path[0].source == 'transaction'
    assert graph.convert(Decimal(150), meter, kg).target_qty == 36


def test_batch_ratios_remain_distinct():
    kg, meter = uuid4(), uuid4()
    rule = ConversionRule(uuid4(), kg, meter, mode='variable')
    results = [ConversionGraph([kg, meter], [rule], batch_overrides={rule.id: ObservedRatio(Decimal(1), Decimal(ratio))})
        .convert(Decimal(10), kg, meter).target_qty for ratio in ('3.8', '4.1')]
    assert results == [Decimal(38), Decimal(41)]


def test_variable_without_observation_never_guesses():
    a, b = uuid4(), uuid4()
    graph = ConversionGraph([a, b], [ConversionRule(uuid4(), a, b, mode='variable')])
    with pytest.raises(ValueError, match='مقدار واقعی'):
        graph.convert(Decimal(1), a, b)


@pytest.mark.parametrize('factor', ['0', '-2', 'NaN', 'Infinity'])
def test_invalid_fixed_factor(factor):
    a, b = uuid4(), uuid4()
    with pytest.raises(ValueError):
        ConversionGraph([a, b], [fixed(a, b, factor)])


@pytest.mark.parametrize('direct', ['5', '6.000000000001'])
def test_inconsistent_cycle_is_rejected_without_float_tolerance(direct):
    a, b, c = uuid4(), uuid4(), uuid4()
    with pytest.raises(ValueError, match='ناسازگار'):
        ConversionGraph([a, b, c], [fixed(a, b, 2), fixed(b, c, 3), fixed(a, c, direct)])


def test_consistent_multiple_paths_and_order_independence():
    a, b, c = [UUID(int=i) for i in range(1, 4)]
    rules = [fixed(a, b, 2), fixed(b, c, 3), fixed(a, c, 6)]
    first = ConversionGraph([a, b, c], rules).convert(Decimal(2), a, c)
    second = ConversionGraph([c, b, a], reversed(rules)).convert(Decimal(2), a, c)
    assert first == second
    assert first.target_qty == 12
    assert len(first.path) == 1


def test_contextual_ratio_cannot_introduce_conflicting_cycle():
    a, b, c = uuid4(), uuid4(), uuid4()
    rule = ConversionRule(uuid4(), a, c, mode='variable')
    with pytest.raises(ValueError, match='ناسازگار'):
        ConversionGraph([a, b, c], [fixed(a, b, 2), fixed(b, c, 3), rule],
                        transaction_overrides={rule.id: ObservedRatio(Decimal(1), Decimal(5))})


def test_fixed_or_unknown_rule_cannot_be_overridden():
    a, b = uuid4(), uuid4()
    rule = fixed(a, b, 2)
    for rule_id in (rule.id, uuid4()):
        with pytest.raises(ValueError):
            ConversionGraph([a, b], [rule], transaction_overrides={rule_id: ObservedRatio(Decimal(1), Decimal(3))})


def test_self_conversion_and_decimal_policy():
    a = uuid4()
    graph = ConversionGraph([a], [])
    assert graph.convert(Decimal(3), a, a).ratio == 1
    assert graph.convert(Decimal(3), a, a).path == ()
    with pytest.raises(ValueError, match='اعشاری'):
        graph.convert(Decimal('0.5'), a, a, decimal_allowed=False)


def test_inactive_or_foreign_unit_and_disconnected_path():
    a, b = uuid4(), uuid4()
    graph = ConversionGraph([a, b], [])
    with pytest.raises(ValueError):
        graph.convert(Decimal(1), a, uuid4())
    with pytest.raises(ValueError):
        graph.convert(Decimal(1), a, b)
    with pytest.raises(ValueError):
        ConversionGraph([a], [fixed(a, b, 2)])


def test_snapshot_does_not_change_when_current_rule_changes():
    carton, piece = uuid4(), uuid4()
    rule = fixed(carton, piece, 24)
    snapshot = ConversionGraph([carton, piece], [rule]).convert(Decimal(2), carton, piece).snapshot()
    ConversionGraph([carton, piece], [fixed(carton, piece, 30)])
    assert historical_return_quantity(snapshot, Decimal(1)) == 24
    assert snapshot['target_qty'] == '48.00000000'


def test_final_return_closes_rounding_residual():
    source, target = uuid4(), uuid4()
    graph = ConversionGraph([source, target], [fixed(target, source, 3)])
    snapshot = graph.convert(Decimal(3), source, target).snapshot()
    first = historical_return_quantity(snapshot, Decimal(1))
    second = historical_return_quantity(snapshot, Decimal(1), returned_entered=Decimal(1), returned_base=first)
    third = historical_return_quantity(snapshot, Decimal(1), returned_entered=Decimal(2), returned_base=first+second)
    assert [first, second, third] == [Decimal('0.33333333'), Decimal('0.33333333'), Decimal('0.33333334')]
    assert first + second + third == 1
    with pytest.raises(ValueError):
        historical_return_quantity(snapshot, Decimal(4))


def test_rounding_is_independent_of_callers_decimal_context_and_rejects_loss():
    with localcontext() as ctx:
        ctx.prec = 4
        assert rounded_quantity(Fraction(123456789, 10)) == Decimal('12345678.90000000')
    assert rounded_quantity(Decimal('0.000000015')) == Decimal('0.00000002')
    for invalid in (Decimal('0.0000000001'), Decimal('10000000000000000')):
        with pytest.raises(ValueError):
            rounded_quantity(invalid)


def test_float_and_boolean_quantities_are_rejected():
    a = uuid4()
    graph = ConversionGraph([a], [])
    for value in (0.1, True):
        with pytest.raises(ValueError):
            graph.convert(value, a, a)


@pytest.mark.parametrize('quantity,factor,message', [
    ('0.000000001', '1000', 'هشت رقم'),
    ('10000000000000000', '0.00000001', 'ظرفیت'),
])
def test_source_quantity_must_fit_storage_even_when_converted_quantity_fits(quantity, factor, message):
    source, target = uuid4(), uuid4()
    graph = ConversionGraph([source, target], [fixed(source, target, factor)])
    with pytest.raises(ValueError, match=message):
        graph.convert(Decimal(quantity), source, target)
