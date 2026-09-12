"""عملیاتِ ماژولِ فروش: قیمت‌گذاری، بستنِ فاکتور، پورسانت، اعلامیه.

قاعده‌هایی که این ماژول بدونشان خطرناک است: پیشنهادِ قیمت هرگز ردیفِ منفی نمی‌سازد،
فاکتورِ بسته دست‌نخوردنی است، پورسانت ذخیره می‌شود نه زنده، و اعلامیه در دفتر
می‌نشیند وگرنه صورت‌حسابِ طرف مقابل با دفتر نمی‌خواند.
"""
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.accounting import JournalEntry, JournalLine
from app.models.analytic import AnalyticAccount
from app.models.advanced_inventory import PriceList, PriceListItem
from app.models.inventory import Contact, Item, Warehouse
from app.models.invoices import SalesInvoice
from app.models.sales_ops import (
    CommissionRule,
    CreditDebitNote,
    DiscountItemGroup,
    DiscountItemGroupMember,
    PricingFactor,
)
from app.services import chart_codes as cc
from app.services import sales_ops as svc
from app.services.common import get_account

TODAY = date(2026, 6, 15)


def _item(db, sku="P-1", name="کالای تست"):
    it = Item(sku=sku, name=name, sales_price=Decimal(0), average_cost=Decimal(0))
    db.add(it)
    db.flush()
    return it


def _price_list(db, user, item, price, *, on=TODAY, name="اعلامیه"):
    pl = PriceList(name=name, effective_from=on, created_by_id=user.id)
    pl.items = [PriceListItem(item_id=item.id, price=Decimal(price))]
    db.add(pl)
    db.flush()
    return pl


def _invoice(db, user, *, net=1_000_000, cost=600_000, day=TODAY, person=None):
    wh = db.query(Warehouse).first()
    inv = SalesInvoice(
        number=None,
        invoice_date=day,
        warehouse_id=wh.id,
        total_amount=Decimal(net),
        total_cost=Decimal(cost),
        salesperson_id=person.id if person else None,
        created_by_id=user.id,
    )
    db.add(inv)
    db.flush()
    return inv


# ───────────────────────── پیشنهادِ قیمت‌گذاری ─────────────────────────


def test_price_comes_from_the_latest_announcement_in_effect(db, user):
    """اعلامیه‌ی آینده نباید روی فاکتورِ امروز بنشیند."""
    it = _item(db)
    _price_list(db, user, it, 100, on=TODAY - timedelta(days=10), name="قدیمی")
    _price_list(db, user, it, 150, on=TODAY - timedelta(days=1), name="جاری")
    _price_list(db, user, it, 999, on=TODAY + timedelta(days=5), name="آینده")

    s = svc.suggest_pricing(db, it.id, Decimal(2), TODAY)
    assert s["unit_price"] == Decimal(150)
    assert s["gross"] == Decimal(300)


def test_markup_applies_before_discount(db, user):
    """تخفیف روی قیمتِ نهایی معنی می‌دهد، نه روی قیمتِ پیش از حمل و بسته‌بندی."""
    it = _item(db)
    _price_list(db, user, it, 1000)
    db.add(PricingFactor(name="حمل", kind="markup", mode="percent", value=Decimal(10), scope="all"))
    db.add(PricingFactor(name="تخفیف", kind="discount", mode="percent", value=Decimal(50), scope="all"))
    db.flush()

    s = svc.suggest_pricing(db, it.id, Decimal(1), TODAY)
    assert s["gross"] == Decimal(1100)          # ۱۰۰۰ + ۱۰٪
    assert s["discount"] == Decimal(550)        # ۵۰٪ از ۱۱۰۰، نه از ۱۰۰۰
    assert s["net"] == Decimal(550)


def test_discount_never_makes_the_line_negative(db, user):
    """دو تخفیفِ بزرگ روی هم نباید مبلغِ منفی بسازند."""
    it = _item(db)
    _price_list(db, user, it, 1000)
    for n in ("الف", "ب"):
        db.add(PricingFactor(name=n, kind="discount", mode="percent", value=Decimal(70), scope="all"))
    db.flush()

    s = svc.suggest_pricing(db, it.id, Decimal(1), TODAY)
    assert s["discount"] == Decimal(1000)
    assert s["net"] == Decimal(0)


