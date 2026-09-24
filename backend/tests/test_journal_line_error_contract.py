"""خطای ردیفِ سند: متنِ قدیمیِ detail پایدار، اندیسِ ساختاری افزوده."""
from datetime import date
from uuid import uuid4

import pytest

from app.models.tenant import Tenant
from app.routers.journal import JournalLineInputError, create_entry
from app.schemas.accounting import JournalEntryIn
from app.services import chart_codes as cc
from app.services.common import get_account
from app.tenant_context import session_tenant


def _payload(db):
    cash = get_account(db, cc.CASH)
    sales = get_account(db, cc.SALES_REVENUE)
    return cash, sales, {
        "entry_date": date(2026, 6, 15).isoformat(),
        "lines": [
            {"account_id": str(cash.id), "debit": 1000},
            {"account_id": str(sales.id), "credit": 1000},
        ],
    }


def test_tracking_error_keeps_detail_and_adds_line_index(db, client):
    _, sales, payload = _payload(db)
    sales.has_tracking = False
    db.flush()
    payload["lines"][1]["tracking_no"] = "R-1"

    response = client.post("/api/journal-entries", json=payload)

    assert response.status_code == 400
    assert isinstance(response.json()["detail"], str)
    assert "پیگیری نمی‌پذیرند" in response.json()["detail"]
    assert response.json()["line_errors"] == [
        {"index": 1, "field": "tracking_no", "message": "این حساب پیگیری نمی‌پذیرد."}
    ]


def test_required_tafsili_error_identifies_each_line(db, client):
    _, sales, payload = _payload(db)
    sales.accepts_tafsili = True
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = "hybrid"
    db.flush()

    response = client.post("/api/journal-entries", json=payload)

    assert response.status_code == 400
    assert "تفصیلی" in response.json()["detail"]
    assert response.json()["line_errors"] == [
        {"index": 1, "field": "analytic_id", "message": "تفصیلیِ این ردیف الزامی است."}
    ]


def test_invalid_line_center_is_indexed_but_header_error_stays_unchanged(db, client):
    _, _, payload = _payload(db)
    payload["lines"][1]["cost_center_id"] = str(uuid4())
    response = client.post("/api/journal-entries", json=payload)
    assert response.status_code == 400
    assert response.json()["line_errors"][0]["index"] == 1
    assert response.json()["line_errors"][0]["field"] == "cost_center_id"

    del payload["lines"][1]["cost_center_id"]
    payload["cost_center_id"] = str(uuid4())
    header_response = client.post("/api/journal-entries", json=payload)
    assert header_response.status_code == 400
    assert "line_errors" not in header_response.json()


def test_line_error_is_raised_not_returned_so_the_transaction_rolls_back(db, user):
    """**خطا = rollback.** `get_db` فقط وقتی rollback می‌کند که استثنا از روتر بیرون
    برود؛ روتری که پاسخِ ۴۰۰ را return کند، تراکنشِ همان درخواست را commit می‌کند.
    پس خودِ تابعِ روتر باید raise کند — پاسخِ `{detail, line_errors}` را
    `journal_line_error_handler` می‌سازد (تست‌های بالا همان را از بیرون می‌سنجند).
    """
    _, sales, payload = _payload(db)
    sales.has_tracking = False
    db.flush()
    payload["lines"][1]["tracking_no"] = "R-1"

    with pytest.raises(JournalLineInputError) as caught:
        create_entry(data=JournalEntryIn(**payload), db=db, user=user)

    assert caught.value.status_code == 400
    assert caught.value.line_errors == [
        {"index": 1, "field": "tracking_no", "message": "این حساب پیگیری نمی‌پذیرد."}
    ]
