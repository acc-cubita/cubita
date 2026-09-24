"""فهرستِ اسناد با همان فیلترهای دفتر و تراز — و جمعی که مالِ کلِ دامنه است.

دفتر روزنامه تا امروز چهار ایراد داشت. دوتایش سمتِ سرور بود:

* `list_entries` فقط تاریخ و وضعیت و منشأ را می‌شناخت. شماره‌ی سند، مرکز هزینه و
  تفصیلی در دفتر و تراز بودند ولی در فهرستِ اسناد نه، پس روزنامه نمی‌توانست بر
  اساسشان فیلتر شود.
* هیچ جمعِ سمتِ سروری نبود. روزنامه جمعِ ۲۰۰ سندِ بارگذاری‌شده را «جمعِ گردشِ بازه»
  می‌نامید.

**مهم‌ترین تستِ این فایل** تطبیقِ جمعِ فهرست با `get_balances` زیرِ یک فیلتر است:
اگر فهرستِ اسناد نسخه‌ی دومی از فیلترها ساخته بود، همان‌جا لو می‌رفت.

هر تست مرکز هزینه، تفصیلی یا محدوده‌ی شماره‌ی خودش را دارد تا عددهایش به داده‌ی
تست‌های دیگر وابسته نباشد.
"""
from decimal import Decimal
from uuid import uuid4

from app.pagination import PageParams
from app.routers.journal import list_entries, list_summary
from app.services import accounting_ops as ops
from app.services.reports import ReportFilters

from tests.test_report_filters import EARLY, LATE, MID, _account, _analytic, _center, _post


def _page(db, filters: ReportFilters, *, limit: int = 200, cursor: str | None = None, q: str | None = None):
    return list_entries(filters=filters, q=q, db=db, params=PageParams(limit=limit, cursor=cursor))


def _summary(db, filters: ReportFilters, q: str | None = None):
    return list_summary(filters=filters, q=q, db=db)


def _code() -> str:
    return f"J{uuid4().hex[:7]}"


def test_number_range_keeps_only_the_entries_inside_it(db, user):
    first = _post(db, user, EARLY, 1_000)
    second = _post(db, user, MID, 2_000)
    third = _post(db, user, LATE, 4_000)

    scope = ReportFilters(entry_from=second.number, entry_to=third.number)
    page = _page(db, scope)
    summary = _summary(db, scope)

    assert sorted(e.number for e in page.items) == [second.number, third.number]
    assert first.number not in {e.number for e in page.items}
    assert summary.entry_count == 2
    #: هر سند یک ردیفِ بدهکار و یک ردیفِ بستانکار دارد، و بی فیلترِ ردیفی هر دو شمرده می‌شوند.
    assert summary.line_count == 4
    assert summary.total_debit == summary.total_credit == Decimal(6_000)


def test_date_and_number_range_combine(db, user):
    """§۷۵: بازه‌ی تاریخ و بازه‌ی شماره با هم، نه یکی به‌جای دیگری."""
    first = _post(db, user, EARLY, 1_000)
    second = _post(db, user, MID, 2_000)
    third = _post(db, user, LATE, 4_000)

    scope = ReportFilters(date_from=MID, entry_from=first.number, entry_to=third.number)

    assert sorted(e.number for e in _page(db, scope).items) == [second.number, third.number]
    assert _summary(db, scope).entry_count == 2


def test_cost_center_brings_the_whole_entry_but_sums_only_its_lines(db, user):
    """سند کامل نشان داده می‌شود، همان‌طور که ثبت شده. ولی جمع فقط ردیف‌های آن مرکز است.

    ردیفِ بستانکارِ `_post` مرکز ندارد. اگر جمع از ردیف‌های سند ساخته می‌شد، بستانکار
    هم ۵٬۰۰۰ می‌شد و با گزارش مرکز هزینه نمی‌خواند.
    """
    center = _center(db, user, _code(), "مرکزِ روزنامه")
    entry = _post(db, user, MID, 5_000, center=center)
    _post(db, user, MID, 9_000)  # بی مرکز؛ نباید بیاید

    scope = ReportFilters(cost_center_id=center.id)
    page = _page(db, scope)
    summary = _summary(db, scope)

    assert [e.id for e in page.items] == [entry.id]
    assert len(page.items[0].lines) == 2
    assert (summary.entry_count, summary.line_count) == (1, 1)
    assert (summary.total_debit, summary.total_credit) == (Decimal(5_000), Decimal(0))


def test_a_parent_cost_center_includes_its_children(db, user):
    """همان قاعده‌ی دفتر و تراز: گزارشِ «شعبه» پروژه‌های زیرش را هم می‌آورد."""
    parent = _center(db, user, _code(), "شعبه")
    child = _center(db, user, _code(), "پروژه", parent=parent)
    entry = _post(db, user, MID, 3_000, center=child)

    scope = ReportFilters(cost_center_id=parent.id)

    assert [e.id for e in _page(db, scope).items] == [entry.id]
    assert _summary(db, scope).total_debit == Decimal(3_000)


