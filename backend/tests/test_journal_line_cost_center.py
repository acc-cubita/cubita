"""مرکزِ هزینه‌ی ردیفِ سندِ دستی — ردیف بر سند مقدم است (UI-01، تکمیل §۹ و §۱۵).

ستونِ `journal_lines.cost_center_id` از مهاجرتِ ۰۰۲۸ بوده و گزارش‌های مرکز هزینه از
همان می‌خوانند؛ فقط `JournalLineIn` راهی به آن نداشت و روتر مرکزِ سند را روی همه‌ی
ردیف‌ها کپی می‌کرد. این فایل قاعده‌ی تازه و **سازگاری با گذشته** را قفل می‌کند:
کلاینتی که فیلدِ ردیفی نمی‌فرستد دقیقاً همان رفتارِ پیشین را می‌بیند.

کدِ مرکزها یکتاست چون تست‌های `client` روی پایگاه‌داده‌ی مشترک کامیت می‌کنند.
"""
from datetime import date
from uuid import uuid4

from app.models.accounting import Account, JournalEntry
from app.models.cost_center import CostCenter
from app.schemas.cost_center import CostCenterIn
from app.services import cost_centers as svc


def _center(db, user, name: str) -> CostCenter:
    out = svc.create_cost_center(db, CostCenterIn(name=name, code=f"L{uuid4().hex[:7]}"), user)
    db.commit()
    return db.get(CostCenter, out["id"])


def _two_leaves(db):
    rows = db.query(Account).filter(Account.is_group.is_(False)).order_by(Account.code).limit(2).all()
    return rows[0], rows[1]


def _post(client, a1, a2, *, header=None, line1=None, line2=None):
    def line(account, debit, credit, center):
        out = {"account_id": str(account.id), "debit": debit, "credit": credit}
        if center is not None:
            out["cost_center_id"] = str(center)
        return out

    body = {
        "entry_date": date.today().isoformat(),
        "description": "مرکزِ هزینه‌ی ردیف",
        "lines": [line(a1, 700, 0, line1), line(a2, 0, 700, line2)],
    }
    if header is not None:
        body["cost_center_id"] = str(header)
    return client.post("/api/journal-entries", json=body)


def _centers_of(db, entry_id):
    db.expire_all()
    entry = db.get(JournalEntry, entry_id)
    return [str(l.cost_center_id) if l.cost_center_id else None for l in sorted(entry.lines, key=lambda l: l.debit, reverse=True)]


def test_line_center_overrides_header(db, user, client):
    a1, a2 = _two_leaves(db)
    header, own = _center(db, user, "سربرگ"), _center(db, user, "ردیف")
    r = _post(client, a1, a2, header=header.id, line1=own.id)
    assert r.status_code == 201, r.text
    #: ردیفِ اول مرکزِ خودش را دارد؛ ردیفِ دوم از سند ارث می‌برد.
    assert _centers_of(db, r.json()["id"]) == [str(own.id), str(header.id)]


def test_without_line_centers_behaviour_is_unchanged(db, user, client):
    a1, a2 = _two_leaves(db)
    header = _center(db, user, "فقط سربرگ")
    r = _post(client, a1, a2, header=header.id)
    assert r.status_code == 201, r.text
    assert _centers_of(db, r.json()["id"]) == [str(header.id), str(header.id)]


def test_line_center_without_header(db, user, client):
    a1, a2 = _two_leaves(db)
    own = _center(db, user, "بی سربرگ")
    r = _post(client, a1, a2, line2=own.id)
    assert r.status_code == 201, r.text
    assert _centers_of(db, r.json()["id"]) == [None, str(own.id)]


def test_read_api_returns_the_line_center(db, user, client):
    a1, a2 = _two_leaves(db)
    own = _center(db, user, "خواندنی")
    entry = _post(client, a1, a2, line1=own.id).json()
    lines = client.get(f"/api/journal-entries/{entry['id']}").json()["lines"]
    assert {l["cost_center_id"] for l in lines} == {str(own.id), None}


def test_unknown_line_center_is_rejected(db, user, client):
    a1, a2 = _two_leaves(db)
    r = _post(client, a1, a2, line1=uuid4())
    assert r.status_code == 400
    assert "مرکز هزینه" in r.json()["detail"]


def test_inactive_line_center_is_rejected(db, user, client):
    a1, a2 = _two_leaves(db)
    closed = _center(db, user, "بسته")
    closed.is_active = False
    db.commit()
    r = _post(client, a1, a2, line1=closed.id)
    assert r.status_code == 400, r.text


def test_void_mirrors_line_centers(db, user, client):
    a1, a2 = _two_leaves(db)
    header, own = _center(db, user, "سربرگِ ابطال"), _center(db, user, "ردیفِ ابطال")
    entry = _post(client, a1, a2, header=header.id, line1=own.id).json()
    r = client.post(f"/api/journal-entries/{entry['id']}/void", json={"reason": "آزمونِ مرکزِ ردیف"})
    assert r.status_code == 200, r.text
    #: سندِ معکوس باید هر ردیف را روی **همان** مرکز برگرداند، وگرنه گزارشِ مرکز
    #: هزینه بعد از ابطال صفر نمی‌شد.
    reversal = sorted(
        db.get(JournalEntry, r.json()["reversal_entry_id"]).lines, key=lambda l: l.credit, reverse=True
    )
    assert [str(l.cost_center_id) for l in reversal] == [str(own.id), str(header.id)]
