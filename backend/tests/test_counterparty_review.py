"""مرور جامع طرف حساب — و مرزهایی که یک گزارش نباید از آن‌ها رد شود.

این فصل بیش از هر چیز درباره‌ی **نشمردنِ دوباره** است. یک مبلغ می‌تواند در سه
دانه‌بندیِ گزارش دیده شود (نقش، سند، ردیفِ سند) و اگر مرزها محو شوند همان مبلغ
سه بار در مانده می‌نشیند.

و یک ادعای مرکزی: **گزارش باید با دفتر بخواند.** تا پیش از این فصل نمی‌خواند —
فاکتوری با اضافات و عوارض در دفتر ۱۵٬۰۰۰ مطالبات می‌ساخت و کارتِ حساب ۱۰٬۰۰۰
می‌گفت.
"""
from datetime import date
from decimal import Decimal

from app.models.accounting import JournalLine
from app.services import chart_codes as cc
from app.services import counterparty
from app.services.common import get_account
from app.services.credit import customer_outstanding
from app.services.reports import contact_balance, get_contact_statement

TODAY = date.today().isoformat()


def _customer(client, name="مشتریِ مرور"):
    return client.post("/api/contacts", json={"name": name, "type": "customer"}).json()["id"]


def _supplier(client, name="تأمین‌کننده‌ی مرور"):
    return client.post("/api/contacts", json={"name": name, "type": "supplier"}).json()["id"]


def _stocked(client, sku="CR-1"):
    wh = client.post("/api/warehouses", json={"code": sku, "name": "انبار"}).json()["id"]
    item = client.post("/api/items", json={"sku": sku, "name": "کالا", "sales_price": 1000}).json()["id"]
    client.post(
        "/api/purchase-invoices",
        json={"invoice_date": TODAY, "warehouse_id": wh, "lines": [{"item_id": item, "qty": 80, "unit_cost": 400}]},
    )
    return wh, item


def _sell(client, wh, item, contact, *, qty=10, price=1000, addition=0, duty=0):
    r = client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": TODAY,
            "warehouse_id": wh,
            "contact_id": contact,
            "tax_rate": 0,
            "lines": [
                {
                    "item_id": item,
                    "qty": qty,
                    "unit_price": price,
                    "addition": addition,
                    "duty_amount": duty,
                }
            ],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _ar_movement(db, contact_analytic_id):
    rows = (
        db.query(JournalLine.debit, JournalLine.credit)
        .filter(JournalLine.analytic_id == contact_analytic_id)
        .all()
    )
    return sum((Decimal(d) - Decimal(c) for d, c in rows), Decimal(0))


# ═══════════════════ ۱) گزارش با دفتر می‌خواند ═══════════════════


def test_the_statement_matches_the_ledger_when_the_invoice_has_additions(client, db):
    """باگی که این فصل بست.

    سندِ فاکتور «خالص + اضافات + عوارض + مالیات + رند» را بدهکار می‌کند. کارتِ
    حساب فقط «خالص + مالیات» را می‌شمرد، پس از مهاجرتِ ۰۱۲۵ به بعد هر فاکتورِ
    اضافات‌دار گزارش را از دفتر جدا می‌کرد.
    """
    contact = _customer(client, "مشتریِ اضافات")
    wh, item = _stocked(client, "CR-ADD")
    ar = get_account(db, cc.ACCOUNTS_RECEIVABLE)

    before = sum(
        (Decimal(d) - Decimal(c))
        for d, c in db.query(JournalLine.debit, JournalLine.credit)
        .filter(JournalLine.account_id == ar.id)
        .all()
    )
    _sell(client, wh, item, contact, qty=10, price=1000, addition=3000, duty=2000)
    db.expire_all()
    after = sum(
        (Decimal(d) - Decimal(c))
        for d, c in db.query(JournalLine.debit, JournalLine.credit)
        .filter(JournalLine.account_id == ar.id)
        .all()
    )

    ledger_delta = after - before
    assert ledger_delta == 15_000, "دفتر: ۱۰٬۰۰۰ کالا + ۳٬۰۰۰ اضافات + ۲٬۰۰۰ عوارض"

    statement = get_contact_statement(db, contact, None, None)
    assert Decimal(statement["closing_balance"]) == ledger_delta
    assert contact_balance(db, contact) == ledger_delta


