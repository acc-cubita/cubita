"""کالا و خدمت یک شناسنامه داشتند، نه یک Item Master

Revision ID: 0117
Revises: 0116

## چه چیزی درست بود

`items` از روزِ اول **یک** جدول بود و خرید، فروش، انبار، صندوق، تولید، بازار و
مؤدیان همه از همان می‌خواندند. اصلِ اصلیِ این فصل — «برای یک کالا سه تعریفِ
جدا نساز» — از قبل رعایت شده بود و این مهاجرت دستش نمی‌زند.

## چه چیزی غلط بود

**بهای خریدِ خدمت به «موجودی کالا» می‌نشست.** خریدِ ده ساعت مشاوره‌ی حقوقی یعنی
پنجاه میلیون دارایی در ترازنامه که وجود نداشت و هرگز خارج نمی‌شد، و هزینه‌ای که
هیچ‌وقت به سود و زیان نمی‌رسید. گزارشِ انبار صفر می‌گفت چون از `stock_ledger`
مشتق می‌شود و خدمت حرکت ندارد. سند متوازن بود و تراز آزمایشی صفر می‌شد، پس هیچ
نگهبانی خبر نمی‌داد.

**قلمِ معاف مالیات می‌خورد.** `vat_status` روی ردیفِ فاکتور ذخیره و در گزارشِ
ارزش افزوده شمرده می‌شد، ولی مالیات روی *جمعِ* فاکتور حساب می‌شد. یعنی گزارش
می‌گفت «فروشِ معاف: X» در حالی که همان فاکتور روی X مالیات بسته بود — و بسته‌ی
مؤدیان هم نرخِ سربرگ را به هر ردیف می‌زد و قلمِ معاف را با مالیات اظهار می‌کرد.

## داده‌ای که نوشته می‌شود — و چرا فبریکه نیست

دو پرکردن، هر دو **بازسازیِ چیزی که واقعاً اتفاق افتاده**، نه اختراعِ تاریخ:

۱. `purchase_vat_status := vat_status`. تا امروز کوبیتا یک پرچم داشت و همان را
   به هر دو سمت می‌زد. ریختنِ «مشمول» به‌جایش یعنی کالایی که امروز معاف است
   یک‌شبه در خرید مشمول شود — تغییرِ رفتار، نه مهاجرت.

۲. `sales_invoice_lines.tax_rate_snapshot/tax_amount_snapshot` از سربرگ.
   نرخِ سربرگ **دقیقاً همان** نرخی است که آن روز روی آن ردیف نشست، و تسهیمِ
   وزنیِ مبلغ همان کاری است که بسته‌ی مؤدیان و ردیفِ فاکتورِ خرید از قبل
   می‌کردند. جمعِ سهم‌ها دقیقاً `invoice.tax_amount` می‌شود (ته‌مانده روی
   بزرگ‌ترین ردیف)، پس دفتر و ردیف‌ها از هم جدا نمی‌افتند.

**هیچ حسابِ تازه‌ای این‌جا ساخته نمی‌شود.** «هزینه خرید خدمات» با اولین خریدِ
خدمت از `get_or_create_account` می‌آید — همان الگوی «چک‌های واگذارشده به بانک».
مهاجرت چارتِ کسی را دست نمی‌زند.
"""
from decimal import Decimal
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled

revision: str = "0117"
down_revision: Union[str, None] = "0116"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ITEM_COLUMNS = (
    ("name2", sa.String(300), "''"),
    ("iran_code", sa.String(30), "''"),
    ("barcode2", sa.String(300), "''"),
    ("purchase_vat_status", sa.String(10), "'taxable'"),
)


