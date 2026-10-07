from uuid import uuid4
from test_repair import intake,admit,approved_case
from tests.factories import make_item
from app.models.inventory import StockLedger
from app.models.accounting import JournalEntry


def post(client,path,data,key=None):
    return client.post('/api/repair/'+path,json=data,headers={'Idempotency-Key':key or str(uuid4())})


def current(client,case):
    return client.get('/api/repair/cases/'+case['id']).json()['version']


def test_service_profile_native_service_revisions_no_posting(client,db,intake):
    stock=make_item(db,name='قطعه')
    service=make_item(db,name='اجرت عیب‌یابی',is_service=True)
    path='branches/'+intake['branch_id']+'/service-profiles'
    data={'service_id':str(service.id),'suggested_charge':'12500','estimated_minutes':30}
    before=(db.query(StockLedger).count(),db.query(JournalEntry).count())
    assert post(client,path,{**data,'service_id':str(stock.id)}).status_code==422
    key=str(uuid4());first=post(client,path,data,key)
    assert first.status_code==201,first.text
    assert post(client,path,data,key).json()['id']==first.json()['id']
    second=post(client,path,{**data,'previous_revision':1,'suggested_charge':'15000'})
    assert second.status_code==201,second.text
    assert second.json()['revision']==2
    assert post(client,path,data).status_code==409
    latest=client.get('/api/repair/'+path).json()
    assert len(latest)==1 and latest[0]['suggested_charge']=='15000'
    assert first.json()['suggested_charge']=='12500'
    assert (db.query(StockLedger).count(),db.query(JournalEntry).count())==before


def test_measurement_exact_protocol_freeze_failure_and_review(client,intake):
    row=admit(client,intake).json()
    protocol_path='branches/'+intake['branch_id']+'/type-protocols'
    config={'type_id':intake['device']['type_id'],'metrics':[{'key':'voltage','title':'ولتاژ','unit':'V','minimum':'4.5','maximum':'5.5'}],'checklist':['اتصال ایمن']}
    result=post(client,protocol_path,config)
    assert result.status_code==201,result.text
    protocol=result.json();path='cases/'+row['id']
    data={'version':row['version'],'protocol_id':protocol['id'],'measurements':[{'key':'voltage','value':'4.499999'}],'checklist':{'اتصال ایمن':True},'root_cause':'افت تغذیه'}
    assert post(client,path+'/diagnostic-records',data).status_code==422
    data['test_failure_reason']='ولتاژ پایین‌تر از حد ایمن'
    key=str(uuid4());diagnosis=post(client,path+'/diagnostic-records',data,key)
    assert diagnosis.status_code==201,diagnosis.text
    assert diagnosis.json()['measurements'][0]['value']=='4.499999'
    assert diagnosis.json()['measurements'][0]['passed'] is False
    assert post(client,path+'/diagnostic-records',data,key).json()['id']==diagnosis.json()['id']
    changed=post(client,protocol_path,{**config,'previous_revision':1,'metrics':[{'key':'voltage','title':'ولتاژ','unit':'V','minimum':'3','maximum':'6'}]})
    assert changed.status_code==201,changed.text
    assert post(client,path+'/diagnostic-records',{**data,'version':current(client,row)}).status_code==409
    frozen=client.get('/api/repair/'+path+'/technical-records').json()['diagnostics'][0]
    assert frozen['protocol_snapshot']['revision']==1
    assert frozen['measurements'][0]['minimum']=='4.5'
    review=post(client,path+'/supervisor-reviews',{'version':current(client,row),'diagnostic_id':diagnosis.json()['id'],'approved':False,'reason':'تغذیه را اصلاح و دوباره آزمون کنید'})
    assert review.status_code==201,review.text
    assert post(client,path+'/supervisor-reviews',{'version':current(client,row),'diagnostic_id':diagnosis.json()['id'],'approved':True}).status_code==409


