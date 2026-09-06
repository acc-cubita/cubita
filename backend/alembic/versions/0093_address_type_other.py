"""نوعِ نشانیِ «سایر»

Revision ID: 0093
Revises: 0092

## چرا «سایر» و چرا فقط همین یکی

هفت نوعِ نشانی از فرمِ سپیدار آمده‌اند (رسمی، محل فعالیت، ارسال صورتحساب، ارسال کالا،
انبار، منزل، پستی) و بیشترِ حالت‌ها را می‌پوشانند — ولی نه همه را: نشانیِ کارگاه،
نمایشگاه، دفترِ موقت، محلِ تحویلِ یک قرارداد. بی‌گزینه‌ی «سایر»، کاربر مجبور می‌شد
یکی از هفت‌تا را دروغ انتخاب کند و از آن به بعد فیلترِ «ارسال کالا» ردیف‌هایی را
برمی‌گرداند که نشانیِ ارسال نیستند.

**فهرست باز نمی‌شود.** «سایر» یک درِ خروج است نه دعوت به متنِ آزاد؛ عنوانِ نشانی
(`title`) همان‌جاست تا کاربر بنویسد دقیقاً چیست.

این مهاجرت **هیچ ردیفی را دست نمی‌زند** — فقط قیدِ بررسی را از نو می‌سازد تا مقدارِ
هشتم را هم بپذیرد. برگشتش هم بی‌خطر است مادامی که ردیفی با `other` ثبت نشده باشد؛
اگر شده باشد، `downgrade` عمداً می‌شکند تا داده بی‌صدا نامعتبر نماند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0093"
down_revision: Union[str, None] = "0092"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "('official', 'business', 'billing', 'shipping', 'warehouse', 'home', 'postal')"
_NEW = "('official', 'business', 'billing', 'shipping', 'warehouse', 'home', 'postal', 'other')"


def upgrade() -> None:
    op.drop_constraint("ck_contact_addresses_type", "contact_addresses", type_="check")
    op.create_check_constraint(
        "ck_contact_addresses_type", "contact_addresses", f"address_type IN {_NEW}"
    )


def downgrade() -> None:
    conn = op.get_bind()
    stuck = conn.execute(
        sa.text("SELECT count(*) FROM contact_addresses WHERE address_type = 'other'")
    ).scalar()
    if stuck:
        raise RuntimeError(
            f"{stuck} نشانی با نوعِ «سایر» ثبت شده است؛ اول نوعشان را عوض کنید."
        )
    op.drop_constraint("ck_contact_addresses_type", "contact_addresses", type_="check")
    op.create_check_constraint(
        "ck_contact_addresses_type", "contact_addresses", f"address_type IN {_OLD}"
    )
