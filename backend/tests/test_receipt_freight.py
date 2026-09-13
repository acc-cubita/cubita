"""هزینه‌ی حمل، تسهیمش روی بهای ورود، و تفکیکِ مالیات و عوارض.

رسیدِ انبار هیچ فیلدی برای حمل نداشت. کرایه‌ای که برای آوردنِ کالا داده می‌شود
یا اصلاً ثبت نمی‌شد، یا هزینه‌ی دوره می‌شد. هر دو یک نتیجه دارند: **موجودی
ارزان‌تر از واقع ارزش‌گذاری می‌شود**، و لحظه‌ی فروش بهای تمام‌شده به همان اندازه
کم و سود به همان اندازه زیاد گزارش می‌شود.

اعدادِ این فایل عمداً همان اعدادِ خودِ فصل‌اند (§۲۰ §۲۲ §۲۴ §۲۵)، تا اگر روزی
رفتار عوض شد، تست بگوید «فصل این را می‌خواست»، نه «یک عددِ دلخواه عوض شد».
"""
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
import pytest

from app.models.accounting import JournalLine
from app.models.inventory import StockLedger
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    WarehouseReceiptIn,
    WarehouseReceiptLineIn,
)
from app.services import chart_codes as cc
from app.services import freight as freight_svc
from app.services.common import get_account
from app.services.inventory import post_purchase_invoice
from app.services.reports import get_inventory_report
from app.services.warehouse_receipts import create_warehouse_receipt, void_warehouse_receipt
from tests.factories import main_warehouse, make_contact, make_item

TODAY = date(2026, 3, 15)


class Ledger:
    """مانده‌ها را **دلتایی** می‌سنجد.

    پایگاه دادهٔ تست بینِ فایل‌ها تمیز نیست (تست‌های همزمانی عمداً commit
    می‌کنند)، پس ادعای مانده‌ی مطلق شکننده است.
    """

    def __init__(self, db):
        self.db = db
        self.before = {}

    def snap(self, *roles):
        for role in roles:
            self.before[role] = self._balance(role)
        return self

    def delta(self, role):
        return self._balance(role) - self.before[role]

    def _balance(self, role):
        account_id = get_account(self.db, role).id
        rows = (
            self.db.query(JournalLine.debit, JournalLine.credit)
            .filter(JournalLine.account_id == account_id)
            .all()
        )
        return sum((Decimal(d) - Decimal(c) for d, c in rows), Decimal(0))


def direct(db, user, lines, **header):
    return create_warehouse_receipt(
        db,
        None,
        WarehouseReceiptIn(
            receipt_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=lines,
            **header,
        ),
        user,
    )


def line(item, qty, unit_cost):
    return WarehouseReceiptLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost))


def ledger_cost(db, receipt, item):
    row = (
        db.query(StockLedger)
        .filter(
            StockLedger.source_type == "warehouse_receipt",
            StockLedger.source_id == receipt.id,
            StockLedger.item_id == item.id,
        )
        .one()
    )
    return Decimal(row.unit_cost)


# ─────────────────── §۲۲ — تسهیم، با اعدادِ خودِ فصل ───────────────────


def test_the_chapters_own_allocation_example(db, user):
    """نمونه‌ی §۲۲: حملِ ۵۰٬۰۰۰ روی دو ردیف → ۲۵٬۰۰۰ و ۲۵٬۰۰۰."""
    first = make_item(db, name="کالای اول")
    second = make_item(db, name="کالای دوم")

    receipt = direct(
        db,
        user,
        [line(first, 100, 5_000), line(second, 150, 6_000)],
        freight_amount=Decimal(50_000),
    )

    assert [Decimal(row.freight_share) for row in receipt.lines] == [
        Decimal(25_000),
        Decimal(25_000),
    ]


