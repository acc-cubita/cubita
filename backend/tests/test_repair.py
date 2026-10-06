from uuid import uuid4
import pytest
from sqlalchemy import text
from app.deps import Principal, get_principal
from app.main import app
from app.models.accounting import JournalEntry
from app.models.inventory import StockLedger
from app.models.repair import RepairCase, RepairDevice, RepairBranchAccess
from app.models.tenant import Membership
from app.models.user import Role, User
from app.models.inventory import Contact
from app.models.repair import RepairBranch, RepairDeviceType
from app.schemas.repair import AdmissionIn
from app.services import repair as svc
from app.services.idempotency import idempotent
from starlette.requests import Request
from concurrent.futures import ThreadPoolExecutor
from conftest import tenant_session
from app.database import Base


@pytest.fixture
def intake(client):
    branch = client.post('/api/repair/branches', json={'name': 'مرکزی'})
    assert branch.status_code == 201, branch.text
    category = client.post('/api/repair/device-types', json={'name': 'رایانه', 'fields': ['رنگ'], 'checklist': ['شارژر']})
    assert category.status_code == 201, category.text
    customer = client.post('/api/contacts', json={'name': 'مالک دستگاه', 'type': 'customer', 'phone': '09123456789'})
    assert customer.status_code == 201, customer.text
    return {'contact_id': customer.json()['id'], 'branch_id': branch.json()['id'],
            'device': {'type_id': category.json()['id'], 'model': 'مدل آزمون', 'serial': 'SERIAL-1', 'attributes': {'رنگ': 'مشکی'}},
            'reported_issue': 'روشن نمی‌شود', 'admission_date': '2026-10-06', 'storage_location': 'قفسه الف',
            'terms': 'برآورد هزینه نیازمند تأیید جداگانه است.', 'approval_method': 'in_person'}


def admit(client, data, key=None):
    return client.post('/api/repair/cases', json=data, headers={'Idempotency-Key': key or str(uuid4())})


def test_admission_replay_no_stock_or_money(client, db, intake):
    counts = (db.query(StockLedger).count(), db.query(JournalEntry).count())
    key = str(uuid4())
    first = admit(client, intake, key)
    assert first.status_code == 201, first.text
    replay = admit(client, intake, key)
    assert replay.json()['id'] == first.json()['id']
    assert db.query(RepairCase).count() == db.query(RepairDevice).count() == 1
    assert (db.query(StockLedger).count(), db.query(JournalEntry).count()) == counts
    assert admit(client, {**intake, 'reported_issue': 'متفاوت'}, key).status_code == 409
    assert client.post('/api/repair/cases', json=intake).status_code == 400


def test_receipt_snapshot_location_and_visit(client, db, intake):
    row = admit(client, intake).json()
    path = '/api/repair/cases/' + row['id']
    receipt = client.get(path + '/receipt')
    assert receipt.status_code == 200 and '<svg' in receipt.text
    assert 'مالک دستگاه' in receipt.text and 'قفسه الف' not in receipt.text
    changed = client.put(path + '/location', json={'version': 1, 'storage_location': 'قفسه ب'})
    assert changed.status_code == 200 and changed.json()['version'] == 2
    assert client.put(path + '/location', json={'version': 1, 'storage_location': 'قدیمی'}).status_code == 409
    second = admit(client, {**intake, 'device': None, 'device_id': row['device_id']})
    assert second.status_code == 201, second.text
    assert len(second.json()['visits']) == 2 and second.json()['open_case_warnings'][0]['number'] == row['number']
    assert db.query(RepairDevice).count() == 1
    assert client.get('/api/repair/cases?q=SERIAL-1').json()['items']
    assert len(client.get('/api/repair/cases?q=09123456789').json()['items']) == 2


def test_branch_scope_and_revocation(client, db, user, tenant_id, intake):
    row = admit(client, intake).json()
    u = User(name='پذیرشگر', email=f'{uuid4()}@example.invalid', hashed_password='unused', active=True)
    role = Role(key=str(uuid4()), name='پذیرشگر', permissions={'repair': ['view','create','update']})
    db.add_all([u,role]); db.flush()
    membership = Membership(tenant_id=tenant_id, user_id=u.id, role_id=role.id, status='active')
    db.add(membership); db.flush()
    owner = app.dependency_overrides[get_principal]
    app.dependency_overrides[get_principal] = lambda: Principal(u, membership)
    assert client.get('/api/repair/cases').json()['items'] == []
    assert client.get('/api/repair/cases/' + row['id']).status_code == 404
    assert client.get('/api/repair/cases/' + row['id'] + '/receipt').status_code == 404
    assert admit(client, intake).status_code == 404
    assert client.post('/api/repair/branches', json={'name':'ممنوع'}).status_code == 403
    app.dependency_overrides[get_principal] = owner
    assert client.put('/api/repair/branches/' + intake['branch_id'] + '/access', json={'user_ids':[str(u.id)]}).status_code == 200
    app.dependency_overrides[get_principal] = lambda: Principal(u, membership)
    assert client.get('/api/repair/cases/' + row['id']).status_code == 200
    assert client.get('/api/contacts').status_code == 200
    db.query(RepairBranchAccess).delete(); db.flush()
    assert client.get('/api/repair/cases/' + row['id']).status_code == 404


def test_attachment_private_bounded_dedup_and_receipt_escape(client, intake):
    row = admit(client, {**intake, 'reported_issue': '<script>alert(1)</script>'}).json()
    path = '/api/repair/cases/' + row['id']
    assert '<script>' not in client.get(path + '/receipt').text
    assert client.post(path + '/attachments', files={'file':('evil.svg',b'<svg/>','image/svg+xml')}).status_code == 422
    first = client.post(path + '/attachments', files={'file':('intake.pdf',b'%PDF-test','application/pdf')})
    assert first.status_code == 200, first.text
    second = client.post(path + '/attachments', files={'file':('retry.pdf',b'%PDF-test','application/pdf')})
    assert first.json()['id'] == second.json()['id']
    assert len(client.get(path + '/attachments').json()) == 1
    assert client.get(path + '/attachments/' + first.json()['id']).headers['content-disposition'] == 'attachment'


def test_config_validation_and_rls(client, db, intake):
    assert client.post('/api/repair/device-types', json={'name':'نامعتبر','fields':['رمز دستگاه']}).status_code == 422
    assert admit(client, {**intake, 'intake_checklist': {'نامعتبر': True}}).status_code == 422
    assert admit(client, {**intake, 'due_date':'2026-10-05'}).status_code == 422
    assert client.get('/api/repair/cases?limit=201').status_code == 422
    flags = db.execute(text("SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname LIKE 'repair_%' AND relkind='r'")).all()
    assert len(flags) == len([t for t in Base.metadata.tables if t.startswith('repair_')]) and all(r[1] and r[2] for r in flags)


@pytest.fixture
def approved_case(client,intake):
    row = admit(client,intake).json()
    path = '/api/repair/cases/' + row['id']
    assert client.post(path + '/diagnosis',json={'version':1,'initial_diagnosis':'تعمیر تغذیه'}).status_code == 200
    est = client.post(path + '/estimates',json={'version':2,'valid_until':'2099-01-01','duration_days':1,'customer_ceiling':'1000000','options':[{'title':'تعمیر','lines':[{'kind':'labor','title':'اجرت','qty':'1','unit_price':'100000'}]}]},headers={'Idempotency-Key':str(uuid4())})
    assert est.status_code == 201, est.text
    decision = client.post(path + '/estimates/' + est.json()['id'] + '/decision',json={'version':3,'decision':'approved','option_index':0,'method':'phone','customer_name':'مالک دستگاه','authorized_ceiling':'1000000'},headers={'Idempotency-Key':str(uuid4())})
    assert decision.status_code == 201, decision.text
    return client.get(path).json()


def test_parts_reserve_dispatch_consume_return_and_quality(client,db,user,approved_case):
    from datetime import date
    from decimal import Decimal
    from tests.factories import make_item,main_warehouse,other_warehouse
    from app.schemas.invoices import PurchaseInvoiceIn,PurchaseInvoiceLineIn
    from app.services.inventory import post_purchase_invoice,get_stock_qty
    item = make_item(db,name='قطعه تعمیر',unit='عدد')
    source,destination = main_warehouse(db),other_warehouse(db)
    post_purchase_invoice(db,PurchaseInvoiceIn(invoice_date=date.today(),warehouse_id=source.id,lines=[PurchaseInvoiceLineIn(item_id=item.id,qty=Decimal(10),unit_cost=Decimal(500))]),user)
    path = '/api/repair/cases/' + approved_case['id']
    version = lambda: client.get(path).json()['version']
    def action(part,kind,**kwargs):
        return client.post(path+'/parts/'+part+'/actions',json={'version':version(),'action':kind,'on':date.today().isoformat(),**kwargs},headers={'Idempotency-Key':str(uuid4())})
    requested = client.post(path+'/parts',json={'version':version(),'item_id':str(item.id),'qty':'2','unit_price':'10000','source_warehouse_id':str(source.id),'work_warehouse_id':str(destination.id)},headers={'Idempotency-Key':str(uuid4())})
    assert requested.status_code == 201, requested.text
    pid = requested.json()['id']
    assert action(pid,'consume',qty='1').status_code == 409
    assert action(pid,'reserve').status_code == 201
    assert get_stock_qty(db,item.id,source.id) == 10
    assert client.post(path+'/status',json={'version':version(),'status':'cancelled','reason':'لغو'}).status_code == 409
    dispatched = action(pid,'dispatch')
    assert dispatched.status_code == 201, dispatched.text
    assert get_stock_qty(db,item.id,source.id) == 8 and get_stock_qty(db,item.id,destination.id) == 2
    consumed = action(pid,'consume',qty='1')
    assert consumed.status_code == 201, consumed.text
    assert consumed.json()['document_type'] == 'warehouse_issue'
    quality = client.post(path+'/quality',json={'version':version(),'passed':True,'result':'آزمون نهایی'},headers={'Idempotency-Key':str(uuid4())})
    assert quality.status_code == 409
    assert action(pid,'return_unused',qty='1').status_code == 201
    assert get_stock_qty(db,item.id,source.id) == 9 and get_stock_qty(db,item.id,destination.id) == 0
    returned = action(pid,'return_consumed',qty='1',source_movement_id=consumed.json()['id'],reason='قطعه معیوب')
    assert returned.status_code == 201, returned.text
    assert get_stock_qty(db,item.id,source.id) == 10
    assert client.get(path).json()['parts'][0]['consumed_qty'] == '0E-8' or Decimal(client.get(path).json()['parts'][0]['consumed_qty']) == 0
    quality = client.post(path+'/quality',json={'version':version(),'passed':True,'result':'آزمون نهایی موفق'},headers={'Idempotency-Key':str(uuid4())})
    assert quality.status_code == 201, quality.text
    ready = client.post(path+'/status',json={'version':version(),'status':'ready','exceptional':True,'reason':'آزمون موفق'})
    assert ready.status_code == 200, ready.text


