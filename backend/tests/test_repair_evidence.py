from uuid import uuid4
import base64
import hashlib
from test_repair import intake, admit

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


def post(client, path, data, key=None):
    return client.post(path, json=data, headers={'Idempotency-Key':key or str(uuid4())})


def evidence(version=1, previous=0):
    return {'version':version,'previous_revision':previous,'reason':'ثبت وضعیت پذیرش',
            'accessories':[{'title':'شارژر','quantity':2,'condition':'سالم'}],
            'tests':[{'title':'روشن شدن','result':'not_tested','reason':'شارژ ندارد'}], 'images':[]}


def test_evidence_snapshot_is_bound_to_signature_and_amendment_preserves_it(client,intake):
    row=admit(client,intake).json(); path='/api/repair/cases/'+row['id']
    photo=client.post(path+'/attachments',files={'file':('device.png',PNG,'image/png')})
    assert photo.status_code==200,photo.text
    row=client.get(path).json()
    data=evidence(row['version'])
    data['images']=[{'attachment_id':photo.json()['id'],'view':'پشت','marks':[{'x':0.2,'y':0.4,'category':'خراش','description':'خراش روی بدنه'}]}]
    key=str(uuid4())
    saved=post(client,path+'/intake-evidence',data,key)
    assert saved.status_code==201,saved.text
    assert post(client,path+'/intake-evidence',data,key).json()==saved.json()
    assert saved.json()['snapshot']['images'][0]['sha256']==hashlib.sha256(PNG).hexdigest()
    current=client.get(path).json()
    signature={'version':current['version'],'kind':'intake','signer_name':'مالک','signer_relation':'مشتری','strokes':[[[10,20],[30,40]]]}
    signed=post(client,path+'/acknowledgments',signature)
    assert signed.status_code==201,signed.text
    current=client.get(path).json()
    revised={**data,'version':current['version'],'previous_revision':1,'accessories':[]}
    assert post(client,path+'/intake-evidence',revised).status_code==201
    history=client.get(path+'/acknowledgments').json()
    assert history[0]['document_snapshot']['intake_evidence']['snapshot']['accessories'][0]['quantity']==2
    current=client.get(path).json()
    assert post(client,path+'/acknowledgments',{**signature,'version':current['version']}).status_code==201
    history=client.get(path+'/acknowledgments').json()
    assert history[0]['document_hash']!=history[1]['document_hash']
    assert len(client.get(path+'/intake-evidence').json()['items'])==2


def test_evidence_rejects_foreign_case_images_missing_reason_and_stale_revision(client,intake):
    first,second=[admit(client,intake).json() for _ in range(2)]
    path='/api/repair/cases/'+first['id']
    photo=client.post('/api/repair/cases/'+second['id']+'/attachments',files={'file':('device.png',PNG,'image/png')}).json()
    data=evidence()
    data['images']=[{'attachment_id':photo['id'],'view':'پشت'}]
    assert post(client,path+'/intake-evidence',data).status_code==422
    invalid=evidence();invalid['tests'][0]['reason']=''
    assert post(client,path+'/intake-evidence',invalid).status_code==422
    assert post(client,path+'/intake-evidence',evidence()).status_code==201
    current=client.get(path).json()
    assert post(client,path+'/intake-evidence',evidence(current['version'],0)).status_code==409


def test_real_browser_professional_intake(client, db, intake):
    import os, socket, threading, subprocess, time
    from pathlib import Path
    import pytest, uvicorn
    from app.main import app
    from app.models.repair_completion import RepairIntakeEvidence
    if os.environ.get('REPAIR_PROFESSIONAL_BROWSER')!='1':
        pytest.skip('Requires WEB_ONLY Vite on localhost:5187')
    row=admit(client,intake).json()
    photo=client.post('/api/repair/cases/'+row['id']+'/attachments',files={'file':('device.png',PNG,'image/png')}).json()
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(128)
    port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,lifespan='off',log_level='warning'))
    thread=threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True);thread.start()
    try:
        deadline=time.monotonic()+10
        while not server.started and time.monotonic()<deadline:thread.join(.05)
        assert server.started
        env={**os.environ,'REPAIR_QA_API_URL':f'http://127.0.0.1:{port}','REPAIR_QA_CASE':row['id'],'REPAIR_QA_PHOTO':photo['id']}
        result=subprocess.run(['node','scripts/verify-repair-professional.mjs'],cwd=Path(__file__).resolve().parents[2]/'desktop',env=env,capture_output=True,text=True,timeout=120,encoding='utf-8')
        assert result.returncode==0,result.stdout+'\n'+result.stderr
        records=db.query(RepairIntakeEvidence).order_by(RepairIntakeEvidence.revision).all()
        assert len(records)==2
        assert len(records[-1].snapshot['images'][0]['marks'])==2
    finally:
        server.should_exit=True;thread.join(10);listener.close()
