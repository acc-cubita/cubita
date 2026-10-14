from datetime import datetime,timedelta
from uuid import uuid4,UUID
from test_repair import intake,approved_case
from app.models.repair import RepairWarranty,RepairWarrantyClaim
from app.models.repair_completion import RepairWarrantyTransfer


def keyed(client,path,data,key=None):
    return client.post(path,json=data,headers={'Idempotency-Key':key or str(uuid4())})


def prepare(client,user,approved_case):
    path='/api/repair/cases/'+approved_case['id']
    def post(suffix,**data):
        result=keyed(client,path+suffix,{'version':client.get(path).json()['version'],**data})
        assert result.status_code in (200,201),result.text
        return result.json()
    work=post('/work',technician_id=str(user.id),description='تنظیم بدون هزینه',work_minutes=10,charge_amount='0')
    post('/status',status='diagnosing');post('/status',status='repairing');post('/status',status='testing')
    post('/quality',passed=True,result='موفق');post('/status',status='ready')
    delivery=post('/delivery',receiver_name='مالک اولیه',receiver_phone='09123456789',authorization='مدرک معتبر',accessories='ندارد',checklist={'device':True,'accessories':True,'receiver_authorized':True})
    start=datetime.fromisoformat(delivery['delivered_at']).date()+timedelta(days=1)
    warranty=post('/warranties',scope='service',source_id=work['id'],title='ضمانت تنظیم',valid_from=start.isoformat(),valid_until=(start+timedelta(days=30)).isoformat(),terms='همان خرابی',exclusions='ضربه')
    return path,warranty,start


def test_transfer_requires_confirmed_owner_and_preserves_warranty_and_documents(client,db,user,intake,approved_case):
    path,warranty,on=prepare(client,user,approved_case)
    endpoint=path+'/warranties/'+warranty['id']
    new=client.post('/api/contacts',json={'name':'مالک تازه ضمانت','type':'customer'}).json()
    row=client.get(path).json()
    preview=client.get(endpoint+'/transfer-preview')
    assert preview.status_code==200 and preview.json()['ownership_id'] is None
    transfer={'version':row['version'],'device_version':1,'ownership_id':str(uuid4()),'previous_revision':0,'reason':'بررسی مدیر فنی'}
    assert keyed(client,endpoint+'/transfers',transfer).status_code==409
    admission={**intake,'contact_id':new['id'],'device':None,'device_id':row['device_id'],'admission_date':on.isoformat()}
    visit={'warranty_id':warranty['id'],'admission':admission,'classification':'repeat_fault','responsibility':'company','cost_policy':'covered','reason':'ایراد تکراری'}
    assert keyed(client,path+'/revisits',visit).status_code==422

    owner=keyed(client,'/api/repair/devices/'+row['device_id']+'/ownership',{'version':1,'contact_id':new['id'],'reason':'انتقال مالکیت','evidence':'مدرک معتبر بررسی شد'})
    assert owner.status_code==201,owner.text
    preview=client.get(endpoint+'/transfer-preview').json()
    payload={**transfer,'device_version':preview['device_version'],'ownership_id':preview['ownership_id']}
    assert keyed(client,endpoint+'/transfers',{**payload,'valid_until':'2099-01-01'}).status_code==422
    key=str(uuid4());result=keyed(client,endpoint+'/transfers',payload,key)
    assert result.status_code==201,result.text
    assert keyed(client,endpoint+'/transfers',payload,key).json()['id']==result.json()['id']
    assert db.query(RepairWarrantyTransfer).count()==1
    original=db.get(RepairWarranty,UUID(warranty['id']))
    assert original.valid_until.isoformat()==warranty['valid_until'] and original.terms==warranty['terms']
    current=client.get(path).json()
    assert current['contact_id']==row['contact_id'] and current['owner_snapshot']==row['owner_snapshot']
    assert keyed(client,path+'/revisits',{**visit,'admission':{**admission,'contact_id':row['contact_id']}}).status_code==422
    accepted=keyed(client,path+'/revisits',visit)
    assert accepted.status_code==201,accepted.text
    assert accepted.json()['contact_id']==new['id']
    claim=db.query(RepairWarrantyClaim).filter_by(revisit_case_id=accepted.json()['id']).one()
    assert str(claim.warranty_id)==warranty['id']
    expired={**visit,'admission':{**admission,'admission_date':(on+timedelta(days=31)).isoformat()}}
    assert keyed(client,path+'/revisits',expired).status_code==422
    # A later ownership decision invalidates the earlier transfer for new visits.
    owner2=keyed(client,'/api/repair/devices/'+row['device_id']+'/ownership',{'version':2,'previous_ownership_id':owner.json()['id'],'contact_id':row['contact_id'],'reason':'برگشت مالکیت','evidence':'مدرک تازه بررسی شد'})
    assert owner2.status_code==201,owner2.text
    assert keyed(client,path+'/revisits',visit).status_code==422


def test_transfer_requires_separate_technical_approval_permission(client,db,user,intake,approved_case,tenant_id):
    from app.deps import Principal,get_principal
    from app.main import app
    from app.models.user import User,Role
    from app.models.tenant import Membership
    path,warranty,on=prepare(client,user,approved_case)
    limited=User(name='مدیر فاقد اختیار انتقال',email=f'{uuid4()}@example.invalid',hashed_password='unused',active=True)
    role=Role(key=str(uuid4()),name='مدیر عادی',permissions={'repair':['view','approve'],'repair_identity':['view','approve']})
    db.add_all([limited,role]);db.flush()
    member=Membership(tenant_id=tenant_id,user_id=limited.id,role_id=role.id,status='active');db.add(member);db.flush()
    original=app.dependency_overrides[get_principal]
    app.dependency_overrides[get_principal]=lambda:Principal(limited,member)
    try:
        assert client.get(path+'/warranties/'+warranty['id']+'/transfer-preview').status_code==403
        assert keyed(client,path+'/warranties/'+warranty['id']+'/transfers',{'version':1,'device_version':1,'ownership_id':str(uuid4()),'previous_revision':0,'reason':'بدون مجوز مستقل'}).status_code==403
    finally:
        app.dependency_overrides[get_principal]=original


def test_real_browser_warranty_transfer(client,db,user,intake,approved_case):
    import os,socket,threading,subprocess,time
    from pathlib import Path
    import pytest,uvicorn
    from app.main import app
    if os.environ.get('REPAIR_PROFESSIONAL_BROWSER')!='1':
        pytest.skip('Requires WEB_ONLY Vite on localhost:5187')
    path,warranty,on=prepare(client,user,approved_case)
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(128)
    port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,lifespan='off',log_level='warning'))
    thread=threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True);thread.start()
    try:
        deadline=time.monotonic()+10
        while not server.started and time.monotonic()<deadline:thread.join(.05)
        assert server.started
        env={**os.environ,'REPAIR_QA_API_URL':f'http://127.0.0.1:{port}','REPAIR_QA_CASE':approved_case['id'],'REPAIR_QA_WARRANTY':warranty['id']}
        result=subprocess.run(['node','scripts/verify-repair-warranty-transfer.mjs'],cwd=Path(__file__).resolve().parents[2]/'desktop',env=env,capture_output=True,text=True,timeout=120,encoding='utf-8')
        assert result.returncode==0,result.stdout+'\n'+result.stderr
        assert db.query(RepairWarrantyTransfer).count()==2
        assert db.get(RepairWarranty,UUID(warranty['id'])).valid_until.isoformat()==warranty['valid_until']
    finally:
        server.should_exit=True;thread.join(10);listener.close()
