"""Separate PostgreSQL transactions; locks cannot be exercised by HTTP fixture alone."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from threading import Barrier
from uuid import uuid4
import pytest
from fastapi import HTTPException
from conftest import tenant_session
from app.deps import Principal
from app.models.user import User
from app.models.tenant import Membership
from app.models.inventory import Contact
from app.models.repair import RepairBranch,RepairDeviceType,RepairDevice,RepairCase,RepairEvent,RepairDeviceIdentityEvent,RepairDelivery
from app.models.repair_completion import RepairCaseDetails,RepairTechnicalSummary,RepairRepresentativeAuthorization
from app.schemas.repair import AdmissionIn,WorkflowIn,RepairDeliveryIn
from app.schemas.repair_identity import OwnershipClaimIn,OwnershipClaimDecisionIn,DeviceOwnershipIn,TechnicalSummaryIn,RepresentativeIn,RepresentativeRevokeIn
from app.services import repair as core,repair_claims,repair_identity,repair_summary,repair_representation,repair_finance


@pytest.mark.parametrize('operation',['claim','summary','delivery_revoke'])
def test_parallel_professional_decisions_are_atomic(tenant_id,user,operation):
    def principal(db):
        return Principal(db.get(User,user.id),db.query(Membership).filter_by(tenant_id=tenant_id,user_id=user.id).one())
    with tenant_session(tenant_id) as db:
        branch=RepairBranch(name='professional-race-'+str(uuid4()));kind=RepairDeviceType(name='professional-race-'+str(uuid4()))
        person=Contact(name='آزمون همزمانی',is_customer=True,phone='09123456789')
        db.add_all([branch,kind,person]);db.flush();p=principal(db)
        row=core.create(db,p,AdmissionIn(contact_id=person.id,branch_id=branch.id,device={'type_id':kind.id,'model':'دستگاه آزمون'},reported_issue='بررسی رقابت',admission_date='2026-10-09',storage_location='آزمایش',terms='آزمایشی',approval_method='in_person'))
        if operation=='claim':
            claim=repair_claims.submit(db,p,row,OwnershipClaimIn(version=row.version,device_version=1,contact_id=person.id,reason='ادعای آزمون',evidence='مدرک بررسی شود'))
            claim_id=claim.id
            payload=OwnershipClaimDecisionIn(version=row.version,device_version=2,decision='approved',reason='تأیید آزمون',evidence='مدرک معتبر')
        elif operation=='summary':
            owner=repair_identity.ownership(db,p,row.device_id,DeviceOwnershipIn(version=1,contact_id=person.id,reason='مالک آزمون',evidence='مدرک معتبر'))
            payload=TechnicalSummaryIn(version=row.version,device_version=2,ownership_id=owner.id,previous_revision=0,content={'condition':'سالم است','repairs':'تنظیم','tests':'موفق','care':'خشک'},reason='بررسی فنی',privacy_reviewed=True)
        else:
            core.transition(db,p,row,WorkflowIn(version=row.version,status='cancelled',reason='آزمون بدون هزینه'))
            representative=repair_representation.approve(db,p,row,RepresentativeIn(version=row.version,operation='delivery',name='نماینده',phone=person.phone,evidence='مدرک معتبر',expires_at=datetime.now(timezone.utc)+timedelta(days=1)))
            representative_id=representative.id
            payload=RepairDeliveryIn(version=row.version,representation_id=representative.id,receiver_name=representative.name,receiver_phone=person.phone,authorization='وکالت مصوب',accessories='ندارد',checklist={'device':True,'accessories':True,'receiver_authorized':True})
        case_id,device_id,branch_id,kind_id,contact_id=row.id,row.device_id,branch.id,kind.id,person.id
        db.commit()
    gate=Barrier(2)
    def attempt(index):
        with tenant_session(tenant_id) as db:
            p=principal(db);gate.wait(timeout=10)
            try:
                row=core.case(db,p,case_id,lock=True)
                if operation=='claim':repair_claims.resolve(db,p,row,claim_id,payload)
                elif operation=='summary':repair_summary.approve(db,p,row,payload)
                elif index==0:repair_finance.delivery(db,p,row,payload)
                else:repair_representation.revoke(db,p,row,representative_id,RepresentativeRevokeIn(version=payload.version,reason='لغو همزمان'))
                db.commit();return 201
            except HTTPException as exc:
                db.rollback();return exc.status_code
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(attempt,range(2)))==[201,409]
        with tenant_session(tenant_id) as db:
            if operation=='claim':assert db.query(RepairDeviceIdentityEvent).filter_by(claim_id=claim_id).count()==1
            elif operation=='summary':assert db.query(RepairTechnicalSummary).filter_by(case_id=case_id).count()==1
            else:
                delivered=db.query(RepairDelivery).filter_by(case_id=case_id).count()
                revoked=db.query(RepairEvent).filter_by(case_id=case_id,action='representation_revoked').count()
                assert delivered+revoked==1
    finally:
        with tenant_session(tenant_id) as db:
            for model in (RepairTechnicalSummary,RepairRepresentativeAuthorization,RepairDelivery,RepairEvent,RepairCaseDetails):
                db.query(model).filter_by(case_id=case_id).delete(synchronize_session=False)
            db.query(RepairDeviceIdentityEvent).filter_by(device_id=device_id).delete(synchronize_session=False)
            for model,id in ((RepairCase,case_id),(RepairDevice,device_id),(RepairDeviceType,kind_id),(RepairBranch,branch_id),(Contact,contact_id)):
                db.query(model).filter_by(id=id).delete(synchronize_session=False)
            db.commit()
