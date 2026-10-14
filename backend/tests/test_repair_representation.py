from datetime import datetime,timedelta,timezone
from uuid import UUID,uuid4
from test_repair import intake,admit
from app.models.repair_completion import RepairRepresentativeAuthorization,RepairConfirmation
from app.services import repair_confirmation as confirmation


def post(client,path,data,key=None):
    return client.post(path,json=data,headers={'Idempotency-Key':key or str(uuid4())})


def prepare(client,intake,operation='intake'):
    row=admit(client,intake).json();path='/api/repair/cases/'+row['id']
    data={'version':row['version'],'operation':operation,'name':'نماینده مجاز','phone':'09123456789',
          'evidence':'وکالت‌نامه بررسی شد','expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
    result=post(client,path+'/representatives',data)
    assert result.status_code==201,result.text
    return row,path,result.json(),data


def test_representation_is_case_operation_recipient_bound_and_revocation_blocks_consumption(client,db,intake,monkeypatch):
    from sqlalchemy import text
    from app.audit import append_only_statements
    for statement in append_only_statements('repair_representative_authorizations'):
        db.execute(text(statement))
    row,path,rep,data=prepare(client,intake)
    assert db.query(RepairRepresentativeAuthorization).count()==1
    codes=[];monkeypatch.setattr(confirmation,'send_code',lambda phone,code:codes.append(code) or True)
    request={'version':client.get(path).json()['version'],'kind':'intake','recipient_name':rep['name'],
        'recipient_phone':rep['phone'],'authority_evidence':'اختیار مصوب','representation_id':rep['id']}
    assert post(client,path+'/confirmations',{**request,'recipient_name':'فرد دیگر'}).status_code==409
    foreign=admit(client,intake).json()
    assert post(client,'/api/repair/cases/'+foreign['id']+'/confirmations',{**request,'version':foreign['version']}).status_code==404
    sent=post(client,path+'/confirmations',request)
    assert sent.status_code==201,sent.text
    verify=post(client,path+'/confirmations/'+sent.json()['id']+'/verify',{'version':1,'code':codes[0]})
    assert verify.json()['status']=='verified'
    payload={'version':client.get(path).json()['version'],'reason':'اختیار از سوی اصیل لغو شد'}
    key=str(uuid4());revoke=post(client,path+'/representatives/'+rep['id']+'/revoke',payload,key)
    assert revoke.status_code==201 and revoke.json()['revoked']
    assert post(client,path+'/representatives/'+rep['id']+'/revoke',payload,key).json()==revoke.json()
    consume=post(client,path+'/confirmations/'+sent.json()['id']+'/intake',{'version':client.get(path).json()['version']})
    assert consume.status_code==409,consume.text
    assert db.get(RepairConfirmation,UUID(sent.json()['id'])).status=='verified'


def test_representation_wrong_operation_expiry_and_permissions(client,db,intake,tenant_id):
    from app.deps import Principal,get_principal
    from app.main import app
    from app.models.user import User,Role
    from app.models.tenant import Membership
    row,path,rep,data=prepare(client,intake,'delivery')
    request={'version':client.get(path).json()['version'],'kind':'intake','recipient_name':rep['name'],
        'recipient_phone':rep['phone'],'authority_evidence':'مدرک مصوب','representation_id':rep['id']}
    assert post(client,path+'/confirmations',request).status_code==409
    assert post(client,path+'/representatives',{**data,'version':request['version'],'expires_at':datetime.now(timezone.utc).isoformat()}).status_code==422
    person=User(name='امضاکننده',email=f'{uuid4()}@example.invalid',hashed_password='unused',active=True)
    role=Role(key=str(uuid4()),name='ثبت تأیید بدون مدیریت نماینده',permissions={'repair':['view','approve'],'repair_signatures':['create']})
    db.add_all([person,role]);db.flush()
    member=Membership(tenant_id=tenant_id,user_id=person.id,role_id=role.id,status='active');db.add(member);db.flush()
    original=app.dependency_overrides[get_principal];app.dependency_overrides[get_principal]=lambda:Principal(person,member)
    try:
        listed=client.get(path+'/representatives')
        assert listed.status_code==200 and 'evidence' not in listed.json()['items'][0]
        assert post(client,path+'/representatives',data).status_code==403
        assert post(client,path+'/representatives/'+rep['id']+'/revoke',{'version':request['version'],'reason':'فاقد مجوز'}).status_code==403
        role.permissions={'repair':['view'],'repair_signatures':['create']};db.flush()
        assert client.get(path+'/representatives').status_code==404
    finally:app.dependency_overrides[get_principal]=original


def test_delivery_rechecks_representation_expiry_and_keeps_original_authorization(client,db,intake,monkeypatch):
    from app.services import repair_representation
    from app.models.repair import RepairDelivery
    row,path,rep,data=prepare(client,intake,'delivery')
    current=client.get(path).json()
    cancelled=client.post(path+'/status',json={'version':current['version'],'status':'cancelled','reason':'آزمون تحویل بدون هزینه'})
    assert cancelled.status_code==200,cancelled.text
    delivery={'version':cancelled.json()['version'],'representation_id':rep['id'],'receiver_name':rep['name'],
        'receiver_phone':rep['phone'],'authorization':'وکالت مصوب همین پرونده','accessories':'ندارد',
        'checklist':{'device':True,'accessories':True,'receiver_authorized':True}}
    class Future(datetime):
        @classmethod
        def now(cls,tz=None):return datetime.now(timezone.utc)+timedelta(days=2)
    monkeypatch.setattr(repair_representation,'datetime',Future)
    assert post(client,path+'/delivery',delivery).status_code==409
    assert db.query(RepairDelivery).count()==0
    monkeypatch.setattr(repair_representation,'datetime',datetime)
    key=str(uuid4());result=post(client,path+'/delivery',delivery,key)
    assert result.status_code==201,result.text
    assert post(client,path+'/delivery',delivery,key).json()['id']==result.json()['id']
    assert db.query(RepairDelivery).count()==1
    assert db.get(RepairRepresentativeAuthorization,UUID(rep['id'])).evidence==data['evidence']
    from sqlalchemy import text
    from app.tenant_context import tenant_scope
    with tenant_scope(db,uuid4()):
        assert db.execute(text('SELECT count(*) FROM repair_representative_authorizations')).scalar_one()==0
