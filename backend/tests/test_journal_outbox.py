"""همان شناسه صف؛ پاسخ گم‌شده، ردشدن قطعی و داده قدیمی از هم متمایزند."""
from datetime import date
from uuid import uuid4

from app.models.accounting import JournalEntry
from app.models.idempotency import IdempotencyKey
from app.schemas.fiscal_year import FiscalYearIn
from app.services import chart_codes as cc
from app.services.common import get_account
from app.services.fiscal_year import create_year


def body(db):
    return {"entry_date": "2026-09-28", "description": "سند صف آزمایشی", "lines": [
        {"account_id": str(get_account(db, cc.CASH).id), "debit": 100, "credit": 0},
        {"account_id": str(get_account(db, cc.SALES_REVENUE).id), "debit": 0, "credit": 100},
    ]}


def check(client, key, payload):
    response = client.post("/api/journal-entries/outbox-status", json={"local_id": key, "payload": payload})
    assert response.status_code == 200, response.text
    return response.json()


def test_manual_journal_replay_is_idempotent(client, db):
    payload, key = body(db), str(uuid4())
    before = db.query(JournalEntry).count()
    first = client.post("/api/journal-entries", json=payload, headers={"Idempotency-Key": key})
    assert first.status_code == 201, first.text
    again = client.post("/api/journal-entries", json=payload, headers={"Idempotency-Key": key})
    assert again.status_code == 201, again.text
    assert again.json()["id"] == first.json()["id"]
    assert db.query(JournalEntry).count() == before + 1
    assert check(client, key, payload) == {"state": "synced", "server_id": first.json()["id"], "server_number": first.json()["number"]}


def test_different_payload_cannot_replace_registered_journal(client, db):
    payload, key = body(db), str(uuid4())
    first = client.post("/api/journal-entries", json=payload, headers={"Idempotency-Key": key})
    assert first.status_code == 201, first.text
    changed = {**payload, "description": "اصلاح غیرمجاز سند ثبت‌شده"}
    response = client.post("/api/journal-entries", json=changed, headers={"Idempotency-Key": key})
    assert response.status_code == 409
    assert check(client, key, changed)["server_id"] == first.json()["id"]
    assert client.get(f'/api/journal-entries/{first.json()["id"]}').json()["description"] == payload["description"]


def test_unsubmitted_document_is_editable_and_check_is_read_only(client, db):
    payload, key = body(db), str(uuid4())
    count = db.query(IdempotencyKey).count()
    assert check(client, key, payload) == {"state": "editable"}
    assert db.query(IdempotencyKey).count() == count


def test_legacy_identical_journal_is_ambiguous_not_assigned(client, db):
    payload = body(db)
    first = client.post("/api/journal-entries", json=payload)
    assert first.status_code == 201, first.text
    assert check(client, str(uuid4()), payload) == {"state": "ambiguous"}
    assert check(client, str(uuid4()), {**payload, "description": "سند دیگر"}) == {"state": "editable"}


def test_automatic_retry_of_unacknowledged_legacy_entry_cannot_duplicate_it(client, db):
    payload = body(db)
    assert client.post("/api/journal-entries", json=payload).status_code == 201
    count = db.query(JournalEntry).count()
    response = client.post("/api/journal-entries", json=payload, headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 409, response.text
    assert "نسخهٔ قدیمی" in response.json()["detail"]
    assert db.query(JournalEntry).count() == count


def test_identical_new_documents_with_distinct_keys_are_not_legacy_ambiguity(client, db):
    payload = body(db)
    first = client.post("/api/journal-entries", json=payload, headers={"Idempotency-Key": str(uuid4())})
    assert first.status_code == 201, first.text
    key = str(uuid4())
    assert check(client, key, payload) == {"state": "editable"}
    second = client.post("/api/journal-entries", json=payload, headers={"Idempotency-Key": key})
    assert second.status_code == 201, second.text
    assert second.json()["id"] != first.json()["id"]


def test_failed_date_can_be_fixed_with_same_key_after_rollback(client, db):
    create_year(db, FiscalYearIn(title="۱۴۰۵", start_date=date(2026, 3, 21), end_date=date(2027, 3, 20)))
    db.commit()  # فقط savepoint فیکسچر؛ outer transaction داده واقعی را لمس نمی‌کند.
    payload, key = {**body(db), "entry_date": "2025-07-08"}, str(uuid4())
    response = client.post("/api/journal-entries", json=payload, headers={"Idempotency-Key": key})
    assert response.status_code == 400, response.text
    assert "2025-07-08" not in response.json()["detail"]
    assert "۱۴۰۴" in response.json()["detail"]
    db.rollback()  # get_db تست override است؛ rollback خطای HTTP را مثل production اعمال می‌کنیم.
    assert check(client, key, payload) == {"state": "editable"}
    payload["entry_date"] = "2026-09-28"
    fixed = client.post("/api/journal-entries", json=payload, headers={"Idempotency-Key": key})
    assert fixed.status_code == 201, fixed.text
    assert check(client, key, payload)["state"] == "synced"


def test_status_requires_create_permission(client, db):
    from app.main import app
    from app.deps import get_principal
    principal = app.dependency_overrides[get_principal]()
    principal.permissions = {"accounting": ["view"]}
    response = client.post("/api/journal-entries/outbox-status", json={"local_id": str(uuid4()), "payload": body(db)})
    assert response.status_code == 403


def test_status_cannot_see_another_tenant_key_or_matching_entry(client, db, tenant_id):
    from app.schemas.accounting import JournalEntryIn
    from app.services.journal_outbox import outbox_status
    from app.tenant_context import bind_session_tenant, apply_tenant_to_transaction
    payload, key = body(db), str(uuid4())
    first = client.post("/api/journal-entries", json=payload, headers={"Idempotency-Key": key})
    assert first.status_code == 201, first.text
    foreign = uuid4()
    try:
        db.expire_all()
        bind_session_tenant(db, foreign)
        apply_tenant_to_transaction(db, foreign)
        assert outbox_status(db, key, JournalEntryIn(**payload)) == {"state": "editable"}
        assert db.query(IdempotencyKey).filter(IdempotencyKey.key == key).count() == 0
    finally:
        bind_session_tenant(db, tenant_id)
        apply_tenant_to_transaction(db, tenant_id)
        db.expire_all()
