from uuid import UUID,uuid4
from datetime import datetime,timedelta
from test_repair import intake,admit
from app.models.repair_completion import RepairConfirmation
from app.services import repair_confirmation as service


def post(client,path,data,key=None):
    return client.post(path,json=data,headers={'Idempotency-Key':key or str(uuid4())})


def prepare(client,intake):
    row=admit(client,intake).json()
    path='/api/repair/cases/'+row['id']
    return row,path,{'version':row['version'],'kind':'intake','recipient_name':'مالک','recipient_phone':'09123456789','recipient_contact_id':intake['contact_id'],'authority_evidence':'مدرک مالکیت بررسی شد'}


def test_failed_sms_is_persisted_rate_limited_and_never_simulated(client,intake,monkeypatch,caplog):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(),'melipayamak_api_key','')
    monkeypatch.setattr(get_settings(),'melipayamak_otp_pattern_id','')
    row,path,data=prepare(client,intake)
    result=post(client,path+'/confirmations',data)
    assert result.status_code==201,result.text
    assert result.json()['status']=='failed'
    assert 'code' not in result.json() and 'code_hash' not in result.json()
    assert 'شبیه‌سازی' not in caplog.text
    current=client.get(path).json()
    assert post(client,path+'/confirmations',{**data,'version':current['version']}).status_code==429


def test_code_attempt_limit_and_retry_do_not_reset_counter(client,db,intake,monkeypatch):
    captured=[]
    monkeypatch.setattr(service,'send_code',lambda phone,code:captured.append(code) or True)
    row,path,data=prepare(client,intake)
    sent=post(client,path+'/confirmations',data).json()
    endpoint=path+'/confirmations/'+sent['id']+'/verify'
    bad='111111' if captured[0]!='111111' else '222222'
    for attempt in range(5):
        payload={'version':attempt+1,'code':bad};key=str(uuid4())
        result=post(client,endpoint,payload,key)
        assert result.status_code==200,result.text
        assert result.json()['attempts_remaining']==4-attempt
        assert post(client,endpoint,payload,key).json()==result.json()
    assert result.json()['status']=='locked'
    assert post(client,endpoint,{'version':6,'code':captured[0]}).json()['status']=='locked'
    record=db.get(RepairConfirmation,UUID(sent['id']))
    assert record.code_hash!=captured[0] and len(record.code_hash)==64


def test_intake_code_is_bound_to_revision_and_consumed_once(client,intake,monkeypatch):
    codes=[];monkeypatch.setattr(service,'send_code',lambda phone,code:codes.append(code) or True)
    row,path,data=prepare(client,intake)
    sent=post(client,path+'/confirmations',data).json()
    endpoint=path+'/confirmations/'+sent['id']
    verified=post(client,endpoint+'/verify',{'version':1,'code':codes[0]})
    assert verified.json()['status']=='verified'
    current=client.get(path).json();payload={'version':current['version']};key=str(uuid4())
    result=post(client,endpoint+'/intake',payload,key)
    assert result.status_code==200,result.text
    assert result.json()['status']=='consumed'
    assert post(client,endpoint+'/intake',payload,key).json()==result.json()
    assert len(client.get(path+'/acknowledgments').json())==1


def test_changed_intake_and_expired_code_cannot_be_consumed(client,intake,monkeypatch):
    codes=[];monkeypatch.setattr(service,'send_code',lambda phone,code:codes.append(code) or True)
    row,path,data=prepare(client,intake)
    sent=post(client,path+'/confirmations',data).json();endpoint=path+'/confirmations/'+sent['id']
    assert post(client,endpoint+'/verify',{'version':1,'code':codes[0]}).json()['status']=='verified'
    current=client.get(path).json()
    result=client.patch(path+'/intake-details',json={'version':current['version'],'accessories':'جدید'},headers={'Idempotency-Key':str(uuid4())})
    assert result.status_code==200,result.text
    assert post(client,endpoint+'/intake',{'version':result.json()['version']}).status_code==409
    original_now=service.now()
    monkeypatch.setattr(service,'now',lambda:original_now+timedelta(minutes=6))
    assert post(client,endpoint+'/verify',{'version':2,'code':codes[0]}).json()['status']=='expired'