def test_pause_and_rejected_deadline_keep_original_agreement_and_ledgers(client,db,intake):
    row=admit(client,{**intake,'due_date':'2026-10-10'}).json();path='cases/'+row['id']
    before=(db.query(StockLedger).count(),db.query(JournalEntry).count())
    key=str(uuid4());pause=post(client,path+'/work-pauses',{'version':row['version'],'reason':'انتظار پاسخ'},key)
    assert pause.status_code==201,pause.text
    assert post(client,path+'/work-pauses',{'version':row['version'],'reason':'انتظار پاسخ'},key).json()['id']==pause.json()['id']
    assert post(client,path+'/work-pauses',{'version':current(client,row),'reason':'توقف دوم'}).status_code==409
    resumed=post(client,path+'/work-pauses/'+pause.json()['id']+'/end',{'version':current(client,row),'pause_version':1,'end_reason':'پاسخ رسید'})
    assert resumed.status_code==200,resumed.text
    assert resumed.json()['duration_seconds']>=0 and resumed.json()['ended_by_id']
    proposal=post(client,path+'/deadline-agreements',{'version':current(client,row),'new_due_date':'2026-10-15','reason':'تأمین قطعه'})
    assert proposal.status_code==201,proposal.text
    rejected=post(client,path+'/deadline-agreements/'+proposal.json()['id']+'/decision',{'version':current(client,row),'agreement_version':1,'decision':'rejected','customer_name':'مالک','method':'phone','reason':'با تأخیر موافق نیست'})
    assert rejected.status_code==200,rejected.text
    assert client.get('/api/repair/'+path).json()['due_date']=='2026-10-10'
    second=post(client,path+'/deadline-agreements',{'version':current(client,row),'new_due_date':'2026-10-12','reason':'توافق تازه'})
    accepted=post(client,path+'/deadline-agreements/'+second.json()['id']+'/decision',{'version':current(client,row),'agreement_version':1,'decision':'accepted','customer_name':'مالک','method':'written','reason':'تأیید موعد تازه'})
    assert accepted.status_code==200,accepted.text
    assert client.get('/api/repair/'+path).json()['due_date']=='2026-10-12'
    history=client.get('/api/repair/'+path+'/technical-records').json()['agreements']
    assert len(history)==2 and all(h['old_due_date']=='2026-10-10' for h in history)
    assert (db.query(StockLedger).count(),db.query(JournalEntry).count())==before


def test_cost_deadline_needs_same_new_approved_estimate(client,approved_case):
    row=approved_case;path='cases/'+row['id']
    estimate=post(client,path+'/estimates',{'version':current(client,row),'valid_until':'2099-01-01','duration_days':3,'customer_ceiling':'100','options':[{'title':'اصلاح','lines':[{'kind':'labor','title':'اجرت','qty':'1','unit_price':'100'}]}]})
    assert estimate.status_code==201,estimate.text
    proposal=post(client,path+'/deadline-agreements',{'version':current(client,row),'new_due_date':'2026-10-20','estimate_id':estimate.json()['id'],'reason':'تغییر هزینه و موعد'})
    assert proposal.status_code==201,proposal.text
    decision={'version':current(client,row),'agreement_version':1,'decision':'accepted','customer_name':'مالک','method':'written','reason':'پذیرش تغییر'}
    assert post(client,path+'/deadline-agreements/'+proposal.json()['id']+'/decision',decision).status_code==409
    approved=post(client,path+'/estimates/'+estimate.json()['id']+'/decision',{'version':current(client,row),'decision':'approved','option_index':0,'method':'written','customer_name':'مالک','authorized_ceiling':'100'})
    assert approved.status_code==201,approved.text
    accepted=post(client,path+'/deadline-agreements/'+proposal.json()['id']+'/decision',{**decision,'version':current(client,row)})
    assert accepted.status_code==200,accepted.text
    assert len(client.get('/api/repair/'+path).json()['estimates'])==2


