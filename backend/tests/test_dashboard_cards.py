"""کارت‌های داشبوردِ کاربر — ذخیره روی عضویت، پیش‌فرض در برابرِ خالیِ عمدی."""


def test_me_has_no_cards_before_first_choice(client):
    """حسابِ تازه: `null` یعنی «انتخاب نکرده» تا فرانت پیش‌فرض‌ها را بگذارد."""
    me = client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["dashboard_cards"] is None


def test_saved_cards_come_back_in_me(client):
    cards = ["salesinvoice", "inventory/products", "journalentry"]
    r = client.put("/api/dashboard/cards", json={"cards": cards})
    assert r.status_code == 200, r.text
    assert r.json()["cards"] == cards
    # ترتیب هم ذخیره می‌شود، نه فقط مجموعه — چیدمانِ باکس همین است.
    assert client.get("/api/auth/me").json()["dashboard_cards"] == cards


def test_empty_list_is_not_the_same_as_never_chosen(client):
    """`[]` یعنی «باکس را خالی بگذار» و نباید به پیش‌فرض برگردد."""
    client.put("/api/dashboard/cards", json={"cards": ["salesinvoice"]})
    r = client.put("/api/dashboard/cards", json={"cards": []})
    assert r.status_code == 200, r.text
    assert r.json()["cards"] == []
    assert client.get("/api/auth/me").json()["dashboard_cards"] == []


def test_reset_returns_to_default_not_to_empty(client):
    client.put("/api/dashboard/cards", json={"cards": ["salesinvoice"]})
    r = client.delete("/api/dashboard/cards")
    assert r.status_code == 200, r.text
    assert r.json()["cards"] is None
    assert client.get("/api/auth/me").json()["dashboard_cards"] is None


def test_duplicates_collapse_keeping_first_position(client):
    r = client.put(
        "/api/dashboard/cards",
        json={"cards": ["salesinvoice", "quotations", "salesinvoice"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["cards"] == ["salesinvoice", "quotations"]


def test_blank_entries_are_dropped(client):
    r = client.put("/api/dashboard/cards", json={"cards": ["  ", "quotations"]})
    assert r.status_code == 200, r.text
    assert r.json()["cards"] == ["quotations"]


def test_garbage_id_is_rejected(client):
    """گاردِ شکل: ستون نباید آشغال‌دانی شود، هرچند وجودِ صفحه را سرور نمی‌سنجد."""
    for bad in ["<script>", "Sales Invoice", "a" * 90, "/products", "inventory/"]:
        r = client.put("/api/dashboard/cards", json={"cards": [bad]})
        assert r.status_code == 400, f"{bad!r} → {r.status_code}"


def test_too_many_cards_is_rejected(client):
    r = client.put("/api/dashboard/cards", json={"cards": [f"page-{i}" for i in range(25)]})
    assert r.status_code == 422, r.text