def test_customer_parts_and_encrypted_secret_boundary(client,db,monkeypatch,approved_case):
    from app.config import get_settings
    from app.models.repair import RepairDeviceSecret
    path = '/api/repair/cases/' + approved_case['id']
    version = lambda: client.get(path).json()['version']
    counts = (db.query(StockLedger).count(),db.query(JournalEntry).count())
    part = client.post(path+'/parts',json={'version':version(),'owner':'customer','title':'شارژر مشتری','qty':'1'},headers={'Idempotency-Key':str(uuid4())})
    assert part.status_code == 201, part.text
    assert (db.query(StockLedger).count(),db.query(JournalEntry).count()) == counts
    monkeypatch.setattr(get_settings(),'secrets_key','')
    password = 'device-password-test-only'
    payload = {'version':version(),'secret':password,'expires_days':1}
    assert client.put(path+'/device-secret',json=payload).status_code == 503
    assert db.query(RepairDeviceSecret).count() == 0
    monkeypatch.setattr(get_settings(),'secrets_key','isolated-test-key-never-use-in-production-2026')
    stored = client.put(path+'/device-secret',json=payload)
    assert stored.status_code == 200, stored.text
    assert password not in db.query(RepairDeviceSecret).one().ciphertext
    assert password not in client.get(path).text and password not in client.get(path+'/receipt').text
    viewed = client.post(path+'/device-secret/reveal',json={'reason':'نیاز برای آزمون'})
    assert viewed.status_code == 200 and viewed.json()['secret'] == password and viewed.headers['cache-control'] == 'no-store'
    quality = client.post(path+'/quality',json={'version':version(),'passed':True,'result':'پایان نیاز'},headers={'Idempotency-Key':str(uuid4())})
    assert quality.status_code == 201, quality.text
    assert db.query(RepairDeviceSecret).count() == 0
    assert client.post(path+'/device-secret/reveal',json={'reason':'نباید باقی باشد'}).status_code == 404


def test_real_case_invoice_multiple_consumptions_advance_delivery(client,db,user,approved_case):
    from datetime import date
    from decimal import Decimal
    from tests.factories import make_item,main_warehouse,other_warehouse
    from app.schemas.invoices import PurchaseInvoiceIn,PurchaseInvoiceLineIn
    from app.services.inventory import post_purchase_invoice,get_stock_qty
    from app.models.invoices import SalesInvoice
    from app.models.receipt import Receipt
    item=make_item(db,name='قطعه فاکتور تعمیر',unit='عدد')
    service=make_item(db,name='اجرت تعمیر',is_service=True)
    source,destination=main_warehouse(db),other_warehouse(db)
    on=date.today().isoformat();path='/api/repair/cases/'+approved_case['id']
    version=lambda:client.get(path).json()['version']
    def post(endpoint,**payload):
        response=client.post(path+endpoint,json={'version':version(),**payload},headers={'Idempotency-Key':str(uuid4())})
        assert response.status_code in {200,201},response.text
        return response.json()
    post_purchase_invoice(db,PurchaseInvoiceIn(invoice_date=date.today(),warehouse_id=source.id,lines=[PurchaseInvoiceLineIn(item_id=item.id,qty=10,unit_cost=500)]),user)
    post('/receipts',on=on,amount='10000',reason='پیش‌دریافت آزمایشی')
    part=post('/parts',item_id=str(item.id),qty='2',unit_price='10000',source_warehouse_id=str(source.id),work_warehouse_id=str(destination.id))
    for action in ('reserve','dispatch','consume','consume'):
        post('/parts/'+part['id']+'/actions',action=action,on=on,**({'qty':'1'} if action=='consume' else {}))
    post('/work',technician_id=str(user.id),service_id=str(service.id),description='تعمیر ثبت‌شده',customer_result='تعویض قطعه',work_minutes=30,charge_amount='50000')
    post('/quality',passed=True,result='آزمون موفق')
    post('/status',status='ready',exceptional=True,reason='آماده با کیفیت موفق')
    counts=(db.query(StockLedger).count(),get_stock_qty(db,item.id,source.id),get_stock_qty(db,item.id,destination.id))
    key=str(uuid4());payload={'version':version(),'on':on}
    response=client.post(path+'/invoice',json=payload,headers={'Idempotency-Key':key})
    assert response.status_code==201,response.text
    assert client.post(path+'/invoice',json=payload,headers={'Idempotency-Key':key}).json()['id']==response.json()['id']
    assert client.post(path+'/invoice',json={**payload,'version':version()},headers={'Idempotency-Key':str(uuid4())}).status_code==409
    assert (db.query(StockLedger).count(),get_stock_qty(db,item.id,source.id),get_stock_qty(db,item.id,destination.id))==counts
    invoice=db.query(SalesInvoice).one()
    assert invoice.total_amount==70000 and invoice.total_cost==1000 and len(invoice.lines)==3
    cost=client.get(path+'/report?financial=true')
    assert cost.status_code==200,cost.text
    assert cost.json()['financial']['revenue_net_rial']=='70000'
    assert cost.json()['financial']['parts_cost_rial']=='1000'
    assert cost.json()['financial']['recorded_margin_rial']=='69000'
    financial=client.get(path+'/finance').json()
    assert Decimal(financial['remaining_balance'])==60000
    post('/receipts',on=on,amount='60000',reason='باقی‌ماندهٔ تعمیر')
    assert db.query(Receipt).count()==2 and Decimal(client.get(path+'/finance').json()['remaining_balance'])==0
    delivery=post('/delivery',receiver_name='مالک آزمون',receiver_phone='09123456789',authorization='مالک با رسید پذیرش',accessories='همهٔ لوازم بازگردانده شد',care_instructions='پرهیز از رطوبت',checklist={'device':True,'accessories':True,'receiver_authorized':True})
    assert delivery['receiver_name']=='مالک آزمون' and client.get(path).json()['status']=='delivered'
    post('/close')
    assert client.get(path).json()['status']=='closed'
    receipt=client.get(path+'/delivery-receipt')
    assert receipt.status_code==200 and 'پرهیز از رطوبت' in receipt.text and '50000' not in receipt.text
    document=next(d for d in client.get(path+'/finance').json()['documents'] if d['document_type']=='sales_invoice')
    before_stock=db.query(StockLedger).count()
    corrected=post('/documents/'+document['id']+'/void',on=on,reason='اصلاح فاکتور آزمایشی با حفظ خروج مستقل')
    assert corrected['document_id']==document['document_id']
    assert db.query(StockLedger).count()==before_stock
    assert client.get(path).json()['status']=='delivered'
    assert Decimal(client.get(path+'/finance').json()['remaining_balance'])==-70000
    post('/invoice',on=on)
    assert db.query(SalesInvoice).count()==2 and db.query(StockLedger).count()==before_stock
    assert Decimal(client.get(path+'/finance').json()['remaining_balance'])==0
    post('/close')


def test_estimate_versions_approval_options_and_financial_independence(client, db, intake):
    counts = (db.query(StockLedger).count(),db.query(JournalEntry).count())
    row = admit(client,intake).json()
    path = '/api/repair/cases/' + row['id']
    diagnosis = client.post(path + '/diagnosis',json={'version':1,'initial_diagnosis':'ایراد تغذیه','final_diagnosis':'تعویض تغذیه'})
    assert diagnosis.status_code == 200, diagnosis.text
    assert diagnosis.json()['reported_issue'] == intake['reported_issue']
    payload = {'version':2,'valid_until':'2099-01-01','duration_days':3,'customer_ceiling':'1000000','options':[{'title':'گزینه اصلی','lines':[{'kind':'labor','title':'عیب‌یابی','qty':'1','unit_price':'250000'}]},{'title':'گزینه جایگزین','lines':[{'kind':'labor','title':'تعمیر','qty':'1','unit_price':'300000'}]}]}
    key = str(uuid4())
    est = client.post(path + '/estimates',json=payload,headers={'Idempotency-Key':key})
    assert est.status_code == 201, est.text
    assert est.json()['options'][1]['total'] == '300000'
    assert client.post(path + '/estimates',json=payload,headers={'Idempotency-Key':key}).json()['id'] == est.json()['id']
    choice = {'version':3,'decision':'approved','option_index':1,'method':'phone','customer_name':'مالک دستگاه','authorized_ceiling':'500000'}
    decidepath = path + '/estimates/' + est.json()['id'] + '/decision'
    assert client.post(decidepath,json={**choice,'authorized_ceiling':'1000001'},headers={'Idempotency-Key':str(uuid4())}).status_code == 422
    decision_key = str(uuid4())
    approved = client.post(decidepath,json=choice,headers={'Idempotency-Key':decision_key})
    assert approved.status_code == 201, approved.text
    assert approved.json()['authorized_ceiling'] == '500000'
    assert client.post(decidepath,json=choice,headers={'Idempotency-Key':decision_key}).json()['id'] == approved.json()['id']
    newer = client.post(path + '/estimates',json={**payload,'version':4},headers={'Idempotency-Key':str(uuid4())})
    assert newer.status_code == 201 and newer.json()['version'] == 2
    assert client.post(path + '/status',json={'version':5,'status':'repairing','exceptional':True,'reason':'شروع'}).status_code == 409
    rejectpath = path + '/estimates/' + newer.json()['id'] + '/decision'
    rejected = client.post(rejectpath,json={'version':5,'decision':'rejected','method':'in_person','customer_name':'مالک دستگاه','reason':'هزینه بالا'},headers={'Idempotency-Key':str(uuid4())})
    assert rejected.status_code == 201
    current = client.get(path).json()
    assert len(current['estimates']) == 2 and len(current['estimate_decisions']) == 2
    assert (db.query(StockLedger).count(),db.query(JournalEntry).count()) == counts


