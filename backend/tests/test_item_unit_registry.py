from decimal import Decimal
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from app.models.item_units import ItemUnit, ItemUnitConversion
from app.models.inventory import UnitOfMeasure, Warehouse
from app.models.advanced_inventory import StockBatch
from app.schemas.item_units import ObservedRatioIn
from app.services import units
from app.seed import provision_tenant
from app.tenant_context import tenant_scope
from tests.factories import make_item


def configured(db, variable=False):
    primary=units.get_or_create(db,'متر' if variable else 'عدد')
    secondary=units.get_or_create(db,'کیلوگرم' if variable else 'کارتن')
    item=make_item(db,primary_unit_id=primary.id,secondary_unit_id=secondary.id,
        conversion_mode='variable' if variable else 'fixed',conversion_factor=0 if variable else 24)
    units.configure_legacy(db,item)
    return item,primary,secondary


def test_preview_uses_legacy_registry_and_extra_chain(db,user,client):
    item,piece,carton=configured(db)
    pallet=units.get_or_create(db,'پالت')
    assert client.post(f'/api/items/{item.id}/units',json={'unit_id':str(pallet.id)}).status_code==201
    response=client.post(f'/api/items/{item.id}/unit-conversions',json={'from_unit_id':str(pallet.id),'to_unit_id':str(carton.id),'factor':'40'})
    assert response.status_code==201,response.text
    response=client.post(f'/api/items/{item.id}/convert-quantity',json={'qty':'2','unit_id':str(pallet.id),'context':'sale'})
    assert response.status_code==200,response.text
    assert response.json()['target_qty']=='1920.00000000'
    assert len(response.json()['path'])==2


def test_context_permissions_and_decimal_policy(db,user,client):
    item,piece,carton=configured(db)
    response=client.patch(f'/api/items/{item.id}/units/{carton.id}',json={'sale_allowed':False,'decimal_allowed':False})
    assert response.status_code==200,response.text
    endpoint=f'/api/items/{item.id}/convert-quantity'
    assert client.post(endpoint,json={'qty':'1','unit_id':str(carton.id),'context':'sale'}).status_code==400
    assert client.post(endpoint,json={'qty':'0.5','unit_id':str(carton.id),'context':'purchase'}).status_code==400
    assert client.post(endpoint,json={'qty':'1','unit_id':str(carton.id),'context':'purchase'}).status_code==200
    assert client.patch(f'/api/items/{item.id}/units/{piece.id}',json={'is_active':False}).status_code==400


def test_preview_rejects_float_contract(db,user,client):
    item,_,carton=configured(db)
    assert client.post(f'/api/items/{item.id}/convert-quantity',json={'qty':0.1,'unit_id':str(carton.id)}).status_code==422


def test_version_changes_and_invalid_cycle_roll_back(db,user,client):
    item,piece,carton=configured(db)
    rule=db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    response=client.put(f'/api/items/{item.id}/unit-conversions/{rule.id}',json={'from_unit_id':str(carton.id),'to_unit_id':str(piece.id),'factor':'30'})
    assert response.status_code==200,response.text
    assert response.json()['version']==2
    assert client.post(f'/api/items/{item.id}/unit-conversions',json={'from_unit_id':str(piece.id),'to_unit_id':str(carton.id),'factor':'2'}).status_code==400
    assert db.query(ItemUnitConversion).filter_by(item_id=item.id).count()==1


def test_observed_batch_ratio_and_transaction_precedence(db,user,client):
    item,meter,kg=configured(db,variable=True)
    rule=db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    warehouse=db.query(Warehouse).first()
    batch=StockBatch(item_id=item.id,warehouse_id=warehouse.id,batch_number='VARIABLE-TEST',qty=150,received_qty=150,
        received_date=date.today(),created_by_id=user.id)
    db.add(batch);db.flush()
    result=units.configure_batch_ratio(db,item,batch.id,ObservedRatioIn(rule_id=rule.id,from_qty='36',to_qty='150'),user.id)
    assert Decimal(result['from_qty'])==36
    assert units.convert_item_quantity(db,item,Decimal(36),kg.id,batch_id=batch.id).target_qty==150
    assert units.convert_item_quantity(db,item,Decimal(36),kg.id,batch_id=batch.id,
        transaction_overrides={rule.id:units.ObservedRatio(Decimal(36),Decimal(144))}).target_qty==144


