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


def test_create_tafsili_under_an_unposted_moin(db, user, client):
    """سطحِ چهارم: زیرِ حسابِ معینِ بی‌سند می‌شود تفصیلی ساخت («بانک ملی» زیرِ «بانک»).

    این تست سه بار عوض شده و هر بار دلیلش را نگه داشته‌ایم:

    ۱. اول عکسِ این را ادعا می‌کرد (۴۰۰) — درخت فقط زیرِ سرفصل رشد می‌کرد و کاربر
       راهی نداشت حسابِ بانکش را تفکیک کند.
    ۲. بعد شرطِ `accepts_tafsili` اضافه شد، به‌گمانِ اینکه همان «تفصیل‌پذیری»ِ
       سپیدار است.
    ۳. حالا آن شرط **برداشته شده**، چون دو چیزِ متفاوت را یکی گرفته بود. زیرشاخه‌ی
       درختی بخشی از کدینگِ چهارسطحیِ ایران است — کم‌تعداد، ثابت، و در خودِ کد.
       `accepts_tafsili` درباره‌ی تفصیلیِ *شناور* روی ردیفِ سند است، که بُعدی متغیر
       و پرتعداد است و اصلاً در کد نمی‌آید. قیدِ واقعیِ زیرشاخه همان «والد سندِ
       مستقیم نخورده باشد» است و تستِ بعدی نگهش می‌دارد.
    """
    leaf, _ = _two_leaves(db)
    assert leaf.accepts_tafsili is False, "و هیچ پرچمی هم لازم نیست"

    res = client.post("/api/accounts", json={
        "code": _free_code(client, leaf), "name": "تفصیلیِ آزمایشی", "type": leaf.type,
        "parent_id": str(leaf.id),
    })
    assert res.status_code == 201, res.text
    assert res.json()["parent_id"] == str(leaf.id)


def test_create_child_rejected_under_a_posted_account(db, user, client):
    """ولی حسابی که سندِ مستقیم خورده نه — مانده‌اش دو منبع پیدا می‌کند."""
    from datetime import date
    from decimal import Decimal

    from app.models.accounting import JournalEntry, JournalLine

    leaf, other = _two_leaves(db)
    entry = JournalEntry(entry_date=date(2026, 1, 1), description="آزمون", created_by_id=user.id)
    entry.lines = [
        JournalLine(account_id=leaf.id, debit=Decimal(1), credit=Decimal(0)),
        JournalLine(account_id=other.id, debit=Decimal(0), credit=Decimal(1)),
    ]
    db.add(entry)
    db.flush()

    res = client.post("/api/accounts", json={
        "code": _free_code(client, leaf), "name": "x", "type": leaf.type, "parent_id": str(leaf.id),
    })
    assert res.status_code == 409, res.text


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


def test_system_account_can_be_deactivated(db, user, client):
    """غیرفعال‌سازی برای هر حسابی مجاز است — حتی سیستمی.

    این تست پیش‌تر عکسش را ادعا می‌کرد (۴۰۹، با پیامِ «برای ثبتِ خودکار لازم است»).
    آن گارد بر فرضِ غلطی بنا شده بود: `get_account` اصلاً `is_active` را نگاه
    نمی‌کند، پس حسابِ غیرفعال هم پیدا می‌شود و ثبتِ خودکار نمی‌شکند. تستِ بعدی
    دقیقاً همین را می‌سنجد.
    """
    sys = Account(code="SYS-1", name="صندوقِ سیستمی", type="asset", system_role="test_cash")
    db.add(sys)
    db.flush()

    r = client.patch(f"/api/accounts/{sys.id}", json={"is_active": False})

    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False


def test_auto_posting_still_finds_a_deactivated_system_account(db, user, client):
    """قیدی که غیرفعال‌سازیِ حسابِ سیستمی را بی‌خطر می‌کند.

    اگر روزی کسی به `get_account` فیلترِ `is_active` اضافه کند، این قرمز می‌شود —
    و همان لحظه معلوم است که غیرفعال‌کردنِ صندوق، ثبتِ فاکتور را می‌شکند.
    """
    from app.services.common import get_account

    sys = Account(code="SYS-2", name="حسابِ نقش‌دار", type="asset", system_role="test_role")
    db.add(sys)
    db.flush()
    client.patch(f"/api/accounts/{sys.id}", json={"is_active": False})

    found = get_account(db, "test_role")

    assert found.id == sys.id
    assert found.is_active is False


def test_system_account_still_cannot_be_deleted(db, user, client):
    """حذف داستانِ دیگری است: `get_account` نبودنش را با ۵۰۰ اعلام می‌کند."""
    sys = Account(code="SYS-3", name="حسابِ سیستمی", type="asset", system_role="test_del")
    db.add(sys)
    db.flush()

    assert client.delete(f"/api/accounts/{sys.id}").status_code == 409


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


# ── فهرستِ حذف (تنظیمات ← کدینگ) ─────────────────────────────────────────
def test_deletable_list_explains_every_refusal(db, user, client):
    """هر حسابِ غیرقابلِ‌حذف باید دلیل داشته باشد، وگرنه کاربر دکمه‌ی خاکستری می‌بیند
    و نمی‌فهمد چرا."""
    rows = client.get("/api/accounts/deletable").json()
    assert rows, "فهرست نباید خالی باشد"

    for r in rows:
        assert (r["reason"] is None) == r["can_delete"], f"{r['code']}: دلیل و پرچم نمی‌خوانند"
        assert r["level"] in ("گروه", "کل", "معین", "تفصیلی")


def test_deletable_marks_system_and_parent_accounts(db, user, client):
    rows = {r["code"]: r for r in client.get("/api/accounts/deletable").json()}

    #: سرفصلی که زیرحساب دارد
    assert rows["11"]["can_delete"] is False
    assert "زیرحساب" in rows["11"]["reason"]

    #: حسابِ نقش‌دار
    assert rows["1101"]["can_delete"] is False
    assert "سیستمی" in rows["1101"]["reason"]


def test_deletable_flags_a_posted_account(db, user, client):
    grp = _a_group(db)
    other, _ = _two_leaves(db)
    aid = client.post("/api/accounts", json={
        "code": _free_code(client, grp), "name": "سنددار", "type": grp.type, "parent_id": str(grp.id),
    }).json()["id"]
    client.post("/api/journal-entries", json={
        "entry_date": date.today().isoformat(), "description": "آزمون",
        "lines": [
            {"account_id": aid, "debit": 1, "credit": 0},
            {"account_id": str(other.id), "debit": 0, "credit": 1},
        ],
    })

    row = next(r for r in client.get("/api/accounts/deletable").json() if r["id"] == aid)

    assert row["can_delete"] is False
    assert "سند" in row["reason"]
