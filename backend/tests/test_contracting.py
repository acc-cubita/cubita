"""پیمانکاری — پیمان (فازِ ۱): ثبت، فهرست و گذارِ وضعیت."""
import uuid
from datetime import date

from app.models.contracting import Contract
from app.schemas.contracting import ContractIn
from app.services import contracting as service
from tests.factories import make_contact

TODAY = date(2026, 3, 15)


def _payload(contact_id, **extra) -> ContractIn:
    data = dict(
        contact_id=contact_id,
        subject="ساختِ سوله",
        total_amount=1_000_000_000,
        start_date=TODAY,
        retention_percent=10,
        advance_percent=20,
    )
    data.update(extra)
    return ContractIn(**data)


def test_create_contract_gets_a_number_and_draft_status(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id), user)

    assert contract.number == 1
    assert contract.status == "draft"
    assert contract.contact_name == contact.name


def test_numbers_are_sequential_per_tenant(db, user):
    contact = make_contact(db)
    first = service.create_contract(db, _payload(contact.id), user)
    second = service.create_contract(db, _payload(contact.id), user)
    assert second.number == first.number + 1


def test_end_date_before_start_date_is_rejected():
    try:
        ContractIn(
            contact_id=uuid.uuid4(), total_amount=1000,
            start_date=TODAY, end_date=date(2026, 1, 1),
        )
        assert False, "باید رد می‌شد"
    except ValueError:
        pass


def test_status_transition_follows_the_allowed_graph(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id), user)

    activated = service.change_contract_status(db, contract.id, "active", user)
    assert activated.status == "active"

    suspended = service.change_contract_status(db, contract.id, "suspended", user)
    assert suspended.status == "suspended"


def test_status_transition_rejects_illegal_jump(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id), user)

    try:
        service.change_contract_status(db, contract.id, "completed", user)
        assert False, "گذارِ draft→completed نباید مجاز باشد"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409


def test_terminal_status_has_no_further_transition(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id), user)
    service.change_contract_status(db, contract.id, "cancelled", user)

    try:
        service.change_contract_status(db, contract.id, "active", user)
        assert False, "cancelled نباید گذارِ دیگری داشته باشد"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409


# ─────────────────── اندپوینت‌ها: ثبت، idempotency، فهرست، فیلتر ───────────────────


def test_the_api_creates_lists_and_filters_contracts(client, db):
    contact = make_contact(db)
    body = {
        "contact_id": str(contact.id),
        "subject": "نصبِ خط تولید",
        "total_amount": 500_000_000,
        "start_date": TODAY.isoformat(),
        "retention_percent": 10,
        "advance_percent": 0,
    }
    headers = {"Idempotency-Key": f"contract-{uuid.uuid4()}"}

    first = client.post("/api/contracting/contracts", json=body, headers=headers)
    second = client.post("/api/contracting/contracts", json=body, headers=headers)

    assert first.status_code == 201, first.text
    assert second.json()["id"] == first.json()["id"]
    created = first.json()
    assert created["status"] == "draft"
    assert created["contact_name"] == contact.name

    listed = client.get("/api/contracting/contracts", params={"limit": 200}).json()["items"]
    assert created["id"] in {row["id"] for row in listed}

    by_status = client.get("/api/contracting/contracts", params={"status": "active"}).json()["items"]
    assert created["id"] not in {row["id"] for row in by_status}


def test_the_api_changes_status_and_rejects_illegal_transitions(client, db):
    contact = make_contact(db)
    created = client.post(
        "/api/contracting/contracts",
        json={
            "contact_id": str(contact.id),
            "total_amount": 100_000_000,
            "start_date": TODAY.isoformat(),
        },
    ).json()

    ok = client.patch(f"/api/contracting/contracts/{created['id']}/status", json={"status": "active"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "active"

    bad = client.patch(f"/api/contracting/contracts/{created['id']}/status", json={"status": "draft"})
    assert bad.status_code == 409
