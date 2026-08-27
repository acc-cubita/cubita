"""موجودیت‌های «شرکت»: گروهِ طرف‌حساب، محلِ جغرافیایی، فردِ مرتبط.

تمرکزِ تست‌ها روی همان سه قاعده‌ای است که سرویس برایشان نوشته شد — چون بقیه‌ی
CRUD همان الگوی مرکزِ هزینه است و ارزشِ تستِ جداگانه ندارد:
حذف داده را یتیم نکند، درختِ جغرافیایی حلقه نگیرد، و «نفرِ اصلی» یکی بماند.
"""


def _contact(client, name="فروشگاه نمونه"):
    r = client.post("/api/contacts", json={"name": name, "type": "customer"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── گروه ─────────────────────────────────────────────────────────────────────


def test_group_roundtrip_and_contact_count(client):
    g = client.post("/api/company/groups", json={"name": "عمده‌فروش", "code": "W"})
    assert g.status_code == 201, g.text
    gid = g.json()["id"]
    assert g.json()["contact_count"] == 0

    cid = _contact(client)
    assert client.patch(f"/api/contacts/{cid}", json={"name": "فروشگاه نمونه", "type": "customer", "group_id": gid}).status_code == 200

    rows = client.get("/api/company/groups").json()
    assert [r["contact_count"] for r in rows if r["id"] == gid] == [1]


def test_group_in_use_cannot_be_deleted(client):
    gid = client.post("/api/company/groups", json={"name": "همکار"}).json()["id"]
    cid = _contact(client, "همکارِ الف")
    client.patch(f"/api/contacts/{cid}", json={"name": "همکارِ الف", "type": "customer", "group_id": gid})

    r = client.delete(f"/api/company/groups/{gid}")
    assert r.status_code == 409, r.text
    assert "غیرفعال" in r.json()["detail"]
    # ولی گروهِ بی‌استفاده حذف می‌شود.
    free = client.post("/api/company/groups", json={"name": "بی‌استفاده"}).json()["id"]
    assert client.delete(f"/api/company/groups/{free}").status_code == 204


# ── محلِ جغرافیایی ───────────────────────────────────────────────────────────


def _geo(client, name, kind, parent=None):
    r = client.post(
        "/api/company/locations", json={"name": name, "kind": kind, "parent_id": parent}
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_geo_path_is_built_from_the_tree(client):
    iran = _geo(client, "ایران", "country")
    tehran_p = _geo(client, "تهران", "province", iran["id"])
    tehran_c = _geo(client, "تهران", "city", tehran_p["id"])
    d3 = _geo(client, "منطقه ۳", "district", tehran_c["id"])
    assert d3["path"] == "ایران / تهران / تهران / منطقه ۳"


def test_geo_rejects_invalid_kind(client):
    r = client.post("/api/company/locations", json={"name": "جایی", "kind": "galaxy"})
    assert r.status_code == 422


def test_geo_cannot_become_its_own_descendant(client):
    a = _geo(client, "الف", "country")
    b = _geo(client, "ب", "province", a["id"])

    # «الف» زیرِ فرزندش برود → حلقه.
    r = client.put(
        f"/api/company/locations/{a['id']}",
        json={"name": "الف", "kind": "country", "parent_id": b["id"]},
    )
    assert r.status_code == 400, r.text
    assert "خودش" in r.json()["detail"]

    # زیرِ خودش هم همین‌طور.
    r2 = client.put(
        f"/api/company/locations/{a['id']}",
        json={"name": "الف", "kind": "country", "parent_id": a["id"]},
    )
    assert r2.status_code == 400


def test_geo_with_children_cannot_be_deleted(client):
    a = _geo(client, "کشور", "country")
    _geo(client, "استان", "province", a["id"])
    r = client.delete(f"/api/company/locations/{a['id']}")
    assert r.status_code == 409
    assert "زیرمجموعه" in r.json()["detail"]


def test_geo_in_use_cannot_be_deleted(client):
    city = _geo(client, "شهرِ الف", "city")
    cid = _contact(client, "مشتریِ شهری")
    client.patch(
        f"/api/contacts/{cid}",
        json={"name": "مشتریِ شهری", "type": "customer", "geo_location_id": city["id"]},
    )
    r = client.delete(f"/api/company/locations/{city['id']}")
    assert r.status_code == 409


# ── فردِ مرتبط ───────────────────────────────────────────────────────────────


def test_person_roundtrip_carries_contact_name(client):
    cid = _contact(client, "شرکتِ الف")
    r = client.post(
        "/api/company/persons",
        json={"contact_id": cid, "name": "رضا", "role": "مدیر خرید", "phone": "0912"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["contact_name"] == "شرکتِ الف"

    rows = client.get(f"/api/company/persons?contact_id={cid}").json()
    assert [p["name"] for p in rows] == ["رضا"]


def test_only_one_primary_person_per_contact(client):
    cid = _contact(client, "شرکتِ ب")
    first = client.post(
        "/api/company/persons", json={"contact_id": cid, "name": "الف", "is_primary": True}
    ).json()
    second = client.post(
        "/api/company/persons", json={"contact_id": cid, "name": "ب", "is_primary": True}
    ).json()

    rows = {p["id"]: p["is_primary"] for p in client.get(f"/api/company/persons?contact_id={cid}").json()}
    assert rows[second["id"]] is True
    assert rows[first["id"]] is False, "علامت‌زدنِ نفرِ تازه باید نفرِ قبلی را از حالتِ اصلی دربیاورد"


def test_primary_flag_survives_editing_the_same_person(client):
    """ویرایشِ نفرِ اصلی نباید خودش را از حالتِ اصلی دربیاورد."""
    cid = _contact(client, "شرکتِ ج")
    p = client.post(
        "/api/company/persons", json={"contact_id": cid, "name": "الف", "is_primary": True}
    ).json()
    edited = client.put(
        f"/api/company/persons/{p['id']}",
        json={"contact_id": cid, "name": "الفِ ویرایش‌شده", "is_primary": True},
    )
    assert edited.status_code == 200
    assert edited.json()["is_primary"] is True


def test_person_needs_a_real_contact(client):
    import uuid

    r = client.post(
        "/api/company/persons", json={"contact_id": str(uuid.uuid4()), "name": "کسی"}
    )
    assert r.status_code == 400


def test_deleting_the_contact_takes_its_people(client, db):
    """CASCADE عمدی است: فردِ مرتبط بدونِ طرف‌حسابش معنایی ندارد."""
    from app.models.company import RelatedPerson
    from app.models.inventory import Contact

    cid = _contact(client, "شرکتِ حذفی")
    client.post("/api/company/persons", json={"contact_id": cid, "name": "کسی"})
    db.delete(db.get(Contact, cid))
    db.flush()
    assert db.query(RelatedPerson).filter(RelatedPerson.contact_id == cid).count() == 0


# ── گزارش‌ساز ────────────────────────────────────────────────────────────────


def test_saved_report_stores_the_definition_not_the_result(client):
    """فقط دستورِ ساخت ذخیره می‌شود؛ اجرا هر بار زنده است."""
    cfg = {"columns": ["number", "total_amount"], "filters": [], "sortBy": "number", "limit": 50}
    r = client.post(
        "/api/company/reports",
        json={"name": "فاکتورهای بزرگ", "source": "sales.invoices", "config": cfg},
    )
    assert r.status_code == 201, r.text
    assert r.json()["config"] == cfg
    assert "rows" not in r.json(), "نتیجه نباید ذخیره شود"

    rows = client.get("/api/company/reports").json()
    assert [x["name"] for x in rows] == ["فاکتورهای بزرگ"]


def test_pinned_reports_come_first(client):
    client.post("/api/company/reports", json={"name": "ب", "source": "s", "config": {}})
    pinned = client.post(
        "/api/company/reports", json={"name": "ی", "source": "s", "config": {}, "is_pinned": True}
    ).json()
    rows = client.get("/api/company/reports").json()
    assert rows[0]["id"] == pinned["id"], "نشان‌شده باید بالای فهرست باشد حتی با نامِ مؤخر"


def test_saved_report_roundtrip_update_and_delete(client):
    made = client.post(
        "/api/company/reports", json={"name": "الف", "source": "s", "config": {"columns": ["a"]}}
    ).json()
    up = client.put(
        f"/api/company/reports/{made['id']}",
        json={"name": "الفِ ویرایش‌شده", "source": "s", "config": {"columns": ["a", "b"]}},
    )
    assert up.status_code == 200
    assert up.json()["config"]["columns"] == ["a", "b"]
    assert client.delete(f"/api/company/reports/{made['id']}").status_code == 204
    assert client.get("/api/company/reports").json() == []
