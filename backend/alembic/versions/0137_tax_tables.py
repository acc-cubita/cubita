"""جدولِ مالیات یک بُعد داشت — سال — و قاعده‌ی واقعی سه بُعد دارد

Revision ID: 0137
Revises: 0136

## نقصی که بسته می‌شود

پلکانِ مالیات یک ستونِ `JSONB` روی `payroll_settings` بود، یکتا روی
`(مستأجر، سال)`. یعنی هر مستأجر در هر سال **یک** پلکان داشت.

ولی قاعده‌ی واقعی سه بُعد دارد، و هر سه هم‌زمان لازم‌اند:

    (تاریخِ اجرا، گروهِ مالیاتی، نوعِ محاسبه)  →  پلکان

در یک سال، «عادی» و «مناطق محروم» دو **جدولِ مستقل** با نرخ‌های مستقل دارند؛ و
«حقوق» و «عیدی» دو جدولِ مستقلِ دیگر با آستانه‌های متفاوت.

## و ضربی که باید بازنشسته شود

کوبیتا تا امروز «مناطق محروم» را این‌طور حساب می‌کرد:

    مالیات = پلکانِ عادی(مبنا) × درصدِ گروه ÷ ۱۰۰

یعنی نرخِ مؤثر را از **نامِ گروه** می‌ساخت. ولی سیستمِ مرجع برای هر گروه جدولِ
مستقل با ردیف‌های مستقل نگه می‌دارد؛ اینکه عددهای نمونه اتفاقاً نصف‌اند یک
مشاهده است، نه قاعده. منبعِ حقیقت باید **ردیف‌های جدول** باشد.

## انتقال: هیچ فیشی عوض نمی‌شود

این نکته‌ی حساسِ مهاجرت است. اگر فقط یک جدولِ پیش‌فرض ساخته می‌شد، هر حکمی که
امروز گروهِ «۵۰٪» دارد از فردا **۱۰۰٪** مالیات می‌گرفت — یک واگراییِ خاموش روی
داده‌ی زنده.

پس ضرب **یک‌بار و برای همیشه** در داده منجمد می‌شود: برای هر
`(سالِ تنظیمات × گروهِ مالیاتیِ موجود)` یک جدول ساخته می‌شود که نرخ‌هایش از قبل
در درصدِ گروه ضرب شده‌اند، به‌علاوه‌ی یک جدولِ پیش‌فرض (بی‌گروه) با نرخ‌های خام.

نتیجه: مالیاتِ محاسبه‌شده **دقیقاً همان** می‌ماند، ولی از فردا عدد در جدول است و
کاربر می‌تواند ویرایشش کند — به‌جای اینکه از یک ضربِ پنهان بیرون بیاید.

تاریخِ اجرا اولِ فروردینِ همان سالِ شمسی است، چون تنها چیزی است که از
`payroll_settings.year` قابلِ استنتاج است. هرچه دقیق‌تر از این حدس است.

## «مبلغ جزء» و «مبلغ کل» ستون ندارند

هر دو از سقف و نرخ **مشتق** می‌شوند. ذخیره‌شان یعنی دو حقیقت که با ویرایشِ یک
نرخ از هم جدا می‌افتند — همان «مشتق بهتر از ذخیره‌شده».

## سقفِ نامحدود `NULL` است، نه ۹۹٬۹۹۹٬۹۹۹٬۹۹۹

عددِ جادویی در نمونه‌ها نقشِ «بی‌نهایت» را بازی می‌کند، ولی در دامنه یک مبلغِ
واقعی است و روزی کسی از آن رد می‌شود.

## و مدلِ «سقفِ تجمعی» عمداً حفظ شد

سیستمِ مرجع «از مبلغ / تا مبلغ» نشان می‌دهد؛ کوبیتا سقفِ تجمعی دارد. با سقفِ
تجمعی مرزِ پایینِ هر پله سقفِ پله‌ی قبل است، پس **شکاف و همپوشانیِ پله‌ها
ساختاراً ناممکن‌اند** — کلِ خانواده‌ای از اعتبارسنجی‌ها بی‌موضوع می‌شود. دو نما
از یک عدد هم ساخته نمی‌شود: «از مبلغ» در رابط از سقفِ ردیفِ قبل خوانده می‌شود.

## آنچه این مهاجرت **نمی‌سازد**

* **تاریخِ پایانِ اعتبار.** فرمِ مرجع ندارد و از جدولِ بعدیِ همان دامنه مشتق
  می‌شود. دو منبع برای یک بازه بالاخره از هم عقب می‌مانند.
* **جدولِ عیدی.** ساخته نمی‌شود چون امروز عیدی **اصلاً مالیات نمی‌خورد**؛
  ساختنِ خودکارش یعنی مهاجرت رفتارِ مالی را عوض کند. مسیرش باز می‌شود و هر وقت
  کاربر جدولِ عیدی تعریف کرد، اعمال می‌شود.
* **ارجاع به شعبه روی جدول.** فرمِ مرجع ندارد؛ یک جدول را چند شعبه استفاده
  می‌کنند.
* **گردشِ تأیید/فعال‌سازی و ماشین‌حسابِ پیش‌نمایش.** هیچ‌کدام در مرجع دیده نشدند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0137"
down_revision: Union[str, None] = "0136"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TAX_CALC_PURPOSES = ("salary", "eidi")

#: UUIDِ صفر به‌عنوان جای‌گزینِ `NULL` در ایندکسِ یکتا. در پستگرس دو `NULL` با هم
#: برابر نیستند، پس بی این `COALESCE` می‌شد دو جدولِ پیش‌فرضِ هم‌زمان ساخت — و
#: حل‌کننده باید بی‌صدا یکی را انتخاب می‌کرد.
_NIL = "00000000-0000-0000-0000-000000000000"


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
    op.create_table(
        "tax_tables",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("title2", sa.String(200), server_default="", nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "tax_group_id",
            UUID(as_uuid=True),
            sa.ForeignKey("payroll_tax_groups.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("calculation_type", sa.String(20), server_default="salary", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "calculation_type IN ({})".format(", ".join(f"'{p}'" for p in TAX_CALC_PURPOSES)),
            name="ck_tax_tables_calculation_type",
        ),
    )
    op.create_index("ix_tax_tables_tenant_id", "tax_tables", ["tenant_id"])
    op.create_index("ix_tax_tables_effective_from", "tax_tables", ["effective_from"])
    op.create_index("ix_tax_tables_tax_group_id", "tax_tables", ["tax_group_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_tax_tables_scope ON tax_tables "
        f"(tenant_id, effective_from, calculation_type, COALESCE(tax_group_id, '{_NIL}'::uuid))"
    )
    _enable_rls("tax_tables")

    op.create_table(
        "tax_table_brackets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_id", UUID(as_uuid=True), sa.ForeignKey("tax_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer(), server_default="0", nullable=False),
        sa.Column("up_to", sa.Numeric(18, 0), nullable=True),
        sa.Column("rate", sa.Numeric(9, 6), server_default="0", nullable=False),
        sa.UniqueConstraint("tenant_id", "table_id", "seq", name="uq_tax_table_brackets_seq"),
        sa.CheckConstraint("rate >= 0 AND rate <= 1", name="ck_tax_table_brackets_rate"),
        sa.CheckConstraint("up_to IS NULL OR up_to > 0", name="ck_tax_table_brackets_up_to"),
    )
    op.create_index("ix_tax_table_brackets_tenant_id", "tax_table_brackets", ["tenant_id"])
    op.create_index("ix_tax_table_brackets_table_id", "tax_table_brackets", ["table_id"])
    _enable_rls("tax_table_brackets")

    op.add_column("payslips", sa.Column("tax_table_id", UUID(as_uuid=True), nullable=True))
    #: اعتبارسنجیِ کلیدِ خارجی مشمولِ RLS است و روی PG 14 با
    #: `invalid input syntax for type uuid: ""` می‌ترکد — `app/migration_utils.py`.
    with rls_disabled(op.get_bind(), ("payslips", "tax_tables")):
        op.create_foreign_key(
            "fk_payslips_tax_table", "payslips", "tax_tables", ["tax_table_id"], ["id"], ondelete="RESTRICT"
        )

    _migrate_existing_brackets()


def _migrate_existing_brackets() -> None:
    """پلکان‌های `payroll_settings` را به جدول‌های تازه می‌برد — بی‌تلفات.

    به‌ازای هر `(مستأجر، سال)` یک جدولِ پیش‌فرض (بی‌گروه) با نرخ‌های خام، و یک
    جدول برای **هر گروهِ مالیاتیِ موجودِ همان مستأجر** با نرخ‌هایی که از قبل در
    درصدِ گروه ضرب شده‌اند.

    این ضرب همان کاری است که `_tax_percent` امروز در زمانِ اجرا می‌کرد. منجمدکردنش
    در داده یعنی **عددِ هیچ فیشی عوض نمی‌شود**، ولی از فردا نرخ در جدول است و
    قابلِ ویرایش — نه نتیجه‌ی یک ضربِ پنهان.
    """
    connection = op.get_bind()

    #: **مستأجربه‌مستأجر، با زمینه‌ی مستأجرِ ست‌شده.**
    #:
    #: این نکته‌ی حیاتیِ این مهاجرت است و با پروب کشف شد: نقشِ `cubita_app`
    #: `BYPASSRLS` **ندارد** و `payroll_settings` هم `FORCE ROW LEVEL SECURITY`
    #: دارد. پس یک `SELECT` بی‌زمینه صفر ردیف می‌دهد — **بی هیچ خطایی**. نسخه‌ی
    #: اولِ همین تابع دقیقاً همین بود و روی تولید هیچ جدولی نمی‌ساخت، بی‌صدا، و
    #: همه‌ی مستأجرها به مسیرِ میراثی می‌افتادند.
    #:
    #: `tenants` خودش مستأجرمحور نیست (دفترِ ثبتِ مستأجرهاست)، پس فهرستش
    #: خواندنی است و بقیه‌ی کار داخلِ زمینه‌ی هرکدام انجام می‌شود.
    tenant_ids = [row[0] for row in connection.execute(sa.text("SELECT id FROM tenants")).fetchall()]
    if not tenant_ids:
        return

    from app.jalali import jalali_to_gregorian

    insert_table = sa.text(
        "INSERT INTO tax_tables "
        "(id, tenant_id, title, title2, effective_from, tax_group_id, calculation_type) "
        "VALUES (gen_random_uuid(), :tenant_id, :title, '', :effective_from, :group_id, 'salary') "
        "RETURNING id"
    )
    insert_bracket = sa.text(
        "INSERT INTO tax_table_brackets (id, tenant_id, table_id, seq, up_to, rate) "
        "VALUES (gen_random_uuid(), :tenant_id, :table_id, :seq, :up_to, :rate)"
    )

    set_tenant = sa.text("SELECT set_config('app.tenant_id', :tenant_id, true)")

    for tenant_id in tenant_ids:
        connection.execute(set_tenant, {"tenant_id": str(tenant_id)})

        settings = connection.execute(
            sa.text("SELECT year, tax_brackets FROM payroll_settings")
        ).fetchall()
        if not settings:
            continue
        groups = connection.execute(
            sa.text("SELECT id, name, percent FROM payroll_tax_groups")
        ).fetchall()

        for row in settings:
            raw = row.tax_brackets or []
            if not raw:
                continue
            effective_from = jalali_to_gregorian(row.year, 1, 1)

            #: همان مرتب‌سازیِ دفاعیِ موتور — اگر مستأجری پلکانِ نامرتب ذخیره
            #: کرده باشد، جدولِ تازه‌اش مرتب ساخته می‌شود، نه نامرتب.
            ordered = sorted(
                raw,
                key=lambda b: (b.get("up_to") is None, float(b.get("up_to") or 0)),
            )

            targets = [(None, "پیش‌فرض", 100.0)]
            for group in groups:
                targets.append((group.id, group.name, float(group.percent)))

            for group_id, label, percent in targets:
                table_id = connection.execute(
                    insert_table,
                    {
                        "tenant_id": tenant_id,
                        "title": f"جدول مالیات حقوق {row.year} — {label}",
                        "effective_from": effective_from,
                        "group_id": group_id,
                    },
                ).scalar_one()

                for seq, bracket in enumerate(ordered, start=1):
                    up_to = bracket.get("up_to")
                    connection.execute(
                        insert_bracket,
                        {
                            "tenant_id": tenant_id,
                            "table_id": table_id,
                            "seq": seq,
                            "up_to": None if up_to is None else str(up_to),
                            #: شش رقمِ اعشار، هم‌اندازه‌ی ستون. ۰٫۱۵ × ۵۰٪ =
                            #: ۰٫۰۷۵ بی‌اتلاف می‌نشیند.
                            "rate": round(float(bracket.get("rate") or 0) * percent / 100.0, 6),
                        },
                    )

    #: زمینه را پاک می‌کند تا مهاجرت‌های بعدی روی همان اتصال، مستأجرِ آخرین
    #: حلقه را به ارث نبرند.
    connection.execute(sa.text("SELECT set_config('app.tenant_id', '', true)"))


def downgrade() -> None:
    op.drop_constraint("fk_payslips_tax_table", "payslips", type_="foreignkey")
    op.drop_column("payslips", "tax_table_id")
    op.drop_table("tax_table_brackets")
    op.execute("DROP INDEX IF EXISTS uq_tax_tables_scope")
    op.drop_table("tax_tables")
