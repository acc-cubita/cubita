"""فرمِ کاملِ طرف حساب — هویت، نقش‌ها، اعتبار، و پیوند به تفصیلی و کارمند

Revision ID: 0090
Revises: 0089

فیلدهای فرمِ «تعریف طرف حساب» که تا امروز نداشتیم. همه اختیاری‌اند و همه پیش‌فرضی
دارند که رفتارِ امروز را عوض نمی‌کند.

**دو پیوند، نه دو کپی.** این نکته‌ی اصلیِ این مهاجرت است:

* `analytic_id` → `analytic_accounts`. در سپیدار هر طرف‌حساب خودش یک تفصیلی است با
  کد و عنوانِ خودش. ساختنِ ستون‌های `tafsili_code`/`tafsili_title` روی `contacts`
  یعنی دو نمای یک داده — همان چیزی که `CLAUDE.md` منع می‌کند و گزارشِ تفصیلی را
  دوپاره می‌کرد. به‌جایش طرف‌حساب به همان تفصیلیِ موجود وصل می‌شود، پس ردیفِ سندی
  که تفصیلیِ این طرف‌حساب را دارد و گزارشِ تفصیلی، هر دو از یک جدول می‌خوانند.
* `employee_id` → `employees`. تبِ «مشخصات کارمند» هم به همان کارمندِ ماژولِ حقوق و
  دستمزد وصل می‌شود، نه اینکه نام و کد ملی و تاریخِ استخدام دوباره روی طرف‌حساب
  نوشته شود. یک آدم، یک رکورد.

`name` دست‌نخورده می‌ماند و «نامِ نمایشی» است — روی فاکتور، گزارشِ فصلی، صورت‌حساب و
ده‌ها جای دیگر نشسته و شکستنش تغییرِ شکننده‌ای بود. `first_name`/`last_name` کنارش
اضافه می‌شوند و سرویس `name` را از آن‌ها می‌سازد؛ طرف‌حساب‌های موجود هر دو را خالی
دارند و دقیقاً مثلِ قبل کار می‌کنند.

**نقشِ «واسطه» پرچمِ مستقل است، نه مقدارِ تازه‌ی `type`.** `CONTACT_TYPES` امروز
(customer, supplier, both) است و ده‌ها فیلتر و گزارش رویش تکیه دارند؛ افزودنِ
`broker` به آن یعنی هر `type == "customer"` در مخزن باید بازبینی شود. پرچمِ جدا
هیچ‌کدام را نمی‌شکند و در فرم همان سه تیکِ سپیدار را می‌دهد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0090"
down_revision: Union[str, None] = "0089"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: (نام، نوع، پیش‌فرضِ DDL) — پیش‌فرض در کاتالوگ می‌نشیند و جدول بازنویسی نمی‌شود،
#: پس هیچ `UPDATE`ی روی جدولِ RLS‌دار اجرا نمی‌شود.
_TEXT_COLUMNS = (
    ("first_name", 100),
    ("last_name", 100),
    ("first_name2", 100),
    ("last_name2", 100),
    ("sub_type", 50),
    ("website", 200),
)

_NULLABLE_TEXT = (
    ("registration_no", 50),
    ("passport_no", 50),
)


def upgrade() -> None:
    for name, length in _TEXT_COLUMNS:
        op.add_column(
            "contacts",
            sa.Column(name, sa.String(length=length), nullable=False, server_default=""),
        )
    for name, length in _NULLABLE_TEXT:
        op.add_column("contacts", sa.Column(name, sa.String(length=length), nullable=True))

    op.add_column("contacts", sa.Column("marriage_date", sa.Date(), nullable=True))
    op.add_column(
        "contacts",
        sa.Column("is_blacklisted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "contacts",
        sa.Column("discount_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "contacts",
        sa.Column("tax_ministry_class", sa.String(length=30), nullable=False, server_default="normal"),
    )
    # کنترلِ اعتبار: تا امروز `credit_limit` ذخیره می‌شد ولی هیچ‌جا اعمال نمی‌شد.
    # پیش‌فرض `none` یعنی همان رفتار، پس هیچ فروشی یک‌شبه مسدود نمی‌شود.
    op.add_column(
        "contacts",
        sa.Column("credit_action", sa.String(length=10), nullable=False, server_default="none"),
    )
    op.add_column(
        "contacts",
        sa.Column("is_broker", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "contacts",
        sa.Column("commission_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
    )

    op.add_column(
        "contacts",
        sa.Column("analytic_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_contacts_analytic", "contacts", "analytic_accounts", ["analytic_id"], ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "contacts",
        sa.Column("employee_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_contacts_employee", "contacts", "employees", ["employee_id"], ["id"], ondelete="SET NULL"
    )

    op.create_check_constraint(
        "ck_contacts_credit_action", "contacts",
        "credit_action IN ('none', 'warn', 'block')",
    )
    op.create_check_constraint(
        "ck_contacts_rates", "contacts",
        "discount_rate >= 0 AND discount_rate <= 100 "
        "AND commission_rate >= 0 AND commission_rate <= 100",
    )

    # عنوانِ تفصیلیِ دوم روی خودِ تفصیلی می‌نشیند، نه روی طرف‌حساب: تفصیلی می‌تواند
    # بدونِ طرف‌حساب هم وجود داشته باشد (خودرو، قرارداد) و عنوانِ دومش مالِ خودش است.
    op.add_column(
        "analytic_accounts",
        sa.Column("name2", sa.String(length=200), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("analytic_accounts", "name2")
    op.drop_constraint("ck_contacts_rates", "contacts", type_="check")
    op.drop_constraint("ck_contacts_credit_action", "contacts", type_="check")
    op.drop_constraint("fk_contacts_employee", "contacts", type_="foreignkey")
    op.drop_column("contacts", "employee_id")
    op.drop_constraint("fk_contacts_analytic", "contacts", type_="foreignkey")
    op.drop_column("contacts", "analytic_id")
    for name in (
        "commission_rate", "is_broker", "credit_action", "tax_ministry_class",
        "discount_rate", "is_blacklisted", "marriage_date",
    ):
        op.drop_column("contacts", name)
    for name, _ in _NULLABLE_TEXT:
        op.drop_column("contacts", name)
    for name, _ in _TEXT_COLUMNS:
        op.drop_column("contacts", name)
