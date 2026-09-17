from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.counters import DOC_SALES_QUOTATION
from app.models.inventory import Contact, Item
from app.models.invoices import SalesInvoice, SalesInvoiceLine
from app.models.quotations import SalesQuotation, SalesQuotationLine
from app.models.user import User
from app.schemas.invoices import SalesInvoiceIn, SalesInvoiceLineIn
from app.schemas.quotations import SalesQuotationConvertIn, SalesQuotationIn
from app.services.inventory import post_sales_invoice
from app.services.numbering import next_document_number

QUOTATION_TRANSITIONS = {"draft": {"sent", "accepted", "rejected"}, "sent": {"accepted", "rejected"}}


def _customer(db: Session, data: SalesQuotationIn) -> tuple[Contact | None, dict]:
    contact = db.get(Contact, data.contact_id) if data.contact_id else None
    if data.contact_id and contact is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مشتری انتخاب‌شده یافت نشد")
    if contact is not None and not contact.is_customer:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "طرف حساب انتخاب‌شده مشتری نیست")
    if contact is None:
        return None, {"name": data.customer_name or "", "name2": data.customer_name2}
    return contact, {key: (getattr(contact, key, None) or "") for key in (
        "name", "name2", "national_id", "economic_code", "registration_no",
        "tax_id", "postal_code", "phone", "address",
    )}


def _make_lines(db: Session, data: SalesQuotationIn) -> tuple[list[SalesQuotationLine], Decimal]:
    items = {i.id: i for i in db.query(Item).filter(Item.id.in_([line.item_id for line in data.lines])).all()}
    lines: list[SalesQuotationLine] = []
    total = Decimal(0)
    for incoming in data.lines:
        item = items.get(incoming.item_id)
        if item is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کالا با شناسه {incoming.item_id} یافت نشد")
        total += incoming.qty * incoming.unit_price
        lines.append(SalesQuotationLine(
            item_id=incoming.item_id, qty=incoming.qty, unit_price=incoming.unit_price,
            description=incoming.description, item_code_snapshot=item.sku,
            item_name_snapshot=item.name, unit_snapshot=item.unit,
        ))
    return lines, total


def attach_progress(db: Session, quotations: list[SalesQuotation]) -> None:
    if not quotations:
        return
    ids = [q.id for q in quotations]
    rows = (
        db.query(SalesInvoiceLine.source_quotation_line_id, func.sum(SalesInvoiceLine.qty))
        .join(SalesInvoice, SalesInvoice.id == SalesInvoiceLine.invoice_id)
        .filter(SalesInvoice.source_quotation_id.in_(ids), SalesInvoice.voided_at.is_(None), SalesInvoiceLine.source_quotation_line_id.is_not(None))
        .group_by(SalesInvoiceLine.source_quotation_line_id).all()
    )
    invoiced = {line_id: Decimal(qty) for line_id, qty in rows}
    invoice_ids: dict[UUID, list[UUID]] = {}
    for invoice_id, quotation_id in db.query(SalesInvoice.id, SalesInvoice.source_quotation_id).filter(
        SalesInvoice.source_quotation_id.in_(ids), SalesInvoice.voided_at.is_(None)
    ).all():
        invoice_ids.setdefault(quotation_id, []).append(invoice_id)
    today = date.today()
    for quotation in quotations:
        done = quoted = Decimal(0)
        for line in quotation.lines:
            line.invoiced_qty = invoiced.get(line.id, Decimal(0))
            line.remaining_invoiceable_qty = max(Decimal(line.qty) - line.invoiced_qty, Decimal(0))
            # خروج، سند مستقل می‌خواهد؛ آن را با تبدیل تجاری یکی نمی‌کنیم.
            line.issued_qty = Decimal(0)
            line.remaining_issueable_qty = Decimal(line.qty) if not line.item.is_service else Decimal(0)
            quoted += Decimal(line.qty)
            done += line.invoiced_qty
        quotation.commercial_status = "not_invoiced" if done == 0 else "fully_invoiced" if done >= quoted else "partially_invoiced"
        quotation.is_expired = bool(quotation.valid_until and quotation.valid_until < today)
        quotation.invoiced_invoice_ids = invoice_ids.get(quotation.id, [])


