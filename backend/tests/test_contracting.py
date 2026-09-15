"""پیمانکاری — پیمان (فازِ ۱)، متممِ پیمان (فازِ ۲)، صورت‌وضعیتِ دریافتی (فازِ ۳) و
تسویه‌حسابِ پیمان (فازِ ۴)."""
import uuid
from datetime import date
from decimal import Decimal

from app.models.accounting import Account, JournalEntry
from app.models.contracting import Contract
from app.schemas.contracting import (
    ContractAmendmentIn,
    ContractIn,
    ContractSettlementIn,
    ContractStatementIn,
)
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


# ────────────────────────── صورت‌وضعیتِ دریافتی (فازِ ۳) ──────────────────────────


def _statement_payload(contract_id, **extra) -> ContractStatementIn:
    data = dict(
        contract_id=contract_id,
        date=TODAY,
        gross_amount=1_000_000,
    )
    data.update(extra)
    return ContractStatementIn(**data)


def test_statement_computes_deductions_from_contract_percents(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id, retention_percent=10, advance_percent=20), user)

    statement = service.create_contract_statement(db, _statement_payload(contract.id), user)
    assert statement.number == 1
    assert statement.retention_amount == 100_000
    assert statement.advance_deduction == 200_000
    assert statement.net_amount == 700_000
    assert statement.contract_number == contract.number


def test_statement_other_deductions_reduce_net_amount(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id, retention_percent=10, advance_percent=20), user)

    statement = service.create_contract_statement(
        db, _statement_payload(contract.id, other_deductions=50_000), user,
    )
    assert statement.net_amount == 650_000


def test_statement_snapshots_contract_percents_at_creation_time(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id, retention_percent=10, advance_percent=20), user)

    first = service.create_contract_statement(db, _statement_payload(contract.id), user)

    # شبیه‌سازیِ تغییرِ بعدیِ درصدهای پیمان (امروز راهِ رسمی ندارد؛ اینجا مستقیم می‌زنیم)
    contract.retention_percent = 5
    db.flush()

    second = service.create_contract_statement(db, _statement_payload(contract.id), user)

    db.refresh(first)
    assert first.retention_percent == 10
    assert second.retention_percent == 5


def test_statement_requires_positive_gross_amount():
    try:
        ContractStatementIn(contract_id=uuid.uuid4(), date=TODAY, gross_amount=0)
        assert False, "باید رد می‌شد"
    except ValueError:
        pass


def test_statement_rejects_negative_other_deductions():
    try:
        ContractStatementIn(contract_id=uuid.uuid4(), date=TODAY, gross_amount=1000, other_deductions=-1)
        assert False, "باید رد می‌شد"
    except ValueError:
        pass


def test_statement_on_a_closed_contract_is_rejected(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id), user)
    service.change_contract_status(db, contract.id, "cancelled", user)

    try:
        service.create_contract_statement(db, _statement_payload(contract.id), user)
        assert False, "پیمانِ لغوشده نباید صورت‌وضعیت بپذیرد"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409


def test_the_api_creates_and_lists_statements_filtered_by_contract(client, db):
    contact = make_contact(db)
    contract = client.post(
        "/api/contracting/contracts",
        json={
            "contact_id": str(contact.id),
            "total_amount": 300_000_000,
            "start_date": TODAY.isoformat(),
            "retention_percent": 10,
            "advance_percent": 20,
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
        "gross_amount": 1_000_000,
    }
    headers = {"Idempotency-Key": f"statement-{uuid.uuid4()}"}
    first = client.post("/api/contracting/statements", json=body, headers=headers)
    second = client.post("/api/contracting/statements", json=body, headers=headers)
    assert first.status_code == 201, first.text
    assert second.json()["id"] == first.json()["id"]
    assert first.json()["net_amount"] == "700000"

    client.post(
        "/api/contracting/statements",
        json={**body, "contract_id": other_contract["id"]},
        headers={"Idempotency-Key": f"statement-{uuid.uuid4()}"},
    )

    filtered = client.get(
        "/api/contracting/statements", params={"contract_id": contract["id"], "limit": 200},
    ).json()["items"]
    assert {row["id"] for row in filtered} == {first.json()["id"]}


# ────────────────────────── تسویه‌حسابِ پیمان (فازِ ۴) ──────────────────────────


def test_settlement_sums_statements_and_posts_a_balanced_entry(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id, retention_percent=10, advance_percent=20), user)
    service.create_contract_statement(db, _statement_payload(contract.id, gross_amount=1_000_000), user)
    service.create_contract_statement(
        db, _statement_payload(contract.id, gross_amount=500_000, other_deductions=20_000), user,
    )

    settlement = service.create_contract_settlement(
        db, ContractSettlementIn(contract_id=contract.id, date=TODAY), user,
    )

    assert settlement.number == 1
    assert settlement.gross_amount == 1_500_000
    assert settlement.retention_amount == 150_000
    assert settlement.advance_amount == 300_000
    assert settlement.other_deductions == 20_000
    assert settlement.net_amount == 1_030_000
    assert settlement.contract_value_at_settlement == contract.total_amount
    assert settlement.journal_entry_id is not None

    entry = db.get(JournalEntry, settlement.journal_entry_id)
    assert entry is not None
    total_debit = sum(Decimal(line.debit) for line in entry.lines)
    total_credit = sum(Decimal(line.credit) for line in entry.lines)
    assert total_debit == total_credit == Decimal(1_500_000)


