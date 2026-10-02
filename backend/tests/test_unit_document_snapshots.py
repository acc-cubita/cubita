from datetime import date
from decimal import Decimal

from app.models.accounting import JournalLine
from app.models.inventory import StockLedger
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, DirectWarehouseIssueIn, WarehouseIssueLineIn
from app.schemas.issue_returns import IssueReturnIn, IssueReturnLineIn
from app.schemas.item_units import ConversionRuleIn, ObservedRatioIn
from app.services.inventory import post_purchase_invoice, get_stock_qty
from app.services.warehouse_issues import create_direct_warehouse_issue
from app.services.issue_returns import create_issue_return
from app.services import units
from app.models.item_units import ItemUnitConversion
from tests.factories import main_warehouse, make_contact
from tests.test_item_unit_registry import configured


def seed_stock(db,user,item,qty):
    post_purchase_invoice(db,PurchaseInvoiceIn(invoice_date=date.today(),warehouse_id=main_warehouse(db).id,
        lines=[PurchaseInvoiceLineIn(item_id=item.id,qty=Decimal(qty),unit_cost=Decimal(100))]),user)


def issue(db,user,item,qty,unit,observations=()):
    return create_direct_warehouse_issue(db,DirectWarehouseIssueIn(issue_date=date.today(),issue_type='sale',
        warehouse_id=main_warehouse(db).id,receiver_id=make_contact(db).id,
        lines=[WarehouseIssueLineIn(item_id=item.id,qty=Decimal(qty),unit_id=unit.id,observations=list(observations))]),user)


def return_slice(db,user,source,qty,unit):
    result=create_issue_return(db,IssueReturnIn(return_date=date.today(),return_type='sale',warehouse_id=main_warehouse(db).id,deliverer_id=source.issue.receiver_id,
        lines=[IssueReturnLineIn(warehouse_issue_line_id=source.id,qty=Decimal(qty),unit_id=unit.id)]),user)
    journal=db.query(JournalLine).filter_by(entry_id=result.journal_entry_id).all()
    assert sum(l.debit for l in journal)==sum(l.credit for l in journal)
    return result


def test_direct_issue_return_freezes_factor_and_unit_name(db,user):
    item,piece,carton=configured(db)
    seed_stock(db,user,item,'100')
    original=issue(db,user,item,'2',carton).lines[0]
    assert original.qty==48 and original.entered_qty==2
    assert original.unit_conversion_snapshot['source_unit_name']=='کارتن'
    rule=db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    units.configure_rule(db,item,ConversionRuleIn(from_unit_id=carton.id,to_unit_id=piece.id,factor='30'),rule_id=rule.id)
    carton.name='کارتن تازه';carton.is_active=False;db.flush()
    first=return_slice(db,user,original,'1',carton).lines[0]
    second=return_slice(db,user,original,'1',carton).lines[0]
    assert first.qty==second.qty==24
    assert first.unit_conversion_snapshot['source_unit_name']=='کارتن'
    assert first.unit_conversion_snapshot['path'][0]['version']==1
    assert get_stock_qty(db,item.id,main_warehouse(db).id)==100
    out_move=db.query(StockLedger).filter_by(source_type='warehouse_issue',source_id=original.issue_id).one()
    assert out_move.entered_qty==-2 and out_move.qty==-48
    assert out_move.unit_conversion_snapshot['path'][0]['version']==1


def test_variable_transaction_return_closes_last_base_residual(db,user):
    item,meter,kg=configured(db,variable=True)
    seed_stock(db,user,item,'1')
    rule=db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    original=issue(db,user,item,'1',kg,[ObservedRatioIn(rule_id=rule.id,from_qty='3',to_qty='1')]).lines[0]
    assert original.qty==Decimal('0.33333333')
    assert original.unit_conversion_snapshot['numerator']=='1'
    assert original.unit_conversion_snapshot['denominator']=='3'
    returned=[return_slice(db,user,original,q,kg).lines[0].qty for q in ('0.25','0.25','0.5')]
    assert returned==[Decimal('0.08333333'),Decimal('0.08333333'),Decimal('0.16666667')]
    assert sum(returned)==original.qty
    assert get_stock_qty(db,item.id,main_warehouse(db).id)==1