def test_workflow_assignment_task_and_gates(client, intake, user):
    row = admit(client,intake).json()
    path = '/api/repair/cases/' + row['id']
    assert client.post(path + '/status',json={'version':1,'status':'repairing'}).status_code == 409
    assert client.post(path + '/status',json={'version':1,'status':'delivered','exceptional':True,'reason':'غیرمجاز'}).status_code == 409
    assigned = client.post(path + '/assignment',json={'version':1,'user_id':str(user.id),'reason':'ارجاع اولیه'})
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()['assigned_to_id'] == str(user.id)
    assert len(client.get('/api/repair/cases?mine=true').json()['items']) == 1
    diagnosed = client.post(path + '/status',json={'version':2,'status':'diagnosing'})
    assert diagnosed.status_code == 200 and diagnosed.json()['version'] == 3
    assert client.post(path + '/status',json={'version':2,'status':'repairing'}).status_code == 409
    assert client.post(path + '/status',json={'version':3,'status':'awaiting_part'}).status_code == 422
    task_payload = {'version':3,'title':'بررسی اولیه','internal_note':'اطلاعات داخلی حساس'}
    key = str(uuid4())
    task = client.post(path + '/tasks',json=task_payload,headers={'Idempotency-Key':key})
    assert task.status_code == 201, task.text
    replay = client.post(path + '/tasks',json=task_payload,headers={'Idempotency-Key':key})
    assert replay.json()['id'] == task.json()['id']
    assert 'اطلاعات داخلی حساس' not in client.get(path + '/receipt').text
    taskpath = path + '/tasks/' + task.json()['id'] + '/status'
    assert client.post(taskpath,json={'version':4,'status':'done'}).status_code == 409
    started = client.post(taskpath,json={'version':4,'status':'working'})
    assert started.status_code == 200 and started.json()['tasks'][0]['started_at']
    done = client.post(taskpath,json={'version':5,'status':'done'})
    assert done.status_code == 200 and done.json()['tasks'][0]['completed_at']
    wait = client.post(path + '/status',json={'version':6,'status':'awaiting_part','reason':'قطعه موجود نیست'})
    assert wait.status_code == 200 and wait.json()['pause_reason'] == 'قطعه موجود نیست'


def test_real_concurrent_numbering_and_identical_retry(tenant_id, user):
    with tenant_session(tenant_id) as db:
        branch = RepairBranch(name='concurrency-' + str(uuid4()))
        kind = RepairDeviceType(name='concurrency-' + str(uuid4()))
        contact = Contact(name='concurrency-customer', is_customer=True)
        db.add_all([branch,kind,contact]); db.flush()
        payload = AdmissionIn(contact_id=contact.id, branch_id=branch.id, device={'type_id':kind.id,'model':'همزمان'}, reported_issue='آزمون همزمان', admission_date='2026-10-06', storage_location='آزمایش', terms='آزمایشی', approval_method='in_person')
        db.commit()

    def run(key):
        with tenant_session(tenant_id) as db:
            membership = db.query(Membership).filter_by(user_id=user.id, tenant_id=tenant_id).one()
            principal = Principal(db.get(User,user.id), membership)
            request = Request({'type':'http','headers':[(b'idempotency-key',key.encode())]})
            row = idempotent(db, request, principal.user, operation='repair.admission', payload=payload,
                run=lambda: svc.create(db, principal,payload), replay=lambda rid: svc.case(db,principal,rid))
            result = (str(row.id),row.number)
            db.commit()

            return result
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=4) as pool:
        repeated = list(pool.map(run,[key]*4))
        distinct = list(pool.map(run,[str(uuid4()) for _ in range(4)]))
    assert len(set(repeated)) == 1
    numbers = sorted([repeated[0][1]] + [r[1] for r in distinct])
    assert numbers == list(range(numbers[0],numbers[0]+5))
    with tenant_session(tenant_id) as db:
        assert db.query(RepairCase).filter_by(branch_id=payload.branch_id).count() == 5
        # مستقل از ترتیب اجرای سایر آزمون‌ها؛ cleanup فقط دادهٔ ساخته‌شده در همین آزمون.
        from app.models.repair import RepairEvent
        from app.models.idempotency import IdempotencyKey
        ids = [r[0] for r in distinct] + [repeated[0][0]]
        db.query(RepairEvent).filter(RepairEvent.case_id.in_(ids)).delete(synchronize_session=False)
        devices = [r.device_id for r in db.query(RepairCase).filter(RepairCase.id.in_(ids)).all()]
        db.query(IdempotencyKey).filter(IdempotencyKey.resource_id.in_(ids)).delete(synchronize_session=False)
        db.query(RepairCase).filter(RepairCase.id.in_(ids)).delete(synchronize_session=False)
        db.query(RepairDevice).filter(RepairDevice.id.in_(devices)).delete(synchronize_session=False)
        db.query(RepairDeviceType).filter_by(id=payload.device.type_id).delete()
        db.query(RepairBranch).filter_by(id=payload.branch_id).delete()
        db.query(Contact).filter_by(id=payload.contact_id).delete()
        db.commit()


def test_notification_unavailable_template_versions_and_replay(client,db,intake,monkeypatch):
    from app.services import repair_notifications as notices
    from app.models.repair import RepairNotification, RepairMessageTemplate
    monkeypatch.setattr(notices,'configured',lambda:False)
    bad=client.post('/api/repair/message-templates',json={'kind':'admission','body':'{customer.__class__}'})
    assert bad.status_code==422
    for text in ('پذیرش {number} برای {customer}','نسخه تازه {number}'):
        response=client.post('/api/repair/message-templates',json={'kind':'admission','body':text,'branch_id':intake['branch_id']})
        assert response.status_code==201,response.text
    row=admit(client,intake).json();path='/api/repair/cases/'+row['id']
    notification=db.query(RepairNotification).one()
    assert notification.status=='unavailable' and notification.attempt_count==0
    assert notification.body.startswith('نسخه تازه') and db.query(RepairMessageTemplate).count()==2
    assert 'قفسه' not in notification.body
    key=str(uuid4());payload={'version':row['version'],'kind':'admission'}
    first=client.post(path+'/notifications',json=payload,headers={'Idempotency-Key':key})
    assert first.status_code==201,first.text
    assert client.post(path+'/notifications',json=payload,headers={'Idempotency-Key':key}).json()['id']==first.json()['id']
    version=client.get(path).json()['version']
    assert client.post(path+'/notifications/'+first.json()['id']+'/retry',json={'version':version,'reason':'سرویس هنوز آماده نیست'}).status_code==503
    history=client.get(path+'/notifications').json()
    assert history['sms_available'] is False and all(n['status']!='accepted' for n in history['messages'])
    assert client.post(path+'/notifications/'+first.json()['id']+'/cancel',json={'version':version}).status_code==200


def test_notification_worker_committed_claim_once_and_uncertain_no_auto_retry(tenant_id,user,monkeypatch):
    from datetime import datetime,timedelta,timezone
    from threading import Lock
    from app.models.repair import RepairNotification,RepairNotificationAttempt,RepairMessageTemplate,RepairEvent
    from app.services import repair_notifications as notices
    from app.schemas.repair import RepairTemplateIn
    monkeypatch.setattr(notices,'configured',lambda:True)
    case_id=None
    with tenant_session(tenant_id) as db:
        branch=RepairBranch(name='notice-'+str(uuid4()));category=RepairDeviceType(name='notice-'+str(uuid4()))
        contact=Contact(name='مشتری صف آزمایشی',is_customer=True,phone='09123456789')
        db.add_all([branch,category,contact]);db.flush()
        ids=(branch.id,category.id,contact.id)
        principal=Principal(db.get(User,user.id),db.query(Membership).filter_by(user_id=user.id,tenant_id=tenant_id).one())
        notices.save_template(db,principal,RepairTemplateIn(branch_id=branch.id,kind='admission',body='پذیرش {number}'))
        row=svc.create(db,principal,AdmissionIn(contact_id=contact.id,branch_id=branch.id,device={'type_id':category.id,'model':'آزمایشی'},reported_issue='آزمون صف',admission_date='2026-10-06',storage_location='آزمایش',terms='آزمایشی',approval_method='in_person'))
        case_id,device_id=row.id,row.device_id
        notice_id=db.query(RepairNotification).filter_by(case_id=case_id).one().id
        db.commit()
    calls=[];guard=Lock()
    def carrier(phone,body):
        # دریافت حامل فقط پس از commit وضعیت ارسال قابل مشاهده است.
        with tenant_session(tenant_id) as db:
            n=db.get(RepairNotification,notice_id)
            assert n.status=='sending' and n.attempt_count==1
        with guard: calls.append((phone,body))
        return True
    factory=lambda:tenant_session(tenant_id)
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _:notices.process_one(factory,tenant_id,sender=carrier),range(3)))
        assert len(calls)==1
        with tenant_session(tenant_id) as db:
            notification=db.get(RepairNotification,notice_id)
            assert notification.status=='accepted'
            assert db.query(RepairNotificationAttempt).filter_by(notification_id=notice_id).count()==1
            stale=notices.enqueue(db,db.get(RepairCase,case_id),'admission','stale')
            stale.status='sending';stale.attempt_count=1;stale.claimed_at=datetime.now(timezone.utc)-timedelta(minutes=10)
            db.add(RepairNotificationAttempt(notification_id=stale.id,number=1,outcome='sending',result='آزمون قطع فرایند'))
            stale_id=stale.id;db.commit()
        assert notices.process_one(factory,tenant_id,sender=carrier) is False
        assert len(calls)==1
        with tenant_session(tenant_id) as db:
            assert db.get(RepairNotification,stale_id).status=='uncertain'
    finally:
        with tenant_session(tenant_id) as db:
            notice_ids=[r.id for r in db.query(RepairNotification).filter_by(case_id=case_id)]
            db.query(RepairNotificationAttempt).filter(RepairNotificationAttempt.notification_id.in_(notice_ids)).delete(synchronize_session=False)
            db.query(RepairNotification).filter_by(case_id=case_id).delete()
            db.query(RepairMessageTemplate).filter_by(branch_id=ids[0]).delete()
            db.query(RepairEvent).filter_by(case_id=case_id).delete()
            db.query(RepairCase).filter_by(id=case_id).delete()
            db.query(RepairDevice).filter_by(id=device_id).delete()
            db.query(RepairDeviceType).filter_by(id=ids[1]).delete()
            db.query(RepairBranch).filter_by(id=ids[0]).delete()
            db.query(Contact).filter_by(id=ids[2]).delete()
            db.commit()