def test_delivery_code_rechecks_recipient_and_atomic_replay(client,intake,monkeypatch):
    codes=[];monkeypatch.setattr(service,'send_code',lambda phone,code:codes.append(code) or True)
    row,path,data=prepare(client,intake)
    cancelled=client.post(path+'/status',json={'version':row['version'],'status':'cancelled','reason':'لغو آزمایشی بدون هزینه'})
    assert cancelled.status_code==200,cancelled.text
    version=cancelled.json()['version']
    delivery={'version':version,'receiver_name':'مالک','receiver_phone':'09123456789','authorization':'مدرک معتبر','accessories':'بدون لوازم','checklist':{'device':True,'accessories':True,'receiver_authorized':True}}
    sent=post(client,path+'/confirmations',{**data,'version':version,'kind':'delivery','delivery':delivery})
    assert sent.status_code==201,sent.text
    sent=sent.json();endpoint=path+'/confirmations/'+sent['id']
    assert post(client,endpoint+'/verify',{'version':1,'code':codes[0]}).json()['status']=='verified'
    version=client.get(path).json()['version']
    final={**delivery,'version':version,'confirmation_id':sent['id']}
    assert post(client,path+'/delivery',{**final,'receiver_name':'شخص دیگر'}).status_code==422
    key=str(uuid4());result=post(client,path+'/delivery',final,key)
    assert result.status_code==201,result.text
    replay=post(client,path+'/delivery',final,key).json()
    assert replay['id']==result.json()['id']
    assert datetime.fromisoformat(replay['delivered_at'])==datetime.fromisoformat(result.json()['delivered_at'])
    assert post(client,endpoint+'/verify',{'version':3,'code':codes[0]}).json()['status']=='consumed'


def configure_policy(client,intake):
    endpoint='/api/repair/branches/'+intake['branch_id']+'/intake-settings'
    values={'version':0,'code':'OTP','default_location':'قفسه','terms':'شرایط مصوب',
            'intake_confirmation_policy':'otp','delivery_confirmation_policy':'otp'}
    result=client.put(endpoint,json=values)
    assert result.status_code==200,result.text
    return endpoint,values


def override_payload(client,path,data):
    preview=post(client,path+'/confirmation-preview',data)
    assert preview.status_code==200,preview.text
    return {**data,'expected_document_hash':preview.json()['document_hash'],'override_reason':'سرویس پیامک در دسترس نیست',
            'acknowledgment':{'version':data['version'],'kind':data['kind'],'signer_name':data['recipient_name'],
                              'signer_relation':'مالک با مدرک معتبر','strokes':[[[10,20],[40,70]]]}}


def test_policy_is_frozen_and_old_clients_cannot_clear_it(client,intake):
    legacy=admit(client,intake).json()
    endpoint,values=configure_policy(client,intake)
    row,path,data=prepare(client,intake)
    old_client={k:v for k,v in values.items() if not k.endswith('_policy')}
    old_client['version']=1
    updated=client.put(endpoint,json=old_client)
    assert updated.status_code==200,updated.text
    assert updated.json()['delivery_confirmation_policy']=='otp'
    assert client.put(endpoint,json={**values,'version':2,'intake_confirmation_policy':'legacy','delivery_confirmation_policy':'legacy'}).status_code==200
    current=client.get(path).json()
    assert current['intake_details']['settings_snapshot']['delivery_confirmation_policy']=='otp'
    ack={'version':row['version'],'kind':'intake','signer_name':'مالک','signer_relation':'مالک','strokes':[[[10,20],[40,70]]]}
    assert post(client,path+'/acknowledgments',ack).status_code==409
    assert post(client,'/api/repair/cases/'+legacy['id']+'/acknowledgments',{**ack,'version':legacy['version']}).status_code==201


def test_signature_override_is_version_bound_and_replay_safe(client,intake):
    configure_policy(client,intake)
    row,path,data=prepare(client,intake)
    payload=override_payload(client,path,data)
    changed={**payload,'recipient_name':'نماینده دیگر','acknowledgment':{**payload['acknowledgment'],'signer_name':'نماینده دیگر'}}
    assert post(client,path+'/confirmation-override',changed).status_code==409
    key=str(uuid4());result=post(client,path+'/confirmation-override',payload,key)
    assert result.status_code==201,result.text
    assert result.json()['method']=='signature_override' and result.json()['status']=='consumed'
    assert post(client,path+'/confirmation-override',payload,key).json()==result.json()
    assert len(client.get(path+'/acknowledgments').json())==1