def test_group_scoped_factor_only_hits_its_members(db, user):
    inside, outside = _item(db, "IN"), _item(db, "OUT")
    _price_list(db, user, inside, 1000, name="الف")
    pl = PriceList(name="ب", effective_from=TODAY, created_by_id=user.id)
    pl.items = [PriceListItem(item_id=outside.id, price=Decimal(1000))]
    db.add(pl)
    g = DiscountItemGroup(name="گروهِ ویژه")
    g.members = [DiscountItemGroupMember(item_id=inside.id)]
    db.add(g)
    db.flush()
    db.add(PricingFactor(name="ویژه", kind="discount", mode="percent", value=Decimal(20), scope="group", group_id=g.id))
    db.flush()

    assert svc.suggest_pricing(db, inside.id, Decimal(1), TODAY)["discount"] == Decimal(200)
    assert svc.suggest_pricing(db, outside.id, Decimal(1), TODAY)["discount"] == Decimal(0)


def test_expired_factor_is_ignored(db, user):
    it = _item(db)
    _price_list(db, user, it, 1000)
    db.add(PricingFactor(
        name="نوروزی", kind="discount", mode="percent", value=Decimal(30), scope="all",
        valid_from=TODAY - timedelta(days=30), valid_to=TODAY - timedelta(days=1),
    ))
    db.flush()
    assert svc.suggest_pricing(db, it.id, Decimal(1), TODAY)["discount"] == Decimal(0)


# ─────────────────────────── بستنِ فاکتور ───────────────────────────


def test_closing_marks_who_and_when(db, user):
    inv = _invoice(db, user)
    assert inv.closed_at is None

    out = svc.close_invoices(db, user, invoice_ids=[inv.id])
    db.refresh(inv)

    assert out["count"] == 1
    assert inv.closed_at is not None
    assert inv.closed_by_id == user.id


def test_a_closed_invoice_is_untouchable(db, user):
    inv = _invoice(db, user)
    svc.close_invoices(db, user, invoice_ids=[inv.id])

    with pytest.raises(HTTPException) as e:
        svc.assert_invoice_open(db, inv.id)
    assert e.value.status_code == 409


def test_closing_twice_finds_nothing_to_close(db, user):
    inv = _invoice(db, user)
    svc.close_invoices(db, user, invoice_ids=[inv.id])

    with pytest.raises(HTTPException) as e:
        svc.close_invoices(db, user, invoice_ids=[inv.id])
    assert e.value.status_code == 400


def test_a_voided_invoice_is_not_closed(db, user):
    """فاکتورِ باطل بسته نمی‌شود — بستنش یعنی وانمود کردنِ یک فروشِ قطعی."""
    from datetime import datetime, timezone

    inv = _invoice(db, user)
    inv.voided_at = datetime.now(timezone.utc)
    db.flush()

    with pytest.raises(HTTPException):
        svc.close_invoices(db, user, invoice_ids=[inv.id])


# ──────────────────────────── پورسانت ────────────────────────────


def test_commission_uses_net_or_profit_as_the_rule_says(db, user):
    db.add(CommissionRule(salesperson_id=user.id, rate=Decimal(10), basis="net"))
    db.flush()
    _invoice(db, user, net=1_000_000, cost=600_000, person=user)

    on_net = svc.preview_commission(db, TODAY, TODAY)
    assert on_net["rows"][0]["amount"] == Decimal(100_000)  # ۱۰٪ از خالص

    db.query(CommissionRule).filter(CommissionRule.salesperson_id == user.id).update({"basis": "profit"})
    db.flush()
    on_profit = svc.preview_commission(db, TODAY, TODAY)
    assert on_profit["rows"][0]["amount"] == Decimal(40_000)  # ۱۰٪ از سودِ ۴۰۰٬۰۰۰


def test_invoice_without_a_salesperson_earns_nobody_commission(db, user):
    db.add(CommissionRule(salesperson_id=user.id, rate=Decimal(10), basis="net"))
    db.flush()
    _invoice(db, user, person=None)

    assert svc.preview_commission(db, TODAY, TODAY)["rows"] == []


def test_a_voided_invoice_is_out_of_the_commission_base(db, user):
    from datetime import datetime, timezone

    db.add(CommissionRule(salesperson_id=user.id, rate=Decimal(10), basis="net"))
    db.flush()
    inv = _invoice(db, user, person=user)
    inv.voided_at = datetime.now(timezone.utc)
    db.flush()

    assert svc.preview_commission(db, TODAY, TODAY)["rows"] == []


def test_a_negative_margin_pays_zero_not_a_negative_commission(db, user):
    db.add(CommissionRule(salesperson_id=user.id, rate=Decimal(10), basis="profit"))
    db.flush()
    _invoice(db, user, net=500_000, cost=900_000, person=user)  # فروشِ زیان‌ده

    assert svc.preview_commission(db, TODAY, TODAY)["rows"][0]["amount"] == Decimal(0)


