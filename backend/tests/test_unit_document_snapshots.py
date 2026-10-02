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


def test_quotation_partial_invoices_keep_original_unit_and_factor(db, user):
    from app.schemas.quotations import SalesQuotationIn, SalesQuotationConvertIn
    from app.services import quotations
    item, piece, carton = configured(db)
    quote = quotations.create_quotation(db, SalesQuotationIn(quotation_date=date.today(),
        warehouse_id=main_warehouse(db).id, lines=[{'item_id': item.id, 'qty': '2',
            'unit_id': carton.id, 'unit_price': '2400'}]), user)
    line = quote.lines[0]
    assert line.qty == 2 and line.base_qty == 48 and line.unit_snapshot == 'کارتن'
    rule = db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    units.configure_rule(db, item, ConversionRuleIn(from_unit_id=carton.id,
        to_unit_id=piece.id, factor='30'), rule_id=rule.id)
    carton.name = 'کارتن تازه'; carton.is_active = False; db.flush()
    for remaining in (Decimal(1), Decimal(0)):
        invoice = quotations.convert_quotation_to_invoice(db, quote.id,
            SalesQuotationConvertIn(lines=[{'quotation_line_id': line.id, 'qty': '1'}]), user)
        assert invoice.lines[0].base_qty == 24 and invoice.lines[0].qty == 1
        assert invoice.lines[0].unit_price == 2400
        assert invoice.lines[0].unit_snapshot == 'کارتن'
        assert invoice.lines[0].unit_conversion_snapshot['path'][0]['version'] == 1
        assert line.remaining_invoiceable_qty == remaining
    assert quote.commercial_status == 'fully_invoiced'


def test_variable_quotation_partial_invoices_close_base_residual(db, user):
    from app.schemas.quotations import SalesQuotationIn, SalesQuotationConvertIn
    from app.services import quotations
    item, meter, kg = configured(db, variable=True)
    rule = db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    quote = quotations.create_quotation(db, SalesQuotationIn(quotation_date=date.today(),
        warehouse_id=main_warehouse(db).id, lines=[{'item_id': item.id, 'qty': '3',
            'unit_id': kg.id, 'unit_price': '100',
            'observations': [{'rule_id': rule.id, 'from_qty': '3', 'to_qty': '1'}]}]), user)
    quantities = []
    for _ in range(3):
        invoice = quotations.convert_quotation_to_invoice(db, quote.id,
            SalesQuotationConvertIn(lines=[{'quotation_line_id': quote.lines[0].id, 'qty': '1'}]), user)
        quantities.append(invoice.lines[0].base_qty)
    assert quantities == [Decimal('0.33333333'), Decimal('0.33333333'), Decimal('0.33333334')]
    assert quote.commercial_status == 'fully_invoiced'


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


def test_sales_invoice_and_return_use_frozen_commercial_quantity(db, user):
    from app.schemas.invoices import SalesInvoiceIn, SalesInvoiceLineIn
    from app.schemas.returns import SalesReturnIn, SalesReturnLineIn
    from app.services.inventory import post_sales_invoice
    from app.services.returns import post_sales_return, get_returnable_summary
    item, piece, carton = configured(db)
    seed_stock(db, user, item, '100')
    invoice = post_sales_invoice(db, SalesInvoiceIn(invoice_date=date.today(),
        warehouse_id=main_warehouse(db).id, lines=[SalesInvoiceLineIn(item_id=item.id,
            qty=Decimal('2'), unit_id=carton.id, unit_price=Decimal('4800'))]), user)
    original = invoice.lines[0]
    assert original.qty == 2 and original.base_qty == 48
    assert invoice.total_amount == 9600 and invoice.total_cost == 4800
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == 52
    rule = db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    units.configure_rule(db, item, ConversionRuleIn(from_unit_id=carton.id,
        to_unit_id=piece.id, factor='30'), rule_id=rule.id)
    carton.name = 'نام تازه'; carton.is_active = False; db.flush()
    for _ in range(2):
        returned = post_sales_return(db, SalesReturnIn(return_date=date.today(), sales_invoice_id=invoice.id,
            lines=[SalesReturnLineIn(sales_invoice_line_id=original.id, qty=Decimal('1'),
                unit_id=carton.id)]), user, physical=True)
        line = returned.lines[0]
        assert line.qty == 1 and line.base_qty == 24 and line.unit_price == 4800
        assert returned.total_amount == 4800 and returned.total_cost == 2400
        assert line.unit_conversion_snapshot['path'][0]['version'] == 1
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == 100
    assert get_returnable_summary(db, invoice.id)[0]['remaining'] == 0