def create_quotation(db: Session, data: SalesQuotationIn, user: User) -> SalesQuotation:
    _contact, snapshot = _customer(db, data)
    lines, total = _make_lines(db, data)
    quotation = SalesQuotation(
        number=next_document_number(db, DOC_SALES_QUOTATION), quotation_date=data.quotation_date,
        valid_until=data.valid_until, contact_id=data.contact_id,
        customer_name=(data.customer_name or None) if not data.contact_id else None,
        customer_name2=data.customer_name2, customer_snapshot=snapshot,
        delivery_location=data.delivery_location, warehouse_id=data.warehouse_id,
        sale_type_id=data.sale_type_id, currency_code=data.currency_code or None,
        exchange_rate=data.exchange_rate, description=data.description, total_amount=total,
        created_by_id=user.id, lines=lines,
    )
    db.add(quotation)
    db.flush()
    db.refresh(quotation)
    attach_progress(db, [quotation])
    return quotation


def _has_active_invoice(db: Session, quotation_id: UUID) -> bool:
    return db.query(SalesInvoice.id).filter(SalesInvoice.source_quotation_id == quotation_id, SalesInvoice.voided_at.is_(None)).first() is not None


def update_quotation(db: Session, quotation_id: UUID, data: SalesQuotationIn, user: User) -> SalesQuotation:
    quotation = db.get(SalesQuotation, quotation_id)
    if quotation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیش‌فاکتور یافت نشد")
    if quotation.terminated_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "پیش‌فاکتور خاتمه‌یافته قابل ویرایش نیست؛ ابتدا آن را بازگشایی کنید")
    if _has_active_invoice(db, quotation.id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این پیش‌فاکتور به فاکتور فروش تبدیل شده است؛ ابتدا سند وابسته را اصلاح یا باطل کنید")
    _contact, snapshot = _customer(db, data)
    lines, total = _make_lines(db, data)
    quotation.lines = lines
    for name, value in {
        "quotation_date": data.quotation_date, "valid_until": data.valid_until,
        "contact_id": data.contact_id, "customer_name": (data.customer_name or None) if not data.contact_id else None,
        "customer_name2": data.customer_name2, "customer_snapshot": snapshot,
        "delivery_location": data.delivery_location, "warehouse_id": data.warehouse_id,
        "sale_type_id": data.sale_type_id, "currency_code": data.currency_code or None,
        "exchange_rate": data.exchange_rate, "description": data.description, "total_amount": total,
    }.items():
        setattr(quotation, name, value)
    db.flush()
    db.refresh(quotation)
    attach_progress(db, [quotation])
    return quotation


def update_quotation_status(db: Session, quotation_id: UUID, new_status: str, user: User) -> SalesQuotation:
    quotation = db.get(SalesQuotation, quotation_id)
    if quotation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیش‌فاکتور یافت نشد")
    if quotation.terminated_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "پیش‌فاکتور خاتمه‌یافته قابل تغییر نیست؛ ابتدا آن را بازگشایی کنید")
    if new_status not in QUOTATION_TRANSITIONS.get(quotation.status, set()):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"انتقال وضعیت از «{quotation.status}» به «{new_status}» مجاز نیست")
    quotation.status = new_status
    db.flush(); db.refresh(quotation); attach_progress(db, [quotation])
    return quotation


