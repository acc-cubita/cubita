"""اصناف: تاکسونومی، اعلامِ صنفِ کسب‌وکار، و هدف‌گیریِ صنف در بازارِ پخش.

سه قیدی که این فایل نگه می‌دارد:

۱. **کلیدها یکتا و پایدارند.** کلیدِ صنف در `tenants.trade` و در
   `marketplace_settings.target_trades` ذخیره می‌شود؛ تکراری یا بلندتر از ستون،
   یعنی داده‌ی خراب.
۲. **فروشگاهی که صنفش را اعلام نکرده، چیزی از دست نمی‌دهد.** همه‌ی حساب‌های موجود
   این‌اند. اگر این بشکند، بازار برای آن‌ها بی‌صدا خالی می‌شود.
۳. **پخش‌کننده‌ی بدونِ هدف پنهان نمی‌شود.** همان قاعده از سمتِ دیگر.
"""
import uuid

import pytest

from app.models.marketplace import MarketplaceSettings
from app.models.tenant import Tenant
from app.services import marketplace as mp
from tests.conftest import PRIMARY_SLUG
from app.services.trades import (
    MAX_TRADE_KEY_LEN,
    TRADE_GROUPS,
    TRADE_LABELS,
    clean_trades,
    is_valid_trade,
    trade_label,
    trades_of_group,
)

ALL_TRADES = [t for g in TRADE_GROUPS for t in g.trades]


@pytest.fixture
def as_distributor(client, db):
    """مستأجرِ اصلیِ تست را پخش‌کننده می‌کند — همان الگوی `test_marketplace.py`."""
    tenant = db.query(Tenant).filter(Tenant.slug == PRIMARY_SLUG).one()
    tenant.kind = "distributor"
    db.flush()
    return client


# ── تاکسونومی ─────────────────────────────────────────────────────────
def test_keys_are_unique():
    keys = [t.key for t in ALL_TRADES]
    assert len(keys) == len(set(keys))


def test_group_keys_are_unique():
    keys = [g.key for g in TRADE_GROUPS]
    assert len(keys) == len(set(keys))


def test_labels_are_unique():
    #: دو برچسبِ یکسان یعنی کاربر در انتخابگر دو ردیفِ تفکیک‌ناپذیر می‌بیند.
    labels = [t.label for t in ALL_TRADES]
    assert len(labels) == len(set(labels))


def test_keys_fit_the_column():
    #: `tenants.trade` ستونِ `String(40)` است؛ کلیدِ بلندتر موقعِ ذخیره می‌ترکد.
    assert all(len(t.key) <= MAX_TRADE_KEY_LEN for t in ALL_TRADES)


def test_keys_are_ascii_snake_case():
    #: کلید در URL و JSON و دیتابیس می‌گردد؛ فارسی/فاصله همان‌جا دردسر می‌شود.
    for t in ALL_TRADES:
        assert t.key.replace("_", "").isalnum() and t.key.isascii() and t.key.islower()


def test_every_trade_has_a_label():
    assert all(TRADE_LABELS[t.key] for t in ALL_TRADES)


def test_taxonomy_is_not_thin():
    #: عددِ دقیق مهم نیست؛ این تست جلوی «فهرست تصادفاً خالی/نصفه شد» را می‌گیرد.
    assert len(TRADE_GROUPS) >= 8
    assert len(ALL_TRADES) >= 50


def test_validity_and_label_lookup():
    assert is_valid_trade("icecream")
    assert not is_valid_trade("nope")
    assert trade_label("icecream") == "بستنی‌فروشی"
    assert trade_label(None) == ""
    #: کلیدِ ناشناخته خودش برمی‌گردد — داده‌ی قدیمی نباید به رشته‌ی خالی تبدیل شود.
    assert trade_label("legacy_key") == "legacy_key"


def test_trades_of_group():
    assert "icecream" in trades_of_group("food")
    assert trades_of_group("nope") == ()


def test_clean_trades_dedupes_drops_unknown_and_orders():
    got = clean_trades(["tools", "nope", "icecream", "tools"])
    #: ترتیبِ خروجی ترتیبِ تاکسونومی است نه ورودی، تا دو ذخیره‌ی یکسان دو مقدارِ
    #: متفاوت در دیتابیس نسازند.
    assert got == ["icecream", "tools"]
    assert clean_trades(None) == []


# ── قاعده‌ی تطبیق (منطقِ خالص) ────────────────────────────────────────
@pytest.mark.parametrize(
    "retailer_trade, targets, visible, why",
    [
        ("icecream", [], True, "پخش‌کننده‌ی بدونِ هدف = بدونِ محدودیت"),
        ("icecream", None, True, "ستونِ خالیِ حسابِ قدیمی هم یعنی بدونِ محدودیت"),
        ("icecream", ["icecream", "bakery"], True, "صنفِ فروشگاه هدف گرفته شده"),
        ("icecream", ["autoparts"], False, "صنفِ فروشگاه هدف گرفته نشده"),
        (None, ["autoparts"], True, "فروشگاهِ بی‌صنف چیزی از دست نمی‌دهد"),
        (None, [], True, "هیچ‌کدام چیزی اعلام نکرده‌اند"),
    ],
)
def test_match_rule(retailer_trade, targets, visible, why):
    assert mp.distributor_matches_trade(retailer_trade, targets) is visible, why