def test_equal_means_equal_not_proportional(db, user):
    """«به نسبت مساوی» یعنی وزنِ ردیف نقشی ندارد.

    در نمونه‌ی فصل ردیفِ ۵۰۰٬۰۰۰ و ردیفِ ۹۰۰٬۰۰۰ سهمِ **برابر** می‌گیرند — پس
    این «به نسبت مبلغ» نیست، و §۲۳ می‌گوید مبناهای دیگر را فرض نکنیم.
    """
    assert freight_svc.allocate(Decimal(50_000), [Decimal(500_000), Decimal(900_000)]) == [
        Decimal(25_000),
        Decimal(25_000),
    ]


def test_the_shares_add_up_to_the_freight_exactly(db, user):
    """ته‌مانده‌ی گِردکردن گم نمی‌شود، وگرنه سند تراز نمی‌شود."""
    items = [make_item(db, name=f"کالا {i}") for i in range(3)]
    receipt = direct(
        db,
        user,
        [line(item, 1, 1_000) for item in items],
        freight_amount=Decimal(1_000),
    )
    assert sum(Decimal(row.freight_share) for row in receipt.lines) == Decimal(1_000)


def test_an_unsupported_basis_is_refused(db, user):
    """§۲۳ — مبنایی که سرویسی برایش نیست از در پشتی وارد نمی‌شود."""
    with pytest.raises(Exception):
        WarehouseReceiptIn(
            receipt_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            freight_basis="by_weight",
            lines=[WarehouseReceiptLineIn(item_id=make_item(db).id, qty=Decimal(1))],
        )


# ─────────────────── §۲۰ §۲۴ — فی و فی تمام‌شده ───────────────────


def test_landed_unit_cost_is_not_the_purchase_rate(db, user):
    """**نمونه‌ی §۲۰ و §۲۴:** فیِ ۵٬۰۰۰ + سهمِ حملِ ۲۵٬۰۰۰ → فیِ تمام‌شده ۵٬۲۵۰."""
    first = make_item(db, name="کالای اول")
    second = make_item(db, name="کالای دوم")

    receipt = direct(
        db,
        user,
        [line(first, 100, 5_000), line(second, 150, 6_000)],
        freight_amount=Decimal(50_000),
    )

    row = receipt.lines[0]
    assert Decimal(row.unit_cost) == Decimal(5_000), "«فی» نباید دست بخورد"
    assert row.landed_unit_cost == Decimal(5_250), "«فی تمام‌شده» باید حمل را در خود داشته باشد"


def test_the_stock_ledger_stores_the_landed_cost(db, user):
    """دفترِ انبار بهای تمام‌شده را می‌نویسد، نه فی.

    اگر فی بنشیند، فروشِ بعدی بهای تمام‌شده‌ی کمتر و **سودِ بیشتر از واقع**
    گزارش می‌کند.
    """
    first = make_item(db, name="کالای اول")
    second = make_item(db, name="کالای دوم")
    receipt = direct(
        db,
        user,
        [line(first, 100, 5_000), line(second, 150, 6_000)],
        freight_amount=Decimal(50_000),
    )
    assert ledger_cost(db, receipt, first) == Decimal(5_250)


def test_inventory_value_includes_the_freight(db, user):
    """ارزشِ موجودی = کالا + حمل. بدونِ این، ۵۰٬۰۰۰ بی‌صدا گم می‌شد."""
    item = make_item(db, name="لیوان")
    before = Decimal(get_inventory_report(db, None, as_of=TODAY)["total_value"])

    direct(db, user, [line(item, 100, 5_000)], freight_amount=Decimal(50_000))

    after = Decimal(get_inventory_report(db, None, as_of=TODAY)["total_value"])
    assert after - before == Decimal(550_000)


def test_average_cost_uses_the_landed_cost(db, user):
    item = make_item(db, name="لیوان")
    direct(db, user, [line(item, 100, 5_000)], freight_amount=Decimal(50_000))
    assert Decimal(item.average_cost) == Decimal(5_500)


