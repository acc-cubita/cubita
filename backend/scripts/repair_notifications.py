"""Worker مستقل: python -m scripts.repair_notifications --tenant UUID --limit 20

cron/timer همین فرمان را فراخوانی می‌کند. روی سرور محلی بدون سرویس واقعی، پیامک
ارسال نمی‌شود. این اسکریپت برای آزمون اجرا نمی‌شود و هیچ راز/متنی چاپ نمی‌کند.
"""
import argparse
from uuid import UUID
from app.database import SessionLocal
import app.models  # noqa: F401
from app.models.tenant import Tenant
from app.services.repair_notifications import enqueue_due, process_one
from app.services.modules import is_module_visible
from app.tenant_context import tenant_scope


def main():
    parser=argparse.ArgumentParser(description='پردازش صف واقعی پیامک تعمیرگاه')
    parser.add_argument('--tenant',type=UUID,required=True)
    parser.add_argument('--limit',type=int,default=20)
    args=parser.parse_args()
    if not 1<=args.limit<=200: parser.error('limit باید بین ۱ و ۲۰۰ باشد.')
    with SessionLocal() as db, tenant_scope(db,args.tenant):
        tenant=db.get(Tenant,args.tenant)
        if not tenant or tenant.status!='active' or not is_module_visible(tenant,'repair'):
            parser.error('شرکت فعال با ماژول تعمیرگاه پیدا نشد.')
        enqueue_due(db,args.tenant)
        db.commit()
    count=0
    while count<args.limit and process_one(SessionLocal,args.tenant): count+=1
    print(f'processed={count}; carrier acceptance is not handset delivery')


if __name__=='__main__': main()
