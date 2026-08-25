"""مدیریت کاربران کسب‌وکار.

مجوز همه‌ی این مسیرها `users` است و هیچ نقش پیش‌فرضی جز «مالک» آن را ندارد (فقط
مالک wildcard دارد). این عمدی است: دعوت کاربر یعنی دادن دسترسی به دفتر مالی، و
تنزل ناخواسته‌ی این تصمیم به «حسابدار» چیزی است که باید در diff دیده شود.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.tenant import Membership, Tenant
from app.schemas.members import (
    ChangeRoleIn,
    InviteIn,
    InviteOut,
    MemberListOut,
    MemberOut,
    PermissionActionOut,
    PermissionModuleOut,
    RoleOut,
    SeatsOut,
    SetPermissionsIn,
    SetStatusIn,
)
from app.services.permissions import ACTION_LABELS, PERMISSION_MODULES
from app.services import members as svc
from app.services.mailer import send_invitation
from app.services.tokens import INVITE_DAYS

router = APIRouter(prefix="/api/members", tags=["members"])


def _out(membership: Membership, me_user_id: UUID) -> MemberOut:
    return MemberOut(
        id=membership.id,
        user_id=membership.user_id,
        name=membership.user.name,
        email=membership.user.email,
        role_key=membership.role.key,
        role_name=membership.role.name,
        status=membership.status,
        is_me=(membership.user_id == me_user_id),
        permissions=svc.effective_permissions(membership),
        custom_permissions=membership.permissions is not None,
    )


@router.get("", response_model=MemberListOut)
def list_members(
    _perm=Depends(require_permission(svc.PERMISSION_MODULE, "view")),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    tenant = db.get(Tenant, principal.tenant_id)
    rows = svc.list_members(db, principal.tenant_id)
    return MemberListOut(
        members=[_out(m, principal.user.id) for m in rows],
        seats=SeatsOut(
            used=svc.seats_used(db, principal.tenant_id),
            limit=tenant.max_users if tenant else None,
        ),
    )


@router.get("/permission-modules", response_model=list[PermissionModuleOut])
def permission_modules(
    _perm=Depends(require_permission(svc.PERMISSION_MODULE, "view")),
):
    """فهرستِ ماژول‌های مجوز و اکشن‌های هرکدام — پایه‌ی جدولِ انتخابِ دسترسی."""
    return [
        PermissionModuleOut(
            key=m["key"],
            label=m["label"],
            hint=m.get("hint"),
            actions=[PermissionActionOut(key=a, label=ACTION_LABELS[a]) for a in m["actions"]],
        )
        for m in PERMISSION_MODULES
    ]


@router.get("/roles", response_model=list[RoleOut])
def list_roles(
    _perm=Depends(require_permission(svc.PERMISSION_MODULE, "view")),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """نقش‌های واقعیِ این کسب‌وکار، با اجازه‌ها و شمارِ اعضا."""
    return [
        RoleOut(key=r.key, name=r.name, permissions=r.permissions or {}, member_count=n)
        for r, n in svc.list_roles(db, principal.tenant_id)
    ]


@router.post("/invite", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
def invite(
    data: InviteIn,
    _perm=Depends(require_permission(svc.PERMISSION_MODULE, "create")),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    membership, raw_token = svc.invite_member(
        db,
        tenant_id=principal.tenant_id,
        inviter=principal.user,
        email=data.email,
        name=data.name,
        role_key=data.role_key,
        permissions=data.permissions,
    )
    sent = send_invitation(
        to=membership.user.email,
        tenant_name=principal.membership.tenant.name,
        inviter_name=principal.user.name,
        token=raw_token,
        valid_days=INVITE_DAYS,
    )
    return InviteOut(member=_out(membership, principal.user.id), email_sent=sent)


@router.post("/{membership_id}/resend-invite", response_model=InviteOut)
def resend_invite(
    membership_id: UUID,
    _perm=Depends(require_permission(svc.PERMISSION_MODULE, "create")),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """لینکِ دعوتِ تازه برای کسی که هنوز نپذیرفته — مثلاً ایمیل را گم کرده."""
    membership, raw_token = svc.resend_invite(
        db, tenant_id=principal.tenant_id, membership_id=membership_id
    )
    sent = send_invitation(
        to=membership.user.email,
        tenant_name=principal.membership.tenant.name,
        inviter_name=principal.user.name,
        token=raw_token,
        valid_days=INVITE_DAYS,
    )
    return InviteOut(member=_out(membership, principal.user.id), email_sent=sent)


@router.patch("/{membership_id}/permissions", response_model=MemberOut)
def set_permissions(
    membership_id: UUID,
    data: SetPermissionsIn,
    _perm=Depends(require_permission(svc.PERMISSION_MODULE, "update")),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """دسترسیِ اختصاصیِ یک کاربر. `permissions: null` یعنی برگرد به مجوزِ نقش."""
    membership = svc.set_permissions(
        db,
        tenant_id=principal.tenant_id,
        membership_id=membership_id,
        permissions=data.permissions,
        actor=principal.user,
    )
    return _out(membership, principal.user.id)


@router.patch("/{membership_id}/role", response_model=MemberOut)
def change_role(
    membership_id: UUID,
    data: ChangeRoleIn,
    _perm=Depends(require_permission(svc.PERMISSION_MODULE, "update")),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    membership = svc.change_role(
        db, tenant_id=principal.tenant_id, membership_id=membership_id, role_key=data.role_key
    )
    return _out(membership, principal.user.id)


@router.patch("/{membership_id}/status", response_model=MemberOut)
def set_status(
    membership_id: UUID,
    data: SetStatusIn,
    _perm=Depends(require_permission(svc.PERMISSION_MODULE, "update")),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """غیرفعال‌سازی به‌جای حذف.

    ردیف عضویت هرگز پاک نمی‌شود چون اسناد مالی به کاربر ارجاع می‌دهند (`created_by`)
    و حذف کاربر یعنی سند بی‌صاحب — که برای نرم‌افزار حسابداری قابل قبول نیست.
    """
    membership = svc.set_member_status(
        db,
        tenant_id=principal.tenant_id,
        membership_id=membership_id,
        active=data.active,
        actor=principal.user,
    )
    return _out(membership, principal.user.id)
