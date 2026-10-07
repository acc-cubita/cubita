from uuid import uuid4
from datetime import date,timedelta,datetime,timezone
from decimal import Decimal
import pytest
from app.deps import get_principal
from app.main import app
from app.models.user import User,Role
from app.models.tenant import Membership
from app.models.repair import RepairCase,RepairNotification,RepairWork
from app.models.repair_completion import RepairParticipation,RepairCustomerFollowup
from app.models.invoices import PurchaseInvoice
from app.models.accounting import JournalEntry
from app.models.inventory import StockLedger
from app.services import repair_notifications
from tests.test_repair import intake,approved_case,admit
from tests.test_repair_tools import post,current
from tests.factories import make_item,make_contact


@pytest.mark.parametrize('mode,value,expected',[('percent_labor','10','250'),('per_operation','1000','250'),('fixed_case','1000','1000')])
def test_participation_weighted_fee_real_debt_once_and_frozen(client,db,user,tenant_id,approved_case,mode,value,expected):
    colleague=User(name='همکار',email=str(uuid4())+'@example.invalid',hashed_password='unused',active=True)
    db.add(colleague);db.flush()
    membership=db.query(Membership).filter_by(user_id=user.id,tenant_id=tenant_id).one()
    db.add(Membership(user_id=colleague.id,tenant_id=tenant_id,role_id=membership.role_id,status='active'));db.flush()
    service=make_item(db,name='خدمت تعمیر',is_service=True);payee=make_contact(db,type_='supplier')
    row=approved_case;path='cases/'+row['id']
    work=post(client,path+'/work',{'version':current(client,row),'technician_id':str(user.id),'collaborators':[str(colleague.id)],'service_id':str(service.id),'description':'یک عملیات مشترک','charge_amount':'10000','work_minutes':10})
    assert work.status_code==201,work.text
    data={'version':current(client,row),'shares':[{'technician_id':str(user.id),'percent':'75'},{'technician_id':str(colleague.id),'percent':'25'}],'reason':'تأیید مشارکت واقعی'}
    assert post(client,path+'/work/'+work.json()['id']+'/participation',{**data,'shares':[{'technician_id':str(user.id),'percent':'75'}]}).status_code==422
    key=str(uuid4());shares=post(client,path+'/work/'+work.json()['id']+'/participation',data,key)
    assert shares.status_code==201,shares.text
    assert post(client,path+'/work/'+work.json()['id']+'/participation',data,key).json()['id']==shares.json()['id']
    assert db.query(RepairWork).count()==1 and db.query(RepairWork).one().charge_amount==10000
    for status,reason in [('diagnosing',''),('unrepairable','نتیجه ثبت شد')]:
        result=client.post('/api/repair/'+path+'/status',json={'version':current(client,row),'status':status,'reason':reason})
        assert result.status_code==200,result.text
    rule=post(client,'fee-rules',{'technician_id':str(colleague.id),'mode':mode,'value':value,'payee_id':str(payee.id),'service_id':str(service.id),'reason':'سهم همکار'})
    assert rule.status_code==201,rule.text
    draft=post(client,path+'/technician-fees',{'version':current(client,row),'technician_id':str(colleague.id)})
    assert draft.status_code==201,draft.text
    assert draft.json()['amount_rial']==expected
    assert Decimal(draft.json()['calculation']['weighted_operations'])==Decimal('.25')
    snapshot=draft.json()['calculation'];key=str(uuid4());body={'version':current(client,row),'on':date.today().isoformat()}
    approved=post(client,path+'/technician-fees/'+draft.json()['id']+'/approve',body,key)
    assert approved.status_code==200,approved.text
    assert post(client,path+'/technician-fees/'+draft.json()['id']+'/approve',body,key).json()['purchase_invoice_id']==approved.json()['purchase_invoice_id']
    assert db.query(PurchaseInvoice).count()==1 and db.query(PurchaseInvoice).one().total_amount==Decimal(expected)
    changed=post(client,path+'/work/'+work.json()['id']+'/participation',{**data,'version':current(client,row),'previous_revision':1})
    assert changed.status_code==409
    assert db.query(RepairParticipation).count()==1 and approved.json()['calculation']==snapshot
    report=client.get('/api/repair/reports',params={'financial':True})
    assert report.status_code==200,report.text
    reported=next(r for r in report.json()['items'] if r['id']==row['id'])
    assert Decimal(reported['financial']['technician_participation'][str(colleague.id)]['labor_rial'])==Decimal('2500')
    assert Decimal(reported['financial']['actual_receipts_rial'])==0


def test_customer_call_complaint_sequence_and_replay_no_postings(client,db,user,intake):
    row=admit(client,intake).json();path='cases/'+row['id']+'/customer-followups'
    before=(db.query(StockLedger).count(),db.query(JournalEntry).count())
    data={'version':current(client,row),'kind':'complaint','body':'پیگیری تأخیر','customer_name':'مالک','direction':'incoming','complaint_stage':'received','responsible_id':str(user.id)}
    key=str(uuid4());first=post(client,path,data,key)
    assert first.status_code==201,first.text
    assert post(client,path,data,key).json()['id']==first.json()['id']
    invalid=post(client,path,{**data,'version':current(client,row),'previous_id':first.json()['id'],'complaint_stage':'closed'})
    assert invalid.status_code==409
    second=post(client,path,{**data,'version':current(client,row),'previous_id':first.json()['id'],'complaint_stage':'investigating','body':'بررسی توسط مسئول'})
    assert second.status_code==201,second.text
    stale=post(client,path,{**data,'version':current(client,row),'previous_id':first.json()['id'],'complaint_stage':'resolved'})
    assert stale.status_code==409
    assert db.query(RepairCustomerFollowup).count()==2
    assert (db.query(StockLedger).count(),db.query(JournalEntry).count())==before
    report=client.get('/api/repair/reports')
    assert report.status_code==200,report.text
    reported=next(r for r in report.json()['items'] if r['id']==row['id'])
    assert reported['financial'] is None
    assert reported['operations']['complaints'][0]['stage']=='investigating'


def test_versioned_notification_policy_disable_reminders_dedup_no_fake_send(client,db,intake,monkeypatch):
    row=admit(client,intake).json();branch='branches/'+intake['branch_id']
    for kind in ['due','ready']:
        assert post(client,'message-templates',{'branch_id':intake['branch_id'],'kind':kind,'body':'پرونده {number}؛ {status}','enabled':True}).status_code==201
    result=post(client,branch+'/notification-policy',{'events':['uncollected'],'uncollected_days':1,'repeat_days':3})
    assert result.status_code==201,result.text
    policy=result.json();record=db.get(RepairCase,row['id']);record.status='ready';record.updated_at=datetime.now(timezone.utc)-timedelta(days=3);db.flush()
    monkeypatch.setattr(repair_notifications,'configured',lambda:False)
    repair_notifications.enqueue_due(db,record.tenant_id);repair_notifications.enqueue_due(db,record.tenant_id)
    messages=db.query(RepairNotification).all()
    assert len(messages)==1 and messages[0].status=='unavailable' and messages[0].kind=='ready'
    assert 'سرویس واقعی' in messages[0].last_result
    assert post(client,branch+'/notification-policy',{'previous_revision':policy['revision'],'events':[]}).status_code==201
    assert repair_notifications.enqueue(db,record,'ready','manual',strict=False) is None
