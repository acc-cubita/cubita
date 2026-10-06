"""گزارش وضعیت کنونی؛ درآمد و هزینه از اسناد واقعی، بدون دفتر سود موازی."""
from datetime import datetime, timezone, date
from decimal import Decimal
from app.models.invoices import SalesInvoice, PurchaseInvoice, WarehouseIssueLine, WarehouseIssue
from app.models.returns import SalesReturn
from app.models.issue_returns import WarehouseIssueReturn, WarehouseIssueReturnLine
from app.models.repair import RepairDocument, RepairPart, RepairPartMovement, RepairWork, RepairOutsource, RepairTechnicianFee, RepairEvent, RepairCustomerMessage, RepairWarrantyClaim
from app.services import repair as core, repair_finance


def current_cost(db,row):
    revenue=Decimal(0);parts=Decimal(0);outsourcing=Decimal(0);fees=Decimal(0);missing=[]
    refs=db.query(RepairDocument).filter_by(case_id=row.id).all()
    invoice_ids={r.document_id for r in refs if r.document_type=='sales_invoice'}
    for invoice in db.query(SalesInvoice).filter(SalesInvoice.id.in_(invoice_ids),SalesInvoice.voided_at.is_(None)):
        revenue+=invoice.total_amount
    # درآمد برگشت حتی اگر مدیر هنوز پیوند نمایشی آن را ثبت نکرده باشد لحاظ می‌شود.
    for returned in db.query(SalesReturn).filter(SalesReturn.sales_invoice_id.in_(invoice_ids),SalesReturn.voided_at.is_(None)):
        revenue-=returned.total_amount
    movements=db.query(RepairPartMovement).join(RepairPart,RepairPart.id==RepairPartMovement.part_id).filter(RepairPart.case_id==row.id,RepairPartMovement.action.in_(['consume','waste']),RepairPartMovement.document_type=='warehouse_issue').all()
    line_ids={m.document_line_id for m in movements if m.document_line_id}
    for line in db.query(WarehouseIssueLine).join(WarehouseIssue,WarehouseIssue.id==WarehouseIssueLine.issue_id).filter(WarehouseIssueLine.id.in_(line_ids),WarehouseIssue.voided_at.is_(None)):
        parts+=line.amount
    # هر برگشت فیزیکی دقیقاً یک‌بار از هزینه کم می‌شود؛ برگشت تجاری دوباره COGS کم نمی‌کند.
    for line in db.query(WarehouseIssueReturnLine).join(WarehouseIssueReturn,WarehouseIssueReturn.id==WarehouseIssueReturnLine.return_id).filter(WarehouseIssueReturnLine.warehouse_issue_line_id.in_(line_ids),WarehouseIssueReturn.voided_at.is_(None)):
        parts-=line.amount
    for job in db.query(RepairOutsource).filter_by(case_id=row.id):
        invoice=db.get(PurchaseInvoice,job.purchase_invoice_id) if job.purchase_invoice_id else None
        if invoice and not invoice.voided_at: outsourcing+=invoice.total_amount
        else: missing.append({'kind':'outsource','id':str(job.id),'message':'هزینهٔ واقعی برون‌سپاری ثبت نشده یا ابطال شده است.'})
    fee_rows=db.query(RepairTechnicianFee).filter_by(case_id=row.id).all()
    for fee in fee_rows:
        invoice=db.get(PurchaseInvoice,fee.purchase_invoice_id) if fee.purchase_invoice_id else None
        if invoice and not invoice.voided_at: fees+=invoice.total_amount
    for tech in {f.technician_id for f in fee_rows if not f.purchase_invoice_id}:
        if not any(f.technician_id==tech and f.purchase_invoice_id for f in fee_rows):
            missing.append({'kind':'technician_fee','id':str(tech),'message':'پیش‌نویس سهم هنوز هزینهٔ ثبت‌شده نیست.'})
    finance=repair_finance.financial(db,row)
    return {'revenue_net_rial':str(revenue),'parts_cost_rial':str(parts),'outsource_cost_rial':str(outsourcing),'technician_cost_rial':str(fees),
        'recorded_margin_rial':str(revenue-parts-outsourcing-fees),'remaining_balance_rial':finance['remaining_balance'],
        'pending_costs':missing,'basis':'current_posted_documents_excluding_vat; not_cash_profit; unrecorded_costs_excluded'}


def case_report(db,p,row,financial=False):
    now=datetime.now(timezone.utc);events=db.query(RepairEvent).filter_by(case_id=row.id).order_by(RepairEvent.created_at,RepairEvent.id).all()
    state='accepted';since=row.created_at;waits={}
    for event in events:
        if event.action=='status_changed':
            if state in {'awaiting_customer','awaiting_part'}:
                waits[state]=waits.get(state,0)+max(0,int((event.created_at-since).total_seconds()//60))
            state=event.detail['to'];since=event.created_at
    if state in {'awaiting_customer','awaiting_part'}: waits[state]=waits.get(state,0)+max(0,int((now-since).total_seconds()//60))
    surveys=db.query(RepairCustomerMessage).filter_by(case_id=row.id,kind='survey').all()
    minutes={}
    for work in db.query(RepairWork).filter_by(case_id=row.id):
        key=str(work.technician_id);minutes[key]=minutes.get(key,0)+work.work_minutes
    result={'id':row.id,'number':row.number,'status':row.status,'customer':row.owner_snapshot['name'],'admission_date':row.admission_date,'due_date':row.due_date,
        'age_days':max(0,(date.today()-row.admission_date).days),'overdue':bool(row.due_date and row.due_date<date.today() and row.status not in {'delivered','closed'}),
        'last_activity_at':events[-1].created_at if events else row.created_at,'waiting_minutes':waits,'technician_minutes':minutes,
        'open_outsources':db.query(RepairOutsource).filter_by(case_id=row.id,returned_at=None).count(),
        'revisit_count':db.query(RepairWarrantyClaim).filter_by(original_case_id=row.id).filter(RepairWarrantyClaim.revisit_case_id.in_(core.visible(db,p).with_entities(core.RepairCase.id))).count(),
        'survey_count':len(surveys),'average_rating':str(sum(s.rating for s in surveys)/len(surveys)) if surveys else None,
        'uncollected':row.status=='ready','financial':current_cost(db,row) if financial else None}
    return result
