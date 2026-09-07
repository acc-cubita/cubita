"""دو قاعده‌ی مرکز هزینه که تا امروز فقط نوشته بودند، نه اجرا.

* **کد یکتاست.** کدی که تکرار می‌شود چیزی را شناسایی نمی‌کند.
* **مرکزِ غیرفعال به سندِ تازه برچسب نمی‌خورد** — و این تا امروز فقط یک فیلترِ
  سمتِ کلاینت بود؛ سرور هر مرکزی را می‌پذیرفت.

و دو استثنا که باید بمانند، چون خودِ ماژول رویشان بنا شده:

* کد **اختیاری** است، پس چند مرکزِ بی‌کد کنارِ هم مجازند.
* سابقه دست نمی‌خورد: رکوردی که از قبل به مرکزِ حالا-غیرفعال اشاره دارد باید
  همچنان قابلِ ویرایش بماند، وگرنه بستنِ یک مرکز قالب‌های قدیمی را قفل می‌کند.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.models.cost_center import CostCenter
from app.models.tenant import Tenant
from app.schemas.cost_center import CostCenterIn
from app.services.cost_centers import (
    create_cost_center,
    resolve_cost_center_id,
    update_cost_center,
)
from app.tenant_context import session_tenant
from tests.factories import main_warehouse, make_item


def _hybrid(db) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = "hybrid"
    db.flush()


def _new(db, user, *, name: str, code: str = "", active: bool = True):
    return create_cost_center(
        db, CostCenterIn(name=name, code=code, is_active=active), user
    )


# ── کد یکتاست ────────────────────────────────────────────────────────────────


def test_a_duplicate_code_is_refused(db, user):
    """**قیدِ اصلی.** دو مرکز با یک کد نمی‌شود."""
    _new(db, user, name="تولید", code="1001")

    with pytest.raises(Exception) as err:
        _new(db, user, name="فروش", code="1001")

    assert "1001" in str(err.value)


def test_several_centers_without_a_code_live_side_by_side(db, user):
    """کد اختیاری است و باید بماند.

    اگر قید ساده بود (نه جزئی)، دومین مرکزِ بی‌کد به اولی گیر می‌کرد چون `''` هم
    یک مقدار است — و کاربر برای هر واحدِ کوچک مجبور به ساختنِ کدِ الکی می‌شد.
    """
    _new(db, user, name="اداری")
    _new(db, user, name="بازاریابی")
    _new(db, user, name="منابع انسانی")

    assert db.query(CostCenter).filter(CostCenter.code == "").count() == 3


def test_editing_a_center_may_keep_its_own_code(db, user):
    """گاردِ یکتایی نباید مرکز را با خودش مقایسه کند."""
    center = _new(db, user, name="تولید", code="1001")

    updated = update_cost_center(
        db, center["id"], CostCenterIn(name="تولیدِ زنجان", code="1001")
    )

    assert updated["name"] == "تولیدِ زنجان"
    assert updated["code"] == "1001"


def test_editing_cannot_steal_another_centers_code(db, user):
    _new(db, user, name="تولید", code="1001")
    other = _new(db, user, name="فروش", code="1002")

    with pytest.raises(Exception) as err:
        update_cost_center(db, other["id"], CostCenterIn(name="فروش", code="1001"))

    assert "1001" in str(err.value)


# ── مرکزِ غیرفعال ────────────────────────────────────────────────────────────


def test_an_inactive_center_is_refused_for_a_new_document(db, user):
    """**قیدِ دوم.** «غیرفعال» باید در سرور معنا داشته باشد، نه فقط در فرم."""
    center = _new(db, user, name="کارخانه‌ی بسته", code="9001", active=False)

    with pytest.raises(Exception) as err:
        resolve_cost_center_id(db, center["id"])

    assert "غیرفعال" in str(err.value)


def test_an_active_center_still_passes(db, user):
    center = _new(db, user, name="کارخانه‌ی زنجان", code="9002")

    assert resolve_cost_center_id(db, center["id"]) == center["id"]


def test_no_cost_center_at_all_is_still_allowed(db, user):
    """برچسب اختیاری است و این گارد نباید اجباری‌اش کند."""
    assert resolve_cost_center_id(db, None) is None


def test_an_unchanged_reference_to_an_inactive_center_still_passes(db, user):
    """**استثنای عمدی.** سابقه نباید قفل شود.

    قالبِ سندِ تکرارشونده‌ای که مرکزش پارسال بسته شده باید هنوز قابلِ ویرایش
    باشد؛ وگرنه کاربر برای عوض‌کردنِ عنوان مجبور می‌شود مرکزش را هم عوض کند و
    سابقه به‌هم می‌ریزد.
    """
    center = _new(db, user, name="پروژه‌ی تمام‌شده", code="9003", active=False)

    assert resolve_cost_center_id(db, center["id"], current=center["id"]) == center["id"]


# ── از طریقِ API، نه فقط سرویس ────────────────────────────────────────────────


def test_a_sales_invoice_cannot_be_tagged_with_an_inactive_center(db, user, client):
    """قید باید از مسیرِ واقعیِ ثبتِ فاکتور هم بگیرد، نه فقط در تستِ واحد."""
    _hybrid(db)
    center = _new(db, user, name="مرکزِ بسته", code="9004", active=False)

    item = make_item(db, sales_price=Decimal(1_000_000))
    warehouse = main_warehouse(db)
    from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
    from app.services.inventory import post_purchase_invoice

    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 1, 1),
            warehouse_id=warehouse.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(1000))],
        ),
        user,
    )

    res = client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": "2026-06-01",
            "warehouse_id": str(warehouse.id),
            "cost_center_id": str(center["id"]),
            "lines": [{"item_id": str(item.id), "qty": 1, "unit_price": 1_000_000}],
        },
    )

    assert res.status_code == 400, res.text
    assert "غیرفعال" in res.json()["detail"]


# ── عنوانِ دوم ──────────────────────────────────────────────────────────────


def test_the_second_title_is_stored_and_returned(db, user):
    """«عنوان انگلیسی»ِ فرمِ سپیدار — برای گزارشِ دوزبانه.

    سه موجودیتِ هم‌رده از قبل داشتندش (`accounts`، `analytic_accounts`،
    `contacts`)؛ مرکز هزینه تنها یکی بود که جا مانده بود.
    """
    center = create_cost_center(
        db, CostCenterIn(name="کارخانه زنجان", name2="Zanjan Plant", code="7001"), user
    )

    assert center["name2"] == "Zanjan Plant"


def test_the_second_title_is_optional(db, user):
    """اختیاری می‌ماند، مثلِ `code`.

    اگر روزی اجباری شود، هر مرکزِ داخلی که عنوانِ لاتین ندارد ساختنش ناممکن می‌شود.
    """
    center = create_cost_center(db, CostCenterIn(name="واحد اداری"), user)

    assert center["name2"] == ""


def test_the_second_title_can_be_edited(db, user):
    center = create_cost_center(db, CostCenterIn(name="فروش"), user)

    updated = update_cost_center(db, center["id"], CostCenterIn(name="فروش", name2="Sales"))

    assert updated["name2"] == "Sales"
