"""Tenant-scoped scheduled cleanup; emits counts only, never credentials."""
import argparse
from uuid import UUID
from app.database import SessionLocal
import app.models  # noqa: F401
from app.models.tenant import Tenant
from app.services.repair_access import purge_expired
from app.tenant_context import tenant_scope


def main():
    parser = argparse.ArgumentParser(description='حذف دوره‌ای رمزهای منقضی دستگاه')
    parser.add_argument('--tenant', type=UUID, required=True)
    parser.add_argument('--limit', type=int, default=200)
    args = parser.parse_args()
    if not 1 <= args.limit <= 200:
        parser.error('limit باید بین ۱ و ۲۰۰ باشد.')
    with SessionLocal() as db, tenant_scope(db, args.tenant):
        if db.get(Tenant, args.tenant) is None:
            parser.error('شرکت پیدا نشد.')
        count = purge_expired(db, limit=args.limit)
        db.commit()
    print(f'expired_secrets_removed={count}')


if __name__ == '__main__':
    main()
