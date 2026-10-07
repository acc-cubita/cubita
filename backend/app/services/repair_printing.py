"""برچسب داخلی حاوی شناسه است؛ هیچ توکن دسترسی مشتری چاپ نمی‌شود."""
from io import BytesIO
from html import escape
import qrcode
from qrcode.image.svg import SvgPathImage
from barcode import Code128
from barcode.writer import SVGWriter
from fpdf import FPDF
from app.services.pdf_invoice import _REGULAR, _BOLD
from app.services.printing import format_jalali
from app.services.repair_completion import metadata


def code_images(row):
    linear=BytesIO()
    Code128('R'+str(row.number),writer=SVGWriter()).write(linear,options={'write_text':False,'module_height':10})
    qr=qrcode.make('cubita:repair:'+str(row.id),image_factory=SvgPathImage,border=4)
    matrix=BytesIO();qr.save(matrix)
    return linear.getvalue(),matrix.getvalue()


def codes_html(row):
    import base64
    barcode,qr=code_images(row)
    return ''.join(f'<img alt="{label}" style="max-width:240px;height:80px" src="data:image/svg+xml;base64,{base64.b64encode(data).decode()}"/>' for label,data in [('بارکد Code128 پذیرش',barcode),('QR پرونده داخلی',qr)])


def label_html(db,row):
    meta=metadata(db,row)
    number=meta.display_number if meta else str(row.number)
    model=escape(' / '.join(row.device_snapshot.get(k,'') for k in ('brand','model') if row.device_snapshot.get(k)))
    return f'<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>برچسب پذیرش</title><style>@page{{size:100mm 60mm;margin:4mm}}body{{font-family:Tahoma}}p{{margin:4px}}</style><h3>{escape(number)}</h3><p>{model}</p>{codes_html(row)}<p>اسکن فقط برای کارکنان مجاز؛ لینک مشتری نیست.</p></html>'


def pdf_receipt(db,row):
    meta=metadata(db,row)
    pdf=FPDF()
    pdf.add_font('Vazir','',_REGULAR);pdf.add_font('Vazir','B',_BOLD)
    pdf.set_text_shaping(True);pdf.set_auto_page_break(True,margin=14);pdf.add_page()
    pdf.set_font('Vazir','B',15);pdf.cell(0,12,'تعمیرگاه — رسید پذیرش',new_x='LMARGIN',new_y='NEXT',align='R')
    pdf.set_font('Vazir','',11)
    fields=[('شماره',meta.display_number if meta else str(row.number)),('نسخهٔ رسید',str(meta.receipt_revision if meta else 1)),('تاریخ',format_jalali(row.admission_date)),('مشتری',row.owner_snapshot['name']),('دستگاه',' / '.join(row.device_snapshot.get(k,'') for k in ('brand','model') if row.device_snapshot.get(k))),('ایراد',row.reported_issue),('ظاهر',row.appearance),('لوازم',row.accessories),('شرایط',row.terms)]
    for label,value in fields:
        pdf.multi_cell(0,8,f'{label}: {value}',new_x='LMARGIN',new_y='NEXT',align='R')
    due=meta.settings_snapshot.get('initial_due_date') if meta and 'initial_due_date' in meta.settings_snapshot else row.due_date
    if due:
        from datetime import date
        pdf.multi_cell(0,8,'موعد اولیه: '+format_jalali(date.fromisoformat(due) if isinstance(due,str) else due),new_x='LMARGIN',new_y='NEXT',align='R')
    barcode,qr=code_images(row)
    if pdf.get_y()>240: pdf.add_page()
    top=pdf.get_y()+5
    pdf.image(BytesIO(barcode),x=15,y=top,w=95,h=25)
    pdf.image(BytesIO(qr),x=145,y=top,w=35)
    pdf.set_y(top+40)
    pdf.multi_cell(0,8,'این رسید فقط پذیرش دستگاه امانی است؛ فاکتور و رسید دریافت وجه نیست.',align='R')
    return bytes(pdf.output())
