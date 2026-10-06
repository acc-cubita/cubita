from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import Principal, get_principal, require_module, require_permission
from app.models.repair import RepairTechnicianSkill,RepairAppointment
from app.schemas.repair import ServiceRequestIn,TechnicianSkillsIn,AppointmentIn,AppointmentStatusIn,ServiceRequestAdmissionIn
from app.services import repair as core,repair_field as svc
from app.routers.repair_operations import once
router=APIRouter(prefix='/api/repair',tags=['repair'],dependencies=[Depends(require_module('repair')),Depends(require_permission('repair','view'))])

@router.get('/service-requests')
def requests(mine:bool=False,cursor:UUID|None=None,limit:int=Query(default=50,ge=1,le=200),db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    q=svc.visible(db,p)
    if mine: q=q.filter(svc.RepairServiceRequest.id.in_(db.query(RepairAppointment.request_id).filter(RepairAppointment.technician_id==p.user.id,RepairAppointment.status.in_(['scheduled','dispatched','onsite']))))
    if cursor: q=q.filter(svc.RepairServiceRequest.id>cursor)
    rows=q.order_by(svc.RepairServiceRequest.id).limit(limit+1).all()
    return {'items':[svc.projection(db,r) for r in rows[:limit]],'next_cursor':str(rows[limit-1].id) if len(rows)>limit else None}

@router.post('/service-requests',status_code=201,dependencies=[Depends(require_permission('repair','create'))])
def create(data:ServiceRequestIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    return svc.projection(db,once(db,request,p,'repair.service-request',data,lambda:svc.create(db,p,data),lambda rid:svc.request(db,p,rid)))

@router.get('/technicians/{uid}/skills')
def skills(uid:UUID,db:Session=Depends(get_db)):
    return {'type_ids':[s.type_id for s in db.query(RepairTechnicianSkill).filter_by(technician_id=uid)]}

@router.put('/technicians/{uid}/skills',dependencies=[Depends(require_permission('repair','approve'))])
def set_skills(uid:UUID,data:TechnicianSkillsIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    svc.skills(db,p,uid,data);return skills(uid,db)

@router.post('/service-requests/{rid}/appointments',status_code=201,dependencies=[Depends(require_permission('repair','approve'))])
def schedule(rid:UUID,data:AppointmentIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    svc.request(db,p,rid)
    def related(aid):
        a=db.query(RepairAppointment).filter_by(request_id=rid,id=aid).one_or_none()
        if a is None: raise HTTPException(404,'نوبت پیدا نشد.')
        return a
    return core.out(once(db,request,p,'repair.appointment:'+str(rid),data,lambda:svc.schedule(db,p,svc.request(db,p,rid,True),data),related))

@router.post('/service-requests/{rid}/appointments/{aid}/status',dependencies=[Depends(require_permission('repair','update'))])
def status(rid:UUID,aid:UUID,data:AppointmentStatusIn,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    row=svc.request(db,p,rid,True);appointment=db.query(RepairAppointment).filter_by(request_id=rid,id=aid).one_or_none()
    if appointment is None: raise HTTPException(404,'نوبت پیدا نشد.')
    return core.out(svc.appointment_status(db,p,row,appointment,data))

@router.post('/service-requests/{rid}/admission',status_code=201,dependencies=[Depends(require_permission('repair','create'))])
def admit(rid:UUID,data:ServiceRequestAdmissionIn,request:Request,db:Session=Depends(get_db),p:Principal=Depends(get_principal)):
    svc.request(db,p,rid)
    result=once(db,request,p,'repair.field-admission:'+str(rid),data,lambda:svc.admit(db,p,svc.request(db,p,rid,True),data),lambda cid:core.case(db,p,cid))
    return core.out(result)