def test_customer_portal_case_scope_hidden_fields_file_visibility_and_revocation(client,db,intake):
    from urllib.parse import urlsplit,parse_qs
    from app.models.repair import RepairPortalToken
    row=admit(client,intake).json();path='/api/repair/cases/'+row['id']
    made=client.post(path+'/portal-links',json={'version':row['version'],'expires_days':7})
    assert made.status_code==201,made.text
    credential=parse_qs(urlsplit(made.json()['url']).fragment)['token'][0]
    auth={'Authorization':'RepairPortal '+credential}
    stored=db.query(RepairPortalToken).one()
    assert credential not in stored.token_hash and credential.split('.')[1] not in stored.token_hash
    public=client.get('/api/repair-portal/case',headers=auth)
    assert public.status_code==200,public.text
    assert public.headers['cache-control']=='no-store'
    assert 'storage_location' not in public.text and 'قفسه الف' not in public.text and 'created_by_id' not in public.text
    assert public.json()['number']==row['number']
    assert client.get('/api/repair-portal/case').status_code==404
    assert client.get('/api/repair-portal/case',headers={'Authorization':'RepairPortal '+credential[:-1]+('X' if credential[-1]!='X' else 'Y')}).status_code==404
    file=client.post(path+'/attachments',files={'file':('private.pdf',b'%PDF-private-test','application/pdf')})
    assert file.status_code==200,file.text
    file_id=file.json()['id']
    assert client.get('/api/repair-portal/attachments/'+file_id,headers=auth).status_code==404
    change=client.put(path+'/attachments/'+file_id+'/visibility',json={'version':client.get(path).json()['version'],'customer_visible':True})
    assert change.status_code==200,change.text
    assert client.get('/api/repair-portal/attachments/'+file_id,headers=auth).content==b'%PDF-private-test'
    second=admit(client,{**intake,'device':{**intake['device'],'serial':'OTHER'}}).json()
    other=client.post('/api/repair/cases/'+second['id']+'/attachments',files={'file':('other.pdf',b'%PDF-other-test','application/pdf')}).json()
    assert client.get('/api/repair-portal/attachments/'+other['id'],headers=auth).status_code==404
    uploaded=client.post('/api/repair-portal/attachments',headers=auth,files={'file':('customer.png',b'\x89PNG\r\n\x1a\ncustomer-test','image/png')})
    assert uploaded.status_code==201,uploaded.text
    assert client.get('/api/repair-portal/attachments/'+uploaded.json()['id'],headers=auth).status_code==200
    assert client.get('/api/repair-portal/receipt',headers=auth).status_code==200
    revoked=client.post(path+'/portal-links/'+made.json()['id']+'/revoke',json={'version':client.get(path).json()['version']})
    assert revoked.status_code==200,revoked.text
    assert client.get('/api/repair-portal/case',headers=auth).status_code==404
    assert client.get('/api/repair-portal/attachments/'+file_id,headers=auth).status_code==404


def test_portal_latest_estimate_exact_decision_retry_and_customer_messages(client,db,intake):
    from datetime import date,timedelta
    from urllib.parse import urlsplit,parse_qs
    from app.models.repair import RepairEstimateDecision,RepairCustomerMessage,RepairPortalToken
    row=admit(client,intake).json();path='/api/repair/cases/'+row['id']
    version=lambda:client.get(path).json()['version']
    diagnosed=client.post(path+'/diagnosis',json={'version':version(),'initial_diagnosis':'یادداشت داخلی نباید عمومی شود','final_diagnosis':'آزمون داخلی'})
    assert diagnosed.status_code==200,diagnosed.text
    def estimate(title):
        response=client.post(path+'/estimates',headers={'Idempotency-Key':str(uuid4())},json={'version':version(),'valid_until':(date.today()+timedelta(days=3)).isoformat(),'duration_days':2,'options':[{'title':title,'lines':[{'kind':'labor','title':'خدمت','qty':'1','unit_price':'12345'}]}]})
        assert response.status_code==201,response.text
        return response.json()
    old=estimate('گزینه قبلی')
    made=client.post(path+'/portal-links',json={'version':version(),'expires_days':7}).json()
    credential=parse_qs(urlsplit(made['url']).fragment)['token'][0]
    auth={'Authorization':'RepairPortal '+credential,'Idempotency-Key':str(uuid4())}
    new=estimate('گزینه تازه')
    data={'version':version(),'estimate_id':old['id'],'decision':'approved','option_index':0,'customer_name':'مالک دستگاه'}
    assert client.post('/api/repair-portal/decision',headers=auth,json=data).status_code==409
    data['estimate_id']=new['id']
    accepted=client.post('/api/repair-portal/decision',headers=auth,json=data)
    assert accepted.status_code==201,accepted.text
    assert client.post('/api/repair-portal/decision',headers=auth,json=data).json()['id']==accepted.json()['id']
    decision=db.query(RepairEstimateDecision).one()
    assert decision.recorded_by_id is None and decision.portal_token_id and decision.authorized_ceiling==12345
    public=client.get('/api/repair-portal/case',headers=auth)
    assert 'یادداشت داخلی' not in public.text and 'آزمون داخلی' not in public.text
    assert public.json()['estimate']['decision']['decision']=='approved'
    auth['Idempotency-Key']=str(uuid4())
    message={'kind':'complaint','name':'مالک دستگاه','body':'درخواست پیگیری','rating':None}
    sent=client.post('/api/repair-portal/messages',headers=auth,json=message)
    assert sent.status_code==201,sent.text
    assert client.post('/api/repair-portal/messages',headers=auth,json=message).json()['id']==sent.json()['id']
    assert db.query(RepairCustomerMessage).count()==1
    auth['Idempotency-Key']=str(uuid4())
    assert client.post('/api/repair-portal/messages',headers=auth,json={**message,'kind':'survey','rating':5}).status_code==409
    assert len(client.get(path+'/customer-messages').json())==1
    from datetime import datetime,timezone
    token=db.query(RepairPortalToken).one();token.expires_at=datetime.now(timezone.utc)-timedelta(days=1);db.flush()
    assert client.get('/api/repair-portal/case',headers=auth).status_code==404


def test_online_payment_server_verified_only_once_and_accounting_recovery(client,db,user,approved_case,monkeypatch):
    from datetime import date
    from urllib.parse import urlsplit,parse_qs
    from tests.factories import make_item
    from app.models.storefront_native import PaymentGateway
    from app.models.pos_terminal import PosTerminal
    from app.models.banking import BankAccount
    from app.services.common import get_account
    from app.services import chart_codes as cc
    from app.models.repair import RepairPaymentIntent
    from app.models.receipt import Receipt
    from app.config import get_settings
    from app.services import repair_payments as online
    from app.services.payment_providers import StartResult,CallbackParse
    path='/api/repair/cases/'+approved_case['id'];version=lambda:client.get(path).json()['version']
    def post(endpoint,**data):
        response=client.post(path+endpoint,headers={'Idempotency-Key':str(uuid4())},json={'version':version(),**data})
        assert response.status_code in {200,201},response.text
        return response.json()
    service=make_item(db,name='خدمت پرداخت اینترنتی',is_service=True)
    post('/work',technician_id=str(user.id),service_id=str(service.id),description='تعمیر',work_minutes=10,charge_amount='12345')
    post('/quality',passed=True,result='آزمون موفق')
    post('/status',status='ready',exceptional=True,reason='پایان آزمون')
    post('/invoice',on=date.today().isoformat())
    made=post('/portal-links',expires_days=7)
    credential=parse_qs(urlsplit(made['url']).fragment)['token'][0]
    auth={'Authorization':'RepairPortal '+credential,'Idempotency-Key':str(uuid4())}
    no_config=client.post('/api/repair-portal/payments',headers=auth,json={'version':version(),'amount_rial':'12345'})
    assert no_config.status_code==503
    dummy_merchant='dummy-merchant-only-for-isolated-test'
    gateway=PaymentGateway(provider='zarinpal',merchant_id=dummy_merchant,is_active=True,config={'sandbox':True})
    bank=BankAccount(name='بانک تسویه آزمایشی',gl_account_id=get_account(db,cc.BANK).id)
    db.add(bank);db.flush()
    terminal=PosTerminal(label='وجوه در راه درگاه آزمایشی',currency_code='IRR',is_active=True,bank_account_id=bank.id)
    db.add_all([gateway,terminal]);db.flush()
    monkeypatch.setattr(get_settings(),'secrets_key','isolated-payment-encryption-test-key-2026')
    configured=client.put('/api/repair/branches/'+approved_case['branch_id']+'/online-payment',json={'gateway_id':str(gateway.id),'pos_terminal_id':str(terminal.id),'enabled':True})
    assert configured.status_code==200,configured.text
    class FakeProvider:
        accepted=False
        starts=[]
        verifies=[]
        def start(self,**kw):
            self.starts.append(kw)
            return StartResult(authority='test-authority-1',redirect_url='https://example.invalid/test-payment')
        def parse_callback(self,params): return CallbackParse(authority=params.get('Authority',''),ok_signal=params.get('Status')=='OK')
        def verify(self,**kw):
            self.verifies.append(kw)
            return self.accepted,'TEST-REF-1' if self.accepted else ''
    provider=FakeProvider();monkeypatch.setattr(online,'get_provider',lambda _:provider)
    public=client.get('/api/repair-portal/case',headers=auth).json()
    assert public['online_payment_available'] is True and public['remaining_balance_rial']=='12345'
    payload={'version':version(),'amount_rial':'12345'}
    started=client.post('/api/repair-portal/payments',headers=auth,json=payload)
    assert started.status_code==201,started.text
    assert client.post('/api/repair-portal/payments',headers=auth,json=payload).json()['id']==started.json()['id']
    assert len(provider.starts)==1 and db.query(Receipt).count()==0
    intent=db.query(RepairPaymentIntent).one()
    assert dummy_merchant not in intent.merchant_ciphertext and dummy_merchant not in client.get('/api/repair-portal/case',headers=auth).text
    assert provider.starts[0]['amount_rial']==12345
    callback=f'/api/repair-payments/callback/{intent.tenant_id}/{intent.id}'
    assert client.get(callback+'?Authority=fake&Status=OK').status_code==400
    forged=client.get(callback+'?Authority=test-authority-1&Status=OK')
    assert forged.status_code==200 and db.query(Receipt).count()==0
    assert len(provider.verifies)==1 and intent.status=='verification_failed'
    provider.accepted=True
    actual_post=online.post_receipt
    from fastapi import HTTPException
    def accounting_failure(*args): raise HTTPException(409,'خطای حساب آزمایشی')
    monkeypatch.setattr(online,'post_receipt',accounting_failure)
    verified=client.get(callback+'?Authority=test-authority-1&Status=OK')
    assert verified.status_code==200 and 'نیاز دارد' in verified.text
    assert db.query(Receipt).count()==0 and intent.verified_at and intent.status=='accounting_pending'
    monkeypatch.setattr(online,'post_receipt',actual_post)
    # مرچنت فعلی می‌تواند عوض شود؛ verify با snapshot رمزگذاری‌شده انجام شده است.
    gateway.merchant_id='changed-test-only';db.flush()
    posted=client.get(callback+'?Authority=test-authority-1&Status=OK')
    assert posted.status_code==200,posted.text
    assert intent.status=='posted' and db.query(Receipt).count()==1
    assert client.get(callback+'?Authority=test-authority-1&Status=OK').status_code==200
    assert db.query(Receipt).count()==1 and len(provider.verifies)==2
    assert provider.verifies[-1]['merchant_id']==dummy_merchant
    assert client.get(path+'/finance').json()['remaining_balance']=='0'
    from app.models.treasury import TreasuryTransaction
    receipt=db.query(Receipt).one()
    card=db.query(TreasuryTransaction).filter_by(receipt_id=receipt.id,paid_via='pos_terminal').one()
    assert card.pos_terminal_id==terminal.id and card.amount==12345
    from app.models.accounting import JournalLine
    clearing=get_account(db,cc.POS_CLEARING)
    lines=db.query(JournalLine).filter_by(entry_id=receipt.journal_entry_id).all()
    assert sum(l.debit for l in lines if l.account_id==clearing.id)==12345
    assert not any(l.account_id==bank.gl_account_id and l.debit for l in lines)
    public=client.get('/api/repair-portal/case',headers=auth).json()
    assert len(public['documents'])==2
    for document in public['documents']:
        printed=client.get('/api/repair-portal/documents/'+document['id'],headers=auth)
        assert printed.status_code==200,printed.text
        assert 'merchant' not in printed.text and 'قفسه الف' not in printed.text
    assert client.get('/api/repair-portal/documents/'+str(uuid4()),headers=auth).status_code==404


