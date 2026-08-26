"""«اتصال فروشگاه» ماژولِ محدود است — پیش‌فرض خاموش، فقط با گرنتِ سوپرادمین.

قبلاً این ماژول برای هر حسابِ پولی باز بود و لای گروهِ «تنظیمات» می‌نشست. حالا مثلِ
«تولید» یک ماژولِ کاریِ مستقل روی منوی اصلی است که سوپرادمین اکانت‌به‌اکانت بازش می‌کند.

نکته‌ی مهم: پنهان‌کردنِ منو کافی نیست — گیت در بک‌اند است، وگرنه هر کسی با یک curl
به همان مسیرها می‌رسید.
"""
import pytest

from app.models.tenant import Tenant
from app.services import modules as svc


# ── گیتِ سرور ────────────────────────────────────────────────────────────────
STOREFRONT_PATHS = ("/api/integration/settings", "/api/storefront")


@pytest.mark.parametrize("path", STOREFRONT_PATHS)
def test_ungranted_account_is_blocked(client, path):
    """بدونِ گرنت، مسیرهای فروشگاه ۴۰۳ می‌دهند — نه ۴۰۴ و نه پاسخِ خالی."""
    r = client.get(path)
    assert r.status_code == 403, r.text
    assert "فعال نیست" in r.json()["detail"]


@pytest.mark.parametrize("path", STOREFRONT_PATHS)
def test_granted_account_passes(client, grant_module, path):
    grant_module("integration")
    assert client.get(path).status_code == 200


def test_public_shop_api_is_not_gated(client, db, tenant_id, grant_module):
    """سطحِ عمومیِ `/api/shop/*` نباید پشتِ گیتِ ماژول برود.

    آن‌جا اصلاً کاربرِ احرازشده‌ای نیست (هویت با کلیدِ publishable است) و بستنش یعنی
    خاموش‌شدنِ سایتِ مشتری‌هایی که همین حالا فروشگاهشان بالاست.
    """
    grant_module("integration")
    client.put(
        "/api/storefront",
        json={
            "theme_id": "general", "theme_config": {}, "seo_title": "", "seo_description": "",
            "contact_block": {}, "allowed_origin": "https://myshop.test",
        },
    )
    client.post("/api/storefront/publish")
    sf = client.get("/api/storefront").json()

    # گرنت را پس می‌گیریم؛ سایتِ عمومی باید همچنان کار کند.
    db.get(Tenant, tenant_id).granted_modules = []
    db.flush()
    assert client.get("/api/storefront").status_code == 403

    from tests.conftest import PRIMARY_SLUG

    r = client.get("/api/shop/info", headers={"X-Shop-Slug": PRIMARY_SLUG, "X-Shop-Key": sf["publishable_key"]})
    assert r.status_code == 200, r.text


# ── رجیستریِ ماژول‌ها ────────────────────────────────────────────────────────
def test_integration_is_off_by_default(db, tenant_id):
    """حسابِ تازه این ماژول را ندارد — نه در «مجاز»، پس نه در منو."""
    tenant = db.get(Tenant, tenant_id)
    tenant.granted_modules = []
    assert "integration" not in svc.allowed_modules(tenant)
    assert not svc.is_module_visible(tenant, "integration")


def test_no_industry_template_turns_it_on(db, tenant_id):
    """هیچ قالبِ صنفی نباید این ماژول را خودکار روشن کند — وگرنه «پیش‌فرض خاموش» دروغ است."""
    for industry in svc.INDUSTRY_TEMPLATES:
        assert "integration" not in svc.INDUSTRY_TEMPLATES[industry], industry


def test_grant_makes_it_visible(db, tenant_id):
    tenant = db.get(Tenant, tenant_id)
    tenant.enabled_modules = None  # شخصی‌سازی‌نشده
    svc.set_grants(tenant, ["integration"])
    assert svc.is_module_visible(tenant, "integration")


def test_owner_save_does_not_wipe_a_granted_module(db, tenant_id):
    """مالک تنظیماتِ پنل را ذخیره می‌کند و ماژولِ گرنت‌شده روشن می‌ماند.

    قبلاً `set_enabled` هر کلیدِ غیرمجاز را دور می‌ریخت؛ چون هنگامِ ذخیره ممکن است
    ترتیبِ گرنت هنوز نرسیده باشد، نتیجه این می‌شد که سوپرادمین «فعال» می‌کرد و مالک
    همچنان چیزی نمی‌دید.
    """
    tenant = db.get(Tenant, tenant_id)
    svc.set_grants(tenant, ["integration"])
    svc.set_enabled(tenant, ["sales", "integration"])
    assert "integration" in tenant.enabled_modules

    # گرنت پس گرفته شود: ترجیح می‌ماند ولی نمایش بسته می‌شود.
    svc.set_grants(tenant, [])
    assert "integration" in svc.enabled_modules(tenant)
    assert not svc.is_module_visible(tenant, "integration")


def test_owner_cannot_grant_it_to_themselves(db, tenant_id):
    """مالک با روشن‌کردنِ دستی نمی‌تواند ماژولِ گرنت‌نشده را باز کند."""
    tenant = db.get(Tenant, tenant_id)
    tenant.granted_modules = []
    tenant.enabled_modules = []
    svc.set_enabled(tenant, ["integration"])
    assert "integration" not in (tenant.enabled_modules or [])


def test_industry_change_keeps_the_grant(db, tenant_id):
    """عوض‌کردنِ صنف نباید گرنتِ موردیِ سوپرادمین را بی‌صدا پس بگیرد."""
    tenant = db.get(Tenant, tenant_id)
    svc.set_grants(tenant, ["integration"])
    svc.set_industry(tenant, "retail")
    assert "integration" in tenant.enabled_modules
    assert svc.is_module_visible(tenant, "integration")
