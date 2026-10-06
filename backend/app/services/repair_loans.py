from datetime import datetime,timezone,date
from fastapi import HTTPException
from app.models.inventory import Contact
from app.models.assets import FixedAsset
from app.models.repair import RepairLoan
from app.schemas.assets import AssetAssignmentIn
from app.services import repair as core,assets


def checkout(db,p,row,data):
    core.check_version(row,data.version);core.editable_case(row)
    if data.due_date<date.today(): raise HTTPException(422,'موعد بازگشت نمی‌تواند گذشته باشد.')
    asset=assets.get_asset(db,data.asset_id,lock=True)
    if asset.is_disposed: raise HTTPException(409,'دارایی واگذارشده قابل امانت نیست.')
    assets._assert_not_loaned(db,asset.id)
    custodian=db.get(Contact,data.return_custodian_id)
    if custodian is None or not custodian.is_active or custodian.is_system or custodian.id==row.contact_id:
        raise HTTPException(422,'جمعدار فعال تعمیرگاه برای دریافت بازگشت انتخاب کنید.')
    assignment=assets._assign(db,asset.id,AssetAssignmentIn(assignment_date=date.today(),to_custodian_id=row.contact_id,
        to_location=f'امانت جایگزین پذیرش {row.number}',notes=f'تحویل به {data.receiver_name}؛ {data.authorization}'),p.user,kind='transfer',commit=False,return_assignment=True)
    loan=RepairLoan(case_id=row.id,asset_snapshot={'name':asset.name,'category':asset.category},checkout_assignment_id=assignment.id,
        checked_out_by_id=p.user.id,**data.model_dump(exclude={'version'}))
    db.add(loan);db.flush();core.event(db,p,row,'loan_checked_out',{'loan_id':str(loan.id),'asset_id':str(asset.id),'assignment_id':str(assignment.id),'receiver':data.receiver_name,'due_date':data.due_date.isoformat()})
    return loan


def checkin(db,p,row,loan,data):
    core.check_version(row,data.version)
    if loan.returned_at: raise HTTPException(409,'بازگشت این امانت قبلاً ثبت شده است.')
    asset=assets.get_asset(db,loan.asset_id,lock=True)
    if asset.is_disposed or asset.custodian_id!=row.contact_id: raise HTTPException(409,'وضعیت جمعداری دارایی با امانت یکسان نیست؛ سوابق دارایی را بررسی کنید.')
    assignment=assets._assign(db,asset.id,AssetAssignmentIn(assignment_date=date.today(),to_custodian_id=loan.return_custodian_id,
        to_location=loan.return_location,notes=f'بازگشت امانت پذیرش {row.number}؛ {data.confirmation}'),p.user,kind='transfer',commit=False,return_assignment=True,repair_loan_id=loan.id)
    loan.return_assignment_id=assignment.id;loan.returned_at=datetime.now(timezone.utc);loan.checked_in_by_id=p.user.id
    loan.condition_in=data.condition_in;loan.return_confirmation=data.confirmation
    core.event(db,p,row,'loan_checked_in',{'loan_id':str(loan.id),'assignment_id':str(assignment.id),'condition':data.condition_in,'confirmation':data.confirmation})
    return loan
