from datetime import date
from decimal import Decimal
from uuid import uuid4
from tests.test_repair import intake,approved_case
from tests.test_repair_tools import post,current
from tests.factories import make_item,main_warehouse,other_warehouse
from app.services.inventory import post_purchase_invoice,get_stock_qty
from app.schemas.invoices import PurchaseInvoiceIn,PurchaseInvoiceLineIn
from app.models.invoices import WarehouseIssue,WarehouseReceipt,PurchaseInvoice
from app.models.inventory import StockLedger
from app.models.accounting import JournalEntry,Account
from app.services.common import get_account
from app.services import chart_codes as cc


def setup_harvest(client,db,user,intake,qty='3',waste='0'):
    device=make_item(db,name='دستگاه شرکت');part=make_item(db,name='قطعه استخراج')
    source=main_warehouse(db);output=other_warehouse(db)
    post_purchase_invoice(db,PurchaseInvoiceIn(invoice_date=date.today(),warehouse_id=source.id,lines=[PurchaseInvoiceLineIn(item_id=device.id,qty=1,unit_cost=1000)]),user)
    waste_account=Account(code='HW'+uuid4().hex[:10],name='ضایعات استخراج',type='expense');db.add(waste_account);db.flush()
    data={'item_id':str(device.id),'on':date.today().isoformat(),'source_warehouse_id':str(source.id),'output_warehouse_id':str(output.id),'outputs':[{'item_id':str(part.id),'qty':qty,'percent':str(100-Decimal(waste))}],'waste_percent':waste,'waste_account_id':str(waste_account.id) if Decimal(waste) else None,'reason':'استخراج دستگاه موجودی شرکت'}
    return device,part,source,output,data


def test_harvest_actual_balanced_cost_two_lots_replay_void(client,db,user,intake):
    device,part,source,output,data=setup_harvest(client,db,user,intake)
    before=(db.query(StockLedger).count(),db.query(JournalEntry).count(),db.query(PurchaseInvoice).count())
    key=str(uuid4());draft=post(client,'branches/'+intake['branch_id']+'/harvests',data,key)
    assert draft.status_code==201,draft.text
    assert post(client,'branches/'+intake['branch_id']+'/harvests',data,key).json()['id']==draft.json()['id']
    assert (db.query(StockLedger).count(),db.query(JournalEntry).count(),db.query(PurchaseInvoice).count())==before
    path='harvests/'+draft.json()['id'];key=str(uuid4())
    posted=post(client,path+'/approval',{'version':1},key)
    assert posted.status_code==200,posted.text
    result=posted.json();assert Decimal(result['device_cost'])==Decimal(result['outputs'][0]['allocated_cost'])==1000
    assert Decimal(result['waste_cost'])==0 and len(result['outputs'][0]['batch_ids'])==2
    assert get_stock_qty(db,device.id,source.id)==0 and get_stock_qty(db,part.id,output.id)==3
    receipt=db.get(WarehouseReceipt,result['receipt_id'])
    assert sum((l.landed_amount for l in receipt.lines),Decimal(0))==1000
    assert sorted((l.qty,l.unit_cost) for l in receipt.lines)==[(Decimal(1),Decimal(334)),(Decimal(2),Decimal(333))]
    assert post(client,path+'/approval',{'version':1},key).json()['id']==result['id']
    assert db.query(WarehouseIssue).count()==1 and db.query(WarehouseReceipt).count()==1 and db.query(PurchaseInvoice).count()==before[2]
    from fastapi import HTTPException
    import pytest
    from app.services import warehouse_issues,warehouse_receipts
    with pytest.raises(HTTPException): warehouse_issues.void_warehouse_issue(db,result['issue_id'],reason='تک سند',user=user)
    with pytest.raises(HTTPException): warehouse_receipts.void_warehouse_receipt(db,result['receipt_id'],reason='تک سند',user=user)
    voided=post(client,path+'/void',{'version':2,'on':date.today().isoformat(),'reason':'ابطال آزمایشی'})
    assert voided.status_code==200,voided.text
    assert get_stock_qty(db,device.id,source.id)==1 and get_stock_qty(db,part.id,output.id)==0
    assert sum((l.debit-l.credit for e in db.query(JournalEntry) for l in e.lines),Decimal(0))==0


def test_harvest_waste_exact_actual_journal_no_customer_device(client,db,user,intake):
    from tests.test_repair import admit
    device,part,source,output,data=setup_harvest(client,db,user,intake,qty='2',waste='25')
    customer=admit(client,intake).json()
    denied=post(client,'branches/'+intake['branch_id']+'/harvests',{**data,'item_id':customer['device_id']})
    assert denied.status_code==422
    assert post(client,'branches/'+intake['branch_id']+'/harvests',{**data,'waste_percent':'24'}).status_code==422
    draft=post(client,'branches/'+intake['branch_id']+'/harvests',data)
    assert draft.status_code==201,draft.text
    posted=post(client,'harvests/'+draft.json()['id']+'/approval',{'version':1})
    assert posted.status_code==200,posted.text
    result=posted.json();assert Decimal(result['outputs'][0]['allocated_cost'])+Decimal(result['waste_cost'])==Decimal(result['device_cost'])==1000
    assert db.get(JournalEntry,result['waste_entry_id']).lines[0].debit==250


