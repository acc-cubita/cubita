"""پروفایلِ حسابداریِ نوعِ فروش — دری که نبود، و برگشتی که تفکیک نمی‌شد.

**آنچه پروب نشان داد.** موتورِ ثبت از ابتدا درست بود: یک نوعِ فروش با حسابِ کالا و
حسابِ خدمت، فاکتورِ مخلوط را دو تکه می‌کرد. ولی تایپِ `SaleType` در رابط پنج فیلدِ
حساب را **نداشت**، `updateSaleType` هیچ مصرف‌کننده‌ای نداشت، و `PATCH` با بدنه‌ی
ناقص ۲۰۰ برمی‌گرداند و هر هفت حساب را `NULL` می‌کرد.

پس این تست‌ها سه چیز را نگه می‌دارند: (۱) تفکیکِ کالا/خدمت در فروش و در **برگشت**،
(۲) اینکه `PATCH`ِ جزئی دیگر چیزی را پاک نمی‌کند، (۳) اینکه سندِ دیروز با تغییرِ
نگاشتِ امروز بازنویسی نمی‌شود.
"""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.accounting import Account, JournalLine
from app.models.audit import AuditLog
from app.models.sales_ops import SaleType
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.schemas.returns import SalesReturnIn, SalesReturnLineIn
from app.services import chart_codes as cc
from app.services.common import get_account
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.returns import post_sales_return, sales_return_account
from tests.factories import main_warehouse, make_contact, make_item

TODAY = date(2026, 3, 15)


# ───────────────────────────── کمکی‌ها ─────────────────────────────


#: کدِ یکتا برای هر حسابِ آزمایشی. تست‌هایی که `client` دارند **commit می‌کنند**
#: و دیتابیسِ تست مشترک است؛ کدِ ثابت از اجرای قبلی جا می‌مانَد و برخورد می‌کند.
def income_account(db, name: str) -> Account:
    parent = db.query(Account).filter(Account.code == "41").one_or_none()
    account = Account(
        code=f"49{uuid4().hex[:8]}", name=name, type="income", is_group=False,
        parent_id=parent.id if parent else None,
    )
    db.add(account)
    db.flush()
    return account


def stock(db, user, item, qty=10, cost=100):
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            contact_id=make_contact(db).id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(cost))],
        ),
        user,
    )


def sell(db, user, lines, sale_type_id=None, contact=None):
    return post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            contact_id=(contact or make_contact(db)).id,
            sale_type_id=sale_type_id,
            lines=lines,
        ),
        user,
    )


def journal_by_code(db, entry_id) -> dict[str, tuple[Decimal, Decimal]]:
    out: dict[str, tuple[Decimal, Decimal]] = {}
    for line in db.query(JournalLine).filter(JournalLine.entry_id == entry_id):
        code = db.get(Account, line.account_id).code
        prev = out.get(code, (Decimal(0), Decimal(0)))
        out[code] = (prev[0] + Decimal(line.debit), prev[1] + Decimal(line.credit))
    return out


# ─────────── ۱) فروش: کالا و خدمت به دو حسابِ نوعِ فروش (§۱۰ §۱۸ §۱۹) ───────────


def test_goods_and_service_revenue_split_by_sale_type(db, user):
    """شاهدِ مرکزیِ فصل: یک فاکتور، دو حسابِ درآمد."""
    goods = make_item(db, name="لیوان")
    service = make_item(db, name="نصب", is_service=True)
    stock(db, user, goods)
    goods_account = income_account(db, "فروش کالا — عمده")
    service_account = income_account(db, "فروش خدمات — عمده")
    sale_type = SaleType(
        name="عمده",
        goods_revenue_account_id=goods_account.id,
        service_revenue_account_id=service_account.id,
    )
    db.add(sale_type)
    db.flush()

    invoice = sell(
        db, user,
        [
            SalesInvoiceLineIn(item_id=goods.id, qty=Decimal(1), unit_price=Decimal(1000)),
            SalesInvoiceLineIn(item_id=service.id, qty=Decimal(1), unit_price=Decimal(500)),
        ],
        sale_type_id=sale_type.id,
    )
    journal = journal_by_code(db, invoice.journal_entry_id)
    assert journal[goods_account.code][1] == Decimal(1000)
    assert journal[service_account.code][1] == Decimal(500)


def test_unconfigured_sale_type_falls_back_to_chart(db, user):
    """پیش‌فرض **رفتارِ دیروز** است: نوعِ فروشِ بی‌حساب، حسابِ سراسری را می‌زند."""
    item = make_item(db, name="بشقاب")
    stock(db, user, item)
    sale_type = SaleType(name="عادی")
    db.add(sale_type)
    db.flush()

    invoice = sell(
        db, user,
        [SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(900))],
        sale_type_id=sale_type.id,
    )
    revenue = get_account(db, cc.SALES_REVENUE)
    assert journal_by_code(db, invoice.journal_entry_id)[revenue.code][1] == Decimal(900)


