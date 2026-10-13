from uuid import UUID, uuid4
from test_repair import intake, admit
from app.deps import Principal, get_principal
from app.main import app
from app.models.repair import RepairDevice, RepairDeviceIdentityEvent, RepairCase
from app.models.user import User, Role
from app.models.tenant import Membership


def post(client, path, data, key=None):
    return client.post('/api/repair/devices/' + path, json=data, headers={'Idempotency-Key': key or str(uuid4())})


def test_identity_candidates_do_not_merge_or_infer_owner(client, db, intake):
    first = admit(client, intake).json()
    second = admit(client, intake).json()
    assert first['device_id'] != second['device_id']
    rows = client.get('/api/repair/devices?q=SERIAL-1').json()['items']
    assert len(rows) == 2
    assert all('attributes' not in row and 'contact_id' not in row for row in rows)
    identity = rows[0]
    assert client.get('/api/repair/devices', params={'q': identity['qr_payload']}).json()['items'][0]['id'] == identity['id']
    assert client.get('/api/repair/devices/' + identity['id'] + '/identity-events').json()['ownership_status'] == 'unverified'
    assert db.query(RepairDeviceIdentityEvent).count() == 0
    label=client.get('/api/repair/devices/'+identity['id']+'/label')
    assert label.status_code==200 and 'data:image/svg+xml;base64,' in label.text
    assert '09123456789' not in label.text and 'مالک دستگاه' not in label.text
    assert client.get('/api/repair/cases',params={'q':identity['qr_payload']}).json()['items'][0]['device_id']==identity['id']


def test_technical_profile_is_versioned_and_does_not_rewrite_admission(client,db,intake):
    from sqlalchemy import text
    from app.audit import append_only_statements
    for statement in append_only_statements('repair_device_identity_events'):db.execute(text(statement))
    first=admit(client,{**intake,'device':{**intake['device'],'hardware_revision':'A1','industry_identifiers':{'board_number':'BOARD-001'}}}).json()
    assert first['device_snapshot']['hardware_revision']=='A1'
    data={'version':1,'hardware_revision':'B2','industry_identifiers':{'board_number':'BOARD-002','manufacturer_part_number':'M-123'},'reason':'تعویض برد با ثبت مشخصات تازه'}
    key=str(uuid4());result=post(client,first['device_id']+'/profile',data,key)
    assert result.status_code==201,result.text
    assert post(client,first['device_id']+'/profile',data,key).json()==result.json()
    assert post(client,first['device_id']+'/profile',data).status_code==409
    assert result.json()['profile_snapshot']['before']['hardware_revision']=='A1'
    old=client.get('/api/repair/cases/'+first['id']).json()
    assert old['device_snapshot']==first['device_snapshot']
    next_case=admit(client,{**intake,'device':None,'device_id':first['device_id']}).json()
    assert next_case['device_snapshot']['hardware_revision']=='B2'
    assert client.get('/api/repair/devices',params={'q':'BOARD-002'}).json()['items'][0]['id']==first['device_id']
    assert post(client,first['device_id']+'/profile',{**data,'version':2,'industry_identifiers':{'customer_phone':'09123456789'}}).status_code==422


def test_merge_preserves_cases_replays_and_rejects_stale_reverse(client, db, intake):
    source, target = [admit(client, intake).json() for _ in range(2)]
    source_id, target_id = source['device_id'], target['device_id']
    before = db.get(RepairCase, UUID(source['id'])).device_snapshot.copy()
    data = {'version': 1, 'target_device_id': target_id, 'target_version': 1, 'reason': 'بررسی دستگاه', 'evidence': 'بازبینی حضوری پلاک'}
    preview = post(client, source_id + '/merge-preview', data)
    assert preview.status_code == 200, preview.text
    key = str(uuid4())
    result = post(client, source_id + '/merge', data, key)
    assert result.status_code == 201, result.text
    assert post(client, source_id + '/merge', data, key).json() == result.json()
    assert post(client, source_id + '/merge', data).status_code == 409
    assert post(client, target_id + '/merge', {**data, 'target_device_id': source_id}).status_code == 409
    db.expire_all()
    preserved = db.get(RepairCase, UUID(source['id']))
    assert str(preserved.device_id) == source_id and preserved.device_snapshot == before
    assert db.query(RepairDevice).count() == 2
    assert len(client.get('/api/repair/devices/' + target_id + '/cases').json()['items']) == 2
    next_case = admit(client, {**intake, 'device': None, 'device_id': source_id})
    assert next_case.status_code == 201, next_case.text
    assert next_case.json()['device_id'] == target_id


def test_owner_confirmation_and_transfer_are_explicit_versioned_decisions(client, db, intake):
    case = admit(client, intake).json()
    path = case['device_id'] + '/ownership'
    data = {'version': 1, 'contact_id': intake['contact_id'], 'reason': 'تأیید مالک', 'evidence': 'مدرک معتبر مالکیت'}
    first = post(client, path, data)
    assert first.status_code == 201, first.text
    customer = client.post('/api/contacts', json={'name': 'مالک جدید', 'type': 'customer'}).json()
    transfer = {**data, 'version': 2, 'contact_id': customer['id']}
    assert post(client, path, transfer).status_code == 409
    transfer['previous_ownership_id'] = first.json()['id']
    result = post(client, path, transfer)
    assert result.status_code == 201, result.text
    old_case = client.get('/api/repair/cases/' + case['id']).json()
    assert old_case['contact_id'] == intake['contact_id']
    assert db.query(RepairDeviceIdentityEvent).count() == 2


