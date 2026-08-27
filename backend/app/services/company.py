"""سرویسِ موجودیت‌های «شرکت» — گروهِ طرف‌حساب، محلِ جغرافیایی، فردِ مرتبط.

سه قاعده‌ی مشترک در همه‌شان:

* **حذف داده را یتیم نمی‌کند.** گروه یا محلی که طرف‌حساب دارد حذف نمی‌شود (۴۰۹)؛
  راهِ درست «غیرفعال‌کردن» است. وگرنه با `SET NULL` دسته‌بندیِ صدها طرف‌حساب با یک
  کلیک بی‌صدا پاک می‌شد.
* **درخت حلقه برنمی‌دارد.** پدرِ یک محل نمی‌تواند خودش یا یکی از فرزندانش باشد؛
  بدونِ این بررسی، محاسبه‌ی مسیر تا ابد می‌چرخد.
* **«نفرِ اصلی» یکی است.** با علامت‌زدنِ یک نفر، بقیه‌ی افرادِ همان طرف‌حساب از
  حالتِ اصلی درمی‌آیند — وگرنه «با چه کسی تماس بگیرم؟» دو جواب پیدا می‌کند.
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company import ContactGroup, GeoLocation, RelatedPerson
from app.models.inventory import Contact
from app.models.user import User
from app.schemas.company import ContactGroupIn, GeoLocationIn, RelatedPersonIn

# ── گروهِ طرف‌حساب ────────────────────────────────────────────────────────────


def _group_counts(db: Session) -> dict[UUID, int]:
    rows = (
        db.query(Contact.group_id, func.count(Contact.id))
        .filter(Contact.group_id.isnot(None))
        .group_by(Contact.group_id)
        .all()
    )
    return {gid: n for gid, n in rows}


def list_groups(db: Session, *, include_inactive: bool = True) -> list[dict]:
    query = db.query(ContactGroup)
    if not include_inactive:
        query = query.filter(ContactGroup.is_active.is_(True))
    counts = _group_counts(db)
    rows = query.order_by(ContactGroup.is_active.desc(), ContactGroup.code, ContactGroup.name).all()
    return [
        {
            "id": g.id,
            "name": g.name,
            "code": g.code,
            "notes": g.notes,
            "is_active": g.is_active,
            "contact_count": counts.get(g.id, 0),
        }
        for g in rows
    ]


def get_group(db: Session, group_id: UUID) -> ContactGroup:
    group = db.get(ContactGroup, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "گروه پیدا نشد")
    return group


def create_group(db: Session, data: ContactGroupIn, user: User) -> dict:
    group = ContactGroup(
        code=data.code.strip(),
        name=data.name.strip(),
        notes=data.notes,
        is_active=data.is_active,
        created_by_id=user.id,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return {**_as_group(group), "contact_count": 0}


def update_group(db: Session, group_id: UUID, data: ContactGroupIn) -> dict:
    group = get_group(db, group_id)
    group.code = data.code.strip()
    group.name = data.name.strip()
    group.notes = data.notes
    group.is_active = data.is_active
    db.commit()
    db.refresh(group)
    return {**_as_group(group), "contact_count": _group_counts(db).get(group.id, 0)}


def delete_group(db: Session, group_id: UUID) -> None:
    group = get_group(db, group_id)
    used = db.query(Contact).filter(Contact.group_id == group.id).count()
    if used:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"این گروه روی {used} طرف‌حساب نشسته است؛ به‌جای حذف آن را غیرفعال کنید.",
        )
    db.delete(group)
    db.commit()


def _as_group(g: ContactGroup) -> dict:
    return {
        "id": g.id,
        "name": g.name,
        "code": g.code,
        "notes": g.notes,
        "is_active": g.is_active,
    }


# ── محلِ جغرافیایی ───────────────────────────────────────────────────────────


def _geo_counts(db: Session) -> dict[UUID, int]:
    rows = (
        db.query(Contact.geo_location_id, func.count(Contact.id))
        .filter(Contact.geo_location_id.isnot(None))
        .group_by(Contact.geo_location_id)
        .all()
    )
    return {gid: n for gid, n in rows}


def _paths(rows: list[GeoLocation]) -> dict[UUID, str]:
    """مسیرِ خوانا برای هر گره: «ایران / تهران / تهران / منطقه ۳».

    یک‌بار روی کلِ مجموعه ساخته می‌شود، نه با یک کوئری به‌ازای هر ردیف. `seen`
    نگهبانِ حلقه است — قید و سرویس جلوی حلقه را می‌گیرند ولی داده‌ی قدیمی یا دستکاری‌شده
    نباید نمایشِ فهرست را قفل کند.
    """
    by_id = {r.id: r for r in rows}
    out: dict[UUID, str] = {}
    for row in rows:
        parts: list[str] = []
        node: GeoLocation | None = row
        seen: set[UUID] = set()
        while node is not None and node.id not in seen:
            seen.add(node.id)
            parts.append(node.name)
            node = by_id.get(node.parent_id) if node.parent_id else None
        out[row.id] = " / ".join(reversed(parts))
    return out


def list_geo(db: Session, *, include_inactive: bool = True) -> list[dict]:
    query = db.query(GeoLocation)
    if not include_inactive:
        query = query.filter(GeoLocation.is_active.is_(True))
    rows = query.all()
    paths = _paths(rows)
    counts = _geo_counts(db)
    rows.sort(key=lambda r: paths[r.id])
    return [
        {
            "id": r.id,
            "name": r.name,
            "kind": r.kind,
            "code": r.code,
            "parent_id": r.parent_id,
            "is_active": r.is_active,
            "path": paths[r.id],
            "contact_count": counts.get(r.id, 0),
        }
        for r in rows
    ]


def get_geo(db: Session, geo_id: UUID) -> GeoLocation:
    row = db.get(GeoLocation, geo_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محلِ جغرافیایی پیدا نشد")
    return row


def _assert_parent_ok(db: Session, *, parent_id: UUID | None, self_id: UUID | None) -> None:
    if parent_id is None:
        return
    parent = db.get(GeoLocation, parent_id)
    if parent is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "محلِ والدِ انتخاب‌شده معتبر نیست")
    if self_id is None:
        return
    # بالا رفتن از والد: اگر به خودمان رسیدیم، این انتساب حلقه می‌سازد.
    node: GeoLocation | None = parent
    seen: set[UUID] = set()
    while node is not None and node.id not in seen:
        if node.id == self_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "محل نمی‌تواند زیرمجموعه‌ی خودش یا فرزندانش شود"
            )
        seen.add(node.id)
        node = db.get(GeoLocation, node.parent_id) if node.parent_id else None


def create_geo(db: Session, data: GeoLocationIn, user: User) -> dict:
    _assert_parent_ok(db, parent_id=data.parent_id, self_id=None)
    row = GeoLocation(
        name=data.name.strip(),
        kind=data.kind,
        code=data.code.strip(),
        parent_id=data.parent_id,
        is_active=data.is_active,
        created_by_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _one_geo(db, row)


def update_geo(db: Session, geo_id: UUID, data: GeoLocationIn) -> dict:
    row = get_geo(db, geo_id)
    _assert_parent_ok(db, parent_id=data.parent_id, self_id=row.id)
    row.name = data.name.strip()
    row.kind = data.kind
    row.code = data.code.strip()
    row.parent_id = data.parent_id
    row.is_active = data.is_active
    db.commit()
    db.refresh(row)
    return _one_geo(db, row)


def delete_geo(db: Session, geo_id: UUID) -> None:
    row = get_geo(db, geo_id)
    kids = db.query(GeoLocation).filter(GeoLocation.parent_id == row.id).count()
    if kids:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"این محل {kids} زیرمجموعه دارد؛ اول آن‌ها را جابه‌جا کنید."
        )
    used = db.query(Contact).filter(Contact.geo_location_id == row.id).count()
    if used:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"این محل روی {used} طرف‌حساب نشسته است؛ به‌جای حذف آن را غیرفعال کنید.",
        )
    db.delete(row)
    db.commit()


def _one_geo(db: Session, row: GeoLocation) -> dict:
    all_rows = db.query(GeoLocation).all()
    paths = _paths(all_rows)
    return {
        "id": row.id,
        "name": row.name,
        "kind": row.kind,
        "code": row.code,
        "parent_id": row.parent_id,
        "is_active": row.is_active,
        "path": paths.get(row.id, row.name),
        "contact_count": _geo_counts(db).get(row.id, 0),
    }


# ── فردِ مرتبط ───────────────────────────────────────────────────────────────


def list_persons(db: Session, *, contact_id: UUID | None = None, include_inactive: bool = True) -> list[dict]:
    query = db.query(RelatedPerson, Contact.name).join(Contact, Contact.id == RelatedPerson.contact_id)
    if contact_id is not None:
        query = query.filter(RelatedPerson.contact_id == contact_id)
    if not include_inactive:
        query = query.filter(RelatedPerson.is_active.is_(True))
    rows = query.order_by(
        Contact.name, RelatedPerson.is_primary.desc(), RelatedPerson.name
    ).all()
    return [{**_as_person(p), "contact_name": name} for p, name in rows]


def get_person(db: Session, person_id: UUID) -> RelatedPerson:
    row = db.get(RelatedPerson, person_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فردِ مرتبط پیدا نشد")
    return row


def _demote_others(db: Session, *, contact_id: UUID, keep_id: UUID | None) -> None:
    """«نفرِ اصلی» در هر طرف‌حساب یکی است.

    شیء‌به‌شیء و نه UPDATEِ گروهی: به‌روزرسانیِ گروهی نقشه‌ی هویتِ session را کهنه
    می‌گذارد و نوشتنِ بعدی روی همان ردیف بی‌اثر می‌شود.
    """
    others = (
        db.query(RelatedPerson)
        .filter(RelatedPerson.contact_id == contact_id, RelatedPerson.is_primary.is_(True))
        .all()
    )
    for other in others:
        if keep_id is None or other.id != keep_id:
            other.is_primary = False


def _assert_contact(db: Session, contact_id: UUID) -> Contact:
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "طرف‌حسابِ انتخاب‌شده معتبر نیست")
    return contact


def create_person(db: Session, data: RelatedPersonIn, user: User) -> dict:
    contact = _assert_contact(db, data.contact_id)
    row = RelatedPerson(
        contact_id=data.contact_id,
        name=data.name.strip(),
        role=data.role.strip(),
        phone=data.phone.strip(),
        email=data.email.strip(),
        is_primary=data.is_primary,
        is_active=data.is_active,
        notes=data.notes,
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    if row.is_primary:
        _demote_others(db, contact_id=row.contact_id, keep_id=row.id)
    db.commit()
    db.refresh(row)
    return {**_as_person(row), "contact_name": contact.name}


def update_person(db: Session, person_id: UUID, data: RelatedPersonIn) -> dict:
    row = get_person(db, person_id)
    contact = _assert_contact(db, data.contact_id)
    row.contact_id = data.contact_id
    row.name = data.name.strip()
    row.role = data.role.strip()
    row.phone = data.phone.strip()
    row.email = data.email.strip()
    row.is_primary = data.is_primary
    row.is_active = data.is_active
    row.notes = data.notes
    db.flush()
    if row.is_primary:
        _demote_others(db, contact_id=row.contact_id, keep_id=row.id)
    db.commit()
    db.refresh(row)
    return {**_as_person(row), "contact_name": contact.name}


def delete_person(db: Session, person_id: UUID) -> None:
    db.delete(get_person(db, person_id))
    db.commit()


def _as_person(p: RelatedPerson) -> dict:
    return {
        "id": p.id,
        "contact_id": p.contact_id,
        "name": p.name,
        "role": p.role,
        "phone": p.phone,
        "email": p.email,
        "is_primary": p.is_primary,
        "is_active": p.is_active,
        "notes": p.notes,
    }
