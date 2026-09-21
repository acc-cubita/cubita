"""CASCADE روی کلیدهای خارجیِ tenant_id — تا حذفِ اکانت واقعاً کار کند

Revision ID: 0181
Revises: 0180

**باگ:** «حذفِ اکانت» در production کار نمی‌کند. `purge_tenant` با
`DELETE FROM tenants WHERE id = :t` کار می‌کند و انتظار دارد همه‌چیز آبشاری پاک
شود، ولی در اسکیمای مهاجرت‌ساخته **۴۷ جدول** کلیدِ خارجیِ `tenant_id`شان
`NO ACTION` است. اولین جدولی که ردیف داشته باشد کلِ حذف را رد می‌کند — و چون
`provision_tenant` برای هر کسب‌وکارِ تازه واحدهای اندازه‌گیری می‌سازد، عملاً
**هیچ اکانتی قابلِ حذف نبود**.

**چرا هیچ تستی نگرفتش — و این مهم‌ترین بخشِ این مهاجرت است:**
`TenantMixin` در `app/models/tenant.py` از روزِ اول `ondelete="CASCADE"` داشته،
پس اسکیمایی که تست‌ها با `create_all` می‌سازند **درست** است و حذف در آن کار
می‌کند. انحراف فقط در مهاجرت‌هاست، و `test_migration_drift` تا امروز فقط
ایندکس‌های یکتا و وجودِ جدول‌ها را مقایسه می‌کرد، نه قاعده‌ی حذفِ کلیدهای خارجی.
تستِ `test_every_tenant_fk_cascades` همین شکاف را می‌بندد.

`SET NULL` دست نمی‌خورد: `client_errors.tenant_id` عمداً این‌طور است (تلهمتریِ
پیش‌از‌احراز‌هویت که نباید با رفتنِ مستأجر پاک شود).

⚠️ **بازسازیِ کلیدِ خارجی روی جدولِ RLS‌دارِ پرردیف، اسکنِ راستی‌آزمایی می‌زند** و
آن اسکن زیرِ سیاستی اجرا می‌شود که `current_setting('app.tenant_id')` را
می‌خواند → `''::uuid` → شکستِ کلِ مهاجرت. پس همه‌چیز داخلِ `rls_disabled` است.
این روی PG 14 (production) رخ می‌دهد و روی PG 17 (ماشینِ توسعه) **نه** — پس
سبزبودنِ محلی چیزی اثبات نمی‌کند؛ همان تله‌ای که `app/migration_utils.py`
مفصل مستندش کرده.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.migration_utils import rls_disabled
from app.tenancy import GLOBAL_TABLES

revision: str = "0181"
down_revision: Union[str, None] = "0180"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: کلیدهای خارجیِ `tenant_id` که به `tenants` اشاره می‌کنند و آبشاری نیستند.
#: `SET NULL` عمدی است و کنار گذاشته می‌شود.
_FIND_SQL = """
SELECT tc.table_name, tc.constraint_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON kcu.constraint_name = tc.constraint_name
 AND kcu.constraint_schema = tc.constraint_schema
JOIN information_schema.referential_constraints rc
  ON rc.constraint_name = tc.constraint_name
 AND rc.constraint_schema = tc.constraint_schema
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name
 AND ccu.constraint_schema = tc.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.constraint_schema = current_schema()
  AND ccu.table_name = 'tenants'
  AND kcu.column_name = 'tenant_id'
  AND rc.delete_rule = :rule
ORDER BY tc.table_name
"""


def _targets(conn, rule: str) -> list[tuple[str, str]]:
    return [(r[0], r[1]) for r in conn.execute(sa.text(_FIND_SQL), {"rule": rule}).all()]


def _rewrite(conn, targets: list[tuple[str, str]], *, ondelete: str) -> None:
    """قید را با قاعده‌ی حذفِ تازه بازمی‌سازد.

    فقط جدول‌های مستأجرمحور وارد `rls_disabled` می‌شوند. `tenants` خودش سیاستِ
    RLS ندارد، پس نمی‌تواند اسکن را بشکند — و واردکردنش یعنی موقعِ خروج روی
    جدولی که اصلاً RLS ندارد پرچمِ FORCE می‌نشست.
    """
    if not targets:
        return
    scoped = sorted({t for t, _ in targets if t not in GLOBAL_TABLES})
    with rls_disabled(conn, scoped):
        for table, constraint in targets:
            conn.execute(sa.text(f'ALTER TABLE {table} DROP CONSTRAINT "{constraint}"'))
            conn.execute(
                sa.text(
                    f'ALTER TABLE {table} ADD CONSTRAINT "{constraint}" '
                    f"FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE {ondelete}"
                )
            )


def upgrade() -> None:
    conn = op.get_bind()
    _rewrite(conn, _targets(conn, "NO ACTION"), ondelete="CASCADE")
    _rewrite(conn, _targets(conn, "RESTRICT"), ondelete="CASCADE")


def downgrade() -> None:
    conn = op.get_bind()
    #: فقط همان‌هایی که این مهاجرت عوضشان کرد قابلِ تشخیص نیستند (قیدها هم‌نام‌اند)،
    #: پس برگشت همه‌ی آبشاری‌ها را به NO ACTION می‌برد — یعنی دقیقاً وضعیتِ پیش از
    #: ۰۱۸۱، که در آن حذفِ اکانت هم کار نمی‌کرد.
    _rewrite(conn, _targets(conn, "CASCADE"), ondelete="NO ACTION")
