from uuid import uuid4
import os
from pathlib import Path
import pytest
from test_repair import intake, admit
from app.models.repair import RepairCase
from app.models.inventory import StockLedger
from app.models.accounting import JournalEntry
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException
from app.deps import Principal
from app.models.tenant import Membership
from app.models.user import User
from app.models.inventory import Contact
from app.models.repair import RepairBranch, RepairDeviceType, RepairDevice, RepairEvent
from app.models.repair_completion import RepairCaseDetails, RepairTechnicianCapacity
from app.schemas.repair import AdmissionIn, AssignmentIn
from app.schemas.repair_completion import CapacityIn
from app.services import repair as core, repair_completion
from conftest import tenant_session


def keyed(client, path, data, key=None):
    return client.post('/api/repair/'+path, json=data, headers={'Idempotency-Key':key or str(uuid4())})


def configure(client, intake):
    result=client.put('/api/repair/branches/'+intake['branch_id']+'/intake-settings',json={
        'version':0,'code':'HQ','default_location':'قفسه سریع','terms':'شرایط نسخه اول'})
    assert result.status_code==200,result.text
    return result.json()


def test_batch_replay_frozen_defaults_and_no_ledgers(client,db,intake):
    configure(client,intake)
    quick={k:v for k,v in intake.items() if k not in {'storage_location','terms'}}
    second={**quick,'device':{**quick['device'],'serial':'SERIAL-2'}}
    data={'contact_id':intake['contact_id'],'admissions':[quick,second]}
    before=(db.query(StockLedger).count(),db.query(JournalEntry).count())
    key=str(uuid4())
    first=keyed(client,'intake-batches',data,key)
    assert first.status_code==201,first.text
    replay=keyed(client,'intake-batches',data,key)
    assert replay.json()['id']==first.json()['id']
    assert db.query(RepairCase).count()==2
    rows=first.json()['items']
    assert len({r['number'] for r in rows})==2
    assert all(r['storage_location']=='قفسه سریع' for r in rows)
    changed=client.put('/api/repair/branches/'+intake['branch_id']+'/intake-settings',json={
        'version':1,'code':'NEW','default_location':'جدید','terms':'شرایط جدید'})
    assert changed.status_code==200,changed.text
    saved=client.get('/api/repair/cases/'+rows[0]['id']).json()
    assert saved['terms']=='شرایط نسخه اول'
    assert saved['intake_details']['display_number'].startswith('HQ-')
    assert (db.query(StockLedger).count(),db.query(JournalEntry).count())==before


def test_signature_revision_immutable_and_delivery_requires_real_delivery(client,intake):
    row=admit(client,intake).json()
    path='cases/'+row['id']
    signed={'version':row['version'],'kind':'intake','signer_name':'مالک','signer_relation':'مشتری','strokes':[[[10,20],[30,40]]]}
    key=str(uuid4())
    first=keyed(client,path+'/acknowledgments',signed,key)
    assert first.status_code==201,first.text
    assert keyed(client,path+'/acknowledgments',signed,key).json()==first.json()
    current=client.get('/api/repair/'+path).json()
    assert keyed(client,path+'/acknowledgments',{**signed,'version':current['version']}).status_code==409
    changed=client.patch('/api/repair/'+path+'/intake-details',json={'version':current['version'],'accessories':'شارژر'},headers={'Idempotency-Key':str(uuid4())})
    assert changed.status_code==200,changed.text
    newer=keyed(client,path+'/acknowledgments',{**signed,'version':changed.json()['version']})
    assert newer.status_code==201,newer.text
    assert newer.json()['document_revision']==2
    history=client.get('/api/repair/'+path+'/acknowledgments').json()
    assert len(history)==2
    assert history[0]['document_snapshot']['accessories']!=history[1]['document_snapshot']['accessories']
    current=client.get('/api/repair/'+path).json()
    assert keyed(client,path+'/acknowledgments',{**signed,'kind':'delivery','version':current['version']}).status_code==409


def test_real_codes_and_pdf_without_customer_tokens(client,intake):
    row=admit(client,intake).json()
    base='/api/repair/cases/'+row['id']
    label=client.get(base+'/label')
    assert label.status_code==200,label.text
    assert label.text.count('data:image/svg+xml;base64,')==2
    assert '09123456789' not in label.text
    pdf=client.get(base+'/receipt.pdf')
    assert pdf.status_code==200,pdf.text[:200]
    assert pdf.content.startswith(b'%PDF-')


