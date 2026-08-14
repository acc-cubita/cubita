"""بهای تمام‌شده‌ی کالا باید دستی قابلِ ویرایش باشد (PATCH /api/items)."""
from decimal import Decimal

from tests.factories import make_item


def test_average_cost_is_editable(db, user, client):
    item = make_item(db, average_cost=0)
    res = client.patch(f"/api/items/{item.id}", json={"average_cost": 1_500_000})
    assert res.status_code == 200
    assert Decimal(res.json()["average_cost"]) == Decimal(1_500_000)
    db.refresh(item)
    assert item.average_cost == Decimal(1_500_000)


def test_partial_update_keeps_other_fields(db, user, client):
    item = make_item(db, name="کالای الف", average_cost=0)
    client.patch(f"/api/items/{item.id}", json={"average_cost": 900_000})
    db.refresh(item)
    assert item.name == "کالای الف"  # فقط بها عوض شد
    assert item.average_cost == Decimal(900_000)


def test_negative_cost_rejected(db, user, client):
    item = make_item(db)
    res = client.patch(f"/api/items/{item.id}", json={"average_cost": -5})
    assert res.status_code == 422
