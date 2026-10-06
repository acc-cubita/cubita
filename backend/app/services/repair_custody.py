from datetime import datetime,timezone
from fastapi import HTTPException
from app.models.repair import RepairCustodyTransfer,RepairCustodyLeg,RepairPart,RepairOutsource
from app.services import repair as core,repair_parts


def assert_present(db,row):
    if db.query(RepairCustodyTransfer).filter_by(case_id=row.id,status='in_transit').first():
        raise HTTPException(409,'دستگاه در حمل است؛ ابتدا دریافت واقعی آن را ثبت کنید.')


def dispatch(db,p,row,data):
    core.check_version(row,data.version);core.editable_case(row);assert_present(db,row)
    destination=core.branch(db,p,data.to_branch_id)
    if not destination.is_active: raise HTTPException(422,'شعبهٔ مقصد فعال نیست.')
    if db.query(RepairOutsource).filter_by(case_id=row.id,returned_at=None).first(): raise HTTPException(409,'دستگاه هنوز در برون‌سپاری باز است.')
    if any(part.status=='reserved' or repair_parts.quantities(db,part)[1]>0 for part in db.query(RepairPart).filter_by(case_id=row.id)):
        raise HTTPException(409,'پیش از حمل دستگاه، قطعات نزد تعمیرگاه و رزرو را تعیین تکلیف کنید.')
    transfer=RepairCustodyTransfer(case_id=row.id,from_branch_id=row.branch_id,from_location=row.storage_location,
        dispatched_by_id=p.user.id,**data.model_dump(exclude={'version'}))
    db.add(transfer);db.flush();row.storage_location='در حمل: '+data.carrier_name[:180]
    core.event(db,p,row,'custody_dispatched',{'transfer_id':str(transfer.id),'to_branch_id':str(destination.id),'carrier':data.carrier_name,'reason':data.reason})
    return transfer


def handover(db,p,row,transfer,data):
    core.check_version(row,data.version)
    if transfer.status!='in_transit': raise HTTPException(409,'این حمل پایان یافته است.')
    leg=RepairCustodyLeg(transfer_id=transfer.id,from_carrier=transfer.carrier_name,to_carrier=data.carrier_name,
        phone=data.carrier_phone,location=data.location,confirmation=data.confirmation,actor_id=p.user.id)
    db.add(leg);transfer.carrier_name=data.carrier_name;transfer.carrier_phone=data.carrier_phone
    row.storage_location='در حمل: '+data.carrier_name[:180]
    db.flush();core.event(db,p,row,'custody_handover',{'transfer_id':str(transfer.id),'leg_id':str(leg.id),'from':leg.from_carrier,'to':leg.to_carrier,'location':leg.location,'confirmation':leg.confirmation})
    return leg


def receive(db,p,row,transfer,data):
    core.check_version(row,data.version)
    if transfer.status!='in_transit': raise HTTPException(409,'دریافت قبلاً ثبت شده است.')
    target=transfer.from_branch_id if data.return_to_source else transfer.to_branch_id
    core.branch(db,p,target)
    transfer.status='returned' if data.return_to_source else 'received';transfer.received_at=datetime.now(timezone.utc)
    transfer.received_by_id=p.user.id;transfer.receiver_name=data.receiver_name;transfer.receipt_confirmation=data.confirmation
    row.branch_id=target;row.storage_location=transfer.from_location if data.return_to_source else transfer.destination_location
    row.assigned_to_id=None
    core.event(db,p,row,'custody_received',{'transfer_id':str(transfer.id),'branch_id':str(target),'receiver':data.receiver_name,'confirmation':data.confirmation,'return_to_source':data.return_to_source})
    return transfer


def overview(db,row):
    transfers=db.query(RepairCustodyTransfer).filter_by(case_id=row.id).order_by(RepairCustodyTransfer.created_at.desc()).limit(200).all()
    result=[]
    for transfer in transfers:
        item=core.out(transfer);item['legs']=[core.out(l) for l in db.query(RepairCustodyLeg).filter_by(transfer_id=transfer.id).order_by(RepairCustodyLeg.created_at).limit(200)]
        result.append(item)
    return result