# ─────────── ۲) برگشت: حسابِ برگشتِ تنظیم‌شده، تفکیک‌شده (§۱۳ §۱۴ §۱۵) ───────────


def test_return_uses_configured_return_accounts_split_by_nature(db, user):
    """برگشتِ کالا و برگشتِ خدمت دو حسابِ جدا می‌گیرند، نه یک عددِ واحد.

    پیش از این **همه‌چیز** — کالا و خدمت، و برای هر نوعِ فروش — به یک حسابِ
    سراسری می‌رفت و تفکیکش اصلاً پرسیدنی نبود.
    """
    goods = make_item(db, name="صندلی")
    service = make_item(db, name="مونتاژ", is_service=True)
    stock(db, user, goods)
    goods_return = income_account(db, "برگشت فروش کالا")
    service_return = income_account(db, "برگشت فروش خدمات")
    sale_type = SaleType(
        name="خرده",
        goods_return_account_id=goods_return.id,
        service_return_account_id=service_return.id,
    )
    db.add(sale_type)
    db.flush()

    invoice = sell(
        db, user,
        [
            SalesInvoiceLineIn(item_id=goods.id, qty=Decimal(2), unit_price=Decimal(1000)),
            SalesInvoiceLineIn(item_id=service.id, qty=Decimal(1), unit_price=Decimal(400)),
        ],
        sale_type_id=sale_type.id,
    )
    sret = post_sales_return(
        db,
        SalesReturnIn(
            return_date=TODAY,
            sales_invoice_id=invoice.id,
            lines=[
                SalesReturnLineIn(item_id=goods.id, qty=Decimal(1)),
                SalesReturnLineIn(item_id=service.id, qty=Decimal(1)),
            ],
        ),
        user,
    )
    journal = journal_by_code(db, sret.journal_entry_id)
    assert journal[goods_return.code][0] == Decimal(1000), "برگشتِ کالا به حسابِ خودش نرفت"
    assert journal[service_return.code][0] == Decimal(400), "برگشتِ خدمت به حسابِ خودش نرفت"
    assert sales_return_account(db).code not in journal, "هنوز حسابِ سراسری هم زده شد"


def test_return_without_configuration_keeps_yesterdays_account(db, user):
    """نوعِ فروشِ بی‌حسابِ برگشت — و فاکتورِ بی‌نوعِ فروش — همان مسیرِ قبلی."""
    item = make_item(db, name="میز")
    stock(db, user, item)
    invoice = sell(db, user, [SalesInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_price=Decimal(500))])
    sret = post_sales_return(
        db,
        SalesReturnIn(
            return_date=TODAY,
            sales_invoice_id=invoice.id,
            lines=[SalesReturnLineIn(item_id=item.id, qty=Decimal(1))],
        ),
        user,
    )
    journal = journal_by_code(db, sret.journal_entry_id)
    assert journal[sales_return_account(db).code][0] == Decimal(500)


def test_return_credits_the_same_receivable_the_invoice_debited(db, user):
    """برگشت باید همان حسابی را ببندد که فاکتور باز کرده بود.

    پیش از این برگشت **همیشه** دریافتنیِ سراسری را بستانکار می‌کرد؛ فاکتوری با
    حسابِ دریافتنیِ اختصاصی، ماندهٔ بازنشده روی حسابِ خودش و یک بستانکارِ شبح روی
    حسابِ سراسری جا می‌گذاشت.
    """
    item = make_item(db, name="کمد")
    stock(db, user, item)
    receivable = db.query(Account).filter(
        Account.code == "1104"
    ).one_or_none() or get_account(db, cc.ACCOUNTS_RECEIVABLE)
    special = Account(
        code=f"19{uuid4().hex[:8]}", name="دریافتنیِ ویژه", type="asset", is_group=False,
        parent_id=receivable.parent_id,
    )
    db.add(special)
    db.flush()

    invoice = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            contact_id=make_contact(db).id,
            receivable_account_id=special.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_price=Decimal(700))],
        ),
        user,
    )
    assert journal_by_code(db, invoice.journal_entry_id)[special.code][0] == Decimal(1400)

    sret = post_sales_return(
        db,
        SalesReturnIn(
            return_date=TODAY,
            sales_invoice_id=invoice.id,
            lines=[SalesReturnLineIn(item_id=item.id, qty=Decimal(1))],
        ),
        user,
    )
    journal = journal_by_code(db, sret.journal_entry_id)
    assert journal[special.code][1] == Decimal(700), "برگشت حسابِ خودِ فاکتور را نبست"


# ─────────── ۳) ویرایشِ جزئی — همان باگی که پروب گرفت ───────────