@pytest.mark.skipif(os.environ.get('REPAIR_PRINT_QA')!='1',reason='Opt-in rendered PDF decoding requires pypdfium2 and zxing-cpp')
def test_rendered_receipt_decodes_both_standard_codes(client,intake):
    import pypdfium2 as pdfium
    import zxingcpp
    row=admit(client,intake).json()
    response=client.get('/api/repair/cases/'+row['id']+'/receipt.pdf')
    assert response.status_code==200
    document=pdfium.PdfDocument(response.content)
    page=document[0];bitmap=page.render(scale=3)
    try:
        rendered=bitmap.to_pil().copy()
        decoded={code.text for code in zxingcpp.read_barcodes(rendered)}
        assert decoded=={'R'+str(row['number']),'cubita:repair:'+row['id']}
        destination=Path(__file__).resolve().parents[2]/'_deploy'/'repair-completion-receipt.png'
        rendered.save(destination)
        destination.with_suffix('.pdf').write_bytes(response.content)
    finally:
        bitmap.close();page.close();document.close()


def test_server_timer_single_active_confirmation_and_correction(client,intake):
    first=admit(client,intake).json()
    second=admit(client,{**intake,'device':{**intake['device'],'serial':'SECOND'}}).json()
    path='cases/'+first['id']+'/time-sessions'
    key=str(uuid4())
    started=keyed(client,path,{'version':first['version']},key)
    assert started.status_code==201,started.text
    assert keyed(client,path,{'version':first['version']},key).json()['id']==started.json()['id']
    assert keyed(client,'cases/'+second['id']+'/time-sessions',{'version':second['version']}).status_code==409
    timer=started.json()
    action='time-sessions/'+timer['id']+'/actions'
    assert keyed(client,action,{'version':timer['version'],'action':'confirm','seconds':1}).status_code==409
    stopped=keyed(client,action,{'version':timer['version'],'action':'stop'})
    assert stopped.status_code==200,stopped.text
    confirmed=keyed(client,action,{'version':stopped.json()['version'],'action':'confirm','seconds':stopped.json()['elapsed_seconds']})
    assert confirmed.status_code==200,confirmed.text
    assert keyed(client,action,{'version':confirmed.json()['version'],'action':'correct','seconds':10}).status_code==422
    corrected=keyed(client,action,{'version':confirmed.json()['version'],'action':'correct','seconds':10,'reason':'زمان آماده‌سازی نیز انجام شد'})
    assert corrected.status_code==200,corrected.text
    assert corrected.json()['confirmed_seconds']==10
    assert keyed(client,'cases/'+second['id']+'/time-sessions',{'version':second['version']}).status_code==201


def test_capacity_manager_override_and_bulk_partial_replay(client,intake,user):
    first=admit(client,intake).json()
    second=admit(client,{**intake,'device':{**intake['device'],'serial':'SECOND'}}).json()
    uid=str(user.id)
    capacity=client.put('/api/repair/technicians/'+uid+'/capacity',json={'version':0,'max_active_cases':1})
    assert capacity.status_code==200,capacity.text
    def assign(row,**extra):
        return client.post('/api/repair/cases/'+row['id']+'/assignment',json={'version':row['version'],'user_id':uid,'reason':'تخصیص آزمون',**extra})
    assert assign(first).status_code==200
    assert assign(second).status_code==409
    override=assign(second,capacity_override=True)
    assert override.status_code==200,override.text
    history=client.get('/api/repair/cases/'+second['id']).json()['events']
    assert any(e['action']=='capacity_override' and e['detail']['reason']=='تخصیص آزمون' for e in history)
    suggestions=client.get('/api/repair/technician-suggestions',params={'branch_id':intake['branch_id']}).json()
    assert next(s for s in suggestions if s['id']==uid)['active_cases']==2
    first=client.get('/api/repair/cases/'+first['id']).json()
    payload={'action':'assign','cases':[{'case_id':first['id'],'version':first['version']},{'case_id':second['id'],'version':1}],'technician_id':None,'reason':'رفع ارجاع گروهی'}
    key=str(uuid4())
    bulk=keyed(client,'bulk-operations',payload,key)
    assert bulk.status_code==201,bulk.text
    assert sorted(r['ok'] for r in bulk.json()['results'])==[False,True]
    assert keyed(client,'bulk-operations',payload,key).json()==bulk.json()


