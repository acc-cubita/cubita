"""نقشِ طرف حساب: چهار پرچمِ مستقل، نه یک رشته‌ی سه‌حالته.

**چه چیزی غلط بود.** `contacts.type` یک ستونِ تکی با `CHECK` بود که فقط سه مقدار
می‌پذیرفت: `customer` · `supplier` · `both`. ولی طرف حساب **چهار** نقش دارد و دوتای
دیگر (`is_broker`، `is_shareholder`) از قبل پرچمِ مستقل بودند. یعنی دو نقش در یک
رشته چپانده شده بودند و دو نقش بیرون — و مدل هیچ راهی نداشت بگوید «این آدم نه
مشتری است نه تأمین‌کننده، فقط واسطه است».

نتیجه‌اش در فرم این بود:

```
const contactType = isCustomer && isSupplier ? 'both' : isCustomer ? 'customer' : 'supplier'
```

کسی که فقط «واسطه» را تیک می‌زد، بی‌آنکه بخواهد **تأمین‌کننده** ثبت می‌شد. و این
فقط یک برچسب نبود: در انتخابگرِ تأمین‌کننده‌ی رسیدِ انبار ظاهر می‌شد، انگار می‌شود
ازش کالا تحویل گرفت.

**چرا آن پیش‌فرض بی‌دلیل هم نبود.** نویسنده‌اش `supplier` را انتخاب کرده بود چون
جریانِ پول از ما به واسطه است — پورسانت. و سه جای کد دقیقاً روی همین تکیه کرده‌اند
تا بشود پورسانت را پرداخت کرد (`default_account_for`، `_assert_role_matches`،
`payments._validate_contact`). پس این مهاجرت تنها وقتی درست است که آن سه گارد هم
یاد بگیرند واسطه/سهامدار/کارمند طرفِ **پرداختنی**‌اند. آن بخش در کد است، نه این‌جا.

**شکلِ راه‌حل: ستون می‌رود، نام می‌ماند.** `type` از دیتابیس حذف می‌شود و جایش
`is_customer`/`is_supplier` می‌نشیند — متقارن با دو پرچمِ موجود. ولی `Contact.type`
به‌صورتِ `hybrid_property` روی مدل زنده می‌ماند و از همان دو پرچم مشتق می‌شود، با
یک مقدارِ چهارم: `none`.

این «دو نمای یک داده» نیست — که پروژه ممنوعش کرده — چون `type` دیگر **قابلِ واگرایی
نیست**: نه ستونی هست که کهنه بماند، نه نوشتنی که با پرچم‌ها نخواند. یک منبعِ حقیقت،
یک نمای مشتق. در عوض ده‌ها جای خواندن (`contact.type`، `Contact.type != "supplier"`)
و ۴۴ ارجاعِ تست که `type="supplier"` می‌نویسند، **بدونِ تغییر** کار می‌کنند — چون
hybrid هم getter دارد هم setter هم expressionِ SQL.

**عقب‌گرد بی‌ضرر است.** `downgrade` ستون را برمی‌گرداند و از پرچم‌ها پرش می‌کند.
تنها چیزی که در عقب‌گرد گم می‌شود همان حالتِ چهارم است: «نه مشتری نه تأمین‌کننده»
دوباره `supplier` می‌شود — یعنی دقیقاً رفتارِ دیروز.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.migration_utils import rls_disabled

revision: str = "0164"
down_revision: Union[str, None] = "0166"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    #: `server_default` لازم است و نه سلیقه: ستون NOT NULL روی جدولی که ردیف دارد
    #: بدونِ پیش‌فرض اضافه نمی‌شود.
    op.add_column("contacts", sa.Column(
        "is_customer", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("contacts", sa.Column(
        "is_supplier", sa.Boolean(), nullable=False, server_default="false"))

    #: **بدونِ این بلوک، پرچم‌ها روی همه‌ی مستأجرها false می‌مانند و هیچ خطایی هم
    #: نمی‌دهد** — `contacts` جدولِ FORCE RLS است و `UPDATE`ِ مهاجرت صفر ردیف
    #: می‌بیند. همان تله‌ای که این پروژه بارها خورده است.
    with rls_disabled(conn, ["contacts"]):
        conn.execute(sa.text("""
            UPDATE contacts SET
                is_customer = (type IN ('customer', 'both')),
                is_supplier = (type IN ('supplier', 'both'))
        """))

    #: قید پیش از ستون می‌رود، وگرنه PG اجازه‌ی حذفِ ستونِ درگیر در `CHECK` را
    #: می‌دهد ولی قید را هم بی‌صدا با خودش می‌برد. صریح بهتر از ضمنی.
    op.drop_constraint("ck_contacts_type", "contacts", type_="check")
    op.drop_column("contacts", "type")


def downgrade() -> None:
    conn = op.get_bind()

    op.add_column("contacts", sa.Column(
        "type", sa.String(20), nullable=False, server_default="customer"))

    #: «نه مشتری نه تأمین‌کننده» در مدلِ قدیمی بیانی ندارد؛ به `supplier` برمی‌گردد
    #: — همان پیش‌فرضی که این مهاجرت آمده بود کنارش بگذارد.
    with rls_disabled(conn, ["contacts"]):
        conn.execute(sa.text("""
            UPDATE contacts SET type = CASE
                WHEN is_customer AND is_supplier THEN 'both'
                WHEN is_customer                 THEN 'customer'
                ELSE                                  'supplier'
            END
        """))

    op.create_check_constraint(
        "ck_contacts_type", "contacts",
        "type IN ('customer', 'supplier', 'both')",
    )
    op.drop_column("contacts", "is_supplier")
    op.drop_column("contacts", "is_customer")