# ── تطبیق روی مسیرِ واقعی ─────────────────────────────────────────────
def _bare(db, kind: str, *, trade: str | None = None) -> Tenant:
    t = Tenant(
        name="آزمون",
        slug=f"tr-{uuid.uuid4().hex[:8]}",
        kind=kind,
        status="active",
        trade=trade,
    )
    db.add(t)
    db.flush()
    return t


def _distributor(db, targets: list[str]) -> Tenant:
    t = _bare(db, "distributor")
    db.add(
        MarketplaceSettings(
            distributor_tenant_id=t.id,
            display_name=f"پخش {t.slug}",
            is_active=True,
            target_trades=targets,
        )
    )
    db.flush()
    return t


def _names(db, retailer: Tenant) -> set[str]:
    return {r["display_name"] for r in mp.list_distributors_for_retailer(db, retailer.id)}


def test_retailer_sees_only_distributors_targeting_its_trade(db):
    mine = _distributor(db, ["icecream"])
    theirs = _distributor(db, ["autoparts"])
    shop = _bare(db, "retailer", trade="icecream")

    seen = _names(db, shop)
    assert f"پخش {mine.slug}" in seen
    assert f"پخش {theirs.slug}" not in seen


def test_distributor_without_targets_stays_visible(db):
    """قیدِ ۳: پخش‌کننده‌ی موجود با این ارتقا از بازار غیب نمی‌شود."""
    open_to_all = _distributor(db, [])
    shop = _bare(db, "retailer", trade="icecream")
    assert f"پخش {open_to_all.slug}" in _names(db, shop)


def test_retailer_without_trade_sees_everyone(db):
    """قیدِ ۲: «نمی‌دانم» دلیلِ پنهان‌کردن نیست.

    بدونِ این، هر فروشگاهِ موجود — که همه‌شان `trade = NULL` اند — با این ارتقا
    پخش‌کننده‌های هدف‌دار را از دست می‌داد.
    """
    targeted = _distributor(db, ["autoparts"])
    shop = _bare(db, "retailer", trade=None)
    assert f"پخش {targeted.slug}" in _names(db, shop)


def test_inactive_distributor_still_hidden(db):
    """فیلترِ صنف جای گیت‌های قبلی را نمی‌گیرد، کنارشان می‌نشیند."""
    t = _bare(db, "distributor")
    db.add(
        MarketplaceSettings(
            distributor_tenant_id=t.id,
            display_name=f"پخش {t.slug}",
            is_active=False,
            target_trades=["icecream"],
        )
    )
    db.flush()
    shop = _bare(db, "retailer", trade="icecream")
    assert f"پخش {t.slug}" not in _names(db, shop)


# ── اندپوینتِ فهرست ───────────────────────────────────────────────────
def test_trades_endpoint_is_public_and_grouped(client):
    #: بدونِ توکن هم باید جواب بدهد — صفحه‌ی ثبت‌نام پیش از ورود صنف را می‌پرسد.
    r = client.get("/api/trades")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == len(TRADE_GROUPS)
    flat = [t["key"] for g in body for t in g["trades"]]
    assert flat == [t.key for t in ALL_TRADES]


# ── اعلامِ صنف توسطِ مالک ──────────────────────────────────────────────
def test_owner_sets_and_clears_trade(client):
    r = client.put("/api/modules/trade", json={"trade": "icecream"})
    assert r.status_code == 200, r.text
    assert r.json()["trade"] == "icecream"
    assert client.get("/api/auth/me").json()["trade"] == "icecream"

    #: پاک‌کردن مجاز است و به «اعلام‌نشده» برمی‌گردد، نه به یک پیش‌فرض.
    assert client.put("/api/modules/trade", json={"trade": None}).json()["trade"] is None


def test_invalid_trade_is_rejected(client):
    assert client.put("/api/modules/trade", json={"trade": "nope"}).status_code == 422


def test_marketplace_settings_reject_unknown_trade(as_distributor):
    r = as_distributor.put(
        "/api/marketplace/distributor/settings",
        json={"display_name": "پخش", "settlement_mode": "credit", "is_active": True, "target_trades": ["nope"]},
    )
    #: صریح رد می‌شود نه بی‌صدا دور ریخته — وگرنه پخش‌کننده فکر می‌کند صنفی را هدف
    #: گرفته که ذخیره نشده و بعد نمی‌فهمد چرا سفارشی نمی‌آید.
    assert r.status_code == 422


def test_marketplace_settings_roundtrip_trades(as_distributor):
    r = as_distributor.put(
        "/api/marketplace/distributor/settings",
        json={
            "display_name": "پخش",
            "settlement_mode": "credit",
            "is_active": True,
            "target_trades": ["tools", "icecream", "tools"],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["target_trades"] == ["icecream", "tools"]