def test_warranty_revisit_expiry_and_charge_guard(client, db, user, intake, approved_case):
    from app.models.repair import RepairEvent, RepairWarrantyClaim
    path='/api/repair/cases/'+approved_case['id']
    def post(suffix, **data):
        return client.post(path+suffix,json={'version':client.get(path).json()['version'],**data},headers={'Idempotency-Key':str(uuid4())})
    work=post('/work',technician_id=str(user.id),description='تنظیم',work_minutes=10,charge_amount='0')
    assert work.status_code==201,work.text
    warranty={'scope':'service','source_id':work.json()['id'],'title':'ضمانت تنظیم','valid_from':'2026-10-06','valid_until':'2026-11-06','terms':'همان خرابی'}
    assert post('/warranties',**warranty).status_code==409
    assert post('/status',status='diagnosing').status_code==200
    assert post('/status',status='repairing').status_code==200
    assert post('/status',status='testing').status_code==200
    assert post('/quality',passed=True,result='موفق').status_code==201
    assert post('/status',status='ready').status_code==200
    delivered=post('/delivery',receiver_name='مالک',receiver_phone='09123456789',authorization='مالک با رسید',accessories='شارژر',care_instructions='پرهیز از ضربه',checklist={'device':True,'accessories':True,'receiver_authorized':True})
    assert delivered.status_code==201,delivered.text
    issued=post('/warranties',**warranty)
    assert issued.status_code==201,issued.text
    old=client.get(path).json(); count=db.query(RepairEvent).filter_by(case_id=old['id']).count()
    admission={**intake,'device':None,'device_id':old['device_id'],'admission_date':'2026-10-07'}
    data={'warranty_id':issued.json()['id'],'admission':admission,'classification':'repeat_fault','responsibility':'company','cost_policy':'covered','reason':'ایراد دوباره'}
    assert client.post(path+'/revisits',json={**data,'admission':{**admission,'admission_date':'2027-01-01'}},headers={'Idempotency-Key':str(uuid4())}).status_code==422
    key=str(uuid4());visit=client.post(path+'/revisits',json=data,headers={'Idempotency-Key':key})
    assert visit.status_code==201,visit.text
    assert client.post(path+'/revisits',json=data,headers={'Idempotency-Key':key}).json()['id']==visit.json()['id']
    assert visit.json()['device_id']==old['device_id'] and visit.json()['number']!=old['number']
    assert client.get(path).json()['version']==old['version'] and db.query(RepairEvent).filter_by(case_id=old['id']).count()==count
    assert db.query(RepairWarrantyClaim).count()==1
    newpath='/api/repair/cases/'+visit.json()['id']
    assert client.get(newpath+'/warranties').json()['origin']['original_case_id']==old['id']
    assert client.post(newpath+'/work',json={'version':visit.json()['version'],'technician_id':str(user.id),'description':'اجرت','work_minutes':10,'charge_amount':'100'},headers={'Idempotency-Key':str(uuid4())}).status_code==409


@pytest.mark.parametrize('mode,value,revised_value',[('percent_labor','10','20'),('fixed_case','1000','2000'),('per_operation','1000','2000')])
def test_technician_fee_versioned_rule_real_payable_and_deduplication(client,db,user,approved_case,mode,value,revised_value):
    from tests.factories import make_item
    from app.models.invoices import PurchaseInvoice
    service=make_item(db,name='خدمت سهم تکنسین',is_service=True)
    payee=client.post('/api/contacts',json={'name':'تکنسین طرف حساب','type':'supplier'}).json()
    path='/api/repair/cases/'+approved_case['id']
    def post(suffix,**data):
        return client.post(path+suffix,json={'version':client.get(path).json()['version'],**data},headers={'Idempotency-Key':str(uuid4())})
    assert post('/work',technician_id=str(user.id),service_id=str(service.id),description='عملیات واقعی',work_minutes=10,charge_amount='10000').status_code==201
    assert post('/status',status='diagnosing').status_code==200
    assert post('/status',status='unrepairable',reason='تعمیر ممکن نشد').status_code==200
    rule={'technician_id':str(user.id),'mode':mode,'value':value,'payee_id':payee['id'],'service_id':str(service.id),'reason':'ده درصد اجرت ثبت‌شده'}
    r=client.post('/api/repair/fee-rules',json=rule,headers={'Idempotency-Key':str(uuid4())})
    assert r.status_code==201,r.text
    draft=post('/technician-fees',technician_id=str(user.id))
    assert draft.status_code==201,draft.text
    assert draft.json()['amount_rial']=='1000' and draft.json()['purchase_invoice_id'] is None
    revised=client.post('/api/repair/fee-rules',json={**rule,'value':revised_value,'reason':'قاعده جدید'},headers={'Idempotency-Key':str(uuid4())})
    assert revised.status_code==201 and revised.json()['version']==2
    assert post('/technician-fees/'+draft.json()['id']+'/approve',on='2026-10-06').status_code==409
    current=post('/technician-fees',technician_id=str(user.id))
    assert current.status_code==201 and current.json()['amount_rial']=='2000',current.text
    key=str(uuid4());body={'version':client.get(path).json()['version'],'on':'2026-10-06'}
    url=path+'/technician-fees/'+current.json()['id']+'/approve'
    posted=client.post(url,json=body,headers={'Idempotency-Key':key})
    assert posted.status_code==200,posted.text
    assert client.post(url,json=body,headers={'Idempotency-Key':key}).json()['purchase_invoice_id']==posted.json()['purchase_invoice_id']
    assert db.query(PurchaseInvoice).count()==1
    invoice=db.get(PurchaseInvoice,posted.json()['purchase_invoice_id'])
    assert invoice.kind=='service' and invoice.journal_entry_id is not None and invoice.total_amount==2000
    fees=client.get(path+'/technician-fees').json()
    payable=next(f for f in fees if f['id']==current.json()['id'])
    assert payable['status']=='payable' and payable['remaining_rial']=='2000'
    report=client.get(path+'/report?financial=true')
    assert report.status_code==200,report.text
    assert report.json()['financial']['technician_cost_rial']=='2000'
    assert report.json()['financial']['revenue_net_rial']=='0'
    assert report.json()['financial']['recorded_margin_rial']=='-2000'
    assert client.get('/api/repair/reports?financial=true&limit=1').status_code==200
    assert post('/delivery',receiver_name='مالک',receiver_phone='09123456789',authorization='مالک',accessories='شارژر',care_instructions='مراقبت',checklist={'device':True,'accessories':True,'receiver_authorized':True}).status_code==409


def test_field_request_skill_capacity_actual_dispatch_and_admission(client,db,user,intake):
    initial_journals=db.query(JournalEntry).count()
    payload={'branch_id':intake['branch_id'],'contact_id':intake['contact_id'],'type_id':intake['device']['type_id'],'device_description':'رایانه مشتری','reported_issue':'خاموشی','address':'نشانی آزمایشی','coordinator_name':'هماهنگ‌کننده','coordinator_phone':'09123456789'}
    def create():
        result=client.post('/api/repair/service-requests',json=payload,headers={'Idempotency-Key':str(uuid4())})
        assert result.status_code==201,result.text
        return result.json()
    first=create();second=create();path='/api/repair/service-requests/'+first['id']
    slot={'technician_id':str(user.id),'starts_at':'2026-10-07T09:00:00+03:30','ends_at':'2026-10-07T10:00:00+03:30'}
    def schedule(r,**changes):
        return client.post('/api/repair/service-requests/'+r['id']+'/appointments',json={'version':r['version'],**slot,**changes},headers={'Idempotency-Key':str(uuid4())})
    assert schedule(first).status_code==422
    assert client.put('/api/repair/technicians/'+str(user.id)+'/skills',json={'type_ids':[payload['type_id']]}).status_code==200
    appointment=schedule(first)
    assert appointment.status_code==201,appointment.text
    assert schedule(second).status_code==409
    assert schedule(second,starts_at='2026-10-07T10:00:00+03:30',ends_at='2026-10-07T11:00:00+03:30').status_code==201
    assert len(client.get('/api/repair/service-requests?mine=true').json()['items'])==2
    version=2
    for status in ('dispatched','onsite','completed'):
        updated=client.post(path+'/appointments/'+appointment.json()['id']+'/status',json={'version':version,'status':status,'result':'نتیجه واقعی '+status})
        assert updated.status_code==200,updated.text
        version+=1
    assert db.query(RepairCase).count()==0 and db.query(JournalEntry).count()==initial_journals
    key=str(uuid4());admission={'version':version,'admission':intake}
    result=client.post(path+'/admission',json=admission,headers={'Idempotency-Key':key})
    assert result.status_code==201,result.text
    assert client.post(path+'/admission',json=admission,headers={'Idempotency-Key':key}).json()['id']==result.json()['id']
    assert db.query(RepairCase).count()==1
    assert any(e['action']=='field_request_linked' for e in client.get('/api/repair/cases/'+result.json()['id']).json()['events'])


