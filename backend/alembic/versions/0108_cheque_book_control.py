"""دسته‌چک: برگِ مصرف‌شده دیگر دوباره خرج نمی‌شود.

`checkbooks` از مهاجرتِ ۰۰۸۴ هست و `checks.checkbook_id` هم هست — ولی **هیچ‌جا
سنجیده نمی‌شد**. `create_check` مقدارِ `checkbook_id` را می‌گرفت و بی‌هیچ
اعتبارسنجی‌ای روی چک می‌نشاند: دو چک با شماره‌ی یکسان از یک دسته هر دو ثبت
می‌شدند، و شماره‌ی بیرونِ بازه هم پذیرفته می‌شد — که بدتر بود، چون «برگِ مانده»
مشتق است و آن ردیف بی‌ربط هم از آن کم می‌کرد. یعنی شمارنده دروغ می‌گفت.

سه تغییر:

۱) **ایندکسِ جزئیِ یکتا روی `(tenant_id, checkbook_id, number)`** — دوباره‌خرج‌کردنِ
   یک برگ را در سطحِ پایگاه‌داده غیرممکن می‌کند. شرطِ جزئی لازم است چون چکِ
   دریافتنی دسته ندارد (`checkbook_id IS NULL`) و شماره‌اش را طرفِ مقابل تعیین
   کرده؛ یکتاییِ بینِ آن‌ها نه ممکن است نه درست.

   این هم‌زمان قاعده‌ی «برگِ باطل‌شده آزاد نمی‌شود» را هم برآورده می‌کند: ردیفِ چک
   می‌ماند، پس شماره‌اش برای همیشه گرفته است.

۲) **`checkbooks.cheque_print_format`** — خالی یعنی «از حسابِ بانکی ارث ببر».
   موتورِ چاپِ چک وجود ندارد و اینجا هم ساخته نمی‌شود؛ فقط ترتیبِ خواندن از قبل
   تعریف می‌شود تا وقتی موتور آمد دو زیرساختِ موازی نداشته باشیم.

۳) **`tenants.cheque_number_control`** — سیاستِ کنترلِ شماره. `NULL` = پیش‌فرضِ
   سرویس = `off`، پس هیچ کسب‌وکارِ موجودی رفتارش عوض نمی‌شود.

**هیچ `INSERT/UPDATE`ای اینجا نیست.** ولی برخلافِ مهاجرت‌های قبل یک `SELECT` هست:
اگر داده‌ی موجود برگِ تکراری داشته باشد، ساختِ ایندکس با خطای خامِ پستگرس
می‌شکست. به‌جایش خودمان زودتر می‌شکنیم، با پیامی که می‌گوید **کدام** دسته و
**کدام** شماره — تا استقرار تمیز متوقف شود، نه نیمه‌کاره.
"""
import sqlalchemy as sa
from alembic import op

from app.migration_utils import rls_disabled

revision = "0108"
down_revision = "0107"
branch_labels = None
depends_on = None

LEAF_INDEX = "uq_checks_tenant_book_number"

#: تکراری‌ها را پیش از ساختِ ایندکس پیدا می‌کند.
#:
#: **`rls_disabled` اینجا حیاتی است.** مهاجرت بدونِ زمینه‌ی مستأجر اجرا می‌شود و
#: `FORCE ROW LEVEL SECURITY` حتی مالکِ جدول را هم مشمول سیاست می‌کند — پس این
#: `SELECT` بی‌آن، همیشه صفر ردیف می‌داد و پیش‌پرواز بی‌صدا سبز می‌شد. آن‌وقت
#: `CREATE UNIQUE INDEX` با خطای خامِ پستگرس می‌شکست (ساختِ ایندکس از RLS رد
#: می‌شود) و کاربر هیچ نمی‌فهمید کدام برگ مقصر است. همان دامی که
#: `migration_utils` از یک اشتباهِ واقعی ثبتش کرده.
_DUPLICATES = sa.text(
    """
    SELECT c.checkbook_id, c.number, count(*) AS n,
           coalesce(b.serial, '') AS serial
      FROM checks c
      LEFT JOIN checkbooks b ON b.id = c.checkbook_id
     WHERE c.checkbook_id IS NOT NULL
     GROUP BY c.tenant_id, c.checkbook_id, c.number, b.serial
    HAVING count(*) > 1
     ORDER BY n DESC
     LIMIT 20
    """
)


def _assert_no_duplicate_leaves() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, ("checks", "checkbooks")):
        rows = conn.execute(_DUPLICATES).fetchall()
    if not rows:
        return
    detail = "؛ ".join(
        f"دسته‌ی «{serial or book_id}» شماره‌ی {number} ({n} بار)"
        for book_id, number, n, serial in rows
    )
    raise RuntimeError(
        "مهاجرتِ ۰۱۰۸ متوقف شد: در داده‌ی موجود یک برگِ چک بیش از یک بار خرج شده "
        f"است، پس ایندکسِ یکتا ساخته نمی‌شود. اول این‌ها را اصلاح کنید — {detail}"
    )


def upgrade() -> None:
    _assert_no_duplicate_leaves()

    op.create_index(
        LEAF_INDEX,
        "checks",
        ["tenant_id", "checkbook_id", "number"],
        unique=True,
        postgresql_where=sa.text("checkbook_id IS NOT NULL"),
    )

    op.add_column(
        "checkbooks",
        sa.Column("cheque_print_format", sa.String(50), server_default="", nullable=False),
    )
    #: nullable عمدی: `NULL` یعنی «هنوز انتخاب نکرده» و با `off`ِ صریح فرق دارد —
    #: همان تفکیکی که رابط برای `tafsili_enforcement` هم نشان می‌دهد.
    op.add_column("tenants", sa.Column("cheque_number_control", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "cheque_number_control")
    op.drop_column("checkbooks", "cheque_print_format")
    op.drop_index(LEAF_INDEX, table_name="checks")