def test_sales_partial_issues_close_frozen_variable_residual(db, user):
    from app.schemas.invoices import SalesInvoiceIn, SalesInvoiceLineIn, WarehouseIssueIn
    from app.services.inventory import post_sales_invoice
    from app.services.warehouse_issues import create_warehouse_issue
    item, meter, kg = configured(db, variable=True)
    seed_stock(db, user, item, '1')
    rule = db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    invoice = post_sales_invoice(db, SalesInvoiceIn(invoice_date=date.today(),
        lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal('1'), unit_id=kg.id,
            unit_price=Decimal('300'), observations=[ObservedRatioIn(rule_id=rule.id,
                from_qty='3', to_qty='1')])]), user, move_inventory=False)
    original = invoice.lines[0]
    actual = []
    for quantity in ('0.25', '0.25', '0.5'):
        document = create_warehouse_issue(db, invoice.id, WarehouseIssueIn(issue_date=date.today(),
            warehouse_id=main_warehouse(db).id, lines=[WarehouseIssueLineIn(
                sales_invoice_line_id=original.id, qty=Decimal(quantity), unit_id=kg.id)]), user)
        actual.append(document.lines[0].qty)
    assert actual == [Decimal('0.08333333'), Decimal('0.08333333'), Decimal('0.16666667')]
    assert sum(actual) == original.base_qty == Decimal('0.33333333')


def test_invoice_from_direct_issue_keeps_original_conversion(db, user):
    from app.schemas.invoices import SalesInvoiceIn, SalesInvoiceLineIn
    from app.services.warehouse_issues import post_sales_invoice_from_issue
    item, piece, carton = configured(db)
    seed_stock(db, user, item, '100')
    document = issue(db, user, item, '2', carton)
    source = document.lines[0]
    rule = db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    units.configure_rule(db, item, ConversionRuleIn(from_unit_id=carton.id,
        to_unit_id=piece.id, factor='30'), rule_id=rule.id)
    carton.is_active = False; db.flush()
    invoice = post_sales_invoice_from_issue(db, SalesInvoiceIn(invoice_date=date.today(),
        source_warehouse_issue_id=document.id, lines=[SalesInvoiceLineIn(item_id=item.id,
            source_issue_line_id=source.id, qty=Decimal('2'), unit_id=carton.id,
            unit_price=Decimal('4800'))]), user)
    assert invoice.lines[0].base_qty == 48
    assert invoice.lines[0].unit_conversion_snapshot['path'][0]['version'] == 1
    assert invoice.total_cost == 4800
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == 52


def test_transfer_posts_equal_base_quantities_and_void_preserves_units(db, user):
    from app.schemas.transfers import StockTransferIn, StockTransferLineIn
    from app.services.transfers import post_stock_transfer, void_stock_transfer
    from tests.factories import other_warehouse
    item, piece, carton = configured(db)
    seed_stock(db, user, item, '100')
    document = post_stock_transfer(db, StockTransferIn(transfer_date=date.today(),
        from_warehouse_id=main_warehouse(db).id, to_warehouse_id=other_warehouse(db).id,
        lines=[StockTransferLineIn(item_id=item.id, qty=Decimal('3'), unit_id=carton.id)]), user)
    assert document.lines[0].qty == 72 and document.lines[0].entered_qty == 3
    moves = db.query(StockLedger).filter_by(source_id=document.id).all()
    assert sorted(m.qty for m in moves) == [-72, 72]
    assert sorted(m.entered_qty for m in moves) == [-3, 3]
    rule = db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    units.configure_rule(db, item, ConversionRuleIn(from_unit_id=carton.id,
        to_unit_id=piece.id, factor='30'), rule_id=rule.id)
    void_stock_transfer(db, document.id, reason='آزمون تاریخی', user=user)
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == 100
    assert get_stock_qty(db, item.id, other_warehouse(db).id) == 0