def test_patch_without_account_fields_does_not_wipe_them(client, db):
    """**گاردِ همان باگ.** بدنه‌ی بی‌حساب دیگر حساب‌ها را پاک نمی‌کند."""
    account = income_account(db, "فروش کالا — نمایندگی")
    sale_type = SaleType(name=f"نمایندگی-{uuid4().hex[:6]}", goods_revenue_account_id=account.id)
    db.add(sale_type)
    db.flush()

    response = client.patch(
        f"/api/sales-ops/sale-types/{sale_type.id}",
        json={"description": "توضیحِ تازه"},
    )
    assert response.status_code == 200
    assert response.json()["goods_revenue_account_id"] == str(account.id)
    db.expire_all()
    assert db.get(SaleType, sale_type.id).goods_revenue_account_id == account.id


def test_patch_can_still_clear_an_account_explicitly(client, db):
    """پاک‌کردن باید **ممکن** بماند — فقط نه به‌طورِ اتفاقی."""
    account = income_account(db, "فروش کالا — پروژه")
    sale_type = SaleType(name=f"پروژه‌ای-{uuid4().hex[:6]}", goods_revenue_account_id=account.id)
    db.add(sale_type)
    db.flush()

    response = client.patch(
        f"/api/sales-ops/sale-types/{sale_type.id}",
        json={"goods_revenue_account_id": None},
    )
    assert response.status_code == 200
    db.expire_all()
    assert db.get(SaleType, sale_type.id).goods_revenue_account_id is None


@pytest.mark.parametrize("field", ["goods_revenue_account_id", "service_return_account_id"])
def test_group_account_is_rejected_at_configuration_time(client, db, field):
    """غافلگیری نباید به لحظه‌ی ثبتِ سند موکول شود (§۶۸)."""
    group = db.query(Account).filter(Account.is_group.is_(True)).first()
    assert group is not None
    response = client.post(
        "/api/sales-ops/sale-types",
        json={"name": f"گروهی-{field}-{uuid4().hex[:6]}", field: str(group.id)},
    )
    assert response.status_code == 400
    assert "گروه" in response.json()["detail"]


def test_duplicate_code_is_rejected_but_empty_code_is_not(client, db):
    """کد اختیاری است؛ چند نوعِ بی‌کد کنارِ هم زندگی می‌کنند (ایندکسِ جزئی)."""
    tag, code = uuid4().hex[:6], uuid4().hex[:8]
    post = lambda body: client.post("/api/sales-ops/sale-types", json=body).status_code
    assert post({"name": f"الف-{tag}", "code": code}) == 201
    assert post({"name": f"ب-{tag}", "code": code}) == 409
    assert post({"name": f"پ-{tag}"}) == 201
    assert post({"name": f"ت-{tag}"}) == 201


# ─────────── ۴) تغییرِ نگاشت گذشته را بازنویسی نمی‌کند (§۲۹ §۳۰ §۳۶) ───────────


def test_changing_the_mapping_never_rewrites_a_posted_journal(db, user, client):
    item = make_item(db, name="قفسه")
    stock(db, user, item, qty=20)
    old = income_account(db, "درآمدِ قدیم")
    new = income_account(db, "درآمدِ جدید")
    sale_type = SaleType(name=f"تاریخی-{uuid4().hex[:6]}", goods_revenue_account_id=old.id)
    db.add(sale_type)
    db.flush()

    invoice = sell(
        db, user,
        [SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(600))],
        sale_type_id=sale_type.id,
    )
    assert journal_by_code(db, invoice.journal_entry_id)[old.code][1] == Decimal(600)

    response = client.patch(
        f"/api/sales-ops/sale-types/{sale_type.id}",
        json={"goods_revenue_account_id": str(new.id)},
    )
    assert response.status_code == 200

    #: سندِ دیروز دست‌نخورده…
    after = journal_by_code(db, invoice.journal_entry_id)
    assert after[old.code][1] == Decimal(600)
    assert new.code not in after
    #: …و فروشِ بعدی حسابِ تازه را می‌گیرد.
    db.expire_all()
    later = sell(
        db, user,
        [SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(600))],
        sale_type_id=sale_type.id,
    )
    assert journal_by_code(db, later.journal_entry_id)[new.code][1] == Decimal(600)


# ─────────── ۵) حسابرسی (§۷۲ §۷۳) ───────────


def test_account_mapping_change_leaves_an_audit_trail(db, user, client):
    """تغییرِ حسابِ نوعِ فروش باید رد بگذارد — تا امروز هیچ ردی نمی‌گذاشت."""
    account = income_account(db, "فروش کالا — حسابرسی")
    sale_type = SaleType(name=f"حسابرسی‌شونده-{uuid4().hex[:6]}")
    db.add(sale_type)
    db.flush()
    before = db.query(AuditLog).count()

    response = client.patch(
        f"/api/sales-ops/sale-types/{sale_type.id}",
        json={"goods_revenue_account_id": str(account.id)},
    )
    assert response.status_code == 200
    assert db.query(AuditLog).count() > before, "تغییرِ نگاشتِ حساب ردی نگذاشت"