def set_termination(db: Session, quotation_id: UUID, *, terminated: bool, user: User) -> SalesQuotation:
    quotation = db.query(SalesQuotation).filter(SalesQuotation.id == quotation_id).with_for_update().one_or_none()
    if quotation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیش‌فاکتور یافت نشد")
    quotation.terminated_at = datetime.now(timezone.utc) if terminated else None
    quotation.terminated_by_id = user.id if terminated else None
    db.flush(); db.refresh(quotation); attach_progress(db, [quotation])
    return quotation


def duplicate_quotation(db: Session, quotation_id: UUID, user: User) -> SalesQuotation:
    source = db.query(SalesQuotation).options(selectinload(SalesQuotation.lines)).filter(SalesQuotation.id == quotation_id).one_or_none()
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیش‌فاکتور یافت نشد")
    return create_quotation(db, SalesQuotationIn(
        quotation_date=date.today(), valid_until=None, warehouse_id=source.warehouse_id,
        contact_id=source.contact_id, customer_name=source.customer_name,
        customer_name2=source.customer_name2, delivery_location=source.delivery_location,
        sale_type_id=source.sale_type_id, currency_code=source.currency_code,
        exchange_rate=Decimal(source.exchange_rate), description=source.description,
        lines=[{"item_id": l.item_id, "qty": l.qty, "unit_price": l.unit_price, "description": l.description} for l in source.lines],
    ), user)


def convert_quotation_to_invoice(db: Session, quotation_id: UUID, data: SalesQuotationConvertIn, user: User) -> SalesInvoice:
    quotation = db.query(SalesQuotation).options(selectinload(SalesQuotation.lines)).filter(SalesQuotation.id == quotation_id).with_for_update().one_or_none()
    if quotation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیش‌فاکتور یافت نشد")
    if quotation.terminated_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "پیش‌فاکتور خاتمه یافته است؛ ابتدا آن را بازگشایی کنید")
    if quotation.status == "rejected":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "پیش‌فاکتور ردشده قابل تبدیل به فاکتور نیست")
    attach_progress(db, [quotation])
    by_id = {line.id: line for line in quotation.lines}
    requested = {line.quotation_line_id: line.qty for line in data.lines}
    if len(requested) != len(data.lines):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "هر ردیف پیش‌فاکتور در تبدیل فقط یک‌بار مجاز است")
    if not requested:
        requested = {line.id: line.remaining_invoiceable_qty for line in quotation.lines if line.remaining_invoiceable_qty > 0}
    invoice_lines = []
    for line_id, qty in requested.items():
        line = by_id.get(line_id)
        if line is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "ردیف انتخاب‌شده متعلق به این پیش‌فاکتور نیست")
        if qty > line.remaining_invoiceable_qty:
            raise HTTPException(status.HTTP_409_CONFLICT, f"مقدار تبدیل «{line.item_name_snapshot or line.item.name}» از مانده بیشتر است")
        invoice_lines.append(SalesInvoiceLineIn(item_id=line.item_id, qty=qty, unit_price=line.unit_price, description=line.description, source_quotation_line_id=line.id))
    if not invoice_lines:
        raise HTTPException(status.HTTP_409_CONFLICT, "تمام مقدار این پیش‌فاکتور قبلاً فاکتور شده است")
    warehouse_id = data.warehouse_id or quotation.warehouse_id
    invoice = post_sales_invoice(db, SalesInvoiceIn(
        invoice_date=date.today(), warehouse_id=warehouse_id, contact_id=quotation.contact_id,
        customer_name2=quotation.customer_name2, delivery_location=quotation.delivery_location,
        description=quotation.description, sale_type_id=quotation.sale_type_id,
        currency_code=quotation.currency_code, exchange_rate=quotation.exchange_rate,
        source_quotation_id=quotation.id, lines=invoice_lines,
    ), user, move_inventory=False, issue_accounting=False)
    if quotation.converted_invoice_id is None:
        quotation.converted_invoice_id = invoice.id
    db.flush(); attach_progress(db, [quotation])
    if quotation.commercial_status == "fully_invoiced":
        quotation.status = "converted"
    return invoice