def test_device_transport_handover_and_branch_receipt(client,db,intake):
    initial_journals=db.query(JournalEntry).count()
    row=admit(client,intake).json();path='/api/repair/cases/'+row['id']
    target=client.post('/api/repair/branches',json={'name':'شعبه مقصد'}).json()
    key=str(uuid4());payload={'version':1,'to_branch_id':target['id'],'destination_location':'قفسه مقصد','carrier_name':'حامل اول','reason':'ارسال برای تعمیر'}
    transfer=client.post(path+'/custody',json=payload,headers={'Idempotency-Key':key})
    assert transfer.status_code==201,transfer.text
    assert client.post(path+'/custody',json=payload,headers={'Idempotency-Key':key}).json()['id']==transfer.json()['id']
    assert client.get(path).json()['branch_id']==intake['branch_id']
    assert client.put(path+'/location',json={'version':2,'storage_location':'محل ساختگی در مسیر'}).status_code==409
    assert client.post(path+'/status',json={'version':2,'status':'diagnosing'}).status_code==409
    leg=client.post(path+'/custody/'+transfer.json()['id']+'/handover',json={'version':2,'carrier_name':'حامل دوم','location':'ایستگاه واسط','confirmation':'تحویل با تطبیق رسید'},headers={'Idempotency-Key':str(uuid4())})
    assert leg.status_code==201,leg.text
    received=client.post(path+'/custody/'+transfer.json()['id']+'/receive',json={'version':3,'receiver_name':'مسئول مقصد','confirmation':'دستگاه و شارژر دریافت شد'},headers={'Idempotency-Key':str(uuid4())})
    assert received.status_code==200,received.text
    current=client.get(path).json()
    assert current['branch_id']==target['id'] and current['storage_location']=='قفسه مقصد'
    assert client.get(path+'/custody').json()[0]['legs'][0]['from_carrier']=='حامل اول'
    assert db.query(StockLedger).count()==0 and db.query(JournalEntry).count()==initial_journals


def test_loan_device_real_asset_custody_and_unique_return(client,db,user,intake):
    initial_journals=db.query(JournalEntry).count()
    from datetime import date
    from app.models.assets import FixedAsset,AssetAssignment
    from app.schemas.assets import AssetAssignmentIn,AssetDisposalIn
    from app.services import assets
    from fastapi import HTTPException
    asset=FixedAsset(name='دستگاه جایگزین',acquired_date=date.today(),cost=0,useful_life_months=12,created_by_id=user.id)
    db.add(asset);db.flush()
    custodian=client.post('/api/contacts',json={'name':'جمعدار','type':'supplier'}).json()
    first=admit(client,intake).json();second=admit(client,intake).json();path='/api/repair/cases/'+first['id']
    data={'version':1,'asset_id':str(asset.id),'receiver_name':'مالک','authorization':'مالک با رسید','accessories':'شارژر','condition_out':'سالم','due_date':'2099-01-01','return_custodian_id':custodian['id'],'return_location':'قفسه جایگزین'}
    key=str(uuid4());loan=client.post(path+'/loans',json=data,headers={'Idempotency-Key':key})
    assert loan.status_code==201,loan.text
    assert client.post(path+'/loans',json=data,headers={'Idempotency-Key':key}).json()['id']==loan.json()['id']
    db.refresh(asset);assert str(asset.custodian_id)==intake['contact_id']
    assert db.query(AssetAssignment).count()==1 and db.query(JournalEntry).count()==initial_journals
    assert client.post('/api/repair/cases/'+second['id']+'/loans',json=data,headers={'Idempotency-Key':str(uuid4())}).status_code==409
    with pytest.raises(HTTPException) as blocked:
        assets.transfer_asset(db,asset.id,AssetAssignmentIn(assignment_date=date.today(),to_location='جای دیگر'),user)
    assert blocked.value.status_code==409
    with pytest.raises(HTTPException) as blocked:
        assets.dispose_asset(db,asset.id,AssetDisposalIn(disposal_date=date.today(),disposal_type='scrap'),user)
    assert blocked.value.status_code==409
    key=str(uuid4());body={'version':2,'condition_in':'سالم','confirmation':'دستگاه و شارژر دریافت شد'}
    url=path+'/loans/'+loan.json()['id']+'/return'
    returned=client.post(url,json=body,headers={'Idempotency-Key':key})
    assert returned.status_code==200,returned.text
    assert client.post(url,json=body,headers={'Idempotency-Key':key}).status_code==200
    db.refresh(asset);assert str(asset.custodian_id)==custodian['id'] and asset.location=='قفسه جایگزین'
    assert db.query(AssetAssignment).count()==2


def test_contract_date_quota_outside_approval_and_periodic_request(client,db,user,intake,approved_case):
    initial_journals=db.query(JournalEntry).count()
    from tests.factories import make_item
    from app.models.repair import RepairMaintenanceVisit,RepairServiceRequest
    from app.models.invoices import SalesInvoice
    path='/api/repair/cases/'+approved_case['id']
    contract={'code':'MAINT-TEST','contact_id':intake['contact_id'],'title':'نگهداری سازمان','valid_from':'2026-10-01','valid_until':'2099-01-01','terms':'خدمت تا سهمیه توافق‌شده','address':'نشانی سازمان آزمایشی','coordinator_name':'نماینده','coordinator_phone':'09123456789','covers_labor':True,'covers_parts':False,'visit_quota':2,'minute_quota':20,'value_quota_rial':'10000','response_hours':4,'completion_hours':24,'device_ids':[approved_case['device_id']]}
    created=client.post('/api/repair/maintenance-contracts',json=contract,headers={'Idempotency-Key':str(uuid4())})
    assert created.status_code==201,created.text
    cid=created.json()['id']
    def post(suffix,**data):
        return client.post(path+suffix,json={'version':client.get(path).json()['version'],**data},headers={'Idempotency-Key':str(uuid4())})
    assert post('/contract',contract_id=cid,service_date='2026-09-01',allocated_minutes=20,covered_value_rial='6000').status_code==422
    bound=post('/contract',contract_id=cid,service_date='2026-10-06',allocated_minutes=20,covered_value_rial='6000')
    assert bound.status_code==201,bound.text
    service=make_item(db,name='خدمت قراردادی',is_service=True)
    assert post('/work',technician_id=str(user.id),service_id=str(service.id),description='خدمت اضافی',work_minutes=1,charge_amount='1000').status_code==409
    approved=client.post(path+'/outside-coverage',json={'version':client.get(path).json()['version'],'estimate_id':approved_case['estimates'][0]['id'],'reason':'برآورد اضافی تأیید شده'})
    assert approved.status_code==200,approved.text
    assert post('/work',technician_id=str(user.id),description='خدمت تحت پوشش',work_minutes=21,charge_amount='0').status_code==409
    assert post('/work',technician_id=str(user.id),description='خدمت تحت پوشش',work_minutes=15,charge_amount='0').status_code==201
    assert post('/work',technician_id=str(user.id),service_id=str(service.id),description='خدمت خارج از پوشش',work_minutes=1,charge_amount='1000').status_code==201
    policy=client.get(path+'/contract').json()
    assert policy['snapshot']['version']==1 and policy['outside_estimate_id']==approved_case['estimates'][0]['id']
    plan=client.post('/api/repair/maintenance-plans',json={'contract_id':cid,'device_id':approved_case['device_id'],'branch_id':intake['branch_id'],'title':'سرویس ماهانه','interval_days':30,'next_due':'2026-10-06','allocated_minutes':5,'covered_value_rial':'2000'},headers={'Idempotency-Key':str(uuid4())})
    assert plan.status_code==201,plan.text
    visit=client.post('/api/repair/maintenance-plans/'+plan.json()['id']+'/request')
    assert visit.status_code==201,visit.text
    assert client.post('/api/repair/maintenance-plans/'+plan.json()['id']+'/request').json()['id']==visit.json()['id']
    assert db.query(RepairMaintenanceVisit).count()==db.query(RepairServiceRequest).count()==1
    assert client.post('/api/repair/maintenance-plans/'+plan.json()['id']+'/visits/'+visit.json()['id']+'/complete',json={'result':'بدون اجرای واقعی'}).status_code==409
    assert db.query(SalesInvoice).count()==0 and db.query(JournalEntry).count()==initial_journals
    assert post('/quality',passed=True,result='کنترل خدمت قراردادی').status_code==201
    assert post('/status',status='ready',exceptional=True,reason='کنترل موفق').status_code==200
    assert post('/invoice',on='2026-10-06').status_code==201
    assert post('/receipts',on='2026-10-06',amount='1000',reason='خدمت خارج از پوشش').status_code==201
    assert post('/delivery',receiver_name='نماینده',receiver_phone='09123456789',authorization='نماینده با رسید',accessories='شارژر',care_instructions='مراقبت',checklist={'device':True,'accessories':True,'receiver_authorized':True}).status_code==201
    assert post('/close').status_code==200
    request_path='/api/repair/service-requests/'+visit.json()['request_id']
    requests=client.get('/api/repair/service-requests').json()['items'];request=next(r for r in requests if r['id']==visit.json()['request_id'])
    assert request['maintenance_device_id']==approved_case['device_id']
    admission={**intake,'device':None,'device_id':approved_case['device_id']}
    newcase=client.post(request_path+'/admission',json={'version':request['version'],'admission':admission},headers={'Idempotency-Key':str(uuid4())})
    assert newcase.status_code==201,newcase.text
    assert client.get('/api/repair/cases/'+newcase.json()['id']+'/contract').json()['allocated_minutes']==5
    client.put('/api/repair/technicians/'+str(user.id)+'/skills',json={'type_ids':[intake['device']['type_id']]})
    request=next(r for r in client.get('/api/repair/service-requests').json()['items'] if r['id']==visit.json()['request_id'])
    scheduled=client.post(request_path+'/appointments',json={'version':request['version'],'technician_id':str(user.id),'starts_at':'2026-10-06T09:00:00+03:30','ends_at':'2026-10-06T10:00:00+03:30'},headers={'Idempotency-Key':str(uuid4())})
    assert scheduled.status_code==201,scheduled.text
    for state in ('dispatched','onsite','completed'):
        request=next(r for r in client.get('/api/repair/service-requests').json()['items'] if r['id']==visit.json()['request_id'])
        assert client.post(request_path+'/appointments/'+scheduled.json()['id']+'/status',json={'version':request['version'],'status':state,'result':'اجرای دوره‌ای'}).status_code==200
    newpath='/api/repair/cases/'+newcase.json()['id']
    def newpost(suffix,**data):
        return client.post(newpath+suffix,json={'version':client.get(newpath).json()['version'],**data},headers={'Idempotency-Key':str(uuid4())})
    assert newpost('/diagnosis',initial_diagnosis='سرویس دوره‌ای مطابق قرارداد').status_code==200
    estimate=newpost('/estimates',valid_until='2099-01-01',duration_days=1,customer_ceiling='0',options=[{'title':'پوشش قرارداد','lines':[{'kind':'labor','title':'خدمت تحت پوشش','qty':'1','unit_price':'0'}]}])
    assert estimate.status_code==201,estimate.text
    assert newpost('/estimates/'+estimate.json()['id']+'/decision',decision='approved',option_index=0,method='written',customer_name='نماینده',authorized_ceiling='0').status_code==201
    assert newpost('/work',technician_id=str(user.id),description='سرویس دوره‌ای',work_minutes=3,charge_amount='0').status_code==201
    assert newpost('/quality',passed=True,result='آزمون دوره‌ای').status_code==201
    completed=client.post('/api/repair/maintenance-plans/'+plan.json()['id']+'/visits/'+visit.json()['id']+'/complete',json={'result':'سرویس انجام شد'})
    assert completed.status_code==200,completed.text
    updated=next(p for p in client.get('/api/repair/maintenance-plans').json() if p['id']==plan.json()['id'])
    assert updated['next_due']=='2026-11-05'
    third=admit(client,admission).json()
    denied=client.post('/api/repair/cases/'+third['id']+'/contract',json={'version':third['version'],'contract_id':cid,'service_date':'2026-10-06','allocated_minutes':0,'covered_value_rial':'0'},headers={'Idempotency-Key':str(uuid4())})
    assert denied.status_code==409,denied.text
    revised=client.post('/api/repair/maintenance-contracts',json={**contract,'visit_quota':3,'minute_quota':30,'terms':'نسخه تازه'},headers={'Idempotency-Key':str(uuid4())})
    assert revised.status_code==201 and revised.json()['version']==2
    assert revised.json()['usage']['visits']==2
    assert client.get(path+'/contract').json()['snapshot']['version']==1