def test_a_service_line_carries_no_freight(db, user):
    """حمل بهای *آوردنِ جنس* است؛ خدمتی که در همان رسید آمده جابه‌جا نشده."""
    goods = make_item(db, name="لیوان")
    service = make_item(db, name="نصب", is_service=True)

    receipt = direct(
        db,
        user,
        [line(goods, 10, 1_000), line(service, 1, 500_000)],
        freight_amount=Decimal(30_000),
    )

    shares = {row.item_id: Decimal(row.freight_share) for row in receipt.lines}
    assert shares[service.id] == Decimal(0)
    assert shares[goods.id] == Decimal(30_000), "همه‌ی حمل باید روی کالا بنشیند"


def test_freight_on_a_services_only_receipt_is_refused(db, user):
    """حملی که جایی برای نشستن ندارد، بی‌صدا به هزینه نمی‌رود."""
    service = make_item(db, name="مشاوره", is_service=True)
    with pytest.raises(HTTPException) as err:
        direct(db, user, [line(service, 1, 100_000)], freight_amount=Decimal(20_000))
    assert err.value.status_code == 400


# ─────────────────── §۲۶ — مالیات وارد بهای کالا نمی‌شود ───────────────────


def test_tax_stays_out_of_the_landed_cost(db, user):
    """§۲۶ — «ایجنت نباید فرض کند Inventory Cost = Price + Freight + VAT.»"""
    item = make_item(db, name="لیوان", tax_rate=Decimal(10))
    ledger = Ledger(db).snap(cc.INVENTORY, cc.VAT_RECEIVABLE)

    receipt = direct(
        db,
        user,
        [line(item, 100, 5_000)],
        freight_amount=Decimal(50_000),
        tax_rate=Decimal(10),
    )

    assert ledger.delta(cc.INVENTORY) == Decimal(550_000), "مالیات نباید در بهای کالا باشد"
    assert ledger.delta(cc.VAT_RECEIVABLE) == Decimal(50_000)
    assert receipt.lines[0].landed_unit_cost == Decimal(5_500)


def test_an_exempt_item_is_not_taxed(db, user):
    """نرخِ مؤثر از همان موتورِ فصلِ کالا می‌آید، نه یک محاسبه‌ی محلیِ تازه."""
    item = make_item(db, name="نان", purchase_vat_status="exempt")
    receipt = direct(db, user, [line(item, 10, 1_000)], tax_rate=Decimal(10))
    assert Decimal(receipt.lines[0].tax_amount_snapshot) == Decimal(0)


def test_freight_tax_is_a_credit_not_a_cost(db, user):
    """مالیاتِ حمل هم اعتبارِ مالیاتی است، نه بهای کالا (§۲۵ §۲۶)."""
    item = make_item(db, name="لیوان")
    ledger = Ledger(db).snap(cc.INVENTORY, cc.VAT_RECEIVABLE)

    direct(
        db,
        user,
        [line(item, 10, 10_000)],
        freight_amount=Decimal(50_000),
        freight_tax=Decimal(4_500),
    )

    assert ledger.delta(cc.INVENTORY) == Decimal(150_000)
    assert ledger.delta(cc.VAT_RECEIVABLE) == Decimal(4_500)


def test_freight_duty_is_a_cost_not_a_credit(db, user):
    """عوارض جزءِ بهای ورود است — همان رفتاری که فاکتورِ خرید با عوارض دارد."""
    item = make_item(db, name="لیوان")
    ledger = Ledger(db).snap(cc.INVENTORY, cc.VAT_RECEIVABLE)

    receipt = direct(
        db,
        user,
        [line(item, 10, 10_000)],
        freight_amount=Decimal(50_000),
        freight_duty=Decimal(10_000),
    )

    assert ledger.delta(cc.INVENTORY) == Decimal(160_000)
    assert ledger.delta(cc.VAT_RECEIVABLE) == Decimal(0)
    assert Decimal(receipt.lines[0].freight_share) == Decimal(60_000)


