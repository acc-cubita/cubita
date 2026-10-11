"""ویرایشِ سند ثبت‌شده، قفل‌های مالی و تاریخچهٔ غیرقابل بازنویسی."""
from datetime import date

from app.audit import bind_session_actor
from app.models.accounting import JournalEntry
from app.models.audit import AuditLog
from app.services import chart_codes as cc
from app.services.common import get_account


def _create(client, db, *, status="temporary"):
    cash = get_account(db, cc.CASH)
    sales = get_account(db, cc.SALES_REVENUE)
    response = client.post("/api/journal-entries", json={
        "entry_date": "2026-06-15", "description": "قبل", "status": status,
        "lines": [
            {"account_id": str(cash.id), "debit": 1000, "credit": 0, "description": "بدهکار"},
            {"account_id": str(sales.id), "debit": 0, "credit": 1000, "description": "بستانکار"},
        ],
    })
    assert response.status_code == 201, response.text
    return response.json()


def _edit_payload(entry, *, amount=2000, reason="تصحیح مبلغ"):
    return {
        "entry_date": entry["entry_date"], "description": "بعد", "status": entry["status"],
        "sub_number": "اصلاح ۱", "expected_updated_at": entry["updated_at"], "reason": reason,
        "lines": [
            {"id": line["id"], "account_id": line["account_id"],
             "debit": amount if i == 0 else 0, "credit": 0 if i == 0 else amount,
             "description": line["description"]}
            for i, line in enumerate(entry["lines"])
        ],
    }


def test_edit_permanent_manual_entry_keeps_identity_and_records_each_revision(client, db, user):
    bind_session_actor(db, user)
    created = _create(client, db, status="permanent")
    first = client.put(f"/api/journal-entries/{created['id']}", json=_edit_payload(created))
    assert first.status_code == 200, first.text
    changed = first.json()
    assert changed["status"] == "permanent"
    assert changed["number"] == created["number"]
    assert changed["atf_number"] == created["atf_number"]
    assert [l["id"] for l in changed["lines"]] == [l["id"] for l in created["lines"]]
    assert changed["lines"][0]["debit"] == "2000"

    second = client.put(f"/api/journal-entries/{created['id']}", json=_edit_payload(changed, amount=3000, reason="بازبینی دوم"))
    assert second.status_code == 200, second.text
    history = client.get(f"/api/journal-entries/{created['id']}/history")
    assert history.status_code == 200, history.text
    items = history.json()["items"]
    assert len(items) == 2
    assert items[0]["changes"]["edit_reason"]["to"] == "بازبینی دوم"
    assert items[0]["changes"]["editor_name"]["to"] == user.name
    assert items[0]["actor_email"] == user.email
    assert items[0]["changes"]["lines"]["from"][0]["debit"] == "2000"
    assert items[0]["changes"]["lines"]["to"][0]["debit"] == "3000"
    assert items[1]["changes"]["lines"]["from"][0]["debit"] == "1000"
    assert db.query(AuditLog).filter(AuditLog.entity_id == created["id"], AuditLog.action == "update").count() == 2


def test_stale_revision_and_invalid_reason_leave_entry_untouched(client, db):
    created = _create(client, db)
    payload = _edit_payload(created)
    assert client.put(f"/api/journal-entries/{created['id']}", json=payload).status_code == 200
    stale = client.put(f"/api/journal-entries/{created['id']}", json=payload)
    assert stale.status_code == 409
    invalid = _edit_payload(client.get(f"/api/journal-entries/{created['id']}").json(), reason=" ")
    assert client.put(f"/api/journal-entries/{created['id']}", json=invalid).status_code == 422
    assert db.get(JournalEntry, created["id"]).description == "بعد"


def test_edit_rejects_system_and_closed_period(client, db, user):
    from app.models.period_close import FiscalPeriodClose

    created = _create(client, db)
    entry = db.get(JournalEntry, created["id"])
    entry.source_type = "sales_invoice"
    db.flush()
    assert client.put(f"/api/journal-entries/{created['id']}", json=_edit_payload(created)).status_code == 409
    assert client.patch(f"/api/journal-entries/{created['id']}/sub-number", json={"sub_number": "بدون مجوز"}).status_code == 409
    entry.source_type = "manual"
    db.flush()
    # قفل دوره روی تاریخِ اصلی هم اعمال می‌شود؛ تغییر تاریخ در payload دورش نمی‌زند.
    close = FiscalPeriodClose(closing_date=date(2026, 6, 15), net_profit=0,
                              journal_entry_id=entry.id, created_by_id=user.id)
    db.add(close)
    db.flush()
    payload = _edit_payload(client.get(f"/api/journal-entries/{created['id']}").json())
    payload["entry_date"] = "2026-06-16"
    assert client.put(f"/api/journal-entries/{created['id']}", json=payload).status_code == 400
    assert client.patch(f"/api/journal-entries/{created['id']}/sub-number", json={"sub_number": "دوره بسته"}).status_code == 400


def test_edit_adds_and_removes_lines_with_full_history(client, db):
    created = _create(client, db)
    cash = get_account(db, cc.CASH)
    sales = get_account(db, cc.SALES_REVENUE)
    payload = _edit_payload(created)
    payload["lines"] = [
        {"id": created["lines"][0]["id"], "account_id": str(cash.id),
         "debit": 2000, "credit": 0, "description": "بدهکار اصلاحی"},
        {"account_id": str(sales.id), "debit": 0, "credit": 2000,
         "description": "بستانکار تازه"},
    ]
    response = client.put(f"/api/journal-entries/{created['id']}", json=payload)
    assert response.status_code == 200, response.text
    changed = response.json()
    assert len(changed["lines"]) == 2
    assert changed["lines"][0]["id"] == created["lines"][0]["id"]
    assert changed["lines"][1]["id"] != created["lines"][1]["id"]
    history = client.get(f"/api/journal-entries/{created['id']}/history").json()["items"]
    assert history[0]["changes"]["lines"]["from"][1]["id"] == created["lines"][1]["id"]
    assert history[0]["changes"]["lines"]["to"][1]["id"] == changed["lines"][1]["id"]
    assert history[0]["changes"]["lines"]["to"][1]["account_name"]


def test_edit_cannot_move_open_entry_into_closed_period(client, db, user):
    from app.models.period_close import FiscalPeriodClose

    created = _create(client, db)
    close = FiscalPeriodClose(closing_date=date(2026, 6, 10), net_profit=0,
                              journal_entry_id=created["id"], created_by_id=user.id)
    db.add(close)
    db.flush()
    payload = _edit_payload(created)
    payload["entry_date"] = "2026-06-09"
    response = client.put(f"/api/journal-entries/{created['id']}", json=payload)
    assert response.status_code == 400, response.text
    assert db.get(JournalEntry, created["id"]).entry_date == date(2026, 6, 15)
