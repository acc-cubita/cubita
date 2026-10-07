from contextlib import nullcontext
from datetime import datetime,timezone,timedelta
from tests.test_repair import intake,admit
from app.models.repair import RepairDeviceSecret
from app import repair_jobs


def test_periodic_jobs_cleanup_without_carrier_io(client,db,user,tenant_id,intake,monkeypatch):
    row=admit(client,intake).json()
    db.add(RepairDeviceSecret(case_id=row['id'],ciphertext='expired-test-value',expires_at=datetime.now(timezone.utc)-timedelta(days=1),created_by_id=user.id));db.flush()
    def forbidden(*args,**kwargs): raise AssertionError('Default worker must never invoke carrier processing')
    monkeypatch.setattr(repair_jobs,'process_one',forbidden)
    result=repair_jobs.execute(tenant_id,session_factory=lambda:nullcontext(db))
    assert result['expired_secrets_removed']==1 and result['notifications_processed']==0 and result['sending_requested'] is False
    assert db.query(RepairDeviceSecret).count()==0
