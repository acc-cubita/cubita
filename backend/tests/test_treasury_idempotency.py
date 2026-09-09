"""ثبتِ دوباره‌ی دریافت/پرداخت نباید دو رکورد بسازد.

صفِ آفلاینِ موبایل وقتی پاسخ را نگیرد دوباره می‌فرستد — رفتارِ درستش همین است.
بدونِ کلیدِ idempotency، همان یک دریافت دو بار در دفتر می‌نشیند و هیچ خطایی هم
دیده نمی‌شود؛ فقط ترازِ نقد غلط می‌شود.
"""
from datetime import date

import pytest

from app.models.inventory import Contact
from app.models.treasury import TreasuryTransaction

MARK = "آزمونِ صفِ آفلاین"


@pytest.fixture()
def contact(db) -> Contact:
    c = Contact(name="مشتریِ آزمونِ خزانه", type="customer")
    db.add(c)
    db.flush()
    return c


def _payload(contact_id, amount=1_000_000) -> dict:
    return {
        "transaction_date": date.today().isoformat(),
        "contact_id": str(contact_id),
        "amount": str(amount),
        "method": "cash",
        "description": MARK,
    }


@pytest.mark.parametrize("kind", ["receipts", "payments"])
def test_the_same_key_records_once(client, db, contact, kind):
    body = _payload(contact.id)
    headers = {"Idempotency-Key": f"mobile-outbox-{kind}-1"}

    first = client.post(f"/api/treasury/{kind}", json=body, headers=headers)
    second = client.post(f"/api/treasury/{kind}", json=body, headers=headers)

    assert first.status_code == 201, first.text
    assert second.status_code in (200, 201), second.text
    # همان رکورد برمی‌گردد، نه یک رکوردِ تازه.
    assert first.json()["id"] == second.json()["id"]

    assert db.query(TreasuryTransaction).filter(TreasuryTransaction.description == MARK).count() == 1


@pytest.mark.parametrize("kind", ["receipts", "payments"])
def test_different_keys_record_separately(client, db, contact, kind):
    """دو تراکنشِ *واقعاً* متفاوت نباید به‌اشتباه یکی شمرده شوند."""
    body = _payload(contact.id)
    a = client.post(f"/api/treasury/{kind}", json=body, headers={"Idempotency-Key": f"{kind}-a"})
    b = client.post(f"/api/treasury/{kind}", json=body, headers={"Idempotency-Key": f"{kind}-b"})

    assert a.status_code == 201, a.text
    assert b.status_code == 201, b.text
    assert a.json()["id"] != b.json()["id"]


def test_without_a_key_it_still_works(client, contact):
    """نبودِ هدر نباید چیزی را بشکند — کلاینت‌های قدیمی هنوز کار می‌کنند."""
    res = client.post("/api/treasury/receipts", json=_payload(contact.id))
    assert res.status_code == 201, res.text