def test_void_uses_original_entered_and_base_quantities_after_rule_change(db,user):
    from app.services.warehouse_issues import void_warehouse_issue
    item,piece,carton=configured(db)
    seed_stock(db,user,item,'100')
    document=issue(db,user,item,'2',carton)
    original=db.query(StockLedger).filter_by(source_type='warehouse_issue',source_id=document.id).one()
    original_snapshot=dict(original.unit_conversion_snapshot)
    rule=db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    units.configure_rule(db,item,ConversionRuleIn(from_unit_id=carton.id,to_unit_id=piece.id,factor='30'),rule_id=rule.id)
    void_warehouse_issue(db,document.id,reason='آزمون snapshot',user=user)
    inverse=db.query(StockLedger).filter_by(source_type='void',source_id=document.id).one()
    assert inverse.qty==48 and inverse.entered_qty==2
    assert inverse.unit_conversion_snapshot['path']==original_snapshot['path']
    assert Decimal(inverse.unit_conversion_snapshot['source_qty'])==2
    assert original.unit_conversion_snapshot==original_snapshot
    assert get_stock_qty(db,item.id,main_warehouse(db).id)==100


def test_purchase_commercial_price_uses_base_stock_and_cost(db, user):
    item, piece, carton = configured(db)
    invoice = post_purchase_invoice(db, PurchaseInvoiceIn(invoice_date=date.today(),
        warehouse_id=main_warehouse(db).id, lines=[PurchaseInvoiceLineIn(
            item_id=item.id, qty=Decimal('2'), unit_id=carton.id, unit_cost=Decimal('2400'))]), user)
    line = invoice.lines[0]
    assert line.qty == 2 and line.base_qty == 48 and line.unit_cost == 2400
    assert invoice.total_amount == 4800
    assert item.average_cost == 100
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == 48


def test_purchase_return_preserves_commercial_unit_after_rule_change(db, user):
    from app.schemas.returns import PurchaseReturnIn, PurchaseReturnLineIn
    from app.services.returns import post_purchase_return, get_purchase_returnable_summary
    item, piece, carton = configured(db)
    invoice = post_purchase_invoice(db, PurchaseInvoiceIn(invoice_date=date.today(),
        warehouse_id=main_warehouse(db).id, lines=[PurchaseInvoiceLineIn(item_id=item.id,
            qty=Decimal('2'), unit_id=carton.id, unit_cost=Decimal('2400'))]), user)
    original = invoice.lines[0]
    rule = db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    units.configure_rule(db, item, ConversionRuleIn(from_unit_id=carton.id,
        to_unit_id=piece.id, factor='30'), rule_id=rule.id)
    for _ in range(2):
        returned = post_purchase_return(db, PurchaseReturnIn(return_date=date.today(),
            purchase_invoice_id=invoice.id, lines=[PurchaseReturnLineIn(
                purchase_invoice_line_id=original.id, qty=Decimal('1'), unit_id=carton.id)]), user)
        line = returned.lines[0]
        assert line.qty == 1 and line.base_qty == 24 and line.unit_cost == 2400
        assert returned.total_amount == 2400
        assert line.unit_conversion_snapshot['path'][0]['version'] == 1
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == 0
    assert get_purchase_returnable_summary(db, invoice.id)[0]['remaining'] == 0
    move = db.query(StockLedger).filter_by(source_type='purchase_invoice', source_id=invoice.id).one()
    assert move.qty == 48 and move.entered_qty == 2 and move.unit_cost == 100


def test_partial_receipts_use_frozen_invoice_conversion(db, user):
    from app.schemas.invoices import WarehouseReceiptIn, WarehouseReceiptLineIn
    from app.services.warehouse_receipts import create_warehouse_receipt
    item, piece, carton = configured(db)
    supplier = make_contact(db)
    supplier.is_supplier = True
    db.flush()
    invoice = post_purchase_invoice(db, PurchaseInvoiceIn(invoice_date=date.today(),
        contact_id=supplier.id, lines=[PurchaseInvoiceLineIn(item_id=item.id,
            qty=Decimal('2'), unit_id=carton.id, unit_cost=Decimal('2400'))]), user)
    original = invoice.lines[0]
    rule = db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    units.configure_rule(db, item, ConversionRuleIn(from_unit_id=carton.id,
        to_unit_id=piece.id, factor='30'), rule_id=rule.id)
    carton.name = 'نام تازه'; carton.is_active = False; db.flush()
    for _ in range(2):
        receipt = create_warehouse_receipt(db, invoice.id, WarehouseReceiptIn(
            receipt_date=date.today(), warehouse_id=main_warehouse(db).id,
            lines=[WarehouseReceiptLineIn(purchase_invoice_line_id=original.id,
                qty=Decimal('1'), unit_id=carton.id)]), user)
        line = receipt.lines[0]
        assert line.qty == 24 and line.entered_qty == 1 and line.unit_cost == 100
        assert line.unit_conversion_snapshot['source_unit_name'] == 'کارتن'
        assert line.unit_conversion_snapshot['path'][0]['version'] == 1
        journal = db.query(JournalLine).filter_by(entry_id=receipt.journal_entry_id).all()
        assert sum(l.debit for l in journal) == sum(l.credit for l in journal) == 2400
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == 48