def _allocate(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """تسهیمِ بدونِ نشتِ ریال — ته‌مانده روی بزرگ‌ترین وزن می‌نشیند.

    همان قاعده‌ای که سرویسِ فاکتور برای تخفیف و مالیات به‌کار می‌برد؛ این‌جا
    دوباره نوشته می‌شود چون مهاجرت نباید به کدِ اپ وابسته باشد (کدِ اپ فردا
    عوض می‌شود، مهاجرتِ اجراشده نه).
    """
    gross = sum(weights, Decimal(0))
    if total == 0 or gross == 0:
        return [Decimal(0) for _ in weights]
    shares = [(total * w / gross).quantize(Decimal(1)) for w in weights]
    residual = total - sum(shares, Decimal(0))
    if residual:
        biggest = max(range(len(weights)), key=lambda i: weights[i])
        shares[biggest] += residual
    return shares


def upgrade() -> None:
    for name, type_, default in ITEM_COLUMNS:
        op.add_column("items", sa.Column(name, type_, server_default=sa.text(default), nullable=False))

    op.add_column("items", sa.Column("is_sellable", sa.Boolean(), server_default="true", nullable=False))
    op.add_column(
        "items", sa.Column("is_serial_tracked", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("items", sa.Column("tax_rate", sa.Numeric(5, 2), server_default="0", nullable=False))
    op.add_column("items", sa.Column("duty_rate", sa.Numeric(5, 2), server_default="0", nullable=False))
    op.add_column(
        "items",
        sa.Column("expense_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=True),
    )

    op.add_column(
        "sales_invoice_lines",
        sa.Column("tax_rate_snapshot", sa.Numeric(5, 2), server_default="0", nullable=False),
    )
    op.add_column(
        "sales_invoice_lines",
        sa.Column("tax_amount_snapshot", sa.Numeric(18, 0), server_default="0", nullable=False),
    )

    conn = op.get_bind()
    with rls_disabled(conn, ["items", "sales_invoices", "sales_invoice_lines"]):
        #: سمتِ خرید همان چیزی می‌شود که تا امروز بود — یک پرچم برای هر دو سمت.
        conn.execute(sa.text("UPDATE items SET purchase_vat_status = vat_status"))

        #: نرخِ سربرگ همان نرخی است که آن روز روی هر ردیف نشست.
        conn.execute(
            sa.text(
                """
                UPDATE sales_invoice_lines l
                   SET tax_rate_snapshot = i.tax_rate
                  FROM sales_invoices i
                 WHERE i.id = l.invoice_id AND i.tax_rate <> 0
                """
            )
        )

        #: مبلغ به‌نسبتِ خالصِ هر ردیف تسهیم می‌شود — همان کاری که بسته‌ی مؤدیان
        #: و ردیفِ فاکتورِ خرید از قبل می‌کردند. جمعِ سهم‌ها دقیقاً برابرِ
        #: `invoice.tax_amount` می‌ماند.
        rows = conn.execute(
            sa.text(
                """
                SELECT i.id, i.tax_amount,
                       l.id, (l.qty * l.unit_price) - COALESCE(l.discount, 0)
                  FROM sales_invoices i
                  JOIN sales_invoice_lines l ON l.invoice_id = i.id
                 WHERE i.tax_amount <> 0
                 ORDER BY i.id, l.id
                """
            )
        ).all()

        by_invoice: dict = {}
        for invoice_id, tax_amount, line_id, line_net in rows:
            entry = by_invoice.setdefault(invoice_id, {"tax": Decimal(tax_amount), "lines": []})
            entry["lines"].append((line_id, max(Decimal(line_net), Decimal(0))))

        updates = []
        for entry in by_invoice.values():
            line_ids = [line_id for line_id, _ in entry["lines"]]
            weights = [net for _, net in entry["lines"]]
            for line_id, share in zip(line_ids, _allocate(entry["tax"], weights)):
                if share:
                    updates.append({"line_id": line_id, "share": share})

        if updates:
            conn.execute(
                sa.text("UPDATE sales_invoice_lines SET tax_amount_snapshot = :share WHERE id = :line_id"),
                updates,
            )


def downgrade() -> None:
    op.drop_column("sales_invoice_lines", "tax_amount_snapshot")
    op.drop_column("sales_invoice_lines", "tax_rate_snapshot")
    op.drop_column("items", "expense_account_id")
    op.drop_column("items", "duty_rate")
    op.drop_column("items", "tax_rate")
    op.drop_column("items", "is_serial_tracked")
    op.drop_column("items", "is_sellable")
    for name, _, _ in reversed(ITEM_COLUMNS):
        op.drop_column("items", name)