def test_analytic_filter(db, user):
    analytic = _analytic(db, user, _code(), "شرکتِ الف")
    entry = _post(db, user, MID, 7_000, analytic=analytic)
    _post(db, user, MID, 7_000)

    scope = ReportFilters(analytic_id=analytic.id)
    summary = _summary(db, scope)

    assert [e.id for e in _page(db, scope).items] == [entry.id]
    assert (summary.line_count, summary.total_debit) == (1, Decimal(7_000))


def test_status_filter(db, user):
    temporary = _post(db, user, MID, 1_000)
    permanent = _post(db, user, MID, 1_000, status="permanent")
    span = dict(entry_from=temporary.number, entry_to=permanent.number)

    assert [e.id for e in _page(db, ReportFilters(status="permanent", **span)).items] == [permanent.id]
    assert [e.id for e in _page(db, ReportFilters(status="temporary", **span)).items] == [temporary.id]


def test_system_entries_can_be_left_out(db, user):
    """چک‌باکسِ «اسنادِ افتتاحیه و اختتامیه» در نوارِ فیلتر حالا به روزنامه هم می‌رسد."""
    regular = _post(db, user, MID, 1_000)
    opening = _post(db, user, MID, 1_000, source="opening")
    span = dict(entry_from=regular.number, entry_to=opening.number)

    assert {e.id for e in _page(db, ReportFilters(**span)).items} == {regular.id, opening.id}
    without = ReportFilters(include_system_entries=False, **span)
    assert [e.id for e in _page(db, without).items] == [regular.id]
    assert _summary(db, without).entry_count == 1


def test_the_summary_covers_every_page_not_just_the_first(db, user):
    """**باگِ اصلی.** روزنامه جمعِ همان سندهایی را می‌گفت که بارگذاری کرده بود."""
    center = _center(db, user, _code(), "چندصفحه‌ای")
    for amount in (1_000, 2_000, 3_000):
        _post(db, user, MID, amount, center=center)
    scope = ReportFilters(cost_center_id=center.id)

    first = _page(db, scope, limit=2)
    rest = _page(db, scope, limit=2, cursor=first.next_cursor)
    summary = _summary(db, scope)

    assert len(first.items) == 2 and first.next_cursor is not None
    assert len(rest.items) == 1 and rest.next_cursor is None
    assert summary.entry_count == 3
    assert summary.total_debit == Decimal(6_000)


def test_the_summary_agrees_with_the_balances_report(db, user):
    """**مهم‌ترین تستِ این فایل.** دو مسیرِ مستقل زیرِ یک فیلتر، یک عدد.

    `get_balances` گردشِ دوره را حساب‌به‌حساب می‌دهد. جمعش باید همان جمعِ فهرستِ
    اسناد باشد. اگر فهرست فیلترها را جورِ دیگری می‌فهمید، این‌جا جدا می‌افتادند.
    """
    center = _center(db, user, _code(), "تطبیق")
    a, b = _account(db), _account(db)
    _post(db, user, EARLY, 11_000, account=a, center=center)
    _post(db, user, MID, 13_000, account=b, center=center)
    _post(db, user, LATE, 17_000, account=a, center=center)  # بیرون از بازه

    scope = ReportFilters(date_from=EARLY, date_to=MID, cost_center_id=center.id)
    rows = ops.get_balances(db, scope.date_from, scope.date_to, scope)
    summary = _summary(db, scope)

    assert summary.total_debit == sum(Decimal(r["period_debit"]) for r in rows) == Decimal(24_000)
    assert summary.total_credit == sum(Decimal(r["period_credit"]) for r in rows)


def test_search_still_narrows_the_list_and_the_summary(db, user):
    center = _center(db, user, _code(), "جست‌وجو")
    entry = _post(db, user, MID, 2_000, center=center)
    _post(db, user, MID, 2_000, center=center)
    scope = ReportFilters(cost_center_id=center.id)

    assert [e.id for e in _page(db, scope, q=str(entry.number)).items] == [entry.id]
    assert _summary(db, scope, q=str(entry.number)).entry_count == 1


def test_the_http_contract_uses_the_report_filter_names(db, user, client):
    """نام‌ها همان `report_filters`اند، و `/summary` پیش از `/{entry_id}` می‌نشیند."""
    center = _center(db, user, _code(), "قرارداد")
    entry = _post(db, user, MID, 8_000, center=center)
    qs = f"entry_from={entry.number}&entry_to={entry.number}&cost_center_id={center.id}"

    listed = client.get(f"/api/journal-entries?{qs}")
    summary = client.get(f"/api/journal-entries/summary?{qs}")

    assert listed.status_code == 200, listed.text
    assert [e["id"] for e in listed.json()["items"]] == [str(entry.id)]
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert (body["entry_count"], body["line_count"]) == (1, 1)
    assert Decimal(body["total_debit"]) == Decimal(8_000)