def test_all_three_balance_readers_agree(client, db):
    """سه جا مانده را می‌خوانند — و باید یک عدد بدهند.

    بنرِ سقفِ اعتبار فرمولِ کامل را داشت و کارتِ حساب نه؛ کاربر بسته به اینکه
    کدام صفحه را باز کند دو عددِ متفاوت می‌دید.
    """
    contact = _customer(client, "مشتریِ سه‌موتور")
    wh, item = _stocked(client, "CR-3E")
    _sell(client, wh, item, contact, qty=5, price=2000, addition=1000, duty=500)

    db.expire_all()
    statement = Decimal(get_contact_statement(db, contact, None, None)["closing_balance"])
    balance = contact_balance(db, contact)
    outstanding = customer_outstanding(db, contact)

    assert statement == balance == outstanding


# ═══════════════════ ۲) نقش‌ها جدا می‌مانند ═══════════════════


def test_customer_and_supplier_positions_stay_apart(client, db):
    """یک عددِ خالص، دو وضعیتِ متفاوتِ تجاری را یکی نشان می‌دهد."""
    both = client.post("/api/contacts", json={"name": "دوطرفه", "type": "both"}).json()["id"]
    wh, item = _stocked(client, "CR-BOTH")
    _sell(client, wh, item, both, qty=10, price=1000)          # طلبِ ما: ۱۰٬۰۰۰
    r = client.post(
        "/api/purchase-invoices",
        json={
            "invoice_date": TODAY,
            "warehouse_id": wh,
            "contact_id": both,
            "lines": [{"item_id": item, "qty": 5, "unit_cost": 600}],  # بدهیِ ما: ۳٬۰۰۰
        },
    )
    assert r.status_code == 201, r.text

    db.expire_all()
    summary = counterparty.position_summary(db, both)
    by_role = {row["role"]: row for row in summary["positions"]}

    assert by_role["customer"]["net"] == 10_000
    assert by_role["supplier"]["net"] == -3_000
    #: جمع **مشتق** است و هر دو عددِ ناخالص سرِ جایشان می‌مانند.
    assert summary["total_net"] == 7_000


def test_the_report_never_offsets_the_roles_in_the_ledger(client, db):
    """تهاترِ واقعی یک رویدادِ اقتصادیِ صریح می‌خواهد، نه بازکردنِ یک گزارش."""
    both = client.post("/api/contacts", json={"name": "دوطرفه‌ی تهاتر", "type": "both"}).json()["id"]
    wh, item = _stocked(client, "CR-OFF")
    _sell(client, wh, item, both, qty=10, price=1000)
    client.post(
        "/api/purchase-invoices",
        json={
            "invoice_date": TODAY,
            "warehouse_id": wh,
            "contact_id": both,
            "lines": [{"item_id": item, "qty": 5, "unit_cost": 600}],
        },
    )
    db.expire_all()
    before = counterparty.position_summary(db, both)

    #: گزارش را چند بار باز کن — هیچ‌چیز نباید عوض شود.
    counterparty.position_summary(db, both)
    counterparty.events(db, both)
    db.expire_all()
    after = counterparty.position_summary(db, both)

    assert {r["role"]: r["net"] for r in before["positions"]} == {
        r["role"]: r["net"] for r in after["positions"]
    }
    assert after["positions"][0]["net"] != 0 and after["positions"][1]["net"] != 0


# ═══════════════════ ۳) دانه‌بندی‌ها قاطی نمی‌شوند ═══════════════════


def test_a_document_appears_once_at_the_event_grain(client, db):
    """فاکتور و سندِ حسابداری‌اش یک رویدادند، نه دو اثرِ مستقل."""
    contact = _customer(client, "مشتریِ دانه‌بندی")
    wh, item = _stocked(client, "CR-GRAIN")
    invoice = _sell(client, wh, item, contact, qty=4, price=2500)

    db.expire_all()
    rows = counterparty.events(db, contact)
    mine = [r for r in rows if str(r["source_id"]) == invoice["id"]]
    assert len(mine) == 1, "یک ردیف، نه یکی برای فاکتور و یکی برای سندش"
    assert mine[0]["entry_number"] is not None, "شماره‌ی سند روی همان ردیف می‌نشیند"
    assert Decimal(mine[0]["document_amount"]) == 10_000