def test_foreign_tenant_unit_is_rejected_by_api_and_composite_fk(db,user,client):
    item,_,_=configured(db)
    # Provisioning binds its new tenant; restore the authenticated tenant afterwards.
    with tenant_scope(db,item.tenant_id):
        other=provision_tenant(db,name='Other UOM tenant',slug=f'uom-{uuid4().hex[:12]}',owner_email=f'{uuid4().hex}@example.invalid',owner_password='TestOnly!2026')
        with tenant_scope(db,other.id):
            foreign=db.query(UnitOfMeasure).filter_by(name='پالت').one()
            foreign_id=foreign.id
    assert client.post(f'/api/items/{item.id}/units',json={'unit_id':str(foreign_id)}).status_code==404
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(ItemUnit(item_id=item.id,tenant_id=item.tenant_id,unit_id=foreign_id))
            db.flush()


def test_base_unit_is_unique_derived_property(db,user,client):
    item,_,_=configured(db)
    response=client.get(f'/api/items/{item.id}/units')
    assert response.status_code==200,response.text
    assert sum(row['is_base'] for row in response.json())==1


def test_base_integer_policy_applies_to_converted_quantity(db,user,client):
    item,piece,carton=configured(db)
    assert client.patch(f'/api/items/{item.id}/units/{piece.id}',json={'decimal_allowed':False}).status_code==200
    response=client.post(f'/api/items/{item.id}/convert-quantity',json={'qty':'0.01','unit_id':str(carton.id)})
    assert response.status_code==400,response.text


def test_legacy_secondary_edit_retires_old_rule(db,user,client):
    item,piece,carton=configured(db)
    pallet=units.get_or_create(db,'پالت')
    response=client.patch(f'/api/items/{item.id}',json={'secondary_unit_id':str(pallet.id),'conversion_factor':'960'})
    assert response.status_code==200,response.text
    old=db.query(ItemUnitConversion).filter_by(item_id=item.id,from_unit_id=carton.id).one()
    assert not old.is_active
    assert units.convert_item_quantity(db,item,Decimal(2),pallet.id).target_qty==1920


def test_base_change_is_blocked_even_when_history_net_is_zero(db,user,client):
    from app.models.inventory import StockLedger
    item,piece,_=configured(db)
    meter=units.get_or_create(db,'متر')
    warehouse=db.query(Warehouse).first()
    for qty in (Decimal('1.00000001'), Decimal('-1.00000001')):
        db.add(StockLedger(item_id=item.id,warehouse_id=warehouse.id,qty=qty,unit_cost=1,source_type='uom-test'))
    db.flush()
    response=client.patch(f'/api/items/{item.id}',json={'primary_unit_id':str(meter.id)})
    assert response.status_code==409,response.text
    assert item.primary_unit_id==piece.id
    db.expire_all()
    assert sum((m.qty for m in db.query(StockLedger).filter_by(item_id=item.id)),Decimal(0))==0
    assert db.query(StockLedger).filter_by(item_id=item.id).first().qty.as_tuple().exponent==-8


def test_extra_active_item_unit_blocks_master_deactivation(db,user,client):
    from fastapi import HTTPException
    item,_,_=configured(db)
    pallet=units.get_or_create(db,'پالت')
    assert client.post(f'/api/items/{item.id}/units',json={'unit_id':str(pallet.id)}).status_code==201
    with pytest.raises(HTTPException) as exc:
        units.assert_can_deactivate(db,pallet)
    assert exc.value.status_code==409


def test_twelve_digit_factor_survives_registry_and_legacy_projection(db,user,client):
    item,piece,carton=configured(db)
    rule=db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    response=client.put(f'/api/items/{item.id}/unit-conversions/{rule.id}',json={'from_unit_id':str(carton.id),'to_unit_id':str(piece.id),'factor':'1.000000000001'})
    assert response.status_code==200,response.text
    assert response.json()['factor']=='1.000000000001'
    db.expire_all()
    assert item.conversion_factor==Decimal('1.000000000001')
    assert rule.factor==item.conversion_factor