def test_settlement_creates_the_new_role_accounts_on_first_use(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id, retention_percent=10, advance_percent=20), user)
    service.create_contract_statement(db, _statement_payload(contract.id, gross_amount=1_000_000), user)

    service.create_contract_settlement(db, ContractSettlementIn(contract_id=contract.id, date=TODAY), user)

    for role in ("contract_revenue", "contract_retention_receivable", "contract_advance_received"):
        account = db.query(Account).filter(Account.system_role == role).one_or_none()
        assert account is not None, f"حسابِ نقش‌دارِ «{role}» ساخته نشد"


def test_settlement_includes_amendments_in_contract_value_snapshot(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id), user)
    service.create_contract_amendment(db, _amendment_payload(contract.id, amount_delta=200_000_000), user)
    service.create_contract_statement(db, _statement_payload(contract.id, gross_amount=1_000_000), user)

    settlement = service.create_contract_settlement(
        db, ContractSettlementIn(contract_id=contract.id, date=TODAY), user,
    )
    assert settlement.contract_value_at_settlement == contract.total_amount + 200_000_000


def test_settlement_requires_at_least_one_statement(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id), user)

    try:
        service.create_contract_settlement(db, ContractSettlementIn(contract_id=contract.id, date=TODAY), user)
        assert False, "باید رد می‌شد"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400


def test_settlement_rejects_a_second_active_settlement_for_the_same_contract(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id), user)
    service.create_contract_statement(db, _statement_payload(contract.id, gross_amount=1_000_000), user)
    service.create_contract_settlement(db, ContractSettlementIn(contract_id=contract.id, date=TODAY), user)

    try:
        service.create_contract_settlement(db, ContractSettlementIn(contract_id=contract.id, date=TODAY), user)
        assert False, "دومین تسویه‌حساب باید رد می‌شد"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409


def test_void_contract_settlement_reverses_the_journal_entry(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id, retention_percent=10, advance_percent=20), user)
    service.create_contract_statement(db, _statement_payload(contract.id, gross_amount=1_000_000), user)
    settlement = service.create_contract_settlement(
        db, ContractSettlementIn(contract_id=contract.id, date=TODAY), user,
    )
    original_entry_id = settlement.journal_entry_id

    voided = service.void_contract_settlement(db, user, settlement.id, "اشتباهِ ثبت")
    assert voided.voided_at is not None
    assert voided.void_reason == "اشتباهِ ثبت"

    reversal = (
        db.query(JournalEntry)
        .filter(JournalEntry.reverses_entry_id == original_entry_id)
        .one_or_none()
    )
    assert reversal is not None
    original = db.get(JournalEntry, original_entry_id)
    for orig_line, rev_line in zip(
        sorted(original.lines, key=lambda l: l.seq), sorted(reversal.lines, key=lambda l: l.seq),
    ):
        assert orig_line.debit == rev_line.credit
        assert orig_line.credit == rev_line.debit

    # پس از ابطال، پیمان دوباره می‌تواند تسویه شود
    resettled = service.create_contract_settlement(
        db, ContractSettlementIn(contract_id=contract.id, date=TODAY), user,
    )
    assert resettled.id != settlement.id


def test_void_contract_settlement_twice_is_rejected(db, user):
    contact = make_contact(db)
    contract = service.create_contract(db, _payload(contact.id), user)
    service.create_contract_statement(db, _statement_payload(contract.id, gross_amount=1_000_000), user)
    settlement = service.create_contract_settlement(
        db, ContractSettlementIn(contract_id=contract.id, date=TODAY), user,
    )
    service.void_contract_settlement(db, user, settlement.id, "اشتباه")

    try:
        service.void_contract_settlement(db, user, settlement.id, "دوباره")
        assert False, "باید رد می‌شد"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409


def test_the_api_creates_lists_and_voids_settlements(client, db):
    contact = make_contact(db)
    contract = client.post(
        "/api/contracting/contracts",
        json={
            "contact_id": str(contact.id),
            "total_amount": 300_000_000,
            "start_date": TODAY.isoformat(),
            "retention_percent": 10,
            "advance_percent": 20,
        },
    ).json()
    client.post(
        "/api/contracting/statements",
        json={"contract_id": contract["id"], "date": TODAY.isoformat(), "gross_amount": 1_000_000},
        headers={"Idempotency-Key": f"statement-{uuid.uuid4()}"},
    )

    body = {"contract_id": contract["id"], "date": TODAY.isoformat()}
    headers = {"Idempotency-Key": f"settlement-{uuid.uuid4()}"}
    first = client.post("/api/contracting/settlements", json=body, headers=headers)
    second = client.post("/api/contracting/settlements", json=body, headers=headers)
    assert first.status_code == 201, first.text
    assert second.json()["id"] == first.json()["id"]
    settlement = first.json()
    assert settlement["net_amount"] == "700000"

    listed = client.get(
        "/api/contracting/settlements", params={"contract_id": contract["id"], "limit": 200},
    ).json()["items"]
    assert {row["id"] for row in listed} == {settlement["id"]}

    voided = client.post(
        f"/api/contracting/settlements/{settlement['id']}/void", json={"reason": "اشتباهِ ثبت"},
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["voided_at"] is not None

    bad = client.post(
        f"/api/contracting/settlements/{settlement['id']}/void", json={"reason": "دوباره"},
    )
    assert bad.status_code == 409
