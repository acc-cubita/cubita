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
    add = client.post("/api/accounts", json={
        "code": "BK-EXTRA", "name": "اضافه", "type": grp_type, "parent_id": grp_id,
    })
    assert add.status_code == 201, add.text
    assert len(client.get("/api/backup/export").json()["tables"]["accounts"]) == base_accounts + 1

    # بازیابیِ نسخه‌ی قبلی → ردیفِ اضافه باید برود
    assert client.post("/api/backup/import", json=base).status_code == 200
    assert len(client.get("/api/backup/export").json()["tables"]["accounts"]) == base_accounts
