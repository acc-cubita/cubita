"""سه ناوردای جداسازیِ ستاد از مستأجر.

این پرونده گرانبهاترین تستِ کوچ به `admin.cubita.ir` است، چون هر سه ناوردا
**بی‌صدا** می‌شکنند: هیچ‌کدام خطا نمی‌دهند، فقط دسترسی‌ای می‌دهند که نباید.

تست‌ها روی `app.routes` پارامتری‌اند و نه روی فهرستِ دستی، تا مسیری که فردا کسی
اضافه می‌کند خودکار پوشش بگیرد — فهرستِ دستی دقیقاً همان‌جایی است که مسیرِ تازه
جا می‌ماند.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.security import create_access_token, create_staff_token
from app.tenant_context import current_tenant_in_db, tenant_scope

_DUMMY = str(uuid.uuid4())

#: ورودِ ستاد عمداً باز است — خودش مسیرِ گرفتنِ توکن است.
_OPEN_ADMIN_PATHS = {"/api/admin/auth/login"}


def _admin_routes():
    out = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/admin") or path in _OPEN_ADMIN_PATHS:
            continue
        for method in sorted(getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}):
            out.append((method, path))
    return sorted(set(out))


def _fill(path: str) -> str:
    out = []
    for part in path.split("/"):
        out.append(_DUMMY if part.startswith("{") and part.endswith("}") else part)
    return "/".join(out)


@pytest.fixture
def raw(db):
    """کلاینت بدونِ override کردنِ احراز هویت — مسیرِ واقعیِ توکن اجرا می‌شود."""
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ── ناوردای ۱: توکنِ مستأجری به /api/admin نمی‌رسد ─────────────────────────────


@pytest.mark.parametrize("method,path", _admin_routes())
def test_ordinary_tenant_token_cannot_reach_admin(raw, user, method, path):
    """کاربرِ عادیِ یک کسب‌وکار، حتی با توکنِ کاملاً معتبر.

    این حتی با `legacy_admin_allowlist`ِ روشن هم باید ببندد — آن پل فقط برای
    ایمیل‌های روی allowlist است، نه برای هر توکنِ مستأجری.
    """
    r = raw.request(
        method,
        _fill(path),
        json={},
        headers={"Authorization": f"Bearer {create_access_token(user)}"},
    )
    assert r.status_code in (401, 403), f"{method} {path} → {r.status_code}: {r.text[:160]}"


@pytest.mark.parametrize("method,path", _admin_routes())
def test_with_the_legacy_bridge_closed_no_tenant_token_works(raw, user, monkeypatch, method, path):
    """بعد از کوچ: هر توکنِ مستأجری روی `/api/admin/*` ۴۰۱ می‌گیرد.

    حتی ایمیلِ سوپرادمینِ قدیمی — که همین را می‌خواهیم اثبات کنیم، چون قدمِ آخرِ
    کوچ فقط خاموش‌کردنِ همین پرچم است.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "legacy_admin_allowlist", False)
    monkeypatch.setattr(settings, "super_admin_emails", user.email)

    r = raw.request(
        method,
        _fill(path),
        json={},
        headers={"Authorization": f"Bearer {create_access_token(user)}"},
    )
    assert r.status_code == 401, f"{method} {path} → {r.status_code}: {r.text[:160]}"


def test_the_legacy_bridge_still_carries_the_old_super_admin(raw, user, monkeypatch):
    """و تا وقتی پرچم روشن است، باندلِ مستقرِ acc.cubita.ir نمی‌شکند."""
    settings = get_settings()
    monkeypatch.setattr(settings, "legacy_admin_allowlist", True)
    monkeypatch.setattr(settings, "super_admin_emails", user.email)

    r = raw.get(
        "/api/admin/accounts", headers={"Authorization": f"Bearer {create_access_token(user)}"}
    )
    assert r.status_code == 200, r.text