def test_shared_identity_never_grants_branch_history_or_management(client, db, tenant_id, intake):
    case = admit(client, intake).json()
    u = User(name='شعبه دیگر', email=f'{uuid4()}@example.invalid', hashed_password='unused', active=True)
    role = Role(key=str(uuid4()), name='محدود', permissions={'repair': ['view', 'create']})
    db.add_all([u, role]); db.flush()
    member = Membership(tenant_id=tenant_id, user_id=u.id, role_id=role.id, status='active')
    db.add(member); db.flush()
    original = app.dependency_overrides[get_principal]
    app.dependency_overrides[get_principal] = lambda: Principal(u, member)
    try:
        base = '/api/repair/devices/' + case['device_id']
        assert client.get(base).status_code == 200
        assert client.get(base + '/cases').json()['items'] == []
        assert client.get(base + '/identity-events').status_code == 403
        assert client.get('/api/repair/cases/' + case['id']).status_code == 404
        assert post(client, case['device_id'] + '/ownership', {'version': 1, 'contact_id': intake['contact_id'], 'reason': 'بدون مجوز', 'evidence': 'نباید ثبت شود'}).status_code == 403
    finally:
        app.dependency_overrides[get_principal] = original


def test_concurrent_reverse_merge_has_one_winner(tenant_id,user):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi import HTTPException
    from conftest import tenant_session
    from app.models.repair import RepairDeviceType
    from app.schemas.repair_identity import DeviceMergeIn
    from app.services import repair_identity as service
    with tenant_session(tenant_id) as db:
        kind=RepairDeviceType(name='identity-race-'+str(uuid4()))
        db.add(kind);db.flush()
        devices=[RepairDevice(type_id=kind.id,model='رقابت') for _ in range(2)]
        db.add_all(devices);db.flush()
        ids=[device.id for device in devices];kind_id=kind.id;db.commit()
    def attempt(pair):
        with tenant_session(tenant_id) as db:
            principal=Principal(db.get(User,user.id),db.query(Membership).filter_by(tenant_id=tenant_id,user_id=user.id).one())
            try:
                service.merge(db,principal,pair[0],DeviceMergeIn(version=1,target_device_id=pair[1],target_version=1,reason='بررسی همزمان',evidence='بازبینی پلاک'))
                db.commit();return 201
            except HTTPException as exc:
                db.rollback();return exc.status_code
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(attempt,[ids,ids[::-1]]))==[201,409]
        with tenant_session(tenant_id) as db:
            assert db.query(RepairDeviceIdentityEvent).filter(RepairDeviceIdentityEvent.device_id.in_(ids)).count()==1
    finally:
        with tenant_session(tenant_id) as db:
            db.query(RepairDeviceIdentityEvent).filter(RepairDeviceIdentityEvent.device_id.in_(ids)).delete(synchronize_session=False)
            db.query(RepairDevice).filter(RepairDevice.id.in_(ids)).delete(synchronize_session=False)
            db.query(RepairDeviceType).filter_by(id=kind_id).delete(synchronize_session=False)
            db.commit()


def test_identity_rls_hides_rows_from_other_tenant(client,db,intake):
    from sqlalchemy import text
    from app.tenant_context import tenant_scope
    row=admit(client,intake).json()
    result=post(client,row['device_id']+'/ownership',{'version':1,'contact_id':intake['contact_id'],'reason':'تأیید مجاز','evidence':'مدرک بررسی شده'})
    assert result.status_code==201,result.text
    with tenant_scope(db,uuid4()):
        assert db.execute(text('SELECT count(*) FROM repair_device_identity_events')).scalar_one()==0
        assert db.execute(text('SELECT count(*) FROM repair_devices')).scalar_one()==0


def test_owned_identity_merge_requires_explicit_resolution_and_keeps_past_owners(client,db,intake):
    source,target=[admit(client,intake).json() for _ in range(2)]
    other=client.post('/api/contacts',json={'name':'مالک هویت مقصد','type':'customer'}).json()
    decisions=[]
    for row,contact in ((source,intake['contact_id']),(target,other['id'])):
        result=post(client,row['device_id']+'/ownership',{'version':1,'contact_id':contact,'reason':'تأیید مالکیت','evidence':'مدرک بررسی شده'})
        assert result.status_code==201,result.text
        decisions.append(result.json())
    data={'version':2,'target_device_id':target['device_id'],'target_version':2,'reason':'رفع تعارض دو شناسنامه','evidence':'مدارک هر دو مالک بررسی و مالک نهایی تعیین شد'}
    preview=post(client,source['device_id']+'/merge-preview',data)
    assert preview.status_code==200,preview.text
    assert preview.json()['owners']['source']['id']==decisions[0]['id']
    assert post(client,source['device_id']+'/merge',data).status_code==409
    data.update(source_ownership_id=decisions[0]['id'],target_ownership_id=decisions[1]['id'],resolved_owner_contact_id=other['id'])
    assert post(client,source['device_id']+'/merge',{**data,'target_ownership_id':str(uuid4())}).status_code==409
    key=str(uuid4());merged=post(client,source['device_id']+'/merge',data,key)
    assert merged.status_code==201,merged.text
    assert post(client,source['device_id']+'/merge',data,key).json()==merged.json()
    for row in (source,target):
        current=client.get('/api/repair/cases/'+row['id']).json()
        assert current['contact_id']==row['contact_id'] and current['owner_snapshot']==row['owner_snapshot']
        assert current['device_id']==row['device_id']
    events=client.get('/api/repair/devices/'+target['device_id']+'/identity-events').json()['items']
    assert events[0]['contact_id']==other['id'] and len(events)==2
    assert db.query(RepairDeviceIdentityEvent).filter(RepairDeviceIdentityEvent.id.in_([UUID(d['id']) for d in decisions])).count()==2