# ─────────────────── §۲۵ §۲۷ — خالص از اجزای خودش توضیح‌پذیر است ───────────────────


def test_the_net_is_explained_by_its_parts(db, user):
    """**نمونه‌ی §۲۵:** ۱٬۴۰۰٬۰۰۰ کالا + ۵۰٬۰۰۰ حمل + ۴۵٬۰۰۰ مالیات = ۱٬۴۹۵٬۰۰۰."""
    taxed = make_item(db, name="کالای اول", tax_rate=Decimal(9))
    exempt = make_item(db, name="کالای دوم", purchase_vat_status="exempt")

    receipt = direct(
        db,
        user,
        [line(taxed, 100, 5_000), line(exempt, 150, 6_000)],
        freight_amount=Decimal(50_000),
    )

    assert receipt.goods_amount == Decimal(1_400_000)
    assert receipt.tax_amount == Decimal(45_000)
    assert receipt.net_amount == Decimal(1_495_000)


def test_the_freight_window_total_is_not_a_net_component(db, user):
    """§۲۱ «جمع مبلغ حمل» جمعِ خودِ پنجره است؛ افزودنش به خالص یعنی دوباره‌شماری."""
    item = make_item(db, name="لیوان")
    receipt = direct(
        db,
        user,
        [line(item, 10, 10_000)],
        freight_amount=Decimal(50_000),
        freight_tax=Decimal(4_500),
        freight_duty=Decimal(1_000),
    )

    assert receipt.freight_total == Decimal(55_500)
    assert receipt.net_amount == Decimal(100_000 + 50_000 + 1_000 + 4_500)


def test_nothing_about_the_net_is_stored(db, user):
    """§۲۷ — «نه اینکه این عدد جداگانه و دستی نگهداری شود.»"""
    from app.models.invoices import WarehouseReceipt

    stored = {column.key for column in WarehouseReceipt.__table__.columns}
    assert "net_amount" not in stored
    assert "goods_amount" not in stored
    assert "total_amount" not in stored


# ─────────────────── §۳۷ — حمل بدهیِ حمل‌کننده است، نه تأمین‌کننده ───────────────────


def test_freight_does_not_touch_the_supplier(db, user):
    """کرایه بدهی به حمل‌کننده است. شمردنش روی تأمین‌کننده یعنی بدهیِ ساختگی."""
    item = make_item(db, name="لیوان")
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    carrier = make_contact(db, name="باربری", type_="supplier")
    ledger = Ledger(db).snap(cc.ACCOUNTS_PAYABLE)

    direct(
        db,
        user,
        [line(item, 10, 10_000)],
        contact_id=supplier.id,
        carrier_id=carrier.id,
        freight_amount=Decimal(50_000),
    )

    #: هر دو بدهی‌اند و هر دو واقعی: ۱۰۰٬۰۰۰ کالا + ۵۰٬۰۰۰ حمل.
    assert ledger.delta(cc.ACCOUNTS_PAYABLE) == Decimal(-150_000)


def test_freight_without_a_carrier_is_cash(db, user):
    item = make_item(db, name="لیوان")
    ledger = Ledger(db).snap(cc.CASH)

    direct(db, user, [line(item, 10, 10_000)], freight_amount=Decimal(50_000))

    assert ledger.delta(cc.CASH) == Decimal(-150_000)


# ─────────────────── حمل روی مسیرِ فاکتوردار هم هست ───────────────────


def buy_pending(db, user, item, *, qty, unit_cost, tax_rate=0):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=None,
            contact_id=make_contact(db, name="تأمین‌کننده", type_="supplier").id,
            tax_rate=Decimal(tax_rate),
            lines=[
                PurchaseInvoiceLineIn(
                    item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost)
                )
            ],
        ),
        user,
    )


