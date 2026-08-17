"""پشتیبان‌گیری و بازیابیِ کاملِ داده‌ی یک کسب‌وکار.

**چرا عمومی و نه جدول‌به‌جدولِ دستی:** هر جدولِ مستأجرمحور یک ستونِ tenant_id دارد و
RLS خودکار به مستأجرِ جاری محدودش می‌کند ([tenancy.py](app/tenancy.py)). پس یک
`SELECT *` روی هر جدول فقط ردیف‌های همین کسب‌وکار را می‌دهد و یک `INSERT` هم با
`WITH CHECK` در همان مستأجر می‌ماند. این یعنی خروجی/ورودی می‌تواند بدونِ برشمردنِ
دستیِ ۴۰ جدول کار کند و با افزودنِ جدولِ تازه هم خودکار پوشش می‌گیرد.

**بازیابی = جایگزینیِ کامل (replace).** بازیابی ابتدا همه‌ی داده‌ی فعلیِ همین
کسب‌وکار را پاک می‌کند و بعد ردیف‌های فایلِ پشتیبان را می‌نشاند. هر دو کار در یک
تراکنش‌اند (get_db در پایان commit/rollback می‌کند)، پس اگر هر جای بازیابی خطا دهد
کلِ کار برمی‌گردد و داده‌ی قبلی دست‌نخورده می‌ماند — بازیابی هرگز داده را نیمه‌کاره
خراب نمی‌کند.

**فقط مالک.** خروجیِ کامل همه‌ی داده‌ی مالی است و بازیابی مخرب؛ هر دو فقط دستِ
نقشِ «owner» است، نه هر کارمندی با دسترسیِ مشاهده.
"""
import base64
import uuid
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.audit import PURGE_SETTING
from app.database import Base, get_db
from app.deps import Principal, get_principal
from app.tenancy import is_tenant_table

router = APIRouter(prefix="/api/backup", tags=["backup"])

#: نسخه‌ی قالبِ فایلِ پشتیبان. اگر روزی شکلِ خروجی عوض شد، بازیابی می‌تواند تشخیص دهد.
FORMAT = "cubita-backup"
FORMAT_VERSION = 1


def require_owner(principal: Principal = Depends(get_principal)) -> Principal:
    """فقط نقشِ مالکِ کسب‌وکار. get_principal زمینه‌ی مستأجر را هم ست می‌کند."""
    if principal.role.key != "owner":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "فقط مالکِ کسب‌وکار می‌تواند پشتیبان‌گیری یا بازیابی کند.",
        )
    return principal


def _skip_tables() -> set[str]:
    """جدول‌های مستأجرمحوری که یک جدولِ *سراسری* به آن‌ها کلیدِ خارجی دارد.

    نمونه: `roles` که `memberships` (سراسری) به آن اشاره می‌کند. این‌ها داده‌ی
    ساختاری‌اند (نقش‌ها هنگامِ ساختِ کسب‌وکار seed می‌شوند)، نه دفترِ کاربر؛ و چون
    جدولِ سراسریِ ارجاع‌دهنده پاک نمی‌شود، پاک‌کردنِ خودشان هم با خطای کلیدِ خارجی
    شکست می‌خورد. پس از پشتیبان/بازیابی کنار می‌مانند و دست‌نخورده باقی می‌مانند.
    """
    skip: set[str] = set()
    for table in Base.metadata.tables.values():
        if is_tenant_table(table.name):
            continue
        for fk in table.foreign_keys:
            if is_tenant_table(fk.column.table.name):
                skip.add(fk.column.table.name)
    return skip


def _tenant_tables_in_order() -> list[sa.Table]:
    """جدول‌های مستأجرمحور به ترتیبِ وابستگیِ کلیدِ خارجی (والد پیش از فرزند)."""
    skip = _skip_tables()
    return [t for t in Base.metadata.sorted_tables if is_tenant_table(t.name) and t.name not in skip]


def _ser(v):
    """مقدارِ پایگاه‌داده → چیزی که JSON بپذیرد و بدونِ اتلافِ دقت برگردد."""
    if v is None:
        return None
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, Decimal):
        return str(v)  # رشته نه float: مبلغِ مالی نباید از float رد شود
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {"__b64__": base64.b64encode(bytes(v)).decode("ascii")}
    return v  # str, int, float, bool, dict/list (JSONB)