def test_a_saved_run_keeps_its_numbers_when_the_invoice_is_voided_later(db, user):
    """چرا محاسبه ذخیره می‌شود: عددی که پرداخت شده نباید بعداً عوض شود."""
    from datetime import datetime, timezone

    db.add(CommissionRule(salesperson_id=user.id, rate=Decimal(10), basis="net"))
    db.flush()
    inv = _invoice(db, user, net=1_000_000, person=user)

    run = svc.run_commission(db, user, TODAY, TODAY, "خردادِ ۱۴۰۵")
    assert run.total_amount == Decimal(100_000)

    inv.voided_at = datetime.now(timezone.utc)
    db.flush()
    db.refresh(run)

    assert run.total_amount == Decimal(100_000), "محاسبه‌ی ذخیره‌شده نباید با ابطالِ بعدی عوض شود"
    assert svc.preview_commission(db, TODAY, TODAY)["rows"] == []  # ولی محاسبه‌ی تازه صفر است


def test_a_run_with_nothing_to_pay_is_refused(db, user):
    with pytest.raises(HTTPException) as e:
        svc.run_commission(db, user, TODAY, TODAY)
    assert e.value.status_code == 400


# ─────────────────── اعلامیه‌ی بدهکار / بستانکار ────────────────────


def _contact(db, name="مشتریِ تست"):
    c = Contact(name=name, type="customer")
    db.add(c)
    db.flush()
    return c


def _balance(db, account_id) -> Decimal:
    rows = db.query(JournalLine.debit, JournalLine.credit).filter(JournalLine.account_id == account_id).all()
    return sum((Decimal(d) - Decimal(c) for d, c in rows), Decimal(0))


def _supplier(db, name="تأمین‌کننده‌ی تست"):
    c = Contact(name=name, type="supplier")
    db.add(c)
    db.flush()
    return c


def _analytic(db, user, code, name):
    row = AnalyticAccount(code=code, name=name, created_by_id=user.id)
    db.add(row)
    db.flush()
    return row


def _line(**kw):
    """ردیفِ اعلامیه به همان شکلی که اسکیما می‌دهد."""
    return SimpleNamespace(
        debit_contact_id=kw.get("debit_contact_id"),
        debit_account_id=kw.get("debit_account_id"),
        credit_contact_id=kw.get("credit_contact_id"),
        credit_account_id=kw.get("credit_account_id"),
        amount=Decimal(kw["amount"]),
        description=kw.get("description", ""),
    )


def test_a_notice_moves_one_balance_to_another_and_never_touches_revenue(db, user):
    """کارِ اصلیِ این سند — و چیزی که تا امروز نمی‌کرد.

    تا مهاجرتِ ۰۱۲۷ سمتِ دومِ هر اعلامیه **حسابِ فروش** بود، پس تعدیلِ مانده
    درآمد می‌ساخت و شکلِ صورتِ سود و زیان را با سندی عوض می‌کرد که هیچ فروشی در
    آن اتفاق نیفتاده بود.
    """
    customer, supplier = _contact(db), _supplier(db)
    ar = get_account(db, cc.ACCOUNTS_RECEIVABLE)
    ap = get_account(db, cc.ACCOUNTS_PAYABLE)
    revenue = get_account(db, cc.SALES_REVENUE)
    ar_before, ap_before, rev_before = _balance(db, ar.id), _balance(db, ap.id), _balance(db, revenue.id)

    note = svc.post_notice(
        db,
        user,
        note_date=TODAY,
        description="بابت تهاتر حساب",
        lines=[_line(debit_contact_id=supplier.id, credit_contact_id=customer.id, amount=20_000_000)],
    )

    assert note.journal_entry_id is not None
    assert _balance(db, ap.id) == ap_before + 20_000_000, "بدهیِ ما به تأمین‌کننده کم می‌شود"
    assert _balance(db, ar.id) == ar_before - 20_000_000, "طلبِ ما از مشتری کم می‌شود"
    assert _balance(db, revenue.id) == rev_before, "فروش دست نمی‌خورد"


def test_the_role_of_each_side_picks_its_account(db, user):
    """نقشِ طرف حساب، معینِ پیش‌فرض را تعیین می‌کند، نه نامِ فرم."""
    customer, supplier = _contact(db), _supplier(db)
    assert svc.default_account_for(db, customer).system_role == cc.ACCOUNTS_RECEIVABLE
    assert svc.default_account_for(db, supplier).system_role == cc.ACCOUNTS_PAYABLE


