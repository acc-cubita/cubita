"""پشتیبان‌گیری/بازیابیِ کاملِ کسب‌وکار.

مهم‌ترین سنجه: round-trip روی اسکیمای واقعیِ Postgres — export ← wipe+restore ← export
باید داده را بی‌کم‌وکاست برگرداند. این ترتیبِ کلیدِ خارجی (والد پیش از فرزند)،
سلسله‌مراتبِ خودارجاعِ چارتِ حساب، پاک‌شدنِ دفترِ حسابرسیِ فقط‌افزودنی، و رفت‌وبرگشتِ
نوعِ داده (UUID/Decimal/تاریخ) را همه با هم می‌سنجد.
"""
from datetime import date


def _two_leaves(db):
    from app.models.accounting import Account

    rows = db.query(Account).filter(Account.is_group.is_(False)).order_by(Account.code).limit(2).all()
    return rows[0], rows[1]


def _seed_some_data(db, client):
    """چند ردیفِ واقعی می‌سازد تا پشتیبان چیزی برای برگرداندن داشته باشد."""
    from app.models.accounting import Account

    grp = db.query(Account).filter(Account.is_group.is_(True)).order_by(Account.code).first()
    # حسابِ تازه زیرِ یک سرفصل → خودارجاعِ parent_id را می‌سنجد
    client.post("/api/accounts", json={
        "code": "BK-9001", "name": "حسابِ پشتیبان", "type": grp.type, "parent_id": str(grp.id),
    })
    # سندِ دستی → journal_entry + journal_lines + رکوردِ audit_log (فقط‌افزودنی)
    a1, a2 = _two_leaves(db)
    r = client.post("/api/journal-entries", json={
        "entry_date": date.today().isoformat(),
        "description": "سندِ آزمایشِ پشتیبان",
        "lines": [
            {"account_id": str(a1.id), "debit": 12345, "credit": 0},
            {"account_id": str(a2.id), "debit": 0, "credit": 12345},
        ],
    })
    assert r.status_code == 201, r.text


def _counts(export: dict) -> dict:
    return {name: len(rows) for name, rows in export["tables"].items() if rows}


def test_export_shape_and_owner_only(db, user, client):
    r = client.get("/api/backup/export")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["format"] == "cubita-backup"
    assert "tables" in body and isinstance(body["tables"], dict)
    # چارتِ حساب seed‌شده باید در خروجی باشد
    assert body["tables"].get("accounts"), "accounts باید در پشتیبان باشد"


def test_invalid_payload_rejected(db, user, client):
    assert client.post("/api/backup/import", json={"nope": 1}).status_code == 400
    assert client.post("/api/backup/import", json={"format": "cubita-backup"}).status_code == 400


def test_roundtrip_replace_preserves_everything(db, user, client):
    _seed_some_data(db, client)

    before = client.get("/api/backup/export").json()
    before_counts = _counts(before)
    # اطمینان از اینکه داده‌ی معنادار داریم
    assert before_counts.get("accounts", 0) >= 1
    assert before_counts.get("journal_entries", 0) >= 1
    assert before_counts.get("journal_lines", 0) >= 2
    assert before_counts.get("audit_log", 0) >= 1

    # بازیابی روی همان کسب‌وکار: باید بی‌خطا پاک و دوباره درج کند (ترتیبِ FK/خودارجاع)
    imp = client.post("/api/backup/import", json=before)
    assert imp.status_code == 200, imp.text
    assert imp.json()["restored"] is True

    after = client.get("/api/backup/export").json()
    after_counts = _counts(after)
    assert after_counts == before_counts, f"شمارشِ ردیف‌ها پس از بازیابی فرق کرد: {before_counts} != {after_counts}"

    # محتوای یک جدولِ کلیدی هم عیناً برگردد (مقایسه‌ی بی‌ترتیب)
    def _norm(rows):
        return sorted((tuple(sorted(r.items(), key=lambda kv: kv[0])) for r in rows))
    assert _norm(after["tables"]["accounts"]) == _norm(before["tables"]["accounts"])
    assert _norm(after["tables"]["journal_lines"]) == _norm(before["tables"]["journal_lines"])


