"""پیمانکاری — پیمان (فازِ ۱) و متممِ پیمان (فازِ ۲)."""
import uuid
from datetime import date

from app.models.contracting import Contract
from app.schemas.contracting import ContractAmendmentIn, ContractIn
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


# ─────────────────────────── متممِ پیمان (فازِ ۲) ───────────────────────────


def _amendment_payload(contract_id, **extra) -> ContractAmendmentIn:
    data = dict(
        contract_id=contract_id,
        date=TODAY,
        description="افزایشِ محدوده‌ی کار",
        amount_delta=50_000_000,
    )
    data.update(extra)
    return ContractAmendmentIn(**data)


def test_create_amendment_gets_a_number(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id), user)

    amendment = service.create_contract_amendment(db, _amendment_payload(contract.id), user)
    assert amendment.number == 1
    assert amendment.contract_number == contract.number


def test_amendment_numbers_are_sequential_and_independent_of_contract_numbers(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id), user)

    first = service.create_contract_amendment(db, _amendment_payload(contract.id), user)
    second = service.create_contract_amendment(db, _amendment_payload(contract.id), user)
    assert second.number == first.number + 1


def test_amendment_amount_delta_can_be_negative_and_leaves_contract_total_untouched(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id), user)
    original_total = contract.total_amount

    service.create_contract_amendment(db, _amendment_payload(contract.id, amount_delta=-20_000_000), user)
    db.refresh(contract)
    assert contract.total_amount == original_total


def test_amendment_new_end_date_updates_the_contract(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id, end_date=date(2026, 6, 1)), user)

    service.create_contract_amendment(
        db, _amendment_payload(contract.id, new_end_date=date(2026, 9, 1)), user,
    )
    db.refresh(contract)
    assert contract.end_date == date(2026, 9, 1)


def test_amendment_new_end_date_before_contract_start_is_rejected(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id), user)

    try:
        service.create_contract_amendment(
            db, _amendment_payload(contract.id, new_end_date=date(2020, 1, 1)), user,
        )
        assert False, "باید رد می‌شد"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400


def test_amendment_on_a_closed_contract_is_rejected(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id), user)
    service.change_contract_status(db, contract.id, "cancelled", user)

    try:
        service.create_contract_amendment(db, _amendment_payload(contract.id), user)
        assert False, "پیمانِ لغوشده نباید متمم بپذیرد"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409


def test_amendment_requires_a_description():
    try:
        ContractAmendmentIn(contract_id=uuid.uuid4(), date=TODAY, description="   ")
        assert False, "باید رد می‌شد"
    except ValueError:
        pass


def test_the_api_creates_and_lists_amendments_filtered_by_contract(client, db):
    contact = make_contact(db)
    contract = client.post(
        "/api/contracting/contracts",
        json={
            "contact_id": str(contact.id),
            "total_amount": 300_000_000,
            "start_date": TODAY.isoformat(),
        },
    ).json()
    other_contract = client.post(
        "/api/contracting/contracts",
        json={
            "contact_id": str(contact.id),
            "total_amount": 100_000_000,
            "start_date": TODAY.isoformat(),
        },
    ).json()

    body = {
        "contract_id": contract["id"],
        "date": TODAY.isoformat(),
        "description": "تمدیدِ زمان",
        "amount_delta": 10_000_000,
    }
    headers = {"Idempotency-Key": f"amendment-{uuid.uuid4()}"}
    first = client.post("/api/contracting/amendments", json=body, headers=headers)
    second = client.post("/api/contracting/amendments", json=body, headers=headers)
    assert first.status_code == 201, first.text
    assert second.json()["id"] == first.json()["id"]

    client.post(
        "/api/contracting/amendments",
        json={**body, "contract_id": other_contract["id"]},
        headers={"Idempotency-Key": f"amendment-{uuid.uuid4()}"},
    )

    filtered = client.get(
        "/api/contracting/amendments", params={"contract_id": contract["id"], "limit": 200},
    ).json()["items"]
    assert {row["id"] for row in filtered} == {first.json()["id"]}
