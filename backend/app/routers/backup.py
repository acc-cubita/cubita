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

**انتقال از ابر به سرورِ سازمانی هم همین فایل است.** ولی ۱۰۱ ستونِ دفتر («ثبت‌کننده»،
«تأییدکننده»…) به جدولِ سراسریِ `users` کلیدِ خارجی دارند، و روی سرورِ تازه آن کاربرها
نیستند. پس خروجی فهرستِ کاربرانِ ارجاع‌شده را هم دارد (نام، ایمیل، نقش — **بدونِ hashِ
رمز**)، و ورودیِ سازمانی آن‌ها را به‌صورتِ عضوِ «غیرفعال» می‌سازد: مالک هر کدام را که
می‌خواهد فعال می‌کند و کدِ بازنشانی می‌دهد تا رمزِ خودش را بگذارد. کاربری که ایمیلش روی
سرور هست (معمولاً خودِ مالک) به همان حساب نگاشته می‌شود. تنظیماتِ حسابداریِ کسب‌وکار
(پهنای کدِ حساب، کنترلِ تفصیلی…) هم همراه می‌آید، چون دفتر بی آن‌ها معنای دیگری می‌دهد.
"""
import base64
import secrets
import uuid
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.audit import PURGE_SETTING
from app.config import get_settings
from app.database import Base, get_db
from app.deps import Principal, get_principal
from app.models.tenant import Membership, Tenant
from app.models.user import Role, User
from app.security import hash_password
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


#: تنظیماتِ حسابداریِ کسب‌وکار که روی جدولِ سراسریِ `tenants` نشسته‌اند و با دفتر جابه‌جا
#: می‌شوند. نام، نوع، سقفِ کاربر، آزمایشی و ماژول‌های اعطایی عمداً نیستند: آن‌ها را نصب
#: و مجوزِ مقصد تعیین می‌کند، نه فایلِ پشتیبان.
TENANT_SETTINGS = (
    "industry",
    "trade",
    "enabled_modules",
    "account_code_widths",
    "tafsili_enforcement",
    "cheque_number_control",
    "sales_invoice_posting",
)

#: نقش‌هایی که با دفتر منتقل نمی‌شوند: حسابرسِ گماشته مهمانِ کوبیتاست و «دمو» حسابِ نمایشی.
_UNMIGRATED_ROLES = {"auditor", "demo"}


def _user_fk_columns(table: sa.Table) -> list[str]:
    return [c.name for c in table.columns if any(fk.column.table.name == "users" for fk in c.foreign_keys)]


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
    referenced: set[uuid.UUID] = set()
    for table in _tenant_tables_in_order():
        rows = db.execute(sa.select(table)).mappings().all()
        user_cols = _user_fk_columns(table)
        for row in rows:
            referenced.update(row[c] for c in user_cols if row[c] is not None)
        tables[table.name] = [{k: _ser(v) for k, v in row.items()} for row in rows]
    tenant = db.get(Tenant, principal.tenant_id)
    return {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "tenant_id": str(principal.tenant_id),
        "tenant_name": principal.membership.tenant.name,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "tenant_settings": {k: _ser(getattr(tenant, k)) for k in TENANT_SETTINGS},
        "users": _export_users(db, principal.tenant_id, referenced),
        "tables": tables,
    }


def _export_users(db: Session, tenant_id: uuid.UUID, referenced: set[uuid.UUID]) -> list[dict]:
    """اعضای این کسب‌وکار به‌اضافه‌ی هر کاربرِ دیگری که دفتر به او ارجاع دارد (کارمندِ رفته).

    hashِ رمز عمداً نیست: فایلِ پشتیبان دستِ مالک است و مالک نباید hashِ رمزِ کارمندانش را
    داشته باشد. روی مقصد هر کس با کدِ بازنشانی رمزِ تازه‌اش را خودش می‌گذارد.
    """
    members = (
        db.query(Membership, Role.key)
        .join(Role, Role.id == Membership.role_id)
        .filter(Membership.tenant_id == tenant_id)
        .all()
    )
    by_user = {m.user_id: (m, key) for m, key in members}
    ids = referenced | set(by_user)
    if not ids:
        return []
    out: list[dict] = []
    for user in db.query(User).filter(User.id.in_(ids)).all():
        membership, role_key = by_user.get(user.id, (None, None))
        out.append(
            {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "role_key": role_key,
                "member_status": membership.status if membership else None,
                "permissions": membership.permissions if membership else None,
            }
        )
    return out


def _import_users(db: Session, principal: Principal, users: list) -> dict[uuid.UUID, uuid.UUID]:
    """سرورِ سازمانی: کاربرانِ فایل را می‌سازد و نگاشتِ شناسه‌ی ابر → شناسه‌ی محلی را می‌دهد.

    - همان شناسه روی سرور هست (بازیابیِ دوباره) → همان.
    - همان ایمیل هست (معمولاً خودِ مالک) → به آن حساب نگاشته می‌شود.
    - وگرنه با همان شناسه ساخته می‌شود، با رمزِ تصادفیِ دورانداختنی.

    هر عضوِ این کسب‌وکار عضویتِ «غیرفعال» می‌گیرد: صندلیِ مجوز مصرف نمی‌کند و تا مالک
    خودش فعالش نکند و کدِ بازنشانی ندهد، کسی با آن وارد نمی‌شود.
    """
    mapping: dict[uuid.UUID, uuid.UUID] = {}
    roles = {r.key: r for r in db.query(Role).filter(Role.tenant_id == principal.tenant_id).all()}
    for entry in users:
        if not isinstance(entry, dict) or not entry.get("id") or not entry.get("email"):
            continue
        cloud_id = uuid.UUID(str(entry["id"]))
        email = str(entry["email"]).strip().lower()
        user = db.get(User, cloud_id) or db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                id=cloud_id,
                email=email,
                name=str(entry.get("name") or email)[:100],
                hashed_password=hash_password(secrets.token_urlsafe(32)),
            )
            db.add(user)
            db.flush()
        mapping[cloud_id] = user.id

        role = roles.get(entry.get("role_key") or "")
        if role is None or role.key in _UNMIGRATED_ROLES:
            continue
        exists = (
            db.query(Membership)
            .filter(Membership.tenant_id == principal.tenant_id, Membership.user_id == user.id)
            .first()
        )
        if exists is None:
            db.add(
                Membership(
                    user_id=user.id,
                    tenant_id=principal.tenant_id,
                    role_id=role.id,
                    status="disabled",
                    permissions=entry.get("permissions"),
                )
            )
    db.flush()
    return mapping


def _missing_users(db: Session, ordered: list[sa.Table], tables_data: dict, mapping: dict) -> int:
    """چند کاربرِ ارجاع‌شده روی این سرور نیستند — فایلِ قدیمی که بخشِ `users` ندارد."""
    wanted: set[uuid.UUID] = set()
    for table in ordered:
        cols = _user_fk_columns(table)
        if not cols:
            continue
        for r in tables_data.get(table.name) or []:
            for c in cols:
                if r.get(c):
                    raw = uuid.UUID(str(r[c]))
                    wanted.add(mapping.get(raw, raw))
    if not wanted:
        return 0
    found = db.query(func.count(User.id)).filter(User.id.in_(wanted)).scalar() or 0
    return len(wanted) - found


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

    user_map: dict[uuid.UUID, uuid.UUID] = {}
    if get_settings().is_enterprise:
        user_map = _import_users(db, principal, payload.get("users") or [])
        if _missing_users(db, ordered, tables_data, user_map):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "این فایلِ پشتیبان فهرستِ کاربران را ندارد (از نسخه‌ی قدیمی‌ترِ کوبیتاست). "
                "از حسابِ ابری یک پشتیبانِ تازه بگیرید و همان را اینجا بازیابی کنید.",
            )
        settings_in = payload.get("tenant_settings")
        tenant = db.get(Tenant, tenant_id)
        if isinstance(settings_in, dict) and tenant is not None:
            for key in TENANT_SETTINGS:
                if key in settings_in:
                    setattr(tenant, key, settings_in[key])

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
        user_cols = _user_fk_columns(table) if user_map else []
        params = []
        for r in rows:
            row = {k: _de(colmap[k], v) for k, v in r.items() if k in colmap}
            if "tenant_id" in colmap:
                row["tenant_id"] = tenant_id
            for c in user_cols:
                if row.get(c) is not None:
                    row[c] = user_map.get(row[c], row[c])
            params.append(row)
        db.execute(table.insert(), params)
        restored[table.name] = len(params)

    return {"restored": True, "tables": restored, "total_rows": sum(restored.values())}
