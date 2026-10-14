from uuid import UUID, uuid4
from test_repair import intake, admit
from app.models.repair import RepairCase
from app.models.repair_completion import RepairTechnicalSummary
from app.services.repair_summary import for_recipient


def post(client,path,data,key=None):
    return client.post(path,json=data,headers={'Idempotency-Key':key or str(uuid4())})


def setup_summary(client,intake):
    old=admit(client,intake).json()
    person=client.post('/api/contacts',json={'name':'مالک تازه خلاصه','type':'customer'}).json()
    owner=post(client,'/api/repair/devices/'+old['device_id']+'/ownership',{'version':1,'contact_id':person['id'],'reason':'انتقال معتبر','evidence':'مدرک مالکیت بررسی شد'})
    assert owner.status_code==201,owner.text
    new=admit(client,{**intake,'contact_id':person['id'],'device':None,'device_id':old['device_id']}).json()
    path='/api/repair/cases/'+old['id']
    preview=client.get(path+'/technical-summary-preview').json()
    data={k:preview[k] for k in ('device_version','ownership_id','previous_revision')}
    data.update(version=old['version'],content={'condition':'دستگاه سالم است','repairs':'تنظیم برد','tests':'آزمون عملکرد موفق','care':'دور از رطوبت'},reason='بازبینی مستقل مدیر فنی',privacy_reviewed=True)
    return old,new,path,data


def test_summary_is_explicit_versioned_and_only_visible_to_approved_owner(client,db,intake):
    old,new,path,data=setup_summary(client,intake)
    assert post(client,path+'/technical-summaries',{**data,'privacy_reviewed':False}).status_code==422
    assert post(client,path+'/technical-summaries',{**data,'content':{**data['content'],'old_owner':'نباید پذیرفته شود'}}).status_code==422
    key=str(uuid4()); result=post(client,path+'/technical-summaries',data,key)
    assert result.status_code==201,result.text
    assert post(client,path+'/technical-summaries',data,key).json()==result.json()
    assert post(client,path+'/technical-summaries',data).status_code==409
    assert db.query(RepairTechnicalSummary).count()==1
    from sqlalchemy import text
    from app.tenant_context import tenant_scope
    with tenant_scope(db,uuid4()):
        assert db.execute(text('SELECT count(*) FROM repair_technical_summaries')).scalar_one()==0
    assert set(result.json())=={'id','revision','approved_at','content'}
    assert client.get(path+'/technical-summaries').json()['items']==[]
    newpath='/api/repair/cases/'+new['id']
    visible=client.get(newpath+'/technical-summaries').json()['items']
    assert visible==[result.json()]
    oldrow=db.get(RepairCase,UUID(old['id']));newrow=db.get(RepairCase,UUID(new['id']))
    assert oldrow.contact_id!=newrow.contact_id and oldrow.owner_snapshot==old['owner_snapshot']
    from app.services.repair_portal import projection
    portal=projection(db,newrow)
    assert len(portal['technical_summaries'])==1
    assert 'case_id' not in portal['technical_summaries'][0]
    assert 'reason' not in portal['technical_summaries'][0]
    # Reconfirmation, even to the same person, is a new ownership decision.
    owner2=post(client,'/api/repair/devices/'+old['device_id']+'/ownership',{'version':2,'previous_ownership_id':data['ownership_id'],'contact_id':new['contact_id'],'reason':'مدرک تازه','evidence':'بازبینی مجدد سند'})
    assert owner2.status_code==201,owner2.text
    assert for_recipient(db,newrow)==[]
    assert db.query(RepairTechnicalSummary).count()==1


def test_summary_separate_permission_and_branch_boundary(client,db,intake,tenant_id):
    from app.deps import Principal,get_principal
    from app.main import app
    from app.models.user import User,Role
    from app.models.tenant import Membership
    old,new,path,data=setup_summary(client,intake)
    person=User(name='محدود',email=f'{uuid4()}@example.invalid',hashed_password='unused',active=True)
    role=Role(key=str(uuid4()),name='فنی بدون تأیید خلاصه',permissions={'repair':['view','approve']})
    db.add_all([person,role]);db.flush()
    membership=Membership(tenant_id=tenant_id,user_id=person.id,role_id=role.id,status='active')
    db.add(membership);db.flush()
    original=app.dependency_overrides[get_principal]
    app.dependency_overrides[get_principal]=lambda:Principal(person,membership)
    try:
        assert client.get(path+'/technical-summary-preview').status_code==403
        assert post(client,path+'/technical-summaries',data).status_code==403
        role.permissions={'repair':['view'],'repair_technical_summary':['approve']};db.flush()
        assert client.get(path+'/technical-summary-preview').status_code==404
        assert client.get(path+'/technical-summaries').status_code==404
        assert post(client,path+'/technical-summaries',data).status_code==404
    finally:
        app.dependency_overrides[get_principal]=original
