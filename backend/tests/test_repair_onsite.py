from uuid import uuid4
from tests.test_repair import intake
from app.models.repair import RepairServiceRequest
from app.models.repair_completion import RepairOnsiteApproval
from app.models.accounting import JournalEntry
from app.models.inventory import StockLedger


def test_onsite_action_signature_version_replay_private_no_financial(client,db,user,intake):
    payload={'branch_id':intake['branch_id'],'contact_id':intake['contact_id'],'type_id':intake['device']['type_id'],'device_description':'دستگاه سازمان','reported_issue':'عیب','address':'محل سازمان','coordinator_name':'نماینده','coordinator_phone':'09123456789'}
    response=client.post('/api/repair/service-requests',json=payload,headers={'Idempotency-Key':str(uuid4())});assert response.status_code==201,response.text
    request=response.json();path='/api/repair/service-requests/'+request['id']
    assert client.put('/api/repair/technicians/'+str(user.id)+'/skills',json={'type_ids':[payload['type_id']]}).status_code==200
    def version(): return db.get(RepairServiceRequest,request['id']).version
    slot=client.post(path+'/appointments',json={'version':version(),'technician_id':str(user.id),'starts_at':'2026-10-07T09:00:00+03:30','ends_at':'2026-10-07T10:00:00+03:30'},headers={'Idempotency-Key':str(uuid4())})
    assert slot.status_code==201,slot.text
    action_path=path+'/appointments/'+slot.json()['id']+'/actions'
    assert client.post(action_path,json={'version':version(),'description':'تنظیم','result':'آزمون موفق'},headers={'Idempotency-Key':str(uuid4())}).status_code==409
    for state in ['dispatched','onsite']:
        assert client.post(path+'/appointments/'+slot.json()['id']+'/status',json={'version':version(),'status':state,'result':'حضور واقعی'}).status_code==200
    before=(db.query(JournalEntry).count(),db.query(StockLedger).count())
    data={'version':version(),'description':'تنظیم دستگاه','result':'آزمون موفق'};key=str(uuid4())
    action=client.post(action_path,json=data,headers={'Idempotency-Key':key});assert action.status_code==201,action.text
    assert client.post(action_path,json=data,headers={'Idempotency-Key':key}).json()['id']==action.json()['id']
    approval_path=path+'/onsite-actions/'+action.json()['id']+'/approval'
    data={'version':version(),'action_version':2,'approver_name':'نماینده سازمان','strokes':[[[10,20],[30,40]]]}
    assert client.post(approval_path,json=data,headers={'Idempotency-Key':str(uuid4())}).status_code==409
    data['action_version']=1;key=str(uuid4());approved=client.post(approval_path,json=data,headers={'Idempotency-Key':key})
    assert approved.status_code==201,approved.text
    assert 'signature' not in approved.json()
    assert client.post(approval_path,json=data,headers={'Idempotency-Key':key}).json()['id']==approved.json()['id']
    record=db.query(RepairOnsiteApproval).one();assert record.snapshot['description']=='تنظیم دستگاه' and record.signature_hash
    assert (db.query(JournalEntry).count(),db.query(StockLedger).count())==before
