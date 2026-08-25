"""دسترسیِ اختصاصیِ کاربر: جایگزینیِ مجوزِ نقش، پاک‌سازیِ ورودی، و گاردِ آخرین مالک."""
import pytest
from fastapi import HTTPException

from app.models.tenant import Membership
from app.models.user import Role, User
from app.security import hash_password
from app.services import members as svc
from app.services.permissions import (
    ACTION_LABELS,
    ACTIONS_BY_MODULE,
    MODULE_KEYS,
    PERMISSION_MODULES,
    sanitize,
)


def _member(db, tenant_id, *, email: str, role_key: str = "accountant") -> Membership:
    user = User(name="همکار", email=email, hashed_password=hash_password("x" * 12))
    db.add(user)
    db.flush()
    role = db.query(Role).filter(Role.tenant_id == tenant_id, Role.key == role_key).first()
    m = Membership(user_id=user.id, tenant_id=tenant_id, role_id=role.id, status="active")
    db.add(m)
    db.flush()
    return m


# ── رجیستری ──────────────────────────────────────────────────────────────────


def test_registry_covers_every_action_label():
    for m in PERMISSION_MODULES:
        for a in m["actions"]:
            assert a in ACTION_LABELS, f"اکشن {a} برچسب فارسی ندارد"


def test_registry_keys_unique():
    keys = [m["key"] for m in PERMISSION_MODULES]
    assert len(keys) == len(set(keys))
    assert MODULE_KEYS == set(keys)


# ── پاک‌سازیِ ورودی ───────────────────────────────────────────────────────────


def test_sanitize_drops_unknown_module_and_action():
    out = sanitize({"invoices": ["view", "fly"], "not_a_module": ["view"]})
    assert out == {"invoices": ["view"]}


def test_sanitize_adds_view_when_missing():
    # ثبت بدونِ مشاهده یعنی کاربری که اجازه دارد بنویسد ولی صفحه‌ای برای دیدن ندارد.
    out = sanitize({"invoices": ["create"]})
    assert out["invoices"][0] == "view"
    assert "create" in out["invoices"]


def test_sanitize_rejects_wildcard():
    assert sanitize({"*": ["view", "create"]}) == {}


def test_sanitize_none_stays_none():
    assert sanitize(None) is None


def test_sanitize_respects_per_module_actions():
    # checks_bank اکشنِ delete ندارد.
    assert "delete" not in ACTIONS_BY_MODULE["checks_bank"]
    assert sanitize({"checks_bank": ["view", "delete"]}) == {"checks_bank": ["view"]}


# ── اثرِ واقعی روی دسترسی ────────────────────────────────────────────────────


def test_custom_permissions_replace_role_permissions(db, user, tenant_id):
    m = _member(db, tenant_id, email="p1@cubita.ir")
    # نقشِ حسابدار به‌طور پیش‌فرض روی accounting اجازه‌ی create دارد.
    assert svc.effective_permissions(m)["accounting"]

    svc.set_permissions(db, actor=user, tenant_id=tenant_id, membership_id=m.id, permissions={"invoices": ["view"]})
    db.refresh(m)
    eff = svc.effective_permissions(m)
    assert eff == {"invoices": ["view"]}
    # جایگزینی است نه ادغام: دسترسیِ حسابداری واقعاً گرفته شد.
    assert "accounting" not in eff


def test_clearing_custom_permissions_falls_back_to_role(db, user, tenant_id):
    m = _member(db, tenant_id, email="p2@cubita.ir")
    svc.set_permissions(db, actor=user, tenant_id=tenant_id, membership_id=m.id, permissions={"invoices": ["view"]})
    svc.set_permissions(db, actor=user, tenant_id=tenant_id, membership_id=m.id, permissions=None)
    db.refresh(m)
    assert m.permissions is None
    assert "accounting" in svc.effective_permissions(m)


def test_last_active_owner_cannot_be_restricted(db, user, tenant_id):
    owner = (
        db.query(Membership)
        .join(Role, Membership.role_id == Role.id)
        .filter(Membership.tenant_id == tenant_id, Role.key == "owner", Membership.status == "active")
        .first()
    )
    assert owner is not None
    with pytest.raises(HTTPException) as err:
        svc.set_permissions(db, actor=_other_user(db), tenant_id=tenant_id, membership_id=owner.id, permissions={"invoices": ["view"]})
    assert err.value.status_code == 409


def test_cannot_change_own_permissions(db, user, tenant_id):
    own = (
        db.query(Membership)
        .filter(Membership.tenant_id == tenant_id, Membership.user_id == user.id)
        .first()
    )
    with pytest.raises(HTTPException) as err:
        svc.set_permissions(
            db, actor=user, tenant_id=tenant_id, membership_id=own.id, permissions={"invoices": ["view"]}
        )
    assert err.value.status_code == 409


def test_invite_stores_custom_permissions(db, user, tenant_id):
    m, _token = svc.invite_member(
        db,
        tenant_id=tenant_id,
        inviter=user,
        email="p3@cubita.ir",
        name="کاربر محدود",
        role_key="accountant",
        permissions={"inventory": ["view", "update"]},
    )
    assert m.permissions == {"inventory": ["view", "update"]}


def test_invite_without_permissions_follows_role(db, user, tenant_id):
    m, _token = svc.invite_member(
        db, tenant_id=tenant_id, inviter=user, email="p4@cubita.ir", name="عادی", role_key="accountant"
    )
    assert m.permissions is None
    assert "accounting" in svc.effective_permissions(m)


# ── ارسالِ دوباره‌ی دعوت ──────────────────────────────────────────────────────


def test_resend_invite_issues_new_token(db, user, tenant_id):
    m, first = svc.invite_member(
        db, tenant_id=tenant_id, inviter=user, email="p5@cubita.ir", name="دعوتی", role_key="accountant"
    )
    _m2, second = svc.resend_invite(db, tenant_id=tenant_id, membership_id=m.id)
    assert second and second != first


def test_resend_invite_rejected_for_accepted_member(db, user, tenant_id):
    m = _member(db, tenant_id, email="p6@cubita.ir")  # status=active
    with pytest.raises(HTTPException) as err:
        svc.resend_invite(db, tenant_id=tenant_id, membership_id=m.id)
    assert err.value.status_code == 400


# ── فهرستِ نقش‌ها ─────────────────────────────────────────────────────────────


def test_list_roles_counts_members(db, user, tenant_id):
    _member(db, tenant_id, email="p7@cubita.ir", role_key="accountant")
    rows = svc.list_roles(db, tenant_id)
    by_key = {r.key: n for r, n in rows}
    assert by_key["accountant"] >= 1
    assert by_key["owner"] >= 1
    assert all(isinstance(r.permissions, dict) for r, _ in rows)


def _other_user(db) -> User:
    """کاربری غیر از فیکسچرِ `user` — برای سنجشِ گاردی که به خودِ کاربر ربط ندارد."""
    u = User(name="مدیر دیگر", email="other-admin@cubita.ir", hashed_password=hash_password("x" * 12))
    db.add(u)
    db.flush()
    return u
