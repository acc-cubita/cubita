"""ارتقای چک و بانک: ویرایشِ حساب بانکی (PATCH)."""
from app.models.accounting import Account
from app.models.banking import BankAccount


def _make_bank(db) -> BankAccount:
    gl = db.query(Account).filter(Account.is_group.is_(False)).first()
    b = BankAccount(name="بانک تست", bank_name="ملت", account_number="123", iban="IR00", gl_account_id=gl.id)
    db.add(b)
    db.flush()
    return b


def test_update_bank_account(db, user, client):
    b = _make_bank(db)
    r = client.patch(f"/api/bank-accounts/{b.id}", json={"name": "بانک نو", "account_number": "999", "is_active": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "بانک نو"
    assert body["account_number"] == "999"
    assert body["is_active"] is False
    assert body["bank_name"] == "ملت"  # دست‌نخورده


def test_update_bank_account_blank_name_rejected(db, user, client):
    b = _make_bank(db)
    assert client.patch(f"/api/bank-accounts/{b.id}", json={"name": "   "}).status_code == 422


def test_update_missing_bank_account(db, user, client):
    r = client.patch("/api/bank-accounts/00000000-0000-0000-0000-000000000000", json={"name": "x"})
    assert r.status_code == 404
