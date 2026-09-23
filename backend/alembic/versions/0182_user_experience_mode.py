"""حالتِ تجربه‌ی کاربر — ساده یا حسابدار

Revision ID: 0182
Revises: 0181

یک ستون روی `users`. کاربر انتخاب می‌کند برنامه را «ساده» ببیند یا «حسابدار».

**چرا روی `users` و نه روی `memberships`.** `dashboard_cards` عمداً روی عضویت
نشست، چون شناسه‌ی کارت به ماژول‌های *همان* کسب‌وکار اشاره می‌کند و حسابداری که
در دو شرکت عضو است نباید کارتِ ماژولِ خاموش را ببیند. حالتِ تجربه چنین وابستگی‌ای
**ندارد**: هیچ شناسه‌ی مستأجری در آن نیست و «با صفحه‌کلید سریع کار می‌کنم» خصلتِ
خودِ شخص است، نه خصلتِ رابطه‌اش با یک شرکت. به‌علاوه این‌طور پیش از انتخابِ
کسب‌وکار هم در دسترس است.

**چرا پیش‌فرض `simple` و نه بر اساسِ نقش.** پیش‌فرض باید رفتارِ امروز را نگه دارد؛
هر کاربرِ موجود همین حالا فرمِ کلاسیک را می‌بیند و `simple` دقیقاً همان است.
نگاشتنِ نقش به حالت وسوسه‌انگیز است ولی حالت را به نقش **قفل** می‌کند، و فرضِ
«هر کسی نقشش `accountant` است حتماً صفحه‌کلیدباز است» فرضِ درستی نیست. کاربر
خودش یک‌بار انتخاب می‌کند و همان می‌ماند.

**چرا `NOT NULL` با `server_default`.** ستونِ تهی‌پذیر یعنی هر خواننده‌ای باید
`or "simple"` بنویسد و یکی‌شان یادش می‌رود. `server_default` ردیف‌های موجود را
همان لحظه پر می‌کند و `users` سراسری است (`GLOBAL_TABLES`)، پس نه RLS درگیر
است نه `rls_disabled` لازم.

`CheckConstraint` عمدی است: این ستون فقط دو مقدار دارد و رشته‌ی آزاد بودنش یعنی
یک غلطِ تایپی در کلاینت بی‌صدا کاربر را به حالتی می‌برد که وجود ندارد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0182"
down_revision: Union[str, None] = "0181"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MODES = ("simple", "accountant")


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "experience_mode",
            sa.String(length=20),
            nullable=False,
            server_default="simple",
        ),
    )
    op.create_check_constraint(
        "ck_users_experience_mode",
        "users",
        f"experience_mode IN {MODES}",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_experience_mode", "users", type_="check")
    op.drop_column("users", "experience_mode")