def test_harvest_failed_approval_rolled_back_no_double_issue(client,db,user,intake):
    device,part,source,output,data=setup_harvest(client,db,user,intake)
    # Input is company stock, but serial was never registered: fail after issue.
    draft=post(client,'branches/'+intake['branch_id']+'/harvests',{**data,'serials':['FAKE-SERIAL']})
    assert draft.status_code==201,draft.text
    before=(db.query(StockLedger).count(),db.query(JournalEntry).count())
    result=post(client,'harvests/'+draft.json()['id']+'/approval',{'version':1})
    assert result.status_code==409,result.text
    assert db.query(WarehouseIssue).count()==db.query(WarehouseReceipt).count()==0
    assert get_stock_qty(db,device.id,source.id)==1
    assert (db.query(StockLedger).count(),db.query(JournalEntry).count())==before


def test_harvest_void_blocks_downstream_even_with_other_available_stock(client,db,user,intake):
    from app.services import warehouse_issues
    from app.schemas.invoices import DirectWarehouseIssueIn,WarehouseIssueLineIn
    device,part,source,output,data=setup_harvest(client,db,user,intake)
    draft=post(client,'branches/'+intake['branch_id']+'/harvests',data)
    posted=post(client,'harvests/'+draft.json()['id']+'/approval',{'version':1})
    assert posted.status_code==200,posted.text
    result=posted.json()
    warehouse_issues.create_direct_warehouse_issue(db,DirectWarehouseIssueIn(issue_date=date.today(),warehouse_id=output.id,issue_type='production',lines=[WarehouseIssueLineIn(item_id=part.id,qty=1)]),user)
    post_purchase_invoice(db,PurchaseInvoiceIn(invoice_date=date.today(),warehouse_id=output.id,lines=[PurchaseInvoiceLineIn(item_id=part.id,qty=3,unit_cost=400)]),user)
    before=(db.query(StockLedger).count(),db.query(JournalEntry).count())
    denied=post(client,'harvests/'+result['id']+'/void',{'version':2,'on':date.today().isoformat(),'reason':'موجودی بچ دیگر مجوز ابطال نیست'})
    assert denied.status_code==409,denied.text
    assert (db.query(StockLedger).count(),db.query(JournalEntry).count())==before
    assert get_stock_qty(db,device.id,source.id)==0


def test_supplier_quality_purchase_warranty_and_claim_no_second_debt(client,db,user,intake,approved_case):
    from tests.factories import make_contact
    part=make_item(db,name='قطعه ضمانت');supplier=make_contact(db,name='تأمین‌کننده',type_='supplier');warehouse=main_warehouse(db);destination=other_warehouse(db)
    purchase=post_purchase_invoice(db,PurchaseInvoiceIn(invoice_date=date.today(),contact_id=supplier.id,warehouse_id=warehouse.id,lines=[PurchaseInvoiceLineIn(item_id=part.id,qty=2,unit_cost=100)]),user)
    row=approved_case;path='cases/'+row['id']
    requested=post(client,path+'/parts',{'version':current(client,row),'item_id':str(part.id),'qty':'1','unit_price':'0','charge_to_customer':False,'source_warehouse_id':str(warehouse.id),'work_warehouse_id':str(destination.id)})
    assert requested.status_code==201,requested.text
    part_id=requested.json()['id'];data={'version':current(client,row),'quality':'rejected','compatibility':'سازگار با مدل، اما رد کیفیت','test_result':'آزمون بار شکست خورد','purchase_invoice_id':str(purchase.id),'purchase_line_id':str(purchase.lines[0].id),'warranty_until':'2099-01-01','warranty_terms':'تعویض در صورت شکست آزمون'}
    before=(db.query(PurchaseInvoice).count(),db.query(JournalEntry).count())
    key=str(uuid4());assessed=post(client,path+'/parts/'+part_id+'/assessments',data,key)
    assert assessed.status_code==201,assessed.text
    assert post(client,path+'/parts/'+part_id+'/assessments',data,key).json()['id']==assessed.json()['id']
    claim=post(client,path+'/supplier-claims',{'version':current(client,row),'assessment_id':assessed.json()['id'],'reason':'مطالبه تعویض قطعه معیوب'})
    assert claim.status_code==201,claim.text
    assert post(client,path+'/supplier-claims',{'version':current(client,row),'assessment_id':assessed.json()['id'],'reason':'مطالبه تکراری'}).status_code==409
    resolution={'version':current(client,row),'claim_version':1,'status':'refunded','response':'مبلغ برگشت خورد'}
    assert post(client,path+'/supplier-claims/'+claim.json()['id']+'/resolution',resolution).status_code==422
    accepted=post(client,path+'/supplier-claims/'+claim.json()['id']+'/resolution',{**resolution,'status':'accepted'})
    assert accepted.status_code==200,accepted.text
    assert (db.query(PurchaseInvoice).count(),db.query(JournalEntry).count())==before
    for action in ['reserve','dispatch']:
        result=post(client,path+'/parts/'+part_id+'/actions',{'version':current(client,row),'on':date.today().isoformat(),'action':action})
        assert result.status_code==201,result.text
    consumed=post(client,path+'/parts/'+part_id+'/actions',{'version':current(client,row),'on':date.today().isoformat(),'action':'consume','qty':'1'})
    assert consumed.status_code==409 and db.query(WarehouseIssue).count()==0
