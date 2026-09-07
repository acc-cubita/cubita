"""ترتیبِ ردیف‌های سند، و برگه‌ی چاپیِ سند.

## باگی که این تست‌ها می‌بندند

`JournalEntry.lines` با `order_by="JournalLine.id"` مرتب می‌شد و `id` یک UUIDِ
**تصادفی** است. یعنی ردیف‌ها به ترتیبِ ورودِ حسابدار برنمی‌گشتند و بستانکار
می‌توانست پیش از بدهکار بیاید.

## چرا `expire_all()` در این فایل حیاتی است

بدونِ آن، تست فقط فهرستِ درونِ حافظه‌ی همان session را می‌خواند — که همیشه ترتیبِ
ورود را دارد، حتی وقتی پایگاه‌داده جورِ دیگری برمی‌گرداند. یعنی **تستِ سبز بدونِ
اینکه چیزی را سنجیده باشد.** `expire_all` مجبورش می‌کند دوباره از پایگاه‌داده
بخواند، یعنی همان مسیری که کاربر سرِ بازکردنِ سند طی می‌کند.
"""
from datetime import date
from decimal import Decimal

from app.models.accounting import JournalEntry, JournalLine
from app.models.tenant import Tenant
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.tenant_context import session_tenant
from tests.factories import main_warehouse, make_item


def _hybrid(db) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = "hybrid"
    db.flush()


def _four_line_entry(db, user) -> JournalEntry:
    """سندی که ترتیبش واقعاً مهم است — چهار ردیف، نه دو تا.

    با دو ردیف هر ترتیبی نصفِ مواقع درست از آب درمی‌آید و باگ دیده نمی‌شود.
    """
    cash = get_account(db, cc.CASH).id
    inventory = get_account(db, cc.INVENTORY).id
    payable = get_account(db, cc.ACCOUNTS_PAYABLE).id
    return make_journal_entry(
        db,
        date(2026, 6, 1),
        "سندِ چهارردیفی",
        "manual",
        user,
        [
            JournalLine(account_id=inventory, debit=Decimal(600), credit=0, description="یک"),
            JournalLine(account_id=cash, debit=Decimal(300), credit=0, description="دو"),
            JournalLine(account_id=payable, debit=0, credit=Decimal(400), description="سه"),
            JournalLine(account_id=payable, debit=0, credit=Decimal(500), description="چهار"),
        ],
    )


# ── ترتیب ────────────────────────────────────────────────────────────────────


def test_lines_keep_their_order_after_reload(db, user):
    """**قیدِ اصلی.** ترتیبِ ورود پس از بازخوانی از پایگاه‌داده هم می‌ماند."""
    entry = _four_line_entry(db, user)
    entry_id = entry.id

    db.expire_all()  # بدونِ این، تست فقط حافظه‌ی session را می‌خواند

    reloaded = db.get(JournalEntry, entry_id)
    assert [l.description for l in reloaded.lines] == ["یک", "دو", "سه", "چهار"]
    assert [l.seq for l in reloaded.lines] == [1, 2, 3, 4]


def test_debits_come_before_credits_on_a_reloaded_entry(db, user):
    """قرینه‌ی معنادارش: قراردادِ حسابداری روی کاغذ برقرار می‌ماند."""
    entry = _four_line_entry(db, user)
    entry_id = entry.id
    db.expire_all()

    sides = [("debit" if Decimal(l.debit) > 0 else "credit") for l in db.get(JournalEntry, entry_id).lines]

    assert sides == ["debit", "debit", "credit", "credit"]


def test_an_automatic_entry_is_numbered_too(db, user, client):
    """سندِ خودکارِ فاکتور فروش هم باید شماره بگیرد، نه فقط سندِ دستی.

    بیشترِ سندهای یک کسب‌وکار خودکارند؛ اگر فقط سندِ دستی شماره بگیرد، باگ برای
    اکثریتِ سندها سرِ جایش می‌ماند.
    """
    _hybrid(db)
    item = make_item(db, sales_price=Decimal(1_000_000))
    warehouse = main_warehouse(db)
    from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
    from app.services.inventory import post_purchase_invoice

    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 1, 1),
            warehouse_id=warehouse.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(5), unit_cost=Decimal(1000))],
        ),
        user,
    )
    res = client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": "2026-06-01",
            "warehouse_id": str(warehouse.id),
            "lines": [{"item_id": str(item.id), "qty": 1, "unit_price": 1_000_000}],
        },
    )
    assert res.status_code == 201, res.text
    entry_id = res.json()["journal_entry_id"]

    db.expire_all()
    seqs = [l.seq for l in db.get(JournalEntry, entry_id).lines]

    assert seqs == list(range(1, len(seqs) + 1)), "سندِ خودکار هم باید ۱..n شماره بگیرد"


def test_an_old_entry_with_zero_seq_still_loads(db, user):
    """**سازگاریِ عقب‌رو.** سندهای پیش از مهاجرت `seq = 0` دارند و backfill نشدند.

    ترتیبِ واقعیشان بازیابی‌شدنی نبود، پس با `id` مرتب می‌شوند — همان رفتارِ قبل.
    این تست فقط می‌گوید نشکسته‌اند.
    """
    entry = _four_line_entry(db, user)
    for line in entry.lines:
        line.seq = 0
    db.flush()
    entry_id = entry.id
    db.expire_all()

    reloaded = db.get(JournalEntry, entry_id)

    assert len(reloaded.lines) == 4
    assert all(l.seq == 0 for l in reloaded.lines)


# ── چاپ ──────────────────────────────────────────────────────────────────────


def test_the_printed_entry_shows_both_totals(db, user, client):
    """جمعِ بدهکار و بستانکار هر دو روی کاغذ می‌آیند.

    برگه‌ی سند سندِ رسمی است؛ خواننده باید توازن را همان‌جا ببیند، نه اینکه به
    درستیِ نرم‌افزار اعتماد کند.
    """
    entry = _four_line_entry(db, user)

    res = client.get(f"/api/journal-entries/{entry.id}/print")

    assert res.status_code == 200, res.text
    assert "سند حسابداری" in res.text
    assert "جمع (ریال)" in res.text
    #: جمعِ هر دو ستون ۹۰۰ است — اگر فقط یکی چاپ می‌شد، توازن دیده نمی‌شد.
    assert res.text.count("۹۰۰") >= 2


def test_the_printed_entry_lists_lines_in_order(db, user, client):
    entry = _four_line_entry(db, user)

    body = client.get(f"/api/journal-entries/{entry.id}/print").text

    assert body.index("یک") < body.index("دو") < body.index("سه") < body.index("چهار")


def test_a_voided_entry_is_marked_on_the_printout(db, user, client):
    """**قیدِ مهم.** برگه‌ی سندِ باطل نباید از سندِ معتبر قابلِ تشخیص نباشد.

    بدونِ این، یک برگه‌ی چاپ‌شده‌ی باطل می‌تواند به‌عنوان سندِ معتبر ارائه شود.
    """
    from app.services.voiding import void_journal_entry

    entry = _four_line_entry(db, user)
    void_journal_entry(db, entry.id, reason="آزمون", user=user, void_date=date(2026, 6, 2))
    db.flush()

    body = client.get(f"/api/journal-entries/{entry.id}/print").text

    assert "این سند باطل شده است" in body
    assert "آزمون" in body


def test_printing_a_missing_entry_is_a_404(db, user, client):
    import uuid

    res = client.get(f"/api/journal-entries/{uuid.uuid4()}/print")

    assert res.status_code == 404