def test_required_delivery_cannot_bypass_confirmation_and_signature_consumes_atomically(client,intake):
    configure_policy(client,intake)
    row,path,data=prepare(client,intake)
    cancelled=post(client,path+'/status',{'version':row['version'],'status':'cancelled','reason':'لغو بدون هزینه'})
    assert cancelled.status_code==200,cancelled.text
    delivery={'version':cancelled.json()['version'],'receiver_name':'مالک','receiver_phone':'09123456789','authorization':'مدرک معتبر',
              'accessories':'بدون لوازم','checklist':{'device':True,'accessories':True,'receiver_authorized':True}}
    assert post(client,path+'/delivery',delivery).status_code==409
    data={**data,'version':delivery['version'],'kind':'delivery','delivery':delivery}
    payload=override_payload(client,path,data)
    proof=post(client,path+'/confirmation-override',payload)
    assert proof.status_code==201,proof.text
    final={**delivery,'version':client.get(path).json()['version'],'confirmation_id':proof.json()['id']}
    assert post(client,path+'/delivery',{**final,'accessories':'لوازم تغییر کرده'}).status_code==409
    result=post(client,path+'/delivery',final)
    assert result.status_code==201,result.text


def test_override_permission_is_independent(client,db,intake,tenant_id):
    from app.deps import Principal,get_principal
    from app.main import app
    from app.models.user import User,Role
    from app.models.tenant import Membership
    row,path,data=prepare(client,intake)
    payload=override_payload(client,path,data)
    user=User(name='مسئول بدون اختیار جایگزین',email=f'{uuid4()}@example.invalid',hashed_password='unused',active=True)
    role=Role(key=str(uuid4()),name='مدیر تعمیر محدود',permissions={'repair':['view','approve'],'repair_signatures':['create']})
    db.add_all([user,role]);db.flush()
    member=Membership(tenant_id=tenant_id,user_id=user.id,role_id=role.id,status='active');db.add(member);db.flush()
    original=app.dependency_overrides[get_principal]
    app.dependency_overrides[get_principal]=lambda:Principal(user,member)
    try:
        assert post(client,path+'/confirmation-override',payload).status_code==403
    finally:
        app.dependency_overrides[get_principal]=original


def test_invalid_code_never_appears_in_validation_response(client,intake):
    row,path,data=prepare(client,intake)
    sent=post(client,path+'/confirmations',data).json()
    for code in ('private-invalid-code',{'private-code':'123456'}):
        result=post(client,path+'/confirmations/'+sent['id']+'/verify',{'version':1,'code':code})
        assert result.status_code==422
        assert 'private' not in result.text and '123456' not in result.text


def test_resend_window_and_wrong_operation_are_rejected(client,intake,monkeypatch):
    codes=[];monkeypatch.setattr(service,'send_code',lambda phone,code:codes.append(code) or True)
    start=service.now()
    row,path,data=prepare(client,intake)
    for minute in range(3):
        monkeypatch.setattr(service,'now',lambda:start+timedelta(minutes=minute+1))
        result=post(client,path+'/confirmations',{**data,'version':client.get(path).json()['version']})
        assert result.status_code==201,result.text
    monkeypatch.setattr(service,'now',lambda:start+timedelta(minutes=4))
    assert post(client,path+'/confirmations',{**data,'version':client.get(path).json()['version']}).status_code==429
    sent=result.json()
    assert post(client,path+'/confirmations/'+sent['id']+'/verify',{'version':1,'code':codes[-1]}).json()['status']=='verified'
    current=client.get(path).json()
    cancelled=post(client,path+'/status',{'version':current['version'],'status':'cancelled','reason':'لغو بدون هزینه'})
    delivery={'version':cancelled.json()['version'],'receiver_name':'مالک','receiver_phone':'09123456789','authorization':'مدرک معتبر',
              'accessories':'بدون لوازم','checklist':{'device':True,'accessories':True,'receiver_authorized':True},'confirmation_id':sent['id']}
    assert post(client,path+'/delivery',delivery).status_code==409