def receive(db, user, invoice, qty, **header):
    return create_warehouse_receipt(
        db,
        invoice.id,
        WarehouseReceiptIn(
            receipt_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[
                WarehouseReceiptLineIn(
                    purchase_invoice_line_id=invoice.lines[0].id, qty=Decimal(qty)
                )
            ],
            **header,
        ),
        user,
    )


def test_an_invoice_backed_receipt_also_lands_its_freight(db, user):
    """فاکتور کالا را شناخته، ولی کرایه را ندیده — پس رسید باید ببیندش."""
    item = make_item(db, name="لیوان")
    invoice = buy_pending(db, user, item, qty=100, unit_cost=5_000)
    ledger = Ledger(db).snap(cc.INVENTORY, cc.GOODS_IN_TRANSIT, cc.CASH)

    receipt = receive(db, user, invoice, 100, freight_amount=Decimal(50_000))

    assert ledger.delta(cc.GOODS_IN_TRANSIT) == Decimal(-500_000), "کالا از «در راه» خارج شود"
    assert ledger.delta(cc.INVENTORY) == Decimal(550_000), "کالا + حمل"
    assert ledger.delta(cc.CASH) == Decimal(-50_000), "فقط کرایه نقد شده"
    assert receipt.lines[0].landed_unit_cost == Decimal(5_500)


def test_an_invoice_backed_receipt_never_re_recognises_the_tax(db, user):
    """§۳۷ — مالیاتِ کالا را فاکتور شناخته؛ رسید فقط چاپش می‌کند."""
    item = make_item(db, name="لیوان", tax_rate=Decimal(9))
    invoice = buy_pending(db, user, item, qty=100, unit_cost=5_000, tax_rate=9)
    ledger = Ledger(db).snap(cc.VAT_RECEIVABLE)

    receipt = receive(db, user, invoice, 100)

    assert Decimal(receipt.lines[0].tax_amount_snapshot) == Decimal(45_000), "برای چاپ هست"
    assert ledger.delta(cc.VAT_RECEIVABLE) == Decimal(0), "ولی دوباره ثبت نمی‌شود"


def test_a_partial_receipt_prints_only_its_share_of_the_tax(db, user):
    item = make_item(db, name="لیوان", tax_rate=Decimal(9))
    invoice = buy_pending(db, user, item, qty=100, unit_cost=5_000, tax_rate=9)

    receipt = receive(db, user, invoice, 40)

    assert Decimal(receipt.lines[0].tax_amount_snapshot) == Decimal(18_000)


def test_one_receipt_makes_one_journal_entry(db, user):
    """کالا و حمل ردیف‌های **یک** سندند — وگرنه ابطال فقط یکی را برمی‌گرداند."""
    item = make_item(db, name="لیوان")
    invoice = buy_pending(db, user, item, qty=100, unit_cost=5_000)

    receipt = receive(db, user, invoice, 100, freight_amount=Decimal(50_000))

    assert receipt.journal_entry_id is not None
    accounts = {
        line.account_id
        for line in db.query(JournalLine).filter(JournalLine.entry_id == receipt.journal_entry_id)
    }
    assert get_account(db, cc.GOODS_IN_TRANSIT).id in accounts
    assert get_account(db, cc.CASH).id in accounts


def test_voiding_reverses_the_freight_too(db, user):
    """ابطالِ نیمه‌کاره یعنی کالا برگردد و کرایه‌اش در دفتر بماند."""
    item = make_item(db, name="لیوان")
    receipt = direct(db, user, [line(item, 10, 10_000)], freight_amount=Decimal(50_000))
    ledger = Ledger(db).snap(cc.INVENTORY, cc.CASH)

    void_warehouse_receipt(db, receipt.id, reason="اشتباه بود", user=user)

    assert ledger.delta(cc.INVENTORY) == Decimal(-150_000)
    assert ledger.delta(cc.CASH) == Decimal(150_000)