def test_item_lines_do_not_change_the_balance(client, db):
    """اقلام برای توضیح‌اند، نه برای جمع‌زدن.

    فاکتوری با سه ردیف، سه قلم دارد ولی یک اثرِ اقتصادی. اگر خلاصه از اقلام
    ساخته می‌شد، مبلغِ سربرگ سه برابر می‌شد.
    """
    contact = _customer(client, "مشتریِ اقلام")
    wh, item = _stocked(client, "CR-LINES")
    r = client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": TODAY,
            "warehouse_id": wh,
            "contact_id": contact,
            "tax_rate": 0,
            "lines": [
                {"item_id": item, "qty": 1, "unit_price": 1000},
                {"item_id": item, "qty": 2, "unit_price": 1000},
                {"item_id": item, "qty": 3, "unit_price": 1000},
            ],
        },
    )
    assert r.status_code == 201, r.text
    invoice = r.json()

    db.expire_all()
    detail = counterparty.event_lines(db, "sales_invoice", invoice["id"])
    products = [x for x in detail["lines"] if x["kind"] == counterparty.LINE_KIND_PRODUCT]
    assert len(products) == 3, "سه قلم دیده می‌شود"

    #: ولی مانده همان یک اثر است.
    assert contact_balance(db, contact) == 6_000


def test_event_lines_carry_the_journal_effect_too(client, db):
    """هر رویداد ردیف‌های دفترش را هم نشان می‌دهد — همان‌جا که اثرِ واقعی است."""
    contact = _customer(client, "مشتریِ دفتر")
    wh, item = _stocked(client, "CR-JL")
    invoice = _sell(client, wh, item, contact, qty=2, price=1500)

    db.expire_all()
    detail = counterparty.event_lines(db, "sales_invoice", invoice["id"])
    journal = [x for x in detail["lines"] if x["kind"] == counterparty.LINE_KIND_JOURNAL]
    assert journal, "ردیف‌های سند باید بیایند"
    assert detail["journal_entry_id"] is not None
    assert sum(x["debit"] for x in journal) == sum(x["credit"] for x in journal)
    #: و ستون‌هایی که برای ردیفِ دفتر معنی ندارند خالی می‌مانند، نه صفرِ ساختگی.
    assert all(x["quantity"] is None and x["unit_price"] is None for x in journal)


# ═══════════════════ ۴) ابطال و ترتیب ═══════════════════


def test_a_voided_document_stops_counting_but_stays_in_history(client, db):
    contact = _customer(client, "مشتریِ ابطال")
    wh, item = _stocked(client, "CR-VOID")
    invoice = _sell(client, wh, item, contact, qty=3, price=1000)
    db.expire_all()
    assert contact_balance(db, contact) == 3_000

    r = client.post(f"/api/sales-invoices/{invoice['id']}/void", json={"reason": "اشتباه بود"})
    assert r.status_code in (200, 204), r.text

    db.expire_all()
    assert contact_balance(db, contact) == 0, "سندِ باطل در مانده نمی‌ماند"
    assert client.get(f"/api/sales-invoices?contact_id={contact}").status_code == 200


def test_same_day_events_have_a_stable_order(client, db):
    """مانده‌ی در حالِ اجرا بدونِ ترتیبِ قطعی عددِ قابلِ اتکایی نیست."""
    contact = _customer(client, "مشتریِ ترتیب")
    wh, item = _stocked(client, "CR-ORD")
    for _ in range(3):
        _sell(client, wh, item, contact, qty=1, price=1000)

    db.expire_all()
    first = [(str(r["source_id"]), r["running_balance"]) for r in counterparty.events(db, contact)]
    second = [(str(r["source_id"]), r["running_balance"]) for r in counterparty.events(db, contact)]
    assert first == second, "دو بار خواندن باید یک ترتیب بدهد"
    assert [b for _, b in first] == [1000, 2000, 3000]


def test_the_running_balance_ends_where_the_balance_says(client, db):
    contact = _customer(client, "مشتریِ ماندهٔ خط")
    wh, item = _stocked(client, "CR-RUN")
    _sell(client, wh, item, contact, qty=7, price=1000, addition=500)

    db.expire_all()
    rows = counterparty.events(db, contact)
    assert rows[-1]["running_balance"] == contact_balance(db, contact)


# ═══════════════════ ۵) مرزهای دامنه ═══════════════════


