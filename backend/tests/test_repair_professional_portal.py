from uuid import uuid4
from urllib.parse import urlsplit, parse_qs
from test_repair import intake
from test_repair_summary import setup_summary, post


def test_transferred_summary_real_portal_hides_source_and_expires_with_ownership(client, db, intake):
    old, new, path, data = setup_summary(client, intake)
    result = post(client, path + '/technical-summaries', data)
    assert result.status_code == 201, result.text
    def portal(row):
        prefix = '/api/repair/cases/' + row['id']
        version = client.get(prefix).json()['version']
        link = client.post(prefix + '/portal-links', json={'version': version, 'expires_days': 7})
        assert link.status_code == 201, link.text
        credential = parse_qs(urlsplit(link.json()['url']).fragment)['token'][0]
        return {'Authorization': 'RepairPortal ' + credential}
    old_auth, new_auth = portal(old), portal(new)
    assert client.get('/api/repair-portal/case', headers=old_auth).json()['technical_summaries'] == []
    response = client.get('/api/repair-portal/case', headers=new_auth)
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    summaries = response.json()['technical_summaries']
    assert summaries == [result.json()]
    assert set(summaries[0]) == {'id', 'revision', 'approved_at', 'content'}
    assert old['id'] not in response.text
    assert old['contact_id'] not in response.text
    assert data['reason'] not in response.text
    # A transferable summary does not grant access to any original attachment.
    attachment = client.post(path + '/attachments', files={'file': ('private.pdf', b'%PDF-private-owner', 'application/pdf')})
    assert attachment.status_code == 200, attachment.text
    assert client.get('/api/repair-portal/attachments/' + attachment.json()['id'], headers=new_auth).status_code == 404
    owner = post(client, '/api/repair/devices/' + old['device_id'] + '/ownership', {
        'version': 2, 'previous_ownership_id': data['ownership_id'], 'contact_id': new['contact_id'],
        'reason': 'بازبینی مالکیت', 'evidence': 'مدرک جدید بررسی شد',
    })
    assert owner.status_code == 201, owner.text
    assert client.get('/api/repair-portal/case', headers=new_auth).json()['technical_summaries'] == []