def test_consolidated_bill_keeps_real_case_invoices_and_no_duplicate_debt(client,db,user,intake):
    from tests.factories import make_item
    from app.models.invoices import SalesInvoice
    service=make_item(db,name='خدمت صورتحساب سازمانی',is_service=True)
    cases=[]
    for amount in ('10000','20000'):
        row=admit(client,intake).json();path='/api/repair/cases/'+row['id']
        def post(suffix,**data):
            return client.post(path+suffix,json={'version':client.get(path).json()['version'],**data},headers={'Idempotency-Key':str(uuid4())})
        assert post('/diagnosis',initial_diagnosis='تعمیر لازم').status_code==200
        estimate=post('/estimates',valid_until='2099-01-01',duration_days=1,customer_ceiling='100000',options=[{'title':'خدمت','lines':[{'kind':'labor','title':'اجرت','qty':'1','unit_price':amount}]}])
        assert estimate.status_code==201,estimate.text
        assert post('/estimates/'+estimate.json()['id']+'/decision',decision='approved',option_index=0,method='phone',customer_name='نماینده سازمان',authorized_ceiling='100000').status_code==201
        assert post('/work',technician_id=str(user.id),service_id=str(service.id),description='خدمت واقعی',work_minutes=10,charge_amount=amount).status_code==201
        assert post('/quality',passed=True,result='موفق').status_code==201
        assert post('/status',status='ready',exceptional=True,reason='کیفیت موفق').status_code==200
        cases.append(row['id'])
    key=str(uuid4());payload={'title':'صورتحساب سازمان آزمایشی','on':'2026-10-06','case_ids':cases}
    bill=client.post('/api/repair/consolidated-bills',json=payload,headers={'Idempotency-Key':key})
    assert bill.status_code==201,bill.text
    assert len(bill.json()['members'])==2 and db.query(SalesInvoice).count()==2
    count=db.query(JournalEntry).count()
    replay=client.post('/api/repair/consolidated-bills',json=payload,headers={'Idempotency-Key':key})
    assert replay.json()['id']==bill.json()['id'] and db.query(SalesInvoice).count()==2 and db.query(JournalEntry).count()==count
    assert sum(int(client.get('/api/repair/cases/'+cid+'/finance').json()['remaining_balance']) for cid in cases)==30000
    assert sum(int(m['current_document']['remaining_amount']) for m in bill.json()['members'])==30000
    printed=client.get('/api/repair/consolidated-bills/'+bill.json()['id']+'/print')
    assert printed.status_code==200 and 'صورتحساب سازمان آزمایشی' in printed.text


def test_external_native_part_return_updates_repair_consumption(client,db,user,approved_case):
    from datetime import date
    from decimal import Decimal
    from tests.factories import make_item,main_warehouse,other_warehouse
    from app.schemas.invoices import PurchaseInvoiceIn,PurchaseInvoiceLineIn
    from app.schemas.issue_returns import IssueReturnIn,IssueReturnLineIn
    from app.services.inventory import post_purchase_invoice
    from app.services import issue_returns
    item=make_item(db,name='قطعه برگشت بیرون تعمیرگاه',unit='عدد')
    source,destination=main_warehouse(db),other_warehouse(db)
    post_purchase_invoice(db,PurchaseInvoiceIn(invoice_date=date.today(),warehouse_id=source.id,lines=[PurchaseInvoiceLineIn(item_id=item.id,qty=Decimal(2),unit_cost=Decimal(500))]),user)
    path='/api/repair/cases/'+approved_case['id']
    def post(suffix,**payload):
        return client.post(path+suffix,json={'version':client.get(path).json()['version'],**payload},headers={'Idempotency-Key':str(uuid4())})
    requested=post('/parts',item_id=str(item.id),qty='1',unit_price='10000',source_warehouse_id=str(source.id),work_warehouse_id=str(destination.id))
    assert requested.status_code==201,requested.text
    suffix='/parts/'+requested.json()['id']+'/actions'
    for action in ('reserve','dispatch'):
        moved=post(suffix,action=action,on=date.today().isoformat())
        assert moved.status_code==201,moved.text
    consumed=post(suffix,action='consume',on=date.today().isoformat(),qty='1')
    assert consumed.status_code==201,consumed.text
    assert Decimal(client.get(path).json()['parts'][0]['consumed_qty'])==1
    issue_returns.create_issue_return(db,IssueReturnIn(return_date=date.today(),warehouse_id=source.id,deliverer_id=approved_case['contact_id'],description='برگشت مستقیم در ماژول انبار',lines=[IssueReturnLineIn(warehouse_issue_line_id=consumed.json()['document_line_id'],qty=Decimal(1),unit_id=item.primary_unit_id,return_condition='sellable')]),user)
    assert Decimal(client.get(path).json()['parts'][0]['consumed_qty'])==0


def test_expired_secrets_cleanup_is_bounded_and_audited(client,db,user,intake):
    from datetime import datetime,timedelta,timezone
    from app.models.repair import RepairDeviceSecret,RepairEvent
    from app.services.repair_access import purge_expired
    ids=[admit(client,intake).json()['id'] for _ in range(3)]
    for index,cid in enumerate(ids):
        db.add(RepairDeviceSecret(case_id=cid,created_by_id=user.id,ciphertext='encrypted-placeholder',expires_at=datetime.now(timezone.utc)+timedelta(days=1 if index==2 else -1)))
    db.flush()
    assert purge_expired(db,limit=1)==1
    assert db.query(RepairDeviceSecret).count()==2
    assert purge_expired(db,limit=200)==1
    assert purge_expired(db,limit=200)==0
    assert db.query(RepairDeviceSecret).count()==1
    assert db.query(RepairEvent).filter_by(action='device_secret_expired').count()==2


def test_repair_batch_transfer_serials_and_frozen_conversion(client,db,user,approved_case):
    from datetime import date
    from decimal import Decimal
    from tests.factories import make_item,main_warehouse,other_warehouse
    from app.models.advanced_inventory import StockBatch
    from app.schemas.invoices import PurchaseInvoiceIn,PurchaseInvoiceLineIn
    from app.services.inventory import post_purchase_invoice,get_stock_qty
    from app.services import units
    primary=units.get_or_create(db,'عدد');secondary=units.get_or_create(db,'کارتن')
    item=make_item(db,name='قطعه بارمحور',primary_unit_id=primary.id,secondary_unit_id=secondary.id,conversion_mode='fixed',conversion_factor=2,is_batch_tracked=True)
    units.configure_legacy(db,item)
    source,destination=main_warehouse(db),other_warehouse(db)
    invoice=post_purchase_invoice(db,PurchaseInvoiceIn(invoice_date=date.today(),warehouse_id=source.id,lines=[PurchaseInvoiceLineIn(item_id=item.id,qty=Decimal(4),unit_cost=Decimal(500))]),user)
    batch=db.query(StockBatch).filter_by(item_id=item.id,warehouse_id=source.id,source_id=invoice.id).one()
    serials=client.post('/api/stock-batches/'+str(batch.id)+'/serials',json={'serials':['REPAIR-A','REPAIR-B','REPAIR-C','REPAIR-D']})
    assert serials.status_code==201,serials.text
    path='/api/repair/cases/'+approved_case['id']
    def post(suffix,**payload):
        return client.post(path+suffix,json={'version':client.get(path).json()['version'],**payload},headers={'Idempotency-Key':str(uuid4())})
    requested=post('/parts',item_id=str(item.id),qty='1',unit_id=str(secondary.id),unit_price='10000',source_warehouse_id=str(source.id),work_warehouse_id=str(destination.id),batch_id=str(batch.id))
    assert requested.status_code==201,requested.text
    assert Decimal(requested.json()['qty'])==2
    frozen=requested.json()['unit_snapshot']
    item.conversion_factor=3;units.configure_legacy(db,item);db.flush()
    suffix='/parts/'+requested.json()['id']+'/actions'
    for action in ('reserve','dispatch'):
        moved=post(suffix,action=action,on=date.today().isoformat())
        assert moved.status_code==201,moved.text
    part=client.get(path).json()['parts'][0]
    assert part['work_batch_id']!=str(batch.id) and part['unit_snapshot']==frozen
    assert get_stock_qty(db,item.id,destination.id)==2
    invalid=post(suffix,action='consume',on=date.today().isoformat(),qty='1',serials=['REPAIR-A','REPAIR-B'])
    assert invalid.status_code==422,invalid.text
    assert get_stock_qty(db,item.id,destination.id)==2
    consumed=post(suffix,action='consume',on=date.today().isoformat(),qty='1',serials=['REPAIR-A'])
    assert consumed.status_code==201,consumed.text
    returned=post(suffix,action='return_consumed',on=date.today().isoformat(),qty='1',source_movement_id=consumed.json()['id'],serials=['REPAIR-A'],reason='عیب قطعه')
    assert returned.status_code==201,returned.text
    assert post(suffix,action='return_unused',on=date.today().isoformat(),qty='1').status_code==201
    assert get_stock_qty(db,item.id,source.id)==4 and get_stock_qty(db,item.id,destination.id)==0


