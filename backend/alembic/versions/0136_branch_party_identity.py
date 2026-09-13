"""شعبه‌ی بیمه و مالیات یک اسمِ متنی بود، نه یک هویتِ قابلِ ردیابی

Revision ID: 0136
Revises: 0134

## نقصی که بسته می‌شود

`insurance_tax_branches` تا امروز چهار ستون داشت: `code`، `name`، `kind`،
`is_active`. یعنی «شعبه ۱۲ تأمین اجتماعی» یک **رشته** بود و بس.

این تا وقتی بی‌ضرر است که شعبه فقط برچسب باشد. ولی نیست: بدهیِ بیمه و مالیاتِ
تکلیفیِ حقوق **به همان سازمان پرداخت می‌شود**، و آن پرداخت طرفِ حساب می‌خواهد —
یک `Contact` با تفصیلیِ خودش. تا امروز این دو هیچ پیوندی نداشتند، پس:

    فیشِ حقوق  →  «مالیات پرداختنی»  →  ؟
                   «بیمه پرداختنی»    →  ؟

کسی که بخواهد بداند «بدهیِ ما به حوزه‌ی مالیاتیِ شمالِ تهران چه‌قدر است»،
جوابی ندارد — چون آن حوزه در دفترِ کوبیتا **وجود ندارد**؛ فقط نامش روی قرارداد
نشسته.

## چرا `contact_id` و نه یک زیرسیستمِ موازی

کوبیتا از قبل مِسترِ طرف حساب را دارد، و طرف حساب از قبل تفصیلی دارد
(`contacts.analytic_id`). پس هویتِ حسابداریِ شعبه **ساخته نمی‌شود، وصل می‌شود**:

    شعبه ──contact_id──▶ طرف حساب ──analytic_id──▶ تفصیلی

این عمداً پیوند به *طرف حساب* است و نه به تفصیلی: کدِ تفصیلی رشته‌ای است که
کاربر می‌تواند عوضش کند، و پیوندِ متنی همان چیزی است که این مهاجرت دارد از بین
می‌برد. شناسه‌ی پایدارِ طرف حساب ثابت می‌ماند حتی اگر کد و عنوان عوض شوند.

## `nullable` می‌ماند — و این تصمیم است، نه تنبلی

شعبه‌های ثبت‌شده‌ی امروز طرف حساب ندارند و حدس‌زدنش ممکن نیست: نامِ «شعبه ۱۲»
با هیچ طرف‌حسابی تطبیق قطعی ندارد، و اتصالِ اشتباه بدتر از اتصالِ نداشته است.
پس **بدونِ backfill**: شعبه‌ی بی‌طرف‌حساب دقیقاً همان‌طور کار می‌کند که تا دیروز
می‌کرد، و کاربر هر وقت خواست وصلش می‌کند.

`ondelete="SET NULL"` هم به همین دلیل: حذفِ یک طرف حساب نباید شعبه‌ای را که
روی ده‌ها قرارداد نشسته از بین ببرد.

## آنچه این مهاجرت **نمی‌سازد**

* **«نحوه محاسبه مالیات»** (تعدیل ماهانه / سالانه / بدون تعدیل). فصل خودش
  می‌گوید فهرستِ کاملش قطعی نیست، و موتورِ امروز تنها یک روش را می‌فهمد.
  ستونی که کاربر پرش کند و هیچ اثری نداشته باشد، از نبودنش بدتر است.
* **بیمه‌ی تکمیلی روی همین مِستر.** `salary_contracts.supplementary_branch`
  فعلاً متن می‌ماند؛ قواعدِ محاسبه‌اش در فصل «نامعلوم» است و عوض‌کردنِ شکل
  بدونِ دانستنِ کارکرد فقط جابه‌جایی است.
* کد کارگاه، آدرسِ کارگاه، شماره‌ی پیمان، تعدادِ نفراتِ معاف، مرکز هزینه —
  هیچ‌کدام شاهدِ مصرف ندارند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0136"
down_revision: Union[str, None] = "0134"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "insurance_tax_branches",
        sa.Column("contact_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_insurance_tax_branches_contact",
        "insurance_tax_branches",
        "contacts",
        ["contact_id"],
        ["id"],
        ondelete="SET NULL",
    )
    #: ایندکس چون پرسشِ طبیعیِ این ستون وارونه است: «کدام شعبه به این طرف حساب
    #: وصل است؟» — از سمتِ صورت‌حسابِ سازمان، نه از سمتِ شعبه.
    op.create_index(
        "ix_insurance_tax_branches_contact_id",
        "insurance_tax_branches",
        ["contact_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_insurance_tax_branches_contact_id", table_name="insurance_tax_branches")
    op.drop_constraint(
        "fk_insurance_tax_branches_contact", "insurance_tax_branches", type_="foreignkey"
    )
    op.drop_column("insurance_tax_branches", "contact_id")
