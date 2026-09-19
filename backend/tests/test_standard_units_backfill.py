"""پُرکردنِ واحدهای استاندارد در مهاجرتِ ۰۱۶۷ — روی همان وضعیتی که تولید داشت.

مهاجرتِ ۰۱۱۸ واحدها را از خودِ داده ساخت و فهرستِ استاندارد را فقط به
کسب‌وکارِ **بی‌کالا** داد. نتیجه: کسب‌وکارِ واقعی سه واحد داشت، چون سه نوشتار
روی کالاهایش بود. ۰۱۶۷ همان فهرست را به هر کسب‌وکاری می‌دهد که نداردش.

این فایل **خودِ SQLِ مهاجرت** را اجرا می‌کند (`_BACKFILL`)، نه رونوشتش — الگوی
`0158`. اگر آن SQL خراب شود، این تست‌ها می‌شکنند.
"""
import importlib.util
from pathlib import Path

import sqlalchemy as sa

from app.models.inventory import UnitOfMeasure
from app.seed import STANDARD_UNITS

_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0167_standard_units_backfill.py"
)


def _backfill_sql() -> str:
    spec = importlib.util.spec_from_file_location("_m0167", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._BACKFILL


def _run(db) -> None:
    """همان کاری که مهاجرت می‌کند، با همان گاردِ RLS."""
    from app.migration_utils import rls_disabled

    conn = db.connection()
    with rls_disabled(conn, ["units_of_measure", "tenants", "items"]):
        conn.execute(sa.text(_backfill_sql()), {"names": list(STANDARD_UNITS)})


def _names(db, tenant_id) -> set[str]:
    rows = db.execute(
        sa.text("SELECT name FROM units_of_measure WHERE tenant_id = :t"), {"t": tenant_id}
    )
    return {r[0] for r in rows}


# ───────────────────────────── فهرستِ خودِ داده ─────────────────────────────


def test_the_standard_list_is_long_and_has_no_duplicates():
    """نامِ واحد در هر کسب‌وکار یکتاست؛ تکراری در فهرست یعنی مهاجرت می‌شکند."""
    assert len(STANDARD_UNITS) == len(set(STANDARD_UNITS))
    assert len(STANDARD_UNITS) > 300


def test_every_name_fits_the_column():
    """ستون `String(20)` است — نامِ بلندتر بی‌صدا بریده یا رد می‌شود."""
    too_long = [u for u in STANDARD_UNITS if len(u) > 20]
    assert too_long == []


def test_the_nineteen_that_existed_before_are_still_there():
    """فهرستِ تازه جایگزین است، نه جانشین: هیچ واحدِ قبلی نباید گم شود."""
    before = (
        "عدد", "متر", "متر مربع", "متر مکعب", "سانتی‌متر", "کیلوگرم", "گرم",
        "تن", "لیتر", "بسته", "کارتن", "جعبه", "جفت", "دست", "رول", "طاقه",
        "شاخه", "عدل", "ساعت",
    )
    assert set(before) <= set(STANDARD_UNITS)


# ──────────────────────────────── پُرکردن ────────────────────────────────


def test_backfill_gives_a_business_the_whole_list(db, user, tenant_id):
    """هسته‌ی مهاجرت: کسب‌وکاری که چند واحد دارد، بقیه را هم می‌گیرد."""
    _run(db)
    assert set(STANDARD_UNITS) <= _names(db, tenant_id)


def test_running_it_twice_changes_nothing(db, user, tenant_id):
    """`NOT EXISTS` یعنی اجرای دوباره تکراری نمی‌سازد.

    مهم است چون `uq_units_of_measure_tenant_name` در اجرای دومِ بی‌گارد
    مهاجرت را با خطا متوقف می‌کرد.
    """
    _run(db)
    first = _names(db, tenant_id)
    _run(db)
    assert _names(db, tenant_id) == first


def test_a_unit_the_user_made_is_not_touched(db, user, tenant_id):
    """واحدِ دست‌ساز باید سرِ جایش بماند — پرکردن، بازنویسی نیست."""
    db.add(UnitOfMeasure(tenant_id=tenant_id, name="واحدِ من", name2="یادداشت"))
    db.flush()
    _run(db)
    mine = (
        db.query(UnitOfMeasure)
        .filter(UnitOfMeasure.tenant_id == tenant_id, UnitOfMeasure.name == "واحدِ من")
        .one()
    )
    assert mine.name2 == "یادداشت"


def test_without_the_rls_guard_it_does_not_work(db, user, tenant_id):
    """**چرا `rls_disabled` اجباری است.**

    `units_of_measure` FORCE RLS دارد و سیاستش `app.tenant_id` را می‌خواند —
    که وسطِ مهاجرت وجود ندارد. بدونِ گارد، نوشتن برای *بقیه‌ی* کسب‌وکارها
    ممکن نیست: یا سیاست ردش می‌کند، یا `SELECT FROM tenants` صفر ردیف
    می‌بیند و مهاجرت **با موفقیت** تمام می‌شود بی‌آنکه چیزی نوشته باشد.

    این‌جا حالتِ اول رخ می‌دهد چون نشستِ تست یک مستأجرِ واقعی دارد؛ روی
    تولید حالتِ دوم. هر دو یک معنی دارند: بدونِ گارد کار نمی‌کند.
    """
    conn = db.connection()
    before = _names(db, tenant_id)
    try:
        conn.execute(sa.text(_backfill_sql()), {"names": list(STANDARD_UNITS)})
    except Exception:
        db.rollback()
        return  # سیاست ردش کرد — همان چیزی که گارد برایش هست
    assert _names(db, tenant_id) == before, "بدونِ گارد نباید چیزی نوشته شود"
