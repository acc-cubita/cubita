"""مرجعِ بانکیِ ردیفِ صورت‌حساب — تا وارداتِ دوباره دفتر را دوبرابر نکند.

`bank_statement_lines` تا امروز فقط تاریخ، مبلغ و شرح داشت و هیچ قیدِ یکتایی
نداشت؛ `import_statement_lines` هم یک `add_all`ِ خام بود. یعنی وارد کردنِ دوباره‌ی
یک فایلِ صورت‌حساب، کلِ ردیف‌ها را **دوبرابر** می‌کرد — و چون تطبیقِ خودکار با
«مبلغِ برابر و تاریخِ ±۳ روز» کار می‌کند، نسخه‌های تکراری به تراکنش‌های دیگری
می‌چسبیدند و مغایرت‌گیری را وارونه می‌کردند.

* `external_ref`: شناسه‌ی خودِ بانک برای آن تراکنش (شماره‌ی پیگیری/مرجع). تهی‌پذیر،
  چون همه‌ی صورت‌حساب‌ها آن را نمی‌دهند.
* ایندکسِ یکتای **جزئی** روی `(tenant_id, bank_account_id, external_ref)` فقط وقتی
  `external_ref` پر است — وگرنه ردیف‌های بی‌مرجع همدیگر را مسدود می‌کردند (همان
  الگوی `uq_sale_types_tenant_code`).

هیچ `UPDATE`ی روی داده‌ی موجود ندارد: ستون با `NULL` شروع می‌شود، پس ایندکسِ جزئی
هیچ ردیفِ قدیمی را نمی‌بیند و مهاجرت روی دادهٔ تولیدی بی‌خطر است.

**چرا `rls_disabled` لازم نیست:** `ADD COLUMN` دادهٔ موجود را نمی‌خواند، و ساختِ
ایندکس یک پویشِ مستقیمِ heap است نه کوئریِ مشمولِ RLS. (آن‌چه `rls_disabled`
می‌خواهد، اعتبارسنجیِ کلیدِ خارجی و هر `SELECT`/`UPDATE`ِ صریح است.)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0150"
down_revision: Union[str, None] = "0149"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bank_statement_lines",
        sa.Column("external_ref", sa.String(length=120), nullable=True),
    )
    op.create_index(
        "uq_bank_statement_lines_external_ref",
        "bank_statement_lines",
        ["tenant_id", "bank_account_id", "external_ref"],
        unique=True,
        postgresql_where=sa.text("external_ref IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_bank_statement_lines_external_ref", table_name="bank_statement_lines")
    op.drop_column("bank_statement_lines", "external_ref")