def test_variable_purchase_batch_ratio_survives_transfer(db, user):
    from app.models.advanced_inventory import StockBatch
    from app.models.item_units import BatchUnitConversion
    from app.schemas.invoices import BatchAllocationIn
    from app.schemas.transfers import StockTransferIn, StockTransferLineIn
    from app.services.transfers import post_stock_transfer, void_stock_transfer
    from app.services.batches import on_hand
    from tests.factories import other_warehouse
    item, meter, kg = configured(db, variable=True)
    item.is_batch_tracked = True; db.flush()
    rule = db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    invoice = post_purchase_invoice(db, PurchaseInvoiceIn(invoice_date=date.today(),
        warehouse_id=main_warehouse(db).id, lines=[PurchaseInvoiceLineIn(item_id=item.id,
            qty=Decimal('36'), unit_id=kg.id, unit_cost=Decimal('500'),
            observations=[ObservedRatioIn(rule_id=rule.id, from_qty='36', to_qty='150')])]), user)
    assert invoice.lines[0].base_qty == 150
    original = db.query(StockBatch).filter_by(source_type='purchase_invoice', source_id=invoice.id).one()
    observed = db.query(BatchUnitConversion).filter_by(batch_id=original.id).one()
    assert observed.from_qty == 36 and observed.to_qty == 150
    document = post_stock_transfer(db, StockTransferIn(transfer_date=date.today(),
        from_warehouse_id=main_warehouse(db).id, to_warehouse_id=other_warehouse(db).id,
        lines=[StockTransferLineIn(item_id=item.id, qty=Decimal('12'), unit_id=kg.id,
            batch_allocations=[BatchAllocationIn(batch_id=original.id, qty=Decimal('50'))])]), user)
    assert document.lines[0].qty == 50
    assert document.lines[0].unit_conversion_snapshot['path'][0]['source'] == 'batch'
    mirror = db.query(StockBatch).filter_by(parent_batch_id=original.id).one()
    copied = db.query(BatchUnitConversion).filter_by(batch_id=mirror.id).one()
    assert copied.from_qty == 36 and copied.to_qty == 150
    converted = units.convert_transaction(db, item, Decimal('12'), kg.id, batch_id=mirror.id)
    assert converted.target_qty == 50
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == 100
    assert get_stock_qty(db, item.id, other_warehouse(db).id) == 50
    void_stock_transfer(db, document.id, reason='آزمون بار', user=user)
    assert on_hand(db, [original.id, mirror.id]) == {original.id: Decimal('150'), mirror.id: Decimal('0')}

def test_production_consumes_frozen_bom_unit_after_rule_change(db, user):
    from app.models.manufacturing import Bom
    from app.schemas.manufacturing import BomLineIn, ProductionOrderIn
    from app.services import manufacturing
    from tests.factories import make_item
    item, piece, carton = configured(db)
    finished = make_item(db, name='محصول آزمون واحد')
    seed_stock(db, user, item, '100')
    bom = Bom(finished_item_id=finished.id, name='فرمول واحد', yield_qty=Decimal(2),
        notes='', created_by_id=user.id,
        lines=manufacturing.build_bom_lines(db, [BomLineIn(component_item_id=item.id,
            qty='2', unit_id=carton.id)]))
    db.add(bom); db.flush()
    assert bom.lines[0].qty == 48 and bom.lines[0].entered_qty == 2
    rule = db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    units.configure_rule(db, item, ConversionRuleIn(from_unit_id=carton.id,
        to_unit_id=piece.id, factor='30'), rule_id=rule.id)
    order = manufacturing.post_production_order(db, ProductionOrderIn(bom_id=bom.id,
        warehouse_id=main_warehouse(db).id, production_date=date.today(), qty_produced='1'), user)
    line = order.lines[0]
    assert line.qty == 24 and line.entered_qty == 1 and line.entered_unit_id == carton.id
    assert line.unit_conversion_snapshot['path'][0]['version'] == 1
    assert get_stock_qty(db, item.id, main_warehouse(db).id) == 76
    move = db.query(StockLedger).filter_by(item_id=item.id, source_type='production').one()
    assert move.qty == -24 and move.entered_qty == -1
    assert move.unit_conversion_snapshot['source_unit_name'] == 'کارتن'

def test_production_uses_meter_stock_from_measured_kg_purchase(db, user):
    from app.models.manufacturing import Bom
    from app.schemas.manufacturing import BomLineIn, ProductionOrderIn
    from app.services import manufacturing
    from tests.factories import make_item
    fabric, meter, kg = configured(db, variable=True)
    rule = db.query(ItemUnitConversion).filter_by(item_id=fabric.id).one()
    post_purchase_invoice(db, PurchaseInvoiceIn(invoice_date=date.today(), warehouse_id=main_warehouse(db).id,
        lines=[PurchaseInvoiceLineIn(item_id=fabric.id, qty='36', unit_id=kg.id, unit_cost='500',
            observations=[ObservedRatioIn(rule_id=rule.id, from_qty='36', to_qty='150')])]), user)
    finished = make_item(db, name='پیراهن آزمون واحد')
    bom = Bom(finished_item_id=finished.id, name='پارچه', yield_qty=Decimal(1), notes='',
        created_by_id=user.id, lines=manufacturing.build_bom_lines(db, [
            BomLineIn(component_item_id=fabric.id, qty='1.5', unit_id=meter.id)]))
    db.add(bom); db.flush()
    order = manufacturing.post_production_order(db, ProductionOrderIn(bom_id=bom.id,
        warehouse_id=main_warehouse(db).id, production_date=date.today(), qty_produced='100'), user)
    assert order.lines[0].qty == 150
    assert get_stock_qty(db, fabric.id, main_warehouse(db).id) == 0
    assert get_stock_qty(db, finished.id, main_warehouse(db).id) == 100
    assert order.component_cost == 18000 and order.unit_cost == 180


