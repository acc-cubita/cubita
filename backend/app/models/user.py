import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

# نقش‌های پیش‌فرض و اکشن‌های هر ماژول - permissions مثال: {"invoices": ["view", "create"], "accounting": ["view"]}
DEFAULT_ROLES: list[dict] = [
    {
        "key": "owner",
        "name": "مدیر/مالک",
        "permissions": {"*": ["view", "create", "update", "delete", "approve"]},
    },
    {
        "key": "accountant",
        "name": "حسابدار",
        "permissions": {
            "accounting": ["view", "create", "update", "approve"],
            "invoices": ["view", "create", "update"],
            "checks_bank": ["view", "create", "update"],
            "payroll": ["view"],
        },
    },
    {
        "key": "salesperson",
        "name": "فروشنده/صندوق‌دار",
        "permissions": {"invoices": ["view", "create"], "inventory": ["view"]},
    },
    {
        "key": "warehouse_keeper",
        "name": "انباردار",
        "permissions": {"inventory": ["view", "create", "update"]},
    },
    {
        "key": "payroll_officer",
        "name": "مسئول حقوق و دستمزد",
        "permissions": {"payroll": ["view", "create", "update", "approve"]},
    },
    {
        "key": "demo",
        "name": "دمو (فقط مشاهده)",
        # عمداً بدون wildcard: هر ماژول باید صراحتاً فهرست شود. قبلاً {"*": ["view"]} بود
        # که به‌طور ناخواسته ماژول billing را هم پوشش می‌داد و چون رمز این حساب روی سایت
        # عمومی نمایش داده می‌شود، داده‌ی هویتی همه‌ی مشتریان پولی قابل خواندن شده بود.
        "permissions": {
            "accounting": ["view"],
            "invoices": ["view"],
            "inventory": ["view"],
            "checks_bank": ["view"],
            "payroll": ["view"],
        },
    },
]


class Role(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_roles_tenant_key"),
    )

    key: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(100))
    permissions: Mapped[dict] = mapped_column(JSONB, default=dict)

    def has_permission(self, module: str, action: str) -> bool:
        for mod_key in (module, "*"):
            actions = self.permissions.get(mod_key)
            if actions and (action in actions or "*" in actions):
                return True
        return False


class User(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # نقش روی User نمی‌نشیند: یک نفر می‌تواند در یک کسب‌وکار حسابدار و در دیگری فقط
    # بیننده باشد، پس نقش خاصیتِ «عضویت» است نه خاصیتِ «کاربر».
    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")  # noqa: F821
