from uuid import UUID,uuid4
from test_repair import intake,admit
from app.models.repair import RepairDeviceIdentityEvent as Event,RepairCase


def post(client,path,data,key=None):
    return client.post(path,json=data,headers={'Idempotency-Key':key or str(uuid4())})


def test_claim_does_not_grant_ownership_and_decision_is_once(client,db,intake):
    from sqlalchemy import text
    from app.audit import append_only_statements
    for statement in append_only_statements('repair_device_identity_events'):
        db.execute(text(statement))
    row=admit(client,intake).json();path='/api/repair/cases/'+row['id']
    other=client.post('/api/contacts',json={'name':'مدعی تازه','type':'customer'}).json()
    payload={'version':row['version'],'device_version':1,'contact_id':other['id'],'reason':'ادعای مالکیت','evidence':'مدرک ارائه شده'}
    key=str(uuid4());claim=post(client,path+'/ownership-claims',payload,key)
    assert claim.status_code==201,claim.text
    assert post(client,path+'/ownership-claims',payload,key).json()==claim.json()
    assert db.query(Event).filter_by(kind='ownership').count()==0
    assert client.get('/api/repair/devices/'+row['device_id']+'/identity-events').json()['items']==[]
    preview=client.get(path+'/ownership-claim-preview').json()
    decision={'version':client.get(path).json()['version'],'device_version':preview['device_version'],
        'previous_ownership_id':preview['previous_ownership_id'],'decision':'approved','reason':'تأیید مسئول مجاز','evidence':'اصالت سند بررسی شد'}
    url=path+'/ownership-claims/'+claim.json()['id']+'/decision'
    assert post(client,url,{**decision,'device_version':1}).status_code==409
    key=str(uuid4());resolved=post(client,url,decision,key)
    assert resolved.status_code==201,resolved.text
    assert resolved.json()['kind']=='ownership' and resolved.json()['claim_id']==claim.json()['id']
    assert post(client,url,decision,key).json()==resolved.json()
    assert post(client,url,{**decision,'version':client.get(path).json()['version'],'device_version':3}).status_code==409
    old=db.get(RepairCase,UUID(row['id']))
    assert str(old.contact_id)==row['contact_id'] and old.owner_snapshot==row['owner_snapshot']


def test_rejection_preserves_current_owner_and_requires_fresh_owner_review(client,db,intake):
    row=admit(client,intake).json();path='/api/repair/cases/'+row['id'];device='/api/repair/devices/'+row['device_id']
    owner=post(client,device+'/ownership',{'version':1,'contact_id':row['contact_id'],'reason':'تأیید مالک','evidence':'مدرک معتبر'}).json()
    claim=post(client,path+'/ownership-claims',{'version':row['version'],'device_version':2,'contact_id':row['contact_id'],'reason':'ادعای تکراری','evidence':'مدرک ادعا'}).json()
    data={'version':client.get(path).json()['version'],'device_version':3,'decision':'rejected','reason':'رد ادعای تکراری','evidence':'مدرک بررسی شد'}
    url=path+'/ownership-claims/'+claim['id']+'/decision'
    assert post(client,url,data).status_code==409
    result=post(client,url,{**data,'previous_ownership_id':owner['id']})
    assert result.status_code==201,result.text
    assert result.json()['kind']=='ownership_rejected'
    assert db.query(Event).filter_by(kind='ownership').one().id==UUID(owner['id'])
    foreign=admit(client,intake).json()
    assert post(client,'/api/repair/cases/'+foreign['id']+'/ownership-claims/'+claim['id']+'/decision',{**data,'version':foreign['version']}).status_code==404


def test_claim_branch_and_approval_permissions(client,db,tenant_id,intake):
    from app.deps import Principal,get_principal
    from app.main import app
    from app.models.user import User,Role
    from app.models.tenant import Membership
    row=admit(client,intake).json();path='/api/repair/cases/'+row['id']
    person=User(name='بدون اختیار',email=f'{uuid4()}@example.invalid',hashed_password='unused',active=True)
    role=Role(key=str(uuid4()),name='پذیرش',permissions={'repair':['view','create','approve'],'repair_identity':['view']})
    db.add_all([person,role]);db.flush()
    membership=Membership(tenant_id=tenant_id,user_id=person.id,role_id=role.id,status='active');db.add(membership);db.flush()
    original=app.dependency_overrides[get_principal];app.dependency_overrides[get_principal]=lambda:Principal(person,membership)
    try:
        claim=post(client,path+'/ownership-claims',{'version':row['version'],'device_version':1,'contact_id':row['contact_id'],'reason':'ثبت ادعا','evidence':'فقط دریافت سند'})
        assert claim.status_code==201,claim.text
        assert client.get(path+'/ownership-claim-preview').status_code==403
        assert post(client,path+'/ownership-claims/'+claim.json()['id']+'/decision',{'version':2,'device_version':2,'decision':'approved','reason':'بدون مجوز','evidence':'نباید ثبت شود'}).status_code==403
        role.permissions={'repair':['view','create'],'repair_identity':['view','approve']};db.flush()
        assert client.get(path+'/ownership-claims').status_code==404
        assert client.get(path+'/ownership-claim-preview').status_code==404
    finally:
        app.dependency_overrides[get_principal]=original
