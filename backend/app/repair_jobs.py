"""Cloud and frozen Windows entry point. No carrier I/O without --send."""
import argparse
import json
from uuid import UUID
from app.database import SessionLocal
import app.models  # noqa: F401
from app.models.tenant import Tenant
from app.services.modules import is_module_visible
from app.services.repair_access import purge_expired
from app.services.repair_notifications import enqueue_due,process_one
from app.tenant_context import tenant_scope


def execute(tenant_id,*,limit=20,send=False,session_factory=SessionLocal):
    if not 1<=limit<=200: raise ValueError('limit باید بین ۱ و ۲۰۰ باشد.')
    with session_factory() as db,tenant_scope(db,tenant_id):
        tenant=db.get(Tenant,tenant_id)
        if tenant is None or tenant.status!='active' or not is_module_visible(tenant,'repair'): raise ValueError('شرکت فعال دارای تعمیرگاه پیدا نشد.')
        removed=purge_expired(db,limit=200)
        considered=enqueue_due(db,tenant_id)
        db.commit()
    processed=0
    if send:
        while processed<limit and process_one(session_factory,tenant_id): processed+=1
    return {'expired_secrets_removed':removed,'reminder_cases_considered':considered,'notifications_processed':processed,'sending_requested':send}


def main(argv=None):
    parser=argparse.ArgumentParser(description='کارهای دوره‌ای تعمیرگاه؛ پیش‌فرض فقط پاک‌سازی و صف یادآوری')
    parser.add_argument('--tenant',required=True,type=UUID)
    parser.add_argument('--limit',type=int,default=20)
    parser.add_argument('--send',action='store_true',help='پردازش پیامک با سرویس واقعی تنظیم‌شده')
    args=parser.parse_args(argv)
    try: result=execute(args.tenant,limit=args.limit,send=args.send)
    except ValueError as error: parser.error(str(error))
    print(json.dumps(result,ensure_ascii=True))
    return 0


if __name__=='__main__': main()