def test_concurrent_delivery_consumes_one_confirmation_once(tenant_id,user,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi import HTTPException
    from conftest import tenant_session
    from app.deps import Principal
    from app.models.user import User
    from app.models.tenant import Membership
    from app.models.inventory import Contact
    from app.models.repair import RepairBranch,RepairDeviceType,RepairDevice,RepairCase,RepairEvent,RepairDelivery
    from app.models.repair_completion import RepairCaseDetails
    from app.schemas.repair import AdmissionIn,WorkflowIn,RepairDeliveryIn
    from app.schemas.repair_confirmation import ConfirmationRequestIn,ConfirmationVerifyIn
    from app.services import repair as core,repair_finance
    codes=[];monkeypatch.setattr(service,'send_code',lambda phone,code:codes.append(code) or True)
    def principal(db):
        return Principal(db.get(User,user.id),db.query(Membership).filter_by(tenant_id=tenant_id,user_id=user.id).one())
    with tenant_session(tenant_id) as db:
        branch=RepairBranch(name='delivery-race-'+str(uuid4()));kind=RepairDeviceType(name='delivery-race-'+str(uuid4()))
        contact=Contact(name='مشتری رقابت تحویل',is_customer=True,phone='09123456789')
        db.add_all([branch,kind,contact]);db.flush()
        p=principal(db)
        row=core.create(db,p,AdmissionIn(contact_id=contact.id,branch_id=branch.id,device={'type_id':kind.id,'model':'آزمون'},reported_issue='آزمون همزمانی',admission_date='2026-10-09',storage_location='آزمایش',terms='آزمایشی',approval_method='in_person'))
        core.transition(db,p,row,WorkflowIn(version=row.version,status='cancelled',reason='لغو بدون هزینه'))
        delivery=RepairDeliveryIn(version=row.version,receiver_name='مالک',receiver_phone=contact.phone,authorization='مدرک معتبر',accessories='ندارد',checklist={'device':True,'accessories':True,'receiver_authorized':True})
        proof=service.request(db,p,row,ConfirmationRequestIn(version=row.version,kind='delivery',recipient_name='مالک',recipient_phone=contact.phone,authority_evidence='مدرک معتبر',delivery=delivery))
        service.verify(db,p,row.id,proof.id,ConfirmationVerifyIn(version=1,code=codes[0]))
        payload=delivery.model_copy(update={'version':row.version,'confirmation_id':proof.id})
        case_id,device_id,branch_id,kind_id,contact_id=row.id,row.device_id,branch.id,kind.id,contact.id
        db.commit()
    gate=Barrier(2)
    def attempt(_):
        with tenant_session(tenant_id) as db:
            p=principal(db);gate.wait(timeout=10)
            try:
                repair_finance.delivery(db,p,core.case(db,p,case_id,lock=True),payload)
                db.commit();return 201
            except HTTPException as exc:
                db.rollback();return exc.status_code
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(attempt,range(2)))==[201,409]
        with tenant_session(tenant_id) as db:
            assert db.query(RepairDelivery).filter_by(case_id=case_id).count()==1
            assert db.query(RepairConfirmation).filter_by(case_id=case_id,status='consumed').count()==1
    finally:
        with tenant_session(tenant_id) as db:
            for model in (RepairConfirmation,RepairDelivery,RepairEvent,RepairCaseDetails):
                db.query(model).filter_by(case_id=case_id).delete(synchronize_session=False)
            for model,id in ((RepairCase,case_id),(RepairDevice,device_id),(RepairDeviceType,kind_id),(RepairBranch,branch_id),(Contact,contact_id)):
                db.query(model).filter_by(id=id).delete(synchronize_session=False)
            db.commit()


def test_provider_exception_does_not_log_code_or_key(monkeypatch, caplog):
    from types import SimpleNamespace
    from app.services import sms
    monkeypatch.setattr(sms, 'get_settings', lambda: SimpleNamespace(
        melipayamak_api_key='private-provider-key', melipayamak_otp_pattern_id='42'))
    def fail(*args, **kwargs):
        raise RuntimeError('private-provider-key code=654321')
    monkeypatch.setattr(sms.httpx, 'post', fail)
    assert sms.send_verification_code('09123456789', '654321') is False
    assert 'private-provider-key' not in caplog.text
    assert '654321' not in caplog.text
    assert 'RuntimeError' in caplog.text
