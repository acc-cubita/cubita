"""هر مسیرِ **تغییردهنده‌ی** ستاد باید ردِ ستادی بنویسد.

ثبتِ ردِ ستاد عمداً صریح است و نه خودکار (دلیلش در docstringِ
`app/services/staff_audit.py`). بهای صراحت این است که می‌شود فراموشش کرد، و
این پرونده همان بها را می‌پردازد.

**این تست یک دزدگیرِ دود است، نه یک تضمین.** متنِ منبعِ تابعِ اندپوینت را
می‌خواند، پس اگر کسی ثبت را داخلِ یک helper ببرد، تست سبز می‌ماند در حالی که
پوشش واقعی همان است. ارزشش در حالتِ رایج است: مسیرِ تازه‌ای که نویسنده‌اش اصلاً
به ردگیری فکر نکرده.
"""
import inspect

from app.main import app

#: کنش‌هایی که عمداً رد نمی‌نویسند، هرکدام با دلیلِ خودش.
_EXEMPT = {
    # ورود خودش ردِ `login` را می‌نویسد، ولی از داخلِ بدنه‌ی تابع و **پیش از**
    # ساختِ توکن؛ متنِ منبع شاملش هست، پس این استثنا فقط برای خوانایی است.
    "/api/admin/auth/login": "خودش ردِ login را می‌نویسد",
}

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def _mutating_admin_routes():
    out = []
    for route in app.routes:
        path = getattr(route, "path", "")
        endpoint = getattr(route, "endpoint", None)
        if not path.startswith("/api/admin") or endpoint is None:
            continue
        if not (getattr(route, "methods", set()) & _MUTATING):
            continue
        out.append((path, endpoint))
    return out


def test_every_mutating_admin_route_records_a_staff_audit_entry():
    missing = []
    for path, endpoint in _mutating_admin_routes():
        if path in _EXEMPT:
            continue
        try:
            source = inspect.getsource(endpoint)
        except OSError:  # pragma: no cover - فقط اگر منبع در دسترس نباشد
            continue
        if "staff_audit.record(" not in source:
            missing.append(f"{path} → {endpoint.__name__}")

    assert not missing, (
        "این مسیرهای تغییردهنده‌ی ستاد هیچ ردی نمی‌نویسند:\n  "
        + "\n  ".join(sorted(missing))
        + "\n\nیا `staff_audit.record(...)` اضافه کنید، یا با دلیل در `_EXEMPT` ثبتش کنید."
    )


def test_the_coverage_check_actually_sees_routes():
    """گاردِ خودِ گارد.

    اگر روزی `_mutating_admin_routes` به‌خاطر تغییری در ساختارِ روترها خالی
    برگردد، تستِ بالا سبز می‌ماند و هیچ چیزی را نمی‌سنجد — بدترین نوعِ تستِ
    مرده، چون به‌نظر سالم می‌آید.
    """
    assert len(_mutating_admin_routes()) >= 10


def test_every_recorded_action_is_a_known_one():
    """`staff_audit.record` روی کنشِ ناشناخته assert می‌کند؛ این فهرست را قفل می‌کند."""
    from app.services.staff_audit import ACTIONS

    assert "account_delete" in ACTIONS
    assert "login" in ACTIONS
    #: نامِ کنش در گزارش دیده می‌شود، پس بی‌فاصله و بی‌حرفِ بزرگ.
    assert all(a == a.lower() and " " not in a for a in ACTIONS)