def _de(col: sa.Column, v):
    """مقدارِ JSON → نوعِ درستِ ستون برای درج."""
    if v is None:
        return None
    if isinstance(v, dict) and "__b64__" in v:
        return base64.b64decode(v["__b64__"])
    t = col.type
    if isinstance(t, sa.Uuid):
        return uuid.UUID(v) if isinstance(v, str) else v
    if isinstance(t, sa.Numeric) and not isinstance(t, sa.Float):
        return Decimal(str(v))
    if isinstance(t, sa.DateTime):
        return datetime.fromisoformat(v) if isinstance(v, str) else v
    if isinstance(t, sa.Date):
        return date.fromisoformat(v) if isinstance(v, str) else v
    return v


def _selfref_columns(table: sa.Table) -> list[str]:
    """ستون‌هایی از جدول که به خودِ همان جدول کلیدِ خارجی دارند (مثلِ accounts.parent_id)."""
    cols: list[str] = []
    for col in table.columns:
        for fk in col.foreign_keys:
            if fk.column.table is table:
                cols.append(col.name)
                break
    return cols


def _order_selfref(table: sa.Table, rows: list[dict]) -> list[dict]:
    """ردیف‌ها را چنان مرتب می‌کند که هر ردیف پس از والدِ خودش بیاید (برای درجِ سلسله‌مراتبی)."""
    self_cols = _selfref_columns(table)
    if not self_cols:
        return rows
    pk = next(iter(table.primary_key.columns)).name
    by_id = {r.get(pk): r for r in rows}
    placed: list[dict] = []
    seen: set = set()

    def place(r: dict) -> None:
        rid = r.get(pk)
        if rid in seen:
            return
        seen.add(rid)  # پیش از بازگشت، تا حلقه‌ی احتمالی بی‌نهایت نشود
        for sc in self_cols:
            parent = r.get(sc)
            if parent is not None and parent in by_id:
                place(by_id[parent])
        placed.append(r)

    for r in rows:
        place(r)
    return placed


@router.get("/export")
def export_backup(principal: Principal = Depends(require_owner), db: Session = Depends(get_db)) -> dict:
    """کلِ داده‌ی این کسب‌وکار را در یک سندِ JSON برمی‌گرداند."""
    tables: dict[str, list[dict]] = {}
    for table in _tenant_tables_in_order():
        rows = db.execute(sa.select(table)).mappings().all()
        tables[table.name] = [{k: _ser(v) for k, v in row.items()} for row in rows]
    return {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "tenant_id": str(principal.tenant_id),
        "tenant_name": principal.membership.tenant.name,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "tables": tables,
    }


@router.post("/import")
def import_backup(
    payload: dict,
    principal: Principal = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict:
    """داده‌ی این کسب‌وکار را با محتوای فایلِ پشتیبان *جایگزین* می‌کند (پاک‌کردن سپس درج)."""
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فایلِ پشتیبان معتبر نیست.")
    tables_data = payload.get("tables")
    if not isinstance(tables_data, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فایلِ پشتیبان محتوای معتبری ندارد.")

    ordered = _tenant_tables_in_order()
    tenant_id = principal.tenant_id

    # پرچمِ purge تا بشود دفترِ حسابرسیِ فقط‌افزودنی را هم پاک کرد (به تراکنش محدود است).
    db.execute(text("SELECT set_config(:k, 'on', true)"), {"k": PURGE_SETTING})

    # ۱) پاک‌کردنِ داده‌ی فعلی — فرزند پیش از والد (ترتیبِ معکوس). RLS خودش به همین مستأجر محدود می‌کند.
    for table in reversed(ordered):
        db.execute(table.delete())

    # ۲) درجِ ردیف‌های پشتیبان — والد پیش از فرزند. tenant_id به مستأجرِ جاری بازنگاشت می‌شود
    #    تا حتی اگر فایل از کسب‌وکارِ دیگری (بازیابی روی حسابِ تازه) باشد، ایزوله بماند.
    restored: dict[str, int] = {}
    for table in ordered:
        raw = tables_data.get(table.name) or []
        if not raw:
            continue
        rows = _order_selfref(table, raw)
        colmap = {c.name: c for c in table.columns}
        params = []
        for r in rows:
            row = {k: _de(colmap[k], v) for k, v in r.items() if k in colmap}
            if "tenant_id" in colmap:
                row["tenant_id"] = tenant_id
            params.append(row)
        db.execute(table.insert(), params)
        restored[table.name] = len(params)

    return {"restored": True, "tables": restored, "total_rows": sum(restored.values())}