def test_a_receipt_without_freight_behaves_exactly_as_before(db, user):
    """رسیدهای موجود تکان نمی‌خورند: بی‌حمل یعنی فی تمام‌شده = فی."""
    item = make_item(db, name="لیوان")
    receipt = direct(db, user, [line(item, 10, 10_000)])

    row = receipt.lines[0]
    assert Decimal(row.freight_share) == Decimal(0)
    assert row.landed_unit_cost == Decimal(row.unit_cost) == Decimal(10_000)
    assert receipt.net_amount == receipt.goods_amount == Decimal(100_000)


def test_lines_come_back_in_the_order_they_were_entered(db, user):
    """ترتیبِ ردیف‌ها با `id` بود و `id` یک UUIDِ **تصادفی** است.

    یعنی چاپِ رسید (§۴۱ §۴۲) هر بار می‌توانست ترتیبِ دیگری بدهد — و بدتر:
    ته‌ماندهٔ تسهیمِ حمل روی «ردیفِ آخر» می‌نشیند و «آخر» معنای ثابتی نداشت.
    """
    names = ["الف", "ب", "پ", "ت", "ث"]
    items = [make_item(db, name=name) for name in names]

    receipt = direct(db, user, [line(item, 1, 1_000) for item in items])

    assert [row.item_name_snapshot for row in receipt.lines] == names
    assert [row.seq for row in receipt.lines] == [1, 2, 3, 4, 5]


def test_the_rounding_remainder_lands_on_the_last_line(db, user):
    """و «آخر» همان ردیفِ آخرِ اپراتور است، نه یک ردیفِ تصادفی."""
    items = [make_item(db, name=f"کالا {i}") for i in range(3)]
    receipt = direct(
        db, user, [line(item, 1, 1_000) for item in items], freight_amount=Decimal(1_000)
    )
    shares = [Decimal(row.freight_share) for row in receipt.lines]
    assert shares == [Decimal(333), Decimal(333), Decimal(334)]


def test_ledger_and_stock_report_agree_when_the_cost_does_not_divide(db, user):
    """**نقصی که فقط راستی‌آزماییِ زنده پیدایش کرد.**

    با اعدادِ خودِ فصل، بهای تمام‌شده‌ی ردیفِ دوم ۹۲۵٬۰۰۰ ÷ ۱۵۰ = ۶٬۱۶۶٫۶۶…
    می‌شود. `average_cost` و `stock_ledger.unit_cost` ریالِ صحیح بودند، پس عدد
    به ۶٬۱۶۷ گِرد می‌شد و گزارش ۱۵۰ × ۶٬۱۶۷ را جمع می‌زد:

        دفتر            = ۱٬۴۵۰٬۰۰۰
        گزارشِ انبار     = ۱٬۴۵۰٬۰۵۰

    ۵۰ ریال، بی‌آنکه هیچ ترازی به‌هم بخورد. نقص از پیش بود (هر فاکتورِ خریدی که
    خالصش بر تعداد بخش‌پذیر نباشد همین را می‌ساخت)، ولی تسهیمِ حمل کسرِ اعشاری
    را از استثنا به قاعده تبدیل می‌کند.

    تست عمداً همان اعدادِ فصل را دارد تا اگر دقتِ ستون‌ها روزی برگشت، این‌جا
    صدا کند.
    """
    first = make_item(db, name="کالای اول")
    second = make_item(db, name="کالای دوم")
    ledger = Ledger(db).snap(cc.INVENTORY)
    before = Decimal(get_inventory_report(db, None, as_of=TODAY)["total_value"])

    direct(
        db,
        user,
        [line(first, 100, 5_000), line(second, 150, 6_000)],
        freight_amount=Decimal(50_000),
    )

    after = Decimal(get_inventory_report(db, None, as_of=TODAY)["total_value"])
    assert ledger.delta(cc.INVENTORY) == Decimal(1_450_000)
    assert after - before == Decimal(1_450_000), "دفتر و گزارشِ انبار باید یک عدد بگویند"
