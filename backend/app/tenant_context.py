"""مستأجر جاری، و چسباندنش به تراکنش پایگاه‌داده.

**چرا ContextVar و نه متغیر ماژول:** هر درخواست باید مستأجر خودش را ببیند. متغیر
سراسری بین درخواست‌های هم‌زمان مشترک می‌شود و دقیقاً همان نشتی را می‌سازد که RLS
قرار بود جلویش را بگیرد.

**چرا after_begin و نه یک‌بار در ابتدای درخواست:** مقدار با SET LOCAL ست می‌شود که
به تراکنش محدود است. هر بار که تراکنش جدیدی شروع شود — از جمله بعد از هر commit —
مقدار از بین رفته و باید دوباره ست شود. این رویداد در شروع هر تراکنش شلیک می‌شود،
پس حتی اگر جایی وسط کار commit کند، تراکنش بعدی باز هم مستأجر درست را دارد.

**چرا SET LOCAL و نه SET:** SET ساده به کل اتصال می‌چسبد و اتصال به connection pool
برمی‌گردد. یعنی درخواست بعدی — که می‌تواند مال مستأجر دیگری باشد — همان مقدار را
به ارث می‌برد. این بدترین حالت شکست ممکن در این سیستم است.

**چرا set_config و نه رشته‌سازی:** SET LOCAL پارامتر bind نمی‌پذیرد، پس تنها راهش
درج مقدار داخل متن SQL بود. set_config(name, value, true) دقیقاً همان کار را می‌کند
ولی مقدار را به‌عنوان پارامتر می‌گیرد.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.tenancy import TENANT_SETTING

_current_tenant: ContextVar[UUID | None] = ContextVar("current_tenant", default=None)


def set_current_tenant(tenant_id: UUID | None) -> None:
    _current_tenant.set(tenant_id)


def get_current_tenant() -> UUID | None:
    return _current_tenant.get()


def require_current_tenant() -> UUID:
    tenant_id = _current_tenant.get()
    if tenant_id is None:
        raise RuntimeError("مستأجر جاری ست نشده — این مسیر نباید بدون زمینه‌ی مستأجر اجرا شود")
    return tenant_id


@contextmanager
def tenant_scope(db: Session, tenant_id: UUID | None):
    """مستأجر را برای یک بلوک ست می‌کند و روی همان تراکنشِ باز هم اعمالش می‌کند.

    ست کردن ContextVar به‌تنهایی کافی نیست وقتی تراکنش از قبل شروع شده: after_begin
    دیگر شلیک نمی‌شود، پس مقدار را همین‌جا هم روی اتصال جاری می‌نشانیم.
    """
    token = _current_tenant.set(tenant_id)
    try:
        apply_tenant_to_transaction(db, tenant_id)
        yield
    finally:
        _current_tenant.reset(token)


def apply_tenant_to_transaction(db: Session, tenant_id: UUID | None) -> None:
    db.execute(text("SELECT set_config(:k, :v, true)"), {"k": TENANT_SETTING, "v": str(tenant_id or "")})


@event.listens_for(Session, "after_begin")
def _bind_tenant_to_new_transaction(session, transaction, connection) -> None:
    tenant_id = _current_tenant.get()
    if tenant_id is None:
        return
    connection.execute(text("SELECT set_config(:k, :v, true)"), {"k": TENANT_SETTING, "v": str(tenant_id)})


@event.listens_for(Session, "before_flush")
def _stamp_tenant_on_new_rows(session, flush_context, instances) -> None:
    """مستأجر را روی هر ردیف جدید می‌نشاند.

    بدون این، هر سرویس باید دستی tenant_id بدهد و کافی بود یک جا فراموش شود تا
    نوشتن با خطای RLS شکست بخورد (یا بدتر، اگر روزی سیاست شل شود، ردیف بی‌صاحب
    بسازد). اینجا یک بار انجام می‌شود و برای هر ۳۴ مدل کار می‌کند.

    RLS همچنان لایه‌ی پشتیبان است نه جایگزین: اگر این مهر به هر دلیلی نخورد،
    WITH CHECK در پایگاه‌داده جلوی نوشتن را می‌گیرد.
    """
    tenant_id = _current_tenant.get()
    if tenant_id is None:
        return
    for obj in session.new:
        if hasattr(type(obj), "tenant_id") and getattr(obj, "tenant_id", None) is None:
            obj.tenant_id = tenant_id


def current_tenant_in_db(db: Session) -> str | None:
    """مقداری که پایگاه‌داده واقعاً می‌بیند — برای تست و عیب‌یابی."""
    return db.execute(text("SELECT current_setting(:k, true)"), {"k": TENANT_SETTING}).scalar()