def test_a_supplier_cannot_sit_on_receivables(db, user):
    """تأمین‌کننده‌ای روی «دریافتنی» طلبی می‌سازد که وجود ندارد."""
    supplier, customer = _supplier(db), _contact(db)
    ar = get_account(db, cc.ACCOUNTS_RECEIVABLE)
    with pytest.raises(HTTPException) as e:
        svc.post_notice(
            db,
            user,
            note_date=TODAY,
            lines=[
                _line(
                    debit_contact_id=supplier.id,
                    debit_account_id=ar.id,
                    credit_contact_id=customer.id,
                    amount=1000,
                )
            ],
        )
    assert e.value.status_code == 400


def test_both_sides_carry_their_own_tafsili(db, user):
    """بدونِ تفصیلی، سندی که فقط برای مانده‌ی این دو نفر ساخته شده در حسابِ
    هیچ‌کدامشان نمی‌نشیند."""
    customer, supplier = _contact(db), _supplier(db)
    customer.analytic_id = _analytic(db, user, "9001", "تفصیلیِ مشتری").id
    supplier.analytic_id = _analytic(db, user, "9002", "تفصیلیِ تأمین‌کننده").id
    db.flush()

    note = svc.post_notice(
        db,
        user,
        note_date=TODAY,
        lines=[_line(debit_contact_id=supplier.id, credit_contact_id=customer.id, amount=5000)],
    )
    entry = db.query(JournalEntry).filter(JournalEntry.id == note.journal_entry_id).one()
    assert {line.analytic_id for line in entry.lines} == {customer.analytic_id, supplier.analytic_id}


def test_a_multi_line_notice_is_one_balanced_entry(db, user):
    """هر ردیف ذاتاً تراز است، پس سند هم — و یک سند، نه چند تا."""
    a, b = _contact(db, "الف"), _contact(db, "ب")
    supplier = _supplier(db)
    note = svc.post_notice(
        db,
        user,
        note_date=TODAY,
        lines=[
            _line(debit_contact_id=supplier.id, credit_contact_id=a.id, amount=1000),
            _line(debit_contact_id=supplier.id, credit_contact_id=b.id, amount=2500),
        ],
    )
    entry = db.query(JournalEntry).filter(JournalEntry.id == note.journal_entry_id).one()
    assert sum(Decimal(x.debit) for x in entry.lines) == sum(Decimal(x.credit) for x in entry.lines) == 3500
    assert Decimal(note.amount) == 3500, "جمعِ سربرگ باید جمعِ ردیف‌ها باشد"
    assert len(note.lines) == 2


def test_a_failing_line_takes_the_whole_notice_with_it(db, user):
    """سندی که نیمی از ردیف‌هایش در دفتر نشسته، بدتر از سندِ ثبت‌نشده است."""
    customer, supplier = _contact(db), _supplier(db)
    before = db.query(CreditDebitNote).count()
    with pytest.raises(HTTPException):
        svc.post_notice(
            db,
            user,
            note_date=TODAY,
            lines=[
                _line(debit_contact_id=supplier.id, credit_contact_id=customer.id, amount=1000),
                _line(debit_contact_id=supplier.id, credit_contact_id=customer.id, amount=0),
            ],
        )
    assert db.query(CreditDebitNote).count() == before


def test_a_notice_that_moves_nothing_is_refused(db, user):
    """همان حساب و همان تفصیلی در دو سمت یعنی سندی بی‌معنا."""
    customer = _contact(db)
    with pytest.raises(HTTPException):
        svc.post_notice(
            db,
            user,
            note_date=TODAY,
            lines=[_line(debit_contact_id=customer.id, credit_contact_id=customer.id, amount=1000)],
        )


def test_a_contact_can_offset_their_own_receivable_against_their_payable(db, user):
    """طرف‌حسابی که هم مشتری است هم تأمین‌کننده — رایج‌ترین تهاتر."""
    both = Contact(name="هم‌مشتری‌هم‌تأمین‌کننده", type="both")
    db.add(both)
    db.flush()
    ar, ap = get_account(db, cc.ACCOUNTS_RECEIVABLE), get_account(db, cc.ACCOUNTS_PAYABLE)
    ar_before, ap_before = _balance(db, ar.id), _balance(db, ap.id)

    svc.post_notice(
        db,
        user,
        note_date=TODAY,
        lines=[
            _line(
                debit_contact_id=both.id,
                debit_account_id=ap.id,
                credit_contact_id=both.id,
                credit_account_id=ar.id,
                amount=7000,
            )
        ],
    )
    assert _balance(db, ap.id) == ap_before + 7000
    assert _balance(db, ar.id) == ar_before - 7000


