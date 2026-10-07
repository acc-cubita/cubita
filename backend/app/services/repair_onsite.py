"""Immutable onsite actions and revision-bound signatures; no automatic billing."""
from hashlib import sha256
import json
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from app.models.repair import RepairAppointment
from app.models.repair_completion import RepairOnsiteAction,RepairOnsiteApproval
from app.services import repair as core,repair_field as field


def action_row(db,p,request_id,action_id):
    field.request(db,p,request_id)
    row=db.query(RepairOnsiteAction).filter_by(request_id=request_id,id=action_id).one_or_none()
    if row is None: raise HTTPException(404,'اقدام در محل پیدا نشد.')
    return row


def create(db,p,request,appointment_id,data):
    core.check_version(request,data.version)
    appointment=db.query(RepairAppointment).filter_by(request_id=request.id,id=appointment_id).one_or_none()
    if appointment is None: raise HTTPException(404,'نوبت پیدا نشد.')
    if appointment.technician_id!=p.user.id and not p.has_permission('repair','approve'): raise HTTPException(403,'اقدام فقط توسط تکنسین همان نوبت یا مدیر ثبت می‌شود.')
    if appointment.status!='onsite': raise HTTPException(409,'اقدام در محل فقط پس از ثبت حضور و پیش از پایان نوبت مجاز است.')
    row=RepairOnsiteAction(request_id=request.id,appointment_id=appointment.id,description=data.description,result=data.result,recorded_by_id=p.user.id)
    db.add(row);db.flush();field.event(db,p,request,'onsite_action',{'action_id':str(row.id),'appointment_id':str(appointment.id)});return row


def approve(db,p,request,action,data):
    core.check_version(request,data.version);core.check_version(action,data.action_version)
    if db.query(RepairOnsiteApproval).filter_by(action_id=action.id,action_version=action.version).first(): raise HTTPException(409,'این نسخهٔ اقدام قبلاً تأیید شده است.')
    appointment=db.get(RepairAppointment,action.appointment_id)
    if appointment.status=='cancelled': raise HTTPException(409,'نوبت لغوشده قابل تأیید نیست.')
    if appointment.technician_id!=p.user.id and not p.has_permission('repair','approve'): raise HTTPException(403,'تأیید در محل دسترسی نوبت می‌خواهد.')
    signature=jsonable_encoder(data.strokes)
    snapshot={'action_id':str(action.id),'action_version':action.version,'description':action.description,'result':action.result,'appointment_id':str(action.appointment_id),'request_id':str(request.id),'approver_name':data.approver_name,'employee_id':str(p.user.id),'employee_name':p.user.name}
    digest=sha256(json.dumps({'document':snapshot,'signature':signature},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    row=RepairOnsiteApproval(request_id=request.id,action_id=action.id,action_version=action.version,approver_name=data.approver_name,signature=signature,snapshot=snapshot,signature_hash=digest,recorded_by_id=p.user.id)
    db.add(row);db.flush();field.event(db,p,request,'onsite_approved',{'approval_id':str(row.id),'action_id':str(action.id)});return row