def test_accounting_balance_is_not_the_open_item_position(client, db):
    """کم‌شدنِ مانده نمی‌گوید کدام فاکتور تسویه شده."""
    contact = _customer(client, "مشتریِ قلمِ باز")
    supplier = _supplier(client, "تأمینِ قلمِ باز")
    wh, item = _stocked(client, "CR-OI")
    _sell(client, wh, item, contact, qty=10, price=1000)

    r = client.post(
        "/api/sales-ops/notes",
        json={
            "note_date": TODAY,
            "reason": "تهاتر",
            "lines": [{"debit_contact_id": supplier, "credit_contact_id": contact, "amount": 4000}],
        },
    )
    assert r.status_code == 201, r.text

    db.expire_all()
    #: مانده عوض شد…
    assert contact_balance(db, contact) == 6_000
    #: …ولی فاکتور همچنان تسویه‌نشده است.
    events = counterparty.events(db, contact)
    invoice_row = next(x for x in events if x["source_type"] == "sales_invoice")
    assert invoice_row["status"] == "unsettled"
    assert Decimal(invoice_row["remaining_amount"]) == 10_000


def test_uncleared_cheques_are_shown_beside_the_balance_not_inside_it(client, db):
    """گزینه‌ی چک یک ستونِ نمایشی است؛ دفتر با آن عوض نمی‌شود."""
    contact = _customer(client, "مشتریِ چک")
    summary = counterparty.position_summary(db, contact)
    assert "uncleared_cheques" in summary
    assert "net_without_uncleared_cheques" in summary
    #: بدونِ چک، این دو یکی‌اند — و ستون خودش صفر است، نه غایب.
    assert summary["uncleared_cheques"] == 0
    assert summary["net_without_uncleared_cheques"] == summary["total_net"]


def test_a_contact_without_tafsili_says_so_instead_of_claiming_zero(client, db):
    """«نمی‌دانم» با صفر یکی نیست.

    مانده‌ی دفتریِ یک طرف حساب فقط با تفصیلی قابلِ استخراج است؛ بدونش گزارش
    نباید عددِ ساختگی بدهد.
    """
    contact = _customer(client, "مشتریِ بی‌تفصیلی")
    rows = counterparty.role_positions(db, contact)
    for row in rows:
        if row["ledger_net"] is None:
            assert row["unattributed"] is None


def test_a_bounced_cheque_puts_the_debt_back_on_the_customer(client, db):
    """چکی که برگشت خورده، مشتری را دوباره بدهکار می‌کند — در **هر** نمایی.

    رویدادِ واخواست تا امروز `contact_id` نداشت، پس احیای مطالبات به هیچ‌کس نسبت
    داده نمی‌شد: در نمای اقلامِ باز، چکِ برگشتی همچنان «پرداختِ مشتری» به نظر
    می‌رسید و می‌شد بابتش فاکتور تسویه کرد.
    """
    from app.models.banking import BankAccount
    from app.schemas.banking import CheckIn
    from app.services.check_ops import create_check, update_check_status

    contact = _customer(client, "مشتریِ چکِ برگشتی")
    wh, item = _stocked(client, "CR-BNC")
    _sell(client, wh, item, contact, qty=10, price=1000)
    db.expire_all()
    assert contact_balance(db, contact) == 10_000

    bank = db.query(BankAccount).first()
    user = db.query(type(db.query(BankAccount).first()).__mro__ and None) if False else None
    from app.models.user import User

    actor = db.query(User).first()
    cheque = create_check(
        db,
        CheckIn(
            type="receivable",
            number="CR-BNC-1",
            amount=Decimal(4_000),
            issue_date=date.today(),
            due_date=date.today(),
            contact_id=contact,
        ),
        actor,
    )
    db.expire_all()
    assert contact_balance(db, contact) == 6_000, "دریافتِ چک مطالبات را کم می‌کند"

    update_check_status(db, cheque.id, "deposited", bank.id, actor)
    update_check_status(db, cheque.id, "bounced", None, actor)
    db.expire_all()

    assert contact_balance(db, contact) == 10_000, "برگشتِ چک بدهی را برمی‌گرداند"
    #: و در خطِ زمانی هر دو رویداد دیده می‌شوند — تاریخ پاک نمی‌شود.
    cheque_rows = [r for r in counterparty.events(db, contact) if r["source_type"] == "check"]
    assert len(cheque_rows) == 2, "دریافت و واخواست، هر دو"
    assert {r["side"] for r in cheque_rows} == {"credit", "debit"}