def test_notes_get_their_own_gapless_numbers(db, user):
    c, s = _contact(db), _supplier(db)
    first = svc.post_notice(
        db, user, note_date=TODAY, lines=[_line(debit_contact_id=s.id, credit_contact_id=c.id, amount=1000)]
    )
    second = svc.post_notice(
        db, user, note_date=TODAY, lines=[_line(debit_contact_id=s.id, credit_contact_id=c.id, amount=2000)]
    )
    assert second.number == first.number + 1


def test_voiding_a_note_reverses_its_entry_and_leaves_the_original(db, user):
    c, s = _contact(db), _supplier(db)
    ar, ap = get_account(db, cc.ACCOUNTS_RECEIVABLE), get_account(db, cc.ACCOUNTS_PAYABLE)
    ar_before, ap_before = _balance(db, ar.id), _balance(db, ap.id)
    note = svc.post_notice(
        db, user, note_date=TODAY, lines=[_line(debit_contact_id=s.id, credit_contact_id=c.id, amount=70_000)]
    )

    svc.void_note(db, user, note.id, "اشتباه ثبت شده بود")
    db.refresh(note)

    assert note.voided_at is not None
    assert _balance(db, ar.id) == ar_before, "معکوس باید اثر را دقیقاً صفر کند"
    assert _balance(db, ap.id) == ap_before
    assert db.query(CreditDebitNote).filter(CreditDebitNote.id == note.id).one() is not None


def test_a_note_cannot_be_voided_twice(db, user):
    c, s = _contact(db), _supplier(db)
    note = svc.post_notice(
        db, user, note_date=TODAY, lines=[_line(debit_contact_id=s.id, credit_contact_id=c.id, amount=500)]
    )
    svc.void_note(db, user, note.id, "بارِ اول")

    with pytest.raises(HTTPException) as e:
        svc.void_note(db, user, note.id, "بارِ دوم")
    assert e.value.status_code == 409


def test_a_zero_or_negative_note_is_refused(db, user):
    c, s = _contact(db), _supplier(db)
    for bad in (Decimal(0), Decimal(-5)):
        with pytest.raises(HTTPException):
            svc.post_notice(
                db,
                user,
                note_date=TODAY,
                lines=[_line(debit_contact_id=s.id, credit_contact_id=c.id, amount=bad)],
            )


def test_an_empty_notice_is_refused(db, user):
    with pytest.raises(HTTPException):
        svc.post_notice(db, user, note_date=TODAY, lines=[])


# ─────────────────── نامِ تکراری: ۴۰۹ نه ۵۰۰ ────────────────────


def test_duplicate_names_are_refused_cleanly_not_with_a_500(client):
    """قیدِ یکتا کار می‌کرد، ولی خطای خامش «خطای داخلی سرور» نشان می‌داد — هم
    ترسناک، هم بی‌فایده. این تست از یک آزمونِ زنده روی سرورِ محلی بیرون آمد."""
    cases = [
        ("/api/sales-ops/sale-types", {"name": "تکراری", "due_days": 0, "description": "", "is_active": True}),
        ("/api/sales-ops/discount-groups", {"name": "تکراری", "description": "", "is_active": True, "item_ids": []}),
        ("/api/sales-ops/price-announcements",
         {"name": "تکراری", "effective_from": TODAY.isoformat(), "notes": "", "is_active": True, "lines": []}),
    ]
    for path, body in cases:
        assert client.post(path, json=body).status_code == 201, path
        again = client.post(path, json=body)
        assert again.status_code == 409, f"{path} → {again.status_code}"
        assert "نام" in again.json()["detail"]


def test_renaming_onto_another_name_is_refused_but_keeping_your_own_is_fine(client):
    a = client.post("/api/sales-ops/sale-types",
                    json={"name": "الف", "due_days": 0, "description": "", "is_active": True}).json()
    client.post("/api/sales-ops/sale-types",
                json={"name": "ب", "due_days": 0, "description": "", "is_active": True})

    clash = client.patch(f"/api/sales-ops/sale-types/{a['id']}",
                         json={"name": "ب", "due_days": 0, "description": "", "is_active": True})
    assert clash.status_code == 409

    same = client.patch(f"/api/sales-ops/sale-types/{a['id']}",
                        json={"name": "الف", "due_days": 7, "description": "", "is_active": True})
    assert same.status_code == 200, "ویرایشِ خودش بدونِ تغییرِ نام نباید با خودش تصادم کند"
    assert same.json()["due_days"] == 7
