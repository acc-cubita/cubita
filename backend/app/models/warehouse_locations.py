"""موقعیتِ قرارگیری داخلِ انبار — راهرو/قفسه/طبقه.

تا مهاجرتِ ۰۱۷۲، کوبیتا هیچ مفهومی از «کجای انبار» نداشت: انبار بود و تمام.
برگه‌ی جمع‌آوری می‌توانست بگوید «۱۰۰ عدد شیر از بارِ B001» ولی نمی‌توانست بگوید
کجاست، و انباردار باید حفظ می‌بود.

`code` رشته‌ی آشنای خودِ انبار است («A-02-04»)؛ `aisle`/`rack`/`level` همان را
تفکیک‌شده نگه می‌دارند تا بعداً بشود مرتب یا گروه‌بندی کرد، ولی **هیچ‌کدام اجباری
نیستند**: انبارِ کوچک فقط یک کد می‌نویسد و بقیه را خالی می‌گذارد.
"""
import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class WarehouseLocation(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک محلِ مشخص داخلِ یک انبار."""

    __tablename__ = "warehouse_locations"

    #: کد در **همان انبار** یکتاست، نه در کلِ کسب‌وکار: «A-01» می‌تواند در دو
    #: انبار وجود داشته باشد و همین هم طبیعی است.
    __table_args__ = (
        UniqueConstraint("tenant_id", "warehouse_id", "code", name="uq_warehouse_locations_code"),
    )

    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    aisle: Mapped[str] = mapped_column(String(20), default="", server_default="")
    rack: Mapped[str] = mapped_column(String(20), default="", server_default="")
    level: Mapped[str] = mapped_column(String(20), default="", server_default="")
    #: غیرفعال یعنی «دیگر جای تازه این‌جا نگذار» — نه «خالی است». باری که روی یک
    #: موقعیتِ غیرفعال نشسته همان‌جا می‌ماند تا جابه‌جا شود.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")

    warehouse: Mapped["Warehouse"] = relationship()  # noqa: F821
