"""تراکنشِ مالک و شریک — نوعِ صریح، و دو نقشی که سی‌ونه‌تای دیگر داشتند و این‌ها نه.

**چه کم بود.** آورده‌ی مالک، برداشتش، و وام‌های دوطرفه‌ی شریک هیچ موجودیتی
نداشتند. روی تولید، آورده‌ی ۲۰۰ میلیونیِ مالک به‌صورتِ **سندِ دستی** ثبت شده است
(سند ۵، `source_type='manual'`، «آورده‌ی نقدیِ مالک») — حسابداری‌اش درست، ولی هیچ
داده‌ای نمی‌گوید این یک آورده بوده. دو پیامد:

* قاعده‌ی پایدارِ ۲ («آورده ≠ درآمد، برداشت ≠ هزینه») هیچ گاردِ نرم‌افزاری نداشت.
* «صورت تغییرات در حقوق صاحبان سهام» — یکی از چهار صورتِ الزامیِ استانداردهای
  ایران — **ساختاراً** ناممکن بود: ورودی‌اش وجود نداشت.

## چه می‌سازد

* `owner_transactions` با `type`ِ صریح و CHECK روی شش مقدار (قاعده‌ی ۵۲:
  «Direction یا PartyRole به‌تنهایی نوعِ حسابداری را تعیین نکند»).
* حسابِ **۲۱۱۵ جاری شرکا** برای هر مستأجر. بدهی است نه حقوق صاحبان سهام، چون
  رابطه‌ی **وام** است نه مالکیت — و همین است که صورتِ تغییراتِ حقوق صاحبان سهام
  را تمیز نگه می‌دارد.
* دو `system_role`: `owner_capital` روی ۳۱۰۱ و `partner_current` روی ۲۱۱۵.
  حسابِ ۳۱۰۱ از روزِ اول در چارت بود ولی **نقش نداشت**، پس هیچ سندِ خودکاری
  نمی‌توانست پیدایش کند.

## چرا `rls_disabled` اجباری است

هر سه backfill `SELECT` و `INSERT`/`UPDATE` روی جدول‌های `FORCE ROW LEVEL
SECURITY` می‌زنند و مهاجرت هیچ `app.tenant_id`ی ست نکرده — بی آن **بی‌صدا صفر
ردیف** می‌دیدند و مهاجرت موفق گزارش می‌شد بی آن‌که چیزی ساخته شود. همان محکی که
در ۰۱۵۶ و ۰۱۵۸ کار کرد: شمارشِ ردیف‌های ساخته‌شده چاپ می‌شود.

`accounts` قیدِ `UNIQUE(tenant_id, system_role)` دارد، پس backfillِ نقش با
`WHERE system_role IS NULL` امن است و اجرای دوباره چیزی را دوبرابر نمی‌کند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0159"
down_revision: Union[str, None] = "0158"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "owner_transactions"

_TYPES = (
    "capital_contribution",
    "capital_withdrawal",
    "loan_to_entity",
    "loan_from_entity",
    "repayment_to_partner",
    "repayment_from_partner",
)

#: حسابِ «جاری شرکا» برای هر مستأجری که گروهِ ۲۱ را دارد و خودش این حساب را ندارد.
#: والد از روی **کد** پیدا می‌شود نه از روی نام، چون نام قابلِ تغییرِ کاربر است.
_MAKE_PARTNER_ACCOUNT = """
INSERT INTO accounts (id, tenant_id, code, name, type, is_group, parent_id,
                      system_role, created_at, updated_at)
SELECT gen_random_uuid(), p.tenant_id, '2115', 'جاری شرکا', 'liability', false, p.id,
       'partner_current', now(), now()
FROM accounts p
WHERE p.code = '21' AND p.is_group
  AND NOT EXISTS (
      SELECT 1 FROM accounts a
      WHERE a.tenant_id = p.tenant_id AND (a.code = '2115' OR a.system_role = 'partner_current')
  )
"""

#: نقشِ سرمایه روی حسابِ موجود. `system_role IS NULL` یعنی حسابی که مشتری خودش
#: نقشِ دیگری بهش داده دست نمی‌خورد.
_ROLE_OWNER_CAPITAL = """
UPDATE accounts SET system_role = 'owner_capital'
WHERE code = '3101' AND system_role IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM accounts b
      WHERE b.tenant_id = accounts.tenant_id AND b.system_role = 'owner_capital'
  )
"""

#: مستأجرهایی که حسابِ ۲۱۱۵ از قبل داشتند ولی بی‌نقش بودند.
_ROLE_PARTNER_CURRENT = """
UPDATE accounts SET system_role = 'partner_current'
WHERE code = '2115' AND system_role IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM accounts b
      WHERE b.tenant_id = accounts.tenant_id AND b.system_role = 'partner_current'
  )
"""


def _enable_rls(table: str) -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name(table)} ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
    )


def upgrade() -> None:
    types_sql = ", ".join(f"'{t}'" for t in _TYPES)
    op.create_table(
        _TABLE,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False, server_default="cash"),
        sa.Column("bank_account_id", UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id"), nullable=True),
        sa.Column("cashbox_id", UUID(as_uuid=True), sa.ForeignKey("cashboxes.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence_ref", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("journal_entry_id", UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True, index=True),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("void_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("voided_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"type IN ({types_sql})", name="ck_owner_transactions_type"),
        sa.CheckConstraint("method IN ('cash', 'bank')", name="ck_owner_transactions_method"),
        sa.CheckConstraint("amount > 0", name="ck_owner_transactions_amount_positive"),
    )
    _enable_rls(_TABLE)

    conn = op.get_bind()
    with rls_disabled(conn, ["accounts"]):
        made = conn.execute(sa.text(_MAKE_PARTNER_ACCOUNT)).rowcount
        capital = conn.execute(sa.text(_ROLE_OWNER_CAPITAL)).rowcount
        partner = conn.execute(sa.text(_ROLE_PARTNER_CURRENT)).rowcount
        tenants = conn.execute(sa.text("SELECT count(*) FROM tenants")).scalar_one()

    print(f"[0159] حسابِ «جاری شرکا» ساخته شد: {made} (از {tenants} مستأجر)")
    print(f"[0159] نقشِ owner_capital روی ۳۱۰۱ نشست: {capital}")
    print(f"[0159] نقشِ partner_current روی ۲۱۱۵ِ موجود نشست: {partner}")
    #: روی دیتابیسِ خالی (نصبِ تازه‌ی «کوبیتا سازمانی») صفر درست است، نه هشدار — این پیام در
    #: پنجره‌ی نصاب جلوی مشتری می‌آمد.
    if tenants and made + partner == 0:
        print("[0159] *** هیچ حسابِ جاری شرکایی ساخته یا نقش‌دار نشد — بررسی کنید ***")


def downgrade() -> None:
    conn = op.get_bind()
    op.drop_table(_TABLE)
    with rls_disabled(conn, ["accounts"]):
        #: نقش‌ها برداشته می‌شوند ولی **خودِ حساب‌ها نه**: ممکن است سند خورده باشند،
        #: و حذفِ حسابِ سنددار دفتر را می‌شکند. حسابِ بی‌نقشِ بی‌سند را کاربر خودش
        #: می‌تواند پاک کند.
        conn.execute(sa.text("UPDATE accounts SET system_role = NULL WHERE system_role IN ('owner_capital', 'partner_current')"))
