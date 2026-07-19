from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.inventory import Item
from app.models.invoices import SalesInvoice
from app.models.quotations import SalesQuotation, SalesQuotationLine
from app.models.user import User
from app.schemas.invoices import SalesInvoiceIn, SalesInvoiceLineIn
from app.schemas.quotations import SalesQuotationIn
from app.services.inventory import post_sales_invoice

# چرخه‌ی مجاز وضعیت پیش‌فاکتور: از draft می‌توان مستقیم فرستاد/رد کرد؛ تبدیل به فاکتور یک اقدام جدا است
QUOTATION_TRANSITIONS = {
    "draft": {"sent", "accepted", "rejected"},
    "sent": {"accepted", "rejected"},
}


def create_quotation(db: Session, data: SalesQuotationIn, user: User) -> SalesQuotation:
    items_by_id = {i.id: i for i in db.query(Item).filter(Item.id.in_([l.item_id for l in data.lines])).all()}
    for line in data.lines:
        if line.item_id not in items_by_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کالا با شناسه {line.item_id} یافت نشد")

    number = db.execute(text("SELECT nextval('sales_quotation_number_seq')")).scalar_one()

    total_amount = Decimal(0)
    lines: list[SalesQuotationLine] = []
    for line in data.lines:
        total_amount += line.qty * line.unit_price
        lines.append(
            SalesQuotationLine(
                item_id=line.item_id, qty=line.qty, unit_price=line.unit_price, description=line.description
            )
        )

    quotation = SalesQuotation(
        number=number,
        quotation_date=data.quotation_date,
        valid_until=data.valid_until,
        contact_id=data.contact_id,
        warehouse_id=data.warehouse_id,
        description=data.description,
        total_amount=total_amount,
        created_by_id=user.id,
        lines=lines,
    )
    db.add(quotation)
    db.flush()
    db.refresh(quotation)
    return quotation


def update_quotation_status(db: Session, quotation_id: UUID, new_status: str, user: User) -> SalesQuotation:
    quotation = db.get(SalesQuotation, quotation_id)
    if quotation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیش‌فاکتور یافت نشد")

    allowed = QUOTATION_TRANSITIONS.get(quotation.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"انتقال وضعیت از «{quotation.status}» به «{new_status}» مجاز نیست"
        )

    quotation.status = new_status
    db.flush()
    db.refresh(quotation)
    return quotation


def convert_quotation_to_invoice(db: Session, quotation_id: UUID, user: User) -> SalesInvoice:
    quotation = db.get(SalesQuotation, quotation_id)
    if quotation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیش‌فاکتور یافت نشد")
    if quotation.converted_invoice_id is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این پیش‌فاکتور قبلاً به فاکتور تبدیل شده است")
    if quotation.status == "rejected":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "پیش‌فاکتور ردشده قابل تبدیل به فاکتور نیست")

    description = f"از پیش‌فاکتور شماره {quotation.number}"
    if quotation.description:
        description += f" — {quotation.description}"

    invoice_data = SalesInvoiceIn(
        invoice_date=date.today(),
        warehouse_id=quotation.warehouse_id,
        contact_id=quotation.contact_id,
        description=description,
        lines=[
            SalesInvoiceLineIn(item_id=line.item_id, qty=line.qty, unit_price=line.unit_price, description=line.description)
            for line in quotation.lines
        ],
    )
    invoice = post_sales_invoice(db, invoice_data, user)

    quotation.converted_invoice_id = invoice.id
    quotation.status = "converted"
    db.flush()
    db.refresh(invoice)
    return invoice