def test_restore_wipes_extra_rows(db, user, client):
    """اگر بعد از گرفتنِ پشتیبان چیزی اضافه شود، بازیابی باید آن را پاک کند (جایگزینیِ کامل)."""
    base = client.get("/api/backup/export").json()
    base_accounts = len(base["tables"].get("accounts", []))

    grp_type = base["tables"]["accounts"][0]["type"]
    grp_id = next(r["id"] for r in base["tables"]["accounts"] if r["is_group"])
    # کد باید با قاعده‌ی کدینگِ چارت جور باشد؛ از خودِ سرویس گرفته می‌شود.
    free = client.get(f"/api/accounts/next-code?parent_id={grp_id}").json()["code"]
    add = client.post("/api/accounts", json={
        "code": free, "name": "اضافه", "type": grp_type, "parent_id": grp_id,
    })
    assert add.status_code == 201, add.text
    assert len(client.get("/api/backup/export").json()["tables"]["accounts"]) == base_accounts + 1

    # بازیابیِ نسخه‌ی قبلی → ردیفِ اضافه باید برود
    assert client.post("/api/backup/import", json=base).status_code == 200
    assert len(client.get("/api/backup/export").json()["tables"]["accounts"]) == base_accounts


def test_restore_pre_registry_item_creates_base_membership(db, user, client, monkeypatch):
    from tests.factories import make_item
    from app.routers import backup as backup_router

    # Isolate the full item restore from the existing cloud broker preservation.
    monkeypatch.setattr(backup_router, "_skip_tables", lambda: {"roles"})

    item = make_item(db, unit="واحد قدیمی")
    item_id = str(item.id)
    backup = client.get("/api/backup/export").json()
    backup["tables"]["items"][0]["primary_unit_id"] = None
    backup["tables"]["item_units"] = []
    backup["tables"]["item_unit_conversions"] = []
    backup["tables"]["units_of_measure"] = []
    response = client.post("/api/backup/import", json=backup)
    assert response.status_code == 200, response.text
    restored = client.get("/api/backup/export").json()["tables"]
    row = next(row for row in restored["items"] if row["id"] == item_id)
    assert row["primary_unit_id"]
    assert row["unit"] == "واحد قدیمی"
    assert any(member["item_id"] == item_id and member["unit_id"] == row["primary_unit_id"]
               for member in restored["item_units"])


def test_invalid_backup_base_rejected_before_replace(db, user, client, monkeypatch):
    from tests.factories import make_item
    from app.routers import backup as backup_router

    monkeypatch.setattr(backup_router, "_skip_tables", lambda: {"roles"})

    make_item(db)
    backup = client.get("/api/backup/export").json()
    before = _counts(backup)
    backup["tables"]["item_units"][0]["inventory_allowed"] = False
    response = client.post("/api/backup/import", json=backup)
    assert response.status_code == 400, response.text
    assert _counts(client.get("/api/backup/export").json()) == before


def test_restore_preserves_registry_of_broker_preserved_items(db, user, client):
    from tests.factories import make_item
    from app.models.item_units import ItemUnit

    item = make_item(db, unit="واحد حفظ‌شده")
    item_id, unit_id = item.id, item.primary_unit_id
    backup = client.get("/api/backup/export").json()
    # Current broker references deliberately keep items outside tenant replace.
    assert "items" not in backup["tables"]
    assert "item_units" not in backup["tables"]
    response = client.post("/api/backup/import", json=backup)
    assert response.status_code == 200, response.text
    assert db.query(ItemUnit).filter_by(item_id=item_id, unit_id=unit_id).count() == 1