def test_farsi_and_internal_scan_search(client,intake):
    row=admit(client,{**intake,'device':{**intake['device'],'model':'يكي ۱۲۳'}}).json()
    for q in ['یکی 123','cubita:repair:'+row['id'],'R'+str(row['number'])]:
        response=client.get('/api/repair/cases',params={'q':q})
        assert response.status_code==200,response.text
        assert row['id'] in {r['id'] for r in response.json()['items']}


def test_organizational_references_frozen_and_batch_failure_atomic(client,db,intake):
    configure(client,intake)
    representative=client.post('/api/contacts',json={'name':'نماینده موجود','type':'customer'}).json()
    data={**intake,'representative_contact_id':representative['id']}
    first=keyed(client,'quick-admissions',data)
    assert first.status_code==201,first.text
    assert first.json()['intake_details']['representative']=='نماینده موجود'
    assert first.json()['intake_details']['representative_contact_id']==representative['id']
    count=db.query(RepairCase).count()
    bad={**data,'device':{**intake['device'],'type_id':str(uuid4())}}
    response=keyed(client,'intake-batches',{'contact_id':intake['contact_id'],'admissions':[data,bad]})
    assert response.status_code==422,response.text
    assert db.query(RepairCase).count()==count


def test_concurrent_capacity_last_slot(tenant_id,user):
    ids=[]
    with tenant_session(tenant_id) as db:
        membership=db.query(Membership).filter_by(user_id=user.id,tenant_id=tenant_id).one()
        principal=Principal(db.get(User,user.id),membership)
        technician=User(name='ظرفیت همزمان',email=str(uuid4())+'@example.invalid',hashed_password='unused',active=True)
        branch=RepairBranch(name='capacity-'+str(uuid4()));kind=RepairDeviceType(name='capacity-'+str(uuid4()));contact=Contact(name='مالک آزمون ظرفیت',is_customer=True)
        db.add_all([technician,branch,kind,contact]);db.flush()
        db.add(Membership(tenant_id=tenant_id,user_id=technician.id,role_id=membership.role_id,status='active'));db.flush()
        policy=repair_completion.save_capacity(db,principal,technician.id,CapacityIn(max_active_cases=1))
        for _ in range(2):
            row=core.create(db,principal,AdmissionIn(contact_id=contact.id,branch_id=branch.id,device={'type_id':kind.id,'model':'همزمان'},reported_issue='تخصیص همزمان',admission_date='2026-10-07',storage_location='آزمایش',terms='آزمایشی',approval_method='in_person'))
            ids.append(row.id)
        technician_id,branch_id,kind_id,contact_id,policy_id=technician.id,branch.id,kind.id,contact.id,policy.id
        db.commit()
    def assign(case_id):
        with tenant_session(tenant_id) as db:
            p=Principal(db.get(User,user.id),db.query(Membership).filter_by(user_id=user.id,tenant_id=tenant_id).one())
            try:
                core.assign(db,p,core.case(db,p,case_id,lock=True),AssignmentIn(version=1,user_id=technician_id,reason='آخرین ظرفیت'))
                db.commit();return 200
            except HTTPException as error:
                db.rollback();return error.status_code
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(assign,ids))==[200,409]
        with tenant_session(tenant_id) as db:
            assert repair_completion.workload(db,technician_id)==1
    finally:
        with tenant_session(tenant_id) as db:
            device_ids=[row.device_id for row in db.query(RepairCase).filter(RepairCase.id.in_(ids))]
            for model,column,values in ((RepairEvent,'case_id',ids),(RepairCaseDetails,'case_id',ids),(RepairCase,'id',ids),(RepairDevice,'id',device_ids),(RepairTechnicianCapacity,'id',[policy_id]),(RepairBranch,'id',[branch_id]),(RepairDeviceType,'id',[kind_id]),(Contact,'id',[contact_id]),(Membership,'user_id',[technician_id]),(User,'id',[technician_id])):
                db.query(model).filter(getattr(model,column).in_(values)).delete(synchronize_session=False)
            db.commit()
