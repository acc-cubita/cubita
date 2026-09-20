"""`tenant_scope` باید زمینه‌ی قبلی را **برگرداند**، نه فقط ContextVar را.

## چرا این تست هست

`tenant_scope` در `finally` فقط `_current_tenant.reset(token)` می‌زد. دو چیزِ
دیگر دست‌نخورده می‌ماندند:

* `db.info[SESSION_KEY]` — که `session_tenant()` **اول** آن را می‌خواند،
* و متغیرِ `app.tenant_id`ِ خودِ Postgres، که سیاستِ RLS رویش می‌نشیند.

یعنی بعد از خروج از بلوک، هم کد و هم پایگاه‌داده فکر می‌کردند مستأجرِ جاری
هنوز مستأجرِ **داخلی** است.

تا امروز نگزیده بود چون هیچ فراخوانی بعد از بلوک کارِ مستأجرمحور نمی‌کرد:
`_fulfill` بعدش فقط جدولِ **سراسریِ** سفارش را می‌نویسد، و دو فراخوانِ دیگر
حلقه‌اند و هر دور مقدار را بازنویسی می‌کنند. ولی «هنوز نگزیده» با «امن» یکی
نیست — و اولین کدی که بعد از بلوک یک کوئریِ مستأجرمحور بزند، آن را زیرِ
مستأجرِ اشتباه می‌زند.
"""
import uuid

from sqlalchemy import text

from app.tenant_context import session_tenant, tenant_scope


def _db_tenant(db) -> str:
    return db.execute(text("SELECT current_setting('app.tenant_id', true)")).scalar() or ""


def test_scope_restores_the_previous_tenant_on_exit(db, tenant_id):
    other = uuid.uuid4()
    assert session_tenant(db) == tenant_id
    assert _db_tenant(db) == str(tenant_id)

    with tenant_scope(db, other):
        assert session_tenant(db) == other
        assert _db_tenant(db) == str(other), "داخلِ بلوک باید مستأجرِ تازه بنشیند"

    #: و بیرونِ بلوک، همه‌چیز باید سرِ جای اولش برگردد — هم کد، هم پایگاه‌داده.
    assert session_tenant(db) == tenant_id, "زمینه‌ی کد برنگشت"
    assert _db_tenant(db) == str(tenant_id), "متغیرِ RLSِ پایگاه‌داده برنگشت"


def test_nested_scopes_unwind_in_order(db, tenant_id):
    a, b = uuid.uuid4(), uuid.uuid4()
    with tenant_scope(db, a):
        with tenant_scope(db, b):
            assert _db_tenant(db) == str(b)
        assert _db_tenant(db) == str(a), "بلوکِ تودرتو باید به لایه‌ی بیرونی برگردد"
    assert _db_tenant(db) == str(tenant_id)


def test_scope_restores_even_when_the_block_raises(db, tenant_id):
    """خطا در بلوک نباید نشست را زیرِ مستأجرِ اشتباه رها کند."""
    other = uuid.uuid4()
    try:
        with tenant_scope(db, other):
            raise RuntimeError("انفجارِ عمدی")
    except RuntimeError:
        pass
    assert session_tenant(db) == tenant_id
    assert _db_tenant(db) == str(tenant_id)
