"""ارتقای حسابداری: چارت حساب‌های قابلِ مدیریت + ابطالِ سندِ دستی."""
from datetime import date

from app.models.accounting import Account, JournalEntry


def _a_group(db) -> Account:
    return db.query(Account).filter(Account.is_group.is_(True)).order_by(Account.code).first()


def _two_leaves(db):
    rows = db.query(Account).filter(Account.is_group.is_(False)).order_by(Account.code).limit(2).all()
    return rows[0], rows[1]


# ── ساختِ حساب ───────────────────────────────────────────────────────────
def test_create_account_under_group(db, user, client):
    grp = _a_group(db)
    res = client.post("/api/accounts", json={
        "code": _free_code(client, grp), "name": "حسابِ آزمایشی", "type": grp.type, "parent_id": str(grp.id),
    })
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "حسابِ آزمایشی"
    assert body["is_active"] is True
    assert body["system_role"] is None
    assert body["parent_id"] == str(grp.id)


def _free_code(client, parent) -> str:
    """کدِ آزادِ بعدی طبقِ قاعده‌ی کدینگ — تست نباید کدِ دلخواه بسازد."""
    return client.get(f"/api/accounts/next-code?parent_id={parent.id}").json()["code"]


def test_create_type_must_match_parent(db, user, client):
    grp = _a_group(db)
    wrong = "income" if grp.type != "income" else "asset"
    res = client.post("/api/accounts", json={
        "code": _free_code(client, grp), "name": "x", "type": wrong, "parent_id": str(grp.id),
    })
    assert res.status_code == 400


def test_create_parent_must_be_group(db, user, client):
    leaf, _ = _two_leaves(db)
    res = client.post("/api/accounts", json={
        "code": _free_code(client, leaf), "name": "x", "type": leaf.type, "parent_id": str(leaf.id),
    })
    assert res.status_code == 400


def test_duplicate_code_rejected(db, user, client):
    grp = _a_group(db)
    p = {"code": _free_code(client, grp), "name": "x", "type": grp.type, "parent_id": str(grp.id)}
    assert client.post("/api/accounts", json=p).status_code == 201
    assert client.post("/api/accounts", json=p).status_code == 409


# ── ویرایش / غیرفعال‌سازی ────────────────────────────────────────────────
def test_rename_and_deactivate(db, user, client):
    grp = _a_group(db)
    aid = client.post("/api/accounts", json={"code": _free_code(client, grp), "name": "قدیمی", "type": grp.type, "parent_id": str(grp.id)}).json()["id"]
    r = client.patch(f"/api/accounts/{aid}", json={"name": "نو", "is_active": False})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "نو"
    assert r.json()["is_active"] is False


def test_cannot_deactivate_system_account(db, user, client):
    # یک حسابِ نقش‌دار می‌سازیم و تلاش می‌کنیم غیرفعالش کنیم
    sys = Account(code="SYS-1", name="صندوقِ سیستمی", type="asset", system_role="test_cash")
    db.add(sys)
    db.flush()
    r = client.patch(f"/api/accounts/{sys.id}", json={"is_active": False})
    assert r.status_code == 409


# ── حذف ──────────────────────────────────────────────────────────────────
def test_delete_unused_account(db, user, client):
    grp = _a_group(db)
    aid = client.post("/api/accounts", json={"code": _free_code(client, grp), "name": "بی‌استفاده", "type": grp.type, "parent_id": str(grp.id)}).json()["id"]
    assert client.delete(f"/api/accounts/{aid}").status_code == 204


def test_cannot_delete_account_with_entries(db, user, client):
    a1, a2 = _two_leaves(db)
    grp = _a_group(db)
    aid = client.post("/api/accounts", json={"code": _free_code(client, grp), "name": "دارای‌سند", "type": grp.type, "parent_id": str(grp.id)}).json()["id"]
    # سندی که این حساب را به کار می‌برد
    r = client.post("/api/journal-entries", json={
        "entry_date": date.today().isoformat(),
        "description": "آزمایش",
        "lines": [
            {"account_id": aid, "debit": 1000, "credit": 0},
            {"account_id": str(a1.id), "debit": 0, "credit": 1000},
        ],
    })
    assert r.status_code == 201, r.text
    assert client.delete(f"/api/accounts/{aid}").status_code == 409


def test_cannot_delete_system_account(db, user, client):
    sys = Account(code="SYS-2", name="نقشِ سیستمی", type="asset", system_role="test_role2")
    db.add(sys)
    db.flush()
    assert client.delete(f"/api/accounts/{sys.id}").status_code == 409


def test_cannot_delete_group_with_children(db, user, client):
    grp = _a_group(db)
    child = client.post("/api/accounts", json={"code": _free_code(client, grp), "name": "بچه", "type": grp.type, "parent_id": str(grp.id)}).json()
    assert client.delete(f"/api/accounts/{grp.id}").status_code == 409  # سرفصل زیرحساب دارد
    client.delete(f"/api/accounts/{child['id']}")  # پاک‌سازی


# ── ابطالِ سندِ دستی ─────────────────────────────────────────────────────
def test_void_manual_entry(db, user, client):
    a1, a2 = _two_leaves(db)
    entry = client.post("/api/journal-entries", json={
        "entry_date": date.today().isoformat(),
        "description": "سندِ دستی",
        "lines": [
            {"account_id": str(a1.id), "debit": 5000, "credit": 0},
            {"account_id": str(a2.id), "debit": 0, "credit": 5000},
        ],
    }).json()
    r = client.post(f"/api/journal-entries/{entry['id']}/void", json={"reason": "اشتباه در ثبت"})
    assert r.status_code == 200, r.text
    assert r.json()["reversal_entry_id"]
    # سندِ اصلی حالا باطل است
    db.expire_all()
    original = db.get(JournalEntry, entry["id"])
    assert original.voided_at is not None


def test_void_requires_reason(db, user, client):
    a1, a2 = _two_leaves(db)
    entry = client.post("/api/journal-entries", json={
        "entry_date": date.today().isoformat(),
        "description": "x",
        "lines": [
            {"account_id": str(a1.id), "debit": 100, "credit": 0},
            {"account_id": str(a2.id), "debit": 0, "credit": 100},
        ],
    }).json()
    assert client.post(f"/api/journal-entries/{entry['id']}/void", json={"reason": ".."}).status_code == 422


def test_cannot_void_twice(db, user, client):
    a1, a2 = _two_leaves(db)
    entry = client.post("/api/journal-entries", json={
        "entry_date": date.today().isoformat(),
        "description": "x",
        "lines": [
            {"account_id": str(a1.id), "debit": 200, "credit": 0},
            {"account_id": str(a2.id), "debit": 0, "credit": 200},
        ],
    }).json()
    assert client.post(f"/api/journal-entries/{entry['id']}/void", json={"reason": "دلیلِ کافی"}).status_code == 200
    assert client.post(f"/api/journal-entries/{entry['id']}/void", json={"reason": "دوباره"}).status_code == 409