def test_production_output_accepts_alternate_unit_and_keeps_ledger_input(db, user):
    from app.models.manufacturing import Bom
    from app.schemas.manufacturing import BomLineIn, ProductionOrderIn
    from app.services import manufacturing
    from tests.factories import make_item
    finished, piece, carton = configured(db)
    component = make_item(db, name='جزء آزمون خروجی')
    component.is_batch_tracked = True; db.flush()
    seed_stock(db, user, component, '100')
    bom = Bom(finished_item_id=finished.id, name='خروجی بسته', yield_qty=Decimal(1), notes='',
        created_by_id=user.id, lines=manufacturing.build_bom_lines(db, [
            BomLineIn(component_item_id=component.id, qty='0.5'),
            BomLineIn(component_item_id=component.id, qty='0.5')]))
    db.add(bom); db.flush()
    order = manufacturing.post_production_order(db, ProductionOrderIn(bom_id=bom.id,
        warehouse_id=main_warehouse(db).id, production_date=date.today(), qty_produced='2', unit_id=carton.id), user)
    assert order.qty_produced == 48 and sum(line.qty for line in order.lines) == 48
    move = db.query(StockLedger).filter_by(item_id=finished.id, source_type='production', source_id=order.id).one()
    assert move.qty == 48 and move.entered_qty == 2 and move.entered_unit_id == carton.id
    assert move.unit_conversion_snapshot['source_unit_name'] == 'کارتن'
    from app.services import batches
    from app.models.advanced_inventory import StockBatch
    source_batch = db.query(StockBatch).filter_by(item_id=component.id).one()
    assert batches.on_hand(db, [source_batch.id])[source_batch.id] == 52
    assert batches.on_hand(db, [move.batch_id])[move.batch_id] == 48
    consumed = db.query(StockLedger).filter_by(item_id=component.id, source_type='production').all()
    assert len(consumed) == 2 and all(row.batch_id == source_batch.id and row.source_line_id for row in consumed)


def test_production_plan_material_issue_and_alternate_receipt_keep_snapshots(db, user):
    from app.models.manufacturing import Bom
    from app.schemas.manufacturing import BomLineIn, ProductionPlanIn, ProductionMaterialIssueIn, ProductionReceiptIn
    from app.services import manufacturing
    from tests.factories import make_item
    component, piece, carton = configured(db)
    finished, _, finished_carton = configured(db)
    seed_stock(db, user, component, '100')
    bom = Bom(finished_item_id=finished.id, name='سفارش بسته', yield_qty=Decimal(24), notes='',
        created_by_id=user.id, lines=manufacturing.build_bom_lines(db, [
            BomLineIn(component_item_id=component.id, qty='1', unit_id=carton.id)]))
    db.add(bom); db.flush()
    plan = manufacturing.create_production_plan(db, ProductionPlanIn(bom_id=bom.id,
        warehouse_id=main_warehouse(db).id, planned_date=date.today(), qty_planned='48'), user)
    plan.status = 'started'; db.flush()
    rule = db.query(ItemUnitConversion).filter_by(item_id=component.id).one()
    units.configure_rule(db, component, ConversionRuleIn(from_unit_id=carton.id,
        to_unit_id=piece.id, factor='30'), rule_id=rule.id)
    issued = manufacturing.issue_materials_to_production(db, plan.id,
        ProductionMaterialIssueIn(issue_date=date.today(), qty='48'), user)
    assert issued.lines[0].qty == 48 and issued.lines[0].entered_qty == 2
    assert issued.lines[0].unit_conversion_snapshot['path'][0]['version'] == 1
    receipt = manufacturing.receive_production_output(db, plan.id,
        ProductionReceiptIn(receipt_date=date.today(), qty='2', unit_id=finished_carton.id), user)
    assert receipt.lines[0].qty == 48 and receipt.lines[0].entered_qty == 2
    assert receipt.lines[0].entered_unit_id == finished_carton.id and plan.qty_produced == 48
    move = db.query(StockLedger).filter_by(source_type='warehouse_receipt', source_id=receipt.id).one()
    assert move.qty == 48 and move.entered_qty == 2