def test_real_concurrent_calendar_and_contract_quota(tenant_id,user):
    from threading import Barrier
    from fastapi import HTTPException
    from app.schemas.repair import ServiceRequestIn,AppointmentIn,MaintenanceContractIn,ContractCaseIn
    from app.services import repair_field as field,repair_contracts as contracts
    from app.models.repair import RepairAppointment,RepairFieldEvent,RepairServiceRequest,RepairTechnicianSkill,RepairContractCase,RepairContractDevice,RepairMaintenanceContract,RepairEvent
    def principal(db):
        return Principal(db.get(User,user.id),db.query(Membership).filter_by(user_id=user.id,tenant_id=tenant_id).one())
    with tenant_session(tenant_id) as db:
        branch=RepairBranch(name='capacity-'+str(uuid4()));kind=RepairDeviceType(name='capacity-'+str(uuid4()));contact=Contact(name='capacity-customer',is_customer=True)
        db.add_all([branch,kind,contact]);db.flush();p=principal(db)
        payload=AdmissionIn(contact_id=contact.id,branch_id=branch.id,device={'type_id':kind.id,'model':'ظرفیت'},reported_issue='همزمان',admission_date='2026-10-06',storage_location='آزمایش',terms='آزمایشی',approval_method='in_person')
        first=svc.create(db,p,payload);second=svc.create(db,p,payload.model_copy(update={'device':None,'device_id':first.device_id}))
        case_ids=[first.id,second.id];device_id=first.device_id
        requests=[field.create(db,p,ServiceRequestIn(branch_id=branch.id,contact_id=contact.id,type_id=kind.id,device_description='آزمایش',reported_issue='همزمان',address='نشانی',coordinator_name='نماینده',coordinator_phone='09123456789')).id for _ in range(2)]
        db.add(RepairTechnicianSkill(technician_id=user.id,type_id=kind.id))
        contract=contracts.create(db,p,MaintenanceContractIn(code='CONCURRENT-'+str(uuid4()),contact_id=contact.id,title='سهمیه همزمان',address='نشانی آزمایشی',coordinator_name='نماینده',coordinator_phone='09123456789',valid_from='2026-10-01',valid_until='2026-12-31',terms='یک مراجعه',response_hours=1,completion_hours=2,visit_quota=1,minute_quota=10,value_quota_rial=100,device_ids=[device_id]))
        cid=contract.id;branch_id=branch.id;kind_id=kind.id;contact_id=contact.id;db.commit()
    barrier=Barrier(2)
    def schedule(rid):
        with tenant_session(tenant_id) as db:
            p=principal(db);row=field.request(db,p,rid,lock=True);barrier.wait(timeout=10)
            try:
                field.schedule(db,p,row,AppointmentIn(version=row.version,technician_id=user.id,starts_at='2026-10-08T09:00:00+03:30',ends_at='2026-10-08T10:00:00+03:30'));db.commit();return 201
            except HTTPException as e:db.rollback();return e.status_code
    def bind(case_id):
        with tenant_session(tenant_id) as db:
            p=principal(db);row=svc.case(db,p,case_id,lock=True);barrier.wait(timeout=10)
            try:
                contracts.bind(db,p,row,ContractCaseIn(version=row.version,contract_id=cid,service_date='2026-10-06',allocated_minutes=10,covered_value_rial=100));db.commit();return 201
            except HTTPException as e:db.rollback();return e.status_code
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(schedule,requests))==[201,409]
            assert sorted(pool.map(bind,case_ids))==[201,409]
        with tenant_session(tenant_id) as db:
            assert db.query(RepairAppointment).filter(RepairAppointment.request_id.in_(requests)).count()==1
            assert db.query(RepairContractCase).filter_by(contract_id=cid).count()==1
    finally:
        with tenant_session(tenant_id) as db:
            for model,column,ids in ((RepairFieldEvent,'request_id',requests),(RepairAppointment,'request_id',requests),(RepairServiceRequest,'id',requests),(RepairTechnicianSkill,'type_id',[kind_id]),(RepairContractCase,'contract_id',[cid]),(RepairContractDevice,'contract_id',[cid]),(RepairMaintenanceContract,'id',[cid]),(RepairEvent,'case_id',case_ids),(RepairCase,'id',case_ids),(RepairDevice,'id',[device_id]),(RepairDeviceType,'id',[kind_id]),(RepairBranch,'id',[branch_id]),(Contact,'id',[contact_id])):
                db.query(model).filter(getattr(model,column).in_(ids)).delete(synchronize_session=False)
            db.commit()


def test_real_browser_admission_against_isolated_backend(client,db,intake):
    import os
    if os.environ.get('REPAIR_BROWSER_QA')!='1':
        pytest.skip('Opt-in Chromium integration requires local WEB_ONLY Vite on 5187')
    import socket,subprocess,time,threading
    from pathlib import Path
    import uvicorn
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(128)
    port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,lifespan='off',log_level='warning'))
    thread=threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True)
    before=(db.query(RepairCase).count(),db.query(StockLedger).count(),db.query(JournalEntry).count())
    thread.start()
    try:
        deadline=time.monotonic()+10
        while not server.started and time.monotonic()<deadline:thread.join(.05)
        assert server.started
        env={**os.environ,'REPAIR_QA_API_URL':f'http://127.0.0.1:{port}','REPAIR_QA_CONTACT':intake['contact_id'],'REPAIR_QA_BRANCH':intake['branch_id'],'REPAIR_QA_TYPE':intake['device']['type_id']}
        result=subprocess.run(['node','scripts/verify-repair-backend.mjs'],cwd=Path(__file__).resolve().parents[2]/'desktop',env=env,capture_output=True,text=True,timeout=120,encoding='utf-8')
        assert result.returncode==0,result.stdout+'\n'+result.stderr
        assert db.query(RepairCase).count()==before[0]+2
        assert db.query(StockLedger).count()==before[1] and db.query(JournalEntry).count()==before[2]
    finally:
        server.should_exit=True;thread.join(10);listener.close()
        assert not thread.is_alive()


def test_cancel_unused_contract_releases_quota_preserving_history(client,db,intake):
    initial_journals=db.query(JournalEntry).count()
    row=admit(client,intake).json();path='/api/repair/cases/'+row['id']
    contract=client.post('/api/repair/maintenance-contracts',json={'code':'RELEASE','contact_id':intake['contact_id'],'title':'یک مراجعه','valid_from':'2026-10-01','valid_until':'2026-12-31','terms':'آزمایشی','address':'نشانی','coordinator_name':'نماینده','coordinator_phone':'09123456789','visit_quota':1,'minute_quota':10,'value_quota_rial':'100','response_hours':1,'completion_hours':2,'device_ids':[row['device_id']]},headers={'Idempotency-Key':str(uuid4())})
    assert contract.status_code==201,contract.text
    payload={'version':1,'contract_id':contract.json()['id'],'service_date':'2026-10-06','allocated_minutes':10,'covered_value_rial':'100'}
    bound=client.post(path+'/contract',json=payload,headers={'Idempotency-Key':str(uuid4())})
    assert bound.status_code==201,bound.text
    cancelled=client.post(path+'/status',json={'version':client.get(path).json()['version'],'status':'cancelled','reason':'لغو پیش از هر عملیات'})
    assert cancelled.status_code==200,cancelled.text
    original=client.get(path+'/contract').json()
    assert original['released_at'] and original['release_reason']=='لغو پیش از هر عملیات'
    assert original['snapshot']['version']==1
    latest=client.get('/api/repair/maintenance-contracts').json()[0]
    assert latest['usage']['visits']==0 and int(latest['usage']['minutes'])==0 and int(latest['usage']['value_rial'])==0
    second=admit(client,{**intake,'device':None,'device_id':row['device_id']}).json()
    assert client.post('/api/repair/cases/'+second['id']+'/contract',json=payload,headers={'Idempotency-Key':str(uuid4())}).status_code==201
    assert db.query(StockLedger).count()==0 and db.query(JournalEntry).count()==initial_journals


def test_credit_delivery_requires_separate_permission_and_real_balance(client,db,user,approved_case,monkeypatch):
    from tests.factories import make_item
    service=make_item(db,name='اجرت تحویل اعتباری',is_service=True)
    path='/api/repair/cases/'+approved_case['id']
    def post(suffix,**payload):
        return client.post(path+suffix,json={'version':client.get(path).json()['version'],**payload},headers={'Idempotency-Key':str(uuid4())})
    assert post('/work',technician_id=str(user.id),service_id=str(service.id),description='خدمت',work_minutes=1,charge_amount='1000').status_code==201
    assert post('/quality',passed=True,result='موفق').status_code==201
    assert post('/status',status='ready',exceptional=True,reason='پایان').status_code==200
    assert post('/invoice',on='2026-10-06').status_code==201
    payload={'receiver_name':'مالک','receiver_phone':'09123456789','authorization':'با رسید','accessories':'شارژر','care_instructions':'مراقبت','checklist':{'device':True,'accessories':True,'receiver_authorized':True},'credit_reason':'اعتبار مجاز آزمایشی'}
    permission=Principal.has_permission
    with monkeypatch.context() as patch:
        patch.setattr(Principal,'has_permission',lambda self,module,action:False if module=='repair_credit' else permission(self,module,action))
        denied=post('/delivery',**payload)
        assert denied.status_code==403,denied.text
        assert client.get(path).json()['status']=='ready'
    delivered=post('/delivery',**payload)
    assert delivered.status_code==201,delivered.text
    assert post('/close').status_code==409
    assert post('/receipts',on='2026-10-06',amount='1000',reason='تسویه اعتبار').status_code==201
    assert post('/close').status_code==200