def test_knowledge_privacy_revision_and_manager_confirmation(client,intake):
    path='branches/'+intake['branch_id']+'/knowledge'
    data={'type_id':intake['device']['type_id'],'title':'رفع افت تغذیه','symptoms':'روشن نمی‌شود','root_cause':'خازن خراب','solution':'خازن را بررسی کنید'}
    assert post(client,path,{**data,'solution':'تماس ۰۹۱۲۳۴۵۶۷۸۹'}).status_code==422
    assert post(client,path,{**data,'solution':'password: 12345'}).status_code==422
    key=str(uuid4());first=post(client,path,data,key)
    assert first.status_code==201,first.text
    article=first.json()
    assert post(client,path,data,key).json()['id']==article['id']
    assert post(client,'knowledge/'+article['id']+'/approval',{'version':1,'privacy_confirmed':False}).status_code==422
    approved=post(client,'knowledge/'+article['id']+'/approval',{'version':1,'privacy_confirmed':True})
    assert approved.status_code==200,approved.text
    second=post(client,path,{**data,'family_id':article['family_id'],'previous_revision':1,'solution':'خازن و مسیر تغذیه بررسی شوند'})
    assert second.status_code==201,second.text
    assert second.json()['revision']==2 and second.json()['approved_at'] is None
    history=client.get('/api/repair/'+path).json()
    assert len(history)==2
    assert next(h for h in history if h['id']==article['id'])['solution']==data['solution']


def test_confirmed_timer_consumed_once_work_snapshot_survives_time_correction(client,db,user,approved_case):
    from app.models.repair import RepairWork
    from app.models.repair_completion import RepairWorkTimeLink
    row=approved_case;path='cases/'+row['id']
    timer=post(client,path+'/time-sessions',{'version':current(client,row)}).json()
    stopped=post(client,'time-sessions/'+timer['id']+'/actions',{'version':timer['version'],'action':'stop'}).json()
    confirmed=post(client,'time-sessions/'+timer['id']+'/actions',{'version':stopped['version'],'action':'confirm','seconds':70,'reason':'زمان آماده‌سازی نیز تأیید شد'})
    assert confirmed.status_code==200,confirmed.text
    data={'version':current(client,row),'technician_id':str(user.id),'time_session_id':timer['id'],'description':'کار با زمان تأییدشده','work_minutes':999,'charge_amount':'0'}
    key=str(uuid4());work=post(client,path+'/work',data,key)
    assert work.status_code==201,work.text
    assert work.json()['work_minutes']==2
    assert post(client,path+'/work',data,key).json()['id']==work.json()['id']
    assert post(client,path+'/work',{**data,'version':current(client,row)}).status_code==409
    corrected=post(client,'time-sessions/'+timer['id']+'/actions',{'version':confirmed.json()['version'],'action':'correct','seconds':20,'reason':'حذف توقف از زمان واقعی'})
    assert corrected.status_code==200,corrected.text
    db.expire_all()
    assert db.query(RepairWork).filter_by(id=work.json()['id']).one().work_minutes==2
    assert db.query(RepairWorkTimeLink).filter_by(session_id=timer['id']).one().confirmed_seconds==70
    assert client.get('/api/repair/time-sessions',params={'case_id':row['id']}).json()[0]['used_work_id']==work.json()['id']


def test_required_supervisor_review_uses_same_work_revision(client,user,approved_case,intake):
    row=approved_case;path='cases/'+row['id']
    work=post(client,path+'/work',{'version':current(client,row),'technician_id':str(user.id),'description':'تعمیر واقعی','work_minutes':1,'charge_amount':'0'})
    assert work.status_code==201,work.text
    protocol=post(client,'branches/'+intake['branch_id']+'/type-protocols',{'type_id':intake['device']['type_id'],'requires_supervisor_review':True}).json()
    record=post(client,path+'/diagnostic-records',{'version':current(client,row),'protocol_id':protocol['id'],'root_cause':'اتصال تغذیه اصلاح شد'}).json()
    quality=post(client,path+'/quality',{'version':current(client,row),'passed':True,'result':'آزمون موفق'})
    assert quality.status_code==201,quality.text
    def ready(): return client.post('/api/repair/'+path+'/status',json={'version':current(client,row),'status':'ready','exceptional':True,'reason':'پایان آزمون'})
    assert ready().status_code==409
    review=post(client,path+'/supervisor-reviews',{'version':current(client,row),'diagnostic_id':record['id'],'approved':True})
    assert review.status_code==201,review.text
    assert ready().status_code==200
