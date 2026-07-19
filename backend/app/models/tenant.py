"""مستأجر، عضویت، و ادمین پلتفرم.

تفکیک عمدی «صفحه‌ی کنترل» از «صفحه‌ی داده»:

- Tenant/Membership/PlatformAdmin سراسری‌اند و RLS ندارند.
- کاربر هم سراسری است، چون یک حسابدار مستقل می‌تواند دفتر چند کسب‌وکار را ببرد.
  تعلقش با Membership بیان می‌شود، نه با ستونی روی خودش. این از همین ابتدا انجام
  می‌شود چون افزودن رابطه‌ی چند‌به‌چند بعد از داشتن مشتری یعنی مهاجرت دوباره‌ی auth.
- PlatformAdmin عمداً یک نقش در RBAC مستأجر نیست. ریشه‌ی نشتی قبلی همین بود که
  کنترل‌پنل فروش و دفتر مشتری یک سیستم مجوز مشترک داشتند و یک نقش با wildcard
  به داده‌ی همه‌ی مشتری‌ها رسید.
"""
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class TenantMixin:
    """ستون مستأجر. کنار UUIDPKMixin روی هر مدل مستأجرمحور می‌نشیند.

    اعلانی بودنش عمدی است: افزودن مستأجر به مدل جدید یک خط است و *نبودش* در
    بازبینی دیده می‌شود — و اگر دیده هم نشود، تست introspection می‌گیردش.
    """

    @declared_attr
    def tenant_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )


class Tenant(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | suspended | cancelled

    #: سقف کاربران. NULL یعنی نامحدود (پلن سازمانی).
    #:
    #: این مقدار موقع ساخت مستأجر از `Plan.max_users` گرفته می‌شود و بعد از آن ثابت
    #: می‌ماند. **این هنوز اشتراک نیست:** جدول subscriptions وجود ندارد، پس ارتقای
    #: پلن سقف را خودکار بالا نمی‌برد و باید دستی عوض شود. سقف ثابتِ قابل اعمال از
    #: `Plan.max_users`ی که تعریف شده بود ولی هیچ‌جا خوانده نمی‌شد بهتر است، چون
    #: بدون هیچ سقفی دعوت یک منبع نامحدود است.
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="tenant")


class Membership(UUIDPKMixin, TimestampMixin, Base):
    """پیوند هویت سراسری به یک مستأجر، همراه با نقشِ همان مستأجر.

    نقش اینجا می‌نشیند و نه روی User، چون یک نفر می‌تواند در یک کسب‌وکار حسابدار
    و در کسب‌وکار دیگر فقط بیننده باشد.
    """

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "tenant_id", name="uq_memberships_user_tenant"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | invited | disabled

    tenant: Mapped["Tenant"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(back_populates="memberships")  # noqa: F821
    role: Mapped["Role"] = relationship()  # noqa: F821


class PlatformAdmin(UUIDPKMixin, TimestampMixin, Base):
    """ادمین خودِ کوبیتا. جدا از RBAC مستأجر، عمداً."""

    __tablename__ = "platform_admins"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship()  # noqa: F821