# ── ناوردای ۲: توکنِ ستاد به مسیرهای مستأجری نمی‌رسد ──────────────────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/auth/me"),
        ("GET", "/api/accounts"),
        ("GET", "/api/journal-entries"),
        ("GET", "/api/members"),
        ("GET", "/api/backup/export"),
        ("POST", "/api/journal-entries"),
    ],
)
def test_staff_token_cannot_reach_tenant_routes(raw, staff_user, method, path):
    """توکنِ ستاد `tid` ندارد.

    بدونِ گاردِ `typ` در `get_principal`، کوئریِ عضویت به «اولین عضویتِ فعال»
    می‌افتاد — و چون کارمندِ ستاد هیچ عضویتی ندارد امروز ۴۰۳ می‌گرفت، ولی
    لحظه‌ای که کسی به یک کارمند عضویتی بدهد (مثلاً نشستِ پشتیبانی) توکنِ ستادش
    ناخواسته کلیدِ دفترِ آن مشتری می‌شد.
    """
    admin = staff_user()
    r = raw.request(
        method,
        path,
        json={},
        headers={"Authorization": f"Bearer {create_staff_token(admin.user)}"},
    )
    assert r.status_code == 401, f"{method} {path} → {r.status_code}: {r.text[:160]}"


def test_a_staff_token_with_a_forged_tenant_claim_is_still_rejected(raw, staff_user, tenant_id):
    """ترتیبِ بررسی مهم است: گاردِ `typ` **پیش از** کوئریِ عضویت می‌آید."""
    import jose.jwt as jwt

    from app.config import get_settings as gs

    admin = staff_user()
    settings = gs()
    forged = jwt.encode(
        {
            "sub": str(admin.user_id),
            "tv": admin.user.token_version or 0,
            "typ": "staff",
            "tid": str(tenant_id),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    r = raw.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


# ── ناوردای ۳: درخواستِ ستاد هیچ مستأجری بسته ندارد ──────────────────────────


def test_a_staff_request_binds_no_tenant(db, staff_user):
    """**دلیلِ وجودِ کلِ این طراحی.**

    سیاستِ RLS در نبودِ `app.tenant_id` صفر ردیف می‌دهد، پس نشستِ ستاد
    نمی‌تواند تصادفی دفترِ کسی را بخواند. اگر روزی `get_staff_principal`
    مستأجری ببندد، این تست تنها چیزی است که می‌گیردش — چون هیچ خطایی رخ نمی‌دهد،
    فقط داده‌ای دیده می‌شود که نباید.

    عمداً خودِ تابع صدا زده می‌شود و نه از راهِ کلاینت: فیکسچرِ `db` از قبل یک
    مستأجر بسته، پس تستِ HTTP اینجا چیزی را اثبات نمی‌کرد.

    **دقتِ لازم درباره‌ی شکلِ شکست:** بسته به اینکه اتصال پیش‌تر درخواستِ
    مستأجری‌ای سرو کرده باشد یا نه، `app.tenant_id` یا NULL است یا `''`؛ اولی
    صفر ردیف می‌دهد و دومی خطای cast. هر دو بسته‌اند، و تست همین را می‌سنجد —
    نه یکی از آن دو شکل را — چون ناوردای واقعی «هیچ ردیفی بیرون نمی‌آید» است.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import DatabaseError
    from starlette.datastructures import Headers
    from starlette.requests import Request

    from app.deps import get_staff_principal
    from fastapi.security import HTTPAuthorizationCredentials

    admin = staff_user()
    creds = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_staff_token(admin.user)
    )
    request = Request({"type": "http", "headers": Headers({}).raw, "client": ("1.2.3.4", 0)})

    # زمینه‌ی یک درخواستِ ستادیِ واقعی: هیچ مستأجری بسته نیست.
    with tenant_scope(db, None):
        staff = get_staff_principal(request=request, credentials=creds, db=db)
        assert staff.role == "owner"
        #: `get_staff_principal` نباید چیزی بسته باشد.
        assert current_tenant_in_db(db) in (None, "")

        for table in ("journal_entries", "accounts", "sales_invoices"):
            savepoint = db.begin_nested()
            try:
                count = db.execute(text(f"SELECT count(*) FROM {table}")).scalar()
                assert count == 0, f"نشستِ ستاد {count} ردیف از {table} دید"
            except DatabaseError:
                pass  # cast خطا داد — همان بسته‌بودن، با صدای بلندتر
            finally:
                savepoint.rollback()
