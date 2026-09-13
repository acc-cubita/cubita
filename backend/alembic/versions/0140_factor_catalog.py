"""«فعال» روی عامل نوشته می‌شد و هیچ‌کس نمی‌خوانْدَش

Revision ID: 0140
Revises: 0139

## نقصی که بسته می‌شود

سه ستون روی `payroll_factors` بودند و **هیچ‌کدام مصرف‌کننده نداشتند**:

    is_active         ← grep: صفر
    is_extraordinary  ← grep: صفر
    kind              ← grep: صفر

یعنی عاملی که کاربر «غیرفعال» کرده بود، همچنان به قراردادِ تازه اضافه می‌شد و
در فیش می‌آمد. پرچمی که زده می‌شود و هیچ اثری ندارد بدترین نوعِ تنظیم است:
کاربر فکر می‌کند کاری کرده.

این مهاجرت خودِ آن سه ستون را عوض نمی‌کند — کد از فردا می‌خوانَدشان. چیزی که
این‌جا اضافه می‌شود دو چیزِ تازه است.

## ۱. اولویتِ نمایش

فرمِ مرجع ستونِ «اولویت نمایش» دارد و ترتیبِ ردیف‌های فیش را با آن می‌سازد.
کوبیتا این ترتیب را در `payslip_breakdown` سخت‌کد کرده بود.

**صریحاً فقط نمایشی است.** هیچ محاسبه‌ای از آن نمی‌خوانَد، و چون `PayslipLine`
شماره‌ی ردیفش را لحظه‌ی صدور منجمد می‌کند، تغییرِ اولویت فیشِ گذشته را تکان
نمی‌دهد — فقط فیشِ بعدی را مرتب می‌کند.

## ۲. پروفایلِ حسابداریِ عامل

سندِ حقوق یک ردیفِ `PAYROLL_EXPENSE` برای کلِ دوره می‌زند، پس «حق مسکن» و
«حق سرپرستی» در یک عدد گم می‌شوند و هیچ عاملی نمی‌تواند مرکزِ هزینه یا
طرفِ‌مقابلِ خودش را داشته باشد.

حالا هر عامل می‌تواند حساب و بُعدِ تفصیلیِ خودش را داشته باشد. **تقدم صریح
است:** عاملی که حساب دارد سهمش به همان می‌رود؛ عاملِ بی‌حساب به حسابِ عمومی.
پس تا وقتی هیچ عاملی حسابی نگیرد، **سند بایت‌به‌بایت همان می‌ماند**.

دو سمت مستقل‌اند و عمداً در یک ستون خلاصه نشدند:

    مزایا  → حسابِ هزینه‌ی خودش   (سمتِ بدهکار)
    کسور   → حسابِ پرداختنیِ خودش (سمتِ بستانکار — مثلاً بیمه‌گرِ تکمیلی)

بُعدِ تفصیلی از همان زیرساختِ مرکزی می‌آید (`cost_center` / `analytic`)، نه یک
بُعدِ موازیِ مخصوصِ حقوق.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled

revision = "0140"
down_revision = "0139"
branch_labels = None
depends_on = None

#: بُعدِ تفصیلیِ ردیفِ سندِ این عامل. خالی = بی‌بُعد، همان رفتارِ امروز.
FACTOR_DETAIL_CLASSES = ("", "cost_center", "counterparty")


def upgrade() -> None:
    op.add_column(
        "payroll_factors",
        sa.Column("display_priority", sa.Integer(), nullable=False, server_default="0"),
    )
    #: صفر برای همه = ترتیبِ امروز دست‌نخورده می‌ماند، چون مرتب‌سازی روی
    #: `(اولویت، نام)` است و با اولویتِ یکسان نام تعیین‌کننده می‌شود.

    for side in ("expense", "payable"):
        #: اعتبارسنجیِ کلیدِ خارجی مشمولِ RLS است و روی PG 14 با
        #: `invalid input syntax for type uuid: ""` می‌ترکد — `app/migration_utils.py`.
        with rls_disabled(op.get_bind(), ("payroll_factors", "accounts")):
            op.add_column(
                "payroll_factors",
                sa.Column(
                    f"{side}_account_id",
                    UUID(as_uuid=True),
                    sa.ForeignKey("accounts.id", ondelete="SET NULL"),
                    nullable=True,
                ),
            )
        op.add_column(
            "payroll_factors",
            sa.Column(f"{side}_detail_class", sa.String(20), nullable=False, server_default=""),
        )
        op.create_check_constraint(
            f"ck_payroll_factors_{side}_detail_class",
            "payroll_factors",
            f"{side}_detail_class IN {FACTOR_DETAIL_CLASSES}",
        )

    #: بُعد بی‌حساب بی‌معنی است: ردیفِ سندی نیست که بُعد بگیرد.
    op.create_check_constraint(
        "ck_payroll_factors_detail_needs_account",
        "payroll_factors",
        "(expense_detail_class = '' OR expense_account_id IS NOT NULL) "
        "AND (payable_detail_class = '' OR payable_account_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_payroll_factors_detail_needs_account", "payroll_factors", type_="check")
    for side in ("payable", "expense"):
        op.drop_constraint(f"ck_payroll_factors_{side}_detail_class", "payroll_factors", type_="check")
        op.drop_column("payroll_factors", f"{side}_detail_class")
        op.drop_column("payroll_factors", f"{side}_account_id")
    op.drop_column("payroll_factors", "display_priority")
